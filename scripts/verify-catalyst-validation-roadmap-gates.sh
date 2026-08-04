#!/usr/bin/env bash
# Execute and record Catalyst Validation Integration (CVR) roadmap gates.
# Usage:
#   scripts/verify-catalyst-validation-roadmap-gates.sh test
#   scripts/verify-catalyst-validation-roadmap-gates.sh g00|g01|...|g15|blocked
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

STATUS="${ROOT}/specs/artifacts/planning/catalyst-validation-integration-roadmap-status.md"
BASE_BRANCH="$(awk -F'|' '/Diff-cover base branch/{gsub(/`| /, "", $3); print $3}' "${STATUS}" | head -1)"
BASE_BRANCH="${BASE_BRANCH:-origin/main}"
# Strip parenthetical fallback notes if present.
BASE_BRANCH="${BASE_BRANCH%%(*}"
BASE_BRANCH="${BASE_BRANCH%% }"

record() {
  local gate="$1" result="$2" note="$3"
  printf 'CVR-%s %s — %s\n' "${gate}" "${result}" "${note}"
}

cmd="${1:-test}"

run_test_suite() {
  uv run pytest -m 'not slow' --ignore=targets \
    --cov=harness --cov=scripts --cov-report=xml --cov-report=term-missing
  uv run diff-cover coverage.xml \
    --compare-branch "${BASE_BRANCH}" \
    --fail-under 90
}

case "${cmd}" in
  test|g03)
    run_test_suite
    record G03 PASS "pytest + diff-cover >=90 against ${BASE_BRANCH}"
    ;;
  g00)
    test -f specs/artifacts/planning/catalyst-validation-integration-roadmap.md
    test -f specs/artifacts/planning/catalyst-validation-integration-roadmap-status.md
    rg -q 'catalyst-validation-integration-roadmap.md' specs/artifacts/README.md
    rg -q 'catalyst-validation-integration-roadmap-status.md' specs/artifacts/README.md
    record G00 PASS "roadmap, status, and README links present"
    ;;
  g01)
    test -f evals/fixtures/validate-run-golden/provenance.json
    test -f evals/fixtures/catalyst-notebook-golden/provenance.json
    uv run pytest evals/catalyst/test_notebook_fixture.py evals/validate/test_report_golden.py -q
    record G01 PASS "fixtures + provenance tests"
    ;;
  g02)
    uv run pytest evals/common/ -q
    record G02 PASS "shared utility semantics"
    ;;
  g04)
    uv run pytest evals/validate/test_report_golden.py -q
    record G04 PASS "byte-identical ChartSearchAI golden report"
    ;;
  g05)
    uv run pytest evals/report_shell/ -q
    record G05 PASS "report_shell ownership + imports"
    ;;
  g06)
    uv run pytest \
      evals/validate/test_report_golden.py \
      evals/validate/test_dom_canon.py \
      evals/scripts/test_validate_dashboard_theme.py \
      evals/scripts/test_build_reports_index.py \
      evals/report_shell/ -q
    record G06 PASS "semantic parity + theme consumer markers"
    ;;
  g07)
    record G07 PENDING "requires MS-A user signoff after G03/G05/G06 green"
    exit 1
    ;;
  g08)
    test -f specs/008-catalyst-query-workbench/pccp/2026-07-21-catalyst-judge-v1.md
    test -f specs/008-catalyst-query-workbench/contracts/catalyst-judge-v1.schema.json
    test -f specs/008-catalyst-query-workbench/contracts/catalyst-judge-manifest-v1.schema.json
    test -f .claude/skills/catalyst-sql-scoring/SKILL.md
    uv run pytest evals/catalyst/test_judge_schema.py evals/catalyst/test_reconcile.py -q
    record G08 PASS "PCCP + schemas + skill + reconcile/schema tests"
    ;;
  g09)
    uv run pytest evals/catalyst/test_reconcile.py evals/catalyst/test_judge_finalize.py -q
    record G09 PASS "finalization + gold precedence"
    ;;
  g10)
    test -f evals/fixtures/catalyst-notebook-golden/judge.jsonl
    test -f evals/fixtures/catalyst-notebook-golden/judge_manifest.json
    test -f evals/fixtures/catalyst-notebook-golden/judge.pass-1.jsonl
    uv run pytest evals/catalyst/test_judge_finalize.py evals/catalyst/test_judge_schema.py -q
    record G10 PENDING "fixture judge evidence green; MS-B user signoff required"
    exit 1
    ;;
  g11)
    uv run pytest evals/catalyst/test_report.py -q
    record G11 PASS "offline catalyst report (socket blocked)"
    ;;
  g12)
    uv run pytest evals/catalyst/test_report.py evals/catalyst/test_report_no_judge.py -q
    record G12 PENDING "import boundary + no-judge green; MS-C user signoff required"
    exit 1
    ;;
  g13)
    uv run pytest \
      evals/metadata/test_metadata_events.py \
      evals/catalyst/test_notebook_events.py \
      evals/catalyst/test_judge_finalize.py \
      tests/test_catalyst_notebook_validation.py -q
    record G13 PASS "versioned notebook manifest/events + judge provenance"
    ;;
  g14)
    uv run pytest \
      evals/orchestration/test_cli_subcommands.py \
      tests/test_catalyst_notebook_validation.py \
      -k 'notebook_cli or catalyst_run or catalyst_report' -q
    record G14 PASS "Catalyst run/report CLI + compatibility wrapper"
    ;;
  g15)
    uv run pytest \
      evals/scripts/test_build_reports_index.py \
      evals/scripts/test_publish_report.py -q
    record G15 PASS "mixed-family dry-run publishing and index"
    ;;
  blocked)
    # Amendment A1 (2026-07-21): P4 and P5 both entry-gate on recorded
    # T094/T095/T111 user acceptance; 008-G5/008-G6 no longer gate CVR phases.
    if rg -q 'T094.*\| PASS' "${STATUS}" \
      && rg -q 'T095.*\| PASS' "${STATUS}" \
      && rg -q 'T111.*\| PASS' "${STATUS}"
    then
      record G13-G15 READY "T094/T095/T111 recorded PASS — P4 may start (A1)"
      record G16-G18 READY "T094/T095/T111 recorded PASS — P5 may start (A1)"
    else
      record G13-G15 BLOCKED "T094/T095/T111 not accepted (A1)"
      record G16-G18 BLOCKED "T094/T095/T111 not accepted (A1)"
    fi
    ;;
  *)
    echo "usage: $0 test|g00|g01|g02|g03|g04|g05|g06|g07|g08|g09|g10|g11|g12|g13|g14|g15|blocked" >&2
    exit 2
    ;;
esac
