#!/usr/bin/env bash
# scripts/loadtest-up.sh
# Bring up the hermetic loadback test surface: an `openmrs_test` schema
# that's a clone of the live CIEL-loaded `openmrs` schema. This is the
# canvas the dlt loader writes into during Phase 5 iteration. Keeping
# loadback against `openmrs_test` instead of the live `openmrs` means
# bad iterations don't destroy the clean CIEL baseline (recovery via
# `make ciel-baseline` is ~30 min).
#
# Strategy: mariadb-dump the live `openmrs` schema (Liquibase-applied
# 2.8 schema + CIEL concepts + stock 50 patients) and stream-load it
# into `openmrs_test`. ~1-2 min depending on data size. The stock 50
# patients are overwritten by the dlt loader's `replace` disposition.
#
# Usage:
#   ./scripts/loadtest-up.sh                  # default
#   ./scripts/loadtest-up.sh --force          # skip the existence prompt
#
# Idempotent: re-runnable. Asks before destroying an existing
# openmrs_test (use --force to skip).
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
DB_USER="${OMRS_DB_USER:-openmrs}"
SOURCE_DB="${SOURCE_DB:-openmrs}"
TARGET_DB="${TARGET_DB:-openmrs_test}"
STAGING_DB="${STAGING_DB:-${TARGET_DB}_dlt}"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Preflight: container reachable?
if ! docker exec "$DB_CONTAINER" sh -c 'true' 2>/dev/null; then
  echo "ERROR: container '${DB_CONTAINER}' not running. Run 'make up' first." >&2
  exit 1
fi

# Preflight: source schema populated?
SOURCE_TABLES=$(docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -N -B -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${SOURCE_DB}';")
if [[ "$SOURCE_TABLES" -lt 200 ]]; then
  echo "ERROR: source schema '${SOURCE_DB}' has only ${SOURCE_TABLES} tables; expected ≥200 (CIEL-loaded 2.8 schema)." >&2
  echo "  Run 'make ciel-baseline' first to populate it." >&2
  exit 1
fi

# Existence check on target
TARGET_EXISTS=$(docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -N -B -e "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='${TARGET_DB}';")
if [[ "$TARGET_EXISTS" == "1" ]] && [[ "$FORCE" != "1" ]]; then
  echo "Target schema '${TARGET_DB}' already exists."
  read -p "Drop + recreate? [y/N] " -n 1 -r
  echo
  [[ ! "$REPLY" =~ ^[Yy]$ ]] && { echo "Aborted."; exit 1; }
fi

echo "Dropping + recreating '${TARGET_DB}' and '${STAGING_DB}'..."
docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -e "DROP SCHEMA IF EXISTS \`${TARGET_DB}\`;
      DROP SCHEMA IF EXISTS \`${STAGING_DB}\`;
      CREATE SCHEMA \`${TARGET_DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
      CREATE SCHEMA \`${STAGING_DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
      GRANT ALL PRIVILEGES ON \`${TARGET_DB}\`.* TO '${DB_USER}'@'%';
      GRANT ALL PRIVILEGES ON \`${STAGING_DB}\`.* TO '${DB_USER}'@'%';
      FLUSH PRIVILEGES;"

# Get rough source size for progress feedback.
SRC_SIZE_MB=$(docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -N -B -e "
SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 0)
FROM information_schema.tables
WHERE table_schema='${SOURCE_DB}';")
echo "Cloning '${SOURCE_DB}' (~${SRC_SIZE_MB}MB) → '${TARGET_DB}' ..."

# Stream-dump source → stream-load target. Inside one docker-exec to avoid
# host-side network round-trips. mariadb-dump deterministic flags match
# scripts/snapshot-baseline.sh conventions.
time docker exec "$DB_CONTAINER" sh -c "
  mariadb-dump \
    --user=root --password='${DB_ROOT_PASS}' \
    --skip-comments \
    --skip-dump-date \
    --skip-tz-utc \
    --single-transaction \
    --quick \
    --hex-blob \
    --default-character-set=utf8mb4 \
    '${SOURCE_DB}' \
  | mariadb \
    --user=root --password='${DB_ROOT_PASS}' \
    --default-character-set=utf8mb4 \
    '${TARGET_DB}'
"

# Clear the stock RefApp demo-patient clinical-detail tables that the dlt load
# does NOT replace. Their rows belong to the RefApp's stock ~50 demo patients
# (seeded by referencedemodata), not our corpus, and would dangle once our
# remapped patients overwrite person/encounter/obs. Emptying them here yields a
# clean base; the load repopulates only our remapped data.
echo "Clearing stock demo-patient residue tables in '${TARGET_DB}'..."
docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -e "SET FOREIGN_KEY_CHECKS=0;
      TRUNCATE \`${TARGET_DB}\`.encounter_diagnosis;
      TRUNCATE \`${TARGET_DB}\`.obs_reference_range;
      TRUNCATE \`${TARGET_DB}\`.visit;
      TRUNCATE \`${TARGET_DB}\`.patient_appointment;
      TRUNCATE \`${TARGET_DB}\`.patient_appointment_audit;
      TRUNCATE \`${TARGET_DB}\`.patient_appointment_provider;"

# Verify
echo ""
echo "Final state of '${TARGET_DB}':"
docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -e "
SELECT
  (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${TARGET_DB}') AS tables,
  (SELECT COUNT(*) FROM \`${TARGET_DB}\`.concept)             AS concepts,
  (SELECT COUNT(*) FROM \`${TARGET_DB}\`.patient)             AS patients,
  (SELECT COUNT(*) FROM \`${TARGET_DB}\`.obs)                 AS obs,
  (SELECT COUNT(*) FROM \`${TARGET_DB}\`.encounter)           AS encounters
\G"

echo ""
echo "OK. Next: run dlt loader to overwrite the stock clinical data with the transformed legacy corpus."
echo "  make load-test"
