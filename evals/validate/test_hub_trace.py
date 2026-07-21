import json

from harness.validate.hub_trace import load_traces, match_trace
from harness.validate.report import _gate_for_row


def test_load_traces_parses_jsonl_and_tolerates_junk(tmp_path):
    f = tmp_path / "trace.jsonl"
    f.write_text(
        json.dumps({"level_id": "a", "ts": "2026-06-05T10:00:00+00:00"}) + "\n"
        + "not-json\n"
        + json.dumps({"level_id": "b", "ts": "2026-06-05T10:01:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    traces = load_traces(f)
    assert [t["level_id"] for t in traces] == ["a", "b"]      # the junk line is skipped
    assert load_traces(tmp_path / "missing.jsonl") == []      # absent file -> []


def test_match_trace_correlates_by_level_and_time_window():
    traces = [
        {"level_id": "med-validated", "ts": "2026-06-05T10:00:05+00:00", "answer_confidence": {"level": "green"}},
        {"level_id": "med-validated", "ts": "2026-06-05T10:02:30+00:00", "answer_confidence": {"level": "red"}},
        {"level_id": "low-validated", "ts": "2026-06-05T10:00:06+00:00", "answer_confidence": {"level": "yellow"}},
    ]
    # in-window, right level -> the 10:00:05 green (not the 10:02 one, not the low one)
    m = match_trace(traces, "med-validated", "2026-06-05T10:00:00+00:00", "2026-06-05T10:00:20+00:00")
    assert m and m["answer_confidence"]["level"] == "green"
    # no trace in the window -> None; wrong backend -> None; bad timestamps -> None
    assert match_trace(traces, "med-validated", "2026-06-05T09:00:00+00:00", "2026-06-05T09:00:20+00:00") is None
    assert match_trace(traces, "high-validated", "2026-06-05T10:00:00+00:00", "2026-06-05T10:00:20+00:00") is None
    assert match_trace(traces, "med-validated", None, None) is None


def test_match_trace_dashboard_style_latest_match_and_slack():
    """Dashboard previously inlined this helper; keep the shared semantics covered."""
    traces = [
        {"level_id": "arm-x", "ts": "2026-06-05T10:00:03+00:00", "n": 1},
        {"level_id": "arm-x", "ts": "2026-06-05T10:00:08+00:00", "n": 2},
        {"level_id": "arm-x", "ts": "2026-06-05T10:00:25+00:00", "n": 3},
    ]
    # window [10:00:05, 10:00:10]: first is in via -5s slack; second is inside; keep latest
    m = match_trace(traces, "arm-x", "2026-06-05T10:00:05+00:00", "2026-06-05T10:00:10+00:00")
    assert m and m["n"] == 2
    # third is outside even with +5s slack on ended_at (10:00:15)
    assert match_trace(traces, "arm-x", "2026-06-05T10:00:05+00:00", "2026-06-05T10:00:10+00:00")["n"] != 3


def test_gate_for_row_present_and_absent(monkeypatch):
    monkeypatch.setattr("harness.validate.report.arm_model_name", lambda backend_id, **_: backend_id)
    traces = [
        {
            "level_id": "arm-a",
            "ts": "2026-06-05T10:00:05+00:00",
            "temporal_gate": {"status": "pass", "delta_days": 0},
        }
    ]
    row = {
        "backend_id": "arm-a",
        "started_at": "2026-06-05T10:00:00+00:00",
        "ended_at": "2026-06-05T10:00:20+00:00",
    }
    assert _gate_for_row(row, traces) == {"status": "pass", "delta_days": 0}
    assert _gate_for_row(row, []) is None
    assert _gate_for_row({**row, "backend_id": "other"}, traces) is None
