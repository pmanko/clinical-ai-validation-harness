#!/usr/bin/env bash
# Executable acceptance matrix for MAH-CONSOLIDATION-2026-07-09-v1.
#
# Run after every milestone. PASS requires every applicable G01-G24 control to
# be proven. G20 may be DEFERRED only when the approved status artifact says so;
# FAIL and PENDING keep the command non-zero. Optional live checks are enabled
# with RUN_E2E=1. The script is deliberately red on the M0 baseline.

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
	local repo="$1" upstream_ref="$2" base_ref="$3" classified_ref="$4" label="$5" section_prefix="$6"
	local sha short section_text base_short classified_short classified_head snapshot_row
	git -C "$repo" rev-parse --verify --quiet "${upstream_ref}^{commit}" >/dev/null || return 1
	git -C "$repo" rev-parse --verify --quiet "${base_ref}^{commit}" >/dev/null || return 1
	classified_head="$(git -C "$repo" rev-parse "${classified_ref}^{commit}")" || return 1
	[[ "$(git -C "$repo" rev-parse "$upstream_ref")" == "$classified_head" ]] || return 1
	base_short="$(git -C "$repo" rev-parse --short=7 "$base_ref")"
	classified_short="$(git -C "$repo" rev-parse --short=7 "$classified_head")"
	printf -v snapshot_row '| %s | `%s` | `%s` | `%s` |' \
		"$label" "$upstream_ref" "$base_short" "$classified_short"
	rg -Fq -- "$snapshot_row" "$STATUS_DOC" || return 1
	if [[ "$(git -C "$repo" rev-parse "$base_ref")" == "$classified_head" ]]; then
		return 0
	fi
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
	done < <(git -C "$repo" rev-list --reverse "${base_ref}..${classified_head}")
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
	&& all_upstream_commits_classified "$ROOT" origin/main d08c12e d08c12e Harness '-' \
	&& all_upstream_commits_classified "$HUB" origin/main 7869c62 7869c62 med-agent-hub '-' \
	&& all_upstream_commits_classified "$CSAI" upstream/main d315500 5223f92 ChartSearchAI 'ChartSearchAI (' \
	&& all_upstream_commits_classified "$ESM" upstream/main 58ed478 3003cd2 chartsearchai-esm 'ChartSearchAI ESM (' \
	&& all_upstream_commits_classified "$QUERYSTORE" upstream/main de2ba8c 577db52 Querystore 'Querystore (' \
	&& all_upstream_commits_classified "$CATALYST" origin/main 3c1f1aa 27ad2aa Catalyst 'Catalyst (' \
	&& all_upstream_commits_classified "$CHATBOT" origin/main 2e723f8 2e723f8 openmrs_chatbot '-'; then
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
  && has_pattern 'test_streaming_and_blocking_adapters_use_the_same_stage_engine' "$HUB/tests/test_stage_engine_v2.py" \
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
relay_probe="$ROOT/artifacts/chartsearchai-local/relay-probe.json"
source_contracts_ok=0
querystore_unit_ok=0
querystore_es_ok=1
querystore_mysql_ok=1
if [[ $hub_m1_suite_ok -eq 1 ]] \
  && "$ROOT/scripts/test-querystore.sh" unit >/tmp/querystore-g07-unit.log 2>&1; then
  querystore_unit_ok=1
fi
if [[ "$RUN_E2E" == "1" ]]; then
  querystore_es_ok=0
  querystore_mysql_ok=0
  if "$ROOT/scripts/test-querystore.sh" elasticsearch-integration >/tmp/querystore-g07-es.log 2>&1; then
    querystore_es_ok=1
  fi
  if "$ROOT/scripts/test-querystore.sh" mysql-integration >/tmp/querystore-g07-mysql.log 2>&1; then
    querystore_mysql_ok=1
  fi
