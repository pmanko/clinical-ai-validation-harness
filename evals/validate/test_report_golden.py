from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from harness.validate.report import build_report, _embed_json

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


def _baseline_with_captured_arm_cards() -> str:
    """The former live-source arm cards are no longer part of the report contract."""
    baseline = (FIXTURE / "report.pre-p0.html").read_text(encoding="utf-8")
    data = _parse_embedded_data(baseline)
    meta_path = FIXTURE / "run_meta.json"
    frozen = json.loads(meta_path.read_text()).get("arm_cards", {}) if meta_path.exists() else {}
    for run in data["runs"]:
        run["arm_cards"] = {bid: frozen.get(bid) for bid in run["backends"]}
    return re.sub(
        r"(<script type='application/json' id='report-data'>).*?(</script>)",
        lambda match: match[1] + _embed_json(data) + match[2],
        baseline, flags=re.DOTALL,
    )


def test_report_regeneration_changes_only_retired_live_arm_cards(monkeypatch) -> None:
    _freeze_report_clock(monkeypatch)
    baseline = _baseline_with_captured_arm_cards().encode("utf-8")
    regenerated = build_report(FIXTURE).read_bytes()
    assert regenerated == baseline


def test_report_regeneration_matches_pre_p0_dom_and_embedded_data(monkeypatch) -> None:
    """P1 semantic parity: canonical HTML structure + exact parsed data island."""
    _freeze_report_clock(monkeypatch)
    baseline_html = _baseline_with_captured_arm_cards()
    regenerated_html = build_report(FIXTURE).read_text(encoding="utf-8")

    assert canonicalize_html(regenerated_html) == canonicalize_html(baseline_html)
    assert _parse_embedded_data(regenerated_html) == _parse_embedded_data(baseline_html)
