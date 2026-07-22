#!/usr/bin/env bash
# scripts/querystore-snapshot.sh
# Cache the BUILT querystore Elasticsearch index (the whole-corpus projection + embeddings) as a
# versioned tarball, so `make reset` (which does `down --volumes` and nukes es-data), a DB reseed,
# or a fresh clone can restore a query-ready index in SECONDS instead of re-running the multi-hour
# corpus bootstrap. Same pattern as snapshot-baseline.sh (which caches the slow CIEL concept import).
#
# The index lives on the `es-data` Docker volume; we copy it via a throwaway alpine container so we
# never depend on a host path inside the ES image. ES is briefly STOPPED for a consistent copy —
# never run this during a live validation run (chartsearchai reads the index through querystore).
#
# Usage:
#   scripts/querystore-snapshot.sh snapshot <version>      # e.g. snapshot v2026-06-20  -> <dir>/<version>/es-data.tar.gz
#   scripts/querystore-snapshot.sh restore  <version>      # restore that snapshot into a fresh es-data volume
#   scripts/querystore-snapshot.sh list                    # list available snapshots
# Snapshot dir defaults to ~/.cache/querystore-snapshots (large, GB-scale — cached like the GGUFs, not git).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
COMPOSE="compose/openmrs-2.8-refapp.yml"
SNAP_DIR="${QUERYSTORE_SNAPSHOT_DIR:-${HOME}/.cache/querystore-snapshots}"
ES_SERVICE="elasticsearch"
# The ES index alone is NOT "query-ready": querystore gauges completion from the
# querystore_bootstrap_progress table (in MySQL), which a DB reseed wipes. If that table is
# empty, querystore treats the deployment as un-indexed (reads unavailable / lazy per-patient
# re-embed) even when the ES index is fully restored. So the snapshot captures + restores that
# readiness state alongside the ES volume — a restore is then complete and never re-embeds.
DB_CONTAINER="${OPENMRS_DB_CONTAINER:-harness-openmrs-db}"
DB_USER="${OMRS_DB_USER:-openmrs}"
DB_PASS="${OMRS_DB_PASSWORD:-openmrs}"
DB_NAME="${OMRS_DB_NAME:-openmrs}"
PROGRESS_TABLE="querystore_bootstrap_progress"

# Resolve the es-data volume name (compose prefixes it with the project dir name, e.g. compose_es-data).
# The `grep | head -1` closes the pipe early, so under `set -euo pipefail` the pipeline can report a
# non-zero status (head done → grep SIGPIPE); `|| true` keeps `VOL="$(es_volume)"` from aborting the
# whole script under set -e when the volume actually resolved fine.
es_volume() {
  docker volume ls --format '{{.Name}}' | grep -E '(^|_)es-data$' | head -1 || true
}

wait_es_healthy() {
  for i in $(seq 1 36); do
    s=$(docker inspect -f '{{.State.Health.Status}}' harness-querystore-es 2>/dev/null || echo none)
    [ "$s" = healthy ] && { echo "    ES healthy"; return 0; }
    sleep 5
  done
  echo "    WARNING: ES not healthy after 180s" >&2; return 1
}

cmd="${1:?usage: querystore-snapshot.sh snapshot|restore|list <version>}"
VOL="$(es_volume)"

case "${cmd}" in
  snapshot)
    VERSION="${2:?usage: querystore-snapshot.sh snapshot <version>}"
    [ -n "${VOL}" ] || { echo "ERROR: no es-data volume found" >&2; exit 1; }
    DEST="${SNAP_DIR}/${VERSION}"; mkdir -p "${DEST}"
    echo "==> snapshotting querystore index (volume ${VOL}) -> ${DEST}/es-data.tar.gz"
    echo "    stopping ES for a consistent copy"
    docker compose -f "${COMPOSE}" stop "${ES_SERVICE}"
    docker run --rm -v "${VOL}":/data:ro -v "${DEST}":/out alpine \
      tar czf /out/es-data.tar.gz -C /data .
    docker compose -f "${COMPOSE}" start "${ES_SERVICE}"
    wait_es_healthy || true
    echo "    dumping ${PROGRESS_TABLE} (bootstrap readiness) -> ${DEST}/bootstrap_progress.sql"
    docker exec "${DB_CONTAINER}" mariadb-dump -u"${DB_USER}" -p"${DB_PASS}" \
      --no-create-info --skip-comments --skip-dump-date "${DB_NAME}" "${PROGRESS_TABLE}" \
      > "${DEST}/bootstrap_progress.sql"
    sz=$(du -h "${DEST}/es-data.tar.gz" | cut -f1)
    echo "✅ snapshot ${VERSION} (${sz} ES + readiness) -> ${DEST}/"
    ;;
  restore)
    VERSION="${2:?usage: querystore-snapshot.sh restore <version>}"
    SRC="${SNAP_DIR}/${VERSION}/es-data.tar.gz"
    [ -f "${SRC}" ] || { echo "ERROR: no snapshot at ${SRC}" >&2; exit 1; }
    [ -n "${VOL}" ] || { echo "ERROR: no es-data volume found (bring the stack up once first)" >&2; exit 1; }
    echo "==> restoring querystore index ${VERSION} into ${VOL}"
    docker compose -f "${COMPOSE}" stop "${ES_SERVICE}"
    docker run --rm -v "${VOL}":/data -v "${SNAP_DIR}/${VERSION}":/in alpine \
      sh -c 'rm -rf /data/* /data/..?* 2>/dev/null; tar xzf /in/es-data.tar.gz -C /data'
    docker compose -f "${COMPOSE}" start "${ES_SERVICE}"
    wait_es_healthy || true
    if [ -f "${SNAP_DIR}/${VERSION}/bootstrap_progress.sql" ]; then
      echo "    restoring ${PROGRESS_TABLE} readiness (so querystore reports COMPLETED, no re-embed)"
      docker exec "${DB_CONTAINER}" mariadb -u"${DB_USER}" -p"${DB_PASS}" "${DB_NAME}" \
        -e "TRUNCATE TABLE ${PROGRESS_TABLE}" 2>/dev/null || true
      docker exec -i "${DB_CONTAINER}" mariadb -u"${DB_USER}" -p"${DB_PASS}" "${DB_NAME}" \
        < "${SNAP_DIR}/${VERSION}/bootstrap_progress.sql"
    else
      echo "    WARNING: snapshot has no bootstrap_progress.sql — querystore may lazy re-index on read"
    fi
    n=$(curl -fsS --max-time 8 "http://localhost:${QUERYSTORE_ES_PORT:-9200}/querystore_*/_count" 2>/dev/null \
        | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count",0))' 2>/dev/null || echo 0)
    echo "✅ restored ${VERSION}: ${n} querystore docs + bootstrap readiness"
    ;;
  list)
    echo "snapshots in ${SNAP_DIR}:"
    ls -1 "${SNAP_DIR}" 2>/dev/null | while read -r v; do
      printf '  %-16s %s\n' "${v}" "$(du -h "${SNAP_DIR}/${v}/es-data.tar.gz" 2>/dev/null | cut -f1)"
    done || echo "  (none)"
    ;;
  *) echo "unknown command: ${cmd} (snapshot|restore|list)" >&2; exit 1 ;;
esac
