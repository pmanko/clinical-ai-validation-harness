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

# Record the exact run DIRECTORY that produced this report, so the index resolves
# judge/results unambiguously. The data's run_id can differ from the dir name — a judged
# sibling reuses another run's results.jsonl and only adds judge.jsonl — so grepping the
# rendered HTML for a run_id is unreliable; meta.run_dir is authoritative.
python3 - "${ROOT}/artifacts/validate/${RUN}" "${SLUG}" "${DEST}/meta.json" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
run_path, slug, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
cset = None
ev = run_path / "events.jsonl"
if ev.exists():
    for line in ev.read_text().splitlines():
        try:
            o = json.loads(line)
            if o.get("event_type") == "run" and o.get("comparison_set"):
                cset = o["comparison_set"]; break
        except Exception:
            pass
gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
Path(out).write_text(json.dumps(
    {"slug": slug, "run_dir": run_path.name, "comparison_set": cset, "generated_at": gen},
    indent=2) + "\n")
print(f"==> wrote {out} (run_dir={run_path.name}, set={cset})")
PY

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
