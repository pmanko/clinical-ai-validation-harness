#!/usr/bin/env bash
# Run (or refresh) the OpenMRS HIV data source into the Spark warehouse:
#   1. one-shot fhir-data-pipes ingestion from the OpenMRS FHIR2 R4 endpoint,
#      writing Parquet under the shared /dwh volume and registering its
#      resource tables and ViewDefinition views into the Spark thriftserver,
#   2. verify the fetch was complete against the live source,
#   3. verify nonempty Parquet and registered views through Spark itself.
#
# Prereqs: the catalyst-mvp-isolated stack is up (spark-thriftserver healthy)
# and the OpenMRS instance answers on :8088. Keep the machine awake for the run
# (caffeinate -i) -- a host sleep expires OpenMRS's paging cursors (HTTP 410)
# and silently truncates the fetch; this script verifies counts to catch that.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK="${NETWORK:-catalyst-mvp-isolated-network}"
IMAGE="${IMAGE:-catalyst/fhir-data-pipes:3ea890884d674e2f31257a2da421601f2d75b5e9}"
CONTROLLER_PORT="${CONTROLLER_PORT:-18091}"
# The controller and the thriftserver must share one warehouse volume mounted
# at the same path: the controller registers absolute Parquet locations into
# the Hive metastore, so a differing mount point yields registered views that
# resolve to nothing while every log line still reports success.
DWH_VOLUME="${DWH_VOLUME:-catalyst-mvp-isolated_data-pipes-dwh}"
SPARK_CONTAINER="${SPARK_CONTAINER:-catalyst-mvp-isolated-spark-thriftserver-1}"
OPENMRS_FHIR="${OPENMRS_FHIR:-http://localhost:8088/openmrs/ws/fhir2/R4}"
OPENMRS_AUTH="${OPENMRS_AUTH:-admin:Admin123}"

beeline_q() {
  docker exec -i "${SPARK_CONTAINER}" beeline -u 'jdbc:hive2://localhost:10000' \
    --silent=true --outputformat=tsv2 -e "$1"
}

echo "==> start one-shot fhir-data-pipes controller on :${CONTROLLER_PORT}"
docker rm -f hiv-data-pipes >/dev/null 2>&1 || true
docker run -d --name hiv-data-pipes \
  --network "${NETWORK}" \
  -v "${SRC_DIR}/config:/app/config:ro" \
  -v "${DWH_VOLUME}:/dwh" \
  -e JAVA_OPTS="-Xms512m -Xmx2g" \
  -e FHIRDATA_GENERATEPARQUETFILES=true \
  -e FHIRDATA_CREATEHIVERESOURCETABLES=true \
  -e FHIRDATA_CREATEPARQUETVIEWS=true \
  -e FHIRDATA_THRIFTSERVERHIVECONFIG="config/thriftserver-hive-config.json" \
  -e FHIRDATA_NUMTHREADS=1 \
  -p "127.0.0.1:${CONTROLLER_PORT}:8080" \
  "${IMAGE}" >/dev/null
curl -fsS --retry-all-errors --retry-connrefused --retry 60 \
  --retry-delay 3 --retry-max-time 180 --max-time 5 \
  "http://localhost:${CONTROLLER_PORT}/actuator/health" | grep -q UP

echo "==> trigger FULL run and wait"
curl -s -X POST --max-time 10 "http://localhost:${CONTROLLER_PORT}/run?runMode=FULL" | grep -q SUCCESS
while curl -s --max-time 5 "http://localhost:${CONTROLLER_PORT}/status" | grep -q RUNNING; do
  sleep 30
done

echo "==> verify fetch completeness against the live source"
expected="$(curl -s --max-time 15 -u "${OPENMRS_AUTH}" \
  "${OPENMRS_FHIR}/Observation?_summary=count" | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])')"
fetched="$(docker logs hiv-data-pipes 2>&1 | grep -oE 'numFetchedResources_Observation_main : [0-9]+' | tail -1 | grep -oE '[0-9]+$')"
if [ "${fetched}" != "${expected}" ]; then
  echo "ERROR: fetched ${fetched} observations but the source reports ${expected}." >&2
  echo "Paging likely truncated (host sleep / HTTP 410) -- re-run with the machine awake." >&2
  exit 1
fi
echo "    observations: ${fetched}/${expected}"

echo "==> verify nonempty Parquet on the shared warehouse volume"
parquet_files="$(docker run --rm -v "${DWH_VOLUME}:/dwh" alpine \
  sh -c 'find /dwh -name "*.parquet" -size +0 2>/dev/null | wc -l' | tr -d '[:space:]')"
if [ "${parquet_files}" -eq 0 ]; then
  echo "ERROR: no nonempty Parquet files under ${DWH_VOLUME}." >&2
  exit 1
fi
echo "    nonempty Parquet files: ${parquet_files}"

echo "==> verify the ViewDefinition views registered and return rows"
# Each ViewDefinition in config/views becomes a Spark view. Reading through
# Spark (not the filesystem) is what proves the metastore locations resolve.
view_failures=0
for view in patient_flat observation_flat encounter_flat \
            medication_request_flat medication_flat condition_flat
do
  rows="$(beeline_q "SELECT COUNT(*) FROM ${view};" 2>/dev/null | tail -1 | tr -d '[:space:]')"
  if ! [ "${rows}" -gt 0 ] 2>/dev/null; then
    echo "ERROR: view ${view} is missing or empty through Spark (got '${rows}')." >&2
    view_failures=$((view_failures + 1))
  else
    echo "    ${view}: ${rows} rows"
  fi
done
if [ "${view_failures}" -ne 0 ]; then
  echo "Registered views did not resolve; check that the controller and the" >&2
  echo "thriftserver mount the same warehouse volume at the same path." >&2
  exit 1
fi

echo "==> done. The HIV source is queryable through Spark."
