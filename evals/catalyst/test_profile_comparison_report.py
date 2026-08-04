"""Offline tests for the multi-profile Catalyst notebook comparison report."""

from __future__ import annotations

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
    from harness.catalyst.profile_comparison_report import build_comparison_report

    html = build_comparison_report(
        [
            {"run_dir": FIXTURE, "profile_id": "catalyst-query-a", "profile_label": "Profile A"},
            {"run_dir": FIXTURE, "profile_id": "catalyst-query-b", "profile_label": "Profile B"},
        ]
    )

    assert "Profile A" in html
    assert "Profile B" in html
    assert "catalyst-query-a" in html
    assert "catalyst-query-b" in html
    # The fixture has 7/8 passed; both rows should show that ratio.
    assert html.count("7/8") == 2
    # Average generation wall time (ms) is a real speed signal for comparing
    # small-model tradeoffs, so it should be surfaced too.
    assert "avg" in html.lower() and "ms" in html.lower()


def test_comparison_report_breaks_down_pass_fail_per_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.profile_comparison_report import build_comparison_report

    html = build_comparison_report(
        [{"run_dir": FIXTURE, "profile_id": "catalyst-query-a", "profile_label": "Profile A"}]
    )

    # The fixture's one genuine failure must be visible per-scenario, not
    # hidden inside an aggregate pass count.
    assert "bounded-hub-tool-failure" in html
    assert "narrowing-unchanged-base" in html
    assert html.count("FAIL") >= 1
    assert html.count("PASS") >= 1
