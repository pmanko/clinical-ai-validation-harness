#!/usr/bin/env bash
# Bring up the complete local ChartSearchAI product path through med-agent-hub.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
HUB_BUILD_REVISION="$(git -C targets/med-agent-hub rev-parse HEAD)"
export HUB_BUILD_REVISION

CHECK_ONLY=0
if [ "${1:-}" = "--check" ]; then
  CHECK_ONLY=1
elif [ "$#" -gt 0 ]; then
  echo "usage: $0 [--check]" >&2
  exit 2
fi

load_config_value() {
  local name="$1" file value
  printenv "${name}" >/dev/null 2>&1 && return
  for file in .env.chartsearch .env.chartsearch.example; do
    [ -f "${file}" ] || continue
    grep -q "^${name}=" "${file}" || continue
    value="$(set -a; . "./${file}"; printenv "${name}")"
    printf -v "${name}" '%s' "${value}"
    export "${name}"
    return
  done
}

for config_name in \
  OMRS_DB_NAME OPENMRS_REFAPP_TAG HARNESS_PROXY_HTTP_PORT HARNESS_PROXY_HTTPS_PORT \
  CHARTSEARCH_HUB_ENDPOINT_URL CHARTSEARCH_HUB_PROFILE_ID CHARTSEARCH_HUB_API_KEY \
  MED_AGENT_HUB_PORT MED_AGENT_LLM_BASE_URL LLAMA_MODEL_DIR LLAMA_ROUTER_MODELS_MAX \
  HUB_TIMEZONE \
  CHARTSEARCH_LOCAL_BUILD CHARTSEARCH_LOCAL_WARM CHARTSEARCH_ADMIN_USER \
  CHARTSEARCH_ADMIN_PASSWORD QUERYSTORE_BASE_URL QUERYSTORE_VERIFY_BASE_URL \
  QUERYSTORE_USERNAME QUERYSTORE_PASSWORD; do
  load_config_value "${config_name}"
done

if [ -z "${HUB_TIMEZONE:-}" ]; then
  LOCALTIME_LINK="$(readlink /etc/localtime 2>/dev/null || true)"
  case "${LOCALTIME_LINK}" in
    */zoneinfo/*) HUB_TIMEZONE="${LOCALTIME_LINK#*/zoneinfo/}" ;;
    *) HUB_TIMEZONE="UTC" ;;
  esac
fi
export HUB_TIMEZONE

COMPOSE=(docker compose -f compose/openmrs-2.8-refapp.yml)
OPENMRS_URL="http://127.0.0.1:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs"
HUB_URL="http://127.0.0.1:${MED_AGENT_HUB_PORT:-18081}"
ROUTER_URL="http://127.0.0.1:8077"
MODEL_DIR="${LLAMA_MODEL_DIR:-${HOME}/.cache/llama-router-models}"
BUILD_MODE="${CHARTSEARCH_LOCAL_BUILD:-auto}"
WARM_MODE="${CHARTSEARCH_LOCAL_WARM:-answer}"
SOURCE_ENV="${ROOT}/artifacts/chartsearchai-local/querystore-service.env"
DEFAULT_PATIENT="${CHARTSEARCH_LOCAL_PATIENT_UUID:-dd75c020-1691-11df-97a5-7038c432aabf}"
MODULES_CHANGED=0

say() { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

wait_http() {
  local label="$1" url="$2" timeout="$3" elapsed=0
  until curl -fsS --max-time 3 "${url}" >/dev/null 2>&1; do
    if [ "${elapsed}" -ge "${timeout}" ]; then
      fail "${label} was not ready after ${timeout}s (${url})"
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  say "  ${label}: ready"
}

wait_container() {
  local label="$1" container="$2" timeout="$3" elapsed=0 status
  while true; do
    status="$(docker inspect -f '{{.State.Health.Status}}' "${container}" 2>/dev/null || echo starting)"
    if [ "${status}" = "healthy" ]; then
      say "  ${label}: healthy"
      return
    fi
    if [ "${status}" = "unhealthy" ]; then
      fail "${label} reported unhealthy; inspect: docker logs ${container}"
    fi
    if [ "${elapsed}" -ge "${timeout}" ]; then
      fail "${label} was not healthy after ${timeout}s (last status: ${status})"
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
}

artifact_stale() {
  local artifact="$1"
  shift
  [ ! -f "${artifact}" ] && return 0
  find "$@" -type f -newer "${artifact}" -print -quit 2>/dev/null | grep -q .
}

build_if_needed() {
  local label="$1" artifact="$2" target="$3"
  local did_build=0
  shift 3
  case "${BUILD_MODE}" in
    always)
      say "==> build ${label} (requested)"
      make "${target}"
      did_build=1
      ;;
    auto)
      if artifact_stale "${artifact}" "$@"; then
        say "==> build ${label} (missing or stale)"
        make "${target}"
        did_build=1
      else
        say "==> ${label}: current"
      fi
      ;;
    never)
      [ -f "${artifact}" ] || fail "${label} artifact is missing and CHARTSEARCH_LOCAL_BUILD=never"
      say "==> ${label}: build skipped"
      ;;
    *) fail "CHARTSEARCH_LOCAL_BUILD must be auto, always, or never" ;;
  esac
  if [ "${did_build}" = "1" ] && { [ "${target}" = "chartsearch-build" ] || [ "${target}" = "querystore-build" ]; }; then
    MODULES_CHANGED=1
  fi
}

require_command curl
require_command docker
require_command python3
"${COMPOSE[@]}" config --quiet

ROUTER_REACHABLE=0
if curl -fsS --max-time 3 "${ROUTER_URL}/v1/models" >/dev/null 2>&1; then
  ROUTER_REACHABLE=1
else
  require_command llama-server
  [ -d "${MODEL_DIR}" ] || fail "model directory not found: ${MODEL_DIR}"
  [ -f "${MODEL_DIR}/gemma-e4b.gguf" ] || fail "default model missing: ${MODEL_DIR}/gemma-e4b.gguf"
fi

if [ "${CHECK_ONLY}" = "1" ]; then
  say "ChartSearchAI local prerequisites are present."
  say "  model directory: ${MODEL_DIR}"
  say "  router: $([ "${ROUTER_REACHABLE}" = "1" ] && echo existing || echo host-native prerequisites)"
  say "  default profile: ${CHARTSEARCH_HUB_PROFILE_ID}"
  say "  temporal timezone: ${HUB_TIMEZONE}"
  exit 0
fi

mkdir -p artifacts/chartsearchai-local artifacts/llama-router

build_if_needed \
  "ChartSearchAI module" \
  "artifacts/openmrs/modules/chartsearchai-1.0.0-SNAPSHOT.omod" \
  chartsearch-build \
  targets/chartsearchai/api/src targets/chartsearchai/omod/src \
  targets/chartsearchai/pom.xml targets/chartsearchai/api/pom.xml targets/chartsearchai/omod/pom.xml
build_if_needed \
  "Querystore module" \
  "artifacts/openmrs/modules/querystore-1.0.0-SNAPSHOT.omod" \
  querystore-build \
  targets/querystore/api/src targets/querystore/omod/src \
  targets/querystore/pom.xml targets/querystore/api/pom.xml targets/querystore/omod/pom.xml

say "==> llama.cpp router"
if [ "${ROUTER_REACHABLE}" = "1" ]; then
  say "  existing router: reachable"
else
  nohup env \
    LLAMA_MODEL_DIR="${MODEL_DIR}" \
    LLAMA_ROUTER_MODELS_MAX="${LLAMA_ROUTER_MODELS_MAX:-1}" \
    ./scripts/llama-router-up.sh \
    >artifacts/llama-router/router.log 2>&1 &
  echo "$!" >artifacts/llama-router/router.pid
  wait_http "llama.cpp router" "${ROUTER_URL}/v1/models" 60
fi
curl -fsS "${ROUTER_URL}/v1/models" \
  | python3 -c "import json,sys; ids={x.get('id') for x in json.load(sys.stdin).get('data',[])}; assert 'gemma-e4b' in ids, 'router does not advertise gemma-e4b'"

say "==> OpenMRS core stack"
"${COMPOSE[@]}" up -d --build db elasticsearch backend frontend gateway proxy
if [ "${MODULES_CHANGED}" = "1" ]; then
  say "  module artifacts changed: refresh OpenMRS module caches"
  docker exec harness-openmrs-backend sh -c \
    'rm -rf /openmrs/data/.openmrs-lib-cache/chartsearchai /openmrs/data/.openmrs-lib-cache/querystore'
  "${COMPOSE[@]}" restart backend
