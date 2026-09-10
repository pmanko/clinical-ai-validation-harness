#!/usr/bin/env bash
# Back up the published validation reports (artifacts/reports) to a versioned GCS bucket so the
# VM's copy is never the only one. Additive: never deletes objects, and the bucket keeps every
# prior version of an overwritten file. publish-report.sh runs this after every publish; run it by
# hand (`make reports-backup`) after restoring or bulk-editing reports.
#
# One-time bucket setup (operator, once per project):
#   gcloud storage buckets create gs://<bucket> --project <project> --location <region> \
#       --uniform-bucket-level-access --public-access-prevention
#   gcloud storage buckets update gs://<bucket> --versioning
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"
BUCKET="${REPORTS_BACKUP_BUCKET:-gs://${GCP_PROJECT}-reports}"
SRC="${REPORTS_ROOT:-${ROOT}/artifacts/reports}"

[[ -d "${SRC}" ]] || { echo "error: no reports directory at ${SRC}" >&2; exit 1; }
if ! gcloud storage buckets describe "${BUCKET}" --project "${GCP_PROJECT}" >/dev/null 2>&1; then
  echo "error: bucket ${BUCKET} does not exist in project ${GCP_PROJECT}. One-time setup:" >&2
  echo "  gcloud storage buckets create ${BUCKET} --project ${GCP_PROJECT} --location ${GCP_REGION} --uniform-bucket-level-access --public-access-prevention" >&2
  echo "  gcloud storage buckets update ${BUCKET} --versioning" >&2
  exit 1
fi
if [[ "$(gcloud storage buckets describe "${BUCKET}" --project "${GCP_PROJECT}" --format='value(versioning.enabled)')" != "True" ]]; then
  echo "error: ${BUCKET} has versioning off; a backup that overwrites in place is not a backup." >&2
  echo "  gcloud storage buckets update ${BUCKET} --versioning" >&2
  exit 1
fi

echo "==> backing up ${SRC} -> ${BUCKET}/artifacts/reports (additive, versioned)"
gcloud storage rsync --recursive "${SRC}" "${BUCKET}/artifacts/reports"
if OBJECT_COUNT="$(gcloud storage ls -r "${BUCKET}/artifacts/reports/**" | wc -l | tr -d ' ')"; then
  echo "==> objects in ${BUCKET}/artifacts/reports: ${OBJECT_COUNT}"
else
  echo "warn: backup completed, but object count unavailable for ${BUCKET}/artifacts/reports." >&2
fi