fi
if [[ -f "$HUB/server/context_sources.py" && -f "$HUB/tests/test_context_sources.py" ]] \
  && missing_pattern 'from \.querystore_client import QueryStoreClient' "$HUB/server/team.py" \
  && has_pattern 'test_supplemental_source_uses_the_same_normalized_ledger' "$HUB/tests" \
  && has_pattern 'test_service_startup_does_not_invent_querystore_credentials' "$HUB/tests" \
  && has_pattern 'queryStoreService\(\)\.getPatientChart' "$ROOT/targets/querystore/omod/src/main/java/org/openmrs/module/querystore/web/rest/QueryStoreRestController.java" \
  && has_pattern 'test_full_chart_accepts_thin_endpoint_envelope' "$HUB/tests/test_querystore_client.py" \
  && has_pattern 'test_full_chart_rejects_duplicate_record_across_pages' "$HUB/tests/test_querystore_client.py" \
  && has_pattern 'elasticsearch-integration' "$ROOT/scripts/test-querystore.sh" \
  && missing_pattern 'ensureIndexedComplete|PatientChartReadException' "$ROOT/targets/querystore/api/src/main" \
  && missing_pattern 'snapshotId|complete.*patient chart' "$HUB/server/querystore_client.py" \
  && missing_pattern 'QUERYSTORE_USERNAME[^\n]*admin|QUERYSTORE_PASSWORD[^\n]*Admin123' \
    "$HUB/server/config.py" "$ROOT/compose/openmrs-2.8-refapp.yml" \
  && [[ $hub_m1_suite_ok -eq 1 ]] \
  && [[ $querystore_unit_ok -eq 1 ]] \
  && [[ $querystore_es_ok -eq 1 ]] \
  && [[ $querystore_mysql_ok -eq 1 ]]; then
  source_contracts_ok=1
fi
if [[ $source_contracts_ok -ne 1 ]]; then
  record G07 FAIL "context source registry, thin Querystore adapter, paging, failure, or credential contract is incomplete"
elif [[ "$RUN_E2E" != "1" ]]; then
  record G07 PENDING "source contracts passed; RUN_E2E=1 is required for the exact deployed Querystore adapter proof"
elif [[ -s "$relay_probe" ]] \
  && "$ROOT/.venv/bin/python" - "$ROOT" "$relay_probe" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
proof = json.loads(Path(sys.argv[2]).read_text())
identity = proof["runtime_identity"]
querystore = identity["querystore"]
assert querystore["tree_clean"] is True
assert querystore["commit"] == subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=root / "targets/querystore", text=True
).strip()
assert proof["querystore_reference_count"] > 0
assert "querystore" in proof["reference_sources"]
module = identity["artifacts"]["querystore_omod"]
assert module["provenance"]["source_commit"] == querystore["commit"]
assert module["mounted_sha256"] == module["sha256"]
PY
then
  record G07 PASS "source contracts and exact deployed Querystore adapter proof passed"
else
  record G07 FAIL "exact deployed Querystore adapter proof failed"
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
import urllib.request
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
assert all(len(row["included"]) == row["selected_records"] for row in proof["results"])
assert all(item["source_id"] and item["reason"] for row in proof["results"] for item in row["included"])
assert all(item["source_id"] and item["reason"] for row in proof["results"] for item in row["excluded"])
PY
then
  record G09 PASS "current dev set has 100% required-source recall within exact budgets"
else
  record G09 PENDING "context quality proof is missing, stale, or failed"
fi

# G10-G12: deterministic temporal invariants and post-review ordering.
if has_pattern 'test_product_profiles.*temporal.*enforce|test_temporal.*cannot.*weaken' "$HUB/tests" \
  && has_pattern 'test_non_advertised_product_envelope_temporal_cannot_weaken_enforce' "$HUB/tests" \
  && has_pattern 'temporal_gate.*enforce' "$HUB/server/levels.yaml" \
  && has_pattern 'test_gate_rejects_malformed_and_nonledger_dates_when_ledger_is_empty' "$HUB/tests" \
  && has_pattern 'test_post_review_punctuation_rewrite_preserves_usable_answer' "$HUB/tests" \
  && has_pattern 'test_product_pipeline_fallback_records_enforced_temporal_gate' "$HUB/tests" \
  && has_pattern 'test_product_profile_defaults_temporal_anchor_to_wall_clock' "$HUB/tests" \
  && has_pattern 'test_fixed_evaluation_anchor_overrides_product_wall_clock_default' "$HUB/tests" \
  && has_pattern 'test_product_client_rejects_low_level_leg_before_execution' "$HUB/tests" \
  && has_pattern 'test_direct_hub_client_can_still_use_low_level_leg' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G10 PASS "Answer substance, malformed-date, rewrite, and enforce tests passed"
else
  record G10 FAIL "product Answer temporal invariant is not proven"
fi

if has_pattern 'test_.*indepth.*temporal.*gate|test_.*temporal.*indepth' "$HUB/tests" \
  && has_pattern '(indepth_temporal_gate|gate_indepth_claims)' "$HUB/server" \
  && has_pattern 'test_empty_indepth_cannot_report_checked_or_complete' "$HUB/tests" \
  && has_pattern 'test_unavailable_indepth_reviewer_cannot_ship_complete' "$HUB/tests" \
  && has_pattern 'test_unavailable_indepth_reviewer_is_withheld_in_product_envelope' "$HUB/tests" \
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
  && has_pattern 'test_final_mixed_grounding_cannot_leave_answer_checked' "$HUB/tests" \
  && has_pattern 'test_answer_and_indepth_grounding_checks_merge_for_shared_reference' "$HUB/tests" \
  && [[ $hub_m1_suite_ok -eq 1 ]]; then
  record G13 PASS "Answer/In-Depth current-ledger and prior-turn isolation tests passed"
