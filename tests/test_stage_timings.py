from harness.validate.stage_timings import (
    expected_stage_labels,
    extract_stage_timings,
    stage_timing_label,
)
from harness.validate import report


def test_extract_stage_timings_ignores_non_timing_and_malformed_steps():
    trace = {
        "steps": [
            {"role": "answer_synth", "model": "m"},
            {"role": "stage_timing", "stage": "context", "occurrence": 1, "duration_ms": 12.4},
            {"role": "stage_timing", "stage": "gate", "occurrence": 2, "duration_ms": 0},
            {"role": "stage_timing", "stage": "review", "duration_ms": -1},
        ]
    }

    timings = extract_stage_timings(trace)

    assert timings == [
        {"stage": "context", "occurrence": 1, "duration_ms": 12, "status": "completed"},
        {"stage": "gate", "occurrence": 2, "duration_ms": 0, "status": "completed"},
    ]
    assert [stage_timing_label(timing) for timing in timings] == ["context", "gate 2"]
    assert expected_stage_labels(["context", "gate", "review", "gate"]) == [
        "context",
        "gate",
        "review",
        "gate 2",
    ]


def test_report_aggregates_stage_latency_by_backend(monkeypatch):
    trace = {
        "steps": [
            {"role": "stage_timing", "stage": "answer", "occurrence": 1, "duration_ms": 100},
            {"role": "stage_timing", "stage": "gate", "occurrence": 1, "duration_ms": 2},
        ]
    }
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: trace)
    rows = report._summary_rows(
        [
            {"backend_id": "b", "metrics": {"latency_ms": 120, "citation_count": 1}},
            {"backend_id": "b", "metrics": {"latency_ms": 130, "citation_count": 1}},
        ],
        ["b"],
        {"b": "Backend"},
        [trace],
        {"b": {"stages": ["context", "answer", "gate", "review"]}},
    )

    assert rows[0]["stage_latency_ms"] == {
        "context": {
            "avg_ms": None,
            "completed": 0,
            "failed": 0,
            "avg_failed_ms": None,
            "cancelled": 0,
            "avg_cancelled_ms": None,
            "observed": 0,
            "expected": 2,
        },
        "answer": {
            "avg_ms": 100,
            "completed": 2,
            "failed": 0,
            "avg_failed_ms": None,
            "cancelled": 0,
            "avg_cancelled_ms": None,
            "observed": 2,
            "expected": 2,
        },
        "gate": {
            "avg_ms": 2,
            "completed": 2,
            "failed": 0,
            "avg_failed_ms": None,
            "cancelled": 0,
            "avg_cancelled_ms": None,
            "observed": 2,
            "expected": 2,
        },
        "review": {
            "avg_ms": None,
            "completed": 0,
            "failed": 0,
            "avg_failed_ms": None,
            "cancelled": 0,
            "avg_cancelled_ms": None,
            "observed": 0,
            "expected": 2,
        },
    }


def test_failed_stage_duration_is_not_reported_as_completed_latency(monkeypatch):
    trace = {
        "steps": [
            {
                "role": "stage_timing",
                "stage": "answer",
                "occurrence": 1,
                "duration_ms": 80,
                "status": "failed",
            }
        ]
    }
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: trace)

    rows = report._summary_rows(
        [{"backend_id": "b", "metrics": {"latency_ms": 80, "citation_count": 0}}],
        ["b"],
        {"b": "Backend"},
        [trace],
        {"b": {"stages": ["answer"]}},
    )

    assert rows[0]["stage_latency_ms"]["answer"] == {
        "avg_ms": None,
        "completed": 0,
        "failed": 1,
        "avg_failed_ms": 80,
        "cancelled": 0,
        "avg_cancelled_ms": None,
        "observed": 1,
        "expected": 1,
    }
