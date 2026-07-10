#!/usr/bin/env bash
# Executable acceptance matrix for MAH-CONSOLIDATION-2026-07-09-v1.
#
# Run after every milestone. PASS requires every G01-G24 control to be proven;
# FAIL and PENDING both keep the command non-zero. Optional live checks are
# enabled with RUN_E2E=1. The script is deliberately red on the M0 baseline.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HUB="${ROOT}/targets/med-agent-hub"
CSAI="${ROOT}/targets/chartsearchai"
ESM="${ROOT}/targets/chartsearchai-esm"
QUERYSTORE="${ROOT}/targets/querystore"
CATALYST="${ROOT}/targets/catalyst"
CHATBOT="${ROOT}/targets/openmrs_chatbot"
ROADMAP="${ROOT}/specs/artifacts/planning/hub-consolidation-roadmap.md"
STATUS_DOC="${ROOT}/specs/artifacts/planning/hub-consolidation-roadmap-status.md"
HUB_VENV="${HUB_VENV:-${ROOT}/.gates-hub-venv}"
RUN_E2E="${RUN_E2E:-0}"

declare -A GATE_TITLES=()
declare -A GATE_STATUS=()
declare -A GATE_EVIDENCE=()

GATE_TITLES[G01]="Roadmap integrity"
GATE_TITLES[G02]="Baseline integrity"
GATE_TITLES[G03]="Upstream reconciliation"
GATE_TITLES[G04]="One engine"
GATE_TITLES[G05]="Profile correctness"
GATE_TITLES[G06]="Raw-leg compatibility"
GATE_TITLES[G07]="Source independence"
GATE_TITLES[G08]="Context budgeting"
GATE_TITLES[G09]="Context quality"
GATE_TITLES[G10]="Answer temporal safety"
GATE_TITLES[G11]="In-Depth temporal safety"
GATE_TITLES[G12]="Review ordering"
GATE_TITLES[G13]="Citation integrity"
GATE_TITLES[G14]="Drug-safety parity"
GATE_TITLES[G15]="Thin OpenMRS relay"
GATE_TITLES[G16]="Product discovery"
GATE_TITLES[G17]="Lifecycle UX"
GATE_TITLES[G18]="Multi-turn and cancellation"
GATE_TITLES[G19]="Local setup"
GATE_TITLES[G20]="Performance"
GATE_TITLES[G21]="Evaluation"
GATE_TITLES[G22]="Documentation"
GATE_TITLES[G23]="Independent QA"
GATE_TITLES[G24]="Release hygiene"

record() {
  GATE_STATUS["$1"]="$2"
  GATE_EVIDENCE["$1"]="$3"
}

has_pattern() {
  local pattern="$1"
  shift
  rg -q -U --no-heading -e "$pattern" "$@" 2>/dev/null
}

missing_pattern() {
  local pattern="$1"
  shift
  ! has_pattern "$pattern" "$@"
}

proof_file() {
  local gate="$1" path="$2"
  if [[ -s "$path" ]]; then
    record "$gate" "PASS" "proof: ${path#${ROOT}/}"
  else
    record "$gate" "PENDING" "missing proof: ${path#${ROOT}/}"
  fi
}

all_upstream_commits_classified() {
  local repo="$1" upstream_ref="$2" section_prefix="$3" sha short section_text
  git -C "$repo" rev-parse --verify --quiet "${upstream_ref}^{commit}" >/dev/null || return 1
  section_text="$(awk -v prefix="### ${section_prefix}" '
    index($0, prefix) == 1 { inside = 1; next }
    inside && /^### / { exit }
    inside { print }
  ' "$STATUS_DOC")"
  while read -r sha; do
    [[ -n "$sha" ]] || continue
    short="$(git -C "$repo" rev-parse --short=7 "$sha")"
    printf '%s\n' "$section_text" \
      | rg -q "^\\| \`${short}\` \\| (Keep|Port|Exclude) \\|" \
      || return 1
  done < <(git -C "$repo" rev-list --reverse "HEAD..${upstream_ref}")
}

