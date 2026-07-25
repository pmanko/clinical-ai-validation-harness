#!/usr/bin/env bash
set -euo pipefail

# The dual-provider roadmap is an executable contract. Foundation mode validates
# prerequisites for Signoff 1; full mode intentionally fails until every acceptance
# gate is implemented by its owning repository.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROADMAP="$ROOT/specs/artifacts/planning/openmrs-dual-provider-parity-roadmap.md"
STATUS="$ROOT/specs/artifacts/planning/openmrs-dual-provider-parity-roadmap-status.md"
OLD_ROADMAP="$ROOT/specs/artifacts/planning/hub-consolidation-roadmap.md"
OLD_STATUS="$ROOT/specs/artifacts/planning/hub-consolidation-roadmap-status.md"
INDEX="$ROOT/specs/artifacts/README.md"
INVENTORY="$ROOT/specs/artifacts/planning/openmrs-dual-provider-upstream-inventory.md"
CONTRACT="$ROOT/specs/artifacts/planning/openmrs-dual-provider-conformance-contract.md"
FIXTURES="$ROOT/datasets/validation/conformance/dual-provider-conformance.v1.json"

phase="foundation"
if [[ $# -gt 0 ]]; then
  case "$1" in
    --phase)
      phase="${2:-}"
      shift 2
      ;;
    --phase=*)
      phase="${1#--phase=}"
      shift
      ;;
  esac
fi
if [[ $# -gt 0 || "$phase" != "foundation" && "$phase" != "full" ]]; then
  printf 'Usage: %s [--phase foundation|full]\n' "${0##*/}" >&2
  exit 2
fi

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

for number in $(seq -w 1 22); do
  if ! rg -q "\\| G${number} " "$STATUS"; then
    record G01 FAIL "status is missing G${number}"
  fi
done

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

if [[ "$phase" == "foundation" ]]; then
  repos=(
    "$ROOT"
    "$ROOT/targets/chartsearchai"
    "$ROOT/targets/chartsearchai-esm"
    "$ROOT/targets/med-agent-hub"
    "$ROOT/targets/querystore"
    "$ROOT/targets/catalyst"
    "$ROOT/targets/openmrs_chatbot"
  )
  for repo in "${repos[@]}"; do
    label="${repo#$ROOT/}"
    [[ "$label" == "$repo" ]] && label="harness"
    if [[ ! -d "$repo/.git" && ! -f "$repo/.git" ]]; then
      record G02 FAIL "${label} is not an initialized Git worktree"
    elif [[ -n "$(git -C "$repo" status --porcelain)" ]]; then
      record G02 FAIL "${label} worktree is not clean"
    else
      record G02 PASS "${label} worktree is clean"
    fi
    if git -C "$repo" branch -r --contains HEAD | rg -q 'origin/'; then
      record G02 PASS "${label} HEAD is remote-reachable"
    else
      record G02 FAIL "${label} HEAD is not contained by an origin branch"
    fi
  done

  if git -C "$ROOT/targets/chartsearchai" show-ref --verify --quiet \
      refs/heads/codex/backup/chartsearchai-pr-26-20260720; then
    record G02 PASS "ChartSearchAI PR #26 rollback ref exists"
  else
    record G02 FAIL "ChartSearchAI PR #26 rollback ref missing"
  fi
  if git -C "$ROOT/targets/chartsearchai-esm" show-ref --verify --quiet \
      refs/heads/codex/backup/chartsearchai-esm-pr-12-20260720; then
    record G02 PASS "ChartSearchAI ESM PR #12 rollback ref exists"
  else
    record G02 FAIL "ChartSearchAI ESM PR #12 rollback ref missing"
  fi

  if [[ -f "$INVENTORY" ]] && rg -q 'Upstream commit' "$INVENTORY" \
      && rg -q 'Current ChartSearchAI PR #26 Replay Inventory' "$INVENTORY"; then
    record G02 PASS "upstream and replay dispositions are recorded"
  else
    record G02 FAIL "upstream/replay disposition inventory missing or incomplete"
  fi

  if [[ -f "$CONTRACT" && -f "$FIXTURES" ]] \
      && rg -q 'Red-First Test Procedure' "$CONTRACT" \
      && rg -q '"schema_version": "dual_provider_conformance.v1"' "$FIXTURES"; then
    record G03 PASS "versioned conformance contract and fixture manifest are ready for red-first adapters"
  else
    record G03 FAIL "conformance contract or versioned fixtures missing"
  fi
fi

if [[ "$phase" == "full" ]]; then
  record G03 FAIL "full cross-repository conformance adapters are not implemented yet"
  for number in $(seq -w 4 22); do
    record "G${number}" FAIL "acceptance gate has not been implemented yet"
  done
fi

if (( failures > 0 )); then
  exit 1
fi
