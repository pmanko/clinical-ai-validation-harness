"""Normalize med-agent-hub stage timing trace records for report surfaces."""

from __future__ import annotations

from typing import Any


def extract_stage_timings(trace: Any) -> list[dict[str, Any]]:
    if not isinstance(trace, dict):
        return []
    timings: list[dict[str, Any]] = []
    for step in trace.get("steps") or []:
        if not isinstance(step, dict) or step.get("role") != "stage_timing":
            continue
        stage = str(step.get("stage") or "").strip()
        duration = step.get("duration_ms")
        occurrence = step.get("occurrence", 1)
        if not stage or not isinstance(duration, (int, float)) or duration < 0:
            continue
        timings.append(
            {
                "stage": stage,
                "occurrence": occurrence if isinstance(occurrence, int) else 1,
                "duration_ms": round(duration),
                "status": str(step.get("status") or "completed"),
            }
        )
    return timings


def stage_timing_label(timing: dict[str, Any]) -> str:
    stage = str(timing.get("stage") or "stage").replace("_", " ")
    occurrence = timing.get("occurrence")
    return f"{stage} {occurrence}" if occurrence and occurrence > 1 else stage


def expected_stage_labels(stages: Any) -> list[str]:
    if not isinstance(stages, (list, tuple)):
        return []
    occurrences: dict[str, int] = {}
    labels: list[str] = []
    for value in stages:
        stage = str(value or "").strip()
        if not stage:
            continue
        occurrences[stage] = occurrences.get(stage, 0) + 1
        labels.append(
            stage.replace("_", " ")
            + (f" {occurrences[stage]}" if occurrences[stage] > 1 else "")
        )
    return labels
