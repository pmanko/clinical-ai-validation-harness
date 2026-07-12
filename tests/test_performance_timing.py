from harness.validate.performance_timing import derive_answer_timing


def test_answer_performance_is_derived_from_stage_timings_through_resolve_refs():
    timing = derive_answer_timing(
        [
            {"role": "stage_timing", "stage": "context", "status": "completed", "duration_ms": 10},
            {"role": "stage_timing", "stage": "answer", "status": "completed", "duration_ms": 80},
            {"role": "stage_timing", "stage": "gate", "status": "completed", "duration_ms": 5},
            {"role": "stage_timing", "stage": "resolve_refs", "status": "completed", "duration_ms": 5},
            {"role": "stage_timing", "stage": "review", "status": "completed", "duration_ms": 999},
        ]
    )
    assert timing == {
        "answer_to_done_ms": 100,
        "answer_stage_ms": 80,
        "pipeline_overhead_ms": 20,
        "pipeline_overhead_ratio": 0.2,
    }


def test_answer_performance_requires_completed_answer_and_resolve_refs():
    assert derive_answer_timing(
        [{"role": "stage_timing", "stage": "answer", "status": "cancelled", "duration_ms": 80}]
    ) is None
