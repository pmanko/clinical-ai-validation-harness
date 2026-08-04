"""Catalyst report must degrade cleanly when judge artifacts are absent."""

from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalyst-notebook-golden"


def test_report_without_judge_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("network blocked")

    monkeypatch.setattr(socket, "socket", _raise)

    run_dir = tmp_path / "no-judge-run"
    shutil.copytree(FIXTURE, run_dir)
    for name in (
        "judge.jsonl",
        "judge_manifest.json",
        "judge.pass-1.jsonl",
        "judge.pass-2.jsonl",
        "judge.pass-3.jsonl",
    ):
        p = run_dir / name
        if p.exists():
            p.unlink()

    from harness.catalyst.report import build_report

    html = build_report(run_dir).read_text(encoding="utf-8")
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    for row in results["results"]:
        assert row["scenarioId"] in html
    assert "Judge not available" in html or "no judge" in html.lower()
    assert "gold-fail-high-judge" in html
    assert "FAIL" in html
