#!/usr/bin/env bash
# Recreate the local Querystore Elasticsearch read model from authoritative OpenMRS data.
# This removes only querystore_* Elasticsearch indexes and Querystore bootstrap progress.
# It does not modify OpenMRS clinical tables.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ "${ALLOW_QUERYSTORE_INDEX_RESET:-}" != "1" ]]; then
  echo "ERROR: set ALLOW_QUERYSTORE_INDEX_RESET=1 to recreate the local Querystore read index" >&2
  exit 1
fi

set -a
[ -f ./.env.chartsearch ] && . ./.env.chartsearch
set +a

BACKEND="${OPENMRS_BACKEND:-harness-openmrs-backend}"
PROXY="${OPENMRS_PROXY:-harness-proxy}"
DB_CONTAINER="${DB_CONTAINER:-harness-openmrs-db}"
DB_USER="${OMRS_DB_USER:-openmrs}"
DB_PASSWORD="${OMRS_DB_PASSWORD:-openmrs}"
DB_NAME="${OMRS_DB_NAME:-openmrs}"
PORT="${HARNESS_PROXY_HTTP_PORT:-8088}"
BASE="http://localhost:${PORT}/openmrs"
AUTH="${CHARTSEARCH_ADMIN_USER:-admin}:${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}"
ES_URL="${QUERYSTORE_ES_URL:-http://localhost:${QUERYSTORE_ES_PORT:-9200}}"
QUERYSTORE_OMOD_PROVENANCE="${ROOT}/artifacts/chartsearchai-local/module-provenance/querystore-1.0.0-SNAPSHOT.omod.provenance.json"
DEPLOYED_QUERYSTORE_PROVENANCE="${ROOT}/artifacts/chartsearchai-local/deployed-querystore-omod.json"

echo "==> clearing cached Querystore module files before restart"
docker exec "${BACKEND}" sh -c \
  'rm -rf /openmrs/data/.openmrs-lib-cache/querystore'

echo "==> stopping OpenMRS so no writer can race the read-index reset"
docker stop "${BACKEND}" >/dev/null

echo "==> deleting only querystore_* Elasticsearch indexes"
indexes="$(
  curl -fsS "${ES_URL}/_cat/indices/querystore_*?h=index&format=json" \
    | python3 -c 'import json,sys; print("\n".join(row["index"] for row in json.load(sys.stdin)))'
)"
while IFS= read -r index; do
  [[ -z "${index}" ]] && continue
  curl -fsS -X DELETE "${ES_URL}/${index}" >/dev/null
  echo "    deleted ${index}"
done <<< "${indexes}"

echo "==> resetting only Querystore bootstrap progress and ensuring autostart"
docker exec "${DB_CONTAINER}" mariadb \
  --user="${DB_USER}" --password="${DB_PASSWORD}" "${DB_NAME}" -e "
    DELETE FROM querystore_bootstrap_progress;
    INSERT INTO global_property (property, property_value, uuid)
      VALUES ('querystore.bootstrap.autostart', 'true', UUID())
      ON DUPLICATE KEY UPDATE property_value='true';"

echo "==> restarting OpenMRS with the rebuilt Querystore module"
docker start "${BACKEND}" >/dev/null
healthy=0
for attempt in $(seq 1 120); do
  status="$(docker inspect -f '{{.State.Health.Status}}' "${BACKEND}" 2>/dev/null || echo starting)"
  if [[ "${status}" == "healthy" ]]; then
    healthy=1
    echo "    backend healthy"
    break
  fi
  sleep 5
done
if [[ "${healthy}" != "1" ]]; then
  echo "ERROR: OpenMRS did not become healthy after the Querystore restart" >&2
  exit 1
fi
if [[ ! -s "${QUERYSTORE_OMOD_PROVENANCE}" ]]; then
  echo "ERROR: missing built Querystore provenance: ${QUERYSTORE_OMOD_PROVENANCE}" >&2
  exit 1
fi
mkdir -p "$(dirname "${DEPLOYED_QUERYSTORE_PROVENANCE}")"
cp "${QUERYSTORE_OMOD_PROVENANCE}" "${DEPLOYED_QUERYSTORE_PROVENANCE}"
echo "    deployed Querystore provenance recorded"

echo "==> starting the local proxy used by Querystore verification"
if ! docker inspect "${PROXY}" >/dev/null 2>&1; then
  echo "ERROR: ${PROXY} does not exist; run 'make chartsearchai-local' once before recreating the index" >&2
  exit 1
fi
docker start "${PROXY}" >/dev/null
proxy_ready=0
for attempt in $(seq 1 60); do
  if curl -fsS --max-time 3 "http://localhost:${PORT}/__proxy_health" >/dev/null 2>&1; then
    proxy_ready=1
    echo "    proxy ready"
    break
  fi
  sleep 2
done
if [[ "${proxy_ready}" != "1" ]]; then
  echo "ERROR: local proxy did not become ready on port ${PORT}" >&2
  exit 1
fi

echo "==> waiting for the clean autostart generation to satisfy validation drift"
drift_report="$(mktemp)"
trap 'rm -f "${drift_report}"' EXIT
for attempt in $(seq 1 1440); do
  status_json="$(curl -fsS --max-time 30 -u "${AUTH}" \
    "${BASE}/ws/rest/v1/querystore/indexingstatus" 2>/dev/null || true)"
  if [[ -n "${status_json}" ]]; then
    if ! generation_state="$(STATUS_JSON="${status_json}" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["STATUS_JSON"])
rows = payload.get("types") or []
failed = [row for row in rows if row.get("status") == "FAILED"]
if failed:
    for row in failed:
        print(
            f"ERROR: {row.get('resourceType')} failed: "
            f"{row.get('failureMessage') or 'unknown error'}",
            file=sys.stderr,
        )
    raise SystemExit(1)
print("complete" if payload.get("complete") is True else "running")
PY
    )"; then
      exit 1
    fi
    if [[ "${generation_state}" == "complete" ]]; then
      drift_json="$(curl -fsS --max-time 60 -u "${AUTH}" \
        "${BASE}/ws/rest/v1/querystore/drift" 2>/dev/null || true)"
      if [[ -n "${drift_json}" ]] \
        && printf '%s' "${drift_json}" \
          | python3 scripts/check-querystore-drift.py >"${drift_report}" 2>&1
      then
        cat "${drift_report}"
        echo "    clean Querystore generation complete"
        exit 0
      fi
    fi
  fi
  if (( attempt % 6 == 0 )); then
    summary="$(STATUS_JSON="${status_json:-{}}" python3 - <<'PY'
import json
import os

try:
    rows = json.loads(os.environ["STATUS_JSON"]).get("types") or []
except Exception:
    rows = []
running = next((row for row in rows if row.get("status") == "RUNNING"), None)
if running:
    print(
        f"{running.get('resourceType')}: "
        f"{running.get('documentsIndexed') or 0} documents"
    )
elif not rows:
    print("status endpoint busy; indexing continues")
else:
    print("waiting for next resource type")
PY
)"
    echo "    ${summary}"
  fi
  sleep 10
done

echo "ERROR: clean Querystore generation did not finish within four hours" >&2
exit 1
