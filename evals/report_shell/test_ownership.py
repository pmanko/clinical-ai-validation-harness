"""Producer/viewer boundary ownership tests (`openclinai.report.v2`)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS_DIR = ROOT / "harness"
VALIDATE_REPORT = HARNESS_DIR / "validate" / "report.py"
CATALYST_REPORT = HARNESS_DIR / "catalyst" / "report.py"
STATS = HARNESS_DIR / "common" / "stats.py"


def test_stats_helpers_live_in_common_module() -> None:
    stats_ast = ast.parse(STATS.read_text(encoding="utf-8"))
    stats_fns = {n.name for n in ast.walk(stats_ast) if isinstance(n, ast.FunctionDef)}
    assert {"avg", "percentile", "box_stats", "robust_axis_max", "ordered_unique"} <= stats_fns


def test_harness_producers_emit_pure_v2_json_without_embedded_html_shells() -> None:
    for path in sorted(HARNESS_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "<!doctype html>" not in text.lower(), f"{path} embeds an HTML document shell"
        assert "report-shell.js" not in text, f"{path} references viewer asset report-shell.js"
        assert "dashboard-shell.js" not in text, f"{path} references viewer asset dashboard-shell.js"

    for report_mod in (VALIDATE_REPORT, CATALYST_REPORT):
        text = report_mod.read_text(encoding="utf-8")
        assert "def build_report" in text
        assert "openclinai.report.v2" in text
