#!/usr/bin/env bash
# scripts/load-demo-data.sh
# Load the OpenMRS 2.7 demo data dump into a disposable `legacy_27_raw`
# database on the harness MariaDB container, side-by-side with the running
# RefApp 3.6.0 stack's `openmrs` database. Used by T021 (profile inventory)
# and T024 (schema diff) — gives us the "before" half of the legacy→clean
# diff without disturbing the live OpenMRS schema.
#
# The 2.7 dump is portable (no USE / CREATE DATABASE statements), 143 tables,
# full DDL + DML, MySQL 5.7 / utf8 origin. We load with --default-character-set
# =utf8mb4 so the bytes survive even though source charset is utf8 (the
# 3-byte subset of utf8mb4).
#
# Usage:
#   ./scripts/load-demo-data.sh                                # defaults
#   ./scripts/load-demo-data.sh --src PATH --db legacy_27_raw  # explicit
#   ./scripts/load-demo-data.sh --reset                        # drop + reload
set -euo pipefail

SRC="${DEMO_DATA_SQL:-data/large-demo-data-2-7-0.sql}"
DB="${LEGACY_DB:-legacy_27_raw}"
DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_USER="${OMRS_DB_USER:-openmrs}"
DB_PASS="${OMRS_DB_PASSWORD:-openmrs}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
RESET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src) SRC="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
    --reset) RESET=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -f "$SRC" ]]; then
  echo "ERROR: demo dump not found at $SRC" >&2
  exit 1
fi

# Detect whether the target DB already has rows; bail unless --reset.
EXISTING=$(docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -N -B -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB}';" 2>/dev/null || echo 0)
if [[ "$EXISTING" != "0" ]]; then
  if [[ "$RESET" != "1" ]]; then
    echo "Target DB '${DB}' already has ${EXISTING} tables. Re-run with --reset to drop + reload." >&2
    echo "(idempotent no-op)"
    exit 0
  fi
  echo "Dropping existing '${DB}' (${EXISTING} tables)..."
  docker exec "$DB_CONTAINER" mariadb \
    --user=root --password="$DB_ROOT_PASS" \
    -e "DROP DATABASE IF EXISTS \`${DB}\`;"
fi

echo "Creating '${DB}' + granting '${DB_USER}' all privileges on it..."
docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -e "CREATE DATABASE \`${DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
      GRANT ALL PRIVILEGES ON \`${DB}\`.* TO '${DB_USER}'@'%';
      FLUSH PRIVILEGES;"

SIZE=$(wc -c < "$SRC" | tr -d ' ')
SIZE_HUMAN=$(awk -v b="$SIZE" 'BEGIN { split("B KB MB GB TB", u); i=1; while (b>=1024 && i<5) { b/=1024; i++ } printf("%.1f %s", b, u[i]) }')
echo "Loading ${SRC} (${SIZE_HUMAN}) into ${DB_CONTAINER}:${DB} ..."
time docker exec -i "$DB_CONTAINER" mariadb \
  --user="$DB_USER" --password="$DB_PASS" \
  --default-character-set=utf8mb4 \
  "$DB" < "$SRC"

echo ""
echo "Load complete. Row-count sanity check:"
docker exec "$DB_CONTAINER" mariadb \
  --user="$DB_USER" --password="$DB_PASS" "$DB" \
  -e "
SELECT
  (SELECT COUNT(*) FROM patient)            AS patient,
  (SELECT COUNT(*) FROM person)             AS person,
  (SELECT COUNT(*) FROM encounter)          AS encounter,
  (SELECT COUNT(*) FROM obs)                AS obs,
  (SELECT COUNT(*) FROM concept)            AS concept,
  (SELECT COUNT(*) FROM allergy)            AS allergy,
  (SELECT COUNT(*) FROM conditions)         AS conditions,
  (SELECT COUNT(*) FROM orders)             AS orders,
  (SELECT COUNT(*) FROM drug_order)         AS drug_order
\G"
