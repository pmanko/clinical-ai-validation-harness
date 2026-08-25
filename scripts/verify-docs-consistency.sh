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

# 6. Phase 1 qualification uses one measurement per cell in each complete
#    suite run. Repetition is three whole runs, optionally extended as a whole
#    to five. The earlier per-cell schedule must not return in any active or
#    explanatory source.
for f in "$PROGRAM" "$QUALIFICATION" "$BRIEF" "$WRITER_ARTIFACT"; do
  [ -f "$f" ] || { err "missing Phase 1 planning source: $f"; continue; }
done
grep -qF 'repetitions: 1' "$PROGRAM" \
  || err "program roadmap does not lock suite repetitions to one"
grep -qF 'three complete runs' "$PROGRAM" \
  || err "program roadmap does not start with three complete runs"
grep -qF 'three fresh complete suite runs' "$QUALIFICATION" \
  || err "qualification roadmap does not require three fresh complete runs"
grep -qE '"repetitions"[[:space:]]*:[[:space:]]*1' "$PHASE1_SUITE" \
  || err "Phase 1 suite repetitions must remain one"
if grep -IinE \
  'start with three repetitions for every|start with three per (model|profile)/scenario pair|extend a pair to five|three-to-five adaptive repetitions|adaptive three-to-five scheduling' \
  "$PROGRAM" "$QUALIFICATION" "$BRIEF" "$WRITER_ARTIFACT"; then
  err "obsolete per-cell Phase 1 repetition rule is present"
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
grep -qF 'Catalog v7 records the corrected 13-relation decision' "$WRITER_ARTIFACT" \
  || err "writer artifact still assigns the corrected surface to catalog v6"
if grep -IinE 'resume continues the same run ID|rewrite(s|ten)? the interrupted run' \
  "$PROGRAM" "$QUALIFICATION"; then
  err "stale same-run recovery rule is present"
fi

# 8. The owner-approved adjudication boundaries remain explicit.
qualification_text="$(tr -s '[:space:]' ' ' < "$QUALIFICATION")"
for phrase in \
  'All three M1 ready answers are scored' \
  'query digest different from both CD4 turns and reuses no CD4/observation relation, predicate, or projection' \
  'unknown status, or an unlisted warning fails' \
  'If no team qualifies, record `none`' \
  'terminal outcome or answer correctness varies across the first three runs' \
  'leaving out any one run changes whether a team passes any qualification gate' \
  'differ by no more than one complete-scenario success among their 36 measurements' \
  'permanently excluded from composition' \
  'regardless of whether the model answer passed or failed' \
  "third infrastructure failure invalidates that team's constituent run" \
  'one excluded, recorded, unscored warm-up must run in a fresh session before each profile in every complete suite run' \
  'copy the exact v6 overlay and generated catalog to new paths whose filenames identify v6'; do
  grep -qF "$phrase" <<<"$qualification_text" \
    || err "approved Phase 1 adjudication rule missing: $phrase"
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
