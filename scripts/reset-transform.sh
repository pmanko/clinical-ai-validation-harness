#!/usr/bin/env bash
# scripts/reset-transform.sh
# Destructive reset of the SQLMesh transform state. Drops three schemas
# and recreates the target so `sqlmesh plan` can re-initialize the prod
# environment from scratch.
#
# Why this exists: SQLMesh's metadata schema (`sqlmesh`) can decouple
# from its snapshot-data schema (`sqlmesh__refapp_28_demo`) — most
# commonly after a MariaDB container restart that reinitializes
# metadata while leaving snapshot tables in place. The result is
# orphaned views in `refapp_28_demo` pointing at snapshot tables
# SQLMesh no longer tracks; row counts can silently be wrong.
#
# Usage:
#   ./scripts/reset-transform.sh                   # confirm + drop + recreate
#   ./scripts/reset-transform.sh --force           # skip confirmation prompt
#   ./scripts/reset-transform.sh --plan            # also auto-run sqlmesh plan
#
# After reset, the next step is:
#   uv run sqlmesh -p datasets/transforms/sqlmesh plan prod --no-prompts --auto-apply
#
# Idempotent: safe to re-run; DROP IF EXISTS handles missing schemas.
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
DB_USER="${OMRS_DB_USER:-openmrs}"
TARGET_DB="${TARGET_DB:-refapp_28_demo}"
STATE_DB="${STATE_DB:-sqlmesh}"
STATE_DATA_DB="${STATE_DATA_DB:-sqlmesh__refapp_28_demo}"
FORCE=0
RUN_PLAN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --plan)  RUN_PLAN=1; shift ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Preflight: container reachable?
if ! docker exec "$DB_CONTAINER" sh -c 'true' 2>/dev/null; then
  echo "ERROR: container '${DB_CONTAINER}' is not running. Run 'make up' first." >&2
  exit 1
fi

# Summarize state before drop.
echo "Pre-reset state (in '${DB_CONTAINER}'):"
docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -N -B -e "
SELECT
  CONCAT('  refapp_28_demo.tables:    ', COUNT(*))
FROM information_schema.tables WHERE table_schema='${TARGET_DB}'
UNION ALL SELECT
  CONCAT('  sqlmesh__*.tables:        ', COUNT(*))
FROM information_schema.tables WHERE table_schema='${STATE_DATA_DB}'
UNION ALL SELECT
  CONCAT('  sqlmesh._snapshots:       ',
         IFNULL((SELECT COUNT(*) FROM \`${STATE_DB}\`._snapshots), 'schema missing'))
UNION ALL SELECT
  CONCAT('  sqlmesh._environments:    ',
         IFNULL((SELECT COUNT(*) FROM \`${STATE_DB}\`._environments), 'schema missing'));
" 2>/dev/null || echo "  (state schemas not present)"

if [[ "$FORCE" != "1" ]]; then
  echo ""
  echo "About to DROP these schemas (DESTRUCTIVE):"
  echo "  - ${TARGET_DB}            (materialized transform output)"
  echo "  - ${STATE_DATA_DB}        (SQLMesh snapshot data)"
  echo "  - ${STATE_DB}             (SQLMesh metadata)"
  echo ""
  echo "Legacy + openmrs schemas are NOT touched."
  echo ""
  read -p "Proceed? [y/N] " -n 1 -r
  echo
  if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

echo "Dropping schemas..."
docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -e "DROP SCHEMA IF EXISTS \`${TARGET_DB}\`;
      DROP SCHEMA IF EXISTS \`${STATE_DATA_DB}\`;
      DROP SCHEMA IF EXISTS \`${STATE_DB}\`;"

echo "Recreating empty target schema (sqlmesh requires it to exist on connect)..."
docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -e "CREATE SCHEMA \`${TARGET_DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
      GRANT ALL PRIVILEGES ON \`${TARGET_DB}\`.* TO '${DB_USER}'@'%';
      FLUSH PRIVILEGES;"

echo ""
echo "Reset complete."

if [[ "$RUN_PLAN" == "1" ]]; then
  echo "Running 'sqlmesh plan prod --no-prompts --auto-apply' ..."
  exec uv run sqlmesh -p datasets/transforms/sqlmesh plan prod --no-prompts --auto-apply
fi

echo ""
echo "Next step:"
echo "  uv run sqlmesh -p datasets/transforms/sqlmesh plan prod --no-prompts --auto-apply"
echo ""
echo "Or pass --plan to chain it from this script."
