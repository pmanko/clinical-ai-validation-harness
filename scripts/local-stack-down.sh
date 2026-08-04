#!/usr/bin/env bash
# Stop the local dev stack started by scripts/local-stack-up.sh.
#
# Leaves Docker volumes intact (patient data, ES index, module state) so the
# next local-stack-up.sh brings everything back exactly as it was. Does not
# stop Docker Desktop itself or uninstall anything.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env.chartsearch"
COMPOSE_FILE="${ROOT}/compose/openmrs-2.8-refapp.yml"
cd "${ROOT}"

stop_managed_router() {
  local pid command_line elapsed

  if [[ ! -s "${ROUTER_PID_FILE}" ]]; then
    echo "    no managed router PID; leaving any externally managed router running"
    return 0
  fi

  pid="$(<"${ROUTER_PID_FILE}")"
  if ! [[ "${pid}" =~ ^[1-9][0-9]*$ ]]; then
    echo "WARNING: removing invalid router PID file: ${ROUTER_PID_FILE}" >&2
    rm -f "${ROUTER_PID_FILE}"
    return 0
  fi

  command_line="$(ps -ww -p "${pid}" -o command= 2>/dev/null || true)"
  if [[ -z "${command_line}" ]]; then
    echo "    removing stale router PID file (${pid})"
    rm -f "${ROUTER_PID_FILE}"
    return 0
  fi
  if [[ "${command_line}" != *llama-server* ]] \
    || [[ "${command_line}" != *"${ROOT}/scripts/llama-router.ini"* ]]; then
    echo "WARNING: PID ${pid} is not this project's llama-router; leaving it running" >&2
    rm -f "${ROUTER_PID_FILE}"
    return 0
  fi

  kill "${pid}" 2>/dev/null || true
  elapsed=0
  while kill -0 "${pid}" 2>/dev/null; do
    if (( elapsed >= 10 )); then
      echo "WARNING: router PID ${pid} did not stop after 10s; sending SIGKILL" >&2
      kill -KILL "${pid}" 2>/dev/null || true
      break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  rm -f "${ROUTER_PID_FILE}"
  echo "    stopped managed router PID ${pid}"
}

echo "==> Loading local configuration when available"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
else
  echo "WARNING: .env.chartsearch is missing; Compose teardown may lack required interpolation values" >&2
fi
ROUTER_RUNTIME_DIR="${LLAMA_ROUTER_RUNTIME_DIR:-${ROOT}/artifacts/llama-router}"
ROUTER_PID_FILE="${ROUTER_RUNTIME_DIR}/router.pid"

if ! command -v docker >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
  for brew_path in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "${brew_path}" ]]; then
      eval "$("${brew_path}" shellenv bash)"
      break
    fi
  done
fi

if [[ -z "${HUB_BUILD_REVISION:-}" ]]; then
  HUB_BUILD_REVISION="$(git -C targets/med-agent-hub rev-parse HEAD 2>/dev/null || printf 'local-stack-down')"
fi
export HUB_BUILD_REVISION
export COMPOSE_FILE
if [[ -f "${ENV_FILE}" ]]; then
  export COMPOSE_ENV_FILE="${ENV_FILE}"
fi

result=0
echo "==> Stopping the Docker Compose stack (named volumes preserved)"
if ! "${ROOT}/scripts/stack-down.sh"; then
  echo "WARNING: Docker Compose teardown failed; continuing with router cleanup" >&2
  result=1
fi

echo "==> Stopping llama-router"
if ! stop_managed_router; then
  result=1
fi

echo "Done."
exit "${result}"
