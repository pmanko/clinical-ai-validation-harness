"""Shared reconciliation: the answer-quality logic used by BOTH the offline judge
(report eval) and the runtime validator (med-agent-hub). Two layers, per the eval
methodology brief:

- Layer 1 (deterministic, no LLM): citation RESOLUTION — does each cited reference's
  resourceUuid resolve to a real record in the patient's chart. Catches fabricated
  references. Cheap + sound; the only reliable detector of an invented citation.
- Layer 2 (semantic, LLM): atomic-claim groundedness + the Scout rubric — done by a
  strong judge; this module only aggregates its structured output.

Pure functions only — the OpenMRS fetch of the valid uuid set lives at the call site
(best-effort, like ChartSearchAiClient.get_patient_profile).
"""

from __future__ import annotations

from typing import Any


def resolve_citations(references: list[dict[str, Any]], valid_uuids: set[str]) -> dict[str, Any]:
    """Layer-1: which references point to a real chart record. `references` is
    chartsearchai's resolved list ({index, resourceUuid, resourceType, date}); a
    reference resolves iff its resourceUuid is in `valid_uuids` (the patient's real
    record uuids). Returns counts + the unresolved (fabricated) references; rate is
    None when there are no references (so it never drags an aggregate down)."""
    refs = references or []
    resolved, unresolved = [], []
    for r in refs:
        uuid = r.get("resourceUuid")
        if uuid and uuid in valid_uuids:
            resolved.append(r)
        else:
            unresolved.append({"index": r.get("index"), "resourceUuid": uuid})
    return {
        "n_refs": len(refs),
        "n_resolved": len(resolved),
        "n_unresolved": len(unresolved),
        "unresolved": unresolved,
        "rate": (len(resolved) / len(refs)) if refs else None,
    }


# Benchmark score — a SOFT, advisory 0-100 composite of the Answer-only Scout axes (NO hard
# gates). A weighted quality core (accuracy/completeness lead, per HealthBench's physician-derived
# axis weights; relevance is down-weighted as the axis most inflated by fluent prose) minus
# bounded additive penalties for the categorical defects, floored at 0. Penalties SUBTRACT points
# (a single — subjective — safety flag costs points, never the whole score); they are never
# multiplicative. Constants are tunable here; rationale + citations live in
# specs/artifacts/planning/eval-methodology-brief.md.
_NUM_WEIGHTS = {"accuracy": 0.40, "completeness": 0.40, "relevance": 0.20}


def cell_benchmark_score(row: dict[str, Any]) -> float | None:
    """One cell's 0-100 benchmark from its Answer-only Scout axes. Returns None when the row has
    no numeric axis (so it is excluded from the mean, never counted as 0). Backward compatible: a
    row missing some numeric axes renormalizes over those present; missing / `n-a` categorical
    fields add no penalty; never raises on a malformed or legacy row."""
    try:
        present = {k: w for k, w in _NUM_WEIGHTS.items()
                   if isinstance(row.get(k), (int, float)) and not isinstance(row.get(k), bool)}
        if not present:
            return None
        core = 10.0 * sum(w * row[k] for k, w in present.items()) / sum(present.values())

        penalty = 0.0
        if row.get("harm"):
            penalty += 12
        ao = row.get("abstention_outcome")
        if ao == "failed-to-abstain":
            penalty += 12
        elif ao == "over-abstained":
            penalty += 5
        cg = row.get("citation_groundedness")
        if cg == "unsupported":
            penalty += 10
        elif cg == "partly":
            penalty += 3
        td = row.get("temporal_date_accuracy")
        if td == "wrong":
            penalty += 6
        elif td == "minor":
            penalty += 2
        if row.get("temporal_window") == "over-claimed":
            penalty += 4
        if row.get("temporal_trend") == "fabricated":
            penalty += 8

        return round(max(0.0, core - penalty), 1)
    except Exception:
        return None


def _benchmark_aggregate(scores: list[float]) -> dict[str, Any]:
    """Per-arm headline: the plain mean of the cell scores (so one bad answer stays visible in the
    number, not hidden by a median), with the min-max spread shown beside it. Empty -> Nones so a
    report column stays aligned."""
    if not scores:
        return {"score": None, "min": None, "max": None}
    return {
        "score": round(sum(scores) / len(scores), 1),
        "min": round(min(scores), 1),
        "max": round(max(scores), 1),
    }


