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

# Reconcile firewall source range first — operator IP may have shifted since
# last cloud-init (DHCP / coffee shop / home), which silently locks them out
# of the proxy without this. Cheap: one gcloud describe + (occasionally) one
# update. Safe: no-op when current source range matches desired.
gcp_reconcile_http_firewall

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

# Force OpenMRS to re-bootstrap openmrs-runtime.properties from the current
# OMRS_CONFIG_* env vars. Without this, a runtime.properties left over from
# an earlier start (e.g. before OMRS_DB_NAME was set) keeps pointing at the
# old DB, and subsequent env changes are silently ignored — the most
# painful instance of this was an entire afternoon of debugging Hibernate
# Search when the backend was connected to the wrong schema. Delete is
# safe — OpenMRS regenerates it from server.properties + env on next start.
docker compose -f compose/openmrs-2.8-refapp.yml run --rm --no-deps \
  --entrypoint sh backend -c 'rm -f /openmrs/data/openmrs-runtime.properties'

# chartsearch-configure.sh reads .env.chartsearch — symlink the cloud variant
# into place so the same script works against either env file.
ln -sf .env.chartsearch.cloud .env.chartsearch

# Source the cloud env file so docker compose interpolates the LM Link URL,
# DB schema name, and chartsearchai apikey.
set -a
. ./.env.chartsearch.cloud
set +a

# Querystore storage backend (mysql|lucene|elasticsearch). Default elasticsearch:
# the harness exists to validate the real CQRS read store — a separate service,
# off the clinical DB. querystore.backend is wired at module startup, so pre-set
# it here (works when the schema already exists, i.e. re-deploys → no extra
# boot); on a fresh DB the schema isn't created until the backend boots, so we
# set it post-boot + restart once (below).
QUERYSTORE_BACKEND="${CHARTSEARCH_QUERYSTORE_BACKEND:-elasticsearch}"

if [ "${QUERYSTORE_BACKEND}" = "elasticsearch" ]; then
  echo "==> starting elasticsearch (querystore read store) + waiting healthy"
  docker compose -f compose/openmrs-2.8-refapp.yml --profile elasticsearch up -d elasticsearch
  for i in $(seq 1 72); do
    es=$(docker inspect -f '{{.State.Health.Status}}' harness-querystore-es 2>/dev/null || echo none)
    [ "${es}" = healthy ] && { echo "    ES healthy after $((i*5))s"; break; }
    sleep 5
  done
fi

backend_preset=0
if docker exec harness-openmrs-db mariadb -u"${OMRS_DB_USER:-openmrs}" -p"${OMRS_DB_PASSWORD:-openmrs}" "${OMRS_DB_NAME:-openmrs}" \
     -e "INSERT INTO global_property (property,property_value,uuid) VALUES ('querystore.backend','${QUERYSTORE_BACKEND}',UUID()) ON DUPLICATE KEY UPDATE property_value='${QUERYSTORE_BACKEND}'" 2>/dev/null; then
  backend_preset=1
  echo "==> querystore.backend pre-set to ${QUERYSTORE_BACKEND}"
fi

# --build so Dockerfile / backend-init.sh changes are picked up on the VM.
docker compose -f compose/openmrs-2.8-refapp.yml up -d --build --force-recreate \
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

# The Docker healthcheck only probes Tomcat's root, which answers before the REST
# API (modules + webservices.rest) finishes initializing — so configure's POSTs
# would hit a connection reset (curl 56). Wait for the systemsetting endpoint to
# actually answer (from inside the backend container) before configuring.
echo "==> waiting for REST API to answer"
for i in $(seq 1 80); do
  if docker exec harness-openmrs-backend curl -fsS -o /dev/null -m 5 \
       -u admin:Admin123 "http://localhost:8080/openmrs/ws/rest/v1/systemsetting?limit=1" 2>/dev/null; then
    echo "    REST ready after $((i*3))s"; break
  fi
  sleep 3
done

echo "==> chartsearch-configure (LLM + querystore globals — REST via docker exec into the backend)"
CHARTSEARCH_EXEC=harness-openmrs-backend ./scripts/chartsearch-configure.sh

# Fresh-DB path: the schema didn't exist when we tried to pre-set querystore.backend,
# so the backend booted on the default store. Set it now and restart once to wire
# the selected backend. (Re-deploys hit the pre-set path above and skip this.)
if [ "${backend_preset}" != "1" ]; then
  echo "==> setting querystore.backend=${QUERYSTORE_BACKEND} + restarting backend to wire it"
  docker exec harness-openmrs-db mariadb -u"${OMRS_DB_USER:-openmrs}" -p"${OMRS_DB_PASSWORD:-openmrs}" "${OMRS_DB_NAME:-openmrs}" \
    -e "INSERT INTO global_property (property,property_value,uuid) VALUES ('querystore.backend','${QUERYSTORE_BACKEND}',UUID()) ON DUPLICATE KEY UPDATE property_value='${QUERYSTORE_BACKEND}'"
  docker compose -f compose/openmrs-2.8-refapp.yml restart backend
  for i in $(seq 1 120); do
    s=$(docker inspect -f '{{.State.Health.Status}}' harness-openmrs-backend 2>/dev/null || echo starting)
    [ "${s}" = "healthy" ] && { echo "    backend healthy on ${QUERYSTORE_BACKEND} after $((i*5))s"; break; }
    sleep 5
  done
fi
REMOTE

IP="$(gcp_vm_ip)"
echo ""
echo "Stack up. Visit: http://${IP}:${GCP_HTTP_PORT}/openmrs/spa"
echo "Login:           admin / Admin123"
