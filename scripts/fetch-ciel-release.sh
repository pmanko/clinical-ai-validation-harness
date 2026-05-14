#!/usr/bin/env bash
# scripts/fetch-ciel-release.sh
# Download a pinned CIEL release ZIP from OCL into datasets/sources/ocl/CIEL/<version>/.
#
# Usage:
#   ./scripts/fetch-ciel-release.sh --version v2026-04-28
#   ./scripts/fetch-ciel-release.sh --version v2026-04-28 --force   # re-download even if cached
#
# Token comes from keychain via harness.ocl.get_token (no echoing).
# Writes the ZIP to datasets/sources/ocl/CIEL/<version>/CIEL_<version>.zip plus
# provenance.json with SHA-256, size, source URL, retrieval timestamp.
set -euo pipefail
VERSION=""
FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done
if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 --version <ciel-version>  (e.g. v2026-04-28)" >&2
  exit 1
fi

DEST_DIR="datasets/sources/ocl/CIEL/${VERSION}"
ZIP_PATH="${DEST_DIR}/CIEL_${VERSION}.zip"
PROVENANCE="${DEST_DIR}/provenance.json"

mkdir -p "$DEST_DIR"

if [[ -f "$ZIP_PATH" ]] && [[ "$FORCE" != "1" ]]; then
  echo "Already cached: $ZIP_PATH"
  echo "(use --force to re-download)"
  ls -lh "$ZIP_PATH"
  exit 0
fi

echo "Resolving OCL token from keychain..."
TOK=$(python3 -c "from harness.ocl import get_token; print(get_token())")

EXPORT_URL="https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/${VERSION}/export/"
echo "Resolving signed download URL via ${EXPORT_URL}..."
SIGNED_URL=$(curl -sS -L -o /dev/null -w "%{url_effective}" \
  -H "Authorization: Token $TOK" \
  "$EXPORT_URL")
if [[ -z "$SIGNED_URL" ]] || [[ "$SIGNED_URL" == "$EXPORT_URL" ]]; then
  echo "ERROR: could not resolve signed download URL (got: $SIGNED_URL)" >&2
  exit 1
fi
echo "Resolved (S3 signed URL; redacted)."

echo "Downloading CIEL ${VERSION} ZIP -> $ZIP_PATH ..."
curl -sS -L -o "$ZIP_PATH" "$SIGNED_URL" --progress-bar
echo "Download complete."

SIZE=$(stat -f %z "$ZIP_PATH" 2>/dev/null || stat -c %s "$ZIP_PATH")
SHA=$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')

python3 - <<PY > "$PROVENANCE"
import json, datetime, os
data = {
  "collection": "CIEL",
  "version": "${VERSION}",
  "ocl_source": "/orgs/CIEL/sources/CIEL/${VERSION}/",
  "ocl_export_endpoint": "${EXPORT_URL}",
  "local_path": "${ZIP_PATH}",
  "sha256": "${SHA}",
  "size_bytes": ${SIZE},
  "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "note": "Pinned CIEL release. Signed S3 URL has 7-day expiry; re-resolve via export/ endpoint if needed.",
}
print(json.dumps(data, indent=2))
PY

echo ""
ls -lh "$ZIP_PATH"
echo ""
echo "Provenance:"
cat "$PROVENANCE"
