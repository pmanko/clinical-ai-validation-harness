#!/usr/bin/env bash
# scripts/stack-down.sh
# Bring down the harness compose stack.
#
# Usage:
#   ./scripts/stack-down.sh             # stop containers; KEEP volumes (data persists)
#   ./scripts/stack-down.sh --volumes   # stop AND nuke volumes (fresh on next up)
set -euo pipefail
COMPOSE_FILE="${COMPOSE_FILE:-compose/openmrs-2.8-refapp.yml}"
EXTRA=()
for arg in "$@"; do
  case "$arg" in
    --volumes|-v) EXTRA+=(-v) ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done
docker compose -f "$COMPOSE_FILE" down "${EXTRA[@]}"
