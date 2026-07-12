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


def test_cancelled_stage_duration_is_reported_separately(monkeypatch):
    trace = {
        "steps": [
            {
                "role": "stage_timing",
                "stage": "indepth",
                "occurrence": 1,
                "duration_ms": 47,
                "status": "cancelled",
            }
        ]
    }
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: trace)

    rows = report._summary_rows(
        [{"backend_id": "b", "metrics": {"latency_ms": 47, "citation_count": 0}}],
        ["b"],
        {"b": "Backend"},
        [trace],
        {"b": {"stages": ["indepth"]}},
    )

    assert rows[0]["stage_latency_ms"]["indepth"] == {
        "avg_ms": None,
        "completed": 0,
        "failed": 0,
        "avg_failed_ms": None,
        "cancelled": 1,
        "avg_cancelled_ms": 47,
        "observed": 1,
        "expected": 1,
    }


def test_cell_blob_exposes_stage_timings_for_detail_renderer(monkeypatch):
    trace = {
        "steps": [
            {
                "role": "stage_timing",
                "stage": "gather",
                "occurrence": 1,
                "duration_ms": 321,
                "status": "completed",
            }
        ]
    }
    monkeypatch.setattr(report, "_trace_for_row", lambda _row, _traces: trace)

    cell = report._cell_blob(
        {
            "response": {"answer": "Answer", "references": [], "blocks": []},
            "metrics": {"latency_ms": 400, "http_status": 200},
        },
        [trace],
    )

    assert cell["stage_timings"] == [
        {
            "stage": "gather",
            "occurrence": 1,
            "duration_ms": 321,
            "status": "completed",
        }
    ]
    assert "Average latency by stage" in report._SCRIPT
    assert "renderStageTimings(cell.stage_timings)" in report._SCRIPT
