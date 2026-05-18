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

# Load env file if present. Sourcing with `set -a` would clobber env vars
# passed on the command line (the obvious "override the file" path), so we
# capture overrides first and restore them afterwards. Result: precedence is
# command-line env > .env.chartsearch > built-in defaults.
__OVR_MODEL="${CHARTSEARCH_REMOTE_MODEL_NAME:-}"
__OVR_ENDPOINT="${CHARTSEARCH_REMOTE_ENDPOINT_URL:-}"
__OVR_ENGINE="${CHARTSEARCH_LLM_ENGINE:-}"
__OVR_BASE_URL="${CHARTSEARCH_BASE_URL:-}"
__OVR_CTX="${CHARTSEARCH_CONTEXT_LENGTH:-}"
if [ -f .env.chartsearch ]; then
  set -a
  # shellcheck disable=SC1091
  . .env.chartsearch
  set +a
fi
[ -n "${__OVR_MODEL}" ]    && CHARTSEARCH_REMOTE_MODEL_NAME="${__OVR_MODEL}"
[ -n "${__OVR_ENDPOINT}" ] && CHARTSEARCH_REMOTE_ENDPOINT_URL="${__OVR_ENDPOINT}"
[ -n "${__OVR_ENGINE}" ]   && CHARTSEARCH_LLM_ENGINE="${__OVR_ENGINE}"
[ -n "${__OVR_BASE_URL}" ] && CHARTSEARCH_BASE_URL="${__OVR_BASE_URL}"
[ -n "${__OVR_CTX}" ]      && CHARTSEARCH_CONTEXT_LENGTH="${__OVR_CTX}"

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

# Ensure the operator account ("admin") has the standard admin role that
# enumerates explicit privileges in the REST /session response. Without this,
# admin's only roles are 'System Developer' (backend super-role that bypasses
# privilege checks server-side but is NOT enumerated by REST) and 'Provider'
# (clinical), so SPA-side userHasAccess() returns false for module-gated
# extensions like the chartsearchai AI button. Idempotent: REST POST with the
# full role set is safe to re-run.
#
# The chartsearchai module's activator binds 'AI Query Patient Data' to
# 'Privilege Level: Full' (along with System Developer + Organizational:
# System Administrator) on every startup. This step is the missing
# operator-side piece — assigning admin to that role.
echo ""
echo "Ensuring admin has Privilege Level: Full role:"
ensure_admin_full_priv_role() {
  local admin_uuid full_uuid sd_uuid prov_uuid roles_payload
  admin_uuid=$(curl -fsS -u "${ADMIN_USER}:${ADMIN_PASS}" "${BASE_URL}/ws/rest/v1/session" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('user',{}).get('uuid',''))")
  if [ -z "${admin_uuid}" ]; then
    echo "  WARN: could not resolve admin uuid; skipping role assignment"
    return 0
  fi
  # Role UUIDs are OpenMRS reference-application metadata constants.
  full_uuid="ab2160f6-0941-430c-9752-6714353fbd3c"   # Privilege Level: Full
  sd_uuid="8d94f852-c2cc-11de-8d13-0010c6dffd0f"     # System Developer
  prov_uuid="8d94f280-c2cc-11de-8d13-0010c6dffd0f"   # Provider
  roles_payload="{\"roles\":[{\"uuid\":\"${sd_uuid}\"},{\"uuid\":\"${prov_uuid}\"},{\"uuid\":\"${full_uuid}\"}]}"
  local result
  result=$(curl -fsS -u "${ADMIN_USER}:${ADMIN_PASS}" -X POST \
    -H "Content-Type: application/json" \
    "${BASE_URL}/ws/rest/v1/user/${admin_uuid}" \
    -d "${roles_payload}" \
    | python3 -c "import json,sys; r=json.load(sys.stdin); print(','.join(x.get('display','') for x in r.get('roles',[])))" \
    2>/dev/null || echo "")
  if [ -n "${result}" ]; then
    echo "  admin roles after update: ${result}"
  else
    echo "  WARN: role update did not return a parseable response"
  fi
}
ensure_admin_full_priv_role

echo ""
echo "Module status:"
curl -fsS -u "${ADMIN_USER}:${ADMIN_PASS}" \
  "${BASE_URL}/ws/rest/v1/module/chartsearchai?v=custom:(uuid,started,version)" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  chartsearchai {d.get('version','?')} started={d.get('started')}\")"

# Warm up the active model on LM Studio so it's loaded with a usable context
# size BEFORE the first chat request. LM Studio's default JIT-load context is
# 4096 tokens, but chartsearchai chart envelopes routinely exceed that, so
# inference fails with HTTP 400 "n_keep > n_ctx" until the model is reloaded.
# Skip cleanly if SKIP_WARMUP=1 or if the warmup script / lms CLI is missing.
if [ "${SKIP_WARMUP:-0}" != "1" ] && [ -x "${ROOT}/scripts/chartsearch-warmup.sh" ]; then
  echo ""
  echo "Warming up active model on local LM Studio:"
  CHARTSEARCH_WARMUP_MODELS="${MODEL}" \
    "${ROOT}/scripts/chartsearch-warmup.sh" || echo "  WARN: warmup failed (model may not be reloaded with full context)"
fi
