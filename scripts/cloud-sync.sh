#!/usr/bin/env bash
# Rsync the harness repo to the VM. Excludes build artifacts, virtualenvs,
# caches, and oversized data files — everything the VM compose stack needs
# survives the diff. Re-runs are fast (rsync diff-and-patch).
#
# Whitelist .env.chartsearch.cloud (the operator's filled-in cloud env file)
# but keep all other .env.* files off the wire — they belong to local dev.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

if ! gcp_vm_exists; then
  echo "error: VM ${GCP_VM_NAME} not found. Run \`make cloud-init\` first." >&2
  exit 1
fi
status="$(gcp_vm_status)"
if [ "${status}" != "RUNNING" ]; then
  echo "error: VM ${GCP_VM_NAME} is ${status}, not RUNNING. Run \`make cloud-start\`." >&2
  exit 1
fi

IP="$(gcp_vm_ip)"
echo "==> rsync to ${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/"

gcp_ssh_keygen_once
gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}"

# Rsync filter rules — FIRST MATCH WINS. Includes come before broad excludes
# so they survive. Notes:
# - `.git` (no slash): matches both the repo-root .git dir AND submodule
#   .git gitdir-pointer files. Covers both shapes.
# - `.env.chartsearch.cloud`: the one .env we ship to the VM. Symlinked on
#   the VM to .env.chartsearch by cloud-up.sh so scripts run there too.
# - `.env.chartsearch`: protected from --delete (it's the symlink target).
# - `artifacts/openmrs/modules/`: NOT excluded — that's where the built
#   .omod lives; the whole point of cloud-deploy is to ship it.

rsync -avz --delete \
  --include='.env.chartsearch.cloud' \
  --include='.env.*.example' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='.env.chartsearch' \
  --exclude='.git' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='.ruff_cache/' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='node_modules/' \
  --exclude='.DS_Store' \
  --exclude='.idea/' \
  --exclude='.vscode/' \
  --exclude='*.iml' \
  --exclude='artifacts/dev-*' \
  --exclude='artifacts/openmrs/backend-logs/' \
  --exclude='targets/*/target/' \
  --exclude='targets/*/node_modules/' \
  --exclude='targets/*/omod/target/' \
  --exclude='targets/*/api/target/' \
  -e "ssh -i ${GCP_SSH_KEY} -o StrictHostKeyChecking=accept-new" \
  "${ROOT}/" \
  "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/"

echo "==> sync complete"
