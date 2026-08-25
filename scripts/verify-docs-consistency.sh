#!/usr/bin/env bash
# Planning-document consistency guard.
#
# The program roadmap, the Feature 008 milestone contract, and the historical
# remediation record each own different facts; this asserts the invariants
# that keep them agreeing. Every check here encodes an acceptance criterion
# from the open-PR closeout roadmap and the active Phase 1 qualification
# remediation roadmap, so drift fails a pull request instead of waiting for
# the next audit.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

TASKS="${DOCS_TASKS_PATH:-specs/008-catalyst-query-workbench/tasks.md}"
PROGRAM="${DOCS_PROGRAM_PATH:-specs/catalyst-program-roadmap.md}"
QUALIFICATION="${DOCS_QUALIFICATION_PATH:-specs/catalyst-phase1-qualification-remediation-roadmap.md}"
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

# 6. Phase 1 uses one measurement per cell in each complete suite run.
#    Repetition means predeclared whole-suite reruns, never selectively
#    repeating a cell after seeing its quality.
for f in "$PROGRAM" "$QUALIFICATION" "$BRIEF" "$WRITER_ARTIFACT" \
  "$FEATURE_SPEC" "$WORKBENCH_API"; do
  [ -f "$f" ] || { err "missing Phase 1 planning source: $f"; continue; }
done
grep -qF 'repetitions: 1' "$PROGRAM" \
  || err "program roadmap does not lock suite repetitions to one"
tr -s '[:space:]' ' ' < "$PROGRAM" \
  | grep -qF 'Repeated measurement means rerunning that whole frozen suite' \
  || err "program roadmap does not define repetition as a whole-suite rerun"
grep -qF 'planned number of complete suite runs' "$QUALIFICATION" \
  || err "qualification roadmap does not predeclare its complete-run count"
if ! python3 - "$PHASE1_SUITE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    repetitions = json.load(source).get("repetitions")
if type(repetitions) is not int or repetitions != 1:
    raise SystemExit(1)
PY
then
  err "Phase 1 suite repetitions must remain one"
fi
# 7. Published catalog v6 and suite v1 are immutable. These hashes lock the
#    current v6 files until R5 copies their exact bytes to versioned archive
#    paths and retargets the same checks before activating v7. Qualification
#    repairs use catalog v7 and suite v2, and interrupted evidence uses a new
#    linked replacement run rather than rewriting the original.
assert_sha256 "$PHASE1_SUITE" "$PHASE1_SUITE_V1_SHA256" "Phase 1 suite v1"
assert_sha256 "$CATALOG_V6_OVERLAY" "$CATALOG_V6_OVERLAY_SHA256" "catalog v6 overlay"
assert_sha256 "$CATALOG_V6_GENERATED" "$CATALOG_V6_GENERATED_SHA256" "catalog v6 generated file"
for f in "$PROGRAM" "$QUALIFICATION"; do
  grep -qF 'catalog v7' "$f" || err "catalog v7 successor missing from $f"
  grep -qF 'suite v2' "$f" || err "suite v2 successor missing from $f"
  grep -qF 'catalog v6' "$f" || err "catalog v6 history missing from $f"
  grep -qF 'suite v1' "$f" || err "suite v1 history missing from $f"
  grep -qF 'resumedFrom' "$f" || err "replacement-run lineage missing from $f"
done
for f in "$PROGRAM" "$QUALIFICATION" "$BRIEF" "$WRITER_ARTIFACT"; do
  normalized_surface_text="$(tr -s '[:space:]' ' ' < "$f")"
  grep -qF 'every relation the configured read-only database role can read' \
    <<<"$normalized_surface_text" \
    || err "shared role-readable catalog decision missing from $f"
done

