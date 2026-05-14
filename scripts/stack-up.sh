#!/usr/bin/env bash
# scripts/stack-up.sh
# Bring up the harness's shared infra compose stack (O3 RefApp on Core 2.8.x).
#
# Usage:
#   ./scripts/stack-up.sh              # all services (gateway+frontend+backend+db)
#   ./scripts/stack-up.sh db           # just db
#   ./scripts/stack-up.sh db backend   # subset
#   ./scripts/stack-up.sh --wait       # all + wait for backend health
#
# Idempotent: re-running with the stack already up is a no-op (docker compose's behavior).
set -euo pipefail
COMPOSE_FILE="${COMPOSE_FILE:-compose/openmrs-2.8-refapp.yml}"
WAIT=0
SVCS=()
for arg in "$@"; do
  case "$arg" in
    --wait) WAIT=1 ;;
    *) SVCS+=("$arg") ;;
  esac
done
docker compose -f "$COMPOSE_FILE" up -d "${SVCS[@]}"
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
