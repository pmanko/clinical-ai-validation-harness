#!/usr/bin/env bash
# Guards shared by scripts/cloud-sync.sh. Sourced, not executed.
#
# rsync_delete_gate: read an `rsync --dry-run -v --delete` transcript on stdin, summarise what the
# real run would delete on the VM by top-level path, and refuse (return 1) when the count exceeds
# CLOUD_SYNC_MAX_DELETES (default 50) or anything under CLOUD_SYNC_SENSITIVE_PATHS (default
# artifacts/openmrs/modules/) would go, unless CLOUD_SYNC_FORCE_DELETE=1. On 2026-09-07 a sync from a
# worktree whose gitignored artifacts/ was empty deleted 4,359 paths on the VM, every published
# report among them, with no summary and nothing to stop it.
rsync_delete_gate() {
  local max="${CLOUD_SYNC_MAX_DELETES:-50}"
  local deletions count
  deletions="$(grep -a '^deleting ' || true)"
  count=0
  [[ -n "${deletions}" ]] && count="$(printf '%s\n' "${deletions}" | wc -l | tr -d ' ')"
  if (( count == 0 )); then
    echo "==> delete gate: nothing would be deleted on the VM"
    return 0
  fi
  echo "==> delete gate: ${count} path(s) would be deleted on the VM, by top-level path:"
  printf '%s\n' "${deletions}" | sed 's/^deleting //' | awk -F/ '{print $1}' | sort | uniq -c | sort -rn | sed 's/^/    /'
  if [[ "${CLOUD_SYNC_FORCE_DELETE:-0}" == "1" ]]; then
    echo "==> delete gate: CLOUD_SYNC_FORCE_DELETE=1, proceeding"
    return 0
  fi
  local sensitive hit="" path
  sensitive="${CLOUD_SYNC_SENSITIVE_PATHS:-artifacts/openmrs/modules/}"
  for path in ${sensitive}; do
    if printf '%s\n' "${deletions}" | sed 's/^deleting //' | grep -q "^${path}"; then
      hit="${hit} ${path}"
    fi
  done
  if [[ -n "${hit}" ]]; then
    echo "error: the sync would delete under sensitive path(s):${hit}" >&2
    echo "       Removing a module from the VM is a deliberate act. Rerun with CLOUD_SYNC_FORCE_DELETE=1 if it is." >&2
    return 1
  fi
  if (( count > max )); then
    echo "error: ${count} deletions exceeds CLOUD_SYNC_MAX_DELETES=${max}." >&2
    echo "       Syncing from the right checkout? A worktree missing gitignored artifacts mirrors that absence onto the VM." >&2
    echo "       Rerun with CLOUD_SYNC_FORCE_DELETE=1 to proceed anyway." >&2
    return 1
  fi
  return 0
}

# cloud_sync_rsync_args ROOT DEST SSH_KEY: print, one per line, the rsync arguments cloud-sync uses.
# The script and tests/test_cloud_sync_guard.py both read this, so the shared filter file cannot
# silently fall off the command line.
cloud_sync_rsync_args() {
  local root="$1" dest="$2" key="$3"
  printf '%s\n' -avz --delete \
    "--filter=merge ${root}/scripts/cloud-sync.filter" \
    -e "ssh -i ${key} -o StrictHostKeyChecking=accept-new" \
    "${root}/" "${dest}"
}
