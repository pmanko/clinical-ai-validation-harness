#!/usr/bin/env bash
# scripts/seed-local.sh
# Provision the local OpenMRS instance FROM the portable demo-data dump — OpenMRS's
# native "the demo data IS the database" path. Restores into a fresh `openmrs`
# (DROP/CREATE), then the backend boots and Liquibase reconciles on top. We never
# mutate a running backend's schema in place (that desynced module/Liquibase state
# and broke chartsearchai — the reason promote.sh was retired).
#
# The dump is TARGET-NEUTRAL and module-clean (chartsearchai tables + changelog
# rows stripped by dump-loaded.sh), so the chartsearchai module installs itself
# fresh on boot — no "table already exists" Liquibase race.
#
# Serves BOTH provisioning modes:
#   - reset-provision (canonical):  make reset && make up && make seed
#   - reseed-in-place (fast iter) :  make seed        (against a running stack)
#
# Usage:
#   ./scripts/seed-local.sh                      # newest artifacts/*/transform/refapp_28_demo.sql.gz → openmrs
#   ./scripts/seed-local.sh --dump PATH          # explicit dump file (.sql or .sql.gz)
#   ./scripts/seed-local.sh --from-schema openmrs_test   # dump that schema now (module-clean), then load it
#   ./scripts/seed-local.sh --target openmrs --no-reindex
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
DB_USER="${OMRS_DB_USER:-openmrs}"
BACKEND="${OPENMRS_BACKEND:-harness-openmrs-backend}"
PROXY_PORT="${PROXY_PORT:-${HARNESS_PROXY_HTTP_PORT:-8088}}"
TARGET_DB="${SEED_TARGET_DB:-openmrs}"
DUMP=""
FROM_SCHEMA=""
REINDEX=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dump) DUMP="$2"; shift 2 ;;
    --from-schema) FROM_SCHEMA="$2"; shift 2 ;;
    --target) TARGET_DB="$2"; shift 2 ;;
    --no-reindex) REINDEX=0; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

if ! docker exec "$DB_CONTAINER" sh -c 'true' 2>/dev/null; then
  echo "ERROR: container '${DB_CONTAINER}' not running. Run 'make up' first." >&2
  exit 1
fi

# --- resolve the dump to restore ---
if [[ -n "$FROM_SCHEMA" ]]; then
  echo "==> building a module-clean dump from '${FROM_SCHEMA}' (dump-loaded.sh)"
  DUMP="${ROOT}/artifacts/seed-local/refapp_28_demo.sql.gz"
  mkdir -p "$(dirname "$DUMP")"
  SOURCE_DB="$FROM_SCHEMA" "${ROOT}/scripts/dump-loaded.sh" --source "$FROM_SCHEMA" --out "$DUMP"
elif [[ -z "$DUMP" ]]; then
  # newest dump-loaded.sh artifact
  DUMP="$(ls -t "${ROOT}"/artifacts/*/transform/refapp_28_demo.sql.gz 2>/dev/null | head -1 || true)"
  if [[ -z "$DUMP" ]]; then
    echo "ERROR: no dump found under artifacts/*/transform/refapp_28_demo.sql.gz" >&2
    echo "  Build one first:  make dump-loaded SOURCE=openmrs_test" >&2
    echo "  or dump-and-seed in one step:  make seed FROM_SCHEMA=openmrs_test" >&2
    exit 1
  fi
fi
if [[ ! -f "$DUMP" ]]; then
  echo "ERROR: dump not found: ${DUMP}" >&2
  exit 1
fi
echo "==> dump: ${DUMP} ($(du -h "$DUMP" | cut -f1))"

# --- stop the backend so the schema swap doesn't race a live Hibernate/Liquibase ---
echo "==> stopping backend '${BACKEND}' (provision into a quiescent DB)"
docker stop "$BACKEND" >/dev/null 2>&1 || true

# --- DROP/CREATE the target schema + restore (target-neutral dump → named DB) ---
echo "==> recreating '${TARGET_DB}' and restoring the dump"
docker exec "$DB_CONTAINER" mariadb --user=root --password="$DB_ROOT_PASS" -e "
  DROP DATABASE IF EXISTS \`${TARGET_DB}\`;
  CREATE DATABASE \`${TARGET_DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
  GRANT ALL PRIVILEGES ON \`${TARGET_DB}\`.* TO '${DB_USER}'@'%';
  FLUSH PRIVILEGES;"

if [[ "$DUMP" == *.gz ]]; then
  gunzip -c "$DUMP" | docker exec -i "$DB_CONTAINER" mariadb \
    --user=root --password="$DB_ROOT_PASS" --default-character-set=utf8mb4 "$TARGET_DB"
else
  docker exec -i "$DB_CONTAINER" mariadb \
    --user=root --password="$DB_ROOT_PASS" --default-character-set=utf8mb4 "$TARGET_DB" < "$DUMP"
fi

echo "    restored. row counts (sample):"
docker exec "$DB_CONTAINER" mariadb --user=root --password="$DB_ROOT_PASS" "$TARGET_DB" -e "
  SELECT 'patient' AS tbl, COUNT(*) AS rows_ct FROM patient
  UNION ALL SELECT 'encounter', COUNT(*) FROM encounter
  UNION ALL SELECT 'obs', COUNT(*) FROM obs;" || true

# --- start the backend; Liquibase reconciles core, chartsearchai installs fresh ---
echo "==> starting backend '${BACKEND}' (Liquibase upgrade-in-place + module install)"
docker start "$BACKEND" >/dev/null
echo "    waiting for backend health (first boot runs Liquibase; can take minutes)..."
UP=0
for i in $(seq 1 100); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -u admin:Admin123 \
    "http://localhost:${PROXY_PORT}/openmrs/ws/fhir2/R4/Patient?_count=1" || true)
  [ "$code" = "200" ] && { echo "    backend up (~$((i*6))s)"; UP=1; break; }
  sleep 6
done
[ "$UP" = "1" ] || { echo "ERROR: backend did not become healthy; check 'make logs SERVICE=backend'." >&2; exit 1; }

# --- reindex: bulk INSERTs don't fire Hibernate Search listeners, so the Lucene
#     index is empty until a full reindex. Synchronous; ~30-60s for 5K patients. ---
if [[ "$REINDEX" == "1" ]]; then
  echo "==> triggering Hibernate Search reindex (synchronous)"
  curl -fsS -u admin:Admin123 -m 600 -X POST \
    "http://localhost:${PROXY_PORT}/openmrs/ws/rest/v1/searchindexupdate" >/dev/null \
    && echo "    reindex complete" \
    || echo "    WARNING: reindex POST failed — run it manually once the backend settles."
fi

echo ""
echo "✓ seeded '${TARGET_DB}' from ${DUMP}."
echo "  chartsearchai reads the querystore index — if chat looks stale, rebuild it (querystore reindex)."
