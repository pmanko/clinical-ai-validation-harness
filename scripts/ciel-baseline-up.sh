#!/usr/bin/env bash
# scripts/ciel-baseline-up.sh
# End-to-end: pin OpenMRS to a specific CIEL release and import it offline.
#
# Idempotent — safe to re-run. Does the right thing whether:
#   - the stack is up or down,
#   - the ZIP is already pinned or needs to be fetched,
#   - the import has already run or not.
#
# Usage:
#   ./scripts/ciel-baseline-up.sh                    # default version
#   ./scripts/ciel-baseline-up.sh --version v2026-04-28
#   ./scripts/ciel-baseline-up.sh --online           # use subscription URL + token (drops determinism)
set -euo pipefail
VERSION="${CIEL_VERSION:-v2026-04-28}"
ONLINE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --online) ONLINE=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

HERE="$(dirname "$0")"

# Cross-platform single-instance lock: two operators (or human + CI) running
# `make ciel-baseline` simultaneously would otherwise both upload the ZIP and
# create duplicate import records. We use a lock-FD pattern that works on
# both macOS (no flock(1)) and Linux. The lock is released automatically when
# the script exits (FD closed).
LOCK_DIR="${TMPDIR:-/tmp}"
LOCK_FILE="${LOCK_DIR}/harness-ciel-baseline-${VERSION}.lock"
exec 9>"$LOCK_FILE"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 9; then
    echo "Another ciel-baseline run is in progress (lock: $LOCK_FILE). Exiting." >&2
    exit 0
  fi
else
  # macOS has no flock(1); use a sentinel PID file alongside.
  PIDFILE="${LOCK_FILE}.pid"
  if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    echo "Another ciel-baseline run is in progress (pid $(cat "$PIDFILE")). Exiting." >&2
    exit 0
  fi
  echo $$ > "$PIDFILE"
  trap 'rm -f "$PIDFILE"' EXIT
fi

# Preflight: cwd + python import sanity.
# shellcheck source=./_preflight.sh
source "$HERE/_preflight.sh"
harness_preflight || exit 1

# 1) If a pre-snapshotted baseline exists, prefer the fast path (seconds)
#    over the full openconceptlab import (30-90 min). The bootstrap is still
#    invoked afterwards so that the subscription URL is recorded in
#    OpenMRS's global_property table.
BASELINE_SQL="datasets/sources/ocl/CIEL/${VERSION}/seeded-baseline.sql"
USE_FAST_PATH=0
if [[ -f "$BASELINE_SQL" ]] && [[ "$ONLINE" != "1" ]]; then
  USE_FAST_PATH=1
  echo "Pre-snapshotted baseline found at $BASELINE_SQL; will use fast-path load."
fi

# 2) Ensure pinned ZIP exists (only required when no baseline snapshot)
ZIP_PATH="datasets/sources/ocl/CIEL/${VERSION}/CIEL_${VERSION}.zip"
if [[ "$USE_FAST_PATH" != "1" ]] && [[ ! -f "$ZIP_PATH" ]] && [[ "$ONLINE" != "1" ]]; then
  echo "ZIP not present at $ZIP_PATH; fetching..."
  "$HERE/fetch-ciel-release.sh" --version "$VERSION"
fi

# 3) Ensure the stack is up + backend is healthy
"$HERE/stack-up.sh" --wait

# 4) If using fast path: load the snapshot directly into MariaDB
if [[ "$USE_FAST_PATH" == "1" ]]; then
  "$HERE/load-baseline.sh" --version "$VERSION"
  echo ""
  echo "Fast-path baseline loaded. Subscription URL will still be set below for"
  echo "consistency with the slow-path bootstrap state."
fi

# 5) Run the Python bootstrap (sets subscription URL; idempotent — if
#    fast-path was used and openconceptlab_import rows came along, the
#    is_already_bootstrapped() check will short-circuit the import step.)
echo ""
echo "=== bootstrapping CIEL ${VERSION} into OpenMRS via openconceptlab module ==="
# Module CLI: argv handles quoting safely (no shell-string interpolation into
# Python source). Exit codes: 0 success, 1 bootstrap error, 2 credential error.
if [[ "$ONLINE" == "1" ]]; then
  python3 -m harness.ocl ciel-baseline --version "$VERSION" --online
else
  python3 -m harness.ocl ciel-baseline --version "$VERSION"
fi

echo ""
echo "Done. RefApp now configured against CIEL ${VERSION}."
echo "Subscription URL persisted in OpenMRS global properties; survives 'stack-down + stack-up'."
echo "Use 'scripts/stack-reset.sh' to nuke the db volume and start over from scratch."
