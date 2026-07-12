"""Derive answer latency summaries from the canonical stage_timing trace schema."""

from __future__ import annotations

from typing import Any


def derive_answer_timing(steps: list[dict[str, Any]]) -> dict[str, int | float] | None:
    answer_stage_ms: int | None = None
    answer_to_done_ms = 0
    reached_answer_done = False
    for step in steps:
        if step.get("role") != "stage_timing" or step.get("status") != "completed":
            continue
        duration = step.get("duration_ms")
        if not isinstance(duration, (int, float)) or duration < 0:
            continue
        elapsed = round(duration)
        answer_to_done_ms += elapsed
        if step.get("stage") == "answer" and answer_stage_ms is None:
            answer_stage_ms = elapsed
        if step.get("stage") == "resolve_refs":
            reached_answer_done = True
            break
    if answer_stage_ms is None or not reached_answer_done:
        return None
    overhead = max(0, answer_to_done_ms - answer_stage_ms)
    return {
        "answer_to_done_ms": answer_to_done_ms,
        "answer_stage_ms": answer_stage_ms,
        "pipeline_overhead_ms": overhead,
        "pipeline_overhead_ratio": (
            round(overhead / answer_to_done_ms, 4) if answer_to_done_ms else 0.0
        ),
    }
