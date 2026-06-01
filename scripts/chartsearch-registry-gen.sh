#!/usr/bin/env bash
# Generate the custom routes.registry.json that Caddy serves at
# /openmrs/spa/routes.registry.json. The OpenMRS app-shell reads this on boot
# to discover which frontend modules and their extensions/workspaces exist.
# If chartsearchai isn't here, the importmap alias is unused — the app-shell
# never imports the bundle, so the patient-banner extension never mounts.
#
# We fetch the baked registry from the running frontend container, then merge
# in the chartsearchai routes.json under the @openmrs/esm-chartsearchai-app
# key. The bundled routes.json (under dist/) is the source of truth for that
# entry — keeping merge logic out of this script means routes-change-only
# updates don't need a script edit.
#
# Where the base is fetched from:
#   - default: the local docker container `harness-openmrs-frontend`
#   - cloud:   pass CLOUD=1 to fetch via gcp_ssh + the VM's container
#
# Output: artifacts/openmrs/spa-custom/routes.registry.json

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${ROOT}/artifacts/openmrs/spa-custom"
TARGET_NAME="openmrs-esm-chartsearchai-app-multiturn"
OUT="${ARTIFACT_DIR}/routes.registry.json"
ENTRY_NAME="@openmrs/esm-chartsearchai-app"
ROUTES_JSON="${ARTIFACT_DIR}/${TARGET_NAME}/routes.json"

mkdir -p "${ARTIFACT_DIR}"

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to merge the routes registry" >&2
  exit 1
fi

if [ ! -f "${ROUTES_JSON}" ]; then
  echo "error: ${ROUTES_JSON} not found — run chartsearch-esm-build first" >&2
  exit 1
fi

if [ "${CLOUD:-0}" = "1" ]; then
  # shellcheck disable=SC1091
  . "${ROOT}/scripts/cloud-lib.sh"
  echo "==> fetching live routes.registry.json from cloud frontend container"
  BASE_JSON="$(gcp_ssh "docker exec harness-openmrs-frontend cat /usr/share/nginx/html/routes.registry.json")"
else
  echo "==> fetching live routes.registry.json from local frontend container"
  if ! docker inspect -f '{{.State.Status}}' harness-openmrs-frontend >/dev/null 2>&1; then
    echo "error: harness-openmrs-frontend container not running locally" >&2
    exit 1
  fi
  BASE_JSON="$(docker exec harness-openmrs-frontend cat /usr/share/nginx/html/routes.registry.json)"
fi

# Merge in the chartsearchai entry — overwrite if already present (idempotent).
echo "${BASE_JSON}" \
  | jq --arg name "${ENTRY_NAME}" --slurpfile routes "${ROUTES_JSON}" \
      '.[$name] = $routes[0]' \
  > "${OUT}"

echo "    wrote ${OUT}"
echo "    chartsearchai entry present: $(jq -r "has(\"${ENTRY_NAME}\")" "${OUT}")"
echo "    total module entries: $(jq 'length' "${OUT}")"
