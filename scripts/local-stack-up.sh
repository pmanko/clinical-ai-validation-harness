#!/usr/bin/env bash
# One-shot local dev bring-up after a reboot or Docker Desktop restart.
#
# Assumes the one-time setup is already done: Homebrew, Docker Desktop, uv,
# Maven/Java, Node/yarn, llama.cpp installed; chartsearchai/querystore .omod
# files and the chartsearchai ESM bundle already built into artifacts/;
# .env.chartsearch configured; querystore backend already switched to
# elasticsearch with bootstrap.autostart. This script does NOT rebuild any of
# that — it just starts the processes/containers so the stack (and the
# already-indexed patient data) comes back up as it was.
#
# Re-run anytime; every step is idempotent. For a first setup or after source
# changes, use `make chartsearchai-local` instead.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env.chartsearch"
COMPOSE_FILE="${ROOT}/compose/openmrs-2.8-refapp.yml"
ROUTER_URL="http://127.0.0.1:8077/v1/models"
STARTED_ROUTER_PID=""

cd "${ROOT}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

validate_timeout() {
  local name="$1"
  local value="$2"
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || fail "${name} must be a positive integer (got: ${value})"
}

wait_http() {
  local url="$1"
  local timeout="$2"
  local elapsed=0
  while ! curl --fail --silent --show-error --max-time 3 "${url}" >/dev/null 2>&1; do
    if (( elapsed >= timeout )); then
      return 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
}

stop_started_router() {
  local elapsed=0

  if [[ -z "${STARTED_ROUTER_PID}" ]]; then
    return
  fi
  if kill -0 "${STARTED_ROUTER_PID}" 2>/dev/null; then
    kill "${STARTED_ROUTER_PID}" 2>/dev/null || true
    while kill -0 "${STARTED_ROUTER_PID}" 2>/dev/null; do
      if (( elapsed >= 10 )); then
        kill -KILL "${STARTED_ROUTER_PID}" 2>/dev/null || true
        break
      fi
      sleep 1
      elapsed=$((elapsed + 1))
    done
  fi
  if [[ -f "${ROUTER_PID_FILE}" ]] \
    && [[ "$(<"${ROUTER_PID_FILE}")" == "${STARTED_ROUTER_PID}" ]]; then
    rm -f "${ROUTER_PID_FILE}"
  fi
}

handle_signal() {
  stop_started_router
  fail "startup interrupted; the router started by this run was stopped"
}

trap handle_signal INT TERM

echo "==> Loading local configuration"
[[ -f "${ENV_FILE}" ]] || fail ".env.chartsearch not found; copy .env.chartsearch.example and configure it first"
# This is an operator-owned shell environment file, matching the repository's
# other local launchers. Export its values for host tools and Compose.
set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

ROUTER_RUNTIME_DIR="${LLAMA_ROUTER_RUNTIME_DIR:-${ROOT}/artifacts/llama-router}"
ROUTER_PID_FILE="${ROUTER_RUNTIME_DIR}/router.pid"
ROUTER_LOG_FILE="${ROUTER_RUNTIME_DIR}/router.log"
DOCKER_TIMEOUT_SECONDS="${LOCAL_STACK_DOCKER_TIMEOUT_SECONDS:-180}"
ROUTER_TIMEOUT_SECONDS="${LOCAL_STACK_ROUTER_TIMEOUT_SECONDS:-60}"

validate_timeout LOCAL_STACK_DOCKER_TIMEOUT_SECONDS "${DOCKER_TIMEOUT_SECONDS}"
validate_timeout LOCAL_STACK_ROUTER_TIMEOUT_SECONDS "${ROUTER_TIMEOUT_SECONDS}"

echo "==> Loading Homebrew environment when installed"
if ! command -v docker >/dev/null 2>&1 || ! command -v llama-server >/dev/null 2>&1; then
  for brew_path in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "${brew_path}" ]]; then
      eval "$("${brew_path}" shellenv bash)"
      break
    fi
  done
