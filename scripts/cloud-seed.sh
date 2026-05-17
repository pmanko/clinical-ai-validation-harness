#!/usr/bin/env bash
# One-time data seed: dump the 5,284-patient corpus from the LOCAL DB,
# rsync to the VM, restore on the cloud DB. ~50MB dump; ~3-10 minutes
# end-to-end depending on uplink.
#
# Source (local) and target (cloud) DB names differ by convention:
#   - Local: openmrs_test (feature 002's transform pipeline target)
#   - Cloud: openmrs      (the OpenMRS default; cloud doesn't carry the
#                          local pipeline's split between baseline and corpus)
# Override via SEED_SOURCE_DB / SEED_TARGET_DB if you need a different shape.
#
# Re-run is destructive on the VM-side TARGET schema (drops then recreates).
# Local DB is read-only here.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

SOURCE_DB="${SEED_SOURCE_DB:-openmrs_test}"
TARGET_DB="${SEED_TARGET_DB:-openmrs}"
DUMP_LOCAL="${ROOT}/artifacts/cloud-seed/${SOURCE_DB}.sql.gz"

mkdir -p "${ROOT}/artifacts/cloud-seed"

echo "==> dumping ${SOURCE_DB} from local harness-openmrs-db"
docker exec harness-openmrs-db \
  mysqldump --user="${OMRS_DB_USER:-openmrs}" \
            --password="${OMRS_DB_PASSWORD:-openmrs}" \
            --single-transaction --quick --no-tablespaces \
            --routines --triggers --events \
            "${SOURCE_DB}" \
  | gzip -c > "${DUMP_LOCAL}"
echo "    dump: ${DUMP_LOCAL} ($(du -h "${DUMP_LOCAL}" | cut -f1))"

echo "==> rsync dump → VM"
IP="$(gcp_vm_ip)"
gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/artifacts/cloud-seed"
rsync -avz --progress \
  -e "ssh -i ${GCP_SSH_KEY} -o StrictHostKeyChecking=accept-new" \
  "${DUMP_LOCAL}" \
  "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/artifacts/cloud-seed/"

echo "==> restoring into ${TARGET_DB} on VM"
# DROP/CREATE/GRANT use root (the openmrs user only has DML privs on whatever
# DB MariaDB initially created from MYSQL_DATABASE; DDL needs root).
gcp_ssh "docker exec -i harness-openmrs-db mysql -u root -popenmrs -e \"
  DROP DATABASE IF EXISTS ${TARGET_DB};
  CREATE DATABASE ${TARGET_DB};
  GRANT ALL PRIVILEGES ON ${TARGET_DB}.* TO 'openmrs'@'%';
  FLUSH PRIVILEGES;
\""

echo "    loading $(du -h "${DUMP_LOCAL}" | cut -f1) of SQL via gunzip → mysql..."
gcp_ssh "cd ${GCP_REMOTE_REPO} && gunzip -c artifacts/cloud-seed/${SOURCE_DB}.sql.gz | docker exec -i harness-openmrs-db mysql -u root -popenmrs ${TARGET_DB}"

echo "    row counts (sample):"
gcp_ssh "docker exec harness-openmrs-db mysql -u openmrs -popenmrs ${TARGET_DB} -e \"
  SELECT 'patient' AS tbl, COUNT(*) AS rows_ct FROM patient
  UNION ALL SELECT 'encounter', COUNT(*) FROM encounter
  UNION ALL SELECT 'obs', COUNT(*) FROM obs;
\""

# Bulk-INSERTed rows don't fire Hibernate Search entity listeners, so OpenMRS's
# Lucene index is out of sync with the freshly-restored data — patient search
# returns 0 hits until a full reindex happens. Trigger it now so the seed
# operation produces a search-ready DB, not a half-loaded state.
#
# Runs over ssh on the VM (POSTs to the proxy's local port 80) so we don't
# need to know the public URL / TLS state from the local shell. POST returns
# when reindex is done; 10-min cap is well above the observed ~35s for 5K
# patients on e2-standard-4. Fails the script if reindex doesn't complete —
# silent success on a stale index is exactly the smell this fix removes.
echo ""
echo "==> trigger Hibernate Search reindex (synchronous, ~30-60s for 5K patients)"
# Reindex requires the backend to be up. During cold bring-up sequences
# (e.g. stop backend → seed → start backend) the seed runs DB-only ops
# without the backend; skip with a clear message in that case.
if gcp_ssh "docker inspect -f '{{.State.Health.Status}}' harness-openmrs-backend 2>/dev/null | grep -q healthy"; then
  gcp_ssh "curl -fsS -u admin:Admin123 -m 600 -X POST http://localhost/openmrs/ws/rest/v1/searchindexupdate"
  echo "    reindex complete"
else
  echo "    backend not healthy — skipping reindex. Run this after backend is up:"
  echo "      make cloud-ssh ARGS='curl -fsS -u admin:Admin123 -m 600 -X POST http://localhost/openmrs/ws/rest/v1/searchindexupdate'"
fi

echo ""
echo "==> seed complete."
