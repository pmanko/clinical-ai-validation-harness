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
       Copy .env.chartsearch.cloud.example. The default
       CHARTSEARCH_REMOTE_ENDPOINT_URL points at the VM's local lms server
       (LM Link → your Mac); change it only to use a cloud LLM directly.
EOF
  exit 1
fi

echo "==> compose up on ${GCP_VM_NAME}"
# Pass remote-repo path through the env so the heredoc can stay quoted
# (literal $vars on the remote) while still parameterizing the dir.
gcp_ssh "REMOTE_REPO='${GCP_REMOTE_REPO}' HTTP_PORT='${GCP_HTTP_PORT}' bash -s" <<'REMOTE'
set -euo pipefail
cd "${HOME}/${REMOTE_REPO}"

# Drop the prebuilt .omod into place (rsync'd from local; module loads on
# backend start). If the local build didn't run, this directory may be empty.
mkdir -p artifacts/openmrs/modules artifacts/openmrs/backend-logs
ls -la artifacts/openmrs/modules/ || true

# chartsearch-configure.sh reads .env.chartsearch — symlink the cloud variant
# into place so the same script works against either env file.
ln -sf .env.chartsearch.cloud .env.chartsearch

# Source the cloud env file so docker compose interpolates the LM Link URL,
# DB schema name, and chartsearchai apikey.
set -a
. ./.env.chartsearch.cloud
set +a

docker compose -f compose/openmrs-2.8-refapp.yml up -d --force-recreate \
  proxy gateway frontend backend db

echo "==> waiting for backend healthy (Liquibase + module init; up to 10 min cold)"
observed_healthy=0
for i in $(seq 1 120); do
  s=$(docker inspect -f '{{.State.Health.Status}}' harness-openmrs-backend 2>/dev/null || echo starting)
  if [ "${s}" = "healthy" ]; then
    echo "    backend healthy after $((i*5))s"
    observed_healthy=1
    break
  fi
  if [ $((i % 6)) -eq 0 ]; then
    echo "    [$((i*5))s] still ${s}..."
  fi
  sleep 5
done
if [ "${observed_healthy}" != "1" ]; then
  echo "ERROR: backend did not reach healthy within 10 min." >&2
  docker logs --tail 50 harness-openmrs-backend >&2
  exit 1
fi

echo "==> chartsearch-configure (LLM globals via REST against localhost on VM)"
HARNESS_PROXY_HTTP_PORT="${HTTP_PORT}" ./scripts/chartsearch-configure.sh
REMOTE

IP="$(gcp_vm_ip)"
echo ""
echo "Stack up. Visit: http://${IP}:${GCP_HTTP_PORT}/openmrs/spa"
echo "Login:           admin / Admin123"
