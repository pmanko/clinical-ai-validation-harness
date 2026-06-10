import json

from harness.validate.hub_trace import load_traces


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
    from harness.validate.hub_trace import match_trace
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