fi
wait_container "OpenMRS backend" harness-openmrs-backend 600
wait_http "OpenMRS proxy" "http://127.0.0.1:${HARNESS_PROXY_HTTP_PORT:-8088}/__proxy_health" 120

build_if_needed \
  "ChartSearchAI ESM" \
  "artifacts/openmrs/spa-custom/openmrs-esm-chartsearchai-app-multiturn/openmrs-esm-chartsearchai-app.js" \
  chartsearch-esm-build \
  targets/chartsearchai-esm/src targets/chartsearchai-esm/package.json targets/chartsearchai-esm/yarn.lock

if [ -n "${QUERYSTORE_BASE_URL:-}" ] || [ -n "${QUERYSTORE_USERNAME:-}" ] || [ -n "${QUERYSTORE_PASSWORD:-}" ]; then
  [ -n "${QUERYSTORE_BASE_URL:-}" ] && [ -n "${QUERYSTORE_USERNAME:-}" ] && [ -n "${QUERYSTORE_PASSWORD:-}" ] \
    || fail "set QUERYSTORE_BASE_URL, QUERYSTORE_USERNAME, and QUERYSTORE_PASSWORD together"
  say "==> use externally managed patient-source credentials"
  SOURCE_VERIFY_BASE_URL="${QUERYSTORE_VERIFY_BASE_URL:-${QUERYSTORE_BASE_URL}}"
else
  say "==> provision least-privileged patient reader"
  python3 scripts/provision-querystore-service-account.py \
    --base-url "${OPENMRS_URL}" \
    --internal-base-url "http://backend:8080/openmrs" \
    --admin-user "${CHARTSEARCH_ADMIN_USER:-admin}" \
    --admin-password "${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}" \
    --output "${SOURCE_ENV}"
  set -a
  # shellcheck disable=SC1090
  . "${SOURCE_ENV}"
  set +a
  QUERYSTORE_BASE_URL=http://backend:8080/openmrs
  SOURCE_VERIFY_BASE_URL="${OPENMRS_URL}"
fi

export QUERYSTORE_BASE_URL QUERYSTORE_USERNAME QUERYSTORE_PASSWORD

say "==> med-agent-hub"
"${COMPOSE[@]}" up -d --build med-agent-hub
wait_http "med-agent-hub" "${HUB_URL}/health" 120
curl -fsS "${HUB_URL}/v1/models" \
  | python3 -c "import json,sys; p={x['id']:x for x in json.load(sys.stdin).get('data',[])}; x=p.get('${CHARTSEARCH_HUB_PROFILE_ID}'); assert x and x.get('available') and x.get('default'), x"

say "==> verify patient source"
curl -fsS --max-time 60 \
  -u "${QUERYSTORE_USERNAME}:${QUERYSTORE_PASSWORD}" \
  "${SOURCE_VERIFY_BASE_URL%/}/ws/rest/v1/querystore/patientrecord?patient=${DEFAULT_PATIENT}&limit=1" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('results'), 'patient source returned no records'"

say "==> configure ChartSearchAI relay"
./scripts/querystore-configure.sh
CHARTSEARCH_HUB_ENDPOINT_URL="${CHARTSEARCH_HUB_ENDPOINT_URL}" \
CHARTSEARCH_HUB_PROFILE_ID="${CHARTSEARCH_HUB_PROFILE_ID}" \
  ./scripts/chartsearch-configure.sh

if [ "${WARM_MODE}" != "off" ]; then
  say "==> exercise ${CHARTSEARCH_HUB_PROFILE_ID} (${WARM_MODE})"
  python3 scripts/warm-hub-profile.py \
    --hub-url "${HUB_URL}/v1/chat/completions" \
    --profile "${CHARTSEARCH_HUB_PROFILE_ID}" \
    --mode "${WARM_MODE}" \
    --output artifacts/chartsearchai-local/warmup.json
fi

say ""
say "ChartSearchAI is ready: http://localhost:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs/spa"
say "med-agent-hub: ${HUB_URL} (${CHARTSEARCH_HUB_PROFILE_ID})"