# Read only current sections. Historical evidence and the append-only log may
# accurately quote an older decision without making it current again.
program_live_text="$(
  awk '
    /^## Phase 1 product and evaluation decisions/ { live = 1 }
    /^## Phase 1 comparison — development first pass/ { live = 0 }
    live { print }
  ' "$PROGRAM"
)"
program_decision_text="$(
  awk '
    /^### Decision summary/ { live = 1 }
    /^### 1[.] / { live = 0 }
    live { print }
  ' "$PROGRAM"
)"
qualification_live_text="$(
  awk '
    /^## Execution rules inherited from the program roadmap/ { live = 1 }
    /^## Append-only status log/ { live = 0 }
    live { print }
  ' "$QUALIFICATION"
)"
program_normalized="$(tr -s '[:space:]' ' ' <<<"$program_decision_text")"
qualification_normalized="$(tr -s '[:space:]' ' ' <<<"$qualification_live_text")"
for phrase in \
  'every relation the configured read-only database role can read' \
  'Relation counts are environment snapshots' \
  'metadata cannot hide a readable relation' \
  'does not by itself stop ordinary startup' \
  'the application adds no blanket query bans' \
  'The exact selected SQL reaches PostgreSQL' \
  'bounded by the configured read-only account, read-only transaction, timeout, and result limit' \
  'wrong query, database diagnostic, or wrong answer is a model-quality result' \
  'do not have to match' \
  'planned run count and decision method are recorded before live work' \
  'no universal pass percentage, automatic disqualifier, or fixed tie-break' \
  'no fixed retry or failure allowance' \
  'no fixed count, physical order, or ranking formula' \
  'not rejected merely for sharing a relation or SQL form' \
  'not on every ordinary pull request' \
  'not Phase 1 product blockers'; do
  grep -qF "$phrase" <<<"$program_normalized" \
    || err "current program outcome missing: $phrase"
done
for phrase in \
  'A wrong query is a model-quality result, not an invalid measurement' \
  'local and demo identities are recorded separately' \
  'before the live comparison'; do
  grep -qF "$phrase" <<<"$qualification_normalized" \
    || err "current qualification outcome missing: $phrase"
done

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

grep -qF "removed the brief's fixed run count" "$BRIEF" \
  || err "historical planning brief lacks the owner-correction banner"
grep -qF 'run counts, pass percentages, retry budgets, and context caps are not locked here' \
  "$WRITER_ARTIFACT" \
  || err "writer artifact lacks the owner-correction banner"
if grep -IinE 'resume continues the same run ID|rewrite(s|ten)? the interrupted run' \
  <<<"${program_live_text}
${qualification_live_text}"; then
  err "stale same-run recovery rule is present"
fi

# 8. The still-current adjudication outcomes remain explicit.
for phrase in \
  'All three M1 ready answers are scored' \
  'carry no irrelevant CD4-specific assumptions into the visit answer' \
  'Validation is advisory' \
  'record `none` or `inconclusive`' \
  'planned number of complete suite runs' \
  'permanently excluded from composition' \
  'regardless of whether the model answer passed or failed' \
  'does not count as another repetition'; do
  grep -qF "$phrase" <<<"$qualification_normalized" \
    || err "current Phase 1 evidence rule missing: $phrase"
done

# 9. The program roadmap owns product decisions and delegates only execution
#    tracking to the new remediation roadmap.
grep -qF 'specs/catalyst-phase1-qualification-remediation-roadmap.md' "$PROGRAM" \
  || err "program roadmap does not link the active qualification roadmap"
tr -s '[:space:]' ' ' < "$PROGRAM" | grep -qF 'not yet qualified or deployed' \
  || err "program roadmap has stale Phase 1 implementation status"
catalyst_pin="$(git ls-tree HEAD targets/catalyst | awk '{print $3}')"
hub_pin="$(git ls-tree HEAD targets/med-agent-hub | awk '{print $3}')"
[ -n "$catalyst_pin" ] || err "unable to resolve the pinned Catalyst revision"
[ -n "$hub_pin" ] || err "unable to resolve the pinned Hub revision"
grep -qF "$catalyst_pin" "$PROGRAM" \
  || err "program roadmap does not name the pinned Catalyst revision"
grep -qF "$hub_pin" "$PROGRAM" \
  || err "program roadmap does not name the pinned Hub revision"

if [ "$fail" -ne 0 ]; then
  exit 1
fi
echo "docs consistency: OK"
