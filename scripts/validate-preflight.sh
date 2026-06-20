#!/usr/bin/env bash
# scripts/validate-preflight.sh
# Make the stack RUN-READY for `make validate-run SET=<set>`, in one command.
#
# A validate run silently produces garbage (empty charts → wrong answers) if any
# piece is down or un-indexed, and the bring-up is fiddly: Elasticsearch is
# profile-gated (off by default), querystore.bootstrap.autostart=false means
# NOTHING indexes on boot (every patient must be reindexed by hand), the proxy
# serves :8088, and the hub + llama-router are separate processes. This script
# brings up every component a run needs, reindexes exactly the SET's patients
# into the querystore, and verifies each piece answers — surfacing a down /
# mis-indexed component as a clear failure up front, not as bad data mid-run.
#
# Usage:
#   scripts/validate-preflight.sh <comparison-set-id> [low|med|high]
# (tier picks the llama-router co-residency cap; default med.)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
# shellcheck disable=SC1091
. "${ROOT}/scripts/_preflight.sh"; harness_preflight || exit 1

SET="${1:?usage: validate-preflight.sh <comparison-set-id> [low|med|high]}"
TIER="${2:-${LLAMA_ROUTER_TIER:-med}}"
COMPOSE="compose/openmrs-2.8-refapp.yml"
SET_FILE="datasets/validation/comparison_sets/${SET}.json"
[ -f "${SET_FILE}" ] || { echo "ERROR: no comparison set ${SET_FILE}" >&2; exit 1; }

# .env.chartsearch carries OPENMRS_REFAPP_TAG (nightly-chartsearch) + the proxy ports;
# without it the frontend/gateway downgrade to stock and the SPA 404s.
set -a; . ./.env.chartsearch; set +a
PORT="${HARNESS_PROXY_HTTP_PORT:-8088}"
AUTH="${CHARTSEARCH_ADMIN_USER:-admin}:${CHARTSEARCH_ADMIN_PASSWORD:-Admin123}"
BASE="http://localhost:${PORT}/openmrs"

echo "==> [1/5] core stack (proxy/db/frontend/gateway/backend)"
./scripts/stack-up.sh --wait

echo "==> [2/5] elasticsearch (querystore backend — profile-gated)"
docker compose -f "${COMPOSE}" --profile elasticsearch up -d elasticsearch
for i in $(seq 1 24); do
  curl -fsS --max-time 4 "http://localhost:${QUERYSTORE_ES_PORT:-9200}/_cluster/health" 2>/dev/null \
    | grep -qE '"status":"(green|yellow)"' && { echo "    ES ready"; break; }
  sleep 5
done

echo "==> [3/5] med-agent-hub + llama-router (tier ${TIER})"
make med-agent-hub-up
if ! curl -fsS --max-time 4 http://localhost:8077/v1/models >/dev/null 2>&1; then
  echo "    starting llama-router (background)"
  LLAMA_ROUTER_TIER="${TIER}" nohup ./scripts/llama-router-up.sh > /tmp/llama-router.log 2>&1 &
  for i in $(seq 1 30); do
    curl -fsS --max-time 4 http://localhost:8077/v1/models >/dev/null 2>&1 && break; sleep 2
  done
fi

echo "==> [4/5] verify the set's patients are indexed in the querystore (back-fill only if missing)"
PATIENTS="$(python3 - "${SET_FILE}" <<'PY'
import json, sys, pathlib
s = json.load(open(sys.argv[1]))
refs = []
for sid in s.get("scenario_ids", []):
    p = pathlib.Path("datasets/validation/scenarios") / f"{sid}.json"
    try:
        pr = json.load(open(p)).get("patient_ref")
        if pr and pr not in refs:
            refs.append(pr)
    except Exception:
        pass
