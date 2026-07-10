from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-hub-consolidation-gates.sh"
STAGE_SCRIPT = ROOT / "scripts" / "verify-stage-refactor-gates.sh"


def test_consolidation_gate_script_declares_every_roadmap_gate_once():
    text = SCRIPT.read_text(encoding="utf-8")
    declared = re.findall(r'^GATE_TITLES\[(G\d{2})\]="', text, re.MULTILINE)

    assert declared == [f"G{i:02d}" for i in range(1, 25)]


def test_consolidation_gate_script_treats_non_pass_as_failure():
    text = SCRIPT.read_text(encoding="utf-8")

    assert '[[ "$status" == "PASS" ]] || overall=1' in text
    assert 'exit "$overall"' in text


def test_consolidation_gate_script_checks_untracked_trees_and_raw_leg_goldens():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "status --porcelain --untracked-files=all" in text
    assert "tests/test_output_goldens.py" in text
    assert "all_upstream_commits_classified" in text
    assert 'rev-list --reverse "HEAD..${upstream_ref}"' in text


def test_gate_scripts_describe_the_current_stage_engine_and_no_java_fallback():
    consolidation = SCRIPT.read_text(encoding="utf-8")
    stage = STAGE_SCRIPT.read_text(encoding="utf-8")

    assert "tests/test_drug_safety_followthrough.py" in consolidation
    assert "tests/test_drug_safety_followthrough.py" in stage
    assert "stage_plan_for_level" not in stage
    assert "run_team_stream" not in stage
    assert "LOCAL-bundled-engine fallback" not in stage
    assert '"id": mid' not in stage
    assert "server/engine.py" in stage


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
    rows = re.findall(r"^(G\d{2})\s+(PASS|FAIL|PENDING)\s+", result.stdout, re.MULTILINE)
    assert [gate for gate, _status in rows] == [f"G{i:02d}" for i in range(1, 25)]
    assert ("G01", "PASS") in rows
    assert ("G04", "FAIL") in rows
