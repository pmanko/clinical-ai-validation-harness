#!/usr/bin/env bash
# One command: from a clean slate to a working dual-provider ChartSearchAI stack, restoring the
# cached Elasticsearch querystore index (the demo dataset is static) instead of re-embedding it.
#
# Every step goes through an existing script/target — this orchestrator only sequences them and
# codifies the two things that used to be tribal knowledge / hand-set: the querystore ES backend
# and the dual-provider registry (providers.enabled=bundled,hub).
#
# Fast path (snapshot present):  reset -> seed -> configure(ES) -> RESTORE snapshot -> hub -> smoke
#   ~minutes; no embedding. Build the snapshot once with:  scripts/querystore-snapshot.sh snapshot <ver>
# Cold path (no snapshot):       ... -> full bootstrap (hours, obs=428k) -> (snapshot it yourself)
#
# Env (all have sane defaults; override via .env.chartsearch):
#   QS_SNAPSHOT_VERSION (default demo-2.8), CHARTSEARCH_HUB_ENDPOINT_URL,
#   CHARTSEARCH_PROVIDERS_ENABLED (default bundled,hub), CHARTSEARCH_PROVIDERS_DEFAULT (default bundled)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "${ROOT}"
COMPOSE="compose/openmrs-2.8-refapp.yml"
BACKEND="${OPENMRS_BACKEND:-harness-openmrs-backend}"

# Config defaults first, then the operator's overrides win.
set -a; . ./.env.chartsearch.example; [ -f ./.env.chartsearch ] && . ./.env.chartsearch; set +a
export HUB_BUILD_REVISION="$(git -C targets/med-agent-hub rev-parse HEAD)"
export MED_AGENT_HUB_UID="$(id -u)" MED_AGENT_HUB_GID="$(id -g)"
QS_SNAPSHOT_VERSION="${QS_SNAPSHOT_VERSION:-demo-2.8}"
DB_CONTAINER="${OPENMRS_DB_CONTAINER:-harness-openmrs-db}"
DB="${OMRS_DB_NAME:-openmrs}"; DBU="${OMRS_DB_USER:-openmrs}"; DBP="${OMRS_DB_PASSWORD:-openmrs}"
OPENMRS_URL="http://127.0.0.1:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs"
SOURCE_ENV="artifacts/chartsearchai-local/querystore-service.env"
SMOKE_PATIENT="${CHARTSEARCH_LOCAL_PATIENT_UUID:-dd553355-1691-11df-97a5-7038c432aabf}"

say() { printf '\n== %s ==\n' "$*"; }
gp() { docker exec "${DB_CONTAINER}" mariadb -u"${DBU}" -p"${DBP}" "${DB}" \
  -e "INSERT INTO global_property (property,property_value,uuid) VALUES ('$1','$2',UUID()) ON DUPLICATE KEY UPDATE property_value='$2'"; }
wait_backend() { for _ in $(seq 1 90); do [ "$(docker inspect -f '{{.State.Health.Status}}' "${BACKEND}" 2>/dev/null)" = healthy ] && return 0; sleep 5; done; echo "backend not healthy" >&2; return 1; }

# Preflight: the hub provider needs llama-router (:8077) and bundled needs its LLM (LM Studio :1234);
# both are host processes. Provisioning still succeeds if they're down, but chat will fail until
# they're up (`make llama-router-up` in a terminal).
curl -fsS -m3 http://localhost:8077/v1/models >/dev/null 2>&1 || \
  echo "WARN: llama-router (:8077) not reachable — hub chat will fail until 'make llama-router-up'."

say "1/6 fresh reset -> up (empty DB, modules install via Liquibase) -> seed (load demo corpus)"
# Canonical provision order is reset && up && seed: seed-local.sh requires a running DB container
# and swaps the schema under a quiescent backend. querystore.bootstrap.autostart defaults to false
# (config.xml), so the post-seed backend boots idle — we restore the index below, never re-embed.
make reset
make up
make seed