fi

require_command curl
require_command docker
require_command git

echo "==> Checking Docker Desktop"
if ! docker info >/dev/null 2>&1; then
  if docker desktop version >/dev/null 2>&1; then
    echo "    starting Docker Desktop through its CLI..."
    docker desktop start >/dev/null || fail "Docker Desktop reported that it could not start"
  elif [[ "$(uname -s)" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
    echo "    starting Docker Desktop..."
    open -gja Docker || fail "macOS could not launch Docker Desktop"
  else
    fail "Docker is installed but its daemon is unavailable; start Docker and retry"
  fi
  printf '    waiting up to %ss for the daemon' "${DOCKER_TIMEOUT_SECONDS}"
  docker_elapsed=0
  until docker info >/dev/null 2>&1; do
    if (( docker_elapsed >= DOCKER_TIMEOUT_SECONDS )); then
      printf '\n' >&2
      fail "Docker did not become ready within ${DOCKER_TIMEOUT_SECONDS}s"
    fi
    printf '.'
    sleep 2
    docker_elapsed=$((docker_elapsed + 2))
  done
  printf '\n'
fi
echo "    docker is up"

if [[ -z "${HUB_BUILD_REVISION:-}" ]]; then
  HUB_BUILD_REVISION="$(git -C targets/med-agent-hub rev-parse HEAD 2>/dev/null)" \
    || fail "cannot resolve targets/med-agent-hub; initialize the project submodules first"
fi
export HUB_BUILD_REVISION
export COMPOSE_ENV_FILE="${ENV_FILE}"
export COMPOSE_FILE

echo "==> Validating the resolved Docker Compose configuration"
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config --quiet

echo "==> Checking llama-router (:8077)"
if curl --fail --silent --show-error --max-time 3 "${ROUTER_URL}" >/dev/null 2>&1; then
  echo "    already running"
else
  require_command llama-server
  mkdir -p "${ROUTER_RUNTIME_DIR}"
  echo "    starting in background (log: ${ROUTER_LOG_FILE})"
  nohup env \
    LLAMA_MODEL_DIR="${LLAMA_MODEL_DIR:-}" \
    LLAMA_ROUTER_MODELS_MAX="${LLAMA_ROUTER_MODELS_MAX:-2}" \
    LLAMA_ROUTER_RUNTIME_DIR="${ROUTER_RUNTIME_DIR}" \
    "${ROOT}/scripts/llama-router-up.sh" \
    >"${ROUTER_LOG_FILE}" 2>&1 </dev/null &
  STARTED_ROUTER_PID="$!"
  printf '%s\n' "${STARTED_ROUTER_PID}" >"${ROUTER_PID_FILE}"
  if ! wait_http "${ROUTER_URL}" "${ROUTER_TIMEOUT_SECONDS}"; then
    stop_started_router
    tail -n 20 "${ROUTER_LOG_FILE}" >&2 || true
    fail "llama-router did not become ready within ${ROUTER_TIMEOUT_SECONDS}s; see ${ROUTER_LOG_FILE}"
  fi
  echo "    ready (pid ${STARTED_ROUTER_PID})"
fi

echo "==> Bringing up the existing Docker Compose stack (builds disabled)"
if ! "${ROOT}/scripts/stack-up.sh" --wait --no-build; then
  stop_started_router
  fail "Compose startup failed; inspect: docker compose --env-file .env.chartsearch -f compose/openmrs-2.8-refapp.yml logs"
fi

trap - INT TERM

cat <<EOF

Stack is up:
  OpenMRS SPA:   http://localhost:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs/spa
  llama-router:  http://localhost:8077/v1/models
  Elasticsearch: http://localhost:${QUERYSTORE_ES_PORT:-9200}/_cat/indices?v

Stop everything with: make local-stack-down
EOF
