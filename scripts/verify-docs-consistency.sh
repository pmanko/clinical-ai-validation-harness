#!/usr/bin/env bash
# Planning-document consistency guard.
#
# The program roadmap, the Feature 008 milestone contract, and the historical
# remediation record each own different facts; this asserts the invariants
# that keep them agreeing. Every check here encodes an acceptance criterion
# from specs/artifacts/planning/catalyst-open-pr-remediation-roadmap-2026-08-23.md
# (R4), so drift fails a pull request instead of waiting for the next audit.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

TASKS="${DOCS_TASKS_PATH:-specs/008-catalyst-query-workbench/tasks.md}"
PROGRAM=specs/catalyst-program-roadmap.md
INVARIANT='WS1–WS7 remediation is closed; Feature 008 D1e/M4 remains in progress and is scheduled as P3.'

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
if grep -rIlnE '[Ss]elected next( product)? milestone|selected next' \
    "${STATUS_SOURCES[@]}" 2>/dev/null; then
  err "a live status source still calls Dashboard Builder the selected next milestone"
fi

# 5. The governing invariant sentence is present verbatim where it binds
#    (whitespace-normalized so ordinary line wrapping is not a violation).
for f in "$PROGRAM" specs/artifacts/planning/catalyst-open-pr-remediation-roadmap-2026-08-23.md; do
  tr -s '[:space:]>' ' ' < "$f" | grep -qF "$INVARIANT" \
    || err "invariant sentence missing from $f"
done

if [ "$fail" -ne 0 ]; then
  exit 1
fi
echo "docs consistency: OK"
