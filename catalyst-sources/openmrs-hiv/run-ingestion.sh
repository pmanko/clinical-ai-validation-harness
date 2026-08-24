#!/usr/bin/env bash
# Run (or refresh) the OpenMRS HIV data source end to end:
#   1. one-shot fhir-data-pipes ingestion from the OpenMRS FHIR2 R4 endpoint
#      into the catalyst_analytics_hiv database (default lossless views),
#   2. apply the curated analytics SQL (fact views + comments),
#   3. register the pipeline run in analytics.pipeline_run_v1 (the freshness
#      contract the gateway requires before serving dataset overview/rows),
#   4. regenerate the catalog from the database + catalog-overlay.json.
#
# Prereqs: the catalyst-mvp-isolated stack is up (analytics-db healthy) and
# the OpenMRS instance answers on :8088. Keep the machine awake for the run
# (caffeinate -i) — a host sleep expires OpenMRS's paging cursors (HTTP 410)
# and silently truncates the fetch; this script verifies counts to catch that.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SRC_DIR}/../.." && pwd)"
NETWORK="${NETWORK:-catalyst-mvp-isolated-network}"
IMAGE="${IMAGE:-catalyst/fhir-data-pipes:3ea890884d674e2f31257a2da421601f2d75b5e9}"
CONTROLLER_PORT="${CONTROLLER_PORT:-18091}"
ANALYTICS_CONTAINER="${ANALYTICS_CONTAINER:-catalyst-mvp-isolated-analytics-db-1}"
HOST_DSN="${HOST_DSN:-postgresql://catalyst_analytics_writer:demo-only-change-me@localhost:15443/catalyst_analytics_hiv}"
OPENMRS_FHIR="${OPENMRS_FHIR:-http://localhost:8088/openmrs/ws/fhir2/R4}"
OPENMRS_AUTH="${OPENMRS_AUTH:-admin:Admin123}"

psql_hiv() {
  docker exec -i "${ANALYTICS_CONTAINER}" psql -v ON_ERROR_STOP=1 \
    -U catalyst_analytics_writer -d catalyst_analytics_hiv "$@"
}

echo "==> ensure catalyst_analytics_hiv exists (idempotent)"
docker exec "${ANALYTICS_CONTAINER}" psql -U catalyst_analytics_writer -d catalyst_analytics \
  -tAc "SELECT 1 FROM pg_database WHERE datname='catalyst_analytics_hiv'" | grep -q 1 || {
  docker exec "${ANALYTICS_CONTAINER}" psql -U catalyst_analytics_writer -d catalyst_analytics \
    -c "CREATE DATABASE catalyst_analytics_hiv;"
  psql_hiv -c "GRANT CONNECT ON DATABASE catalyst_analytics_hiv TO catalyst_readonly;
               GRANT USAGE ON SCHEMA public TO catalyst_readonly;
               ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO catalyst_readonly;"
}

echo "==> start one-shot fhir-data-pipes controller on :${CONTROLLER_PORT}"
docker rm -f hiv-data-pipes >/dev/null 2>&1 || true
docker run -d --name hiv-data-pipes \
  --network "${NETWORK}" \
  -v "${SRC_DIR}/config:/app/config:ro" \
  -v hiv-data-pipes-dwh:/app/dwh \
  -e JAVA_OPTS="-Xms512m -Xmx2g" \
  -e FHIRDATA_SINKDBCONFIGPATH="config/postgres-sink.json" \
  -e FHIRDATA_GENERATEPARQUETFILES=false \
  -e FHIRDATA_CREATEHIVERESOURCETABLES=false \
  -e FHIRDATA_CREATEPARQUETVIEWS=false \
  -e FHIRDATA_NUMTHREADS=1 \
  -p "127.0.0.1:${CONTROLLER_PORT}:8080" \
  "${IMAGE}" >/dev/null
curl -fsS --retry-all-errors --retry-connrefused --retry 60 \
  --retry-delay 3 --retry-max-time 180 --max-time 5 \
  "http://localhost:${CONTROLLER_PORT}/actuator/health" | grep -q UP

echo "==> trigger FULL run and wait"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
curl -s -X POST --max-time 10 "http://localhost:${CONTROLLER_PORT}/run?runMode=FULL" | grep -q SUCCESS
while curl -s --max-time 5 "http://localhost:${CONTROLLER_PORT}/status" | grep -q RUNNING; do
  sleep 30
done
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "==> verify fetch completeness against the live source"
expected="$(curl -s --max-time 15 -u "${OPENMRS_AUTH}" \
  "${OPENMRS_FHIR}/Observation?_summary=count" | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])')"
fetched="$(docker logs hiv-data-pipes 2>&1 | grep -oE 'numFetchedResources_Observation_main : [0-9]+' | tail -1 | grep -oE '[0-9]+$')"
if [ "${fetched}" != "${expected}" ]; then
  echo "ERROR: fetched ${fetched} observations but the source reports ${expected}." >&2
  echo "Paging likely truncated (host sleep / HTTP 410) — re-run with the machine awake." >&2
  exit 1
