#!/usr/bin/env bash
# Engine-parity mode (spec: specs/artifacts/planning/engine-parity-instrument.md, AC-1/D1/D2):
# route BOTH providers' engine traffic through per-arm tap ingresses onto ONE shared
# llama-router model, then verify the shared-engine claim instead of assuming it.
#
#   bundled: chartsearchai.llm.engine=remote -> host.docker.internal:${BUNDLED_TAP_PORT} -> router
#   hub:     MED_AGENT_LLM_BASE_URL          -> host.docker.internal:${HUB_TAP_PORT}     -> router
#
# Requires the dual-provider stack up (make dual-provider-up) and the llama-router
# serving ${PARITY_MODEL_ID}. Idempotent: reuses a tap that is already listening.
# After this, run:  make parity-engine-probe PATIENT=<uuid> QUESTION='<q>'
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "${ROOT}"
# shellcheck source=scripts/openmrs-settings-lib.sh
. scripts/openmrs-settings-lib.sh

PARITY_MODEL_ID="${PARITY_MODEL_ID:-gemma-e4b}"
BUNDLED_TAP_PORT="${BUNDLED_TAP_PORT:-8078}"
HUB_TAP_PORT="${HUB_TAP_PORT:-8079}"
ROUTER_URL="${ROUTER_URL:-http://127.0.0.1:8077}"
CAPTURE_DIR="artifacts/parity-engine/captures"
SOURCE_ENV="artifacts/chartsearchai-local/querystore-service.env"
HUB_CONTAINER="harness-med-agent-hub"

say() { printf '\n== %s ==\n' "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

tap_relays() { # does a tap ingress relay the router's model list?
  curl -fsS -m5 "http://127.0.0.1:$1/v1/models" 2>/dev/null | grep -q "\"${PARITY_MODEL_ID}\""
}

say "preflight: shared engine ${ROUTER_URL} must serve ${PARITY_MODEL_ID}"
curl -fsS -m5 "${ROUTER_URL}/v1/models" 2>/dev/null | grep -q "\"${PARITY_MODEL_ID}\"" \
  || fail "llama-router at ${ROUTER_URL} is not serving ${PARITY_MODEL_ID} (make llama-router-up)"

say "engine tap: bundled=:${BUNDLED_TAP_PORT} hub=:${HUB_TAP_PORT} -> ${ROUTER_URL}"
if tap_relays "${BUNDLED_TAP_PORT}" && tap_relays "${HUB_TAP_PORT}"; then
  echo "  tap already up and relaying — reusing"
else
  mkdir -p logs "$(dirname "${CAPTURE_DIR}")"
  nohup python3 scripts/engine-tap.py \
    --arm "bundled=${BUNDLED_TAP_PORT}" --arm "hub=${HUB_TAP_PORT}" \
    --upstream "${ROUTER_URL}" --capture-dir "${CAPTURE_DIR}" \
    > logs/engine-tap.log 2>&1 &
  echo $! > artifacts/parity-engine/tap.pid
  for _ in $(seq 1 10); do
    tap_relays "${BUNDLED_TAP_PORT}" && tap_relays "${HUB_TAP_PORT}" && break
    sleep 1
  done
  tap_relays "${BUNDLED_TAP_PORT}" || fail "bundled tap ingress :${BUNDLED_TAP_PORT} not relaying (logs/engine-tap.log)"
  tap_relays "${HUB_TAP_PORT}" || fail "hub tap ingress :${HUB_TAP_PORT} not relaying (logs/engine-tap.log)"
  echo "  tap started (pid $(cat artifacts/parity-engine/tap.pid)), capture -> ${CAPTURE_DIR}"
fi

say "bundled arm: engine=remote through the bundled tap ingress"
set_openmrs_property "chartsearchai.llm.engine" "remote"
set_openmrs_property "chartsearchai.llm.remote.endpointUrl" \
  "http://host.docker.internal:${BUNDLED_TAP_PORT}/v1/chat/completions"
set_openmrs_property "chartsearchai.llm.remote.modelName" "${PARITY_MODEL_ID}"

say "hub arm: LLM_BASE_URL through the hub tap ingress (recreate med-agent-hub)"
[ -f "${SOURCE_ENV}" ] || fail "${SOURCE_ENV} missing — run scripts/provision-querystore-service-account.py (or make dual-provider-up) first"
# shellcheck disable=SC1090
set -a; . "${SOURCE_ENV}"; set +a
export QUERYSTORE_BASE_URL QUERYSTORE_USERNAME QUERYSTORE_PASSWORD
MED_AGENT_LLM_BASE_URL="http://host.docker.internal:${HUB_TAP_PORT}" make med-agent-hub-up

say "AC-1 checks: both arms verifiably on the same engine"
checks=0
gp() { # read one GP value via REST
  openmrs_curl -fsS -u "${OPENMRS_SETTINGS_USER}:${OPENMRS_SETTINGS_PASS}" \
    "${OPENMRS_SETTINGS_BASE_URL}/ws/rest/v1/systemsetting/$1" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('value',''))"
}
check() { # check <label> <actual> <expected-substring>
  if printf '%s' "$2" | grep -q "$3"; then
    echo "  PASS $1: $2"
  else
    echo "  FAIL $1: got '$2', want match '$3'"; checks=$((checks + 1))
  fi
}
check "bundled engine GP" "$(gp chartsearchai.llm.engine)" "^remote$"
check "bundled endpoint GP" "$(gp chartsearchai.llm.remote.endpointUrl)" ":${BUNDLED_TAP_PORT}/"
check "bundled model GP" "$(gp chartsearchai.llm.remote.modelName)" "^${PARITY_MODEL_ID}$"
check "hub LLM_BASE_URL" \
  "$(docker exec "${HUB_CONTAINER}" sh -c 'echo "$LLM_BASE_URL"' 2>/dev/null)" ":${HUB_TAP_PORT}$"
check "bundled tap relays model" \
  "$(curl -fsS -m5 "http://127.0.0.1:${BUNDLED_TAP_PORT}/v1/models" | grep -o "\"${PARITY_MODEL_ID}\"" | head -1)" "${PARITY_MODEL_ID}"
check "hub tap relays model" \
  "$(curl -fsS -m5 "http://127.0.0.1:${HUB_TAP_PORT}/v1/models" | grep -o "\"${PARITY_MODEL_ID}\"" | head -1)" "${PARITY_MODEL_ID}"
check "providers registry" \
  "$(openmrs_curl -fsS -u "${OPENMRS_SETTINGS_USER}:${OPENMRS_SETTINGS_PASS}" \
      "${OPENMRS_SETTINGS_BASE_URL}/ws/rest/v1/chartsearchai/providers" 2>/dev/null \
      | python3 -c "import sys,json; print(','.join(sorted(p['id'] for p in json.load(sys.stdin)['providers'])))")" \
  "bundled,hub"

[ "${checks}" -eq 0 ] || fail "${checks} AC-1 check(s) failed"
echo ""
echo "engine-parity mode up: both arms -> ${ROUTER_URL} (${PARITY_MODEL_ID})."
echo "next: make parity-engine-probe PATIENT=<uuid> QUESTION='<question>'"
