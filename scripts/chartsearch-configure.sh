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

# Load env file if present. An explicitly-exported CHARTSEARCH_LLM_ENGINE must win over the
# file default, so capture it before sourcing and restore it after.
_OVERRIDE_ENGINE="${CHARTSEARCH_LLM_ENGINE:-}"
if [ -f .env.chartsearch ]; then
  set -a
  # shellcheck disable=SC1091
  . .env.chartsearch
  set +a
fi
if [ -n "${_OVERRIDE_ENGINE}" ]; then
  CHARTSEARCH_LLM_ENGINE="${_OVERRIDE_ENGINE}"
fi

# CHARTSEARCH_EXEC: run every REST call inside a container (the backend) via
# `docker exec`, hitting localhost:8080 directly. On the cloud the host can only
# reach the backend through Caddy, which serves the public domain on :80 and
# redirects to HTTPS — host-side curls get 308/reset. Running inside the backend
# container (localhost:8080) is the reliable path. Empty = plain host curl (local).
EXEC="${CHARTSEARCH_EXEC:-}"
if [ -n "${EXEC}" ]; then
  BASE_URL="${CHARTSEARCH_BASE_URL:-http://localhost:8080/openmrs}"
else
  BASE_URL="${CHARTSEARCH_BASE_URL:-http://localhost:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs}"
fi
ADMIN_USER="${CHARTSEARCH_ADMIN_USER:-admin}"
ADMIN_PASS="${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}"

# curl wrapper: runs inside CHARTSEARCH_EXEC's container when set, else on the host.
rc() { if [ -n "${EXEC}" ]; then docker exec "${EXEC}" curl "$@"; else curl "$@"; fi; }

ENGINE="${CHARTSEARCH_LLM_ENGINE:-remote}"
if [ "${ENGINE}" != "remote" ]; then
  echo "error: CHARTSEARCH_LLM_ENGINE=${ENGINE} is not supported." >&2
  echo "  chartsearchai now relays chat to an OpenAI-compatible endpoint;" >&2
  echo "  local serving should run behind that endpoint, usually med-agent-hub." >&2
  echo "  Unset CHARTSEARCH_LLM_ENGINE" >&2
  echo "  or set it to 'remote' in .env.chartsearch." >&2
  exit 1
fi
ENDPOINT="${CHARTSEARCH_REMOTE_ENDPOINT_URL:?must be set in .env.chartsearch}"
MODEL="${CHARTSEARCH_REMOTE_MODEL_NAME:-}"

# Auto-discover model if not set: derive the models endpoint from the chat
# endpoint (replace /chat/completions with /models) and pick the first id.
if [ -z "${MODEL}" ]; then
  MODELS_URL="${ENDPOINT%/chat/completions}/models"
  echo "Auto-discovering model from ${MODELS_URL}..."
  MODEL=$(rc -fsS "${MODELS_URL}" 2>/dev/null \
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
  # Build the request bodies with python so values that themselves contain
  # JSON/quotes (e.g. the endpoint registry) are escaped correctly. Simple
  # string values are unaffected.
  local body body_create
  body=$(python3 -c "import json,sys; print(json.dumps({'value': sys.argv[1]}))" "${value}")
  body_create=$(python3 -c "import json,sys; print(json.dumps({'property': sys.argv[1], 'value': sys.argv[2]}))" "${name}" "${value}")
  # Update the existing (registered) setting. If it has no row yet — e.g.
  # querystore.backend, which the module reads with a code default instead of
  # registering a global property — fall back to creating it via the collection
  # endpoint.
  if ! rc -fsS -o /dev/null \
      -u "${ADMIN_USER}:${ADMIN_PASS}" \
      -H "Content-Type: application/json" \
      -X POST "${BASE_URL}/ws/rest/v1/systemsetting/${name}" \
      -d "${body}" 2>/dev/null; then
    rc -fsS -o /dev/null \
      -u "${ADMIN_USER}:${ADMIN_PASS}" \
      -H "Content-Type: application/json" \
      -X POST "${BASE_URL}/ws/rest/v1/systemsetting" \
      -d "${body_create}"
  fi
}

echo "Configuring chartsearchai LLM globals at ${BASE_URL}:"
set_property "chartsearchai.llm.engine"             "${ENGINE}"
set_property "chartsearchai.llm.remote.endpointUrl" "${ENDPOINT}"
set_property "chartsearchai.llm.remote.modelName"   "${MODEL}"

# Optional endpoint registry for the picker's per-endpoint sections (LM Studio,
# Med Agent Hub, ...). JSON array of {label,url}; single-quote it in
# .env.chartsearch so the shell preserves the inner quotes. Unset -> the picker
# falls back to a single section from endpointUrl above.
ENDPOINTS_JSON="${CHARTSEARCH_REMOTE_ENDPOINTS:-}"
if [ -n "${ENDPOINTS_JSON}" ]; then
  set_property "chartsearchai.llm.remote.endpoints" "${ENDPOINTS_JSON}"
fi

# Querystore (CQRS read-store) retrieval model. chartsearchai no longer has an
# in-process retrieval fallback; querystore owns indexing and chart projection.
# The embedding model + vocab are the files backend-init.sh downloads into
# /openmrs/data/chartsearchai (paths relative to the app data dir).
echo ""
echo "Configuring querystore:"
set_property "querystore.embedding.modelFilePath" "chartsearchai/model.onnx"
set_property "querystore.embedding.vocabFilePath" "chartsearchai/vocab.txt"

echo ""
echo "Module status:"
# Informational only — the GPs above are already set. Don't let a transient
# status-read (or the custom-rep parse) fail the whole configure/deploy.
if ! rc -fsS -u "${ADMIN_USER}:${ADMIN_PASS}" \
     "${BASE_URL}/ws/rest/v1/module/chartsearchai?v=custom:(uuid,started,version)" 2>/dev/null \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  chartsearchai {d.get('version','?')} started={d.get('started')}\")" 2>/dev/null; then
  echo "  (module status unavailable right now — GPs above are set regardless)"
fi