else
  record G13 FAIL "citation replay/current-ledger invariant is not proven"
fi

java_m2_contracts_ok=0
if [[ $hub_m1_suite_ok -eq 1 ]] && command -v mvn >/dev/null 2>&1; then
  if "$ROOT/scripts/openmrs-source-pair-test.sh" >/tmp/hub-m2-java-contracts.log 2>&1; then
    java_m2_contracts_ok=1
  fi
fi

esm_m2_contracts_ok=0
if [[ $hub_m1_suite_ok -eq 1 ]] && [[ -d "$ESM/node_modules" ]] \
  && (cd "$ESM" && yarn test --run \
    src/components/model-picker.test.tsx src/hooks/useChartSearchAi.test.ts \
    src/components/ai-response-panel.test.tsx >/tmp/hub-m2-esm-contracts.log 2>&1); then
  esm_m2_contracts_ok=1
fi

if [[ -x "${HUB_VENV}/bin/pytest" ]] \
  && [[ -s "$HUB/server/drug_data/cross-reactivity-groups.json" ]] \
  && [[ $java_m2_contracts_ok -eq 1 ]] \
  && has_pattern 'persistHubStagedAnswer_preservesSafetyWarningsInAssistantWire' "$CSAI/api/src/test" \
  && has_pattern 'chatHistory_rehydratesSafetyWarningsAndInterruptedInDepth' "$CSAI/omod/src/test" \
  && (cd "$HUB" && "${HUB_VENV}/bin/python" -m pytest \
    tests/test_drug_safety.py tests/test_drug_safety_atc.py \
    tests/test_drug_safety_followthrough.py tests/test_drug_safety_integration.py \
    -q >/tmp/hub-g14.log 2>&1); then
  record G14 PASS "hub parity plus Java persistence/history safety-warning contracts passed"
else
  record G14 FAIL "drug-safety parity or Java persistence/history contracts failed"
fi

# G15-G17: thin relay, hub-owned discovery, and complete staged UX.
legacy_java='LocalLlmEngine|CitationGroundingVerifier|ModelSwitchService|LlmInferenceService|value = "/warmup"|value = "/search"|value = "/endpoints"|value = "/model/load"|chartSnapshot|chartMappingsJson|progressive.*preview|LM Studio'
if missing_pattern "$legacy_java" "$CSAI/api/src/main" "$CSAI/omod/src/main" \
  && missing_pattern 'response_format|chartAnswerResponseFormat' "$CSAI/api/src/main" "$CSAI/omod/src/main" \
  && missing_pattern 'querystore-api' "$CSAI/api/pom.xml" \
  && missing_pattern 'require_module[^>]*>org.openmrs.module.querystore' "$CSAI/omod/src/main/resources/config.xml" \
  && missing_pattern 'GGUF_MODEL_URL|gguf_model_url' "$CSAI/.github/workflows/build-standalone.yml" \
  && missing_pattern 'timeout\(Duration\.ofSeconds\([0-9]+\)\)' "$CSAI/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java" \
  && has_pattern 'hubRelay' "$CSAI/omod/src/main" \
  && has_pattern 'buildHubRelayHttpRequest_shouldNotImposeAWholeProfileTimeout' "$CSAI/omod/src/test" \
  && has_pattern 'hubRequestCount\.incrementAndGet' "$CSAI/omod/src/test" \
  && has_pattern 'assertEquals\(1, hubRequestCount\.get' "$CSAI/omod/src/test" \
  && has_pattern 'require_product_profile' "$CSAI/omod/src/main" "$CSAI/omod/src/test" \
  && has_pattern 'the hub product profile, not the Java relay, owns the answer schema' "$CSAI/omod/src/test"; then
  record G15 PASS "Java is a thin hub relay without a whole-profile timeout; the hub owns prompts, output schema, and inference"
else
  record G15 FAIL "legacy inference, schema ownership, discovery, bundled model, or Querystore coupling remains"
fi

