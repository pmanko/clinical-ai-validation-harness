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
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-sync-lib.sh"

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

# One shared definition of the argv (scripts/cloud-sync-lib.sh), read here and by the tests.
RSYNC_ARGS=()
while IFS= read -r arg; do RSYNC_ARGS+=("${arg}"); done \
  < <(cloud_sync_rsync_args "${ROOT}" "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/" "${GCP_SSH_KEY}")

# Say what is being shipped from where: a worktree missing gitignored artifacts is the shape that
# mirrors an empty directory onto the VM.
echo "==> source: ${ROOT} (branch $(git -C "${ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?'), $(git -C "${ROOT}" status --porcelain 2>/dev/null | wc -l | tr -d ' ') uncommitted paths)"

# Dry run first; the gate prints what would be deleted and refuses a mass or sensitive deletion.
rsync --dry-run "${RSYNC_ARGS[@]}" | rsync_delete_gate
if [[ "${CLOUD_SYNC_DRY_RUN:-0}" == "1" ]]; then
  echo "==> CLOUD_SYNC_DRY_RUN=1: stopping before the real sync"
  exit 0
fi

# Reclaim ownership of dirs we chown'd to 1001:0 on a previous run so this
# rsync can write into them. Without this, an updated .omod cannot replace
# the existing one (permission denied) and rsync exits 23 with the cosmetic
# warning that gets users blaming "rsync flakiness". Chown back to the
# real container UID happens at the end of this script.
gcp_ssh "sudo chown -R ${GCP_SSH_USER}:${GCP_SSH_USER} ${GCP_REMOTE_REPO}/artifacts/openmrs/modules ${GCP_REMOTE_REPO}/artifacts/openmrs/backend-logs 2>/dev/null || true"

rsync "${RSYNC_ARGS[@]}"

# Lock down .env.chartsearch.cloud on the VM. The file contains the
# CHARTSEARCH_LLM_REMOTE_APIKEY plus DB passwords, and rsync preserves
# the local umask perms (usually 644 = world-readable). If the project
# later enables OS Login, other authorized GCP users inherit shell access
# and could read the env file. chmod 600 makes it owner-only-readable.
gcp_ssh "chmod 600 ${GCP_REMOTE_REPO}/.env.chartsearch.cloud"

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