# G01: immutable approved roadmap body.
expected_hash="$(sed -n 's/| Approved roadmap SHA-256 | `\([^`]*\)`.*/\1/p' "$STATUS_DOC")"
actual_hash="$(shasum -a 256 "$ROADMAP" | awk '{print $1}')"
if [[ -n "$expected_hash" && "$actual_hash" == "$expected_hash" ]]; then
  record G01 PASS "SHA-256 ${actual_hash}"
else
  record G01 FAIL "roadmap hash mismatch: expected=${expected_hash:-missing} actual=$actual_hash"
fi

# G02: local cleanliness and remote-reachable pins. CI state is recorded separately in M0 status.
baseline_ok=1
if [[ -n "$(git -C "$ROOT" status --porcelain --untracked-files=all)" ]] \
  || [[ -z "$(git -C "$ROOT" branch -r --contains HEAD 2>/dev/null)" ]]; then
  baseline_ok=0
fi
while read -r _key rel; do
  repo="${ROOT}/${rel}"
  sha="$(git -C "$repo" rev-parse HEAD)"
  if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=all)" ]] \
    || [[ -z "$(git -C "$repo" branch -r --contains "$sha" 2>/dev/null)" ]]; then
    baseline_ok=0
  fi
done < <(git -C "$ROOT" config --file .gitmodules --get-regexp 'submodule\..*\.path')
if [[ $baseline_ok -eq 1 ]] && has_pattern '\| G02 Baseline integrity \| Pass \|' "$STATUS_DOC"; then
  record G02 PASS "clean trees, reachable pins, and status-recorded green CI"
else
  record G02 FAIL "tree/pin/PR baseline is not yet fully green"
fi

# G03: every fetched upstream delta must have a final disposition in the status record.
if has_pattern '^## Upstream Disposition$' "$STATUS_DOC" \
  && has_pattern '^Disposition status: Complete$' "$STATUS_DOC" \
  && missing_pattern '\| Unclassified \|' "$STATUS_DOC" \
  && all_upstream_commits_classified "$ROOT" origin/main 'Harness (' \
  && all_upstream_commits_classified "$HUB" origin/main 'med-agent-hub (' \
  && all_upstream_commits_classified "$CSAI" upstream/main 'ChartSearchAI (' \
  && all_upstream_commits_classified "$ESM" upstream/main 'ChartSearchAI ESM (' \
  && all_upstream_commits_classified "$QUERYSTORE" upstream/main 'Querystore (' \
  && all_upstream_commits_classified "$CATALYST" origin/main 'Catalyst (' \
  && all_upstream_commits_classified "$CHATBOT" origin/main 'openmrs_chatbot ('; then
  record G03 PASS "upstream disposition table is complete"
else
  record G03 PENDING "upstream keep/port/exclude table incomplete"
fi

# G04/G05: final hub architecture and model resolution.
hub_m1_suite_ok=0
if [[ -x "${HUB_VENV}/bin/pytest" ]] \
  && (cd "$HUB" && "${HUB_VENV}/bin/python" -m pytest -q >/tmp/hub-m1-suite.log 2>&1); then
  hub_m1_suite_ok=1
fi

if missing_pattern '^async def run_team\(' "$HUB/server/team.py" \
  && missing_pattern '^async def run_team_stream\(' "$HUB/server/team.py" \
  && missing_pattern '\b(two_call|indepth_shared|indepth_only|answer_only|answer_review|solo)\b' "$HUB/server/levels_loader.py" \
  && [[ ! -f "$HUB/tests/profile_runner.py" ]] \
  && has_pattern 'class (StageEngine|ExecutionEngine)' "$HUB/server" \
  && has_pattern 'test_named_sse_resumes_all_events_in_one_task_context' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G04 PASS "one stage engine, no flag bridge, and full hub suite passed"
else
  record G04 FAIL "duplicate runtime paths or old topology flags remain"
fi