if missing_pattern 'LM Studio|parseLmStudio|loadModel' "$CSAI/api/src/main" "$ESM/src" \
  && missing_pattern 'default_profile' "$HUB/server/main.py" \
  && missing_pattern 'profileId\?:' "$ESM/src/api/chartsearchai.ts" \
  && has_pattern 'single-e4b-checked' "$HUB/server/levels.yaml" \
  && has_pattern 'selection_priority' "$HUB/server/levels_loader.py" "$HUB/server/levels.yaml" \
  && has_pattern 'effective_default' "$HUB/server/openai_compat.py" \
  && has_pattern "visibility === 'product'" "$ESM/src/components/model-picker.component.tsx" \
  && has_pattern 'does not invent a fallback when the hub advertises no available default' "$ESM/src/components/model-picker.test.tsx" \
  && [[ $esm_m2_contracts_ok -eq 1 ]]; then
  record G16 PASS "hub metadata owns picker and default"
else
  record G16 FAIL "LM Studio/client-curated discovery or missing default metadata remains"
fi

if has_pattern 'answerValidation' "$ESM/src" \
  && has_pattern 'originalAnswer' "$ESM/src" \
  && has_pattern 'originalBlocks' "$ESM/src" \
  && has_pattern 'reviewDraft' "$ESM/src" \
  && has_pattern 'RED \(low\): shows both the caveat and the flagged message' "$ESM/src/components/ai-response-panel.test.tsx" \
  && has_pattern 'test_report_and_dashboard_share_flagged_output_semantics' "$ROOT/evals/validate/test_report_confidence.py" \
  && has_pattern 'section_confidence_displays' "$ROOT/harness/validate/review_presentation.py" \
  && has_pattern 'flagged Answer and review-only artifacts stay visible through reload' "$ROOT/tests/e2e/specs/chartsearchai-low-confidence-review.spec.ts" \
  && has_pattern 'onAnswerDone:[^\n]*answerDone' "$ESM/src/hooks/useChartSearchAi.ts" \
  && has_pattern 'onAnswerValidation:[^\n]*answerValidation' "$ESM/src/hooks/useChartSearchAi.ts" \
  && has_pattern 'onInDepthPending:[^\n]*inDepthPending' "$ESM/src/hooks/useChartSearchAi.ts" \
  && has_pattern 'tracks the turn phase through the staged lifecycle' "$ESM/src/hooks/useChartSearchAi.test.ts" \
  && has_pattern 'answer-validation lifecycle' "$ESM/src/components/ai-response-panel.test.tsx" \
  && has_pattern 'does not collapse mixed claim-level support' "$ESM/src/components/ai-response-panel.test.tsx" \
  && has_pattern 'hydrates a stale pending In-Depth as failed' "$ESM/src/hooks/useChartSearchAi.test.ts" \
  && has_pattern 'hydrates a stale checking answer as check unavailable' "$ESM/src/hooks/useChartSearchAi.test.ts" \
  && has_pattern 'preliminary_problem_stays_checking_until_configured_review_finishes' "$HUB/tests" \
  && has_pattern 'final grounding still completes before the answer settles' "$HUB/tests" \
  && has_pattern 'test_final_unsupported_grounding_marks_answer_needs_review' "$HUB/tests/test_staged_stream.py" \
  && has_pattern 'persistInterruptedState' "$CSAI/omod/src/main" \
  && has_pattern 'answer check was interrupted before completion' "$CSAI/omod/src/main" \
  && has_pattern 'abortsPromptlyOnDisconnectDuringHeartbeats' "$CSAI/omod/src/test" \
  && has_pattern 'noReviewGroundingSettledBeforeInterruptedInDepth_preservesCheckedValidation' "$CSAI/omod/src/test" \
  && has_pattern 'preserves checked validation when a no-review profile preempts after final grounding' "$ESM/src/hooks/useChartSearchAi.test.ts" \
  && [[ $esm_m2_contracts_ok -eq 1 ]] \
  && [[ $java_m2_contracts_ok -eq 1 ]]; then
  record G17 PASS "Answer and In-Depth validation lifecycle is rendered"
else
  record G17 FAIL "complete staged lifecycle UX is not implemented"
fi

# G18: positive cancellation evidence and unit proof are always required; live proof is required
# for final PASS.
if has_pattern 'test_profile_stream_client_disconnect_mid_indepth_frees_router_lock' "$HUB/tests" \
  && has_pattern '_write_cancellation_trace' "$HUB/server/engine.py" "$HUB/server/team.py" \
  && has_pattern 'test_conversation_history_summary_proves_priors_without_plaintext' "$HUB/tests" \
  && has_pattern 'prior_message_count' "$HUB/tests/test_stage_engine_v2.py" \
  && has_pattern 'hubTraceEntriesSince' "$ROOT/tests/e2e/specs/chartsearchai-e4b-multiturn-trivial.spec.ts" \
  && has_pattern 'hubCancellationsSince' "$ROOT/tests/e2e/specs/chartsearchai-preempt.spec.ts" \
  && [[ "$RUN_E2E" == "1" ]]; then
  if (cd "$ROOT/tests/e2e" && yarn playwright test chartsearchai-e4b-multiturn-trivial chartsearchai-preempt >/tmp/hub-g18.log 2>&1); then
    record G18 PASS "live multi-turn and preempt E2E passed"
  else
    record G18 FAIL "live multi-turn/preempt E2E failed"
  fi
