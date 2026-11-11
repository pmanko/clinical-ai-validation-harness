"""Shared numeric helpers for report-family distribution charts."""

from __future__ import annotations

from typing import Any


def ordered_unique(values: list[Any]) -> list[Any]:
    seen: dict[Any, None] = {}
    for v in values:
        seen.setdefault(v, None)
    return list(seen)


def avg(nums: list[int]) -> int:
    return round(sum(nums) / len(nums)) if nums else 0


def box_stats(values: list[float]) -> dict[str, Any] | None:
    """Five-number summary + Tukey whiskers/outliers + mean for a box-and-whisker
    plot. Quartiles use linear interpolation. Returns None for an empty series."""
    xs = sorted(v for v in values if v is not None)
    n = len(xs)
    if n == 0:
        return None

    def _q(p: float) -> float:
        if n == 1:
            return float(xs[0])
        idx = p * (n - 1)
        lo = int(idx)
        frac = idx - lo
        return xs[lo] + (xs[min(lo + 1, n - 1)] - xs[lo]) * frac

    q1, med, q3 = _q(0.25), _q(0.5), _q(0.75)
    iqr = q3 - q1
    lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inliers = [x for x in xs if lo_fence <= x <= hi_fence]
    return {
        "n": n,
        "min": xs[0],
        "max": xs[-1],
        "q1": round(q1, 2),
        "median": round(med, 2),
        "q3": round(q3, 2),
        "whisker_lo": min(inliers) if inliers else xs[0],
        "whisker_hi": max(inliers) if inliers else xs[-1],
        "outliers": [x for x in xs if x < lo_fence or x > hi_fence],
        "mean": round(sum(xs) / n, 1),
    }


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile of a non-empty sorted-able list (p in [0,1])."""
    xs = sorted(values)
    n = len(xs)
    if n == 0:
        return 0.0
    if n == 1:
        return float(xs[0])
    idx = p * (n - 1)
    lo = int(idx)
    return xs[lo] + (xs[min(lo + 1, n - 1)] - xs[lo]) * (idx - lo)


def robust_axis_max(series: list[dict[str, Any]], all_values: list[float]) -> float:
    """Robust y-axis ceiling so a lone extreme outlier can't squish every box.

    Bound is the upper Tukey fence (Q3 + 1.5·IQR) of the pooled values, falling
    back to global p95 when the fence is degenerate. Floored at the widest arm's
    box top (max q3) and at the global max when nothing is extreme.
    """
    if not all_values:
        return 0.0
    q1 = percentile(all_values, 0.25)
    q3 = percentile(all_values, 0.75)
    iqr = q3 - q1
    fence = q3 + 1.5 * iqr if iqr > 0 else percentile(all_values, 0.95)
    box_top = max((s.get("q3", 0) or 0) for s in series) if series else 0.0
    data_max = max(all_values)
    return float(min(data_max, max(fence, box_top)))