if missing_pattern '_passthrough_content' "$HUB/server/openai_compat.py" \
  && missing_pattern 'solo -> unused|unused, but a required field' "$HUB/server/levels.yaml" \
  && has_pattern 'model_not_found' "$HUB/server" \
  && has_pattern '(label|display_name)' "$HUB/server/levels.yaml" \
  && has_pattern 'final_resolve_refs.*run after review' "$HUB/server/levels_loader.py" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G05 PASS "profiles, invalid-order rejection, and unknown-id behavior passed"
else
  record G05 FAIL "passthrough, fake topology, or missing profile metadata remains"
fi

# G06: current low-level contract suite remains executable throughout the refactor.
if [[ -x "${HUB_VENV}/bin/pytest" ]] \
  && (cd "$HUB" && "${HUB_VENV}/bin/python" -m pytest tests/test_bridge.py tests/test_output_goldens.py -q >/tmp/hub-g06.log 2>&1); then
  record G06 PASS "hub bridge and byte-exact golden suites passed"
else
  record G06 FAIL "hub raw-leg/golden contract suite failed or test environment is missing"
fi

# G07-G09: context-source and exact-budget implementation/evidence.
if [[ -f "$HUB/server/context_sources.py" && -f "$HUB/tests/test_context_sources.py" ]] \
  && missing_pattern 'from \.querystore_client import QueryStoreClient' "$HUB/server/team.py" \
  && has_pattern 'test_supplemental_source_uses_the_same_normalized_ledger' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G07 PASS "source contracts, explicit failures, and provider independence passed"
else
  record G07 FAIL "context source registry/contract is not implemented"
fi

if has_pattern 'class TokenCounter' "$HUB/server" \
  && missing_pattern '(len\([^)]*\)\s*/\s*4|chars_per_token|character estimate)' "$HUB/server" \
  && [[ -f "$HUB/tests/test_context_budget.py" ]] \
  && has_pattern '/v1/chat/completions/input_tokens' "$HUB/server/context_sources.py" \
  && has_pattern 'test_actual_chat_request_overflow_is_rejected_before_backend_call' "$HUB/tests/test_context_budget.py" \
  && has_pattern 'test_product_envelope_requires_exact_budget_even_when_not_advertised' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]] \
  && "$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import configparser
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1])
router = configparser.ConfigParser()
router.read(root / "scripts/llama-router.ini")
router_window = int(router["*"]["ctx-size"])
levels = yaml.safe_load((root / "targets/med-agent-hub/server/levels.yaml").read_text())
product = [
    spec for spec in levels["profiles"].values()
    if spec.get("visibility") == "product"
]
assert product
assert all(spec["context"]["window"] == router_window for spec in product)
PY
then
  record G08 PASS "exact counter, budget tests, and router/profile windows agree"
else
  record G08 FAIL "exact context budgeting is not implemented"
fi

context_set="$ROOT/datasets/validation/comparison_sets/context-supply-dev.json"
context_proof="$ROOT/artifacts/roadmap/gates/G09-context-quality.json"
if [[ -f "$context_set" && -s "$context_proof" ]] \
  && "$ROOT/.venv/bin/python" - "$context_set" "$context_proof" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

comparison_path, proof_path = map(Path, sys.argv[1:])
root = comparison_path.parents[3]
proof = json.loads(proof_path.read_text(encoding="utf-8"))
current_hash = hashlib.sha256(comparison_path.read_bytes()).hexdigest()

