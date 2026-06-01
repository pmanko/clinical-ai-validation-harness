#!/usr/bin/env bash
# Generate the custom importmap.json that Caddy serves at
# /openmrs/spa/importmap.json. We fetch the current baked importmap from
# the running frontend container, then rewrite only the
# @openmrs/esm-chartsearchai-app entry to point at our locally-built
# bundle directory. Re-fetching the base each run keeps unrelated module
# version entries in sync with whatever `:nightly-chartsearch` is
# currently in use — no manual editing of importmap.json ever.
#
# Where the base is fetched from:
#   - default: the local docker container `harness-openmrs-frontend`
#   - cloud:   pass CLOUD=1 to fetch via gcp_ssh + the VM's container
#
# Output: artifacts/openmrs/spa-custom/importmap.json

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${ROOT}/artifacts/openmrs/spa-custom"
TARGET_NAME="openmrs-esm-chartsearchai-app-multiturn"
OUT="${ARTIFACT_DIR}/importmap.json"
ENTRY_VALUE="./${TARGET_NAME}/openmrs-esm-chartsearchai-app.js"

mkdir -p "${ARTIFACT_DIR}"

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to rewrite the importmap entry" >&2
  exit 1
fi

if [ "${CLOUD:-0}" = "1" ]; then
  # shellcheck disable=SC1091
  . "${ROOT}/scripts/cloud-lib.sh"
  echo "==> fetching live importmap from cloud frontend container"
  BASE_JSON="$(gcp_ssh "docker exec harness-openmrs-frontend cat /usr/share/nginx/html/importmap.json")"
else
  echo "==> fetching live importmap from local frontend container"
  if ! docker inspect -f '{{.State.Status}}' harness-openmrs-frontend >/dev/null 2>&1; then
    echo "error: harness-openmrs-frontend container not running locally" >&2
    echo "  bring stack up first (make up) or pass CLOUD=1 to fetch from the VM" >&2
    exit 1
  fi
  BASE_JSON="$(docker exec harness-openmrs-frontend cat /usr/share/nginx/html/importmap.json)"
fi

echo "${BASE_JSON}" | jq --arg value "${ENTRY_VALUE}" '.imports."@openmrs/esm-chartsearchai-app" = $value' > "${OUT}"

echo "    wrote ${OUT}"
echo "    chartsearchai entry → $(jq -r '.imports."@openmrs/esm-chartsearchai-app"' "${OUT}")"
echo "    total entries: $(jq '.imports | length' "${OUT}")"
