#!/usr/bin/env bash
# Lightweight guard for current Catalyst documentation.
#
# Product behavior belongs in the current authorities and executable tests.
# This script catches only inexpensive documentation failures: missing
# authorities, leaked infrastructure identifiers, malformed task markers,
# broken local links, discarded architecture terms, and loss of the central
# connection boundary. It intentionally does not freeze prose, counts, hashes,
# status ledgers, or historical artifacts.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

TASKS="${DOCS_TASKS_PATH:-specs/008-catalyst-query-workbench/tasks.md}"
PROGRAM="${DOCS_PROGRAM_PATH:-specs/catalyst-program-roadmap.md}"
EXECUTION="${DOCS_EXECUTION_PATH:-specs/catalyst-implementation-plan.md}"
FEATURE_SPEC="${DOCS_FEATURE_SPEC_PATH:-specs/008-catalyst-query-workbench/spec.md}"
FEATURE_PLAN="${DOCS_FEATURE_PLAN_PATH:-specs/008-catalyst-query-workbench/plan.md}"
QUICKSTART="${DOCS_QUICKSTART_PATH:-specs/008-catalyst-query-workbench/quickstart.md}"
WORKBENCH_API="${DOCS_WORKBENCH_API_PATH:-specs/008-catalyst-query-workbench/contracts/workbench-api.md}"
DASHBOARD_GOAL="${DOCS_DASHBOARD_GOAL_PATH:-specs/008-catalyst-query-workbench/dashboard-mvp-delivery-goal.md}"

CURRENT_DOCS=(
  README.md
  AGENTS.md
  "$PROGRAM"
  "$EXECUTION"
  "$FEATURE_SPEC"
  "$FEATURE_PLAN"
  "$TASKS"
  "$QUICKSTART"
  "$WORKBENCH_API"
  "$DASHBOARD_GOAL"
)

for file in "${CURRENT_DOCS[@]}"; do
  [ -f "$file" ] || err "missing current Catalyst document: $file"
done
if [ "$fail" -ne 0 ]; then
  exit 1
fi

if [ -n "${DOCS_SECRET_SCAN_PATH:-}" ]; then
  SECRET_PATHS=("${DOCS_SECRET_SCAN_PATH}")
else
  SECRET_PATHS=(
    README.md
    AGENTS.md
    .claude
    specs
    catalyst-sources
    landing
    targets/catalyst/README.md
    targets/catalyst/AGENTS.md
    targets/catalyst/docs
  )
fi
if grep -rIhnE '[0-9]{1,3}(\.[0-9]{1,3}){3}/32|sgr-[0-9a-f]{8,}' -- "${SECRET_PATHS[@]}"; then
  err "tracked documentation contains a concrete /32 address or security-group rule id"
fi

if grep -nE '^- \[x\]' "$TASKS"; then
  err "task checkboxes must use uppercase [X]"
fi

if [ "${DOCS_SKIP_LINK_CHECK:-0}" != "1" ]; then
  if [ -n "${DOCS_LINK_FILES:-}" ]; then
    IFS=':' read -r -a LINK_FILES <<<"${DOCS_LINK_FILES}"
    python3 scripts/verify-local-markdown-links.py "${LINK_FILES[@]}" || fail=1
  else
    python3 scripts/verify-local-markdown-links.py || fail=1
  fi
fi

program_text="$(tr '\n' ' ' < "$PROGRAM")"
feature_text="$(tr '\n' ' ' < "$FEATURE_SPEC")"
workbench_text="$(tr '\n' ' ' < "$WORKBENCH_API")"

grep -qi 'generic SQL' <<<"$program_text" \
  || err "program roadmap is missing the generic SQL boundary"
for phase in 'Phase 1' 'Phase 2' 'Phase 3'; do
  grep -q "$phase" <<<"$program_text" \
    || err "program roadmap is missing $phase"
done
grep -qiE 'explicit (SQL )?dialect' <<<"$feature_text" \
  || err "Feature 008 is missing the explicit dialect"
grep -qiE '(complete readable schema|every table.*view.*column)' <<<"$feature_text" \
  || err "Feature 008 is missing the complete readable schema"
grep -qi 'advisory' <<<"$feature_text" \
  || err "Feature 008 is missing advisory validation"
grep -qiE 'exact.{0,80}SQL|SQL.{0,80}exact' <<<"$feature_text" \
  || err "Feature 008 is missing exact selected-SQL execution"
grep -qi 'configured connection' <<<"$workbench_text" \
  || err "workbench API is missing the configured-connection boundary"
grep -qi 'advisory' <<<"$workbench_text" \
  || err "workbench API is missing advisory validation"

PRODUCT_DOCS=(
  README.md
  AGENTS.md
  "$PROGRAM"
  "$FEATURE_SPEC"
  "$FEATURE_PLAN"
  "$QUICKSTART"
  "$WORKBENCH_API"
  "$DASHBOARD_GOAL"
  landing/index.html
  targets/catalyst/README.md
  targets/catalyst/AGENTS.md
  targets/catalyst/docs/specification.md
  targets/catalyst/docs/dashboard-builder-mvp-design.md
  targets/catalyst/docs/contracts/dashboard-builder-api.md
  .claude
)
if grep -rIinE \
  'PostgresAnalyticsAdapter|Postgres(ReadOnly|Gold)[A-Za-z]*|approved (catalog|relation list|view list)|gold (query|execution)|fixed 13[- ](relation|table)' \
  "${PRODUCT_DOCS[@]}"; then
  err "a current product document restores discarded architecture"
fi
if [ "$fail" -ne 0 ]; then
  exit 1
fi
echo "docs consistency: OK"
