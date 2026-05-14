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
if [[ "$ONLINE" == "1" ]]; then
  python3 -c "
from harness.ocl.bootstrap import bootstrap_ciel
bootstrap_ciel('${VERSION}', use_online_subscription=True)
"
else
  python3 -c "
from harness.ocl.bootstrap import bootstrap_ciel
bootstrap_ciel('${VERSION}')
"
fi

echo ""
echo "Done. RefApp now configured against CIEL ${VERSION}."
echo "Subscription URL persisted in OpenMRS global properties; survives 'stack-down + stack-up'."
echo "Use 'scripts/stack-reset.sh' to nuke the db volume and start over from scratch."
