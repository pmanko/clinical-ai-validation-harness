#!/usr/bin/env bash
# The Phase 1 comparison, one command, end to end.
#
#   scripts/catalyst-comparison.sh run              start (or restart) the frozen comparison
#   scripts/catalyst-comparison.sh resume <run-id>  create a linked recovery run for
#                                                   an interrupted run
#   scripts/catalyst-comparison.sh prepare-review <run-id>
#                                                   verify the completed evidence and
#                                                   write the reviewer's input file
#   scripts/catalyst-comparison.sh finish <run-id>  verify evidence, require the attached
#                                                   reader review, and publish the report
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

cmd="${1:?usage: catalyst-comparison.sh run|resume <run-id>|prepare-review <run-id>|finish <run-id>}"

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
  prepare-review|finish)
    run_id="${2:?${cmd} needs the run id}"
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

    echo "==> verify: every conversation has the evidence its question requires"
    (cd "${ROOT}" && uv run python scripts/triage-run.py "${run_dir}")

    echo "==> prepare one full-context reader-review input"
    (cd "${ROOT}" && uv run python scripts/prepare-catalyst-reader-review.py "${run_dir}")

    if [[ "${cmd}" == "prepare-review" ]]; then
      echo "review input ready: ${run_dir}/reader-review-input.json"
      exit 0
    fi

    echo "==> verify attached review used this exact reader-review input"
    (cd "${ROOT}" && uv run python scripts/prepare-catalyst-reader-review.py \
      "${run_dir}" --check-attached)

    echo "==> full-evidence report with the attached reader review"
    (cd "${ROOT}" && uv run harness-cli catalyst report "${run_dir}")

    echo "==> stage the report and its evidence into the curated index"
    "${ROOT}/scripts/publish-report.sh" catalyst "${run_dir}" "${SLUG}" \
      "${TITLE:-$(cfg "${CONFIG}" publish.title)}" \
      "${SUMMARY:-$(cfg "${CONFIG}" publish.summary)}" \
      "${TAKEAWAY:-$(cfg "${CONFIG}" publish.takeaway)}"
    ;;
  *)
    echo "unknown command ${cmd}" >&2; exit 1;;
esac