def scout_summary(rows: list[dict[str, Any]], backends: list[str]) -> list[dict[str, Any]]:
    """Layer-2 aggregation: per-arm Scout-rubric means + categorical tallies over the
    judged scenarios. accuracy/completeness/relevance are 0-10 means; abstention &
    groundedness are category counts; harm is a count of hard-fails. Arms with no
    judged rows still appear (n=0, None means) so report columns stay aligned."""
    out = []
    for b in backends:
        rs = [r for r in rows if r.get("backend_id") == b]

        def _mean(key: str) -> float | None:
            vals = [r[key] for r in rs if isinstance(r.get(key), (int, float))]
            return round(sum(vals) / len(vals), 2) if vals else None

        abstention: dict[str, int] = {}
        groundedness: dict[str, int] = {}
        # temporal failure tallies (date↔value / window-scope / trend-from-too-few-points)
        temporal = {"date_wrong": 0, "date_minor": 0, "window_over": 0, "trend_fab": 0}
        # Layer-1 citation resolution, pooled across the arm's judged cells: each cell's
        # resolve_citations() output (written into the row by the judge). Pooled rate =
        # resolved/refs across all refs; None when the arm cited nothing (never drags down).
        cit = {"n_refs": 0, "n_resolved": 0, "n_unresolved": 0, "rate": None}
        for r in rs:
            ao = r.get("abstention_outcome")
            if ao:
                abstention[ao] = abstention.get(ao, 0) + 1
            cg = r.get("citation_groundedness")
            if cg:
                groundedness[cg] = groundedness.get(cg, 0) + 1
            cr = r.get("citation_resolution") or {}
            cit["n_refs"] += cr.get("n_refs") or 0
            cit["n_resolved"] += cr.get("n_resolved") or 0
            cit["n_unresolved"] += cr.get("n_unresolved") or 0
            if r.get("temporal_date_accuracy") == "wrong":
                temporal["date_wrong"] += 1
            elif r.get("temporal_date_accuracy") == "minor":
                temporal["date_minor"] += 1
            if r.get("temporal_window") == "over-claimed":
                temporal["window_over"] += 1
            if r.get("temporal_trend") == "fabricated":
                temporal["trend_fab"] += 1
        if cit["n_refs"]:
            cit["rate"] = round(cit["n_resolved"] / cit["n_refs"], 2)

        # Benchmark headline (Answer-only): per-cell soft composite -> per-arm mean + spread.
        cell_scores = [s for s in (cell_benchmark_score(r) for r in rs) if s is not None]
        bench = _benchmark_aggregate(cell_scores)

        # Background rubric (team In-Depth only): aggregate ONLY over rows that carry a `background`
        # block, in a SEPARATE namespace so it never touches the Answer means. n_background == 0 for
        # pure single-model arms (or any pre-change judge.jsonl), which then render as "—".
        bg_rows = [r["background"] for r in rs if isinstance(r.get("background"), dict)]

        def _bg_mean(key: str) -> float | None:
            vals = [b[key] for b in bg_rows
                    if isinstance(b.get(key), (int, float)) and not isinstance(b.get(key), bool)]
            return round(sum(vals) / len(vals), 2) if vals else None

        background = {
            "n_background": len(bg_rows),
            "support_mean": _bg_mean("support"),
            "added_value_mean": _bg_mean("added_value"),
            "new_harm_count": sum(1 for b in bg_rows if b.get("no_new_harm") == "harm"),
            "padded_count": sum(1 for b in bg_rows if b.get("conciseness") == "padded"),
            "claims_total": sum(int(b["n_claims"]) for b in bg_rows
                                if isinstance(b.get("n_claims"), int) and not isinstance(b.get("n_claims"), bool)),
        }
        out.append({
            "backend": b,
            "n": len(rs),
            "accuracy_mean": _mean("accuracy"),
            "completeness_mean": _mean("completeness"),
            "relevance_mean": _mean("relevance"),
            "harm_count": sum(1 for r in rs if r.get("harm")),
            # Benchmark headline + the safety counts shown beside it (never read the number naked).
            "benchmark_score": bench["score"],
            "benchmark_spread": {"min": bench["min"], "max": bench["max"]},
            "confabulation_count": abstention.get("failed-to-abstain", 0),
            "fabricated_citation_count": groundedness.get("unsupported", 0),
            "abstention": abstention,
            "groundedness": groundedness,
            "temporal": temporal,
            "citation_resolution": cit,
            "background": background,
        })
    return out


# Trust ordering of the three-tier escalation ladder — the badge surfaces the
# HIGHEST-trust reviewer who touched an arm (a clinician sign-off outranks an owner spot-check).
_TIER_RANK = {"owner": 0, "domain": 1, "clinical": 2}


