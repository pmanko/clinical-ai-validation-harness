#!/usr/bin/env bash
# Planning-document consistency guard.
#
# This guard protects a small set of durable boundaries shared by the program
# roadmap, the Phase 1 execution plan, and Feature 008. It deliberately does
# not mirror current commits, pull requests, test totals, collection counts,
# reviewer choices, or operational history; Git, tests, continuous integration,
# and the generated report own those facts.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

TASKS="${DOCS_TASKS_PATH:-specs/008-catalyst-query-workbench/tasks.md}"
PROGRAM="${DOCS_PROGRAM_PATH:-specs/catalyst-program-roadmap.md}"
EXECUTION="${DOCS_EXECUTION_PATH:-${DOCS_QUALIFICATION_PATH:-specs/catalyst-phase1-qualification-remediation-roadmap.md}}"
BRIEF="${DOCS_BRIEF_PATH:-specs/artifacts/planning/phase-1-planning-discussion-brief.md}"
WRITER_ARTIFACT="${DOCS_WRITER_ARTIFACT_PATH:-specs/artifacts/planning/what-the-writer-sees.html}"
FEATURE_SPEC="${DOCS_FEATURE_SPEC_PATH:-specs/008-catalyst-query-workbench/spec.md}"
WORKBENCH_API="${DOCS_WORKBENCH_API_PATH:-specs/008-catalyst-query-workbench/contracts/workbench-api.md}"
PHASE1_SUITE="${DOCS_PHASE1_SUITE_PATH:-datasets/validation/catalyst/catalyst-phase1-comparison-v1.json}"
CATALOG_V6_OVERLAY="${DOCS_CATALOG_V6_OVERLAY_PATH:-catalyst-sources/openmrs-hiv/catalog-overlay.json}"
CATALOG_V6_GENERATED="${DOCS_CATALOG_V6_GENERATED_PATH:-catalyst-sources/openmrs-hiv/catalog/openmrs-hiv-catalog.json}"
INVARIANT='WS1–WS7 remediation is closed; Feature 008 D1e/M4 remains in progress and is scheduled as P3.'
PHASE1_SUITE_V1_SHA256='2ce2356a22ed336d48eb3f45cb414e20735aeade2317ae68ea06a86d53e251ac'
CATALOG_V6_OVERLAY_SHA256='52e43e8d067fa9e9716acd4afbc7943c94dc39398664c9ab25eb96704fdf053a'
CATALOG_V6_GENERATED_SHA256='43b00b636acea183ef6e70caefab3cd702ccc6cc4a2e2657915b4483aad0d1df'

sha256_path() {
  local path="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  else
    return 127
  fi
}

assert_sha256() {
  local path="$1"
  local expected="$2"
  local label="$3"
  local actual
  if [ ! -f "$path" ]; then
    err "missing immutable ${label}: ${path}"
    return
  fi
  actual="$(sha256_path "$path")" || {
    err "unable to hash immutable ${label}: ${path}"
    return
  }
  [ "$actual" = "$expected" ] \
    || err "immutable ${label} bytes changed; create the approved successor version instead"
}

# 1. No workstation address or security-group rule id in tracked specs.
if grep -rInE '[0-9]{1,3}(\.[0-9]{1,3}){3}/32|sgr-[0-9a-f]{8,}' specs/; then
  err "concrete /32 address or sgr-* rule id in tracked specs"
fi

# 2. Task checkboxes use the uppercase marker.
if grep -n '^- \[x\]' "$TASKS"; then
  err "lowercase [x] task marker in $TASKS"
fi

# 3. Phase 10 carries the exact 15 active gates plus the two consolidated
#    historical ceremonies T144/T149.
phase10_block="$(
  awk '
    /^## Phase 10([[:space:]]|$)/ { in_phase = 1 }
    in_phase && /^## / && $0 !~ /^## Phase 10([[:space:]]|$)/ { exit }
    in_phase { print }
  ' "$TASKS"
)"
unchecked="$(grep -cE '^- \[ \]' <<<"${phase10_block}" || true)"
[ "$unchecked" -eq 17 ] || err "Phase 10 unchecked entries: $unchecked (expected 17)"
active_gates=(
  T166 T147 T168 T169 T170 T171 T148 T172 T173
  T180 T181 T182 T155 T156 T157
)
for gate in "${active_gates[@]}"; do
  grep -qE "^- \[ \] ${gate}[[:space:]]" <<<"${phase10_block}" \
    || err "active Phase 10 gate missing or checked: ${gate}"
done
for ceremony in T144 T149; do
  grep -qE "^- \[ \] ${ceremony}[[:space:]].*Consolidated" \
    <<<"${phase10_block}" \
    || err "historical consolidated ceremony is not recorded correctly: ${ceremony}"
done

