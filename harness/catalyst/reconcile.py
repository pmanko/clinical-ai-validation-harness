"""Catalyst judge composites, three-pass median finalization, and gold precedence."""

from __future__ import annotations

from statistics import median
from typing import Any

BASE_WEIGHTS: dict[str, int] = {
    "intent_fidelity": 47,
    "sql_quality": 29,
    "schema_discipline": 24,
}

SUCCESSOR_WEIGHTS: dict[str, int] = {
    "intent_fidelity": 40,
    "sql_quality": 25,
    "schema_discipline": 20,
    "followup_coherence": 15,
}

BASE_AXES = tuple(BASE_WEIGHTS)
SUCCESSOR_AXES = tuple(SUCCESSOR_WEIGHTS)


def weights_for_turn(turn: int) -> dict[str, int]:
    if turn < 0:
        raise ValueError(f"turn must be >= 0, got {turn}")
    return SUCCESSOR_WEIGHTS if turn >= 1 else BASE_WEIGHTS


def axes_for_turn(turn: int) -> tuple[str, ...]:
    return SUCCESSOR_AXES if turn >= 1 else BASE_AXES


def composite_score(axes: dict[str, int], *, turn: int) -> int:
    """D6 composite: round(100 * Σ(w*axis) / (3 * Σ(w)))."""
    weights = weights_for_turn(turn)
    missing = [name for name in weights if name not in axes]
    if missing:
        raise ValueError(f"missing axes for turn {turn}: {missing}")
    weighted = sum(weights[name] * int(axes[name]) for name in weights)
    denom = 3 * sum(weights.values())
    return int(round(100 * weighted / denom))


def median_axes(pass_rows: list[dict[str, Any]]) -> dict[str, int]:
    if len(pass_rows) != 3:
        raise ValueError(f"exactly 3 pass rows required, got {len(pass_rows)}")
    turns = {int(row["turn"]) for row in pass_rows}
    if len(turns) != 1:
        raise ValueError(f"pass rows must share one turn, got {sorted(turns)}")
    turn = next(iter(turns))
    out: dict[str, int] = {}
    for axis in axes_for_turn(turn):
        values = [int(row[axis]) for row in pass_rows]
        out[axis] = int(median(values))
    return out


def _cell_key(row: dict[str, Any]) -> tuple[str, int, str]:
    return (str(row["scenario_id"]), int(row["turn"]), str(row["version_id"]))


def finalize_judge_row(pass_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Median applicable axes across three passes, then recompute composite."""
    if len(pass_rows) != 3:
        raise ValueError(f"exactly 3 pass rows required, got {len(pass_rows)}")
    keys = {_cell_key(row) for row in pass_rows}
    if len(keys) != 1:
        raise ValueError(f"pass rows must share scenario/turn/version, got {keys}")

    ordered = sorted(pass_rows, key=lambda row: int(row["repetition"]))
    reps = [int(row["repetition"]) for row in ordered]
    if reps != [1, 2, 3]:
        raise ValueError(f"repetitions must be 1..3, got {reps}")

    for field in ("provider", "model", "model_version", "rubric_sha256"):
        values = {row[field] for row in ordered}
        if len(values) != 1:
            raise ValueError(f"mixed {field} across passes: {sorted(values)}")

    turn = int(ordered[0]["turn"])
    axes = median_axes(ordered)
    # Middle pass supplies rationales / evidence / identity; axes+composite are recomputed.
    finalized = dict(ordered[1])
    finalized.update(axes)
    finalized["composite"] = composite_score(axes, turn=turn)
    finalized["repetition"] = 2
    if turn == 0:
        finalized.pop("followup_coherence", None)
        finalized.pop("followup_coherence_rationale", None)
    return finalized


def merge_gold_and_judge(
    *,
    gold_passed: bool,
    judge_row: dict[str, Any] | None,
) -> dict[str, Any]:
    """D7 hard precedence: gold FAIL always reports FAIL, even with a perfect judge."""
    judge_composite = None if judge_row is None else judge_row.get("composite")
    reported = "PASS" if gold_passed else "FAIL"
    return {
        "reported": reported,
        "gold_passed": bool(gold_passed),
        "judge_composite": judge_composite,
        "judge_advisory": judge_row,
    }
