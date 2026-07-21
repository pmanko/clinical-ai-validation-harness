"""Offline Catalyst report tests (CVR-G11 / D8)."""

from __future__ import annotations

import ast
import json
import socket
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalyst-notebook-golden"
ROOT = Path(__file__).resolve().parents[2]


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("network blocked in catalyst report tests")

    monkeypatch.setattr(socket, "socket", _raise)


def test_build_report_offline_contains_required_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_report

    out = build_report(FIXTURE)
    assert out == FIXTURE / "report.html"
    html = out.read_text(encoding="utf-8")

    results = json.loads((FIXTURE / "results.json").read_text(encoding="utf-8"))
    assertion_names = sorted(
        {a["name"] for row in results["results"] for a in row["assertions"]}
    )
    for row in results["results"]:
        assert row["scenarioId"] in html
    for name in assertion_names:
        assert name in html

    assert "gold-fail-high-judge" in html
    assert "row_set mismatch" in html
    assert "scenarios/gold-fail-high-judge/repetition-01/15-gold-execution-match-base.json" in html
    assert "FAIL" in html
    assert "advisory" in html.lower() or "Judge" in html

    # Judge medians / rationales from finalized judge.jsonl
    assert "intent_fidelity" in html
    assert "Synthetic fixture: SQL projection/filters align" in html

    # Multi-version SQL unified diff hunk markers (line-level, rstrip)
    assert "mid revision" in html
    assert "result_status = 'final'" in html or "result_status = &#x27;final&#x27;" in html
    assert "@@" in html or "diff" in html.lower()

    assert "data-theme=" in html
    assert "theme-toggle" in html
    assert "th-sort" in html or "makeSortable" in html


def test_gold_fail_with_perfect_judge_still_reports_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_report

    html = build_report(FIXTURE).read_text(encoding="utf-8")
    # Scenario cell must remain FAIL despite composite 100 judge scores.
    idx = html.index("gold-fail-high-judge")
    window = html[idx : idx + 2500]
    assert "FAIL" in window
    assert "100" in window  # advisory judge composite still visible


def test_import_boundary_rejects_harness_validate() -> None:
    src = (ROOT / "harness" / "catalyst" / "report.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "harness.validate" or alias.name.startswith(
                    "harness.validate."
                ):
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "harness.validate" or node.module.startswith(
                "harness.validate."
            ):
                bad.append(node.module)
    assert bad == [], bad
