"""Canonical evaluation report data compiler, pool deduplicator, and cross-family normalizer.

Owns Layer 1 (Deterministic), Layer 2 (Advisory LLM Judge), and Layer 3 (Human Adjudication & PPI)
summary enrichment, plus `source_card_pool` and `refs_pool` deduplication so `build_report()` in
`clinical-ai-validation-harness` natively emits clean, deduplicated `report-data.json` payloads.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
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


def _esc(val: Any) -> str:
    return html.escape(str(val or ""), quote=True)


def enrich_and_deduplicate_run(
    run: dict[str, Any],
    *,
    pool_threshold: int = 4,
    force_pool: bool = False,
) -> tuple[int, int]:
    """Enrich a single run dict in-place and deduplicate `source_card_pool` & `refs_pool`.

    When `force_pool=True` or total cell count >= `pool_threshold`, repeated `<article class='source-card'>`
    blocks are pooled into `run['source_card_pool']` (`cell['source_card_refs']`), `cell['refs_html']`
    is pooled into `run['refs_pool']` (`cell['refs_pool_id']`), and duplicate `cell['sources']['sources']`
    arrays are stripped while preserving `cell['sources']['diagnostics']`.
    """
    scenarios = run.get("scenarios") or []
    backends = run.get("backends") or []
    total_cells = sum(
        len((tn.get("cells") or {}))
        for sc in scenarios
        for tn in (sc.get("turns") or [])
    )
    do_pool = force_pool or (total_cells >= pool_threshold)
    pooled_cards = 0

    det_by_b: dict[str, dict[str, int]] = {
        b: {
            "valid_turns": 0,
            "resolved_chart_refs": 0,
            "unresolved_chart_refs": 0,
            "temporal_gate_pass": 0,
        }
        for b in backends
    }

    rec_list: list[str] = list(run.get("source_card_pool") or [])
    rec_pool: dict[str, int] = {card: idx for idx, card in enumerate(rec_list)}
    refs_list: list[str] = list(run.get("refs_pool") or [])
    refs_pool: dict[str, int] = {r: idx for idx, r in enumerate(refs_list)}

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

                if not do_pool:
                    continue

                # 1. Slim indepth_view when not_in_profile
                iv = cell.get("indepth_view")
                if isinstance(iv, dict) and iv.get("status") == "not_in_profile" and not iv.get("body_html"):
                    cell["indepth_view"] = {"status": "not_in_profile"}

                # 2. Strip duplicate cell.sources.sources and empty diagnostic arrays
                srcs = cell.get("sources")
                if isinstance(srcs, dict):
                    srcs.pop("sources", None)
                    if "diagnostics" in srcs:
                        slim_diag = {k: v for k, v in (srcs.get("diagnostics") or {}).items() if v}
                        cell["sources"] = {"diagnostics": slim_diag} if slim_diag else {}

                # 3. Pool refs_html into run.refs_pool
                rh = cell.get("refs_html") or ""
                if rh:
                    if rh not in refs_pool:
                        refs_pool[rh] = len(refs_list)
                        refs_list.append(rh)
                    cell["refs_pool_id"] = refs_pool[rh]
                    cell.pop("refs_html", None)
                elif "refs_html" in cell:
                    cell.pop("refs_html", None)

                # 4. Pool sources_html cards into run.source_card_pool
                sh = cell.get("sources_html") or ""
                if sh:
                    cards = re.findall(r"<article class=['\"]source-card['\"]>.*?</article>", sh, re.S)
                    refs = []
                    for card in cards:
                        m_li = re.search(
                            r"<ul><li>(.*?)</li></ul><details><summary>open source record</summary><pre>(.*?)</pre></details>",
                            card,
                            re.S,
                        )
                        if m_li and m_li.group(1).strip() == m_li.group(2).strip():
                            card = card.replace(
                                f"<details><summary>open source record</summary><pre>{m_li.group(2)}</pre></details>",
                                "",
                            )
                        m_head = re.search(r"chart \[([^\]]+)\] (.*?)</span></div>", card, re.S)
                        chart_idx = m_head.group(1) if m_head else "?"
                        if m_head and m_li and m_head.group(2).strip() in m_li.group(1).strip():
                            card = card.replace(f"<ul><li>{m_li.group(1)}</li></ul>", "")
                        m_sid = re.search(r"<b>(S\d+)</b>", card)
                        sid = m_sid.group(1) if m_sid else "S1"
                        m_cite = re.search(r"cite \[([^\]]+)\] · ", card)
                        cite_num = m_cite.group(1) if m_cite else "?"
                        norm = re.sub(r"<b>S\d+</b>", "<b>__SID__</b>", card, count=1)
                        norm = re.sub(r"cite \[[^\]]+\] · chart \[[^\]]+\] ", "__CITE_CHART__", norm, count=1)
                        norm = norm.replace(
                            " title='Hub record-to-claim grounding result; not a whole-answer quality verdict'",
                            "",
                        )
                        if norm not in rec_pool:
                            rec_pool[norm] = len(rec_list)
                            rec_list.append(norm)
                        refs.append([rec_pool[norm], sid, cite_num, chart_idx])
                        pooled_cards += 1
                    cell["source_card_refs"] = refs
                    cell.pop("sources_html", None)
                elif "sources_html" in cell:
                    cell.pop("sources_html", None)

    if do_pool:
        if rec_list:
            run["source_card_pool"] = rec_list
        if refs_list:
            run["refs_pool"] = refs_list

        # Slim judge_passes when pooled
        jr_notes = {(r.get("scenario_id"), r.get("backend_id")): r.get("note") for r in (run.get("judge_rows") or [])}
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


def write_report_data(run_dir: Path, blob: dict[str, Any]) -> Path:
    """Write the standalone canonical `report-data.json` artifact into `run_dir`."""
    out = Path(run_dir) / "report-data.json"
    out.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    return out
