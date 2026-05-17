#!/usr/bin/env bash
# One-time data seed: dump openmrs_test from the LOCAL DB container, gzip,
# rsync to the VM, and restore into the VM's DB container. ~1 GB dataset;
# expect ~3-10 minutes depending on uplink.
#
# Re-run is destructive on the VM-side openmrs_test schema (drops then
# recreates). Local DB is read-only here.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

SCHEMA="${SEED_SCHEMA:-openmrs_test}"
DUMP_LOCAL="${ROOT}/artifacts/cloud-seed/${SCHEMA}.sql.gz"

mkdir -p "${ROOT}/artifacts/cloud-seed"

echo "==> dumping ${SCHEMA} from local harness-openmrs-db (this can take a few minutes)"
docker exec harness-openmrs-db \
  mysqldump --user="${OMRS_DB_USER:-openmrs}" \
            --password="${OMRS_DB_PASSWORD:-openmrs}" \
            --single-transaction --quick --no-tablespaces \
            --routines --triggers --events \
            "${SCHEMA}" \
  | gzip -c > "${DUMP_LOCAL}"
echo "    dump: ${DUMP_LOCAL} ($(du -h "${DUMP_LOCAL}" | cut -f1))"

echo "==> rsync dump → VM"
IP="$(gcp_vm_ip)"
gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/artifacts/cloud-seed"
rsync -avz --progress \
  -e "ssh -i ${GCP_SSH_KEY} -o StrictHostKeyChecking=accept-new" \
  "${DUMP_LOCAL}" \
  "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/artifacts/cloud-seed/"

echo "==> restoring ${SCHEMA} on VM"
# Each step is a discrete ssh invocation so any failure surfaces a non-zero
# exit and `set -e` aborts cleanly. The earlier heredoc-bash + pipefail
# approach silently passed on a stuck pipeline, which is exactly the smell
# we don't want. DROP/CREATE/GRANT need root (the openmrs user only has
# privs on `openmrs`, the default DB MariaDB created from MYSQL_DATABASE);
# root password is MYSQL_ROOT_PASSWORD from compose (default `openmrs`).

gcp_ssh "docker exec -i harness-openmrs-db mysql -u root -popenmrs -e \"
  DROP DATABASE IF EXISTS ${SCHEMA};
  CREATE DATABASE ${SCHEMA};
  GRANT ALL PRIVILEGES ON ${SCHEMA}.* TO 'openmrs'@'%';
  FLUSH PRIVILEGES;
\""

echo "    loading $(du -h "${DUMP_LOCAL}" | cut -f1) of SQL via gunzip → mysql..."
gcp_ssh "cd ${GCP_REMOTE_REPO} && gunzip -c artifacts/cloud-seed/${SCHEMA}.sql.gz | docker exec -i harness-openmrs-db mysql -u root -popenmrs ${SCHEMA}"

echo "    row counts (sample):"
gcp_ssh "docker exec harness-openmrs-db mysql -u openmrs -popenmrs ${SCHEMA} -e \"
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
gcp_ssh "curl -fsS -u admin:Admin123 -m 600 -X POST http://localhost/openmrs/ws/rest/v1/searchindexupdate"
echo "    reindex complete"

echo ""
echo "==> seed complete."
