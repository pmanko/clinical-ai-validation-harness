"""Producer/viewer boundary ownership tests (`openclinai.report.v2`)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATE_REPORT = ROOT / "harness" / "validate" / "report.py"
CATALYST_REPORT = ROOT / "harness" / "catalyst" / "report.py"
STATS = ROOT / "harness" / "common" / "stats.py"


def test_harness_report_shell_is_retired_and_stats_live_in_common() -> None:
    assert not (ROOT / "harness" / "report_shell").exists()
    assert not (ROOT / "harness" / "catalyst" / "phase1_report.py").exists()
    assert not (ROOT / "harness" / "catalyst" / "profile_comparison_report.py").exists()

    stats_ast = ast.parse(STATS.read_text(encoding="utf-8"))
    stats_fns = {n.name for n in ast.walk(stats_ast) if isinstance(n, ast.FunctionDef)}
    assert {"avg", "percentile", "box_stats", "robust_axis_max", "ordered_unique"} <= stats_fns


def test_report_builders_emit_pure_v2_json_without_html_shells() -> None:
    val_text = VALIDATE_REPORT.read_text(encoding="utf-8")
    cat_text = CATALYST_REPORT.read_text(encoding="utf-8")
    for text in (val_text, cat_text):
        assert "def build_report" in text
        assert "openclinai.report.v2" in text
        assert "<!doctype html>" not in text.lower()
        assert "report-shell.js" not in text