print(" ".join(refs))
PY
)"
[ -n "${PATIENTS}" ] || { echo "ERROR: no patient_refs resolved from ${SET}" >&2; exit 1; }
# The querystore ES index persists on the es-data volume and is back-filled once at SEED time
# (seed-local.sh / cloud-seed.sh project the whole store), so the normal case here is a fast,
# NON-DESTRUCTIVE verify: count each run-patient's docs straight from Elasticsearch (patient_uuid
# is a keyword field → exact term match).
#   - count > 0  : already indexed (the persisted baseline) — nothing to do.
#   - count == 0 : genuinely missing (a fresh seed not yet back-filled, or a wiped ES). Back-fill
#                  just that one patient with POST /reindex {patient} (reindexPatient's delete-first
#                  is a no-op on an empty patient), then re-count. We never re-fire reindex on an
#                  already-indexed patient: it is delete-first, so that would wipe-then-rebuild a
#                  good chart for nothing. The ES backend writes with refresh=wait_for, so the
#                  re-count needs no settle.
# A patient still at 0 after a targeted back-fill is a real querystore indexing failure → surface it
# (a run would get empty charts), never mask it.
ES="http://localhost:${QUERYSTORE_ES_PORT:-9200}"
es_count() {  # doc count across all querystore_* indices for patient $1 (0 on any error)
  curl -fsS --max-time 10 "${ES}/querystore_*/_count" -H 'Content-Type: application/json' \
    -d "{\"query\":{\"term\":{\"patient_uuid\":\"$1\"}}}" 2>/dev/null \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count",0))' 2>/dev/null || echo 0
}
missing=""
for u in ${PATIENTS}; do
  c=$(es_count "${u}")
  if [ "${c:-0}" -gt 0 ]; then
    echo "    ${u}: indexed (${c} docs)"
    continue
  fi
  echo "    ${u}: not indexed — back-filling this patient (POST /reindex)"
  curl -fsS --max-time 180 -u "${AUTH}" -H 'Content-Type: application/json' \
    -X POST "${BASE}/ws/rest/v1/querystore/reindex" -d "{\"patient\":\"${u}\"}" >/dev/null 2>&1 || true
  c=$(es_count "${u}")
  if [ "${c:-0}" -gt 0 ]; then
    echo "    ${u}: back-filled (${c} docs)"
  else
    echo "    ${u}: STILL 0 docs after back-fill" >&2
    missing="${missing} ${u}"
  fi
done
if [ -n "${missing}" ]; then
  echo "ERROR: querystore has 0 documents for:${missing}" >&2
  echo "       A run on '${SET}' would get EMPTY charts — a real querystore indexing failure," >&2
  echo "       surfaced rather than masked. The baseline should be indexed at seed time:" >&2
  echo "       re-run 'make seed' (with ES up), or inspect the module log + GET /querystore/drift." >&2
  exit 1
fi

echo "==> [5/5] verify everything answers"
fail=0
chk() { printf '    %-26s %s\n' "$1" "$2"; [ "$3" = ok ] || fail=1; }
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "${BASE}/" || true)
chk "proxy :${PORT}" "HTTP ${code}" "$([ "$code" = 200 ] && echo ok)"
rcount=$(curl -s --max-time 6 http://localhost:8077/v1/models | python3 -c 'import sys,json;print(len(json.load(sys.stdin).get("data",[])))' 2>/dev/null || echo 0)
chk "llama-router :8077" "${rcount} models" "$([ "${rcount:-0}" -gt 0 ] && echo ok)"
hub=$(docker inspect -f '{{.State.Health.Status}}' harness-med-agent-hub 2>/dev/null || echo missing)
chk "med-agent-hub" "${hub}" "$([ "$hub" = healthy ] && echo ok)"
qs=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -u "${AUTH}" "${BASE}/ws/rest/v1/querystore/indexingstatus" || true)
chk "querystore endpoint" "HTTP ${qs}" "$([ "$qs" = 200 ] && echo ok)"
pdocs=$(curl -s --max-time 6 "http://localhost:${QUERYSTORE_ES_PORT:-9200}/querystore_patient/_count" \
        | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count",0))' 2>/dev/null || echo 0)
chk "querystore indexed" "${pdocs} patient docs" "$([ "${pdocs:-0}" -gt 0 ] && echo ok)"

[ "$fail" = 0 ] && echo "✅ preflight OK — stack run-ready for: make validate-run SET=${SET}" \
  || { echo "❌ preflight: one or more components not ready (see above)" >&2; exit 1; }
