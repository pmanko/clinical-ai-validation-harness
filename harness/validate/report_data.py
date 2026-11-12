"""Canonical evaluation report data compiler, pool deduplicator, and cross-family normalizer (`openclinai.report.v2` & `openclinai.summary.v2`).

Owns Layer 1 (Deterministic), Layer 2 (Advisory LLM Judge), and Layer 3 (Human Adjudication & PPI)
summary enrichment, plus structured `source_card_pool` and `refs_pool` deduplication so `build_report()`
in `clinical-ai-validation-harness` natively emits 100% pure JSON `report-data.json`, `run-summary.json`,
and `dashboard-data.json` packets with zero HTML strings inside JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.validate.reconcile import (
    calibrated_summary,
    cell_benchmark_score,
    cell_safety_adjusted_benchmark_score,
    has_critical_omission,
    has_severe_harm,
    scout_summary,
)


def enrich_and_deduplicate_run(
    run: dict[str, Any],
    *,
    pool_threshold: int = 1,
    force_pool: bool = True,
) -> tuple[int, int]:
    """Enrich a single run dict in-place and deduplicate structured `source_card_pool` & `refs_pool`."""
    scenarios = run.get("scenarios") or []
    backends = run.get("backends") or []
    total_cells = sum(
        len((tn.get("cells") or {}))
        for sc in scenarios
        for tn in (sc.get("turns") or [])
    )
    do_pool = force_pool or (total_cells >= pool_threshold)

    det_by_b: dict[str, dict[str, int]] = {
        b: {
            "valid_turns": 0,
            "resolved_chart_refs": 0,
            "unresolved_chart_refs": 0,
            "temporal_gate_pass": 0,
        }
        for b in backends
    }

    rec_list: list[dict[str, Any]] = [
        item for item in (run.get("source_card_pool") or []) if isinstance(item, dict)
    ]
    rec_pool: dict[str, int] = {
        json.dumps(card, sort_keys=True, ensure_ascii=False): idx
        for idx, card in enumerate(rec_list)
    }
    refs_list: list[list[dict[str, Any]]] = [
        item for item in (run.get("refs_pool") or []) if isinstance(item, list)
    ]
    refs_pool: dict[str, int] = {
        json.dumps(r, sort_keys=True, ensure_ascii=False): idx
        for idx, r in enumerate(refs_list)
    }

    for sc in scenarios:
        for tn in sc.get("turns") or []:
            cells = tn.get("cells") or {}
            for b, cell in cells.items():
                if not isinstance(cell, dict):
                    continue
                st = det_by_b.setdefault(
                    b,
                    {
                        "valid_turns": 0,
                        "resolved_chart_refs": 0,
                        "unresolved_chart_refs": 0,
                        "temporal_gate_pass": 0,
                    },
                )
                if not cell.get("error") and (cell.get("http_status") in (None, 200)):
                    st["valid_turns"] += 1
                diag = ((cell.get("sources") or {}).get("diagnostics")) or {}
                top_refs = diag.get("top_level_refs") or []
                unres_refs = diag.get("unresolved_indices") or diag.get("unresolved_refs") or []
                if top_refs:
                    st["resolved_chart_refs"] += max(0, len(top_refs) - len(unres_refs))
                    st["unresolved_chart_refs"] += len(unres_refs)
                tg = cell.get("temporal_gate") or {}
                if tg.get("status") == "pass":
                    st["temporal_gate_pass"] += 1

                # Strip any legacy HTML keys if present
                for legacy_key in (
                    "answer_html",
                    "conf_html",
                    "sources_html",
                    "refs_html",
                    "blocks_html",
                    "chips_html",
                ):
                    cell.pop(legacy_key, None)

                iv = cell.get("indepth_view")
                if isinstance(iv, dict):
                    iv.pop("body_html", None)
                    if iv.get("status") == "not_in_profile" and not iv.get("body_text"):
                        cell["indepth_view"] = {"status": "not_in_profile"}

                if not do_pool:
                    continue

                # Pool structured cell.sources.sources into run.source_card_pool
                srcs = cell.get("sources")
                if isinstance(srcs, dict):
                    raw_sources = srcs.pop("sources", None) or []
                    if raw_sources and "source_card_refs" not in cell:
                        card_refs = []
                        for s_item in raw_sources:
                            if not isinstance(s_item, dict):
                                continue
                            card_base = {
                                "title": s_item.get("title") or "",
                                "resource_type": s_item.get("resource_type") or "",
                                "date": s_item.get("date") or "",
                                "sections": s_item.get("sections") or [],
                                "record_label": (
                                    s_item.get("record_label")
                                    or s_item.get("resolution_status")
                                    or "unknown"
                                ),
                                "record_tone": s_item.get("record_tone") or "neutral",
                                "support_label": (
                                    s_item.get("support_label")
                                    or s_item.get("support_status")
                                    or "unchecked"
                                ),
                                "support_tone": s_item.get("support_tone") or "neutral",
                                "facts_used": (s_item.get("facts_used") or [])[:4],
                                "source_text": s_item.get("source_text") or "",
                            }
                            key = json.dumps(card_base, sort_keys=True, ensure_ascii=False)
                            if key not in rec_pool:
                                rec_pool[key] = len(rec_list)
                                rec_list.append(card_base)
                            sid = s_item.get("source_id") or "S1"
                            cite_num = (
                                s_item.get("citation_index")
                                if s_item.get("citation_index") is not None
                                else (s_item.get("record_index") or "?")
                            )
                            chart_idx = (
                                s_item.get("chart_record_index")
                                if s_item.get("chart_record_index") is not None
                                else (s_item.get("record_index") or "?")
                            )
                            card_refs.append([rec_pool[key], sid, cite_num, chart_idx])
                        cell["source_card_refs"] = card_refs
                    if "diagnostics" in srcs:
                        slim_diag = {k: v for k, v in (srcs.get("diagnostics") or {}).items() if v}
                        cell["sources"] = {"diagnostics": slim_diag} if slim_diag else {}

                # Pool structured cell.refs into run.refs_pool
                raw_refs = cell.pop("refs", None) or []
                if raw_refs and "refs_pool_id" not in cell:
                    slim_refs = [
                        {
                            "index": r.get("index"),
                            "resourceType": r.get("resourceType") or "",
                        }
                        for r in raw_refs
                        if isinstance(r, dict)
                    ]
                    if slim_refs:
                        r_key = json.dumps(slim_refs, sort_keys=True, ensure_ascii=False)
                        if r_key not in refs_pool:
                            refs_pool[r_key] = len(refs_list)
                            refs_list.append(slim_refs)
                        cell["refs_pool_id"] = refs_pool[r_key]

    run.pop("check_precision_html", None)

    if do_pool:
        if rec_list:
            run["source_card_pool"] = rec_list
        if refs_list:
            run["refs_pool"] = refs_list

        jr_notes = {
            (r.get("scenario_id"), r.get("backend_id")): r.get("note")
            for r in (run.get("judge_rows") or [])
        }
        jp = run.get("judge_passes") or {}
        if len(jp) < 2:
            run["judge_passes"] = {}
        else:
            for actor, rows in jp.items():
                slim_rows = []
                for r in rows:
                    sr: dict[str, Any] = {
                        "scenario_id": r.get("scenario_id"),
                        "backend_id": r.get("backend_id"),
                        "accuracy": r.get("accuracy"),
                        "completeness": r.get("completeness"),
                        "relevance": r.get("relevance"),
                        "abstention_outcome": r.get("abstention_outcome"),
                        "citation_groundedness": r.get("citation_groundedness"),
                    }
                    if r.get("harm"):
                        sr["harm"] = r.get("harm")
                    rec_note = jr_notes.get((r.get("scenario_id"), r.get("backend_id")))
                    if r.get("note") and r.get("note") != rec_note:
                        sr["note"] = r.get("note")
                    slim_rows.append(sr)
                jp[actor] = slim_rows

    j_by_b = {j.get("backend"): j for j in (run.get("judge") or []) if isinstance(j, dict)}
    for s in run.get("summary") or []:
        b = s.get("backend_id", "")
        st = det_by_b.get(b, {})
        cr = ((j_by_b.get(b) or {}).get("citation_resolution")) or {}
        turns = s.get("turns") or 0
        errors = s.get("errors") or 0
        if s.get("valid_turns") is None:
            s["valid_turns"] = st.get("valid_turns") or max(0, turns - errors)
        tot_refs = (s.get("total_chart_refs") or 0) or (cr.get("n_refs") or 0)
        s["total_chart_refs"] = tot_refs
        if not s.get("resolved_chart_refs"):
            if cr.get("n_resolved") is not None:
                s["resolved_chart_refs"] = cr["n_resolved"]
            else:
                unres = st.get("unresolved_chart_refs", 0)
                s["resolved_chart_refs"] = max(0, tot_refs - unres)
        if not s.get("unresolved_chart_refs"):
            s["unresolved_chart_refs"] = cr.get("n_unresolved") or st.get("unresolved_chart_refs", 0)
        if s.get("temporal_gate_pass") is None:
            g_warn = s.get("temporal_gate_warn") or 0
            g_fail = s.get("temporal_gate_fail") or 0
            s["temporal_gate_pass"] = st.get("temporal_gate_pass") or max(0, turns - errors - g_warn - g_fail)
        s.setdefault("temporal_gate_warn", 0)
        s.setdefault("temporal_gate_fail", 0)
        s.setdefault("temporal_gate_applied", 0)
        s.setdefault("answer_check_edited", 0)
        s.setdefault("answer_check_flagged", 0)

    jrows = run.get("judge_rows") or []
    for jr in jrows:
        if jr.get("benchmark_score") is None:
            jr["benchmark_score"] = cell_benchmark_score(jr)
        if jr.get("safety_adjusted_benchmark_score") is None:
            jr["safety_adjusted_benchmark_score"] = cell_safety_adjusted_benchmark_score(jr)
        if jr.get("critical_omission") is None:
            jr["critical_omission"] = has_critical_omission(jr)
        if jr.get("severe_harm") is None:
            jr["severe_harm"] = has_severe_harm(jr)

    if jrows and run.get("judge"):
        recomputed = {row["backend"]: row for row in scout_summary(jrows, backends)}
        for j_arm in run["judge"]:
            b = j_arm.get("backend")
            rc = recomputed.get(b)
            if rc:
                for k in (
                    "benchmark_score",
                    "safety_adjusted_benchmark_score",
                    "safety_adjusted_ci",
                    "critical_omission_count",
                    "severe_harm_count",
                ):
                    if j_arm.get(k) is None and rc.get(k) is not None:
                        j_arm[k] = rc[k]

    if not run.get("calibrated"):
        run["calibrated"] = calibrated_summary(jrows, run.get("adjudication_rows") or [], backends)

    run.setdefault("adjudication_rows", [])
    run.setdefault("judge_actor_cells", {})
    return total_cells, len(rec_list)


def build_run_summary(blob: dict[str, Any], *, family: str | None = None) -> dict[str, Any]:
    """Build the immutable machine `openclinai.summary.v2` (`run-summary.json`) from a report packet blob."""
    runs = blob.get("runs") or []
    run = runs[0] if runs else {}
    meta = run.get("meta") or {}
    resolved_family = family or run.get("family") or blob.get("family") or "chartsearchai"
    backends = list(run.get("backends") or [])
    arm_cards = run.get("arm_cards") or {}
    labels = run.get("labels") or {}
    summary_by_b = {
        s.get("backend_id"): s
        for s in (run.get("summary") or [])
        if isinstance(s, dict) and s.get("backend_id")
    }
    judge_by_b = {
        j.get("backend"): j
        for j in (run.get("judge") or [])
        if isinstance(j, dict) and j.get("backend")
    }
    cal_by_b = {
        c.get("backend"): c.get("calibrated")
        for c in (run.get("calibrated") or [])
        if isinstance(c, dict) and c.get("backend")
    }

    arms: list[dict[str, Any]] = []
    for b in backends:
        card = arm_cards.get(b) or {}
        s = summary_by_b.get(b) or {}
        j = judge_by_b.get(b) or {}
        title = card.get("title") or labels.get(b) or s.get("label") or b
        short_title = card.get("short_title") or title
        arm_entry: dict[str, Any] = {
            "id": b,
            "title": title,
            "short_title": short_title,
            "kind": card.get("kind") or "single",
            "path": card.get("path") or "",
            "models": card.get("models") or [],
            "roles": card.get("roles") or {},
            "turns": s.get("turns") or 0,
            "valid_turns": s.get("valid_turns") or 0,
            "errors": s.get("errors") or 0,
            "degraded": s.get("degraded") or 0,
            "avg_latency_ms": s.get("avg_latency_ms") or 0,
            "max_latency_ms": s.get("max_latency_ms") or 0,
            "total_chart_refs": s.get("total_chart_refs") or 0,
            "resolved_chart_refs": s.get("resolved_chart_refs") or 0,
            "unresolved_chart_refs": s.get("unresolved_chart_refs") or 0,
            "temporal_gate_pass": s.get("temporal_gate_pass") or 0,
            "temporal_gate_warn": s.get("temporal_gate_warn") or 0,
            "temporal_gate_fail": s.get("temporal_gate_fail") or 0,
            "temporal_gate_applied": s.get("temporal_gate_applied") or 0,
            "answer_check_edited": s.get("answer_check_edited") or 0,
            "answer_check_flagged": s.get("answer_check_flagged") or 0,
            "benchmark_score": j.get("benchmark_score"),
            "safety_adjusted_benchmark_score": j.get("safety_adjusted_benchmark_score"),
            "accuracy_mean": j.get("accuracy_mean"),
            "completeness_mean": j.get("completeness_mean"),
            "relevance_mean": j.get("relevance_mean"),
            "harm_count": j.get("harm_count"),
            "critical_omission_count": j.get("critical_omission_count"),
            "severe_harm_count": j.get("severe_harm_count"),
            "abstention": j.get("abstention") or {},
            "groundedness": j.get("groundedness") or {},
            "temporal": j.get("temporal") or {},
        }
        if cal_by_b.get(b):
            arm_entry["calibrated"] = cal_by_b[b]
        if s.get("catalyst"):
            arm_entry["catalyst"] = s["catalyst"]
        arms.append(arm_entry)

    scored_arms = [a for a in arms if a.get("benchmark_score") is not None]
    winner = None
    if scored_arms:
        best = max(scored_arms, key=lambda a: float(a.get("benchmark_score") or 0.0))
        winner = {
            "id": best["id"],
            "title": best["title"],
            "short_title": best["short_title"],
            "benchmark_score": best["benchmark_score"],
            "safety_adjusted_benchmark_score": best.get("safety_adjusted_benchmark_score"),
            "avg_latency_ms": best["avg_latency_ms"],
        }

    judging = run.get("judging") or {}
    judge_actors = run.get("judge_actors") or []
    cards = judging.get("cards") or []
    judge_groups = {
        "-".join(
            str(x)
            for x in (c.get("agent"), c.get("model"), c.get("reasoning_effort"))
            if x
        ).lower()
        or str(c.get("actor_id") or "judge")
        for c in cards
        if isinstance(c, dict)
    }
    n_judges = (
        len((((judging.get("consensus") or {}).get("judges") or {}).get("per_judge") or {}))
        or len(judge_groups)
        or len(judge_actors)
    )

    gen_at = str(meta.get("generated_at") or blob.get("generated_at") or "")
    date_str = gen_at[:10] if len(gen_at) >= 10 else ""
    turns_per_arm = max((a.get("turns") or 0 for a in arms), default=0)
    total_cells = sum(int(a.get("turns") or 0) for a in arms)
    patients_out: Any = (
        str(meta["patients_summary"])
        if meta.get("patients_summary")
        else [
            p.get("display") or p.get("identifier") or p.get("uuid")
            for p in (run.get("patients") or [])
            if isinstance(p, dict) and (p.get("display") or p.get("identifier") or p.get("uuid"))
        ]
    )

    out: dict[str, Any] = {
        "schema": "openclinai.summary.v2",
        "schema_version": 2,
        "run_id": str(run.get("run_id") or meta.get("run_id") or ""),
        "family": resolved_family,
        "report_family": resolved_family,
        "component": meta.get("component") or "",
        "dataset_id": meta.get("dataset_id") or "",
        "date": date_str,
        "generated_at": gen_at,
        "git_sha": str(meta.get("git_sha") or "")[:10],
        "reference_date": meta.get("reference_date"),
        "scenarios": len(run.get("scenarios") or []),
        "turns": turns_per_arm,
        "cells": total_cells,
        "backends": backends,
        "patients": patients_out,
        "scout": list(run.get("judge") or []),
        "judging": {
            "recorded": bool(judging.get("recorded") or judge_actors),
            "actor_count": len(judge_actors),
            "judge_count": n_judges,
            "actors": judge_actors,
            "aggregation": judging.get("aggregation"),
            "sentence": judging.get("sentence") or "",
            "canonical": judging.get("canonical") or [],
        },
        "arms": arms,
        "winner": winner,
    }
    if run.get("evaluation_modality"):
        out["evaluation_modality"] = str(run["evaluation_modality"])
    if run.get("seeds"):
        out["seeds"] = list(run["seeds"])
    if run.get("domain_guardrails"):
        out["domain_guardrails"] = list(run["domain_guardrails"])
    if run.get("catalyst"):
        out["catalyst"] = {
            k: v
            for k, v in (run["catalyst"] or {}).items()
            if k in ("kind", "gate", "totals", "outcomes")
        }
    return out


def write_report_data(run_dir: Path | str, blob: dict[str, Any]) -> Path:
    """Write the standalone canonical `report-data.json` artifact into `run_dir`."""
    out = Path(run_dir) / "report-data.json"
    out.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    return out


def write_run_summary(
    run_dir: Path | str,
    blob: dict[str, Any],
    *,
    family: str | None = None,
) -> Path:
    """Write `run-summary.json` (`openclinai.summary.v2`) into `run_dir`."""
    summary_payload = (
        blob
        if blob.get("schema") == "openclinai.summary.v2"
        else build_run_summary(blob, family=family)
    )
    out = Path(run_dir) / "run-summary.json"
    out.write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out
