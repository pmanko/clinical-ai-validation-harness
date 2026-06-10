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
        out.append({
            "backend": b,
            "n": len(rs),
            "accuracy_mean": _mean("accuracy"),
            "completeness_mean": _mean("completeness"),
            "relevance_mean": _mean("relevance"),
            "harm_count": sum(1 for r in rs if r.get("harm")),
            "abstention": abstention,
            "groundedness": groundedness,
            "temporal": temporal,
            "citation_resolution": cit,
        })
    return out
