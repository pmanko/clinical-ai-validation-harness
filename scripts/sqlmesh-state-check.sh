#!/usr/bin/env bash
# scripts/sqlmesh-state-check.sh
# Inspect SQLMesh state health. Reports environment count, snapshot
# count, snapshot-data table count, and orphan-view count. Exits 0 if
# healthy, 1 if drift detected.
#
# A state-drift situation looks like:
#   - sqlmesh._environments  = 0   (metadata wiped)
#   - sqlmesh__refapp_28_demo has tables (snapshot data persisted)
#   - refapp_28_demo has views pointing at sqlmesh__refapp_28_demo
#     tables SQLMesh no longer tracks
#
# This was the silent failure mode behind the clin__obs 0-rows
# incident. Recovery: ./scripts/reset-transform.sh
#
# Usage:
#   ./scripts/sqlmesh-state-check.sh           # default
#   ./scripts/sqlmesh-state-check.sh --quiet   # only print on drift
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
TARGET_DB="${TARGET_DB:-refapp_28_demo}"
STATE_DB="${STATE_DB:-sqlmesh}"
STATE_DATA_DB="${STATE_DATA_DB:-sqlmesh__refapp_28_demo}"
QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quiet) QUIET=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Preflight: container reachable?
if ! docker exec "$DB_CONTAINER" sh -c 'true' 2>/dev/null; then
  echo "ERROR: container '${DB_CONTAINER}' not running" >&2
  exit 1
fi

mariadb_query() {
  docker exec "$DB_CONTAINER" mariadb \
    --user=root --password="$DB_ROOT_PASS" \
    -N -B -e "$1" 2>/dev/null || echo "0"
}

ENV_COUNT=$(mariadb_query "SELECT COUNT(*) FROM \`${STATE_DB}\`._environments")
SNAP_COUNT=$(mariadb_query "SELECT COUNT(*) FROM \`${STATE_DB}\`._snapshots")
SNAP_DATA_COUNT=$(mariadb_query "
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema='${STATE_DATA_DB}'
")
TARGET_VIEW_COUNT=$(mariadb_query "
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema='${TARGET_DB}' AND table_type='VIEW'
")

# Detect orphan views: views in TARGET_DB whose underlying snapshot
# table no longer exists. Parse the view definition for the referenced
# sqlmesh__* table name and check.
ORPHAN_VIEWS=$(mariadb_query "
  SELECT COUNT(*) FROM (
    SELECT
      v.table_name,
      v.view_definition,
      SUBSTRING_INDEX(
        SUBSTRING_INDEX(
          SUBSTRING_INDEX(v.view_definition, '\`${STATE_DATA_DB}\`.\`', -1),
          '\`', 1),
        '\`', 1) AS snap_table
    FROM information_schema.views v
    WHERE v.table_schema='${TARGET_DB}'
  ) refs
  LEFT JOIN information_schema.tables t
    ON t.table_schema='${STATE_DATA_DB}' AND t.table_name=refs.snap_table
  WHERE t.table_name IS NULL
    AND refs.snap_table != ''
    AND refs.snap_table NOT LIKE '%refapp_28_demo.view_definition%'
")

# Health logic: drift if metadata is empty but snapshot data persists,
# OR if orphan views exist.
DRIFT=0
if [[ "$ENV_COUNT" == "0" && "$SNAP_DATA_COUNT" != "0" ]]; then
  DRIFT=1
fi
if [[ "$ORPHAN_VIEWS" != "0" ]]; then
  DRIFT=1
fi

if [[ "$QUIET" == "1" && "$DRIFT" == "0" ]]; then
  exit 0
fi

echo "SQLMesh state (${DB_CONTAINER}):"
printf "  %-30s %s\n" "sqlmesh._environments:"  "$ENV_COUNT"
printf "  %-30s %s\n" "sqlmesh._snapshots:"     "$SNAP_COUNT"
printf "  %-30s %s\n" "${STATE_DATA_DB}.tables:"  "$SNAP_DATA_COUNT"
printf "  %-30s %s\n" "${TARGET_DB}.views:"       "$TARGET_VIEW_COUNT"
printf "  %-30s %s\n" "orphan views:"             "$ORPHAN_VIEWS"

if [[ "$DRIFT" == "1" ]]; then
  echo ""
  echo "DRIFT DETECTED. Recover with: ./scripts/reset-transform.sh --plan"
  exit 1
fi

echo ""
echo "OK (no drift detected)"
exit 0
