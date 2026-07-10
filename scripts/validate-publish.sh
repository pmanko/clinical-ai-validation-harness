#!/usr/bin/env bash
# Publish a single validation run's report to the reports subdomain (reports.<domain>).
#
# One-step publish: re-renders the chosen run's report.html (latest report.py), stages it under
# artifacts/reports/<slug>/index.html, FREEZES a self-contained interactive dashboard alongside it
# (so the index's "Interactive dashboard" button appears), REBUILDS the curated index, and rsyncs
# the whole reports dir to the VM (NO --delete, so previously published reports survive). Caddy
# serves it live at https://<CADDY_SITE_REPORTS>/<slug>/ (file_server, no restart needed).
#
# The slug is auto-upserted into reports-index.json so a published run is never left unlisted:
# insert-if-absent (newest first), NEVER overwriting an existing entry, so curated title/summary
# survive a re-publish. Pass [title] [summary] [takeaway] to seed the prose (else a placeholder
# title you edit later); editing reports-index.json afterwards stays the source of curation.
#
# Usage: scripts/validate-publish.sh <run_id> <slug> [title] [summary] [takeaway]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

RUN="${1:?usage: validate-publish.sh <run_id> <slug> [title] [summary] [takeaway]}"
SLUG="${2:?usage: validate-publish.sh <run_id> <slug> [title] [summary] [takeaway]}"
TITLE="${3:-}"
SUMMARY="${4:-}"
TAKEAWAY="${5:-}"

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

# Freeze a self-contained interactive dashboard alongside the report. build-reports-index.py's
# _card() only adds the "Interactive dashboard" button when <slug>/dashboard.html exists, so this
# is what makes the button appear. Best-effort: a freeze hiccup must not block the report publish.
echo "==> freezing interactive dashboard snapshot"
( cd "${ROOT}" && uv run python scripts/validate-dashboard.py --freeze "${DEST}/dashboard.html" \
    --run "${ROOT}/artifacts/validate/${RUN}" ) \
  || echo "warn: dashboard freeze failed — the 'Interactive dashboard' button will be absent for ${SLUG}" >&2

# Upsert this run into the curated manifest BEFORE the index rebuild, so a published run is never
# left deployed-but-unlisted. Insert-if-absent (newest first); NEVER overwrite an existing entry,
# so curated prose survives a re-publish. New slugs get the passed TITLE/SUMMARY/TAKEAWAY or a
# placeholder title to edit.
echo "==> upserting ${SLUG} into reports-index.json"
python3 - "${ROOT}/reports-index.json" "${SLUG}" "${TITLE}" "${SUMMARY}" "${TAKEAWAY}" <<'PY'
import json, sys
from pathlib import Path
idx_path, slug, title, summary, takeaway = (
    Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
idx = json.loads(idx_path.read_text())
runs = idx.setdefault("runs", [])
if any(r.get("slug") == slug for r in runs):
    print(f"==> {slug} already curated in reports-index.json — left as-is")
else:
    runs.insert(0, {"slug": slug,
                    "title": title or f"{slug} (auto-added — edit title)",
                    "summary": summary or "",
                    "takeaway": takeaway or ""})
    idx_path.write_text(json.dumps(idx, indent=2) + "\n")
    print(f"==> inserted {slug} at the top of reports-index.json (edit title/summary to curate)")
PY

# Rebuild the curated index now (reads reports-index.json + this run's just-staged meta.json), so the
# single rsync below pushes the report, the dashboard, AND the refreshed index together.
echo "==> rebuilding reports index"
( cd "${ROOT}" && uv run python scripts/build-reports-index.py ) \
  || echo "warn: index rebuild failed" >&2

# Stage the curated manifest ALONGSIDE the reports so each report's in-page run-switcher can fetch
# it at runtime (the report requests ../reports-index.json, which resolves to <reports>/reports-index.json
# on the served subdomain). The single rsync below carries it up with everything else; without it the
# switcher just degrades to hidden (graceful), so this is what turns the cross-run switcher ON in prod.
cp "${ROOT}/reports-index.json" "${ROOT}/artifacts/reports/reports-index.json"
echo "==> staged reports-index.json alongside the reports (for the in-report run-switcher)"

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
