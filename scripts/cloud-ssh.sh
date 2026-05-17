#!/usr/bin/env bash
# Open an interactive SSH session on the VM, or run a one-shot command if
# args are provided.  `make cloud-ssh` opens a shell;
# `make cloud-ssh ARGS='docker ps'` runs that one command.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

if [ "$#" -gt 0 ]; then
  gcp_ssh "$*"
else
  # Interactive — bypass the gcp_ssh wrapper so we get a TTY allocation.
  ip="$(gcp_vm_ip)"
  exec ssh -i "${GCP_SSH_KEY}" \
       -o StrictHostKeyChecking=accept-new \
       "${GCP_SSH_USER}@${ip}"
fi
