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
# By DEFAULT the dump is a clean portable CORPUS: OpenMRS-core + clinical only, with the consumer
# chartsearchai module's tables AND its liquibasechangelog rows excluded, so it loads onto any RefApp
# and the module installs itself fresh on boot (no checksum mismatch). Override the module prefix with
# MODULE_PREFIX=, or keep all module state (full backup) with --include-module-state.
#
# Usage:
#   ./scripts/dump-loaded.sh                                    # clean corpus, default openmrs_test → artifacts/<run>/transform/refapp_28_demo.sql.gz
#   ./scripts/dump-loaded.sh --source openmrs --out /tmp/x.sql.gz
#   ./scripts/dump-loaded.sh --no-gzip                          # plain .sql
#   ./scripts/dump-loaded.sh --include-module-state            # full backup (keep chartsearchai tables + changelog)
#   ./scripts/dump-loaded.sh --ignore-pattern 'foo_%'          # exclude additional table patterns
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-openmrs}"
SOURCE_DB="${SOURCE_DB:-openmrs_test}"
OUT=""
GZIP=1
IGNORE_PATTERNS=()
# A portable CORPUS is OpenMRS-core + clinical only — never the consumer-side chartsearchai
# module's state. By default we exclude BOTH its tables AND its liquibasechangelog rows: those
# rows carry version-specific checksums, so shipping them makes the module fail to start under a
# different omod version (liquibase checksum mismatch). With them absent, the module's own
# liquibase installs it fresh on boot. --include-module-state keeps everything (a full backup).
MODULE_PREFIX="${MODULE_PREFIX:-chartsearchai}"
EXCLUDE_MODULE=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) SOURCE_DB="$2"; shift 2 ;;
    --out)    OUT="$2"; shift 2 ;;
    --no-gzip) GZIP=0; shift ;;
    --ignore-pattern) IGNORE_PATTERNS+=("$2"); shift 2 ;;
    --include-module-state) EXCLUDE_MODULE=0; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done
# Exclude the consumer module's TABLES via the existing ignore mechanism (its changelog rows are
# stripped separately in the dump below, since mariadb-dump can't row-filter within --databases).
[[ "$EXCLUDE_MODULE" == "1" ]] && IGNORE_PATTERNS+=("${MODULE_PREFIX}_%")

# Resolve --ignore-pattern globs to concrete --ignore-table flags by querying
# information_schema. mariadb-dump itself doesn't accept LIKE patterns.
IGNORE_TABLE_FLAGS=()
EXCLUDED_TABLES=()
for pat in "${IGNORE_PATTERNS[@]:-}"; do
  [[ -z "$pat" ]] && continue
  while IFS= read -r tbl; do
    [[ -z "$tbl" ]] && continue
    IGNORE_TABLE_FLAGS+=( "--ignore-table=${SOURCE_DB}.${tbl}" )
    EXCLUDED_TABLES+=( "$tbl" )
  done < <(docker exec "$DB_CONTAINER" mariadb \
    --user=root --password="$DB_ROOT_PASS" \
    -N -B -e "SELECT table_name FROM information_schema.tables WHERE table_schema='${SOURCE_DB}' AND table_name LIKE '${pat}';" \
    2>/dev/null)
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

if (( ${#EXCLUDED_TABLES[@]} > 0 )); then
  EFFECTIVE_TABLE_COUNT=$(( TABLE_COUNT - ${#EXCLUDED_TABLES[@]} ))
  echo "Dumping '${SOURCE_DB}' (${EFFECTIVE_TABLE_COUNT} of ${TABLE_COUNT} tables, ~${ROW_COUNT} rows; excluding ${#EXCLUDED_TABLES[@]}: ${EXCLUDED_TABLES[*]}) → ${OUT}"
  TABLE_COUNT=$EFFECTIVE_TABLE_COUNT
else
  echo "Dumping '${SOURCE_DB}' (${TABLE_COUNT} tables, ~${ROW_COUNT} rows) → ${OUT}"
fi

COMMON_FLAGS=(
  --user=root --password="$DB_ROOT_PASS"
  --skip-comments --skip-dump-date --skip-tz-utc --skip-add-locks --skip-disable-keys
  --single-transaction --quick --extended-insert --hex-blob --default-character-set=utf8mb4
)

# Stream the dump. When excluding a consumer module, do it in two parts: (1) everything except
# liquibasechangelog (its tables already in IGNORE_TABLE_FLAGS), keeping --databases so the dump is
# self-contained; (2) liquibasechangelog WITHOUT the module's rows, no --databases so it applies to
# the schema part 1 USE'd. mariadb-dump can't row-filter inside a --databases dump, hence the split.
dump_stream() {
  if [[ "$EXCLUDE_MODULE" == "1" ]]; then
    docker exec "$DB_CONTAINER" mariadb-dump "${COMMON_FLAGS[@]}" "${IGNORE_TABLE_FLAGS[@]}" \
      --ignore-table="${SOURCE_DB}.liquibasechangelog" --databases "$SOURCE_DB"
    docker exec "$DB_CONTAINER" mariadb-dump "${COMMON_FLAGS[@]}" \
      --where="id NOT LIKE '${MODULE_PREFIX}%' AND filename NOT LIKE '%${MODULE_PREFIX}%'" \
      "$SOURCE_DB" liquibasechangelog
  else
    docker exec "$DB_CONTAINER" mariadb-dump "${COMMON_FLAGS[@]}" "${IGNORE_TABLE_FLAGS[@]}" \
      --databases "$SOURCE_DB"
  fi
}

if [[ "$GZIP" == "1" ]]; then
  time dump_stream | gzip -9 > "$OUT"
else
  time dump_stream > "$OUT"
fi

SIZE=$(wc -c < "$OUT" | tr -d ' ')
SIZE_HUMAN=$(awk -v b="$SIZE" 'BEGIN { split("B KB MB GB", u); i=1; while (b>=1024 && i<4) { b/=1024; i++ } printf("%.1f %s", b, u[i]) }')
SHA=$(shasum -a 256 "$OUT" | awk '{print $1}')

EXCLUDED_JSON="[]"
if (( ${#EXCLUDED_TABLES[@]} > 0 )); then
  EXCLUDED_JSON=$(printf '%s\n' "${EXCLUDED_TABLES[@]}" | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')
fi

cat > "${OUT}.provenance.json" <<EOF
{
  "source_schema": "${SOURCE_DB}",
  "table_count": ${TABLE_COUNT},
  "approx_row_count": ${ROW_COUNT:-0},
  "excluded_tables": ${EXCLUDED_JSON},
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
