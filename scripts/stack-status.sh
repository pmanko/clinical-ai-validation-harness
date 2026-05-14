#!/usr/bin/env bash
# scripts/stack-status.sh
# Show health + port mappings for the harness compose stack.
set -euo pipefail
COMPOSE_FILE="${COMPOSE_FILE:-compose/openmrs-2.8-refapp.yml}"
docker compose -f "$COMPOSE_FILE" ps
echo ""
for c in harness-openmrs-db harness-openmrs-backend harness-openmrs-frontend harness-openmrs-gateway; do
  s=$(docker inspect "$c" --format '{{.State.Health.Status}}' 2>/dev/null || echo "missing")
  printf "  %-30s %s\n" "$c" "$s"
done
