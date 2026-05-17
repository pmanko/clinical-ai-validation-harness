#!/usr/bin/env bash
# Bring up the chartsearch compose stack on the VM. Mirrors `make chartsearch-up`
# from the local Makefile but runs over SSH against the rsync'd copy. Loads
# .env.chartsearch.cloud (operator's cloud-specific env) before compose up.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

if [ ! -f "${ROOT}/.env.chartsearch.cloud" ]; then
  cat >&2 <<EOF
error: .env.chartsearch.cloud not found.
       Copy .env.chartsearch.cloud.example and fill in CHARTSEARCH_REMOTE_ENDPOINT_URL
       (the cloudflared / tunnel URL). Then re-run.
EOF
  exit 1
fi

echo "==> compose up on ${GCP_VM_NAME}"
gcp_ssh bash <<'REMOTE'
set -euo pipefail
cd "${HOME}/clinical-ai-validation-harness"

# Drop the prebuilt .omod into place (rsync'd from local; module loads on
# backend start). If the local build didn't run, this directory may be empty.
mkdir -p artifacts/openmrs/modules artifacts/openmrs/backend-logs
ls -la artifacts/openmrs/modules/ || true

# chartsearch-configure.sh reads .env.chartsearch — symlink the cloud variant
# into place so the same script works against either env file.
ln -sf .env.chartsearch.cloud .env.chartsearch

# Source the cloud env file so docker compose interpolates the cloudflared
# URL, DB schema name, and chartsearchai apikey.
set -a
. ./.env.chartsearch.cloud
set +a

docker compose -f compose/openmrs-2.8-refapp.yml up -d --force-recreate \
  proxy gateway frontend backend db

echo "==> waiting for backend healthy (Liquibase + module init; up to 10 min cold)"
for i in $(seq 1 120); do
  s=$(docker inspect -f '{{.State.Health.Status}}' harness-openmrs-backend 2>/dev/null || echo starting)
  if [ "${s}" = "healthy" ]; then
    echo "    backend healthy after $((i*5))s"
    break
  fi
  if [ $((i % 6)) -eq 0 ]; then
    echo "    [$((i*5))s] still ${s}..."
  fi
  sleep 5
done

echo "==> chartsearch-configure (LLM globals via REST against localhost on VM)"
HARNESS_PROXY_HTTP_PORT=8088 ./scripts/chartsearch-configure.sh || true
REMOTE

IP="$(gcp_vm_ip)"
echo ""
echo "Stack up. Visit: http://${IP}:${GCP_HTTP_PORT}/openmrs/spa"
echo "Login:           admin / Admin123"
