#!/usr/bin/env bash
# Family-aware report/evidence staging and optional cloud publication.
# Usage: publish-report.sh <chartsearchai|catalyst> <run_dir> <slug> [title] [summary] [takeaway]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAMILY="${1:?usage: publish-report.sh <family> <run_dir> <slug> [title] [summary] [takeaway]}"
RUN_DIR="${2:?usage: publish-report.sh <family> <run_dir> <slug> [title] [summary] [takeaway]}"
SLUG="${3:?usage: publish-report.sh <family> <run_dir> <slug> [title] [summary] [takeaway]}"
TITLE="${4:-}"
SUMMARY="${5:-}"
TAKEAWAY="${6:-}"
REPORTS_ROOT="${REPORTS_ROOT:-${ROOT}/artifacts/reports}"
DRY_RUN="${PUBLISH_DRY_RUN:-0}"

mkdir -p "${REPORTS_ROOT}"
if [[ "${DRY_RUN}" == "1" ]]; then
  MANIFEST="${REPORTS_ROOT}/reports-index.json"
  if [[ ! -f "${MANIFEST}" ]]; then
    cp "${ROOT}/reports-index.json" "${MANIFEST}"
  fi
else
  MANIFEST="${ROOT}/reports-index.json"
fi

python3 "${ROOT}/scripts/stage-report.py" \
  "${FAMILY}" "${RUN_DIR}" "${SLUG}" "${TITLE}" "${SUMMARY}" "${TAKEAWAY}" \
  --reports-root "${REPORTS_ROOT}" --manifest "${MANIFEST}" --root "${ROOT}"

if [[ "${FAMILY}" == "chartsearchai" && "${DRY_RUN}" != "1" ]]; then
  echo "==> freezing ChartSearchAI interactive dashboard snapshot"
  (cd "${ROOT}" && uv run python scripts/validate-dashboard.py \
    --freeze "${REPORTS_ROOT}/${SLUG}/dashboard.html" --run "${RUN_DIR}") \
    || echo "warn: dashboard freeze failed for ${SLUG}" >&2
fi

python3 "${ROOT}/scripts/build-reports-index.py" \
  --reports-root "${REPORTS_ROOT}" --manifest "${MANIFEST}" --root "${ROOT}"
if [[ "${MANIFEST}" != "${REPORTS_ROOT}/reports-index.json" ]]; then
  cp "${MANIFEST}" "${REPORTS_ROOT}/reports-index.json"
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "==> dry-run staged only under ${REPORTS_ROOT}"
  exit 0
fi

# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"
if ! gcp_vm_exists || [[ "$(gcp_vm_status)" != "RUNNING" ]]; then
  echo "warn: VM ${GCP_VM_NAME} not RUNNING — staged locally only." >&2
  exit 1
fi

IP="$(gcp_vm_ip)"
gcp_ssh_keygen_once
gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/artifacts/reports"
rsync -avz \
  -e "ssh -i ${GCP_SSH_KEY} -o StrictHostKeyChecking=accept-new" \
  "${REPORTS_ROOT}/" \
  "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/artifacts/reports/"
gcp_ssh "chmod -R a+rX ${GCP_REMOTE_REPO}/artifacts/reports"

SITE="$(awk -F= '/^CADDY_SITE_REPORTS=/{print $2}' "${ROOT}/.env.chartsearch.cloud" 2>/dev/null || true)"
SITE="${SITE:-reports.openclinai.org}"
echo "==> published: https://${SITE}/${SLUG}/"