fi
echo "    observations: ${fetched}/${expected}"

echo "==> apply curated analytics SQL"
psql_hiv <"${SRC_DIR}/sql/001_analytics_hiv_v1.sql" >/dev/null
psql_hiv <"${SRC_DIR}/sql/002_analytics_hiv_comments_v1.sql" >/dev/null

echo "==> verify curated views hold exactly one row per resource"
# The base *_flat tables are lossless cross products by design, so their row
# counts exceed their entity counts and that is fine. The curated views are the
# query surface, and each promises one row per resource in its COMMENT ON VIEW.
# Nothing checked that promise, which is how a fan-out reached a result: a join
# that multiplies rows still returns a plausible number.
#
# Iterated as a list rather than `while read` from a heredoc, because psql_hiv
# runs `docker exec -i` and would eat the loop's stdin after the first view.
grain_failures=0
for grain in \
  hiv_observation_fact_v1:observation_id \
  hiv_visit_fact_v1:encounter_id \
  hiv_medication_request_fact_v1:medication_request_id \
  hiv_patient_dim_v1:patient_id
do
  view="${grain%%:*}"
  key="${grain##*:}"
  counts="$(psql_hiv -tAc \
    "SELECT count(*)||' '||count(DISTINCT ${key}) FROM analytics.${view}")"
  rows="${counts%% *}"
  distinct="${counts##* }"
  if [ "${rows}" != "${distinct}" ]; then
    echo "ERROR: analytics.${view} has ${rows} rows for ${distinct} distinct ${key}." >&2
    grain_failures=$((grain_failures + 1))
  else
    echo "    ${view}: ${rows} rows, one per ${key}"
  fi
done
if [ "${grain_failures}" -ne 0 ]; then
  echo "A curated view lost its one-row-per-resource grain; a join is fanning out." >&2
  exit 1
fi

echo "==> verify medication coding is safe to pivot per system"
# hiv_medication_request_fact_v1 aggregates code.coding per system (openmrs
# local / CIEL / SNOMED / WHO-ANC) so a multi-coded resource cannot pair a
# code with the wrong system. That pivot assumes at most one coding per
# system per resource, and that every non-null system is one of the four it
# knows about -- an ingestion producing more than one, or a system outside
# that set, would have its extra coding silently discarded by the view.
known_systems="'https://cielterminology.org', 'http://snomed.info/sct/', 'http://fhir.org/guides/who/anc-cds/CodeSystem/anc-custom-codes'"
coding_failures=0
for check in \
  "medication_flat:id:code_sys" \
  "medication_request_flat:id:medication_system"
do
  table="${check%%:*}"
  rest="${check#*:}"
  key="${rest%%:*}"
  system_col="${rest##*:}"
  # This source represents "no external coding system" (the OpenMRS-native
  # arm the view buckets separately) as '' on some tables and NULL on
  # others, not consistently -- both mean the same thing here.
  no_system="${system_col} IS NULL OR ${system_col} = ''"
  duplicate_systems="$(psql_hiv -tAc \
    "SELECT count(*) FROM (
       SELECT ${key} FROM public.${table}
       WHERE NOT (${no_system})
       GROUP BY ${key}, ${system_col} HAVING count(*) > 1
     ) x")"
  if [ "${duplicate_systems}" -ne 0 ]; then
    echo "ERROR: public.${table} has ${duplicate_systems} resource(s) with more than one coding for the same ${system_col}." >&2
    coding_failures=$((coding_failures + 1))
  fi
  unexpected_systems="$(psql_hiv -tAc \
    "SELECT count(DISTINCT ${system_col}) FROM public.${table}
     WHERE NOT (${no_system}) AND ${system_col} NOT IN (${known_systems})")"
  if [ "${unexpected_systems}" -ne 0 ]; then
    echo "ERROR: public.${table}.${system_col} has ${unexpected_systems} system(s) outside {${known_systems}}; hiv_medication_request_fact_v1 would silently discard that coding." >&2
    coding_failures=$((coding_failures + 1))
  fi
done
if [ "${coding_failures}" -ne 0 ]; then
  echo "Medication coding does not fit the per-system pivot; extend it before trusting this run." >&2
  exit 1
fi
echo "    medication_flat, medication_request_flat: at most one coding per known system"

echo "==> verify OpenMRS-native observation coding and displays"
mapping_counts="$(psql_hiv -tAc \
  "SELECT count(*)||' '||count(NULLIF(openmrs_concept_code, ''))
   FROM analytics.hiv_concept_mapping_v1")"
mapping_rows="${mapping_counts%% *}"
mapping_native_codes="${mapping_counts##* }"
if [ "${mapping_rows}" != "${mapping_native_codes}" ]; then
  echo "ERROR: analytics.hiv_concept_mapping_v1 has ${mapping_native_codes} nonblank OpenMRS-native codes for ${mapping_rows} rows." >&2
  exit 1
fi