hub_inputs = (
    root / "targets/med-agent-hub/server/context_sources.py",
    root / "targets/med-agent-hub/server/engine.py",
    root / "targets/med-agent-hub/server/levels_loader.py",
    root / "targets/med-agent-hub/server/levels.yaml",
    root / "targets/med-agent-hub/server/team.py",
    root / "targets/med-agent-hub/server/temporal.py",
)
digest = hashlib.sha256()
for path in sorted(hub_inputs):
    digest.update(str(path.relative_to(root)).encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
assert proof["schema_version"] == "context_quality_gate.v1"
assert proof["status"] == "pass"
assert proof["comparison_set_sha256"] == current_hash
assert proof["hub_code_sha256"] == digest.hexdigest()
assert proof["router_config_sha256"] == hashlib.sha256(
    (root / "scripts/llama-router.ini").read_bytes()
).hexdigest()
assert proof["required_source_recall"] == 1.0
assert proof["cases"] == len(proof["results"]) and proof["cases"] > 0
assert all(not row["missing_source_indices"] for row in proof["results"])
assert all(row["input_tokens"] <= row["input_limit"] for row in proof["results"])
PY
then
  record G09 PASS "current dev set has 100% required-source recall within exact budgets"
else
  record G09 PENDING "context quality proof is missing, stale, or failed"
fi

# G10-G12: deterministic temporal invariants and post-review ordering.
if has_pattern 'test_product_profiles.*temporal.*enforce|test_temporal.*cannot.*weaken' "$HUB/tests" \
  && has_pattern 'temporal_gate.*enforce' "$HUB/server/levels.yaml" \
  && has_pattern 'test_gate_rejects_malformed_and_nonledger_dates_when_ledger_is_empty' "$HUB/tests" \
  && has_pattern 'test_post_review_punctuation_rewrite_preserves_usable_answer' "$HUB/tests" \
  && has_pattern 'test_product_pipeline_fallback_records_enforced_temporal_gate' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G10 PASS "Answer substance, malformed-date, rewrite, and enforce tests passed"
else
  record G10 FAIL "product Answer temporal invariant is not proven"
fi

if has_pattern 'test_.*indepth.*temporal.*gate|test_.*temporal.*indepth' "$HUB/tests" \
  && has_pattern '(indepth_temporal_gate|gate_indepth_claims)' "$HUB/server" \
  && has_pattern 'test_empty_indepth_cannot_report_checked_or_complete' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G11 PASS "In-Depth per-claim, empty-output, and withholding tests passed"
else
  record G11 FAIL "In-Depth temporal gate is absent"
fi

if has_pattern 'index\("review"\).*index\("ground_verdicts"\)|review.*final_resolve_refs.*ground_verdicts' "$HUB/tests" \
  && has_pattern '_regate_after_rewrite' "$HUB/server/team.py" \
  && has_pattern 'test_final_reference_resolution_before_review_is_rejected' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G12 PASS "review re-gate and final resolution/grounding order tests passed"
else
  record G12 FAIL "final review/grounding order lacks executable proof"
fi

# G13/G14: current-patient citations and deterministic drug safety. The hub owns
# history fitting and source-ledger resolution; M2 adds a relay-level integration test.
if has_pattern 'citation.*prior.*turn|prior.*citation' "$HUB/tests" \
  && has_pattern 'current.*patient|current.*source.*ledger' "$HUB/tests" \
  && has_pattern 'test_indepth_unresolved_citation_is_not_displayed' "$HUB/tests" \
  && has_pattern 'test_indepth_citation_cannot_inherit_answer_verified_verdict' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G13 PASS "Answer/In-Depth current-ledger and prior-turn isolation tests passed"
else
  record G13 FAIL "citation replay/current-ledger invariant is not proven"
fi

if [[ -x "${HUB_VENV}/bin/pytest" ]] \
  && (cd "$HUB" && "${HUB_VENV}/bin/python" -m pytest tests/test_drug_safety.py tests/test_drug_safety_integration.py -q >/tmp/hub-g14.log 2>&1); then
  record G14 PASS "hub drug-safety parity/integration tests passed"
else
  record G14 FAIL "hub drug-safety tests failed"
fi

# G15-G17: thin relay, hub-owned discovery, and complete staged UX.
legacy_java='LocalLlmEngine|CitationGroundingVerifier|ModelSwitchService|LlmInferenceService|/warmup|value = "/search"|chartSnapshot|chartMappingsJson|progressive.*preview'
if missing_pattern "$legacy_java" "$CSAI/api/src/main" "$CSAI/omod/src/main" \
  && has_pattern 'hubRelay' "$CSAI/omod/src/main"; then
  record G15 PASS "Java is a thin hub relay"
else
  record G15 FAIL "legacy Java inference/discovery/orchestration remains"
fi

if missing_pattern 'LM Studio|parseLmStudio|loadModel' "$CSAI/api/src/main" "$ESM/src" \
  && has_pattern 'single-e4b-checked' "$HUB/server/levels.yaml" \
  && has_pattern '(default|is_default)' "$HUB/server/openai_compat.py"; then
  record G16 PASS "hub metadata owns picker and default"
else
  record G16 FAIL "LM Studio/client-curated discovery or missing default metadata remains"
fi

if has_pattern 'answerValidation' "$ESM/src" \
  && has_pattern 'inDepth.*validation|validation.*inDepth' "$ESM/src" \
  && has_pattern 'originalAnswer' "$ESM/src"; then
  record G17 PASS "Answer and In-Depth validation lifecycle is rendered"
else
  record G17 FAIL "complete staged lifecycle UX is not implemented"
fi

# G18: unit proof always required; live proof required for final PASS.
if [[ "$RUN_E2E" == "1" ]]; then
  if (cd "$ROOT/tests/e2e" && yarn playwright test chartsearchai-e4b-multiturn-trivial chartsearchai-preempt >/tmp/hub-g18.log 2>&1); then
    record G18 PASS "live multi-turn and preempt E2E passed"
  else
    record G18 FAIL "live multi-turn/preempt E2E failed"
  fi
else
  record G18 PENDING "rerun with RUN_E2E=1 for live proof"
fi

# G19-G21: portable local setup, latency, and evaluation evidence.
if has_pattern '^chartsearchai-local:' "$ROOT/Makefile" \
  && missing_pattern '/Users/[[:alnum:]_.-]+/' "$ROOT/scripts/llama-router.ini" \
  && missing_pattern 'LM_STUDIO|lmstudio' "$ROOT/.env.chartsearch.example"; then
  record G19 PASS "portable hub-only local entrypoint is present"
else
  record G19 FAIL "portable chartsearchai-local path is incomplete"
fi

proof_file G20 "$ROOT/artifacts/roadmap/gates/G20-performance.json"
proof_file G21 "$ROOT/artifacts/roadmap/gates/G21-evaluation.json"

# G22: active documentation alignment across root and every submodule.
if "$ROOT/scripts/verify-doc-drift.sh" >/tmp/hub-g22.log 2>&1; then
  record G22 PASS "verify-doc-drift.sh passed"
else
  record G22 FAIL "verify-doc-drift.sh failed"
fi

# G23: code-qa outputs are explicit release artifacts.
qa_dir="$ROOT/artifacts/roadmap/code-qa"
if [[ -s "$qa_dir/meaningful-test-coverage.md" \
  && -s "$qa_dir/simplicity-review.md" \
  && -s "$qa_dir/spec-code-alignment.md" \
  && -s "$qa_dir/cross-repo-companion-pr.md" \
  && -s "$qa_dir/evidence-bundle.md" ]]; then
  record G23 PASS "all required DIGI-UW/code-qa reports present"
else
  record G23 PENDING "one or more required code-qa reports are missing"
fi

# G24 is derived from G01-G23 plus final clean-tree state.
release_ready=1
for n in $(seq -w 1 23); do
  [[ "${GATE_STATUS[G${n}]:-PENDING}" == "PASS" ]] || release_ready=0
done
if [[ $release_ready -eq 1 ]] \
  && git -C "$ROOT" diff --quiet \
  && git -C "$ROOT" diff --cached --quiet; then
  record G24 PASS "G01-G23 pass and root tree is clean"
else
  record G24 PENDING "release prerequisites are not all green"
fi

printf 'Roadmap: MAH-CONSOLIDATION-2026-07-09-v1\n\n'
printf '%-4s  %-7s  %-32s  %s\n' Gate Status Requirement Evidence
printf '%-4s  %-7s  %-32s  %s\n' ---- ------- ----------- --------

overall=0
for n in $(seq -w 1 24); do
  gate="G${n}"
  status="${GATE_STATUS[$gate]:-PENDING}"
  printf '%-4s  %-7s  %-32s  %s\n' "$gate" "$status" "${GATE_TITLES[$gate]}" "${GATE_EVIDENCE[$gate]:-no evidence}"
  [[ "$status" == "PASS" ]] || overall=1
done

exit "$overall"
