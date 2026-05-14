#!/usr/bin/env bash
# scripts/load-baseline.sh
# Fast-path: load a pre-snapshotted CIEL baseline SQL into the running harness
# MariaDB. Used on fresh restarts to skip the slow openconceptlab import.
#
# Usage:
#   ./scripts/load-baseline.sh --version v2026-04-28
#   ./scripts/load-baseline.sh --version v2026-04-28 --from PATH   # override input
#
set -euo pipefail
VERSION=""
SRC=""
DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_USER="${OMRS_DB_USER:-openmrs}"
DB_PASS="${OMRS_DB_PASSWORD:-openmrs}"
DB_NAME="${OMRS_DB_NAME:-openmrs}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --from) SRC="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done
if [[ -z "$VERSION" ]] && [[ -z "$SRC" ]]; then
  echo "Usage: $0 --version <ciel-version> | --from PATH" >&2
  exit 1
fi

SRC="${SRC:-datasets/sources/ocl/CIEL/${VERSION}/seeded-baseline.sql}"
PROVENANCE="datasets/sources/ocl/CIEL/${VERSION}/seeded-baseline.provenance.json"

if [[ ! -f "$SRC" ]]; then
  echo "ERROR: baseline SQL not found at $SRC" >&2
  echo "       Generate one with: ./scripts/snapshot-baseline.sh --version ${VERSION}" >&2
  exit 1
fi

if [[ -f "$PROVENANCE" ]]; then
  EXPECTED=$(python3 -c "import json; print(json.load(open('$PROVENANCE'))['sha256'])")
  ACTUAL=$(shasum -a 256 "$SRC" | awk '{print $1}')
  if [[ "$EXPECTED" != "$ACTUAL" ]]; then
    echo "ERROR: SHA-256 mismatch for $SRC" >&2
    echo "  expected: $EXPECTED" >&2
    echo "  actual:   $ACTUAL" >&2
    exit 1
  fi
  echo "Checksum OK ($ACTUAL)"
fi

SIZE=$(stat -f %z "$SRC" 2>/dev/null || stat -c %s "$SRC")
echo "Loading ${SRC} ($(numfmt --to=iec-i --suffix=B "$SIZE" 2>/dev/null || echo "${SIZE} bytes")) into ${DB_CONTAINER}:${DB_NAME} ..."
time docker exec -i "${DB_CONTAINER}" mariadb \
  --user="${DB_USER}" \
  --password="${DB_PASS}" \
  --default-character-set=utf8mb4 \
  "${DB_NAME}" \
  < "$SRC"

echo "Load complete."
echo ""
echo "Verify row counts:"
docker exec "${DB_CONTAINER}" mariadb \
  --user="${DB_USER}" --password="${DB_PASS}" "${DB_NAME}" \
  -e "
SELECT
  (SELECT COUNT(*) FROM concept) AS concept,
  (SELECT COUNT(*) FROM concept_name) AS concept_name,
  (SELECT COUNT(*) FROM concept_reference_term) AS concept_reference_term,
  (SELECT COUNT(*) FROM concept_reference_map) AS concept_reference_map\G
"
