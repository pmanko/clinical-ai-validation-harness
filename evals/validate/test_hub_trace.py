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
    """Dashboard and report paths share the same bounded matching semantics."""
    traces = [
        {"level_id": "arm-x", "ts": "2026-06-05T10:00:03+00:00", "n": 1},
        {"level_id": "arm-x", "ts": "2026-06-05T10:00:08+00:00", "n": 2},
        {"level_id": "arm-x", "ts": "2026-06-05T10:00:25+00:00", "n": 3},
    ]
    matched = match_trace(
        traces,
        "arm-x",
        "2026-06-05T10:00:05+00:00",
        "2026-06-05T10:00:10+00:00",
    )
    assert matched and matched["n"] == 2


def test_gate_for_row_present_and_absent(monkeypatch):
    monkeypatch.setattr(
        "harness.validate.report.arm_model_name",
        lambda backend_id, **_: backend_id,
    )
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


def test_match_trace_prefers_same_question_and_nearest_completion_over_next_cell():
    traces = [
        {
            "level_id": "eval-e4b-temporal-enforce",
            "ts": "2026-07-14T05:37:50.295000+00:00",
            "question": "What has been ordered for this patient over the past 6 months?",
        },
        {
            "level_id": "eval-e4b-temporal-enforce",
            "ts": "2026-07-14T05:37:52.319000+00:00",
            "question": "How has this child's growth changed?",
        },
    ]

    matched = match_trace(
        traces,
        "eval-e4b-temporal-enforce",
        "2026-07-14T05:37:38.052000+00:00",
        "2026-07-14T05:37:50.297000+00:00",
        question="What has been ordered for this patient over the past 6 months?",
    )

    assert matched is traces[0]


def test_match_trace_prefers_stable_session_when_questions_repeat():
    from harness.validate.hub_trace import match_trace

    traces = [
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:37:50+00:00",
            "question": "Repeat question",
            "correlation": {"session": "session-a"},
        },
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:37:51+00:00",
            "question": "Repeat question",
            "correlation": {"session": "session-b"},
        },
    ]

    matched = match_trace(
        traces,
        "profile",
        "2026-07-14T05:37:40+00:00",
        "2026-07-14T05:37:52+00:00",
        question="Repeat question",
        session="session-a",
    )

    assert matched is traces[0]


def test_match_trace_prefers_turn_unique_request_id_within_one_session():
    from harness.validate.hub_trace import match_trace

    traces = [
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:37:50+00:00",
            "question": "Repeat question",
            "correlation": {"session": "session-a", "request_id": "request-a"},
        },
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:37:51+00:00",
            "question": "Repeat question",
            "correlation": {"session": "session-a", "request_id": "request-b"},
        },
    ]

    matched = match_trace(
        traces,
        "profile",
        "2026-07-14T05:37:40+00:00",
        "2026-07-14T05:37:52+00:00",
        question="Repeat question",
        session="session-a",
        request_id="request-a",
    )

    assert matched is traces[0]


def test_match_trace_exact_request_id_outweighs_clock_window():
    from harness.validate.hub_trace import match_trace

    traces = [
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:00:00+00:00",
            "question": "Same question",
            "correlation": {"request_id": "exact-request"},
        },
        {
            "level_id": "profile",
            "ts": "2026-07-14T06:00:01+00:00",
            "question": "Same question",
            "correlation": {"request_id": "adjacent-request"},
        },
    ]

    matched = match_trace(
        traces,
        "profile",
        "2026-07-14T06:00:00+00:00",
        "2026-07-14T06:00:02+00:00",
        question="Same question",
        request_id="exact-request",
    )

    assert matched is traces[0]


def test_match_trace_exact_request_id_rejects_explicit_session_or_question_mismatch():
    from harness.validate.hub_trace import match_trace

    traces = [
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:00:00+00:00",
            "question": "Recorded question",
            "correlation": {
                "request_id": "exact-request",
                "session": "recorded-session",
            },
        }
    ]

    common = {
        "traces": traces,
        "backend": "profile",
        "started_at": "2026-07-14T06:00:00+00:00",
        "ended_at": "2026-07-14T06:00:02+00:00",
        "request_id": "exact-request",
    }
    assert match_trace(**common, session="different-session") is None
    assert match_trace(**common, question="Different question") is None


def test_match_trace_mixed_versions_allow_bounded_keyless_fallback():
    from harness.validate.hub_trace import match_trace

    traces = [
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:00:00+00:00",
            "question": "Historical question",
        },
        {
            "level_id": "profile",
            "ts": "2026-07-14T07:00:00+00:00",
            "question": "Unrelated modern question",
            "correlation": {"request_id": "unrelated-request"},
        },
    ]

    matched = match_trace(
        traces,
        "profile",
        "2026-07-14T04:59:58+00:00",
        "2026-07-14T05:00:02+00:00",
        question="Historical question",
        request_id="client-generated-but-unsent",
    )

    assert matched is traces[0]


def test_match_trace_does_not_borrow_trace_with_different_request_id():
    from harness.validate.hub_trace import match_trace

    traces = [
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:37:50+00:00",
            "question": "Same question",
            "correlation": {"session": "session-a", "request_id": "another-request"},
        }
    ]

    assert (
        match_trace(
            traces,
            "profile",
            "2026-07-14T05:37:40+00:00",
            "2026-07-14T05:37:52+00:00",
            question="Same question",
            session="session-a",
            request_id="wanted-request",
        )
        is None
    )


def test_match_trace_does_not_borrow_trace_with_different_session():
    from harness.validate.hub_trace import match_trace

    traces = [
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:37:50+00:00",
            "question": "Same question",
            "correlation": {"session": "another-session"},
        }
    ]

    assert (
        match_trace(
            traces,
            "profile",
            "2026-07-14T05:37:40+00:00",
            "2026-07-14T05:37:52+00:00",
            question="Same question",
            session="wanted-session",
        )
        is None
    )


def test_match_trace_does_not_borrow_trace_with_different_question():
    from harness.validate.hub_trace import match_trace

    traces = [
        {
            "level_id": "profile",
            "ts": "2026-07-14T05:37:50+00:00",
            "question": "Adjacent question",
        }
    ]

    assert (
        match_trace(
            traces,
            "profile",
            "2026-07-14T05:37:40+00:00",
            "2026-07-14T05:37:52+00:00",
            question="Wanted question",
        )
        is None
    )
