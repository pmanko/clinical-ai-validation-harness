#!/usr/bin/env bash
# Publish a single validation run's report to the reports subdomain (reports.<domain>).
#
# Quick + selective: re-renders the chosen run's report.html (so it carries the latest report.py —
# PDF button, feedback seam), stages it under artifacts/reports/<slug>/index.html, and rsyncs the
# curated reports dir to the VM (NO --delete, so previously published reports survive). Caddy serves
# it live at https://<CADDY_SITE_REPORTS>/<slug>/ (file_server, no restart needed).
#
# Usage: scripts/validate-publish.sh <run_id> <slug>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

RUN="${1:?usage: validate-publish.sh <run_id> <slug>}"
SLUG="${2:?usage: validate-publish.sh <run_id> <slug>}"

echo "==> rendering report for run ${RUN} (picks up the latest report.py)"
( cd "${ROOT}" && uv run harness-cli validate report "${RUN}" )

SRC="${ROOT}/artifacts/validate/${RUN}/report.html"
[ -f "${SRC}" ] || { echo "error: no report.html for run ${RUN}" >&2; exit 1; }

DEST="${ROOT}/artifacts/reports/${SLUG}"
mkdir -p "${DEST}"
cp "${SRC}" "${DEST}/index.html"
echo "==> staged ${DEST}/index.html"

if ! gcp_vm_exists || [ "$(gcp_vm_status)" != "RUNNING" ]; then
  echo "warn: VM ${GCP_VM_NAME} not RUNNING — staged locally only. Start it (make cloud-start) and re-run to publish." >&2
  exit 1
fi

IP="$(gcp_vm_ip)"
gcp_ssh_keygen_once
gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/artifacts/reports"
echo "==> rsync artifacts/reports/ -> ${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/artifacts/reports/"
rsync -avz \
  -e "ssh -i ${GCP_SSH_KEY} -o StrictHostKeyChecking=accept-new" \
  "${ROOT}/artifacts/reports/" \
  "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/artifacts/reports/"
gcp_ssh "chmod -R a+rX ${GCP_REMOTE_REPO}/artifacts/reports"

SITE="$(awk -F= '/^CADDY_SITE_REPORTS=/{print $2}' "${ROOT}/.env.chartsearch.cloud" 2>/dev/null || true)"
SITE="${SITE:-reports.openclinai.org}"
echo "==> published: https://${SITE}/${SLUG}/"
