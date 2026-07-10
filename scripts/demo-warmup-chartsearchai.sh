#!/usr/bin/env bash
# Preflight warmup for the ChartSearchAI demo recording. Warms the ACTUAL demo path
# — the host llama-router raw models AND the med-agent-hub staged-answer path (via
# ChartSearchAI /chat) — then blanks the visible chat, so the recorded first answer
# reflects the warm, steady-state experience instead of a cold JIT model load.
#
# Why there is no module warmup here: chartsearchai no longer owns an embedded LLM
# process or prompt cache, and the removed module warmup endpoint does not touch
# med-agent-hub or llama-router. This script warms the serving side explicitly
# through the real request path.
#
# Reachability (grounded):
#   - llama-router raw models: host :8077          (scripts/llama-router-up.sh)
#   - med-agent-hub:           med-agent-hub:8080  (in the docker net only, NOT host-exposed)
#                              -> warmed THROUGH ChartSearchAI /chat, which runs in the
#                                 OpenMRS backend container and can reach it.
#   - OpenMRS REST:            harness-proxy on host :8088 (tests/e2e/playwright.config.ts)
#
# Run it immediately BEFORE recording the Playwright video:
#   scripts/demo-warmup-chartsearchai.sh && \
#     E2E_VIDEO=on yarn --cwd tests/e2e test chartsearchai-staged-validation

set -uo pipefail   # not -e: one failed warm should not abort the rest of the preflight

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# --- config (override via env) ---------------------------------------------------
ROUTER_URL="${DEMO_ROUTER_URL:-http://localhost:8077}"
OPENMRS_URL="${DEMO_OPENMRS_URL:-http://localhost:8088}"
HUB_ENDPOINT="${DEMO_HUB_ENDPOINT:-http://med-agent-hub:8080/v1/chat/completions}"
HUB_CONTAINER="${DEMO_HUB_CONTAINER:-harness-med-agent-hub}"
E2E_USER="${E2E_USER:-admin}"
E2E_PASSWORD="${E2E_PASSWORD:-Admin123}"
PATIENT="${E2E_PATIENT_UUID:-dd75c020-1691-11df-97a5-7038c432aabf}"
QUESTION="${DEMO_QUESTION:-In one short sentence, what was the most recent documented clinical visit?}"
DEMO_MODEL="${DEMO_MODEL_NAME:-answer:gemma-4-12b@synthesis-answer~enforce~temp0}"
# Raw router models behind the demo model: the writer (gemma-4-12b) and the staged
# answer validator (qwen2.5-14b). Warming both makes the whole staged path warm.
RAW_MODELS="${DEMO_RAW_MODELS:-gemma-4-12b,qwen2.5-14b}"

REST="${OPENMRS_URL}/openmrs/ws/rest/v1/chartsearchai"
CHAT_BODY_FILE="$(mktemp -t demo-warmup-chat.XXXXXX)"
trap 'rm -f "${CHAT_BODY_FILE}"' EXIT

say()  { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

# --- 1. health ------------------------------------------------------------------
say "== health =="
curl -sf --max-time 5 "${ROUTER_URL}/v1/models" >/dev/null \
  && say "  llama-router ${ROUTER_URL}: OK" \
  || fail "llama-router ${ROUTER_URL} not reachable (start it: scripts/llama-router-up.sh)"

curl -sf --max-time 10 -u "${E2E_USER}:${E2E_PASSWORD}" \
  "${OPENMRS_URL}/openmrs/ws/rest/v1/session" >/dev/null \
  && say "  OpenMRS REST ${OPENMRS_URL}: OK" \
  || fail "OpenMRS REST ${OPENMRS_URL} not reachable / auth failed"

hub_health="$(docker inspect -f '{{.State.Health.Status}}' "${HUB_CONTAINER}" 2>/dev/null || echo missing)"
say "  med-agent-hub (${HUB_CONTAINER}): ${hub_health}"
[ "${hub_health}" = "healthy" ] || say "  warn: hub not reporting healthy — the /chat warm below will surface any real problem"

# --- 2. warm the raw llama-router models ---------------------------------------
say ""
say "== warm raw llama-router models =="
IFS=',' read -ra MODEL_LIST <<<"${RAW_MODELS}"
for raw in "${MODEL_LIST[@]}"; do
  model="$(echo "${raw}" | xargs)"
  [ -z "${model}" ] && continue
  code_time="$(curl -s -o /dev/null -w '%{http_code} %{time_total}' --max-time 300 \
    "${ROUTER_URL}/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}],\"max_tokens\":1}")"
  say "  ${model}: HTTP ${code_time%% *}, ${code_time##* }s"
done

# --- 3. warm the demo answer path (ChartSearchAI /chat -> med-agent-hub) --------
say ""
say "== warm demo answer path (ChartSearchAI /chat -> med-agent-hub) =="

chat_new() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 30 -u "${E2E_USER}:${E2E_PASSWORD}" \
    -H 'Content-Type: application/json' \
    -d "{\"patient\":\"${PATIENT}\"}" "${REST}/chat/new"
}

say "  /chat/new (clear session before warm) -> HTTP $(chat_new)"

warm_time="$(curl -s -o "${CHAT_BODY_FILE}" -w '%{http_code} %{time_total}' --max-time 300 \
  -u "${E2E_USER}:${E2E_PASSWORD}" -H 'Content-Type: application/json' \
  -d "{\"patient\":\"${PATIENT}\",\"question\":\"${QUESTION}\",\"endpointUrl\":\"${HUB_ENDPOINT}\",\"modelName\":\"${DEMO_MODEL}\"}" \
  "${REST}/chat")"
say "  /chat warm (${DEMO_MODEL}): HTTP ${warm_time%% *}, ${warm_time##* }s"

# Report whether the warm produced a substantive answer (mirrors the harness's bad-answer guard).
answer_len="$(python3 - "${CHAT_BODY_FILE}" <<'PY' 2>/dev/null || echo 0
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(0); sys.exit()
ans = (d.get("answer") or d.get("response", {}).get("answer") or "") if isinstance(d, dict) else ""
print(len(ans.strip()))
PY
)"
if [ "${answer_len:-0}" -gt 0 ] 2>/dev/null; then
  say "  warm answer: ${answer_len} chars (substantive — path is warm)"
else
  say "  warn: warm /chat returned no answer text — inspect ${REST}/chat manually before recording"
fi

say "  /chat/new (blank the visible demo chat) -> HTTP $(chat_new)"

say ""
say "Warm. Record now — e.g.:"
say "  E2E_VIDEO=on yarn --cwd tests/e2e test chartsearchai-staged-validation"
