#!/usr/bin/env bash
# Apply existing source/network configuration without rebuilding or touching data services.
set -euo pipefail
: "${CATALYST_DIR:?Use scripts/catalyst-mvp.sh source-update}"
: "${MVP_COMPOSE_OVERRIDE_FILE:?Use scripts/catalyst-mvp.sh source-update}"
if [[ ! -f "${CATALYST_DIR}/.env" ]]; then
  echo "ERROR: source-update requires the existing configured checkout." >&2
  exit 1
fi
exec docker compose --project-directory "${CATALYST_DIR}" \
  --env-file "${CATALYST_DIR}/.env" \
  -f "${CATALYST_DIR}/docker-compose.mvp.yml" \
  -f "${MVP_COMPOSE_OVERRIDE_FILE}" \
  up --detach --no-build --no-deps catalyst-gateway superset
