from __future__ import annotations

import re
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
