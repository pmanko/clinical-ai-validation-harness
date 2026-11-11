"""Offline tests for the multi-profile Catalyst notebook comparison v2 JSON packet."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalyst-notebook-golden"


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("network blocked in catalyst report tests")

    monkeypatch.setattr(socket, "socket", _raise)


def test_comparison_report_shows_each_profiles_pass_rate_and_assertion_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_comparison_report

    packet = build_comparison_report(
        [
            {"run_dir": FIXTURE, "profile_id": "catalyst-query-a", "profile_label": "Profile A"},
            {"run_dir": FIXTURE, "profile_id": "catalyst-query-b", "profile_label": "Profile B"},
        ]
    )
    assert packet["schema"] == "openclinai.report.v2"
    assert packet["schema_version"] == 2
    entries = packet["runs"][0]["catalyst"]["comparison_entries"]
    assert [e["entry_id"] for e in entries] == ["Profile A", "Profile B"]
    assert [e["passed_count"] for e in entries] == ["7/8", "7/8"]
    assert all(e["avg_latency_ms"] is not None for e in entries)


def test_comparison_report_breaks_down_pass_fail_per_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_comparison_report

    packet = build_comparison_report(
        [{"run_dir": FIXTURE, "profile_id": "catalyst-query-a", "profile_label": "Profile A"}]
    )
    serialized = json.dumps(packet)
    assert "bounded-hub-tool-failure" in serialized
    assert "narrowing-unchanged-base" in serialized
