"""WS4 guided adjudication — the statistics + sampling core.

This is the layer that turns LLM-judge scores into a *clinician-calibrated*
benchmark with a confidence interval. It answers three questions a human reviewer
faces on a fresh run:

  1. Which cells should I look at?  -> sample_cells(...)  (priority defects +
     a seeded random calibration set; the random part is what makes the stats valid)
  2. Do I agree with the judge?     -> agreement(...) via weighted_kappa(...)
     (linearly-weighted Cohen's kappa on the ordinal accuracy/completeness/relevance axes)
  3. What is the run's TRUE mean Benchmark, given the judge is biased?
     -> ppi_benchmark(...) — Prediction-Powered Inference: use the cheap judge score
     on ALL cells, and correct its bias with the small human-labeled subset, getting a
     point estimate AND a 95% CI that is tighter than reviewing the labeled cells alone.

Dependency-light by design: stdlib `math` / `random` only (no numpy / sklearn /
scipy). The cell -> 0-100 Benchmark scoring is reused from reconcile.py so the human
and the judge are scored by the IDENTICAL composite.

References:
- PPI: Angelopoulos et al., "Prediction-Powered Inference" (2023). The mean estimator
  used here is the rectified estimator theta = mean_all(f) + mean_L(y - f) with the two
  independent-variance terms, which is the standard PPI mean for an i.i.d. labeled subset.
- Linearly-weighted kappa: Cohen (1968); weights w_ij = |i-j|/(k-1).
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Any

from .reconcile import cell_benchmark_score

__all__ = [
    "sample_cells",
    "weighted_kappa",
    "agreement",
    "ppi_benchmark",
    "adjudication_record",
]

# Ordinal axes scored 0-10 by both judge and human; the axes kappa is computed over.
_ORDINAL_AXES = ("accuracy", "completeness", "relevance")
_Z_95 = 1.959963984540054  # two-sided 95% normal quantile


# --------------------------------------------------------------------------- #
# 1. sampling — which cells a human reviews
# --------------------------------------------------------------------------- #
def _cell_id(row: dict[str, Any]) -> tuple[Any, Any]:
    return (row.get("scenario_id"), row.get("backend_id"))


def _is_priority(row: dict[str, Any]) -> bool:
    """A cell that, on its face, MIGHT be a safety/grounding defect — the cells worth a
    human's scarce attention regardless of budget."""
    if row.get("harm"):
        return True
    if row.get("abstention_outcome") == "failed-to-abstain":
        return True
    if row.get("citation_groundedness") in {"partly", "unsupported"}:
        return True
    return False


def _why_priority(row: dict[str, Any]) -> str:
    reasons = []
    if row.get("harm"):
        reasons.append("harm")
    if row.get("abstention_outcome") == "failed-to-abstain":
        reasons.append("failed-to-abstain")
    cg = row.get("citation_groundedness")
    if cg in {"partly", "unsupported"}:
        reasons.append(f"citation:{cg}")
    return "priority:" + ",".join(reasons)


def _as_cell(row: dict[str, Any], why: str) -> dict[str, Any]:
    """The reviewer-facing cell record: identity + provenance + the judge's own score
    (so a human sees what the machine thought before they grade)."""
    return {
        "scenario_id": row.get("scenario_id"),
        "backend_id": row.get("backend_id"),
        "why_selected": why,
        "cell_benchmark_score": cell_benchmark_score(row),
    }


