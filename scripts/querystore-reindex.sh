#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

set -a
[ -f ./.env.chartsearch ] && . ./.env.chartsearch
set +a

PORT="${HARNESS_PROXY_HTTP_PORT:-8088}"
BASE="http://localhost:${PORT}/openmrs"
USER="${CHARTSEARCH_ADMIN_USER:-admin}"
PASSWORD="${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}"

echo "==> force-resyncing every current Querystore resource type"
drift="$(curl -fsS --max-time 60 -u "${USER}:${PASSWORD}" \
  "${BASE}/ws/rest/v1/querystore/drift")"
resource_types=()
while IFS= read -r resource_type; do
  resource_types+=("${resource_type}")
done < <(DRIFT="${drift}" python3 - <<'PY'
import json, os
for row in json.loads(os.environ["DRIFT"]).get("types") or []:
    if int(row.get("coreCount") or 0) > 0:
        print(row["resourceType"])
PY
)
if (( ${#resource_types[@]} == 0 )); then
  echo "ERROR: Querystore drift endpoint returned no populated resource types" >&2
  exit 1
fi

status_row() {
  local resource_type="$1" payload
  payload="$(curl -fsS --max-time 30 -u "${USER}:${PASSWORD}" \
    "${BASE}/ws/rest/v1/querystore/indexingstatus")"
  STATUS="${payload}" RESOURCE_TYPE="${resource_type}" python3 - <<'PY'
import json, os
target = os.environ["RESOURCE_TYPE"]
row = next((item for item in json.loads(os.environ["STATUS"]).get("types") or []
            if item.get("resourceType") == target), {})
print("|".join(str(row.get(key) if row.get(key) is not None else "")
               for key in ("status", "startedAt", "completedAt", "documentsIndexed", "failureMessage")))
PY
}

response="$(mktemp)"
cleanup() {
  rm -f "${response}"
}
trap cleanup EXIT
for resource_type in "${resource_types[@]}"; do
  IFS='|' read -r baseline_state baseline_started _ _ _ <<< "$(status_row "${resource_type}")"
  if [[ "${baseline_state}" == "RUNNING" ]]; then
    echo "ERROR: ${resource_type} already has an active resync; wait for it to finish" >&2
    exit 1
  fi
  code="$(curl -sS --max-time 60 -o "${response}" -w '%{http_code}' \
    -u "${USER}:${PASSWORD}" \
    -H 'Content-Type: application/json' \
    -X POST "${BASE}/ws/rest/v1/querystore/reindex" \
    -d "{\"scope\":\"type\",\"resourceType\":\"${resource_type}\"}")"
  if [[ "${code}" != "202" ]]; then
    echo "ERROR: ${resource_type} resync was not accepted (HTTP ${code}): $(cat "${response}")" >&2
    exit 1
  fi

  echo "    ${resource_type}: accepted; waiting for a new completed generation"
  last_state=""
  stalled_polls=0
  attempt=0
  while true; do
    attempt=$((attempt + 1))
    IFS='|' read -r state started completed indexed failure <<< "$(status_row "${resource_type}")"
    signature="${state}|${started}|${completed}|${indexed}"
    if [[ "${state}" == "FAILED" ]]; then
      echo "ERROR: ${resource_type} resync failed: ${failure:-unknown error}" >&2
      exit 1
    fi
    if [[ "${state}" == "COMPLETED" && -n "${started}" && "${started}" != "${baseline_started}" ]]; then
      echo "    ${resource_type}: complete (${indexed} documents)"
      break
    fi
    if [[ "${signature}" == "${last_state}" ]]; then
      stalled_polls=$((stalled_polls + 1))
    else
      stalled_polls=0
      last_state="${signature}"
    fi
    if (( stalled_polls >= 120 )); then
      echo "ERROR: ${resource_type} resync made no observable progress for 10 minutes (${signature})" >&2
      exit 1
    fi
    if (( attempt % 6 == 0 )); then
      echo "    ${resource_type}: ${state:-queued}, ${indexed:-0} documents"
    fi
    sleep 5
  done
done

echo "==> checking post-resync drift"
post_drift="$(curl -fsS --max-time 60 -u "${USER}:${PASSWORD}" \
  "${BASE}/ws/rest/v1/querystore/drift")"
if ! printf '%s' "${post_drift}" | python3 scripts/check-querystore-drift.py
then
  echo "ERROR: the rebuilt index does not satisfy validation preflight." >&2
  echo "       Stale extras require recreating the Querystore index from the intended corpus." >&2
  exit 1
fi
echo "    all populated resource types rewalked; validation drift policy passes"
