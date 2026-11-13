"""Pure JSON builder and live status/detail provider for diagnostic dashboards (`openclinai.dashboard.v2`)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from harness.common.jsonl import read_jsonl as _read_jsonl
from harness.common.text import esc_inline
from harness.validate.bundle import frozen_arm_cards, load_run_meta, review_results, run_chart
from harness.validate.context_store import rehydrate_response_envelope
from harness.validate.check_precision import load_scores as load_check_precision
from harness.validate.hub_trace import match_trace, trace_model_for_result, trace_transport_for_result
from harness.validate.judging import judge_summary
from harness.validate.reconcile import combined_judge_summary, scout_summary
from harness.validate.response_artifacts import (
    in_depth_artifact,
    prepare_answer_review,
    prepare_indepth_review,
    response_for_displayed_evidence,
    split_answer_sections,
)
from harness.validate.review_presentation import (
    annotate_sources,
    answer_section_view,
    cell_review_summary,
    indepth_section_view,
    section_confidence_displays,
    status_legend,
)
from harness.validate.sources import build_sources
from harness.validate.stage_timings import extract_stage_timings

try:
    from harness.catalyst.attribution import blame as _blame
    from harness.catalyst.notebook_validation import assertion_class

    CLASSIFIER_SOURCE: str | None = "harness.catalyst.notebook_validation"
    _CLASSIFIER_ERROR = ""
except Exception as _classifier_error:  # pragma: no cover - deployment guard
    CLASSIFIER_SOURCE = None
    _CLASSIFIER_ERROR = str(_classifier_error)

    def assertion_class(name: str) -> str:
        return "conformance"

    def _blame(assertions: Any, ledger_path: Any = None) -> dict[str, Any]:
        return {"kind": "invalid", "root": None, "consequences": 0, "rationale": None}


blame_failure = _blame

_SQL_CLAUSE = re.compile(
    r"\s+(FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|OFFSET|UNION ALL|UNION"
    r"|LEFT JOIN|RIGHT JOIN|FULL JOIN|INNER JOIN|CROSS JOIN|JOIN|ON|AND|OR)\s+",
    re.IGNORECASE,
)


def format_sql(sql: Any) -> Any:
    """Break a single-line SQL query at clause boundaries for display."""
    if not sql or not isinstance(sql, str) or "\n" in sql or not re.match(r"\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        return sql

    def _break(chunk: str) -> str:
        return _SQL_CLAUSE.sub(
            lambda m: "\n"
            + ("  " if m.group(1).upper() in ("ON", "AND", "OR") else "")
            + m.group(1).upper()
            + " ",
            chunk,
        )

    parts = re.split(r"('(?:[^']|'')*')", sql)
    return "".join(part if i % 2 else _break(part) for i, part in enumerate(parts))


def read_judge_actors(run: Path | str) -> dict[str, list[dict[str, Any]]]:
    actors: dict[str, list[dict[str, Any]]] = {}
    judges_dir = Path(run) / "judges"
    if judges_dir.exists():
        for path in sorted(judges_dir.glob("*/judge.jsonl")):
            rows = _read_jsonl(path, strict=False)
            if rows:
                actors[path.parent.name] = rows
    if not actors:
        rows = _read_jsonl(Path(run) / "judge.jsonl", strict=False)
        if rows:
            actors["canonical"] = rows
    return actors


def _captured_backends(run: Path | str) -> dict[str, Any]:
    try:
        return json.loads((Path(run) / "inputs" / "backends.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def profile_titles(run: Path | str, back_ids: list[str]) -> dict[str, str]:
    meta_backends = load_run_meta(run).get("backends") or {}
    captured = _captured_backends(run)
    by_profile = {
        str(entry.get("modelName")): str(entry.get("label"))
        for entry in captured.values()
        if isinstance(entry, dict)
        and entry.get("kind") == "product_profile"
        and entry.get("modelName")
        and entry.get("label")
    }
    out: dict[str, str] = {}
    for b in back_ids:
        backend = meta_backends.get(b) or captured.get(b) or {}
        if backend.get("provider") == "bundled":
            continue
        title = by_profile.get(str(backend.get("modelName") or ""))
        if title:
            out[b] = title
    return out


def arm_models(run: Path | str, arm_cards: dict[str, Any]) -> list[dict[str, str]]:
    meta_backends = load_run_meta(run).get("backends") or {}
    seen: dict[str, str] = {}
    for b, card in arm_cards.items():
        provider = (meta_backends.get(b) or {}).get("provider")
        for model in (card or {}).get("models") or []:
            ident = model.get("id")
            if ident and ident not in seen:
                seen[str(ident)] = "Hub profile" if provider == "hub" else "model"
    return [{"id": ident, "kind": kind} for ident, kind in sorted(seen.items())]


def run_family(run: Path | str) -> str:
    run_path = Path(run)
    if (run_path / "suite.json").exists():
        return "catalyst"
    try:
        manifest = json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8"))
        explicit = str(manifest.get("family") or manifest.get("report_family") or "").lower()
        if explicit in ("chartsearchai", "wahs", "catalyst"):
            return explicit
        comp = str(manifest.get("component") or "").lower()
        if "wahs" in comp:
            return "wahs"
        if "catalyst" in comp:
            return "catalyst"
    except Exception:
        pass
    return "chartsearchai"


def catalyst_expectation(run: Path | str, scenario_id: str) -> dict[str, Any] | None:
    try:
        suite = json.loads((Path(run) / "suite.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    scenario = next(
        (s for s in suite.get("scenarios") or [] if s.get("id") == scenario_id), None
    )
    if not scenario:
        return None
    gold = scenario.get("baseGoldCheck") or scenario.get("successorGoldCheck")
    return {
        "criterion": scenario.get("comment") or "",
        "question": scenario.get("initialQuestion") or "",
        "baseOutcome": scenario.get("expectedBaseOutcome", "ready"),
        "turns": [
            {
                "instruction": t.get("instruction"),
                "expectedOutcome": t.get("expectedOutcome", "ready"),
            }
            for t in scenario.get("turns") or []
        ],
        "goldCheck": (
            {"mode": gold.get("mode"), "referenceSql": gold.get("referenceSql")}
            if gold
            else None
        ),
    }


SHARD_CELL_THRESHOLD = 500


def _resolved_shard_threshold(shard_threshold: int | None) -> int:
    if shard_threshold is not None:
        return max(1, int(shard_threshold))
    raw = os.environ.get("OPENCLINAI_DASHBOARD_SHARD_THRESHOLD", "").strip()
    if raw:
        try:
            val = int(raw)
            if val > 0:
                return val
        except ValueError:
            pass
    return SHARD_CELL_THRESHOLD


def _shard_rel_path(idx: int, backend_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(backend_id or "arm")).strip("-")[:48] or "arm"
    digest = hashlib.sha1(str(backend_id).encode("utf-8")).hexdigest()[:8]
    return f"dashboard-details/{idx:02d}-{safe}-{digest}.json"


def _row_conformed(r: dict[str, Any]) -> bool:
    m = r.get("metrics") or {}
    if "passed" not in m:
        return m.get("http_status") == 200 and (m.get("answer_chars") or 0) > 0
    if m.get("passed"):
        return True
    for item in (r.get("response") or {}).get("failedAssertions") or []:
        if (item.get("class") or assertion_class(item.get("name") or "")) == "conformance":
            return False
    return bool((r.get("response") or {}).get("failedAssertions"))


def _row_judged(r: dict[str, Any]) -> bool:
    m = r.get("metrics") or {}
    if "passed" in m:
        return bool(m["passed"])
    return m.get("http_status") == 200 and (m.get("answer_chars") or 0) > 0


def _make_feed_item(r: dict[str, Any]) -> dict[str, Any]:
    m = r.get("metrics") or {}
    ind = r.get("indepth") or {}
    iresp = ind.get("response") or {}
    if isinstance(iresp, str):
        try:
            iresp = json.loads(iresp)
        except Exception:
            iresp = {"answer": iresp}
    return {
        "scenario": r.get("scenario_id"),
        "backend": r.get("backend_id"),
        "turn": r.get("turn"),
        "status": m.get("http_status"),
        "chars": m.get("answer_chars"),
        "indepth_status": ind.get("http_status"),
        "indepth_chars": len((iresp or {}).get("answer") or ""),
        "ans": esc_inline(((r.get("response") or {}).get("answer", "") or "")[:90]),
    }


def _read_scenario_turn_count(run_path: Path, sid: str) -> int | None:
    try:
        data = json.loads((run_path / "inputs" / "scenarios" / f"{sid}.json").read_text(encoding="utf-8"))
        return len(data["turns"])
    except Exception:
        return None


def _read_scenario_expectations(run_path: Path, scenario: str) -> dict[str, Any]:
    try:
        exp = json.loads((run_path / "inputs" / "scenarios" / f"{scenario}.json").read_text(encoding="utf-8")).get(
            "expectations", {}
        )
        return exp if isinstance(exp, dict) else {}
    except Exception:
        return {}


def build_status_from_loaded(
    run_path: Path,
    *,
    events: list[dict[str, Any]],
    results: list[dict[str, Any]],
    judge_actors: dict[str, list[dict[str, Any]]] | None = None,
    canonical_rows: list[dict[str, Any]] | None = None,
    check_precision: dict[str, Any] | None = None,
    judging: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble full status payload from pre-loaded run artifacts in a single O(N) pass."""
    run_ev = next((e for e in events if e.get("event_type") == "run"), {})
    set_id = run_ev.get("comparison_set")
    scen_ids = list(run_ev.get("scenario_ids", []))
    back_ids = list(run_ev.get("backend_ids", []))
    labels = {
        e["backend_id"]: e.get("label", "")
        for e in events
        if e.get("event_type") == "backend_selected"
    }

    if not scen_ids and results:
        scen_ids = list(dict.fromkeys(r.get("scenario_id") for r in results if r.get("scenario_id")))
    if not back_ids and results:
        back_ids = list(dict.fromkeys(r.get("backend_id") for r in results if r.get("backend_id")))

    by_arm: dict[str, list[dict[str, Any]]] = {}
    cell_rows: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    max_obs_turns: dict[Any, int] = {}
    for r in results:
        bid = r.get("backend_id")
        sid = r.get("scenario_id")
        if bid is not None:
            by_arm.setdefault(bid, []).append(r)
        cell_rows.setdefault((sid, bid), []).append(r)
        t_val = r.get("turn") or 1
        if isinstance(t_val, int) and t_val > max_obs_turns.get(sid, 0):
            max_obs_turns[sid] = t_val

    cells = run_ev.get("cells")
    if cells:
        expected_cells = [(c["scenario_id"], c["backend_id"]) for c in cells]
        exp_turns = {(c["scenario_id"], c["backend_id"]): c["turns"] for c in cells}
        total = sum(c["turns"] for c in cells)
        scen_ids = list(dict.fromkeys(c["scenario_id"] for c in cells))
        back_ids = list(dict.fromkeys(c["backend_id"] for c in cells))
    else:
        turns = {}
        for sid in scen_ids:
            cnt = _read_scenario_turn_count(run_path, sid)
            turns[sid] = cnt if cnt is not None else (max_obs_turns.get(sid) or 1)
        expected_cells = [(s, b) for s in scen_ids for b in back_ids]
        exp_turns = {(s, b): turns.get(s, 1) for (s, b) in expected_cells}
        total = sum(turns.values()) * len(back_ids) if back_ids else 0

    _rp = run_path / "results.jsonl"
    active = _rp.exists() and (time.time() - _rp.stat().st_mtime) < 120
    arms = {}
    for b in back_ids:
        rs = by_arm.get(b, [])
        errs = sum(1 for r in rs if (r.get("metrics") or {}).get("http_status") != 200)
        lat_sum = sum(((r.get("metrics") or {}).get("latency_ms", 0) or 0) for r in rs)
        ch_sum = sum(((r.get("metrics") or {}).get("answer_chars", 0) or 0) for r in rs)
        n_rs = len(rs)
        arms[b] = {
            "label": labels.get(b, b),
            "rows": n_rs,
            "errors": errs,
            "avg_latency_ms": (lat_sum // n_rs) if n_rs else 0,
            "avg_chars": (ch_sum // n_rs) if n_rs else 0,
            "last": rs[-1]["scenario_id"] if rs else "",
        }

    states = {}
    for s, b in expected_cells:
        exp = exp_turns.get((s, b), 1)
        rs = cell_rows.get((s, b), [])
        good = sum(1 for r in rs if _row_conformed(r))
        bad = sum(1 for r in rs if (r.get("metrics") or {}).get("http_status") not in (200, None))
        if bad > 0:
            st = "err"
        elif good >= exp:
            st = "done"
        elif len(rs) >= exp:
            st = "err"
        elif len(rs) > 0:
            st = "running" if active else "err"
        else:
            st = "pending"
        states[(s, b)] = st

    scored_cnt = 0
    judged_passed = 0
    for r in results:
        if "passed" in (r.get("metrics") or {}):
            scored_cnt += 1
            if _row_judged(r):
                judged_passed += 1

    if total and len(results) < total and active:
        if cells:
            for s, b in expected_cells:
                if states[(s, b)] in ("pending", "running"):
                    states[(s, b)] = "running"
                    break
        else:
            marked = False
            for b in back_ids:
                for s in scen_ids:
                    if states[(s, b)] in ("pending", "running"):
                        states[(s, b)] = "running"
                        marked = True
                        break
                if marked:
                    break

    grid_list = []
    for s, b in expected_cells:
        entry: dict[str, Any] = {"scenario": s, "backend": b, "state": states[(s, b)]}
        rows = cell_rows.get((s, b), [])
        if rows and not any("passed" in (r.get("metrics") or {}) for r in rows):
            entry.update(cell_review_summary(rows))
        grid_list.append(entry)

    feed = [_make_feed_item(r) for r in results[-14:]]

    arm_cards = frozen_arm_cards(run_path, back_ids)
    models = arm_models(run_path, arm_cards)
    actors = judge_actors if judge_actors is not None else read_judge_actors(run_path)
    cp = check_precision if check_precision is not None else load_check_precision(run_path)
    titles = profile_titles(run_path, back_ids)
    canon = canonical_rows if canonical_rows is not None else _read_jsonl(run_path / "judge.jsonl", strict=False)
    judging_info = judging if judging is not None else judge_summary(run_path)

    return {
        "run": run_path.name,
        "family": run_family(run_path),
        "check_precision": cp,
        "set": set_id,
        "done": len(results),
        "total": total,
        "warning": (
            None
            if CLASSIFIER_SOURCE
            else "This page cannot classify assertions ("
            + _CLASSIFIER_ERROR
            + "), so every failure is shown as unexpected behaviour. "
            "Serve the dashboard from a checkout whose harness package "
            "matches this script."
        ),
        "conformant": sum(1 for v in states.values() if v == "done"),
        "unexpected": sum(1 for v in states.values() if v == "err"),
        "judged_passed": judged_passed,
        "judged_scored": scored_cnt,
        "scenarios": scen_ids,
        "backends": back_ids,
        "arms": arms,
        "arm_cards": arm_cards,
        "judge": scout_summary(canon, back_ids) if canon else [],
        "judge_actors": sorted(actors.keys()),
        "judging": judging_info,
        "judge_combined": combined_judge_summary(actors, back_ids),
        "grid": grid_list,
        "feed": feed,
        "models": models,
        "status_legend": status_legend(),
        "profile_titles": titles,
        "finished": bool(total) and len(results) >= total,
    }


def build_status(
    run: Path | str | None, *, since_seq: int | None = None
) -> dict[str, Any]:
    if not run:
        return {"run": None}
    from harness.validate.run_index import GLOBAL_RUN_INDEX

    return GLOBAL_RUN_INDEX.get(Path(run)).get_status(since_seq=since_seq)


def build_detail_from_rows(
    run_path: Path,
    scenario: str,
    backend: str,
    rows: list[dict[str, Any]],
    *,
    traces: list[dict[str, Any]] | None = None,
    judge_by_actor: dict[str, dict[str, Any]] | None = None,
    chart_fixture: dict[str, Any] | None = None,
    chart_loaded: bool = False,
    expectations: dict[str, Any] | None = None,
    catalyst_expected: dict[str, Any] | None = None,
    family: str | None = None,
) -> dict[str, Any]:
    """Assemble one cell detail payload from pre-filtered rows and cached sidecars."""
    fam = family or run_family(run_path)
    cat_exp = (
        catalyst_expected
        if catalyst_expected is not None or fam != "catalyst"
        else catalyst_expectation(run_path, scenario)
    )
    sorted_rows = sorted(rows, key=lambda r: r.get("turn", 0))
    exp = expectations if expectations is not None else _read_scenario_expectations(run_path, scenario)
    chart_obj = chart_fixture if chart_loaded else run_chart(run_path, scenario)
    trace_rows = traces if traces is not None else _read_jsonl(run_path / "trace.jsonl", strict=False)

    turns = []
    for r in sorted_rows:
        m = r.get("metrics") or {}
        resp = r.get("response") or {}
        request = r.get("request") or {}
        if "passed" in m:
            turns.append(
                {
                    "turn": r.get("turn"),
                    "question": request.get("question", ""),
                    "answer": format_sql(resp.get("answer")) or "",
                    "status": m.get("http_status"),
                    "latency_ms": m.get("latency_ms"),
                    "chars": m.get("answer_chars"),
                    "error": r.get("error"),
                    "catalyst": {
                        "passed": m.get("passed"),
                        "question": resp.get("question"),
                        "baseOutcome": resp.get("baseOutcome"),
                        "baseAnswerText": resp.get("baseAnswerText"),
                        "baseSql": format_sql(resp.get("baseSql")),
                        "expectedBaseOutcome": resp.get("expectedBaseOutcome"),
                        "turns": [
                            {**turn, "sql": format_sql(turn.get("sql"))}
                            for turn in resp.get("turns") or []
                        ],
                        "failedAssertions": resp.get("failedAssertions") or [],
                        "resultPreview": resp.get("resultPreview"),
                        "conformed": not any(
                            (item.get("class") or assertion_class(item.get("name") or ""))
                            == "conformance"
                            for item in resp.get("failedAssertions") or []
                        ),
                    },
                }
            )
            continue
        tr = (
            match_trace(
                trace_rows,
                trace_model_for_result(r, backend),
                r.get("started_at"),
                r.get("ended_at"),
                question=request.get("question"),
                session=request.get("session"),
                request_id=request.get("request_id"),
                transport=trace_transport_for_result(r),
            )
            if trace_rows
            else None
        )
        direct_answer, embedded_indepth = split_answer_sections(resp.get("answer"))
        review_artifact = prepare_indepth_review(
            in_depth_artifact(r, resp, embedded_indepth), tr, chart_obj
        )
        answer_validation = prepare_answer_review(
            resp.get("answerValidation"),
            direct_answer,
            tr,
            chart_obj,
        )
        evidence_response = response_for_displayed_evidence(
            resp, direct_answer, review_artifact, embedded_indepth
        )
        sources_v1 = annotate_sources(
            build_sources(evidence_response, chart_obj),
            direct_answer,
            resp.get("blocks"),
            review_artifact,
        )
        refs = evidence_response.get("references") or evidence_response.get("citations") or []
        answer_confidence_display, indepth_confidence_display = section_confidence_displays(
            tr, resp.get("confidence")
        )
        turns.append(
            {
                "turn": r.get("turn"),
                "question": request.get("question", ""),
                "answer": direct_answer,
                "answer_validation": answer_validation,
                "answer_view": answer_section_view(
                    answer_validation,
                    answer_confidence_display,
                    direct_answer,
                    resp.get("blocks"),
                    resp.get("references"),
                ),
                "indepth_view": indepth_section_view(
                    review_artifact, indepth_confidence_display, sources_v1
                ),
                "indepth_latency_ms": (r.get("indepth") or {}).get("latency_ms"),
                "review_sources": review_artifact.get("reviewSources") or {},
                "blocks": resp.get("blocks") or [],
                "sources": sources_v1,
                "refs": refs,
                "status": m.get("http_status"),
                "latency_ms": m.get("latency_ms"),
                "chars": m.get("answer_chars"),
                "citations": m.get("citation_count"),
                "error": r.get("error"),
                "trace": (
                    {
                        "answer_confidence": tr.get("answer_confidence"),
                        "indepth_confidence": tr.get("indepth_confidence"),
                        "answer_text": tr.get("answer_text", ""),
                        "in_depth_claims": tr.get("in_depth_claims") or [],
                        "steps": tr.get("steps") or [],
                        "stage_timings": extract_stage_timings(tr),
                        "models": tr.get("models") or {},
                    }
                    if tr
                    else None
                ),
            }
        )

    if judge_by_actor is None:
        judge_map = {
            actor: next(
                (
                    r
                    for r in rows_
                    if r.get("scenario_id") == scenario and r.get("backend_id") == backend
                ),
                None,
            )
            for actor, rows_ in read_judge_actors(run_path).items()
        }
        judge_clean = {a: r for a, r in judge_map.items() if r}
    else:
        judge_clean = {a: r for a, r in judge_by_actor.items() if r}

    return {
        "scenario": scenario,
        "backend": backend,
        "expectations": exp,
        "catalystExpected": cat_exp,
        "turns": turns,
        "judge": judge_clean,
    }


def build_detail(run: Path | str | None, scenario: str, backend: str) -> dict[str, Any]:
    if not run or not scenario or not backend:
        return {"turns": []}
    from harness.validate.run_index import GLOBAL_RUN_INDEX

    return GLOBAL_RUN_INDEX.get(Path(run)).get_detail(scenario, backend)


def deduplicate_dashboard_details(
    details: dict[str, dict[str, Any]]
) -> tuple[list[list[str]], list[dict[str, Any]], list[list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Pool repeated context records, source cards, and raw refs across all detail cells."""
    record_pool: list[list[str]] = []
    record_map: dict[tuple[str, str], int] = {}

    sources_pool: list[dict[str, Any]] = []
    sources_map: dict[tuple[Any, ...], int] = {}

    refs_pool: list[list[dict[str, Any]]] = []
    refs_map: dict[str, int] = {}

    def _pool_record(item: Any) -> int:
        if isinstance(item, dict):
            sid = str(item.get("source_id") or "")
            reason = str(item.get("reason") or "")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            sid, reason = str(item[0] or ""), str(item[1] or "")
        else:
            sid, reason = str(item or ""), ""
        key = (sid, reason)
        idx = record_map.get(key)
        if idx is None:
            idx = len(record_pool)
            record_map[key] = idx
            record_pool.append([sid, reason])
        return idx

    def _pool_sources_obj(sources_obj: Any) -> dict[str, Any]:
        if not isinstance(sources_obj, dict):
            return {}
        raw_sources = sources_obj.get("sources") or []
        diag = {
            k: v
            for k, v in (sources_obj.get("diagnostics") or {}).items()
            if v
        }
        if not raw_sources:
            return {"diagnostics": diag} if diag else {}
        refs_list = []
        for s in raw_sources:
            if not isinstance(s, dict):
                continue
            title = s.get("title") or ""
            rtype = s.get("resource_type") or ""
            sdate = s.get("date") or ""
            sections = s.get("sections") or []
            rec_lbl = s.get("record_label") or s.get("resolution_status") or "unknown"
            rec_tone = s.get("record_tone") or "neutral"
            sup_lbl = s.get("support_label") or s.get("support_status") or "unchecked"
            sup_tone = s.get("support_tone") or "neutral"
            facts_used = (s.get("facts_used") or [])[:4]
            src_txt = s.get("source_text") or ""
            key = (
                title,
                rtype,
                sdate,
                tuple(sections),
                rec_lbl,
                rec_tone,
                sup_lbl,
                sup_tone,
                tuple(str(f) for f in facts_used),
                src_txt,
            )
            p_idx = sources_map.get(key)
            if p_idx is None:
                p_idx = len(sources_pool)
                sources_map[key] = p_idx
                sources_pool.append(
                    {
                        "title": title,
                        "resource_type": rtype,
                        "date": sdate,
                        "sections": sections,
                        "record_label": rec_lbl,
                        "record_tone": rec_tone,
                        "support_label": sup_lbl,
                        "support_tone": sup_tone,
                        "facts_used": facts_used,
                        "source_text": src_txt,
                    }
                )
            refs_list.append(
                [
                    p_idx,
                    s.get("source_id") or "",
                    s.get("citation_index") if s.get("citation_index") is not None else s.get("record_index"),
                    s.get("chart_record_index") if s.get("chart_record_index") is not None else s.get("record_index"),
                    s.get("record_index"),
                ]
            )
        out: dict[str, Any] = {"sources_pool_refs": refs_list}
        if diag:
            out["diagnostics"] = diag
        return out

    out_details: dict[str, dict[str, Any]] = {}
    for cell_key, cell_detail in details.items():
        if not isinstance(cell_detail, dict):
            continue
        new_turns = []
        for turn in cell_detail.get("turns") or []:
            if not isinstance(turn, dict):
                continue
            t = dict(turn)
            # 1. Pool sources
            if "sources" in t and isinstance(t["sources"], dict):
                t["sources"] = _pool_sources_obj(t["sources"])
            if "review_sources" in t and isinstance(t["review_sources"], dict):
                t["review_sources"] = _pool_sources_obj(t["review_sources"])
            av = t.get("answer_validation")
            if isinstance(av, dict):
                av_view = t.get("answer_view")
                if isinstance(av_view, dict) and av_view.get("show_original"):
                    av_copy = {
                        "status": av.get("status"),
                        "originalAnswer": av.get("originalAnswer"),
                        "originalBlocks": av.get("originalBlocks") or [],
                        "originalSources": _pool_sources_obj(av.get("originalSources")),
                    }
                    t["answer_validation"] = av_copy
                else:
                    t["answer_validation"] = {"status": av.get("status")} if av.get("status") else None

            # 2. Slim indepth_view when body_html was legacy or not_in_profile
            iv = t.get("indepth_view")
            if isinstance(iv, dict):
                iv_copy = dict(iv)
                iv_copy.pop("body_html", None)
                t["indepth_view"] = iv_copy

            # 3. Pool refs
            raw_refs = t.pop("refs", None) or []
            if raw_refs:
                slim_refs = [
                    (
                        {"index": r.get("index"), "resourceType": r.get("resourceType")}
                        if isinstance(r, dict)
                        else r
                    )
                    for r in raw_refs
                ]
                r_key = json.dumps(slim_refs, sort_keys=True, ensure_ascii=False)
                r_idx = refs_map.get(r_key)
                if r_idx is None:
                    r_idx = len(refs_pool)
                    refs_map[r_key] = r_idx
                    refs_pool.append(slim_refs)
                t["refs_pool_id"] = r_idx

            # 4. Pool trace context steps
            tr = t.get("trace")
            if isinstance(tr, dict):
                tr_copy = dict(tr)
                new_steps = []
                for step in tr_copy.get("steps") or []:
                    if not isinstance(step, dict):
                        continue
                    if step.get("role") == "stage_timing":
                        continue
                    if step.get("role") == "context":
                        s_copy = {
                            k: v
                            for k, v in step.items()
                            if k not in ("included", "excluded", "included_ids")
                        }
                        inc = step.get("included") or []
                        exc = step.get("excluded") or []
                        if inc:
                            s_copy["included_pool_ids"] = [_pool_record(x) for x in inc]
                        if exc:
                            s_copy["excluded_pool_ids"] = [_pool_record(x) for x in exc]
                        new_steps.append(s_copy)
                    else:
                        new_steps.append(step)
                tr_copy["steps"] = new_steps
                t["trace"] = tr_copy

            new_turns.append(t)
        out_details[cell_key] = {**cell_detail, "turns": new_turns}

    return record_pool, sources_pool, refs_pool, out_details


def build_dashboard_data(run_dir: Path | str) -> dict[str, Any]:
    """Assemble a complete deduplicated `openclinai.dashboard.v2` packet for `run_dir` in O(N) time."""
    run_path = Path(run_dir)
    events = _read_jsonl(run_path / "events.jsonl", strict=False)
    results = review_results(run_path, strict=False)
    traces = _read_jsonl(run_path / "trace.jsonl", strict=False)
    judge_actors = read_judge_actors(run_path)
    canonical_rows = _read_jsonl(run_path / "judge.jsonl", strict=False)
    check_precision = load_check_precision(run_path)
    judging = judge_summary(run_path)

    st = build_status_from_loaded(
        run_path,
        events=events,
        results=results,
        judge_actors=judge_actors,
        canonical_rows=canonical_rows,
        check_precision=check_precision,
        judging=judging,
    )
    st.pop("check_precision_html", None)

    rows_by_cell: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for r in results:
        rows_by_cell.setdefault((r.get("scenario_id"), r.get("backend_id")), []).append(r)

    judge_by_cell: dict[tuple[Any, Any], dict[str, dict[str, Any]]] = {}
    for actor, a_rows in judge_actors.items():
        for jr in a_rows:
            cell_k = (jr.get("scenario_id"), jr.get("backend_id"))
            judge_by_cell.setdefault(cell_k, {}).setdefault(actor, jr)

    family = str(st.get("family") or run_family(run_path) or "chartsearchai")
    chart_cache: dict[str, dict[str, Any] | None] = {}
    exp_cache: dict[str, dict[str, Any]] = {}
    cat_exp_cache: dict[str, dict[str, Any] | None] = {}

    details: dict[str, dict[str, Any]] = {}
    for g in st.get("grid") or []:
        if g.get("state") == "pending":
            continue
        s, b = g["scenario"], g["backend"]
        if s not in chart_cache:
            chart_cache[s] = run_chart(run_path, s)
            exp_cache[s] = _read_scenario_expectations(run_path, s)
            cat_exp_cache[s] = catalyst_expectation(run_path, s) if family == "catalyst" else None
        details[f"{s}|{b}"] = build_detail_from_rows(
            run_path,
            s,
            b,
            rows_by_cell.get((s, b), []),
            traces=traces,
            judge_by_actor=judge_by_cell.get((s, b), {}),
            chart_fixture=chart_cache[s],
            chart_loaded=True,
            expectations=exp_cache[s],
            catalyst_expected=cat_exp_cache[s],
            family=family,
        )

    record_pool, sources_pool, refs_pool, dedup_details = deduplicate_dashboard_details(details)
    return {
        "schema": "openclinai.dashboard.v2",
        "schema_version": 2,
        "family": family,
        "status": st,
        "record_pool": record_pool,
        "sources_pool": sources_pool,
        "refs_pool": refs_pool,
        "details": dedup_details,
    }


def write_dashboard_data(
    run_dir: Path | str,
    payload: dict[str, Any] | None = None,
    *,
    shard_threshold: int | None = None,
) -> Path:
    """Write `dashboard-data.json` (and sharded `dashboard-details/` packets when large) into `run_dir`."""
    run_path = Path(run_dir)
    data = payload if payload is not None else build_dashboard_data(run_path)
    threshold = _resolved_shard_threshold(shard_threshold)
    details = data.get("details") or {}
    shards_dir = run_path / "dashboard-details"

    if len(details) >= threshold:
        by_backend: dict[str, dict[str, Any]] = {}
        for cell_key, cell_obj in details.items():
            _, _, backend_id = cell_key.partition("|")
            by_backend.setdefault(backend_id, {})[cell_key] = cell_obj

        ordered_backends = list((data.get("status") or {}).get("backends") or [])
        for b in sorted(by_backend):
            if b not in ordered_backends:
                ordered_backends.append(b)

        if shards_dir.exists():
            shutil.rmtree(shards_dir)
        shards_dir.mkdir(parents=True, exist_ok=True)

        detail_shards: dict[str, str] = {}
        for idx, backend_id in enumerate(ordered_backends):
            shard_cells = by_backend.get(backend_id)
            if not shard_cells:
                continue
            rel_path = _shard_rel_path(idx, backend_id)
            (run_path / rel_path).write_text(
                json.dumps(shard_cells, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            detail_shards[backend_id] = rel_path

        out_data = {
            **data,
            "details": {},
            "detail_shards": detail_shards,
        }
    else:
        if shards_dir.exists():
            shutil.rmtree(shards_dir)
        out_data = dict(data)
        out_data.pop("detail_shards", None)

    out = run_path / "dashboard-data.json"
    out.write_text(json.dumps(out_data, ensure_ascii=False), encoding="utf-8")
    return out
