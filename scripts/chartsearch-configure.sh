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
  # Update the existing (registered) setting. If it has no row yet — e.g.
  # querystore.backend, which the module reads with a code default instead of
  # registering a global property — fall back to creating it via the collection
  # endpoint.
  if ! rc -fsS -o /dev/null \
      -u "${ADMIN_USER}:${ADMIN_PASS}" \
      -H "Content-Type: application/json" \
      -X POST "${BASE_URL}/ws/rest/v1/systemsetting/${name}" \
      -d "{\"value\": \"${value}\"}" 2>/dev/null; then
    rc -fsS -o /dev/null \
      -u "${ADMIN_USER}:${ADMIN_PASS}" \
      -H "Content-Type: application/json" \
      -X POST "${BASE_URL}/ws/rest/v1/systemsetting" \
      -d "{\"property\": \"${name}\", \"value\": \"${value}\"}"
  fi
}

echo "Configuring chartsearchai LLM globals at ${BASE_URL}:"
set_property "chartsearchai.llm.engine"             "${ENGINE}"
set_property "chartsearchai.llm.remote.endpointUrl" "${ENDPOINT}"
set_property "chartsearchai.llm.remote.modelName"   "${MODEL}"

# Querystore (CQRS read-store) retrieval. On by default; set
# CHARTSEARCH_QUERYSTORE_ENABLED=false to fall back to chartsearchai's in-process
# retrieval. The embedding model + vocab are the files backend-init.sh downloads
# into /openmrs/data/chartsearchai (paths relative to the app data dir); both are
# read per-query, so setting them here (post-startup, after the backend is
# healthy) takes effect on the next search with no restart.
#
# querystore.backend is intentionally NOT set here: QueryStoreActivator wires the
# store once at module startup, so a post-startup change wouldn't take effect
# without a restart. The single-step path therefore uses the module default
# (mysql, wired at startup); it serves identically to lucene.
QUERYSTORE_ENABLED="${CHARTSEARCH_QUERYSTORE_ENABLED:-true}"
echo ""
echo "Configuring querystore (enabled=${QUERYSTORE_ENABLED}):"
set_property "chartsearchai.querystore.enabled"     "${QUERYSTORE_ENABLED}"
if [ "${QUERYSTORE_ENABLED}" = "true" ]; then
  set_property "querystore.embedding.modelFilePath" "chartsearchai/model.onnx"
  set_property "querystore.embedding.vocabFilePath" "chartsearchai/vocab.txt"
fi

echo ""
echo "Module status:"
# Informational only — the GPs above are already set. Don't let a transient
# status-read (or the custom-rep parse) fail the whole configure/deploy.
if ! rc -fsS -u "${ADMIN_USER}:${ADMIN_PASS}" \
     "${BASE_URL}/ws/rest/v1/module/chartsearchai?v=custom:(uuid,started,version)" 2>/dev/null \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  chartsearchai {d.get('version','?')} started={d.get('started')}\")" 2>/dev/null; then
  echo "  (module status unavailable right now — GPs above are set regardless)"
fi
