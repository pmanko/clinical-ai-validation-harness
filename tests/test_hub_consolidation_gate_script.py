from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-hub-consolidation-gates.sh"
STAGE_SCRIPT = ROOT / "scripts" / "verify-stage-refactor-gates.sh"
DOC_SCRIPT = ROOT / "scripts" / "verify-doc-drift.sh"
SOURCE_PAIR_SCRIPT = ROOT / "scripts" / "openmrs-source-pair-test.sh"
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


def test_gate_scripts_keep_the_historical_consolidation_matrix_separate_from_dual_provider_governance():
    consolidation = SCRIPT.read_text(encoding="utf-8")
    stage = STAGE_SCRIPT.read_text(encoding="utf-8")
    dual = (ROOT / "scripts" / "verify-dual-provider-parity-gates.sh").read_text(
        encoding="utf-8"
    )
    dual_evaluator = (ROOT / "scripts" / "verify_dual_provider_parity_gates.py").read_text(
        encoding="utf-8"
    )

    assert "tests/test_drug_safety_followthrough.py" in consolidation
    assert 'exec "${ROOT}/scripts/verify-hub-consolidation-gates.sh" "$@"' in stage
    assert "Gate matrix" not in stage
    assert "suite_run" not in stage
    assert "Bundled and hub use fully separate inference backends" in (
        ROOT / "specs/artifacts/planning/openmrs-dual-provider-parity-roadmap-status.md"
    ).read_text(encoding="utf-8")
    assert "verify_dual_provider_parity_gates.py" in dual
    assert "ChartSearchAI PR #26" in dual_evaluator


def test_openmrs_source_pair_gate_builds_exact_integration_heads_in_dependency_order():
    script = SOURCE_PAIR_SCRIPT.read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "openmrs-source-pair-test:" in makefile
    assert "./scripts/openmrs-source-pair-test.sh" in makefile
    assert script.count("origin/harness-integration") >= 2
    assert 'verify_integration_head "${ROOT}/targets/querystore"' in script
    assert 'verify_integration_head "${ROOT}/targets/chartsearchai"' in script
    assert 'verify_integration_head "${ROOT}/targets/chartsearchai-esm"' in script
    assert 'rev-parse "HEAD:${gitlink_path}"' in script
    assert "status --porcelain --untracked-files=all" in script
    assert script.index('"${MVN_BIN}" -q -B clean install') < script.index(
        '"${MVN_BIN}" -q -B clean package'
    )


def test_active_docs_gate_preserves_bundled_and_hub_provider_contracts():
    text = DOC_SCRIPT.read_text(encoding="utf-8")

    assert "approved dual-provider" in text
    assert "hub-only provider claim" in text
    assert "removed bundled-provider claim" in text
    assert "LocalLlmEngine" not in text
    assert "CitationGroundingVerifier" not in text


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
        '"targets/querystore/docs/chartsearchai-port-map.md"',
        '"targets/querystore/docs/migration-chartsearchai.md"',
        '"targets/chartsearchai/docs/embedding-improvement-plan.md"',
    ):
        assert current_surface in text
    for required_dual_provider_statement in (
        'r"bundled provider"',
        'r"med-agent-hub provider"',
        'r"no automatic fallback"',
    ):
        assert required_dual_provider_statement in text
    assert "header_is_historical" in text
    assert "text.splitlines()[:12]" in text


def test_documentation_gate_rejects_removed_shared_state_and_hub_only_configuration():
    text = DOC_SCRIPT.read_text(encoding="utf-8")

    for stale_surface in (
        "chartSnapshot",
        "chartMappingsJson",
        "indepth_token",
        "MED_AGENT_(?:ORCHESTRATOR_MODEL|MED_MODEL)",
        "hub-only provider claim",
        "removed bundled-provider claim",
    ):
        assert stale_surface in text


def test_documentation_gate_passes_the_current_dual_provider_docs():
    result = subprocess.run(
        ["bash", str(DOC_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: scanned 7 repos" in result.stdout


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
