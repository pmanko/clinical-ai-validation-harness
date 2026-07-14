#!/usr/bin/env bash
# scripts/validate-preflight.sh
# Make the stack RUN-READY for `make validate-run SET=<set>`, in one command.
#
# A validate run silently produces garbage (empty charts → wrong answers) if any
# piece is down or un-indexed, and the bring-up is fiddly: Elasticsearch is
# profile-gated (off by default), the proxy serves :8088, and the hub +
# llama-router are separate processes. This script brings up every component a
# run needs and verifies each piece answers — surfacing a down / mis-indexed
# component as a clear failure up front, not as bad data mid-run.
#
# The querystore self-bootstraps the WHOLE corpus on boot (GP
# querystore.bootstrap.autostart=true), so preflight does NOT back-fill anything:
# it READ-ONLY validates the corpus index via GET /querystore/drift (per-type
# coreCount/indexedCount/drift) and surfaces an un-bootstrapped / under-indexed
# store as a failure, telling the operator to restart the backend (autostart) or
# run the fallback reindex {scope:all} — never masking it with a silent backfill.
#
# Usage:
#   scripts/validate-preflight.sh <comparison-set-id> [low|med|high]
# (tier picks the llama-router co-residency cap; default med.)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
# shellcheck disable=SC1091
. "${ROOT}/scripts/_preflight.sh"; harness_preflight || exit 1

SET="${1:?usage: validate-preflight.sh <comparison-set-id> [low|med|high]}"
TIER="${2:-${LLAMA_ROUTER_TIER:-med}}"
case "${TIER}" in
  low|med) ROUTER_MODELS_MAX=4 ;;
  high) ROUTER_MODELS_MAX=1 ;;
  *) echo "ERROR: router tier must be low|med|high (got: ${TIER})" >&2; exit 1 ;;
esac
COMPOSE="compose/openmrs-2.8-refapp.yml"
SET_FILE="datasets/validation/comparison_sets/${SET}.json"
[ -f "${SET_FILE}" ] || { echo "ERROR: no comparison set ${SET_FILE}" >&2; exit 1; }

echo "==> [0/5] validate comparison execution contract"
uv run harness-cli validate check "${SET}" --data-root datasets/validation

# .env.chartsearch carries OPENMRS_REFAPP_TAG (nightly-chartsearch) + the proxy ports;
# without it the frontend/gateway downgrade to stock and the SPA 404s.
[ -f ./.env.chartsearch ] || { echo "ERROR: ./.env.chartsearch not found — provision it (see scripts/chartsearch-configure.sh) before running preflight." >&2; exit 1; }
set -a; . ./.env.chartsearch; set +a
SOURCE_ENV="${ROOT}/artifacts/chartsearchai-local/querystore-service.env"
if [ ! -s "${SOURCE_ENV}" ]; then
  echo "ERROR: ${SOURCE_ENV} is missing — run 'make chartsearchai-local' to provision the least-privileged patient source" >&2
  exit 1
fi
set -a; . "${SOURCE_ENV}"; set +a
HUB_BUILD_REVISION="$(git -C targets/med-agent-hub rev-parse HEAD)"
export HUB_BUILD_REVISION
PORT="${HARNESS_PROXY_HTTP_PORT:-8088}"
AUTH="${CHARTSEARCH_ADMIN_USER:-admin}:${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}"
BASE="http://localhost:${PORT}/openmrs"

echo "==> [1/5] core stack (proxy/db/frontend/gateway/backend)"
./scripts/stack-up.sh --wait

echo "==> [2/5] elasticsearch (querystore CQRS read store — part of the default stack)"
docker compose -f "${COMPOSE}" up -d elasticsearch
for i in $(seq 1 24); do
  curl -fsS --max-time 4 "http://localhost:${QUERYSTORE_ES_PORT:-9200}/_cluster/health" 2>/dev/null \
    | grep -qE '"status":"(green|yellow)"' && { echo "    ES ready"; break; }
  sleep 5
done

echo "==> [3/5] med-agent-hub + llama-router (tier ${TIER})"
make med-agent-hub-up
if ! curl -fsS --max-time 4 http://localhost:8077/v1/models >/dev/null 2>&1; then
  echo "    starting llama-router (background)"
  LLAMA_ROUTER_MODELS_MAX="${ROUTER_MODELS_MAX}" nohup ./scripts/llama-router-up.sh > /tmp/llama-router.log 2>&1 &
  for i in $(seq 1 30); do
    curl -fsS --max-time 4 http://localhost:8077/v1/models >/dev/null 2>&1 && break; sleep 2
  done
fi

echo "==> [4/5] validate querystore corpus index (read-only GET /querystore/drift)"
# The querystore self-bootstraps the whole corpus on boot, so the index is a shared
# baseline — preflight VALIDATES it rather than back-filling. /querystore/drift is
# read-only: per resourceType it reports coreCount (rows in the clinical DB),
# indexedCount (docs in ES), and drift = coreCount - indexedCount. A correctly
# bootstrapped store has indexedCount ≈ coreCount; a small STABLE positive drift is
# normal (the serializer legitimately drops obs-group parents etc.) and PASSES. We
# FAIL when a type is empty-but-expected (indexedCount==0 while coreCount>0) or badly
# under-indexed (drift > 5% of coreCount AND > 50 absolute) — that means the corpus
# is un-bootstrapped / broken and a run would get empty charts. Surfaced, never masked.
# Fetch /drift, retrying a few times: right after the backend/hub come up it can return a
# transient empty / non-JSON body (proxy blip, GC pause) before settling. We accept only a
# well-formed {"types":...} payload; persistent failure across all tries → querystore/ES not up.
DRIFT_JSON=""
for i in $(seq 1 6); do
  DRIFT_JSON="$(curl -fsS --max-time 30 -u "${AUTH}" "${BASE}/ws/rest/v1/querystore/drift" 2>/dev/null || true)"
  case "${DRIFT_JSON}" in
    '{"types":'*) break ;;
    *) DRIFT_JSON=""; [ "$i" -lt 6 ] && sleep 3 ;;
  esac
