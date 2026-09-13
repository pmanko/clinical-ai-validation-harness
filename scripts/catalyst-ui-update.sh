#!/usr/bin/env bash
# Called by the lifecycle wrapper after its location, pin and cleanliness checks.
set -euo pipefail

: "${CATALYST_DIR:?Use scripts/catalyst-mvp.sh ui-update}"
: "${MVP_COMPOSE_OVERRIDE_FILE:?Use scripts/catalyst-mvp.sh ui-update}"

if [[ ! -f "${CATALYST_DIR}/.env" ]]; then
  echo "ERROR: UI update requires an already configured Catalyst checkout (.env missing)." >&2
  exit 1
fi

exec docker compose --project-directory "${CATALYST_DIR}" \
  --env-file "${CATALYST_DIR}/.env" \
  -f "${CATALYST_DIR}/docker-compose.mvp.yml" \
  -f "${MVP_COMPOSE_OVERRIDE_FILE}" \
  up --detach --build --no-deps catalyst-ui