def _priority_ordered(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """All flagged-defect cells, then the lowest-Benchmark cells. Stable + deterministic:
    sorted by (ascending benchmark score, cell id) so the worst cells lead. None scores
    sort first (treated as the most-uncertain)."""
    pri = [r for r in rows if _is_priority(r)]
    pri_ids = {_cell_id(r) for r in pri}

    def _score_key(r):
        s = cell_benchmark_score(r)
        return (s if s is not None else -1.0, str(_cell_id(r)))

    cells: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for r in sorted(pri, key=_score_key):
        cid = _cell_id(r)
        if cid not in seen:
            cells.append(_as_cell(r, _why_priority(r)))
            seen.add(cid)
    # then the remaining lowest-benchmark cells (the "worst answers" a reviewer should
    # spot-check even without a categorical flag).
    rest = sorted((r for r in rows if _cell_id(r) not in pri_ids), key=_score_key)
    for r in rest:
        cid = _cell_id(r)
        if cid not in seen:
            cells.append(_as_cell(r, "low-benchmark"))
            seen.add(cid)
    return cells


def _seeded_sample(pool: list[dict[str, Any]], k: int, seed: int) -> list[dict[str, Any]]:
    """k cells drawn without replacement from `pool`, deterministic given seed. Sorted by
    cell id first so the draw is independent of input row order."""
    if k <= 0 or not pool:
        return []
    ordered = sorted(pool, key=lambda r: str(_cell_id(r)))
    rng = random.Random(seed)
    return rng.sample(ordered, min(k, len(ordered)))


def sample_cells(judge_rows: list[dict[str, Any]], mode: str, n: int | None = None,
                 seed: int = 0) -> list[dict[str, Any]]:
    """Ordered list of cells a human should review, deterministic given `seed`.

    mode:
      "triage"   -> EVERY priority cell (harm / failed-to-abstain / partly|unsupported
                    citation) + the lowest-Benchmark cells + a small SEEDED random
                    calibration set. The random component is REQUIRED — PPI's rectifier
                    is only unbiased over a random labeled subset. Priority first,
                    random last; deduped.
      "standard" -> triage + a stratified random sample of ~1 extra cell per scenario.
      "full"     -> every judged cell.
      "budget"   -> the `n` most-informative cells (priority order), capped at n.

    If `n` is given (any mode), the returned list is capped at the n most-informative
    cells (priority order preserved). Each returned dict carries scenario_id, backend_id,
    why_selected and the judge's cell_benchmark_score.
    """
    rows = list(judge_rows or [])

    if mode == "full":
        cells = _priority_ordered(rows)  # every cell, worst-first, with provenance
        return cells[:n] if n is not None else cells

    if mode not in {"triage", "standard", "budget"}:
        raise ValueError(
            f"unknown mode {mode!r} (expected triage|standard|full|budget)")

    if mode == "budget":
        if n is None:
            raise ValueError("mode='budget' requires n")
        return _priority_ordered(rows)[:n]

    # triage / standard share the priority spine, then append a seeded random tail.
    pri_cells = [c for c in _priority_ordered(rows) if c["why_selected"].startswith("priority:")]
    pri_ids = {(c["scenario_id"], c["backend_id"]) for c in pri_cells}
    nonpri = [r for r in rows if _cell_id(r) not in pri_ids]

    # Calibration random set: small fixed-fraction of the run (>=1 when any cell is
    # unflagged), seeded. This is the part PPI's CI leans on.
    calib_k = max(1, round(0.15 * len(rows))) if nonpri else 0
    calib = _seeded_sample(nonpri, calib_k, seed)
    calib_ids = {_cell_id(r) for r in calib}
    cells = list(pri_cells) + [_as_cell(r, "random-calibration") for r in calib]

    if mode == "standard":
        # Stratified add: ensure every scenario contributes >=1 reviewed cell, picking a
        # seeded representative backend per scenario.
        chosen_ids = pri_ids | calib_ids
        by_scenario: dict[Any, list[dict[str, Any]]] = {}
        for r in rows:
            by_scenario.setdefault(r.get("scenario_id"), []).append(r)
        for sid in sorted(by_scenario, key=str):
            if any(cid[0] == sid for cid in chosen_ids):
                continue
            pick = _seeded_sample(by_scenario[sid], 1, seed)
            if pick:
                r = pick[0]
                cells.append(_as_cell(r, "random-stratified"))
                chosen_ids.add(_cell_id(r))

    return cells[:n] if n is not None else cells


# --------------------------------------------------------------------------- #
# 2. weighted_kappa — judge<->human ordinal agreement
# --------------------------------------------------------------------------- #
def weighted_kappa(a: list[int], b: list[int], max_score: int = 10) -> float:
    """Linearly-weighted Cohen's kappa between two equal-length integer-score lists.

    Weights w_ij = |i-j| / (k-1) over the category grid 0..max_score (k = max_score+1),
    so a 1-point disagreement counts less than a far-apart one (the right model for an
    ordinal 0-10 rubric). Returns 1.0 for perfect agreement, 0.0 at chance, negative
    below chance.

    Conventions for degenerate inputs:
      - identical lists  -> 1.0 (even if all one category: no disagreement to penalize).
      - non-identical but zero expected disagreement (raters confined to a single shared
        category yet differing — impossible, but defended) -> 0.0.
    """
    if len(a) != len(b):
        raise ValueError("weighted_kappa: lists must be equal length")
    if not a:
        raise ValueError("weighted_kappa: empty input")
    if list(a) == list(b):
        return 1.0

    n = len(a)
    k = max_score  # denominator of the linear weight is (categories-1) = max_score-0

    # Observed weighted disagreement.
    do = sum(abs(ai - bi) for ai, bi in zip(a, b)) / (k * n)

    # Expected weighted disagreement under independence of the two marginals.
    cats = list(range(0, max_score + 1))
    pa = {c: a.count(c) / n for c in cats}
    pb = {c: b.count(c) / n for c in cats}
    de = 0.0
    for i in cats:
        if not pa[i]:
            continue
        for j in cats:
            if not pb[j]:
                continue
            de += pa[i] * pb[j] * (abs(i - j) / k)

    if de == 0.0:
        # No expected disagreement -> kappa undefined; by convention 0.0 (chance) when
        # the raters nonetheless differ.
        return 0.0
    return 1.0 - do / de


# --------------------------------------------------------------------------- #
# 3. agreement — per-axis + overall kappa on the reviewed cells
# --------------------------------------------------------------------------- #
def agreement(judge_rows: list[dict[str, Any]],
              adj_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-axis (accuracy/completeness/relevance) + overall linearly-weighted kappa
    between the judge and the human, matched on the cells the human reviewed.

    `adj_rows` are adjudication records (see adjudication_record). Matching is by
    (scenario_id, backend_id). Only cells present in BOTH and carrying an integer score
    on a given axis contribute to that axis. `overall` pools all axes into one kappa.
    Axes with <1 paired observation are None.
    """
    jindex = {_cell_id(r): r for r in judge_rows}

    paired: dict[str, tuple[list[int], list[int]]] = {ax: ([], []) for ax in _ORDINAL_AXES}
    for adj in adj_rows:
        jr = jindex.get(_cell_id(adj))
        if jr is None:
            continue
        axes = adj.get("axes", {})
        for ax in _ORDINAL_AXES:
            jv, hv = jr.get(ax), axes.get(ax)
            if _is_int(jv) and _is_int(hv):
                paired[ax][0].append(int(jv))
                paired[ax][1].append(int(hv))

    out: dict[str, Any] = {}
    all_j: list[int] = []
    all_h: list[int] = []
    for ax in _ORDINAL_AXES:
        js, hs = paired[ax]
        out[ax] = weighted_kappa(js, hs) if js else None
        all_j.extend(js)
        all_h.extend(hs)
    out["overall"] = weighted_kappa(all_j, all_h) if all_j else None
    out["n"] = len({_cell_id(a) for a in adj_rows if _cell_id(a) in jindex})
    return out


# --------------------------------------------------------------------------- #
# 4. ppi_benchmark — Prediction-Powered Inference for the run's mean Benchmark
# --------------------------------------------------------------------------- #
def _human_cell_score(adj: dict[str, Any]) -> float | None:
    """Recompute the 0-100 Benchmark from the HUMAN's adjudicated scores, using the
    SAME composite the judge cell uses (reconcile.cell_benchmark_score). The human's
    per-axis grades + harm flag are mapped onto a synthetic row so the scoring is
    identical to the judge path."""
    axes = adj.get("axes", {})
    row: dict[str, Any] = {
        "accuracy": axes.get("accuracy"),
        "completeness": axes.get("completeness"),
        "relevance": axes.get("relevance"),
        "harm": adj.get("harm"),
    }
    # Carry through any categorical defects the human re-graded (abstention / citation /
    # temporal) so a human correction of those also moves the score.
    for key in ("abstention_outcome", "citation_groundedness",
                "temporal_date_accuracy", "temporal_window", "temporal_trend"):
        if key in axes:
            row[key] = axes[key]
    return cell_benchmark_score(row)


def ppi_benchmark(judge_rows: list[dict[str, Any]],
                  adj_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Prediction-Powered Inference point estimate + 95% CI for the run's mean Benchmark.

    f_i = the judge's cell Benchmark for ALL judged cells.
    y_i = the human's recomputed cell Benchmark for the reviewed subset L.

    Point:  theta = mean_all(f) + mean_L(y - f)      (rectifier corrects judge bias on L)
    Var:    Var(mean_all f) + Var_L(y - f) / |L|     (two independent terms)
    CI:     theta +/- 1.96 * sqrt(Var)

    Guards:
      - |L| == 0           -> judge_only_mean as the point, ci_low/ci_high = None + a note.
      - |L| == n_all (full) -> CI straight from the labeled set (the judge term vanishes;
                               the estimate IS the human mean).

    Returns {point, ci_low, ci_high, n_all, n_labeled, judge_only_mean, rectifier, note?}.
    """
    f_all = [cell_benchmark_score(r) for r in judge_rows]
    f_all = [s for s in f_all if s is not None]
    n_all = len(f_all)
    if n_all == 0:
        return {"point": None, "ci_low": None, "ci_high": None, "n_all": 0,
                "n_labeled": 0, "judge_only_mean": None, "rectifier": None,
                "note": "no judged cells with a numeric Benchmark"}

    judge_only_mean = statistics.fmean(f_all)
    jindex = {_cell_id(r): r for r in judge_rows}

    # Build the labeled pairs (f_i, y_i) on the human-reviewed subset.
    pairs: list[tuple[float, float]] = []
    for adj in adj_rows:
        jr = jindex.get(_cell_id(adj))
        if jr is None:
            continue
        f_i = cell_benchmark_score(jr)
        y_i = _human_cell_score(adj)
        if f_i is None or y_i is None:
            continue
        pairs.append((f_i, y_i))
    n_lab = len(pairs)

    if n_lab == 0:
        return {"point": round(judge_only_mean, 2), "ci_low": None, "ci_high": None,
                "n_all": n_all, "n_labeled": 0,
                "judge_only_mean": round(judge_only_mean, 2), "rectifier": 0.0,
                "note": "no labeled cells — judge-only mean, no CI"}

    diffs = [y - f for (f, y) in pairs]
    rectifier = statistics.fmean(diffs)
    ys = [y for (_f, y) in pairs]

    if n_lab >= n_all:
        # Fully labeled: the estimate is the human mean directly; CI from the labeled
        # variance (the unlabeled judge term has zero weight).
        point = statistics.fmean(ys)
        var = (statistics.pvariance(ys) / n_lab) if n_lab > 1 else 0.0
        half = _Z_95 * math.sqrt(var)
        return {"point": round(point, 2), "ci_low": round(point - half, 2),
                "ci_high": round(point + half, 2), "n_all": n_all,
                "n_labeled": n_lab, "judge_only_mean": round(judge_only_mean, 2),
                "rectifier": round(rectifier, 4),
                "note": "fully labeled — CI from the labeled set"}

    point = judge_only_mean + rectifier

    # Two independent variance terms.
    var_f_all = (statistics.pvariance(f_all) / n_all) if n_all > 1 else 0.0
    var_diff_l = (statistics.pvariance(diffs) / n_lab) if n_lab > 1 else 0.0
    se = math.sqrt(var_f_all + var_diff_l)
    half = _Z_95 * se
    return {"point": round(point, 2), "ci_low": round(point - half, 2),
            "ci_high": round(point + half, 2), "n_all": n_all, "n_labeled": n_lab,
            "judge_only_mean": round(judge_only_mean, 2),
            "rectifier": round(rectifier, 4)}


# --------------------------------------------------------------------------- #
# 5. adjudication_record — the adjudication.jsonl schema
# --------------------------------------------------------------------------- #
def adjudication_record(*, scenario_id: str, backend_id: str, reviewer_id: str,
                        reviewer_tier: str, accuracy: int | None = None,
                        completeness: int | None = None, relevance: int | None = None,
                        harm: bool | None = None, note: str = "",
                        judged_at: str | None = None,
                        **extra_axes: Any) -> dict[str, Any]:
    """One human-reviewed cell — the row written to `adjudication.jsonl`.

    Schema:
      {
        scenario_id, backend_id,
        reviewer_id,                       # who reviewed it
        reviewer_tier,                     # owner | domain | clinical
        axes: {accuracy, completeness, relevance, ...},  # the human's 0-10 grades,
                                           # plus any re-graded categorical defects
                                           # (abstention_outcome, citation_groundedness,
                                           #  temporal_*) the reviewer overrode
        harm,                              # the human's boolean safety call
        note,                              # free-text rationale
        judged_at,                         # ISO timestamp (None until persisted)
      }

    reviewer_tier is validated against the three-tier escalation ladder so a bad value
    fails loud at write time rather than silently skewing an agreement stat later.
    """
    if reviewer_tier not in {"owner", "domain", "clinical"}:
        raise ValueError(
            f"reviewer_tier must be owner|domain|clinical, got {reviewer_tier!r}")

    axes: dict[str, Any] = {}
    if accuracy is not None:
        axes["accuracy"] = accuracy
    if completeness is not None:
        axes["completeness"] = completeness
    if relevance is not None:
        axes["relevance"] = relevance
    axes.update(extra_axes)  # re-graded categorical defects, if any

    return {
        "scenario_id": scenario_id,
        "backend_id": backend_id,
        "reviewer_id": reviewer_id,
        "reviewer_tier": reviewer_tier,
        "axes": axes,
        "harm": harm,
        "note": note,
        "judged_at": judged_at,
    }


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)