def _highest_tier(adj_rows: list[dict[str, Any]]) -> str | None:
    """The most-trusted reviewer tier present in `adj_rows` (clinical > domain > owner),
    None when nothing was reviewed. Drives which badge the report shows for the arm."""
    tiers = [a.get("reviewer_tier") for a in adj_rows if a.get("reviewer_tier") in _TIER_RANK]
    return max(tiers, key=lambda t: _TIER_RANK[t]) if tiers else None


def _calibrated_block(judge_rows: list[dict[str, Any]],
                      adj_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The adjudication-calibrated estimate for ONE scope (an arm, or the whole run).

    When `adj_rows` carries ≥1 cell that matches a judged cell, this is the PPI point
    estimate ± 95% CI (the judge's cheap score on every cell, bias-corrected by the small
    human-labeled subset) plus the judge↔human agreement κ and the highest reviewer tier.
    With no adjudication it degrades to the judge-only mean: a point, but ci_low/ci_high =
    None and kappa = None so a caller can branch on `adjudicated`.

    Pure + defensive: imports the stats core lazily (adjudicate imports reconcile, so a
    top-level import would cycle), and never raises on empty / malformed input."""
    from . import adjudicate  # lazy: adjudicate -> reconcile, avoid an import cycle

    ppi = adjudicate.ppi_benchmark(judge_rows, adj_rows or [])
    n_labeled = ppi.get("n_labeled") or 0
    if n_labeled <= 0:
        # Judge-only: keep the judge mean as the point, but withhold the interval + κ so
        # the report renders this exactly as the pre-adjudication (advisory) headline.
        return {
            "adjudicated": False,
            "point": ppi.get("point"),
            "ci_low": None,
            "ci_high": None,
            "judge_only_mean": ppi.get("judge_only_mean"),
            "rectifier": ppi.get("rectifier"),
            "kappa": None,
            "n_labeled": 0,
            "n_all": ppi.get("n_all") or 0,
            "tier": None,
        }
    agr = adjudicate.agreement(judge_rows, adj_rows)
    return {
        "adjudicated": True,
        "point": ppi.get("point"),
        "ci_low": ppi.get("ci_low"),
        "ci_high": ppi.get("ci_high"),
        "judge_only_mean": ppi.get("judge_only_mean"),
        "rectifier": ppi.get("rectifier"),
        "kappa": agr.get("overall"),
        "kappa_by_axis": {ax: agr.get(ax) for ax in ("accuracy", "completeness", "relevance")},
        "n_labeled": n_labeled,
        "n_all": ppi.get("n_all") or 0,
        "tier": _highest_tier(adj_rows),
    }


def calibrated_summary(judge_rows: list[dict[str, Any]],
                       adj_rows: list[dict[str, Any]] | None,
                       backends: list[str]) -> list[dict[str, Any]]:
    """Per-arm (and run-level) adjudication-calibrated Benchmark.

    For each arm: the judge Benchmark (`benchmark_score`, identical to scout_summary's)
    PLUS a `calibrated` block — when that arm has ≥1 adjudicated cell, the PPI point
    estimate ± 95% CI and the judge↔human agreement κ; otherwise judge-only (no CI / no
    κ). A trailing row with backend "__run__" carries the run-level calibrated estimate
    pooled over every adjudicated cell. Rows are filtered to each backend so an arm's
    calibration leans only on its own cells.

    `adj_rows` empty / None -> every block is judge-only (the default, pre-adjudication
    report path). Pure + defensive: never raises on a malformed row."""
    judge_rows = list(judge_rows or [])
    adj_rows = list(adj_rows or [])

    out: list[dict[str, Any]] = []
    for b in backends:
        j_b = [r for r in judge_rows if r.get("backend_id") == b]
        a_b = [a for a in adj_rows if a.get("backend_id") == b]
        cell_scores = [s for s in (cell_benchmark_score(r) for r in j_b) if s is not None]
        bench = _benchmark_aggregate(cell_scores)
        out.append({
            "backend": b,
            "n": len(j_b),
            "benchmark_score": bench["score"],
            "benchmark_spread": {"min": bench["min"], "max": bench["max"]},
            "calibrated": _calibrated_block(j_b, a_b),
        })

    # Run-level: the calibrated estimate over the whole run (all arms pooled).
    all_scores = [s for s in (cell_benchmark_score(r) for r in judge_rows) if s is not None]
    run_bench = _benchmark_aggregate(all_scores)
    out.append({
        "backend": "__run__",
        "n": len(judge_rows),
        "benchmark_score": run_bench["score"],
        "benchmark_spread": {"min": run_bench["min"], "max": run_bench["max"]},
        "calibrated": _calibrated_block(judge_rows, adj_rows),
    })
    return out