say "2/6 pin querystore to Elasticsearch, autostart OFF (we restore the index, never rebuild here)"
gp querystore.backend elasticsearch
gp querystore.bootstrap.autostart false
docker compose -f "${COMPOSE}" up -d elasticsearch
docker compose -f "${COMPOSE}" up -d --force-recreate backend
wait_backend

say "3/6 configure querystore embedding + dual-provider registry (via scripts, REST cache-safe)"
./scripts/querystore-configure.sh
./scripts/chartsearch-configure.sh   # sets hub.endpointUrl + providers.enabled=bundled,hub + default

say "4/6 querystore index: restore cached snapshot if present, else full bootstrap (slow)"
# Deterministic file test — do NOT depend on `snapshot.sh list` exit status (its es_volume pipe can
# report non-zero under pipefail and silently drop us into the multi-hour cold path).
SNAP_DIR="${QUERYSTORE_SNAPSHOT_DIR:-${HOME}/.cache/querystore-snapshots}"
if [ -f "${SNAP_DIR}/${QS_SNAPSHOT_VERSION}/es-data.tar.gz" ]; then
  echo "  snapshot found: ${SNAP_DIR}/${QS_SNAPSHOT_VERSION}/es-data.tar.gz"
  scripts/querystore-snapshot.sh restore "${QS_SNAPSHOT_VERSION}"
  docker restart "${BACKEND}" >/dev/null   # re-read restored bootstrap_progress (COMPLETED) + ES index
  wait_backend
else
  echo "no snapshot '${QS_SNAPSHOT_VERSION}' — running a full bootstrap (hours; obs is ~428k)."
  echo "  after it completes, cache it:  scripts/querystore-snapshot.sh snapshot ${QS_SNAPSHOT_VERSION}"
  gp querystore.bootstrap.autostart true
  docker restart "${BACKEND}" >/dev/null; wait_backend
  make querystore-reindex
fi

say "5/6 provision hub<->querystore reader, then start med-agent-hub"
# The reset wiped the DB, so any previous service account is gone. Provision a fresh least-privileged
# patient reader; med-agent-hub-up sources ${SOURCE_ENV} for these creds and wires the hub to querystore.
mkdir -p "$(dirname "${SOURCE_ENV}")"
python3 scripts/provision-querystore-service-account.py \
  --base-url "${OPENMRS_URL}" \
  --internal-base-url "http://backend:8080/openmrs" \
  --admin-user "${CHARTSEARCH_ADMIN_USER:-admin}" \
  --admin-password "${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}" \
  --output "${SOURCE_ENV}"
# Export the freshly-provisioned reader creds so med-agent-hub-up wires them into the hub. This is
# REQUIRED: the top-of-file `. .env.chartsearch.example` sets QUERYSTORE_* to EMPTY, and
# med-agent-hub-up treats any *set* value (even empty) as an override that would blank the real creds.
set -a; . "${SOURCE_ENV}"; set +a
export QUERYSTORE_BASE_URL QUERYSTORE_USERNAME QUERYSTORE_PASSWORD
make med-agent-hub-up

say "6/6 smoke test — retrieval against the restored index (the ES-reset goal)"
# Core check: querystore serves a patient chart from the restored ES index without re-embedding.
qs_code=$(curl -s -o /dev/null -w '%{http_code}' -u admin:Admin123 \
  "${OPENMRS_URL}/ws/rest/v1/querystore/patientrecord?patient=${SMOKE_PATIENT}&q=recent%20visit&limit=5" 2>/dev/null || echo 000)
echo "  querystore patientrecord -> HTTP ${qs_code} (200 = index query-ready, no re-embed)"
echo ""
echo "dual-provider stack up. Providers:"
curl -fsS -u admin:Admin123 "${OPENMRS_URL}/ws/rest/v1/chartsearchai/providers" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('  pickerVisible',d['pickerVisible'],'providers',[(p['id'],p['ready']) for p in d['providers']])" 2>/dev/null || true
