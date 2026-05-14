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
  # Validate the provenance file shape before trusting its sha256. A malformed
  # provenance.json should fail fast with a clear message, not a python
  # traceback in front of the operator.
  EXPECTED=$(python3 - "$PROVENANCE" <<'PY' 2>/dev/null || true
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
except (OSError, json.JSONDecodeError) as e:
    sys.stderr.write(f"provenance unreadable: {e}\n")
    sys.exit(2)
sha = data.get("sha256")
if not isinstance(sha, str) or len(sha) != 64:
    sys.stderr.write("provenance missing valid sha256 field\n")
    sys.exit(3)
print(sha)
PY
)
  if [[ -z "$EXPECTED" ]]; then
    echo "ERROR: provenance file $PROVENANCE is missing/invalid (no sha256). Refusing to load." >&2
    exit 1
  fi
  ACTUAL=$(shasum -a 256 "$SRC" | awk '{print $1}')
  if [[ "$EXPECTED" != "$ACTUAL" ]]; then
    echo "ERROR: SHA-256 mismatch for $SRC" >&2
    echo "  expected: $EXPECTED" >&2
    echo "  actual:   $ACTUAL" >&2
    exit 1
  fi
  echo "Checksum OK ($ACTUAL)"
else
  echo "WARNING: no provenance file at $PROVENANCE; loading without checksum verification."
fi

# Portable byte count: wc -c is on every POSIX system; avoids the macOS/Linux
# stat-flag fork (-f vs -c) and the GNU-only numfmt.
SIZE=$(wc -c < "$SRC" | tr -d ' ')
SIZE_HUMAN=$(awk -v b="$SIZE" 'BEGIN { split("B KB MB GB TB", u); i=1; while (b>=1024 && i<5) { b/=1024; i++ } printf("%.1f %s", b, u[i]) }')
echo "Loading ${SRC} (${SIZE_HUMAN}) into ${DB_CONTAINER}:${DB_NAME} ..."
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
