#!/usr/bin/env bash
# Build the chartsearchai ESM bundle from the pinned submodule and stage
# it under artifacts/openmrs/spa-custom/ for Caddy to serve (which shadows
# the bundle baked into :nightly-chartsearch). The regenerated importmap
# is fetched from the running frontend container so unrelated entries
# stay in sync with whatever upstream nightly is currently in use.
#
# Layout produced under artifacts/openmrs/spa-custom/:
#   importmap.json                                           — Caddy-served
#   openmrs-esm-chartsearchai-app-multiturn/main.js          — Caddy-served
#   openmrs-esm-chartsearchai-app-multiturn/<chunks>.js      — Caddy-served
#
# Mirror of `make chartsearch-build` for the .omod side.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ESM_DIR="${ROOT}/targets/chartsearchai-esm"
ARTIFACT_DIR="${ROOT}/artifacts/openmrs/spa-custom"
TARGET_NAME="openmrs-esm-chartsearchai-app-multiturn"

if [ ! -d "${ESM_DIR}" ]; then
  echo "error: ESM submodule not initialized at ${ESM_DIR}" >&2
  echo "  run: git submodule update --init --recursive" >&2
  exit 1
fi

echo "==> yarn install ($(cd "${ESM_DIR}" && pwd))"
(cd "${ESM_DIR}" && yarn install)

echo "==> yarn build"
(cd "${ESM_DIR}" && yarn build)

echo "==> stage dist/ → artifacts/openmrs/spa-custom/${TARGET_NAME}/"
mkdir -p "${ARTIFACT_DIR}/${TARGET_NAME}"
rsync -a --delete "${ESM_DIR}/dist/" "${ARTIFACT_DIR}/${TARGET_NAME}/"

echo "==> regenerate custom importmap.json"
"${ROOT}/scripts/chartsearch-importmap-gen.sh"

echo "==> esm build complete:"
ls -lh "${ARTIFACT_DIR}/${TARGET_NAME}/openmrs-esm-chartsearchai-app.js" "${ARTIFACT_DIR}/importmap.json" 2>/dev/null || true
