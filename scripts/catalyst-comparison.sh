#!/usr/bin/env bash
# The Phase 1 comparison, one command, end to end.
#
#   scripts/catalyst-comparison.sh run              start (or restart) the frozen comparison
#   scripts/catalyst-comparison.sh resume <run-id>  continue an interrupted run
#   scripts/catalyst-comparison.sh finish <run-id>  score twice (byte-check), build the
#                                                   report, freeze the dashboard, stage both
#
# The run lands in artifacts/catalyst-notebook-validation/<run-id>/ where the
# live dashboard (scripts/validate-dashboard.py, :8099) picks it up; `finish`
# is idempotent and re-runnable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUITE="${SUITE:-datasets/validation/catalyst/catalyst-phase1-comparison-v1.json}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:18000}"
OUT_DIR="${OUT_DIR:-${ROOT}/artifacts/catalyst-notebook-validation}"
POSTGRES_DSN="${POSTGRES_DSN:-postgresql://catalyst_readonly:demo-readonly-change-me@127.0.0.1:15443/catalyst_analytics_hiv}"
# SLUG defaults per run id inside `finish`, so re-running finish on any day
# restages the same run under the same slug instead of duplicating it.
SLUG="${SLUG:-}"

cmd="${1:?usage: catalyst-comparison.sh run|resume <run-id>|finish <run-id>}"

run_suite() {
  (cd "${ROOT}" && uv run harness-cli catalyst run \
    --suite "${SUITE}" \
    --gateway-url "${GATEWAY_URL}" \
    --output-dir "${OUT_DIR}" \
    --postgres-dsn "${POSTGRES_DSN}" \
    "$@")
}

case "${cmd}" in
  run)
    run_suite
    ;;
  resume)
    run_id="${2:?resume needs the run id}"
    run_suite --resume "${OUT_DIR}/${run_id}"
    ;;
  finish)
    run_id="${2:?finish needs the run id}"
    run_dir="${OUT_DIR}/${run_id}"
    SLUG="${SLUG:-catalyst-phase1-comparison-${run_id%%-*}}"
    [[ -f "${run_dir}/results.json" ]] || { echo "ERROR: ${run_dir} has no results.json (run not finished — use resume)" >&2; exit 1; }

    echo "==> triage: every failure vetted, every pass exercised"
    (cd "${ROOT}" && uv run python scripts/triage-run.py "${run_dir}")

    echo "==> scoring twice; replays must be byte-identical"
    (cd "${ROOT}" && uv run python - "$run_dir" <<'PY'
import sys
from harness.catalyst.notebook_scoring import score_run
first = score_run(sys.argv[1], as_json=True)
second = score_run(sys.argv[1], as_json=True)
assert first == second, "scorer replay was not byte-identical"
out = f"{sys.argv[1]}/score.json"
open(out, "w", encoding="utf-8").write(first)
print(f"score -> {out} (byte-identical on replay)")
PY
)

    echo "==> single-run narrative report"
    (cd "${ROOT}" && uv run harness-cli catalyst report "${run_dir}")

    echo "==> per-team comparison page"
    (cd "${ROOT}" && uv run python - "$run_dir" <<'PY'
import sys
from pathlib import Path
from harness.catalyst.profile_comparison_report import (
    build_comparison_report,
    entries_from_comparison_run,
)
run_dir = Path(sys.argv[1])
entries = entries_from_comparison_run(run_dir)
html = build_comparison_report(entries, title="Catalyst Phase 1 team comparison")
out = run_dir / "comparison.html"
out.write_text(html, encoding="utf-8")
print(f"comparison -> {out} ({len(entries)} teams)")
PY
)

    echo "==> stage report + frozen dashboard into the curated index"
    "${ROOT}/scripts/publish-report.sh" catalyst "${run_dir}" "${SLUG}" \
      "${TITLE:-Catalyst Phase 1: three model teams on the locked HIV suite}" \
      "${SUMMARY:-}" "${TAKEAWAY:-}"
    ;;
  score)
    # Compose any number of single-pass runs of the same suite into one
    # sample: catalyst-comparison.sh score <run-id> [<run-id> ...]
    shift
    [[ $# -ge 1 ]] || { echo "score needs at least one run id" >&2; exit 1; }
    dirs=()
    for run_id in "$@"; do dirs+=("${OUT_DIR}/${run_id}"); done
    (cd "${ROOT}" && uv run python -c '
import sys
from harness.catalyst.notebook_scoring import score_runs
print(score_runs(sys.argv[1:], as_json=True), end="")
' "${dirs[@]}")
    ;;
  *)
    echo "unknown command ${cmd}" >&2; exit 1;;
esac
