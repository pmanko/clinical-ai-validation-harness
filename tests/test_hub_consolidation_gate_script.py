from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-hub-consolidation-gates.sh"


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