# 4. No live status source still names Dashboard Builder the selected next
#    milestone; that sequencing now lives in the program roadmap.
STATUS_SOURCES=(
  README.md AGENTS.md "$PROGRAM"
  specs/008-catalyst-query-workbench/plan.md "$TASKS"
  specs/artifacts/planning/catalyst-product-roadmap-status.md
  specs/artifacts/planning/catalyst-validation-integration-roadmap-status.md
)
if [ -n "${DOCS_STATUS_EXTRA_PATH:-}" ]; then
  STATUS_SOURCES+=("${DOCS_STATUS_EXTRA_PATH}")
fi
status_matches=""
if status_matches="$(
  grep -IlnE '[Ss]elected next( product)? milestone|selected next' \
    "${STATUS_SOURCES[@]}"
)"; then
  printf '%s\n' "${status_matches}"
  err "a live status source still calls Dashboard Builder the selected next milestone"
else
  status_check=$?
  if [ "${status_check}" -ne 1 ]; then
    err "unable to inspect every live status source"
  fi
fi

# 5. The governing invariant sentence is present verbatim where it binds
#    (whitespace-normalized so ordinary line wrapping is not a violation).
for f in "$PROGRAM" specs/artifacts/planning/catalyst-open-pr-remediation-roadmap-2026-08-23.md; do
  tr -s '[:space:]>' ' ' < "$f" | grep -qF "$INVARIANT" \
    || err "invariant sentence missing from $f"
done

# 6. Required planning and contract sources exist.
for f in "$PROGRAM" "$EXECUTION" "$BRIEF" "$WRITER_ARTIFACT" \
  "$FEATURE_SPEC" "$WORKBENCH_API"; do
  [ -f "$f" ] || { err "missing Phase 1 planning source: $f"; continue; }
done
# 7. Published catalog v6 and suite v1 are immutable. Corrected work uses new
#    version identities rather than relabelling historical evidence.
assert_sha256 "$PHASE1_SUITE" "$PHASE1_SUITE_V1_SHA256" "Phase 1 suite v1"
assert_sha256 "$CATALOG_V6_OVERLAY" "$CATALOG_V6_OVERLAY_SHA256" "catalog v6 overlay"
assert_sha256 "$CATALOG_V6_GENERATED" "$CATALOG_V6_GENERATED_SHA256" "catalog v6 generated file"
for f in "$PROGRAM" "$EXECUTION"; do
  grep -qF 'catalog v7' "$f" || err "catalog v7 successor missing from $f"
  grep -qF 'suite v2' "$f" || err "suite v2 successor missing from $f"
  grep -qF 'catalog v6' "$f" || err "catalog v6 history missing from $f"
  grep -qF 'suite v1' "$f" || err "suite v1 history missing from $f"
done

# 8. The active roadmaps retain one authority and the current section shape.
#    The guard rejects the superseded rules that caused the earlier conflict,
#    but does not copy the roadmaps' prose or operational status.
grep -qF 'specs/catalyst-phase1-qualification-remediation-roadmap.md' "$PROGRAM" \
  || err "program roadmap does not link the active execution plan"
grep -qF '## Phase 1 comparison and reader review' "$PROGRAM" \
  || err "program roadmap is missing reader-led comparison"
grep -qF '### 3. Session context and the open guidance question' "$PROGRAM" \
  || err "program roadmap is missing the open guidance question"
grep -qF '### R4 — Context-rich report and manual rubric review' "$EXECUTION" \
  || err "execution plan is missing manual full-context review"
grep -qF '### R6 — Honest context evidence and guidance research seam' "$EXECUTION" \
  || err "execution plan is missing guidance research"

if grep -IinE \
  'owner records a selected team|decision selects one team|record .none. or .inconclusive.|Deploy the selected team|selected-team deployment|planned run count|planned number of complete|composer pin|pin-from-failure' \
  "$PROGRAM" "$EXECUTION"; then
  err "an active roadmap restores a superseded Phase 1 rule"
fi

feature_spec_text="$(tr -s '[:space:]' ' ' < "$FEATURE_SPEC")"
workbench_api_text="$(tr -s '[:space:]' ' ' < "$WORKBENCH_API")"
grep -qF 'include every relation the configured read-only database role can read' \
  <<<"$feature_spec_text" \
  || err "Feature 008 does not require the complete role-readable catalog"
grep -qF 'Users MUST be able to run the exact displayed draft regardless of its validator status' \
  <<<"$feature_spec_text" \
  || err "Feature 008 does not preserve advisory exact-SQL execution"
grep -qF 'validator findings MUST NOT disable the Run action' \
  <<<"$feature_spec_text" \
  || err "Feature 008 allows validator findings to disable manual Run"
grep -qF 'Database authentication, permissions, and transaction behavior MUST be authoritative' \
  <<<"$feature_spec_text" \
  || err "Feature 008 does not preserve the database execution boundary"
grep -qF 'Workbench validation is advisory' <<<"$workbench_api_text" \
  || err "workbench API does not preserve advisory validation"
grep -qF 'submits its exact SQL and typed parameters' <<<"$workbench_api_text" \
  || err "workbench API does not preserve exact-SQL execution"

if [ "$fail" -ne 0 ]; then
  exit 1
fi
echo "docs consistency: OK"