elif [[ "$RUN_E2E" == "1" ]]; then
  record G18 FAIL "positive cancellation/slot-release proof is missing"
else
  record G18 PENDING "rerun with RUN_E2E=1 for live proof"
fi

# G19-G21: portable local setup, latency, and evaluation evidence.
residency_probe="$ROOT/artifacts/chartsearchai-local/small-model-residency.json"
if ! has_pattern '^chartsearchai-local:' "$ROOT/Makefile" \
  || ! has_pattern 'probe-chartsearchai-relay.py' "$ROOT/scripts/chartsearchai-local.sh" \
  || ! missing_pattern '/Users/[[:alnum:]_.-]+/' "$ROOT/scripts/llama-router.ini" \
  || ! missing_pattern 'LM_STUDIO|lmstudio' "$ROOT/.env.chartsearch.example"; then
  record G19 FAIL "portable chartsearchai-local path is incomplete"
elif [[ -s "$relay_probe" && -s "$residency_probe" ]] \
  && "$ROOT/.venv/bin/python" - "$ROOT" "$relay_probe" "$residency_probe" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
proof = json.loads(Path(sys.argv[2]).read_text())
residency = json.loads(Path(sys.argv[3]).read_text())
assert residency["schema_version"] == "llama_router_small_model_residency.v1"
assert residency["models"] == ["gemma-e2b", "gemma-e4b"]
assert residency["configured_default_models_max"] >= len(residency["models"])
assert residency["proof_scope"]["configured_default"] == "fresh chartsearchai-local launch"
assert residency["passed"] is True and residency["failure"] is None
assert residency["after"] == {"gemma-e2b": "loaded", "gemma-e4b": "loaded"}
assert [call["model"] for call in residency["calls"]] == residency["models"]
for item in residency["inputs"].values():
    path = (root / item["path"]).resolve()
    assert path.is_relative_to(root) and path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
assert proof["schema_version"] == "chartsearchai_relay_probe.v2"
assert proof["profile"] == "single-e4b-checked"
assert proof["querystore_reference_count"] > 0
assert "querystore" in proof["reference_sources"]
assert proof["hydrated"] is True and proof["cleared_after"] is True
assert proof["session"] and proof["message_id"] and proof["answer_done_ms"] > 0
assert isinstance(proof["audit_log_id"], int) and proof["audit_log_id"] > 0
assert proof["done_ms"] >= proof["answer_done_ms"]
assert proof["answer_validation"]["status"] in {"checked", "edited", "needs_review"}
if proof["answer_validation"]["status"] == "needs_review":
    assert proof["answer_validation"].get("issues")
assert proof["in_depth_terminal_event"] in {"indepth_done", "indepth_error"}
assert proof["in_depth_status"] == (
    "complete" if proof["in_depth_terminal_event"] == "indepth_done" else "needs_review"
)
assert proof["events"] == [
    "answer_done",
    "answer_validation",
    "indepth_pending",
    proof["in_depth_terminal_event"],
    "done",
]
assert proof["final_envelope_sha256"] == proof["hydrated_envelope_sha256"]
assert len(proof["answer_sha256"]) == 64
repos = {
    "harness": root,
    "med_agent_hub": root / "targets/med-agent-hub",
    "chartsearchai": root / "targets/chartsearchai",
    "chartsearchai_esm": root / "targets/chartsearchai-esm",
    "querystore": root / "targets/querystore",
}
identity = proof["runtime_identity"]
for name, path in repos.items():
    assert identity[name]["tree_clean"] is True
    assert identity[name]["commit"] == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=path, text=True
    ).strip()