done
if [ -z "${DRIFT_JSON}" ]; then
  echo "ERROR: querystore/ES not up — GET ${BASE}/ws/rest/v1/querystore/drift returned no valid" >&2
  echo "       drift payload after several tries. Bring up the backend + Elasticsearch (this" >&2
  echo "       script's [1]+[2]) before a run." >&2
  exit 1
fi
DRIFT_REPORT="$(printf '%s' "${DRIFT_JSON}" | python3 scripts/check-querystore-drift.py)" \
  && DRIFT_RC=0 || DRIFT_RC=$?
# Always print the per-type table (no truncation), pass or fail.
[ -n "${DRIFT_REPORT}" ] && printf '%s\n' "${DRIFT_REPORT}"
if [ "${DRIFT_RC}" -ne 0 ]; then
  echo "ERROR: querystore not bootstrapped / under-indexed (see types flagged FAIL above)." >&2
  echo "       A run on '${SET}' would get EMPTY/partial charts. Fix the corpus index, do NOT" >&2
  echo "       proceed: restart the backend so it re-bootstraps (autostart), or run:" >&2
  echo "         make querystore-reindex" >&2
  exit 1
fi
echo "    corpus index OK — every type satisfies the shared validation drift policy"

echo "==> [4b/5] verify live ledger dates match committed validation fixtures"
if [ -z "${QUERYSTORE_USERNAME:-}" ] || [ -z "${QUERYSTORE_PASSWORD:-}" ]; then
  echo "ERROR: QUERYSTORE_USERNAME and QUERYSTORE_PASSWORD are required for corpus alignment" >&2
  exit 1
fi
python3 scripts/verify-validation-corpus.py \
  --set "${SET}" \
  --endpoint "${BASE}/ws/rest/v1/querystore/patientrecord" \
  --username "${QUERYSTORE_USERNAME}" \
  --password "${QUERYSTORE_PASSWORD}"

echo "==> [5/5] verify everything answers"
fail=0
chk() { printf '    %-26s %s\n' "$1" "$2"; [ "$3" = ok ] || fail=1; }
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "${BASE}/" || true)
chk "proxy :${PORT}" "HTTP ${code}" "$([ "$code" = 200 ] && echo ok)"
rcount=$(curl -s --max-time 6 http://localhost:8077/v1/models | python3 -c 'import sys,json;print(len(json.load(sys.stdin).get("data",[])))' 2>/dev/null || echo 0)
chk "llama-router :8077" "${rcount} models" "$([ "${rcount:-0}" -gt 0 ] && echo ok)"
hub=$(docker inspect -f '{{.State.Health.Status}}' harness-med-agent-hub 2>/dev/null || echo missing)
chk "med-agent-hub" "${hub}" "$([ "$hub" = healthy ] && echo ok)"
SOURCE_PROBE_PATIENT="$(python3 - "${SET_FILE}" <<'PY'
import json, pathlib, sys
root = pathlib.Path("datasets/validation")
comparison = json.loads(pathlib.Path(sys.argv[1]).read_text())
scenario = json.loads((root / "scenarios" / f"{comparison['scenario_ids'][0]}.json").read_text())
print(scenario["patient_ref"])
PY
)"
if docker exec -i -e SOURCE_PROBE_PATIENT="${SOURCE_PROBE_PATIENT}" harness-med-agent-hub \
    python - <<'PY'
import base64
import json
import os
import urllib.parse
import urllib.request

required = ("QUERYSTORE_BASE_URL", "QUERYSTORE_USERNAME", "QUERYSTORE_PASSWORD")
assert all(os.environ.get(name) for name in required)
query = urllib.parse.urlencode(
    {"patient": os.environ["SOURCE_PROBE_PATIENT"], "limit": 1}
)
url = (
    os.environ["QUERYSTORE_BASE_URL"].rstrip("/")
    + "/ws/rest/v1/querystore/patientrecord?"
    + query
)
credentials = (
    os.environ["QUERYSTORE_USERNAME"] + ":" + os.environ["QUERYSTORE_PASSWORD"]
).encode()
request = urllib.request.Request(
    url,
    headers={"Authorization": "Basic " + base64.b64encode(credentials).decode()},
)
with urllib.request.urlopen(request, timeout=30) as response:
    payload = json.load(response)
assert isinstance(payload.get("results"), list)
PY
then
  chk "hub context source" "authenticated patient record" ok
else
  chk "hub context source" "missing config, auth failure, or empty response" fail
fi
qs=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -u "${AUTH}" "${BASE}/ws/rest/v1/querystore/drift" || true)
chk "querystore /drift" "HTTP ${qs}" "$([ "$qs" = 200 ] && echo ok)"
# corpus index already validated per-type in [4/5] (drift-gated) — not re-checked here.

[ "$fail" = 0 ] && echo "✅ preflight OK — stack run-ready for: make validate-run SET=${SET}" \
  || { echo "❌ preflight: one or more components not ready (see above)" >&2; exit 1; }
