#!/usr/bin/env bash
# Shared REST helpers for focused OpenMRS configuration scripts.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "${ROOT}/.env.chartsearch" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${ROOT}/.env.chartsearch"
  set +a
fi

OPENMRS_SETTINGS_EXEC="${CHARTSEARCH_EXEC:-}"
if [ -n "${OPENMRS_SETTINGS_EXEC}" ]; then
  OPENMRS_SETTINGS_BASE_URL="${CHARTSEARCH_BASE_URL:-http://localhost:8080/openmrs}"
else
  OPENMRS_SETTINGS_BASE_URL="${CHARTSEARCH_BASE_URL:-http://localhost:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs}"
fi
OPENMRS_SETTINGS_USER="${CHARTSEARCH_ADMIN_USER:-admin}"
OPENMRS_SETTINGS_PASS="${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}"

openmrs_curl() {
  if [ -n "${OPENMRS_SETTINGS_EXEC}" ]; then
    docker exec "${OPENMRS_SETTINGS_EXEC}" curl "$@"
  else
    curl "$@"
  fi
}

set_openmrs_property() {
  local name="$1"
  local value="$2"
  local body body_create
  echo "  ${name} = ${value}"
  body=$(python3 -c "import json,sys; print(json.dumps({'value': sys.argv[1]}))" "${value}")
  body_create=$(python3 -c "import json,sys; print(json.dumps({'property': sys.argv[1], 'value': sys.argv[2]}))" "${name}" "${value}")
  if ! openmrs_curl -fsS -o /dev/null \
      -u "${OPENMRS_SETTINGS_USER}:${OPENMRS_SETTINGS_PASS}" \
      -H "Content-Type: application/json" \
      -X POST "${OPENMRS_SETTINGS_BASE_URL}/ws/rest/v1/systemsetting/${name}" \
      -d "${body}" 2>/dev/null; then
    openmrs_curl -fsS -o /dev/null \
      -u "${OPENMRS_SETTINGS_USER}:${OPENMRS_SETTINGS_PASS}" \
      -H "Content-Type: application/json" \
      -X POST "${OPENMRS_SETTINGS_BASE_URL}/ws/rest/v1/systemsetting" \
      -d "${body_create}"
  fi
}