assert identity["deployment"]["revision"] == identity["med_agent_hub"]["commit"]
def content(path):
    if path.is_file():
        return {"kind": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    files = [
        {
            "path": str(item.relative_to(path)),
            "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
            "size_bytes": item.stat().st_size,
        }
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"kind": "directory", "sha256": hashlib.sha256(encoded).hexdigest(), "files": files}

for artifact in list(identity["artifacts"].values()) + list(identity["configuration"].values()):
    path = root / artifact["path"]
    current = content(path)
    assert current["sha256"] == artifact["sha256"]
    if artifact.get("kind") == "directory":
        assert current["files"] == artifact["files"]
esm = identity["artifacts"]["chartsearchai_esm"]
for module_name in ("chartsearchai_omod", "querystore_omod"):
    module = identity["artifacts"][module_name]
    assert module["mounted_sha256"] == module["sha256"]
assert esm["served_files"] == {item["path"]: item["sha256"] for item in esm["files"]}
assert esm["import_map_target"] == "./openmrs-esm-chartsearchai-app-multiturn/openmrs-esm-chartsearchai-app.js"
artifact_sources = {
    "chartsearchai_omod": "chartsearchai",
    "querystore_omod": "querystore",
    "chartsearchai_esm": "chartsearchai_esm",
}
for name, artifact in identity["artifacts"].items():
    provenance_path = root / artifact["provenance_path"]
    assert provenance_path.is_file()
    provenance = json.loads(provenance_path.read_text())
    assert provenance == artifact["provenance"]
    assert provenance["source_tree_clean"] is True
    source_name = artifact_sources[name]
    assert provenance["source_commit"] == identity[source_name]["commit"]
for module_name in ("chartsearchai_omod", "querystore_omod"):
    module = identity["artifacts"][module_name]
    deployed = root / module["deployed_provenance_path"]
    assert json.loads(deployed.read_text()) == module["provenance"]
PY
then
  record G19 PASS "portable local startup proved relay hydration and E2B/E4B co-residency"
else
  record G19 PENDING "run make chartsearchai-local and make llama-router-small-model-proof"
fi

if has_pattern '\| G20 Performance \| Deferred \|' "$STATUS_DOC"; then
  record G20 DEFERRED "user-approved performance deferral; observations remain non-gating"
else
  record G20 PENDING "performance gate needs an approved criterion or explicit deferral"
fi
evaluation_proof="$ROOT/artifacts/roadmap/gates/G21-evaluation.json"
if [[ -s "$evaluation_proof" ]] \
  && "$ROOT/.venv/bin/python" - "$ROOT" "$evaluation_proof" <<'PY'
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

root = Path(sys.argv[1]).resolve()
proof = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
sys.path.insert(0, str(root))
from harness.validate.reconcile import cell_benchmark_score, combined_judge_summary

def artifact(entry):
    path = (root / entry["path"]).resolve()
    assert path.is_relative_to(root) and path.is_file() and path.stat().st_size > 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    return path

assert proof["schema_version"] == "hub_consolidation_evaluation.v1"
assert proof["status"] == "pass"
assert proof["reference_date"] == "2026-06-20"
assert proof["expected_cells"] == proof["completed_cells"] == 12
run_id = proof["run_id"]
run_dir = root / "artifacts" / "validate" / run_id
assert run_dir.is_dir()

manifest = json.loads((run_dir / "run_manifest.json").read_text())
run_sha = str(manifest.get("git_sha") or "")
assert re.fullmatch(r"[0-9a-f]{40}", run_sha)

def run_json(relative):
    return json.loads(subprocess.check_output(
        ["git", "show", f"{run_sha}:{relative}"], cwd=root, text=True
    ))

run_event = next(
    event
    for event in (
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text().splitlines()
        if line
    )
    if event.get("event_type") == "run"
)
comparison_set = run_event["comparison_set"]
assert proof["comparison_set"] == comparison_set
comparison = run_json(
    f"datasets/validation/comparison_sets/{comparison_set}.json"
)
assert comparison["scenario_ids"] == run_event["scenario_ids"]
assert comparison["backend_ids"] == run_event["backend_ids"]
required_scenarios = {
    "date-zabella-weight-table",
    "date-zabella-weight-endpoints",
    "date-aloice-orders-table",
    "date-aloice-last-visit-exact",
    "single-upcoming-appointments",
    "am-upcoming-appointments",
    "am-last-visit",
    "am-weight-trend",
    "am-cd4-history",
    "am-orders-6mo",
    "ek-growth",
    "abstain-out-of-chart",
}
assert set(comparison["scenario_ids"]) == required_scenarios
backend_registry = run_json("datasets/validation/backends.json")
profiles_by_backend = {
    backend: backend_registry[backend]["modelName"]
    for backend in comparison["backend_ids"]
}
assert set(profiles_by_backend.values()) == {"single-12b-checked"}
assert proof["backends"] == comparison["backend_ids"]
expected = {
    (scenario, backend)
    for scenario in comparison["scenario_ids"]
    for backend in comparison["backend_ids"]
}
assert len(expected) == 12
temporal_scenarios = set(comparison["temporal_scenario_ids"])
assert temporal_scenarios < set(comparison["scenario_ids"])

results_path = artifact(proof["results"])
assert results_path == run_dir / "results.jsonl"
results = [json.loads(line) for line in results_path.read_text().splitlines() if line]
assert {(row["scenario_id"], row["backend_id"]) for row in results} == expected
assert len(results) == 12 and all(row.get("reference_date") == "2026-06-20" for row in results)
assert all(not row.get("error") and (row.get("metrics") or {}).get("http_status") == 200 for row in results)

traces = [
    json.loads(line)
    for line in artifact(proof["selected_traces"]).read_text().splitlines()
    if line
]
assert {(row["scenario_id"], row["backend_id"]) for row in traces} == expected
assert len(traces) == 12
assert all((row.get("trace") or {}).get("reference_date") == "2026-06-20" for row in traces)

audit = json.loads(artifact(proof["deterministic_audit"]).read_text())
assert audit["schema_version"] == "product_run_deterministic_audit.v1"
assert audit["status"] == "pass" and audit["blockers"] == []
assert audit["profiles_by_backend"] == profiles_by_backend
assert {(row["scenario_id"], row["backend_id"]) for row in audit["cells"]} == expected

judgments = proof["judgments"]
assert len(judgments) >= 2
assert len({row["actor"] for row in judgments}) == len(judgments)
assert len({row["path"] for row in judgments}) == len(judgments)
assert len({row["sha256"] for row in judgments}) == len(judgments)
rubric = {
    "scenario_id", "backend_id", "accuracy", "completeness", "relevance",
    "abstention_outcome", "citation_groundedness", "harm", "note",
}
actor_rows = {}
judge_configurations = set()
for judgment in judgments:
    path = artifact(judgment)
    assert judgment["rows"] == 12
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert len(rows) == 12 and all(rubric <= row.keys() for row in rows)
    assert {(row["scenario_id"], row["backend_id"]) for row in rows} == expected
    assert all(
        isinstance(row[axis], (int, float)) and not isinstance(row[axis], bool)
        and 0 <= row[axis] <= 10
        for row in rows for axis in ("accuracy", "completeness", "relevance")
    )
    assert all(row["abstention_outcome"] in {"n-a", "correct", "over-abstained", "failed-to-abstain"} for row in rows)
    assert all(row["citation_groundedness"] in {"n-a", "supported", "partly", "unsupported"} for row in rows)
    assert all(row["citation_groundedness"] != "unsupported" for row in rows)
    assert all(isinstance(row["harm"], bool) and str(row["note"]).strip() for row in rows)
    assert all(not row["harm"] for row in rows)
    temporal_rows = [row for row in rows if row["scenario_id"] in temporal_scenarios]
    assert all(row.get("temporal_date_accuracy") == "ok" for row in temporal_rows)
    assert all(row.get("temporal_window") == "ok" for row in temporal_rows)
    assert all(row.get("temporal_trend") == "ok" for row in temporal_rows)
    manifest = json.loads(artifact(judgment["manifest"]).read_text())
    assert manifest["schema_version"] == "judge_actor.v1"
    assert manifest["actor_id"] == judgment["actor"]
    assert manifest["actor_type"] in {"llm-judge", "human"}
    assert manifest["model"] and manifest["method"] and manifest["created_at"]
    judge_configurations.add((manifest["model"], manifest["method"]))
    assert manifest["run_id"] == run_id and manifest["n_rows"] == 12
    assert manifest["output_sha256"] == judgment["sha256"]
    actor_rows[judgment["actor"]] = rows
assert len(judge_configurations) == len(judgments)

combined = json.loads(artifact(proof["combined_judgment"]).read_text())
assert combined["schema_version"] == "combined_judgment.v1"
assert combined["actors"] == sorted(actor_rows)
assert len(combined["cells"]) == 12
assert {(row["scenario_id"], row["backend_id"]) for row in combined["cells"]} == expected
actor_index = {
    actor: {(row["scenario_id"], row["backend_id"]): row for row in rows}
    for actor, rows in actor_rows.items()
}
for cell in combined["cells"]:
    key = (cell["scenario_id"], cell["backend_id"])
    scores = {actor: cell_benchmark_score(rows[key]) for actor, rows in actor_index.items()}
    assert cell["actor_scores"] == scores
    values = [float(score) for score in scores.values()]
    assert cell["consensus_score"] == round(sum(values) / len(values), 1)
    assert cell["actor_range"] == round(max(values) - min(values), 1)
assert combined["backend_summary"] == combined_judge_summary(
    actor_rows, sorted({backend for _scenario, backend in expected})
)

review = json.loads(artifact(proof["per_cell_review"]).read_text())
assert review["schema_version"] == "product_run_per_cell_review.v1"
assert review["completed"] is True and len(review["cells"]) == 12
assert {(row["scenario_id"], row["backend_id"]) for row in review["cells"]} == expected
assert review["baseline"]["run_id"] and review["baseline"]["comparison_set"]
consensus = {
    (row["scenario_id"], row["backend_id"]): row["consensus_score"]
    for row in combined["cells"]
}
derived_regressions = set()
for row in review["cells"]:
    key = (row["scenario_id"], row["backend_id"])
    assert row["baseline_status"] in {"compared", "not_comparable"}
    assert row["disposition"] and row["evidence"]
    assert row["current_score"] == consensus[key]
    if row["baseline_status"] == "compared":
        assert isinstance(row["baseline_score"], (int, float))
        assert row["delta"] == round(row["current_score"] - row["baseline_score"], 1)
        if row["delta"] < -10:
            derived_regressions.add(key)
    else:
        assert row["baseline_score"] is None and row["delta"] is None
        assert row["not_comparable_reason"]
assert isinstance(review["regressions"], list)
assert all(item.get("disposition") and item.get("evidence") for item in review["regressions"])
assert {
    (item["scenario_id"], item["backend_id"]) for item in review["regressions"]
} == derived_regressions

report = proof["report"]
local_report = artifact(report)
assert report["published"] is True and report["http_status"] == 200
assert report["url"] == f"https://reports.openclinai.org/{report['slug']}/"
assert report["checked_at"]
assert local_report.name == "index.html"
meta_path = artifact(report["meta"])
meta = json.loads(meta_path.read_text())
assert meta["slug"] == report["slug"] and meta["run_dir"] == run_id
assert meta["comparison_set"] == comparison_set
with urllib.request.urlopen(report["url"], timeout=30) as response:
    remote_report = response.read()
    assert response.status == 200
with urllib.request.urlopen(report["url"] + "meta.json", timeout=30) as response:
    remote_meta = response.read()
    assert response.status == 200
assert hashlib.sha256(remote_report).hexdigest() == report["sha256"]
assert hashlib.sha256(remote_meta).hexdigest() == report["meta"]["sha256"]
PY
then
  record G21 PASS "12-cell stable-profile run, independent judgments, per-cell review, and published report are hash-bound"
else
  record G21 PENDING "missing or invalid judged publication proof: ${evaluation_proof#${ROOT}/}"
fi

# G22: active documentation alignment across root and every submodule.
if "$ROOT/scripts/verify-doc-drift.sh" >/tmp/hub-g22.log 2>&1; then
  record G22 PASS "verify-doc-drift.sh passed"
else
  record G22 FAIL "verify-doc-drift.sh failed"
fi

# G23: code-qa outputs are hash-bound reviews of the exact release heads, not presence checks.
qa_dir="$ROOT/artifacts/roadmap/code-qa"
qa_result="$qa_dir/result.json"
if [[ -s "$qa_result" ]] \
  && "$ROOT/.venv/bin/python" - "$ROOT" "$qa_result" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
result = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert result["schema_version"] == "code_qa_result.v1"
assert result["status"] == "pass"
assert result["blockers"] == []
heads = result["reviewed_shas"]
assert heads["root"] == subprocess.check_output(
    ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
).strip()
for path, expected_sha in heads["submodules"].items():
    target = (root / path).resolve()
    assert target.is_relative_to(root) and (target / ".git").exists()
    actual_sha = subprocess.check_output(
        ["git", "-C", str(target), "rev-parse", "HEAD"], text=True
    ).strip()
    assert actual_sha == expected_sha

required = {
    "meaningful-test-coverage",
    "simplicity-review",
    "spec-code-alignment",
    "cross-repo-companion-review",
    "evidence-bundle",
}
reviews = result["reviews"]
assert {review["id"] for review in reviews} == required
for review in reviews:
    assert review["status"] == "pass" and review["blockers"] == []
    report = review["report"]
    path = (root / report["path"]).resolve()
    assert path.is_relative_to(root) and path.is_file() and path.stat().st_size > 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report["sha256"]
PY
then
  record G23 PASS "DIGI-UW/code-qa reports pass with zero blockers and match the exact reviewed heads"
else
  record G23 PENDING "missing, stale, or blocking DIGI-UW/code-qa result: ${qa_result#${ROOT}/}"
fi

# G24 is derived from G01-G23 plus final clean-tree state.
release_ready=1
for n in $(seq -w 1 23); do
  gate="G${n}"
  status="${GATE_STATUS[$gate]:-PENDING}"
  if [[ "$gate" == "G20" && "$status" == "DEFERRED" ]]; then
    continue
  fi
  [[ "$status" == "PASS" ]] || release_ready=0
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
  if [[ "$gate" == "G20" && "$status" == "DEFERRED" ]]; then
    continue
  fi
  [[ "$status" == "PASS" ]] || overall=1
done

exit "$overall"