# Recompute the mapping independently from the raw table in both directions.
# The source uses both '' (production) and potentially NULL (compatibility) for
# "no external system"; either denotes the OpenMRS-native coding arm.
mapping_differences="$(psql_hiv -tAc "
WITH raw_per_observation AS (
  SELECT
    o.id,
    MAX(o.obs_date) AS observed_at,
    MAX(o.code_display) FILTER (
      WHERE o.code_sys IS NULL OR o.code_sys = ''
    ) AS concept_name,
    MAX(o.code_code) FILTER (
      WHERE o.code_sys IS NULL OR o.code_sys = ''
    ) AS openmrs_concept_code,
    MAX(o.code_code) FILTER (
      WHERE o.code_sys = 'https://cielterminology.org'
    ) AS ciel_code,
    MAX(o.code_code) FILTER (
      WHERE o.code_sys = 'http://snomed.info/sct/'
    ) AS snomed_code,
    MAX(o.code_code) FILTER (
      WHERE o.code_sys = 'http://fhir.org/guides/who/anc-cds/CodeSystem/anc-custom-codes'
    ) AS who_anc_code
  FROM public.observation_flat AS o
  GROUP BY o.id
), expected AS (
  SELECT
    concept_name,
    openmrs_concept_code,
    ciel_code,
    snomed_code,
    who_anc_code,
    COUNT(*) AS observation_count
  FROM raw_per_observation
  WHERE observed_at >= '2020-01-01' AND observed_at < '2035-01-01'
  GROUP BY 1, 2, 3, 4, 5
), missing_from_view AS (
  SELECT * FROM expected
  EXCEPT
  SELECT * FROM analytics.hiv_concept_mapping_v1
), missing_from_raw AS (
  SELECT * FROM analytics.hiv_concept_mapping_v1
  EXCEPT
  SELECT * FROM expected
)
SELECT (SELECT COUNT(*) FROM missing_from_view)
     + (SELECT COUNT(*) FROM missing_from_raw);")"
if [ "${mapping_differences}" -ne 0 ]; then
  echo "ERROR: analytics.hiv_concept_mapping_v1 differs from the independent raw-table mapping in ${mapping_differences} direction-row(s)." >&2
  exit 1
fi

display_mismatches="$(psql_hiv -tAc "
WITH raw_displays AS (
  SELECT
    o.id,
    MAX(o.code_display) FILTER (
      WHERE o.code_sys IS NULL OR o.code_sys = ''
    ) AS concept_name,
    MAX(o.value_display) FILTER (
      WHERE o.value_sys IS NULL OR o.value_sys = ''
    ) AS value_coded_name
  FROM public.observation_flat AS o
  GROUP BY o.id
)
SELECT COUNT(*)
FROM analytics.hiv_observation_fact_v1 AS f
JOIN raw_displays AS r ON r.id = f.observation_id
WHERE f.concept_name IS DISTINCT FROM r.concept_name
   OR f.value_coded_name IS DISTINCT FROM r.value_coded_name;")"
if [ "${display_mismatches}" -ne 0 ]; then
  echo "ERROR: analytics.hiv_observation_fact_v1 has ${display_mismatches} OpenMRS-native display mismatch(es)." >&2
  exit 1
fi
echo "    concept mapping: ${mapping_rows}/${mapping_rows} native codes; raw mapping and displays reconcile"

echo "==> register pipeline run (freshness contract)"
counts="$(psql_hiv -tAc "SELECT json_build_object(
  'Patient', (SELECT COUNT(DISTINCT id) FROM public.patient_flat),
  'Observation', (SELECT COUNT(DISTINCT id) FROM public.observation_flat),
  'Encounter', (SELECT COUNT(DISTINCT id) FROM public.encounter_flat),
  'MedicationRequest', (SELECT COUNT(DISTINCT id) FROM public.medication_request_flat),
  'Medication', (SELECT COUNT(DISTINCT id) FROM public.medication_flat),
  'Condition', (SELECT COUNT(DISTINCT id) FROM public.condition_flat))")"
psql_hiv <<SQL >/dev/null
INSERT INTO analytics.pipeline_run_v1 (
    pipeline_run_id, completion_state, source_watermark,
    started_at, completed_at, data_pipes_commit, resource_counts
) VALUES (
    'hiv-' || to_char(now(), 'YYYYMMDD"T"HH24MISS"Z"'),
    'succeeded',
    (SELECT MAX(obs_date) FROM public.observation_flat),
    '${started_at}', '${completed_at}',
    '${IMAGE#*:}',
    '${counts}'::jsonb
);
SQL

echo "==> regenerate catalog from database + overlay"
(cd "${ROOT}" && uv run python scripts/generate-catalyst-source-catalog.py \
  --dsn "${HOST_DSN}" \
  --overlay "${SRC_DIR}/catalog-overlay.json" \
  --out "${SRC_DIR}/catalog/openmrs-hiv-catalog.json")

echo "==> done. Restart catalyst-gateway to load the regenerated catalog."
