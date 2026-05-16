#!/usr/bin/env bash
# scripts/dump-loaded.sh
# Dump a loaded OpenMRS schema (default: openmrs_test) into a portable
# SQL.gz file ready to ship — same shape as the original
# data/large-demo-data-2-7-0.sql.zip we started with, so a downstream
# consumer can `gunzip | mariadb` it into a fresh empty DB.
#
# The dump uses deterministic flags (no comments, no dump-date,
# extended-inserts for speed, hex-blob for binary safety) so two runs
# against identical state produce byte-identical output (SC-004).
#
# Usage:
#   ./scripts/dump-loaded.sh                                    # default openmrs_test → artifacts/<run>/transform/refapp_28_demo.sql.gz
#   ./scripts/dump-loaded.sh --source openmrs --out /tmp/x.sql.gz
#   ./scripts/dump-loaded.sh --no-gzip                          # plain .sql
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
SOURCE_DB="${SOURCE_DB:-openmrs_test}"
OUT=""
GZIP=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) SOURCE_DB="$2"; shift 2 ;;
    --out)    OUT="$2"; shift 2 ;;
    --no-gzip) GZIP=0; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

if ! docker exec "$DB_CONTAINER" sh -c 'true' 2>/dev/null; then
  echo "ERROR: container '${DB_CONTAINER}' not running. Run 'make up'." >&2
  exit 1
fi

if [[ -z "$OUT" ]]; then
  RUN_ID="dev-$(date -u +%Y%m%d-%H%M%S)"
  EXT="sql.gz"; [[ "$GZIP" == "0" ]] && EXT="sql"
  OUT="artifacts/${RUN_ID}/transform/refapp_28_demo.${EXT}"
fi
mkdir -p "$(dirname "$OUT")"

ROW_COUNT=$(docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -N -B -e "SELECT SUM(table_rows) FROM information_schema.tables WHERE table_schema='${SOURCE_DB}';" \
  2>/dev/null | head -1)
TABLE_COUNT=$(docker exec "$DB_CONTAINER" mariadb \
  --user=root --password="$DB_ROOT_PASS" \
  -N -B -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${SOURCE_DB}';" \
  2>/dev/null | head -1)

echo "Dumping '${SOURCE_DB}' (${TABLE_COUNT} tables, ~${ROW_COUNT} rows) → ${OUT}"

DUMP_CMD=(
  docker exec "$DB_CONTAINER" mariadb-dump
  --user=root --password="$DB_ROOT_PASS"
  --skip-comments
  --skip-dump-date
  --skip-tz-utc
  --skip-add-locks
  --skip-disable-keys
  --single-transaction
  --quick
  --extended-insert
  --hex-blob
  --default-character-set=utf8mb4
  --databases "$SOURCE_DB"
)

if [[ "$GZIP" == "1" ]]; then
  time "${DUMP_CMD[@]}" | gzip -9 > "$OUT"
else
  time "${DUMP_CMD[@]}" > "$OUT"
fi

SIZE=$(wc -c < "$OUT" | tr -d ' ')
SIZE_HUMAN=$(awk -v b="$SIZE" 'BEGIN { split("B KB MB GB", u); i=1; while (b>=1024 && i<4) { b/=1024; i++ } printf("%.1f %s", b, u[i]) }')
SHA=$(shasum -a 256 "$OUT" | awk '{print $1}')

cat > "${OUT}.provenance.json" <<EOF
{
  "source_schema": "${SOURCE_DB}",
  "table_count": ${TABLE_COUNT},
  "approx_row_count": ${ROW_COUNT:-0},
  "output_path": "${OUT}",
  "output_bytes": ${SIZE},
  "output_sha256": "${SHA}",
  "gzipped": $([ "$GZIP" == "1" ] && echo "true" || echo "false"),
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "generator": "scripts/dump-loaded.sh",
  "load_into_command": "$([ "$GZIP" == "1" ] && echo "zcat ${OUT} | mariadb -u root -p" || echo "mariadb -u root -p < ${OUT}")"
}
EOF

echo ""
echo "✓ ${OUT} (${SIZE_HUMAN})"
echo "  sha256: ${SHA}"
echo "  provenance: ${OUT}.provenance.json"
echo ""
echo "Load into a fresh MariaDB elsewhere with:"
if [[ "$GZIP" == "1" ]]; then
  echo "  zcat ${OUT} | mariadb -u root -p"
else
  echo "  mariadb -u root -p < ${OUT}"
fi
