from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from harness.validate.report import build_report

from .dom_canon import canonicalize_html

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "validate-run-golden"
_FROZEN = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


def _freeze_report_clock(monkeypatch) -> None:
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return _FROZEN if tz is None else _FROZEN.astimezone(tz)

    monkeypatch.setattr("harness.validate.report.datetime", _FrozenDateTime)


def _parse_embedded_data(html: str) -> dict:
    m = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>",
        html,
        flags=re.DOTALL,
    )
    assert m is not None, "missing report-data island"
    return json.loads(m.group(1))


def test_report_regeneration_is_byte_identical_to_pre_p0_baseline(monkeypatch) -> None:
    _freeze_report_clock(monkeypatch)
    baseline = (FIXTURE / "report.pre-p0.html").read_bytes()
    regenerated = build_report(FIXTURE).read_bytes()
    assert regenerated == baseline


def test_report_regeneration_matches_pre_p0_dom_and_embedded_data(monkeypatch) -> None:
    """P1 semantic parity: canonical HTML structure + exact parsed data island."""
    _freeze_report_clock(monkeypatch)
    baseline_html = (FIXTURE / "report.pre-p0.html").read_text(encoding="utf-8")
    regenerated_html = build_report(FIXTURE).read_text(encoding="utf-8")

    assert canonicalize_html(regenerated_html) == canonicalize_html(baseline_html)
    assert _parse_embedded_data(regenerated_html) == _parse_embedded_data(baseline_html)
