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

# Reclaim ownership of dirs we chown'd to 1001:0 on a previous run so this
# rsync can write into them. Without this, an updated .omod cannot replace
# the existing one (permission denied) and rsync exits 23 with the cosmetic
# warning that gets users blaming "rsync flakiness". Chown back to the
# real container UID happens at the end of this script.
gcp_ssh "sudo chown -R ${GCP_SSH_USER}:${GCP_SSH_USER} ${GCP_REMOTE_REPO}/artifacts/openmrs/modules ${GCP_REMOTE_REPO}/artifacts/openmrs/backend-logs 2>/dev/null || true"

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

# OpenMRS RefApp backend image runs as UID 1001:0. The compose bind-mounts
# artifacts/openmrs/modules and artifacts/openmrs/backend-logs INTO the
# container's writable paths (/openmrs/data/modules + /usr/local/tomcat/logs).
# On Linux the rsync'd files keep host ownership (UID 1000 / pmanko), which
# the container can't write into — startup.sh fails to populate distribution
# modules, backend never reaches healthy. On Docker Desktop (Mac) the UID
# virtualization papers over this, which is why the local flow works.
# Chown the two bind-mount targets here so the container can take ownership.
gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/artifacts/openmrs/modules ${GCP_REMOTE_REPO}/artifacts/openmrs/backend-logs && sudo chown -R 1001:0 ${GCP_REMOTE_REPO}/artifacts/openmrs/modules ${GCP_REMOTE_REPO}/artifacts/openmrs/backend-logs"

# Caddy in the proxy container reads /srv/spa-custom (mounted from this
# host path) as read-only static files. No UID-fix needed — the alpine
# nginx process can read any owner's files as long as the dir is +rx.
gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/artifacts/openmrs/spa-custom && chmod -R a+rX ${GCP_REMOTE_REPO}/artifacts/openmrs/spa-custom"

echo "==> sync complete"
