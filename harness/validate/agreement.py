"""Chance-corrected agreement between judge passes: Krippendorff's alpha.

One unit is one cell; its ratings are the values the passes gave it. Alpha is 1 for perfect
agreement, 0 for what chance would give, negative below that. ``level`` is ``"ordinal"`` for
the 0-10 axes (a disagreement of one point counts less than one of five) and ``"nominal"`` for
labels (any disagreement counts the same). Units with fewer than two ratings are left out,
so a pass that skipped a cell does not break the measure. Thresholds in use in the
literature: 0.667 acceptable, 0.8 good (Krippendorff 2004); a page states which it applies.

Stdlib only, like ``adjudicate.weighted_kappa``.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Hashable, Sequence

THRESHOLDS = {"acceptable": 0.667, "good": 0.8}


def krippendorff_alpha(units: Sequence[Sequence[Hashable]], level: str = "nominal",
                       order: Sequence[Hashable] | None = None) -> float | None:
    """Alpha over ``units`` (each a sequence of ratings). Returns None when fewer than two
    units carry two ratings, or when every rating is the same (no disagreement to correct)."""
    usable = [[v for v in u if v is not None] for u in units]
    usable = [u for u in usable if len(u) >= 2]
    if len(usable) < 2:
        return None
    values = sorted({v for u in usable for v in u}, key=lambda v: _rank(v, order))
    if len(values) < 2:
        return None
    # Coincidence matrix: each unit contributes its ordered pairs, weighted by 1/(m-1).
    co: Counter = Counter()
    for u in usable:
        m = len(u)
        for i, c in enumerate(u):
            for j, k in enumerate(u):
                if i != j:
                    co[(c, k)] += 1.0 / (m - 1)
    n_c = {c: sum(co[(c, k)] for k in values) for c in values}
    n = sum(n_c.values())
    if n <= 1:
        return None

    def delta2(c: Hashable, k: Hashable) -> float:
        if c == k:
            return 0.0
        if level == "nominal":
            return 1.0
        lo, hi = sorted((c, k), key=lambda v: _rank(v, order or values))
        between = [g for g in values if _rank(lo, order or values) <= _rank(g, order or values)
                   <= _rank(hi, order or values)]
        return (sum(n_c[g] for g in between) - (n_c[c] + n_c[k]) / 2) ** 2

    d_o = sum(co[(c, k)] * delta2(c, k) for c in values for k in values) / n
    d_e = sum(n_c[c] * n_c[k] * delta2(c, k) for c in values for k in values) / (n * (n - 1))
    if d_e == 0:
        return None
    return round(1.0 - d_o / d_e, 3)


def _rank(value: Hashable, order: Sequence[Hashable] | None) -> float:
    if order is not None and value in order:
        return float(list(order).index(value))
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("inf")


def verdict(alpha: float | None) -> str:
    """The threshold band an alpha falls in, named on the page beside the number."""
    if alpha is None:
        return "not measurable"
    if alpha >= THRESHOLDS["good"]:
        return "good"
    if alpha >= THRESHOLDS["acceptable"]:
        return "acceptable"
    return "below acceptable"


def pass_agreement(actor_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Alpha per axis across the passes in ``actor_rows`` (actor id -> judge rows), plus the
    cells whose Benchmark spread across passes is largest. Shape is what the page shows."""
    from .reconcile import cell_benchmark_score

    cells: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for actor, rows in actor_rows.items():
        for r in rows:
            cells.setdefault((r["scenario_id"], r["backend_id"]), {})[actor] = r
    axes = {
        "accuracy": "ordinal", "completeness": "ordinal", "relevance": "ordinal",
        "harm": "nominal", "abstention_outcome": "nominal", "citation_groundedness": "nominal",
    }
    alpha = {}
    for axis, level in axes.items():
        units = [[r.get(axis) for r in by_actor.values()] for by_actor in cells.values()]
        value = krippendorff_alpha(units, level)
        alpha[axis] = {"alpha": value, "level": level, "verdict": verdict(value)}
    spread = []
    for (scenario, backend), by_actor in cells.items():
        scores = {a: cell_benchmark_score(r) for a, r in by_actor.items()}
        nums = [s for s in scores.values() if s is not None]
        if len(nums) >= 2:
            spread.append({"scenario_id": scenario, "backend_id": backend,
                           "scores": scores, "range": round(max(nums) - min(nums), 1)})
    spread.sort(key=lambda s: (-s["range"], s["scenario_id"], s["backend_id"]))
    return {"schema_version": "judge_consensus.v1", "actors": sorted(actor_rows),
            "n_cells": len(cells), "alpha": alpha, "thresholds": dict(THRESHOLDS),
            "spread_cells": spread[:10]}
