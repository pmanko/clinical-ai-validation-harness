#!/usr/bin/env bash
# The Phase 1 comparison, one command, end to end.
#
#   scripts/catalyst-comparison.sh run              start (or restart) the frozen comparison
#   scripts/catalyst-comparison.sh resume <run-id>  create a linked replacement for
#                                                   an interrupted run
#   scripts/catalyst-comparison.sh finish <run-id>  score twice (byte-check), build the
#                                                   report, freeze the dashboard, stage both
#
# The run lands in artifacts/catalyst-notebook-validation/<run-id>/ where the
# live dashboard (scripts/validate-dashboard.py, :8099) picks it up; `finish`
# is idempotent and re-runnable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Everything a run needs comes from one seed file, so nothing about a
# comparison depends on which variables happened to be exported that day.
CONFIG="${CONFIG:-${ROOT}/datasets/validation/catalyst/run-config.template.json}"

# Reads one field out of a config file (the template for `run`, the run's own
# frozen copy afterwards).
cfg() {
  (cd "${ROOT}" && uv run python -c '
import sys
field = sys.argv[2]
from harness.catalyst.run_config import postgres_dsn, resolve
config = resolve(sys.argv[1], require_secrets=(field == "dsn"))
if field == "dsn":
    print(postgres_dsn(config))
else:
    value = config
    for part in field.split("."):
        value = (value or {}).get(part)
    print(value if value is not None else "")
' "$1" "$2")
}

cmd="${1:?usage: catalyst-comparison.sh run|resume <run-id>|finish <run-id>}"

OUT_DIR="${ROOT}/$(cfg "${CONFIG}" outputDir)"

run_suite() {
  (cd "${ROOT}" && uv run harness-cli catalyst run \
    --run-config "${CONFIG}" \
    "$@")
}

case "${cmd}" in
  run)
    run_suite
    ;;
  resume)
    run_id="${2:?resume needs the run id}"
    source_dir="${OUT_DIR}/${run_id}"
    CONFIG="${source_dir}/run-config.json"
    frozen_out_dir="${ROOT}/$(cfg "${CONFIG}" outputDir)"
    [[ "${source_dir}" == "${frozen_out_dir}/${run_id}" ]] || {
      echo "ERROR: recovery source does not match its frozen outputDir" >&2
      exit 1
    }
    OUT_DIR="${frozen_out_dir}"
    run_suite --resume "${source_dir}"
    ;;
  finish)
    run_id="${2:?finish needs the run id}"
    run_dir="${OUT_DIR}/${run_id}"
    # The run's own seed decides how it is judged and published.
    if [[ -f "${run_dir}/run-config.json" ]]; then
      CONFIG="${run_dir}/run-config.json"
      frozen_out_dir="${ROOT}/$(cfg "${CONFIG}" outputDir)"
      [[ "${run_dir}" == "${frozen_out_dir}/${run_id}" ]] || {
        echo "ERROR: run directory does not match its frozen outputDir" >&2
        exit 1
      }
      OUT_DIR="${frozen_out_dir}"
    fi
    SLUG="${SLUG:-$(cfg "${CONFIG}" publish.slug)}"
    SLUG="${SLUG:-catalyst-phase1-comparison-${run_id%%-*}}"
    [[ -f "${run_dir}/results.json" ]] || { echo "ERROR: ${run_dir} has no results.json (run not finished — use resume)" >&2; exit 1; }

    echo "==> triage: every conversation conformed, every pass exercised"
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
from harness.catalyst.run_config import load_frozen
run_dir = Path(sys.argv[1])
entries = entries_from_comparison_run(run_dir)
# The gates come from the run's own seed, so the page records the policy it
# was judged against rather than whatever the programme uses today.
gates = (load_frozen(run_dir).get("gates") or None)
html = build_comparison_report(
    entries, title="Catalyst Phase 1 team comparison", gates=gates
)
out = run_dir / "comparison.html"
out.write_text(html, encoding="utf-8")
print(f"comparison -> {out} ({len(entries)} teams, gates={gates})")
PY
)

    echo "==> stage report + frozen dashboard into the curated index"
    "${ROOT}/scripts/publish-report.sh" catalyst "${run_dir}" "${SLUG}" \
      "${TITLE:-$(cfg "${CONFIG}" publish.title)}" \
      "${SUMMARY:-$(cfg "${CONFIG}" publish.summary)}" \
      "${TAKEAWAY:-$(cfg "${CONFIG}" publish.takeaway)}"
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
