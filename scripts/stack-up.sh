#!/usr/bin/env bash
# scripts/stack-up.sh
# Bring up the harness's shared infra compose stack (O3 RefApp on Core 2.8.x).
#
# Usage:
#   ./scripts/stack-up.sh              # all configured services
#   ./scripts/stack-up.sh db           # just db
#   ./scripts/stack-up.sh db backend   # subset
#   ./scripts/stack-up.sh --wait       # all + wait for service readiness
#   ./scripts/stack-up.sh --no-build   # start only from existing images
#
# Idempotent: re-running with the stack already up is a no-op (docker compose's behavior).
set -euo pipefail
COMPOSE_FILE="${COMPOSE_FILE:-compose/openmrs-2.8-refapp.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"
WAIT_TIMEOUT_SECONDS="${STACK_WAIT_TIMEOUT_SECONDS:-900}"

usage() {
  cat >&2 <<'EOF'
usage: scripts/stack-up.sh [--wait] [--wait-timeout SECONDS] [--no-build] [SERVICE...]
EOF
}

if ! [[ "${WAIT_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: STACK_WAIT_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi

if [[ "$(id -u)" == "0" ]]; then
  echo "ERROR: stack-up must run as a non-root host user." >&2
  echo "Root would map UID 0 into the med-agent-hub container." >&2
  exit 1
fi
export MED_AGENT_HUB_UID="${MED_AGENT_HUB_UID:-$(id -u)}"
export MED_AGENT_HUB_GID="${MED_AGENT_HUB_GID:-$(id -g)}"
WAIT=0
NO_BUILD=0
SVCS=()
while (( $# > 0 )); do
  case "$1" in
    --wait)
      WAIT=1
      shift
      ;;
    --wait-timeout)
      if (( $# < 2 )) || ! [[ "$2" =~ ^[1-9][0-9]*$ ]]; then
        usage
        exit 2
      fi
      WAIT=1
      WAIT_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --wait-timeout=*)
      WAIT=1
      WAIT_TIMEOUT_SECONDS="${1#*=}"
      if ! [[ "${WAIT_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
        usage
        exit 2
      fi
      shift
      ;;
    --no-build)
      NO_BUILD=1
      shift
      ;;
    -*)
      echo "ERROR: unknown option: $1" >&2
      usage
      exit 2
      ;;
    *)
      SVCS+=("$1")
      shift
      ;;
  esac
done

COMPOSE=(docker compose)
if [[ -n "${COMPOSE_ENV_FILE}" ]]; then
  COMPOSE+=(--env-file "${COMPOSE_ENV_FILE}")
fi
COMPOSE+=(-f "${COMPOSE_FILE}")

UP_ARGS=(-d)
if [[ "${NO_BUILD}" == "1" ]]; then
  UP_ARGS+=(--no-build)
fi
if [[ "${WAIT}" == "1" ]] || [[ "${#SVCS[@]}" -eq 0 ]]; then
  echo "Waiting up to ${WAIT_TIMEOUT_SECONDS}s for Compose services to be running/healthy..."
  UP_ARGS+=(--wait --wait-timeout "${WAIT_TIMEOUT_SECONDS}")
fi

# The alternate-value form expands to zero arguments for an empty array under
# macOS Bash 3.2 + `set -u`; plain "${SVCS[@]}" raises "unbound variable".
"${COMPOSE[@]}" up "${UP_ARGS[@]}" "${SVCS[@]+"${SVCS[@]}"}"
"${COMPOSE[@]}" ps
echo ""
PROXY_PORT="${HARNESS_PROXY_HTTP_PORT:-8088}"
DB_PORT="${OMRS_DB_PORT:-3307}"
echo "Access:"
echo "  O3 RefApp UI:    http://localhost:${PROXY_PORT}/openmrs/spa"
echo "  REST API:        http://localhost:${PROXY_PORT}/openmrs/ws/rest/v1/"
echo "  FHIR API:        http://localhost:${PROXY_PORT}/openmrs/ws/fhir2/R4/"
echo "  MariaDB (host):  localhost:${DB_PORT}"
echo "  OpenMRS login:   credentials from local configuration"
