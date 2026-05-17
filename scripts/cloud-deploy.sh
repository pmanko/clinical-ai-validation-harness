#!/usr/bin/env bash
# Fast iteration loop: rebuild .omod locally, rsync the diff to the VM,
# restart only the backend container so the new module is picked up. The
# rest of the compose stack (db, frontend, gateway, proxy) keeps running.
#
# Use this when iterating on chartsearchai Java code. For host-side compose
# changes (compose/, Caddyfile, etc.), the rsync still picks them up but
# you may want `cloud-up` (full recreate) instead.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

SKIP_BUILD="${SKIP_BUILD:-0}"

if [ "${SKIP_BUILD}" != "1" ]; then
  echo "==> rebuilding chartsearchai .omod locally"
  ( cd "${ROOT}" && make chartsearch-build )
fi

echo "==> syncing repo → VM"
"${ROOT}/scripts/cloud-sync.sh"

echo "==> restarting backend on VM (module reload)"
gcp_ssh "cd ${GCP_REMOTE_REPO} && docker compose -f compose/openmrs-2.8-refapp.yml restart backend"

echo "==> waiting for backend healthy (up to 5 min)"
# Fail the deploy if the loop times out without observing 'healthy' — silent
# success on a stuck backend is the worst-case for an iteration tool.
if ! gcp_ssh 'observed=0; for i in $(seq 1 60); do s=$(docker inspect -f "{{.State.Health.Status}}" harness-openmrs-backend 2>/dev/null || echo starting); if [ "$s" = healthy ]; then echo "    healthy after $((i*5))s"; observed=1; break; fi; sleep 5; done; [ "$observed" = 1 ]'; then
  echo "ERROR: backend did not reach healthy within 5 min." >&2
  gcp_ssh 'docker logs --tail 30 harness-openmrs-backend' >&2 || true
  exit 1
fi

IP="$(gcp_vm_ip)"
echo ""
echo "Deploy complete. Test at: http://${IP}:${GCP_HTTP_PORT}/openmrs/spa"
