#!/usr/bin/env bash
# Full reset of the cloud stack: nuke containers + volumes, clear bind-mount
# state, then re-sync + bring back up clean. Mirrors `make reset` locally.
#
# Use when iterating on compose / startup / DB-init state changes, or when
# a previous cloud-up left a half-broken state.
#
# DESTRUCTIVE: nukes the cloud DB volume (the canonical `openmrs` corpus) on the
# VM. After this, you'll need `make cloud-seed` again to re-populate the corpus.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

if [ "${FORCE:-0}" != "1" ]; then
  printf 'About to drop all compose volumes (incl. the openmrs corpus) on %s. Type YES to confirm: ' "${GCP_VM_NAME}"
  read -r answer
  [ "${answer}" = "YES" ] || { echo aborted; exit 1; }
fi

echo "==> compose down --volumes"
"${ROOT}/scripts/cloud-down.sh" --volumes

echo "==> clear bind-mount state (the named volume removal above doesn't touch these)"
gcp_ssh "rm -rf ${GCP_REMOTE_REPO}/artifacts/openmrs/modules/* ${GCP_REMOTE_REPO}/artifacts/openmrs/backend-logs/* 2>/dev/null || true"

echo "==> re-sync (rsync'es repo + chowns bind mounts to container UID 1001)"
"${ROOT}/scripts/cloud-sync.sh"

echo "==> cloud-up (compose up + wait healthy + configure LLM globals)"
"${ROOT}/scripts/cloud-up.sh"

echo ""
echo "Reset complete. Next: \`make cloud-seed\` to repopulate openmrs."
