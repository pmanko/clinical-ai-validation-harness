from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from harness.validate.report import build_report

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "validate-run-golden"
_FROZEN = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


def _freeze_report_clock(monkeypatch) -> None:
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return _FROZEN if tz is None else _FROZEN.astimezone(tz)

    monkeypatch.setattr("harness.validate.report.datetime", _FrozenDateTime)


def test_report_regeneration_emits_deterministic_v2_json_packets(monkeypatch, tmp_path: Path) -> None:
    _freeze_report_clock(monkeypatch)
    run_copy = tmp_path / "run"
    shutil.copytree(FIXTURE, run_copy)

    out_path = build_report(run_copy)
    assert out_path == run_copy / "report-data.json"
    assert (run_copy / "run-summary.json").is_file()
    assert (run_copy / "dashboard-data.json").is_file()

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["schema"] == "openclinai.report.v2"
    assert data["schema_version"] == 2
    assert data["generated_at"] == "2026-07-21T12:00:00+00:00"
    assert len(data["runs"]) == 1

    run = data["runs"][0]
    meta_path = FIXTURE / "run_meta.json"
    frozen = json.loads(meta_path.read_text(encoding="utf-8")).get("arm_cards", {}) if meta_path.exists() else {}
    assert run["arm_cards"] == {bid: frozen.get(bid) for bid in run["backends"]}

    # Regenerate a second time and verify byte-for-byte determinism
    first_bytes = out_path.read_bytes()
    second_bytes = build_report(run_copy).read_bytes()
    assert first_bytes == second_bytes
