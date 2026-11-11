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

    out = build_report(run_dir)
    assert out == run_dir / "report-data.json"
    raw = out.read_text(encoding="utf-8")
    packet = json.loads(raw)
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    for row in results["results"]:
        assert row["scenarioId"] in raw
    assert packet["runs"][0]["judging"]["recorded"] is False
    assert packet["runs"][0]["judging"]["canonical"] == []
    assert packet["runs"][0]["judge"] == []
    assert packet["runs"][0]["judge_rows"] == []
    assert packet["runs"][0]["judge_actors"] == []

    summary = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
    assert summary["judges"] == []
    assert summary["scout"] == []

    dash = json.loads((run_dir / "dashboard-data.json").read_text(encoding="utf-8"))
    assert dash["status"]["judged_scored"] == 0
    assert dash["status"]["judged_passed"] == 0
    assert "gold-fail-high-judge" in raw
    assert "FAIL" in raw
