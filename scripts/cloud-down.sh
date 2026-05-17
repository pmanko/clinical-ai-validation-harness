#!/usr/bin/env bash
# Stop the compose stack on the VM but keep the VM running.
# Use `make cloud-stop` if you want to halt the VM itself (saves cost).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

echo "==> compose down on ${GCP_VM_NAME}"
gcp_ssh "cd ${GCP_REMOTE_REPO} && docker compose -f compose/openmrs-2.8-refapp.yml down"
