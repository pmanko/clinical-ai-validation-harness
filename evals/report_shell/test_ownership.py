"""CVR-G05: generic shell ownership vs domain renderers."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "harness" / "report_shell"
REPORT = ROOT / "harness" / "validate" / "report.py"


def test_shell_has_document_assets_stats_defs() -> None:
    doc = ast.parse((SHELL / "document.py").read_text(encoding="utf-8"))
    assets = ast.parse((SHELL / "assets.py").read_text(encoding="utf-8"))
    stats = ast.parse((SHELL / "stats.py").read_text(encoding="utf-8"))

    doc_fns = {n.name for n in ast.walk(doc) if isinstance(n, ast.FunctionDef)}
    asset_assigns = {
        n.targets[0].id
        for n in ast.walk(assets)
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name)
    }
    stats_fns = {n.name for n in ast.walk(stats) if isinstance(n, ast.FunctionDef)}

    assert "render_document" in doc_fns
    assert "embed_json" in doc_fns
    assert "THEME_CSS_VARS" in asset_assigns
    assert "SORTABLE_TABLE_CSS" in asset_assigns
    assert {"avg", "percentile", "box_stats", "robust_axis_max", "ordered_unique"} <= stats_fns


def test_domain_renderers_remain_outside_shell() -> None:
    shell_text = "\n".join(p.read_text(encoding="utf-8") for p in SHELL.glob("*.py"))
    for needle in (
        "chartsearchai",
        "scout",
        "adjudicat",
        "source_cell",
        "answer_cell",
        "catalyst-judge",
    ):
        assert needle not in shell_text.lower(), needle

    report_text = REPORT.read_text(encoding="utf-8")
    assert "from harness.report_shell" in report_text
    assert "def build_report" in report_text
