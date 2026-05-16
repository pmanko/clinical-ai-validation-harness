#!/usr/bin/env bash
# scripts/loadtest-down.sh
# Drop the hermetic loadback test surface (`openmrs_test`).
# Idempotent: no-op if the schema doesn't exist.
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
TARGET_DB="${TARGET_DB:-openmrs_test}"
STAGING_DB="${STAGING_DB:-${TARGET_DB}_dlt}"

if ! docker exec "$DB_CONTAINER" sh -c 'true' 2>/dev/null; then
  echo "ERROR: container '${DB_CONTAINER}' not running." >&2
  exit 1
fi

echo "Dropping schemas '${TARGET_DB}' and '${STAGING_DB}' (if exist)..."
docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -e "DROP SCHEMA IF EXISTS \`${TARGET_DB}\`;
      DROP SCHEMA IF EXISTS \`${STAGING_DB}\`;"

echo "OK."
