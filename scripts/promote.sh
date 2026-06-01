#!/usr/bin/env bash
# scripts/promote.sh
# Promote the loaded, verified-clean schema (default: openmrs_test) into the
# canonical schema the RefApp backend reads (default: openmrs), then restart the
# backend to clear Hibernate caches.
#
# GATED (FR-013): refuses to promote unless the source schema passes the orphan-FK
# audit with ZERO orphans — a dirty dataset never reaches the live schema.
#
# Usage:
#   ./scripts/promote.sh                 # openmrs_test → openmrs (+ restart)
#   PROMOTE_SOURCE_DB=openmrs_test PROMOTE_TARGET_DB=openmrs ./scripts/promote.sh
#   ./scripts/promote.sh --no-restart    # skip the backend restart
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
SOURCE_DB="${PROMOTE_SOURCE_DB:-openmrs_test}"
TARGET_DB="${PROMOTE_TARGET_DB:-openmrs}"
BACKEND="${OPENMRS_BACKEND:-harness-openmrs-backend}"
PROXY_PORT="${PROXY_PORT:-8088}"
RESTART=1
[ "${1:-}" = "--no-restart" ] && RESTART=0

if ! docker exec "$DB_CONTAINER" sh -c 'true' 2>/dev/null; then
  echo "ERROR: container '${DB_CONTAINER}' not running. Run 'make up' first." >&2
  exit 1
fi

# --- FR-013 gate: source must be referentially clean before it can go live ---
echo "==> FR-013 gate: auditing '${SOURCE_DB}' (must be 0 orphans to promote)"
if ! uv run python -m harness.transform.orphan_fk --target "${SOURCE_DB}"; then
  echo "REFUSING TO PROMOTE: '${SOURCE_DB}' has orphan FKs. Fix the load and re-run." >&2
  exit 1
fi

# --- FR-013 completeness gate: no non-empty source table silently dropped ---
echo "==> FR-013 completeness gate: every non-empty source table loaded or excluded-with-reason"
if ! uv run python -m harness.transform.completeness; then
  echo "REFUSING TO PROMOTE: completeness gate failed (a source table is silently dropped)." >&2
  exit 1
fi

# --- copy SOURCE_DB → TARGET_DB (drop+recreate tables, full data) ---
echo "==> promoting '${SOURCE_DB}' → '${TARGET_DB}'"
docker exec "$DB_CONTAINER" sh -c "
  mariadb-dump --user=root --password='${DB_ROOT_PASS}' \
    --add-drop-table --skip-comments --single-transaction --quick --hex-blob \
    --default-character-set=utf8mb4 '${SOURCE_DB}' \
  | mariadb --user=root --password='${DB_ROOT_PASS}' \
    --default-character-set=utf8mb4 '${TARGET_DB}'
"

# --- confirm the live schema is clean ---
echo "==> verifying '${TARGET_DB}' is referentially clean"
uv run python -m harness.transform.orphan_fk --target "${TARGET_DB}"

if [ "$RESTART" = "1" ]; then
  echo "==> restarting backend '${BACKEND}' (clear Hibernate caches)"
  docker restart "$BACKEND" >/dev/null
  echo "    waiting for backend health..."
  for i in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w "%{http_code}" -u admin:Admin123 \
      "http://localhost:${PROXY_PORT}/openmrs/ws/fhir2/R4/Patient?_count=1" || true)
    [ "$code" = "200" ] && { echo "    backend up (~$((i*6))s)"; break; }
    sleep 6
  done
fi

echo "✓ promoted '${SOURCE_DB}' → '${TARGET_DB}'."
echo "  chartsearchai reads the querystore ES index — if its data looks stale,"
echo "  rebuild the index (querystore reindex) so chat reflects the promoted data."
