#!/usr/bin/env bash
# Stop the local dev stack started by scripts/local-stack-up.sh.
#
# Leaves Docker volumes intact (patient data, ES index, module state) so the
# next local-stack-up.sh brings everything back exactly as it was. Does not
# stop Docker Desktop itself or uninstall anything.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "==> Stopping the Docker Compose stack (volumes preserved)"
docker compose -f compose/openmrs-2.8-refapp.yml down

echo "==> Stopping llama-router"
if pkill -f "llama-server .*models-preset .*llama-router.ini" 2>/dev/null; then
  echo "    stopped"
else
  echo "    was not running"
fi

echo "Done."
