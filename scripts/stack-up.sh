#!/usr/bin/env bash
# scripts/stack-up.sh
# Bring up the harness's shared infra compose stack (O3 RefApp on Core 2.8.x).
#
# Usage:
#   ./scripts/stack-up.sh              # all services (gateway+frontend+backend+db)
#   ./scripts/stack-up.sh db           # just db
#   ./scripts/stack-up.sh db backend   # subset
#   ./scripts/stack-up.sh --wait       # all + wait for backend health
#   ./scripts/stack-up.sh --no-build   # never build images; fail if one is missing
#
# Idempotent: re-running with the stack already up is a no-op (docker compose's behavior).
set -euo pipefail
COMPOSE_FILE="${COMPOSE_FILE:-compose/openmrs-2.8-refapp.yml}"
if [[ "$(id -u)" == "0" ]]; then
  echo "ERROR: stack-up must run as a non-root host user." >&2
  echo "Root would map UID 0 into the med-agent-hub container." >&2
  exit 1
fi
export MED_AGENT_HUB_UID="${MED_AGENT_HUB_UID:-$(id -u)}"
export MED_AGENT_HUB_GID="${MED_AGENT_HUB_GID:-$(id -g)}"
WAIT=0
NOBUILD=0
SVCS=()
for arg in "$@"; do
  case "$arg" in
    --wait) WAIT=1 ;;
    --no-build) NOBUILD=1 ;;
    *) SVCS+=("$arg") ;;
  esac
done
UP_ARGS=(up -d)
[[ "$NOBUILD" == "1" ]] && UP_ARGS+=(--no-build)
# "${SVCS[@]+"${SVCS[@]}"}" (not "${SVCS[@]}"): macOS ships bash 3.2, which
# raises "unbound variable" expanding an empty array under `set -u`. Note this
# must be the `+` alternate-value form, not `${SVCS[@]-}` — that substitutes
# a single empty-string argument when SVCS is empty (Compose then sees a
# blank service name), whereas `+` correctly yields zero arguments.
docker compose -f "$COMPOSE_FILE" "${UP_ARGS[@]}" "${SVCS[@]+"${SVCS[@]}"}"
if [[ "$WAIT" == "1" ]] || [[ "${#SVCS[@]}" -eq 0 ]]; then
  echo "Waiting for backend health (this can take 5-10 min on first boot)..."
  for i in $(seq 1 600); do
    status=$(docker inspect harness-openmrs-backend --format '{{.State.Health.Status}}' 2>/dev/null || echo "missing")
    if [[ "$status" == "healthy" ]]; then echo "backend healthy after ${i}s"; break; fi
    if (( i % 30 == 0 )); then echo "  still waiting (${i}s, status=$status)..."; fi
    sleep 1
  done
fi
docker compose -f "$COMPOSE_FILE" ps
echo ""
PROXY_PORT="${HARNESS_PROXY_HTTP_PORT:-8088}"
DB_PORT="${OMRS_DB_PORT:-3307}"
echo "Access:"
echo "  O3 RefApp UI:    http://localhost:${PROXY_PORT}/openmrs/spa"
echo "  REST API:        http://localhost:${PROXY_PORT}/openmrs/ws/rest/v1/"
echo "  FHIR API:        http://localhost:${PROXY_PORT}/openmrs/ws/fhir2/R4/"
echo "  MariaDB (host):  localhost:${DB_PORT}  (user/pass: openmrs/openmrs)"
echo "  default creds:   admin / Admin123 (NOT FOR PRODUCTION)"
