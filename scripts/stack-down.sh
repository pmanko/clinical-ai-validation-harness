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
# "${EXTRA[@]+"${EXTRA[@]}"}" (not "${EXTRA[@]}"): macOS ships bash 3.2, which
# raises "unbound variable" expanding an empty array under `set -u`. Note this
# must be the `+` alternate-value form, not `${EXTRA[@]-}` — that substitutes
# a single empty-string argument when EXTRA is empty (Compose then sees a
# blank service name), whereas `+` correctly yields zero arguments.
docker compose -f "$COMPOSE_FILE" down "${EXTRA[@]+"${EXTRA[@]}"}"
