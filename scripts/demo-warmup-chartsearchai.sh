#!/usr/bin/env bash
# Prepare a configured product profile and demo patient's chart prefix for a
# steady-state UI recording. The canonical default remains E4B; DEMO_PROFILE_ID
# selects an explicit comparison profile without changing product defaults.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

set -a
# shellcheck disable=SC1091
. ./.env.chartsearch.example
if [ -f .env.chartsearch ]; then
  # shellcheck disable=SC1091
  . ./.env.chartsearch
fi
set +a

ROUTER_URL="${DEMO_ROUTER_URL:-http://127.0.0.1:8077}"
HUB_URL="${DEMO_HUB_URL:-http://127.0.0.1:${MED_AGENT_HUB_PORT:-18081}}"
OPENMRS_URL="${DEMO_OPENMRS_URL:-http://127.0.0.1:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs}"
PROFILE="${DEMO_PROFILE_ID:-}"
PATIENT="${E2E_PATIENT_UUID:-dd75c020-1691-11df-97a5-7038c432aabf}"
QUESTION="${DEMO_WARMUP_QUESTION:-In one short sentence, what was the most recent documented clinical visit?}"
USER="${E2E_USER:-admin}"
PASSWORD="${E2E_PASSWORD:-Admin123}"

curl -fsS --max-time 5 "${ROUTER_URL}/v1/models" >/dev/null
curl -fsS --max-time 5 "${HUB_URL}/health" >/dev/null
curl -fsS --max-time 10 -u "${USER}:${PASSWORD}" \
  "${OPENMRS_URL}/ws/rest/v1/session" >/dev/null

if [ -z "${PROFILE}" ]; then
  PROFILE="$(curl -fsS "${HUB_URL}/v1/models" \
    | python3 -c "import json,sys; defaults=[x for x in json.load(sys.stdin).get('data',[]) if x.get('visibility') == 'product' and x.get('available') and x.get('default')]; assert len(defaults) == 1, defaults; print(defaults[0]['id'])")"
fi

echo "Warming ${PROFILE} with patient ${PATIENT} through med-agent-hub to answer_done..."
python3 scripts/warm-hub-profile.py \
  --hub-url "${HUB_URL}/v1/chat/completions" \
  --profile "${PROFILE}" \
  --patient "${PATIENT}" \
  --question "${QUESTION}" \
  --mode answer \
  --output artifacts/chartsearchai-local/demo-warmup.json

echo "Clearing the visible ChartSearchAI session..."
curl -fsS --max-time 30 -u "${USER}:${PASSWORD}" \
  -H 'Content-Type: application/json' \
  -d "{\"patient\":\"${PATIENT}\"}" \
  "${OPENMRS_URL}/ws/rest/v1/chartsearchai/chat/new" >/dev/null

echo "Ready to record the warm ${PROFILE} product path."
