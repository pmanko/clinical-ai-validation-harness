#!/usr/bin/env bash
# Stop the compose stack on the VM.
#
# Usage:
#   ./scripts/cloud-down.sh             # stop containers; keep volumes (data persists)
#   ./scripts/cloud-down.sh --volumes   # stop AND nuke volumes (fresh on next cloud-up)
#
# Mirrors the local stack-down.sh pattern. The VM itself stays running —
# use `make cloud-stop` to halt the instance.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

EXTRA=()
for arg in "$@"; do
  case "$arg" in
    --volumes|-v) EXTRA+=(-v) ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

echo "==> compose down on ${GCP_VM_NAME}${EXTRA:+ (with volume nuke)}"
gcp_ssh "cd ${GCP_REMOTE_REPO} && docker compose -f compose/openmrs-2.8-refapp.yml down ${EXTRA[*]:-}"
