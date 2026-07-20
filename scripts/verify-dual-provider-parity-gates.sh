#!/usr/bin/env bash
set -euo pipefail

# The dual-provider roadmap is an executable contract. This first gate keeps its
# authority and integrity verifiable while implementation gates are added red-first.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROADMAP="$ROOT/specs/artifacts/planning/openmrs-dual-provider-parity-roadmap.md"
STATUS="$ROOT/specs/artifacts/planning/openmrs-dual-provider-parity-roadmap-status.md"
OLD_ROADMAP="$ROOT/specs/artifacts/planning/hub-consolidation-roadmap.md"
OLD_STATUS="$ROOT/specs/artifacts/planning/hub-consolidation-roadmap-status.md"
INDEX="$ROOT/specs/artifacts/README.md"

failures=0

record() {
  local gate="$1"
  local status="$2"
  local detail="$3"
  printf '%-4s %-4s %s\n' "$gate" "$status" "$detail"
  [[ "$status" == "PASS" ]] || failures=$((failures + 1))
}

for path in "$ROADMAP" "$STATUS" "$OLD_ROADMAP" "$OLD_STATUS" "$INDEX"; do
  if [[ ! -f "$path" ]]; then
    record G01 FAIL "missing ${path#$ROOT/}"
  fi
done

if [[ -f "$ROADMAP" && -f "$STATUS" ]]; then
  expected_hash="$(sed -n 's/| Approved roadmap SHA-256 | `\([^`]*\)`.*/\1/p' "$STATUS")"
  actual_hash="$(shasum -a 256 "$ROADMAP" | awk '{print $1}')"
  if [[ -n "$expected_hash" && "$expected_hash" != "PENDING_INITIAL_HASH" && "$expected_hash" == "$actual_hash" ]]; then
    record G01 PASS "roadmap SHA-256 matches status record"
  else
    record G01 FAIL "roadmap SHA-256 is missing or mismatched"
  fi
fi

if rg -q 'Status: Historical and superseded by `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`' "$OLD_ROADMAP" \
  && rg -q 'Status: Historical and superseded by `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`' "$OLD_STATUS"; then
  record G01 PASS "prior roadmap and status are explicitly superseded"
else
  record G01 FAIL "prior roadmap supersession marker missing"
fi

if rg -q 'planning/openmrs-dual-provider-parity-roadmap.md' "$INDEX" \
  && rg -q 'planning/openmrs-dual-provider-parity-roadmap-status.md' "$INDEX"; then
  record G01 PASS "artifact index links canonical roadmap and status"
else
  record G01 FAIL "artifact index does not link canonical roadmap and status"
fi

if [[ -e "$ROOT/specs/artifacts/planning/openmrs-dual-runtime-pivot-audit-roadmap-2026-07-20.md" ]]; then
  record G01 FAIL "obsolete dual-runtime draft remains active"
else
  record G01 PASS "obsolete dual-runtime draft removed"
fi

if (( failures > 0 )); then
  exit 1
fi
