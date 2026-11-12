"""Assemble 100% pure structured JSON validation report packets (`openclinai.report.v2`, `openclinai.summary.v2`, `openclinai.dashboard.v2`) from one or more runs' results.jsonl + run_manifest.json.

Zero HTML/CSS/JS lives in this producer module: `openclinai.org/reports/assets/` owns all
client-side presentation (`report-shell.{css,js}` and `dashboard-shell.{css,js}`).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.common.jsonl import read_jsonl as _read_jsonl
from harness.common.stats import avg, box_stats, ordered_unique, percentile, robust_axis_max

from .adjudicate import _human_cell_score
from .bundle import frozen_arm_cards, review_results, run_chart
from .check_precision import load_scores as load_check_precision
from .dashboard_data import write_dashboard_data
from .hub_trace import load_traces, match_trace, trace_model_for_result, trace_transport_for_result
from .judging import judge_summary
from .reconcile import (
    calibrated_summary,
    cell_benchmark_score,
    cell_safety_adjusted_benchmark_score,
    combined_judge_summary,
    has_critical_omission,
    has_severe_harm,
    scout_summary,
)
from .report_data import (
    enrich_and_deduplicate_run,
    write_report_data,
    write_run_summary,
)
from .response_artifacts import (
    in_depth_artifact,
    prepare_answer_review,
    prepare_indepth_review,
    response_for_displayed_evidence,
    split_answer_sections,
)
from .review_presentation import (
    annotate_sources,
    answer_section_view,
    indepth_section_view,
    section_confidence_displays,
)
from .sources import build_sources
from .stage_timings import expected_stage_labels, extract_stage_timings, stage_timing_label

_FALLBACK_MARKER = "could not produce a complete answer"

_ordered_unique = ordered_unique
_avg = avg
_box_stats = box_stats
_percentile = percentile
_robust_axis_max = robust_axis_max


def _is_degraded(r: dict[str, Any]) -> bool:
    answer = (r.get("response") or {}).get("answer")
    return isinstance(answer, str) and _FALLBACK_MARKER in answer.lower()


def _backend_labels(events: list[dict[str, Any]]) -> dict[str, str]:
    return {
        e["backend_id"]: (e.get("label") or e.get("modelName", ""))
        for e in events
        if e.get("event_type") == "backend_selected"
    }


_DIST_METRICS = [
    ("latency_ms", "latency (ms)"),
    ("citation_count", "chart references"),
    ("answer_chars", "answer length (chars)"),
]


def _metric_distributions(
    results: list[dict[str, Any]], backends: list[str]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, label in _DIST_METRICS:
        series = []
        all_values: list[float] = []
        for b in backends:
            vals = [
                (r.get("metrics") or {}).get(key)
                for r in results
                if r.get("backend_id") == b and (r.get("metrics") or {}).get("http_status") == 200
            ]
            nums = [v for v in vals if isinstance(v, (int, float))]
            stats = _box_stats(nums)
            if stats:
                series.append({"backend": b, **stats})
                all_values.extend(nums)
        out[key] = {
            "label": label,
            "series": series,
            "axis_max": round(_robust_axis_max(series, all_values), 2),
        }
    return out


def _load_judge(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "judge.jsonl"
    if not path.exists():
        return []
    return _read_jsonl(path)


def _load_judge_actors(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    actors: dict[str, list[dict[str, Any]]] = {}
    judges_dir = run_dir / "judges"
    if judges_dir.exists():
        for path in sorted(judges_dir.glob("*/judge.jsonl")):
            rows = _read_jsonl(path)
            if rows:
                actors[path.parent.name] = rows
    if not actors:
        root_rows = _load_judge(run_dir)
        if root_rows:
            actors["canonical"] = root_rows
    return actors


def _load_adjudication(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "adjudication.jsonl"
    if not path.exists():
        return []
    return _read_jsonl(path)


def _trace_for_row(r: dict[str, Any], traces: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    request = r.get("request") or {}
    return match_trace(
        traces or [],
        trace_model_for_result(r, r.get("backend_id")),
        r.get("started_at"),
        r.get("ended_at"),
        question=request.get("question"),
        session=request.get("session"),
        request_id=request.get("request_id"),
        transport=trace_transport_for_result(r),
    )


def _gate_for_row(r: dict[str, Any], traces: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    tr = _trace_for_row(r, traces)
    gate = tr.get("temporal_gate") if isinstance(tr, dict) else None
    if isinstance(gate, dict):
        return gate
    resp = r.get("response") if isinstance(r.get("response"), dict) else {}
    inline_gate = resp.get("temporalGate") or resp.get("temporal_gate") or r.get("temporal_gate")
    return inline_gate if isinstance(inline_gate, dict) else None


def _summary_rows(
    results: list[dict[str, Any]],
    backends: list[str],
    labels: dict[str, str],
    traces: list[dict[str, Any]] | None = None,
    arm_cards: dict[str, dict[str, Any]] | None = None,
    scenarios: list[dict[str, Any]] | None = None,
    judge_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for b in backends:
        rs = [r for r in results if r.get("backend_id") == b]
        lat = [r["metrics"]["latency_ms"] for r in rs if r.get("metrics")]
        cites = sum(
            (r["metrics"].get("citation_count") or r["metrics"].get("chart_ref_count") or 0)
            for r in rs
            if r.get("metrics")
        )
        gates = [_gate_for_row(r, traces) for r in rs]
        gates = [g for g in gates if g]
        valid_turns = sum(
            1
            for r in rs
            if (r.get("metrics") or {}).get("http_status") == 200
            and (r.get("metrics") or {}).get("json_valid", True)
            and not r.get("error")
        )
        resolved_refs = 0
        unresolved_refs = 0
        ans_edited = 0
        ans_flagged = 0
        for sc in scenarios or []:
            for tn in sc.get("turns") or []:
                cell = (tn.get("cells") or {}).get(b)
                if not isinstance(cell, dict):
                    continue
                av_status = cell.get("answer_validation_status")
                if not av_status and isinstance(cell.get("answer_view"), dict):
                    av_status = cell["answer_view"].get("status")
                if av_status == "edited":
                    ans_edited += 1
                elif av_status == "needs_review":
                    ans_flagged += 1
                srcs = cell.get("sources")
                if isinstance(srcs, dict):
                    for s_item in srcs.get("sources") or []:
                        if not isinstance(s_item, dict):
                            continue
                        st = s_item.get("resolution_status")
                        if st == "resolved":
                            resolved_refs += 1
                        elif st == "unresolved":
                            unresolved_refs += 1
                    diag = srcs.get("diagnostics") or {}
                    unres_diag = diag.get("unresolved_refs") or diag.get("unresolved_indices") or []
                    if isinstance(unres_diag, list) and unres_diag and unresolved_refs == 0:
                        unresolved_refs += len(unres_diag)
        if resolved_refs == 0 and unresolved_refs == 0 and judge_rows:
            for jr in judge_rows:
                if jr.get("backend_id") != b:
                    continue
                cr = jr.get("citation_resolution")
                if isinstance(cr, dict):
                    resolved_refs += int(cr.get("n_resolved") or 0)
                    unresolved_refs += int(cr.get("n_unresolved") or 0)

        expected_labels = expected_stage_labels(
            ((arm_cards or {}).get(b) or {}).get("stages")
        )
        stage_stats: dict[str, dict[str, Any]] = {
            label: {
                "completed_values": [],
                "failed_values": [],
                "cancelled_values": [],
                "observed": 0,
            }
            for label in expected_labels
        }
        for result in rs:
            trace = _trace_for_row(result, traces)
            for timing in extract_stage_timings(trace):
                label = stage_timing_label(timing)
                stats = stage_stats.setdefault(
                    label,
                    {
                        "completed_values": [],
                        "failed_values": [],
                        "cancelled_values": [],
                        "observed": 0,
                    },
                )
                stats["observed"] += 1
                status = timing["status"]
                if status == "completed":
                    stats["completed_values"].append(timing["duration_ms"])
                elif status == "cancelled":
                    stats["cancelled_values"].append(timing["duration_ms"])
                else:
                    stats["failed_values"].append(timing["duration_ms"])
        ttft_vals = [
            r["metrics"]["ttft_ms"]
            for r in rs
            if isinstance((r.get("metrics") or {}).get("ttft_ms"), (int, float))
        ]
        ans_vals = [
            r["metrics"]["answer_done_ms"]
            for r in rs
            if isinstance((r.get("metrics") or {}).get("answer_done_ms"), (int, float))
        ]
        turn_vals = [
            r["metrics"]["turn_done_ms"]
            for r in rs
            if isinstance((r.get("metrics") or {}).get("turn_done_ms"), (int, float))
        ]
        tpot_vals = [
            r["metrics"]["tpot_ms"]
            for r in rs
            if isinstance((r.get("metrics") or {}).get("tpot_ms"), (int, float))
        ]
        cached_vals = [
            r["metrics"]["cached_tokens"]
            for r in rs
            if isinstance((r.get("metrics") or {}).get("cached_tokens"), (int, float))
        ]
        row_summary: dict[str, Any] = {
            "backend_id": b,
            "label": labels.get(b, ""),
            "turns": len(rs),
            "valid_turns": valid_turns,
            "avg_latency_ms": _avg(lat),
            "max_latency_ms": max(lat) if lat else 0,
            "total_chart_refs": cites,
            "resolved_chart_refs": resolved_refs,
            "unresolved_chart_refs": unresolved_refs,
            "degraded": sum(1 for r in rs if _is_degraded(r)),
            "errors": sum(1 for r in rs if r.get("error")),
            "temporal_gate_pass": sum(1 for g in gates if g.get("status") == "pass"),
            "temporal_gate_warn": sum(1 for g in gates if g.get("status") == "warn"),
            "temporal_gate_fail": sum(1 for g in gates if g.get("status") == "fail"),
            "temporal_gate_applied": sum(
                1 for g in gates if g.get("applied") in {"patch", "fallback", True}
            ),
            "answer_check_edited": ans_edited,
            "answer_check_flagged": ans_flagged,
            "stage_latency_ms": {
                stage: {
                    "avg_ms": (
                        _avg(stats["completed_values"])
                        if stats["completed_values"]
                        else None
                    ),
                    "completed": len(stats["completed_values"]),
                    "failed": len(stats["failed_values"]),
                    "avg_failed_ms": (
                        _avg(stats["failed_values"])
                        if stats["failed_values"]
                        else None
                    ),
                    "cancelled": len(stats["cancelled_values"]),
                    "avg_cancelled_ms": (
                        _avg(stats["cancelled_values"])
                        if stats["cancelled_values"]
                        else None
                    ),
                    "observed": stats["observed"],
                    "expected": len(rs),
                }
                for stage, stats in stage_stats.items()
            },
        }
        if ttft_vals or ans_vals or turn_vals or tpot_vals or cached_vals:
            row_summary["streaming_latency"] = {
                "avg_ttft_ms": _avg(ttft_vals) if ttft_vals else None,
                "p95_ttft_ms": (
                    round(_percentile(sorted(ttft_vals), 0.95), 1)
                    if ttft_vals
                    else None
                ),
                "avg_answer_done_ms": _avg(ans_vals) if ans_vals else None,
                "p95_answer_done_ms": (
                    round(_percentile(sorted(ans_vals), 0.95), 1)
                    if ans_vals
                    else None
                ),
                "avg_turn_done_ms": _avg(turn_vals) if turn_vals else None,
                "avg_tpot_ms": (
                    round(sum(tpot_vals) / len(tpot_vals), 2) if tpot_vals else None
                ),
                "avg_cached_tokens": _avg(cached_vals) if cached_vals else None,
            }
        rows.append(row_summary)
    return rows


def _cell_blob(
    r: dict[str, Any],
    traces: list[dict[str, Any]] | None = None,
    chart_fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One pure structured JSON cell for the report packet (zero HTML strings)."""
    m = r.get("metrics") or {}
    resp = r.get("response") or {}
    trace = _trace_for_row(r, traces)
    gate = _gate_for_row(r, traces)
    raw_answer = str(resp.get("answer") or "").replace("\\n", "\n")
    answer, embedded_indepth = split_answer_sections(raw_answer)
    indepth = in_depth_artifact(r, resp, embedded_indepth)
    indepth = prepare_indepth_review(indepth, trace, chart_fixture)
    answer_validation = prepare_answer_review(
        resp.get("answerValidation"), answer, trace, chart_fixture
    )
    answer_confidence_display, indepth_confidence_display = section_confidence_displays(
        trace, resp.get("confidence")
    )
    evidence_response = response_for_displayed_evidence(
        resp, answer, indepth, embedded_indepth
    )
    sources_v1 = annotate_sources(
        build_sources(evidence_response, chart_fixture), answer, resp.get("blocks"), indepth
    )
    answer_view = answer_section_view(
        answer_validation,
        answer_confidence_display,
        answer,
        resp.get("blocks"),
        resp.get("references"),
    )
    indepth_view = indepth_section_view(indepth, indepth_confidence_display, sources_v1)

    show_orig = bool(
        isinstance(answer_validation, dict)
        and isinstance(answer_view, dict)
        and answer_view.get("show_original")
    )
    slim_answer_validation = (
        {
            "status": answer_validation.get("status"),
            "originalAnswer": answer_validation.get("originalAnswer"),
            "originalBlocks": answer_validation.get("originalBlocks") or [],
            "originalSources": answer_validation.get("originalSources") or {},
        }
        if show_orig
        else None
    )
    has_draft = bool(isinstance(indepth_view, dict) and indepth_view.get("draft"))
    review_sources = ((indepth or {}).get("reviewSources") or {}) if has_draft else {}

    cell: dict[str, Any] = {
        "error": r.get("error"),
        "http_status": m.get("http_status"),
        "answer_text": answer or "",
        "answer_view": answer_view,
        "indepth_view": indepth_view,
        "answer_validation_status": (
            answer_validation.get("status") if isinstance(answer_validation, dict) else None
        ),
        "blocks": resp.get("blocks") or [],
        "sources": sources_v1,
        "refs": [
            {
                "index": x.get("index"),
                "resourceType": x.get("resourceType") or "",
            }
            for x in (evidence_response.get("references") or [])
            if isinstance(x, dict)
        ],
        "temporal_gate": gate,
        "stage_timings": extract_stage_timings(trace),
        "degraded": _is_degraded(r),
        "metrics": {
            "latency_ms": m.get("latency_ms"),
            "http_status": m.get("http_status"),
            "citation_count": m.get("citation_count"),
            "first_turn": m.get("first_turn"),
            "json_valid": m.get("json_valid", True),
            **{
                k: m[k]
                for k in (
                    "ttft_ms",
                    "answer_done_ms",
                    "turn_done_ms",
                    "tpot_ms",
                    "cached_tokens",
                )
                if m.get(k) is not None
            },
        },
    }
    if slim_answer_validation is not None:
        cell["answer_validation"] = slim_answer_validation
    if review_sources:
        cell["review_sources"] = review_sources
    return cell


