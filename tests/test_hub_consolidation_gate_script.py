from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-hub-consolidation-gates.sh"
STAGE_SCRIPT = ROOT / "scripts" / "verify-stage-refactor-gates.sh"
DOC_SCRIPT = ROOT / "scripts" / "verify-doc-drift.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "harness-ci.yml"


def test_consolidation_gate_script_declares_every_roadmap_gate_once():
    text = SCRIPT.read_text(encoding="utf-8")
    declared = re.findall(r'^GATE_TITLES\[(G\d{2})\]="', text, re.MULTILINE)

    assert declared == [f"G{i:02d}" for i in range(1, 25)]


def test_ci_installs_the_consolidation_gate_search_tool():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "sudo apt-get install --yes ripgrep" in workflow


def test_consolidation_gate_script_allows_only_approved_g20_deferral():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "G20 may be DEFERRED only" in text
    assert "user-approved performance deferral" in text
    assert 'if [[ "$gate" == "G20" && "$status" == "DEFERRED" ]]' in text
    assert '[[ "$status" == "PASS" ]] || overall=1' in text
    assert 'exit "$overall"' in text
    assert "local_performance.v1" not in text
    assert "G20-performance.json" not in text
    assert "relative warm-run performance proof" not in text


def test_consolidation_gate_script_checks_untracked_trees_and_raw_leg_goldens():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "status --porcelain --untracked-files=all" in text
    assert "tests/test_output_goldens.py" in text
    assert "all_upstream_commits_classified" in text
    assert 'rev-list --reverse "${base_ref}..${classified_head}"' in text
    assert '"$(git -C "$repo" rev-parse "$upstream_ref")" == "$classified_head"' in text
    assert 'rev-list --reverse "HEAD..${upstream_ref}"' not in text


def test_multi_turn_gate_names_the_real_positive_history_test():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "test_conversation_history_summary_proves_priors_without_plaintext" in text
    assert 'has_pattern \'prior_message_count\' "$HUB/tests/test_stage_engine_v2.py"' in text
    assert "conversation_history.*prior_message_count" not in text


def test_gate_scripts_describe_the_current_stage_engine_and_no_java_fallback():
    consolidation = SCRIPT.read_text(encoding="utf-8")
    stage = STAGE_SCRIPT.read_text(encoding="utf-8")

    assert "tests/test_drug_safety_followthrough.py" in consolidation
    assert 'exec "${ROOT}/scripts/verify-hub-consolidation-gates.sh" "$@"' in stage
    assert "Gate matrix" not in stage
    assert "suite_run" not in stage


def test_thin_relay_gate_names_every_removed_product_surface():
    text = SCRIPT.read_text(encoding="utf-8")

    for stale_surface in (
        "ModelSwitchService",
        'value = "/endpoints"',
        'value = "/model/load"',
        "LM Studio",
        "CitationGroundingVerifier",
        "chartSnapshot",
        'value = "/search"',
        'value = "/warmup"',
        "querystore-api",
        "require_module[^>]*>org.openmrs.module.querystore",
        "GGUF_MODEL_URL|gguf_model_url",
    ):
        assert stale_surface in text


def test_documentation_gate_requires_positive_current_architecture_statements():
    text = DOC_SCRIPT.read_text(encoding="utf-8")

    assert "REQUIRED_CURRENT" in text
    for current_surface in (
        '"README.md"',
        '"adapters/chartsearchai/README.md"',
        '"adapters/querystore/README.md"',
        '"specs/006-validation-harness-mvp/spec.md"',
        '"targets/chartsearchai/README.md"',
        '"targets/chartsearchai-esm/README.md"',
        '"targets/med-agent-hub/README.md"',
        '"targets/querystore/docs/rest-api.md"',
    ):
        assert current_surface in text
    assert "header_is_historical" in text


def test_documentation_gate_rejects_removed_role_and_relay_configuration():
    text = DOC_SCRIPT.read_text(encoding="utf-8")

    for stale_surface in (
        "PROMPT_INJECTION",
        "ORCHESTRATOR_MODEL",
        "SYNTHESIZER_MODEL",
        "MED_MODEL",
        "bundled-LLM compatibility",
        "orchestrator-as-validator",
    ):
        assert stale_surface in text


def test_consolidation_gate_script_executes_the_red_baseline(tmp_path):
    env = dict(os.environ)
    env["HUB_VENV"] = str(tmp_path / "missing-hub-venv")
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    rows = re.findall(
        r"^(G\d{2})\s+(PASS|FAIL|PENDING|DEFERRED)\s+",
        result.stdout,
        re.MULTILINE,
    )
    assert [gate for gate, _status in rows] == [f"G{i:02d}" for i in range(1, 25)]
    assert ("G01", "PASS") in rows
    assert ("G04", "FAIL") in rows
    assert ("G20", "DEFERRED") in rows
