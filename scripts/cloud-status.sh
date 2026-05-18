#!/usr/bin/env bash
# Print VM + stack status: instance state, IP, browser URL, docker ps,
# backend health.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

if ! gcp_vm_exists; then
  echo "VM ${GCP_VM_NAME}: MISSING (run \`make cloud-init\`)"
  exit 0
fi

status="$(gcp_vm_status)"
ip="$(gcp_vm_ip)"
echo "VM:           ${GCP_VM_NAME} (${GCP_MACHINE_TYPE} in ${GCP_ZONE})"
echo "State:        ${status}"
echo "External IP:  ${ip:-<none>}"
[ -n "${ip}" ] && echo "Browser URL:  http://${ip}:${GCP_HTTP_PORT}/openmrs/spa"

if [ "${status}" = "RUNNING" ] && [ -n "${ip}" ]; then
  echo ""
  echo "Compose services on VM:"
  gcp_ssh "cd ${GCP_REMOTE_REPO} 2>/dev/null && docker compose -f compose/openmrs-2.8-refapp.yml ps 2>/dev/null || echo '  (repo not synced or compose not up)'" \
    | sed 's/^/  /'
fi