def _arm_cards_for(run_dir: Path, backends: list[str]) -> dict[str, Any]:
    return frozen_arm_cards(run_dir, backends)


def _comparison_context(
    run_dir: Path,
    events: list[dict[str, Any]],
    manifest: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    context: Any = None
    set_id = next(
        (
            e.get("comparison_set")
            for e in events
            if e.get("event_type") == "run" and e.get("comparison_set")
        ),
        None,
    )
    if set_id:
        path = run_dir / "inputs" / "comparison_sets" / f"{set_id}.json"
        try:
            context = json.loads(path.read_text(encoding="utf-8")).get("context")
        except (OSError, ValueError):
            context = None
    if not isinstance(context, dict) and isinstance(manifest, dict):
        context = manifest.get("context")
    if not isinstance(context, dict):
        return None
    url = str(context.get("url") or "").replace("'", "%27").replace('"', "%22")
    if not url.startswith("https://"):
        return None
    return {
        "url": url,
        "label": str(context.get("label") or url),
        "text": str(context.get("text") or ""),
    }


def _load_hardware_meta(run_dir: Path) -> dict[str, Any] | None:
    meta_path = run_dir / "run_meta.json"
    if not meta_path.exists():
        return None
    try:
        hw = json.loads(meta_path.read_text(encoding="utf-8")).get("hardware")
    except (OSError, ValueError):
        return None
    return hw if isinstance(hw, dict) and hw else None


def _load_domain_guardrails(run_dir: Path) -> list[dict[str, Any]]:
    guardrails_path = run_dir / "domain_guardrails.json"
    if not guardrails_path.is_file():
        return []
    try:
        raw = json.loads(guardrails_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and item.get("id") and item.get("label")]


_SEED_SCENARIO_RE = re.compile(r"^(?P<base>.+)__s(?P<seed>\d+)$")


def _split_scenario_seed(scenario_id: Any, fallback_seed: Any = None) -> tuple[str, int | None]:
    sid = str(scenario_id or "")
    m = _SEED_SCENARIO_RE.match(sid)
    if m:
        return m.group("base"), int(m.group("seed"))
    if isinstance(fallback_seed, int) and not isinstance(fallback_seed, bool):
        return sid, fallback_seed
    return sid, None


def _mean_numeric(vals: list[Any], ndigits: int = 2) -> float | None:
    nums = [float(v) for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return None
    return round(sum(nums) / len(nums), ndigits)


def _consolidate_multiseed_judge_rows(
    judge_rows_raw: list[dict[str, Any]],
    base_scenario_ids: list[str],
    backends: list[str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    for idx, r in enumerate(judge_rows_raw):
        base_sid, s_val = _split_scenario_seed(r.get("scenario_id"), r.get("seed"))
        bid = str(r.get("backend_id") or "")
        if not base_sid or not bid:
            continue
        grouped.setdefault((base_sid, bid), []).append((s_val if s_val is not None else idx, r))

    out: list[dict[str, Any]] = []
    for base_sid in base_scenario_ids:
        for bid in backends:
            entries = sorted(grouped.get((base_sid, bid), []), key=lambda t: t[0])
            if not entries:
                continue
            rows = [r for _, r in entries]
            first = rows[0]
            b_scores = [cell_benchmark_score(r) for r in rows]
            sa_scores = [cell_safety_adjusted_benchmark_score(r) for r in rows]
            notes = [
                f"[s{s_val}] {str(r.get('note') or '').strip()}"
                for s_val, r in entries
                if str(r.get("note") or "").strip()
            ]
            pooled: dict[str, Any] = {
                "scenario_id": base_sid,
                "backend_id": bid,
                "turn": first.get("turn", 1),
                "accuracy": _mean_numeric([r.get("accuracy") for r in rows], 2),
                "completeness": _mean_numeric([r.get("completeness") for r in rows], 2),
                "relevance": _mean_numeric([r.get("relevance") for r in rows], 2),
                "harm": any(bool(r.get("harm")) for r in rows),
                "benchmark_score": _mean_numeric(b_scores, 1),
                "safety_adjusted_benchmark_score": _mean_numeric(sa_scores, 1),
                "critical_omission": any(has_critical_omission(r) for r in rows),
                "severe_harm": any(has_severe_harm(r) for r in rows),
                "note": " | ".join(notes),
            }
            for opt_key in ("abstention_outcome", "citation_groundedness", "citation_resolution"):
                if first.get(opt_key) is not None:
                    pooled[opt_key] = first[opt_key]
            out.append(pooled)
    return out


def _run_blob(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    results = review_results(run_dir)
    events = _read_jsonl(run_dir / "events.jsonl")
    labels = _backend_labels(events)
    traces = load_traces(run_dir / "trace.jsonl")

    backends = _ordered_unique([r.get("backend_id") for r in results])
    scenario_ids = _ordered_unique([r.get("scenario_id") for r in results])
    run_id = manifest.get("run_id", "")
    family = str(manifest.get("family") or manifest.get("report_family") or "chartsearchai")
    evaluation_modality = str(manifest.get("evaluation_modality") or "")
    otel = manifest.get("otel", {})

    patient_meta = manifest.get("patients", {})
    raw_scenarios = []
    for sid in scenario_ids:
        chart_fixture = run_chart(run_dir, sid)
        rs = [r for r in results if r.get("scenario_id") == sid]
        if chart_fixture is None and isinstance(patient_meta, dict):
            for r in rs:
                pt_id = (r.get("request") or {}).get("patient")
                pt_obj = patient_meta.get(pt_id) if pt_id else None
                if isinstance(pt_obj, dict) and ("chart_snapshot" in pt_obj or "mappings" in pt_obj):
                    chart_fixture = pt_obj
                    break
        turns_seen = _ordered_unique([r.get("turn") for r in rs])
        index = {(r.get("turn"), r.get("backend_id")): r for r in rs}
        questions = {r.get("turn"): r.get("request", {}).get("question", "") for r in rs}
        turns = []
        for t in turns_seen:
            cells = {}
            for b in backends:
                r = index.get((t, b))
                if r is not None:
                    cells[b] = _cell_blob(r, traces, chart_fixture)
            turns.append({"turn": t, "question": questions.get(t, ""), "cells": cells})
        raw_scenarios.append({"scenario_id": sid, "turns": turns})

    distinct_seeds = sorted(
        {
            s_val
            for sid in scenario_ids
            for _, s_val in (_split_scenario_seed(sid),)
            if s_val is not None
        }
    )
    multi_seed = len(distinct_seeds) > 1

    chart_base = manifest.get(
        "openmrs_chart_base", "https://openmrs.openclinai.org/openmrs/spa/patient"
    )
    patient_uuids = _ordered_unique(
        [
            (r.get("request") or {}).get("patient")
            for r in results
            if (r.get("request") or {}).get("patient")
        ]
    )
    patients = []
    for u in patient_uuids:
        profile = dict(patient_meta.get(u) or {})
        profile["uuid"] = u
        profile.setdefault("chart_url", f"{chart_base}/{u}/chart")
        patients.append(profile)

    _ref_dates = _ordered_unique(
        [(_trace_for_row(r, traces) or {}).get("reference_date") for r in results]
    )
    _ref_dates = [d for d in _ref_dates if d]
    if not _ref_dates:
        meta_ref = None
        if (run_dir / "run_meta.json").is_file():
            try:
                meta_ref = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8")).get(
                    "reference_date"
                )
            except (OSError, ValueError):
                meta_ref = None
        if meta_ref:
            _ref_dates = [str(meta_ref)]
    reference_date = (
        _ref_dates[0]
        if len(_ref_dates) == 1
        else (", ".join(_ref_dates) if _ref_dates else None)
    )
    judge_rows_raw = _load_judge(run_dir)
    judge_actors = _load_judge_actors(run_dir)

    if multi_seed:
        base_scenario_ids = _ordered_unique([_split_scenario_seed(sid)[0] for sid in scenario_ids])
        raw_scen_by_id = {sc["scenario_id"]: sc for sc in raw_scenarios}
        raw_jr_by_key = {
            (str(r.get("scenario_id") or ""), str(r.get("backend_id") or "")): r
            for r in judge_rows_raw
        }
        raw_res_by_key = {
            (str(r.get("scenario_id") or ""), r.get("turn"), str(r.get("backend_id") or "")): r
            for r in results
        }
        seed_sids_by_base: dict[str, list[tuple[int, str]]] = {}
        for sid in scenario_ids:
            b_sid, s_val = _split_scenario_seed(sid)
            seed_sids_by_base.setdefault(b_sid, []).append((s_val if s_val is not None else 0, sid))
        scenarios = []
        for b_sid in base_scenario_ids:
            ordered_sids = [sid for _, sid in sorted(seed_sids_by_base.get(b_sid, []))]
            primary_sc = raw_scen_by_id[ordered_sids[0]]
            consolidated_turns = []
            for t_idx, primary_turn in enumerate(primary_sc.get("turns") or []):
                t_num = primary_turn.get("turn")
                consolidated_cells: dict[str, Any] = {}
                for b in backends:
                    p_cell = (primary_turn.get("cells") or {}).get(b)
                    if not isinstance(p_cell, dict):
                        continue
                    cell_copy = dict(p_cell)
                    reps: list[dict[str, Any]] = []
                    for s_val, full_sid in sorted(seed_sids_by_base.get(b_sid, [])):
                        rr = raw_res_by_key.get((full_sid, t_num, b))
                        jr = raw_jr_by_key.get((full_sid, b))
                        if rr is None and jr is None:
                            continue
                        reps.append(
                            {
                                "seed": s_val,
                                "latency_ms": ((rr or {}).get("metrics") or {}).get("latency_ms"),
                                "http_status": ((rr or {}).get("metrics") or {}).get("http_status"),
                                "benchmark_score": cell_benchmark_score(jr) if jr else None,
                                "accuracy": jr.get("accuracy") if jr else None,
                                "completeness": jr.get("completeness") if jr else None,
                                "relevance": jr.get("relevance") if jr else None,
                                "harm": bool(jr.get("harm")) if jr else False,
                            }
                        )
                    if reps:
                        cell_copy["seed_replicates"] = reps
                    consolidated_cells[b] = cell_copy
                consolidated_turns.append(
                    {
                        "turn": t_num,
                        "question": primary_turn.get("question", ""),
                        "cells": consolidated_cells,
                    }
                )
            scenarios.append({"scenario_id": b_sid, "turns": consolidated_turns})

        judge_rows = _consolidate_multiseed_judge_rows(judge_rows_raw, base_scenario_ids, backends)
        judge_actor_cells: dict[str, list[dict[str, Any]]] = {}
        for actor_name, a_rows in sorted(judge_actors.items()):
            pooled_actor_rows = _consolidate_multiseed_judge_rows(a_rows, base_scenario_ids, backends)
            for ar in pooled_actor_rows:
                key = f"{ar['scenario_id']}|{ar['backend_id']}"
                judge_actor_cells.setdefault(key, []).append(
                    {
                        "actor": actor_name,
                        "benchmark_score": ar.get("benchmark_score"),
                        "safety_adjusted_benchmark_score": ar.get("safety_adjusted_benchmark_score"),
                        "accuracy": ar.get("accuracy"),
                        "completeness": ar.get("completeness"),
                        "relevance": ar.get("relevance"),
                        "harm": bool(ar.get("harm")),
                        "critical_omission": bool(ar.get("critical_omission")),
                        "note": ar.get("note") or "",
                    }
                )
    else:
        scenarios = raw_scenarios
        judge_rows = [
            {
                **r,
                "benchmark_score": cell_benchmark_score(r),
                "safety_adjusted_benchmark_score": cell_safety_adjusted_benchmark_score(r),
                "critical_omission": has_critical_omission(r),
                "severe_harm": has_severe_harm(r),
            }
            for r in judge_rows_raw
        ]
        judge_actor_cells = {}
        for actor_name, a_rows in sorted(judge_actors.items()):
            for ar in a_rows:
                key = f"{ar.get('scenario_id')}|{ar.get('backend_id')}"
                judge_actor_cells.setdefault(key, []).append(
                    {
                        "actor": actor_name,
                        "benchmark_score": cell_benchmark_score(ar),
                        "safety_adjusted_benchmark_score": cell_safety_adjusted_benchmark_score(ar),
                        "accuracy": ar.get("accuracy"),
                        "completeness": ar.get("completeness"),
                        "relevance": ar.get("relevance"),
                        "harm": bool(ar.get("harm")),
                        "critical_omission": has_critical_omission(ar),
                        "note": ar.get("note") or "",
                    }
                )

    adj_raw = _load_adjudication(run_dir)
    adj_rows = []
    for a in adj_raw:
        axes = a.get("axes") if isinstance(a.get("axes"), dict) else {}
        merged_for_score = {**axes, **a, "axes": {**a, **axes}}
        adj_rows.append(
            {
                **axes,
                **a,
                "reviewer": a.get("reviewer") or a.get("reviewer_id") or "",
                "human_benchmark_score": _human_cell_score(merged_for_score),
                "critical_omission": (
                    has_critical_omission(axes) or has_critical_omission(a)
                ),
            }
        )
    arm_cards = _arm_cards_for(run_dir, backends)
    context = _comparison_context(run_dir, events, manifest)
    check_precision = load_check_precision(run_dir)
    domain_guardrails = _load_domain_guardrails(run_dir)

    summary_rows = _summary_rows(
        results, backends, labels, traces, arm_cards, raw_scenarios, judge_rows_raw
    )

    meta_block: dict[str, Any] = {
        "run_id": run_id,
        "component": manifest.get("component"),
        "git_sha": (manifest.get("git_sha") or "")[:10],
        "dataset_id": manifest.get("dataset_id"),
        "provider": otel.get("gen_ai.provider.name", "?"),
        "generated_at": manifest.get("generated_at", ""),
        "reference_date": reference_date,
    }
    if manifest.get("patients_summary"):
        meta_block["patients_summary"] = str(manifest["patients_summary"])

    run_dict: dict[str, Any] = {
        "run_id": run_id,
        "family": family,
        "meta": meta_block,
        "backends": backends,
        "labels": {b: labels.get(b, "") for b in backends},
        "scenarios": scenarios,
        "summary": summary_rows,
        "metrics": _metric_distributions(results, backends),
        "judge": scout_summary(judge_rows_raw, backends),
        "judge_rows": judge_rows,
        "judge_actors": sorted(judge_actors.keys()),
        "judge_actor_cells": judge_actor_cells,
        "judging": judge_summary(run_dir),
        "judge_passes": judge_actors,
        "judge_combined": combined_judge_summary(judge_actors, backends),
        "calibrated": calibrated_summary(judge_rows_raw, adj_raw, backends),
        "adjudication_rows": adj_rows,
        "check_precision": check_precision,
        "patients": patients,
        "context": context,
        "arm_cards": arm_cards,
        **(
            {"evaluation_modality": evaluation_modality}
            if evaluation_modality
            else {}
        ),
        **(
            {"seeds": distinct_seeds}
            if multi_seed
            else {}
        ),
        **(
            {"domain_guardrails": domain_guardrails}
            if domain_guardrails
            else {}
        ),
        **(
            {"hardware": _load_hardware_meta(run_dir)}
            if _load_hardware_meta(run_dir)
            else {}
        ),
    }
    return run_dict


def _assemble(run_dirs: list[Path], *, deduplicate: bool = True) -> dict[str, Any]:
    runs = [_run_blob(Path(d)) for d in run_dirs]
    if deduplicate:
        for r in runs:
            enrich_and_deduplicate_run(r, force_pool=True)
    top_family = (runs[0].get("family") if runs else None) or "chartsearchai"
    return {
        "schema": "openclinai.report.v2",
        "schema_version": 2,
        "family": top_family,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": runs,
    }


def build_report(
    run_dir: Path | str,
    *,
    deduplicate: bool = True,
    write_data_json: bool = True,
    write_summary: bool = True,
    write_dashboard: bool = True,
) -> Path:
    """Assemble and write the pure JSON report packet (`report-data.json`, `run-summary.json`, `dashboard-data.json`) for `run_dir`."""
    run_dir = Path(run_dir)
    blob = _assemble([run_dir], deduplicate=deduplicate)
    out = write_report_data(run_dir, blob) if write_data_json else (run_dir / "report-data.json")
    if not write_data_json:
        out.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    if write_summary:
        write_run_summary(run_dir, blob, family=str(blob.get("family") or "chartsearchai"))
    if write_dashboard:
        write_dashboard_data(run_dir)
    return out


def build_multi_report(run_dirs: list[Path | str], out_path: Path | str) -> Path:
    """Assemble and write a multi-run `openclinai.report.v2` JSON packet to `out_path`."""
    blob = _assemble([Path(d) for d in run_dirs], deduplicate=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    return out
