#!/usr/bin/env bash
# Configure chartsearchai LLM global properties on the running backend.
#
# Reads endpoint + model + engine from .env.chartsearch (or current env). Sets
# 3 DB-backed global properties via REST POST. The API key is injected
# separately via the OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY env var in
# the backend compose service (runtime properties, not a DB global, for
# security).
#
# If CHARTSEARCH_REMOTE_MODEL_NAME is empty, probes the LLM endpoint's
# /v1/models and auto-picks the first model identifier (LM Studio JIT-loads
# it on first inference call).
#
# Idempotent — POST to /ws/rest/v1/systemsetting/<name> updates the existing
# module-default value that chartsearchai's activator registered at startup.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# Load env file if present.
if [ -f .env.chartsearch ]; then
  set -a
  # shellcheck disable=SC1091
  . .env.chartsearch
  set +a
fi

BASE_URL="${CHARTSEARCH_BASE_URL:-http://localhost:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs}"
ADMIN_USER="${CHARTSEARCH_ADMIN_USER:-admin}"
ADMIN_PASS="${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}"

ENGINE="${CHARTSEARCH_LLM_ENGINE:-remote}"
ENDPOINT="${CHARTSEARCH_REMOTE_ENDPOINT_URL:?must be set in .env.chartsearch}"
MODEL="${CHARTSEARCH_REMOTE_MODEL_NAME:-}"

# Auto-discover model if not set: derive the models endpoint from the chat
# endpoint (replace /chat/completions with /models) and pick the first id.
if [ -z "${MODEL}" ]; then
  MODELS_URL="${ENDPOINT%/chat/completions}/models"
  echo "Auto-discovering model from ${MODELS_URL}..."
  MODEL=$(curl -fsS "${MODELS_URL}" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); ms=d.get('data',[]); print(ms[0]['id']) if ms else sys.exit('no models loaded — load one in LM Studio first')" \
    || true)
  if [ -z "${MODEL}" ]; then
    echo "error: could not auto-discover model from ${MODELS_URL}"
    echo "  Set CHARTSEARCH_REMOTE_MODEL_NAME in .env.chartsearch, or load a model in LM Studio."
    exit 1
  fi
  echo "  picked: ${MODEL}"
fi

set_property() {
  local name="$1"
  local value="$2"
  echo "  ${name} = ${value}"
  curl -fsS -o /dev/null \
    -u "${ADMIN_USER}:${ADMIN_PASS}" \
    -H "Content-Type: application/json" \
    -X POST "${BASE_URL}/ws/rest/v1/systemsetting/${name}" \
    -d "{\"value\": \"${value}\"}"
}

echo "Configuring chartsearchai LLM globals at ${BASE_URL}:"
set_property "chartsearchai.llm.engine"             "${ENGINE}"
set_property "chartsearchai.llm.remote.endpointUrl" "${ENDPOINT}"
set_property "chartsearchai.llm.remote.modelName"   "${MODEL}"

echo ""
echo "Module status:"
curl -fsS -u "${ADMIN_USER}:${ADMIN_PASS}" \
  "${BASE_URL}/ws/rest/v1/module/chartsearchai?v=custom:(uuid,started,version)" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  chartsearchai {d.get('version','?')} started={d.get('started')}\")"
