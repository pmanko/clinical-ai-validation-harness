"""Generate a standalone, self-contained HTML validation report from one or more
runs' results.jsonl + run_manifest.json (spec 006 SC-006.4/5).

No build step, no server, no CDN, no ESM import — open report.html in a browser.
The report embeds every run as one inert JSON blob and a vanilla-JS shell renders
from it: a run selector (exactly one run active at a time), a per-backend
comparison summary, then one CSS-grid band per question (turn) with one tile per
backend so same-question answers align vertically for comparison. Reviewers can
filter by scenario/question text, toggle individual backends on/off, and
drag-reorder the backend tiles within a single question to rank them (persisted to
localStorage, exported as rankings.json). A separate per-cell Scout-rubric
adjudication form on every tile serialises to feedback.jsonl in the shape the
repository expects (client-side; drop the file into the run dir).

Answer/block markdown is rendered to HTML in Python (escape-FIRST, then upgrade
the light markdown forms) so the untrusted-text injection contract is enforced on
the server side and stays unit-testable; the blob carries the rendered HTML and
the JS injects it. This is the single source of the escaping contract.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reconcile import scout_summary


# The med-agent-team bridge gracefully degrades to a schema-valid envelope when
# its own LLM calls fail, so a degraded turn looks like a 200/json_valid/0-cites
# answer to the harness. Surface it from the answer text so a broken backend is
# visible instead of silently passing as an empty answer.
_FALLBACK_MARKER = "could not produce a complete answer"


def _is_degraded(r: dict[str, Any]) -> bool:
    answer = (r.get("response") or {}).get("answer")
    return isinstance(answer, str) and _FALLBACK_MARKER in answer.lower()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _render_answer(text: Any) -> str:
    """Render the answer's light markdown to HTML, escaping the untrusted model
    text FIRST so it can never inject markup, then upgrading the two structural
    forms the v2 synthesis prompt emits: `**bold**` section headers (-> <strong>)
    and `##` ATX headings (-> <h3>). Newlines stay as-is — the .ans { pre-wrap }
    style already renders them as line breaks."""
    s = html.escape("" if text is None else str(text))
    # A literal backslash-n the 4B may copy verbatim from the v2 prompt's JSON-string
    # few-shot -> a real newline (pre-wrap renders it), so a copied escape can't
    # masquerade as worse v2 output and confound the A/B.
    s = s.replace("\\n", "\n")
    s = re.sub(r"^##\s+(.+?)\s*$", r"<h3>\1</h3>", s, flags=re.MULTILINE)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


def _render_blocks(blocks: Any) -> str:
    """Render the bridge's `blocks[]` (kind:"table" enumerations the chart-answer
    envelope carries alongside the prose answer) as HTML tables, reusing the
    existing `.ref` chip for each cell's chart-record indices. A missing column
    key in a row -> empty cell rather than a KeyError, so a partial row can't
    drop the whole report."""
    out = []
    for b in blocks or []:
        if not isinstance(b, dict) or b.get("kind") != "table":
            continue
        cols = b.get("columns") or []
        head = "".join(f"<th>{_esc(c.get('label'))}</th>" for c in cols)
        rows_html = []
        for row in b.get("rows") or []:
            cells = row.get("cells") or {}
            tds = []
            for c in cols:
                cell = cells.get(c.get("key")) or {}
                refs = "".join(
                    f"<span class='ref'>[{_esc(i)}]</span>" for i in (cell.get("refs") or [])
                )
                tds.append(f"<td>{_esc(cell.get('text'))}{(' ' + refs) if refs else ''}</td>")
            rows_html.append("<tr>" + "".join(tds) + "</tr>")
        title = f"<div class='block-title'>{_esc(b.get('title'))}</div>" if b.get("title") else ""
        out.append(
            f"<div class='block'>{title}<table class='block-tbl'>"
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>"
        )
    return "".join(out)


def _render_refs(references: Any) -> str:
    """The first-8 + overflow reference chips that sit under the answer."""
    refs = references or []
    if not refs:
        return ""
    shown = " ".join(
        f"<span class='ref'>[{_esc(x.get('index'))}] {_esc(x.get('resourceType'))}</span>"
        for x in refs[:8]
    )
    more = f" <span class='more'>+{len(refs) - 8}</span>" if len(refs) > 8 else ""
    return f"<div class='refs'>{shown}{more}</div>"


def _render_chips(r: dict[str, Any]) -> str:
    """The deterministic metric chips: latency (warm on first turn), chart-refs
    COUNT (never a grounding signal), invalid-json, and the degraded-fallback
    flag (keyed on _is_degraded so the marker contract lives in one place)."""
    m = r.get("metrics") or {}
    chips = [
        f"<span class='chip{' warm' if m.get('first_turn') else ''}'>⏱ {_esc(m.get('latency_ms'))}ms</span>",
        f"<span class='chip'>{_esc(m.get('citation_count'))} chart refs</span>",
    ]
    if not m.get("json_valid", True):
        chips.append("<span class='chip bad'>invalid</span>")
    if _is_degraded(r):
        chips.append("<span class='chip bad'>⚠ degraded</span>")
    return "".join(chips)


def _ordered_unique(values: list[Any]) -> list[Any]:
    seen: dict[Any, None] = {}
    for v in values:
        seen.setdefault(v, None)
    return list(seen)


def _backend_labels(events: list[dict[str, Any]]) -> dict[str, str]:
    # The backend's config descriptor (prompt variant + orchestrator/expert models),
    # carried on the backend_selected event so report columns are self-describing.
    # Falls back to modelName for runs recorded before the label was emitted.
    return {
        e["backend_id"]: (e.get("label") or e.get("modelName", ""))
        for e in events
        if e.get("event_type") == "backend_selected"
    }


def _avg(nums: list[int]) -> int:
    return round(sum(nums) / len(nums)) if nums else 0


def _box_stats(values: list[float]) -> dict[str, Any] | None:
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


# Numeric metrics worth a per-arm distribution (box-and-whisker). Only successful
# (HTTP 200) turns count — an errored turn is not a real measurement of speed/length.
_DIST_METRICS = [
    ("latency_ms", "latency (ms)"),
    ("citation_count", "chart references"),
    ("answer_chars", "answer length (chars)"),
]


def _metric_distributions(
    results: list[dict[str, Any]], backends: list[str]
) -> dict[str, Any]:
    """Per-arm box-and-whisker stats for each distribution metric, computed over the
    successful turns only. Shape: {metric_key: {label, series:[{backend, ...stats}]}}."""
    out: dict[str, Any] = {}
    for key, label in _DIST_METRICS:
        series = []
        for b in backends:
            vals = [
                (r.get("metrics") or {}).get(key)
                for r in results
                if r.get("backend_id") == b and (r.get("metrics") or {}).get("http_status") == 200
            ]
            stats = _box_stats([v for v in vals if isinstance(v, (int, float))])
            if stats:
                series.append({"backend": b, **stats})
        out[key] = {"label": label, "series": series}
    return out


def _load_judge(run_dir: Path) -> list[dict[str, Any]]:
    """Optional reviewer scores at run_dir/judge.jsonl: one line per (scenario_id,
    backend_id) carrying faithfulness + correctness in [0,1] and a short note — the
    LLM-dependent quality layer the raw metrics can't capture. Absent file -> no layer."""
    path = run_dir / "judge.jsonl"
    if not path.exists():
        return []
    return _read_jsonl(path)


def _summary_rows(results: list[dict[str, Any]], backends: list[str], labels: dict[str, str]) -> list[dict[str, Any]]:
    """Per-backend aggregates (the old summary table rows), precomputed so the JS
    renders a table without re-deriving any contract."""
    rows = []
    for b in backends:
        rs = [r for r in results if r.get("backend_id") == b]
        lat = [r["metrics"]["latency_ms"] for r in rs if r.get("metrics")]
        cites = sum(r["metrics"].get("citation_count", 0) for r in rs if r.get("metrics"))
        rows.append(
            {
                "backend_id": b,
                "label": labels.get(b, ""),
                "turns": len(rs),
                "avg_latency_ms": _avg(lat),
                "max_latency_ms": max(lat) if lat else 0,
                "total_chart_refs": cites,
                "degraded": sum(1 for r in rs if _is_degraded(r)),
                "errors": sum(1 for r in rs if r.get("error")),
            }
        )
    return rows


def _cell_blob(r: dict[str, Any]) -> dict[str, Any]:
    """One rendered cell for the blob. Answer/block HTML is rendered in Python
    (escape-FIRST) so the injection contract is enforced and testable; the JS
    just injects the strings. Carries only the surfaced metric subset + the
    precomputed degraded flag."""
    m = r.get("metrics") or {}
    resp = r.get("response") or {}
    return {
        "error": r.get("error"),
        "http_status": m.get("http_status"),
        "answer_html": _render_answer(resp.get("answer")),
        "refs_html": _render_refs(resp.get("references")),
        "blocks_html": _render_blocks(resp.get("blocks")),
        "chips_html": _render_chips(r),
        "degraded": _is_degraded(r),
        "metrics": {
            "latency_ms": m.get("latency_ms"),
            "http_status": m.get("http_status"),
            "citation_count": m.get("citation_count"),
            "first_turn": m.get("first_turn"),
            "json_valid": m.get("json_valid", True),
        },
    }


def _run_blob(run_dir: Path) -> dict[str, Any]:
    """Assemble one run into the blob shape. Reads the same three files as before;
    a missing run_manifest.json still raises (contract), results/events tolerated."""
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    results = _read_jsonl(run_dir / "results.jsonl")
    events = _read_jsonl(run_dir / "events.jsonl")
    labels = _backend_labels(events)

    backends = _ordered_unique([r.get("backend_id") for r in results])
    scenario_ids = _ordered_unique([r.get("scenario_id") for r in results])
    run_id = manifest.get("run_id", "")
    otel = manifest.get("otel", {})

    scenarios = []
    for sid in scenario_ids:
        rs = [r for r in results if r.get("scenario_id") == sid]
        turns_seen = _ordered_unique([r.get("turn") for r in rs])
        index = {(r.get("turn"), r.get("backend_id")): r for r in rs}
        questions = {r.get("turn"): r.get("request", {}).get("question", "") for r in rs}
        turns = []
        for t in turns_seen:
            cells = {}
            for b in backends:
                r = index.get((t, b))
                if r is not None:
                    cells[b] = _cell_blob(r)
            turns.append({"turn": t, "question": questions.get(t, ""), "cells": cells})
        scenarios.append({"scenario_id": sid, "turns": turns})

    # Patient grounding: the chart-QA runs are about a real OpenMRS patient. Surface the
    # patient(s) the run actually hit (results' request.patient) with a deep link to the live
    # chart, plus name/identifier when the manifest carries a `patients` map (uuid -> meta;
    # the runner can populate it from OpenMRS — falls back to UUID + chart link without it).
    chart_base = manifest.get(
        "openmrs_chart_base", "https://openmrs.openclinai.org/openmrs/spa/patient")
    patient_meta = manifest.get("patients", {})
    patient_uuids = _ordered_unique(
        [(r.get("request") or {}).get("patient") for r in results if (r.get("request") or {}).get("patient")])
    patients = []
    for u in patient_uuids:
        profile = dict(patient_meta.get(u) or {})  # display/identifier/medications/vitals/counts...
        profile["uuid"] = u
        profile["chart_url"] = f"{chart_base}/{u}/chart"
        patients.append(profile)

    return {
        "run_id": run_id,
        "meta": {
            "run_id": run_id,
            "component": manifest.get("component"),
            "git_sha": (manifest.get("git_sha") or "")[:10],
            "dataset_id": manifest.get("dataset_id"),
            "provider": otel.get("gen_ai.provider.name", "?"),
            "generated_at": manifest.get("generated_at", ""),
        },
        "backends": backends,
        "labels": {b: labels.get(b, "") for b in backends},
        "scenarios": scenarios,
        "summary": _summary_rows(results, backends, labels),
        "metrics": _metric_distributions(results, backends),
        "judge": scout_summary(_load_judge(run_dir), backends),
        "judge_rows": _load_judge(run_dir),
        "patients": patients,
    }


# The reviewer rubric (Scout): accuracy/completeness/relevance 0-10,
# abstention_outcome, citation_groundedness, harm_fail, pass/fail decision, and a
# free-text note. Field names are PINNED by spec 006 FR-006.5 and consumed only by
# repository.find("feedback", query) — they must stay verbatim or feedback capture
# breaks. Rendered server-side once and cloned by the JS into each tile so the
# name=/data-* attributes are identical across tiles.
_RUBRIC_FORM = (
    "<details class='adj'><summary>adjudicate</summary>"
    "<div class='cell-form'>"
    "<div class='scores'>"
    "<label>acc<input type='number' min='0' max='10' step='1' name='accuracy'></label>"
    "<label>com<input type='number' min='0' max='10' step='1' name='completeness'></label>"
    "<label>rel<input type='number' min='0' max='10' step='1' name='relevance'></label>"
    "</div>"
    "<label>abstention<select name='abstention_outcome'>"
    "<option value='n-a'>n/a</option><option value='correct'>correct</option>"
    "<option value='over-abstained'>over-abstained</option>"
    "<option value='failed-to-abstain'>failed-to-abstain</option></select></label>"
    "<label>citations<select name='citation_groundedness'>"
    "<option value='n-a'>n/a</option><option value='supported'>supported</option>"
    "<option value='partly'>partly</option><option value='unsupported'>unsupported</option></select></label>"
    "<label class='harm'><input type='checkbox' name='harm_fail'> harm hard-fail</label>"
    "<div class='decision'>"
    "<label><input type='radio' name='decision' value='pass'> pass</label>"
    "<label><input type='radio' name='decision' value='fail'> fail</label></div>"
    "<textarea name='free_text' placeholder='notes'></textarea>"
    "</div></details>"
)


_STYLE = """
:root { --fg:#1a1a1a; --mut:#666; --line:#e2e2e2; --bg:#fafafa; }
* { box-sizing: border-box; }
body { font: 14px/1.5 -apple-system, system-ui, sans-serif; color: var(--fg); margin: 0; background: var(--bg); }
.topbar { position: sticky; top: 0; z-index: 30; background: #fff; border-bottom: 1px solid var(--line); padding: 12px 24px; }
.topbar h1 { font-size: 18px; margin: 0 0 8px; }
.controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.controls label { font-size: 12px; color: var(--mut); }
.controls select, .controls input[type=search], .controls input { font: inherit; padding: 3px 6px; }
.controls button { font: inherit; font-weight: 600; padding: 5px 12px; cursor: pointer; }
.controls .spacer { flex: 1; }
.toggles { display: flex; gap: 8px; align-items: center; border: 1px solid var(--line); border-radius: 6px; padding: 3px 8px; margin: 0; }
.toggles legend { font-size: 11px; color: var(--mut); padding: 0 4px; }
.toggles label { font-size: 12px; color: var(--fg); display: inline-flex; gap: 3px; align-items: center; }
.meta { color: var(--mut); font-size: 12px; font-family: ui-monospace, monospace; }
main { max-width: none; margin: 0 auto; padding: 16px 24px 120px; }
h2 { font-size: 15px; margin: 28px 0 8px; font-family: ui-monospace, monospace; }
table { border-collapse: collapse; width: 100%; background: #fff; }
th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #f3f3f3; font-weight: 600; font-size: 12px; }
.summary td, .summary th { text-align: center; }
.summary td.b { text-align: left; font-family: ui-monospace, monospace; }
.summary .model { display: block; color: var(--mut); font-size: 11px; }
.metrics-section { margin-top: 18px; }
.metrics-legend { color: #6b7280; font-size: 12px; margin: 2px 0 10px; }
.metrics-grid { display: flex; flex-wrap: wrap; gap: 16px; }
.boxplot-wrap { flex: 1 1 300px; min-width: 280px; max-width: 460px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 6px 8px; background: #fff; }
.boxplot { width: 100%; height: auto; }
.bp-title { font-size: 12px; font-weight: 600; fill: #1f2937; }
.bp-grid { stroke: #eef0f3; stroke-width: 1; }
.bp-ytick { font-size: 9px; fill: #8b949e; text-anchor: end; }
.bp-xtick { font-size: 10px; fill: #374151; text-anchor: middle; }
.bp-xn { font-size: 8.5px; fill: #9aa3af; text-anchor: middle; }
.bp-box { fill: rgba(39,72,160,.14); stroke: #2748a0; stroke-width: 1.3; }
.bp-median { stroke: #2748a0; stroke-width: 2.2; }
.bp-mean { stroke: #d9730d; stroke-width: 1.4; stroke-dasharray: 3 2; }
.bp-whisker, .bp-cap { stroke: #2748a0; stroke-width: 1; }
.bp-out { fill: #d9730d; opacity: .75; }
.judge-section { margin-top: 18px; }
.jb-faith { fill: #2748a0; }
.jb-corr { fill: #d9730d; }
.jb-acc { fill: #2748a0; }
.jb-comp { fill: #2f9e44; }
.jb-rel { fill: #d9730d; }
.jh-title { font-size: 13px; margin: 16px 0 5px; color: #374151; }
table.jheat { border-collapse: collapse; font-size: 11px; }
.jheat th, .jheat td { border: 1px solid #e5e7eb; padding: 3px 7px; text-align: center; }
.jheat th.jh-scen { text-align: left; font-weight: 400; font-family: ui-monospace, monospace; white-space: nowrap; }
.jh { cursor: pointer; font-variant-numeric: tabular-nums; }
.jh:hover { outline: 2px solid #2748a0; }
.jh-good { background: #d6f0d8; }
.jh-mid { background: #fdedc8; }
.jh-bad { background: #f6d2d2; }
.jh-na { color: #cbd5e1; }
.jh-note { margin-top: 8px; padding: 8px 10px; background: #f6f8fa; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 12px; color: #374151; min-height: 18px; }
.qband { display: grid; grid-template-columns: var(--qcol, 240px) 1fr; gap: 12px; align-items: start; border-top: 1px solid var(--line); padding: 12px 0; }
.qhead { position: sticky; left: 0; z-index: 1; background: var(--bg); align-self: start; }
.qhead .n { font-family: ui-monospace, monospace; font-weight: 700; color: var(--mut); }
.qhead .q { margin-top: 2px; }
.tiles { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(340px, 1fr); gap: 12px; align-items: stretch; overflow-x: auto; min-height: 60px; scroll-behavior: smooth; }
.tile { display: flex; flex-direction: column; border: 1px solid var(--line); border-radius: 10px; background: #fff; padding: 10px 12px; cursor: grab; user-select: none; }
.tile.dragging { opacity: .4; cursor: grabbing; }
.tile.empty { color: #bbb; align-items: center; justify-content: center; cursor: default; }
.tile-head { display: flex; gap: 6px; align-items: baseline; margin-bottom: 6px; }
.rank-badge { font: 11px ui-monospace, monospace; background: #eef3ff; color: #2748a0; border-radius: 4px; padding: 0 5px; }
.tile-head .backend { font-family: ui-monospace, monospace; font-weight: 700; font-size: 12px; }
.tile-head .label { color: var(--mut); font-size: 11px; }
.expand { font: 600 11px/1.2 ui-monospace, monospace; color: #2748a0; cursor: pointer; background: #eef3ff; border: 1px solid #c7d6f5; border-radius: 6px; padding: 4px 11px; align-self: flex-start; margin-top: 6px; }
.expand:hover { background: #dce6fb; }
.ans { white-space: pre-wrap; max-height: 20em; overflow: auto; }
.tile.expanded .ans { max-height: none; }
.refs { margin-top: 6px; }
.ref { display: inline-block; font-size: 10px; font-family: ui-monospace, monospace; background: #eef3ff; color: #2748a0; padding: 1px 4px; border-radius: 3px; margin: 1px; }
.more { color: var(--mut); font-size: 10px; }
.err { color: #a01; font-family: ui-monospace, monospace; font-size: 12px; }
.chips { margin-top: 6px; }
.chip { display: inline-block; font-size: 10px; font-family: ui-monospace, monospace; background: #eee; color: #444; padding: 1px 5px; border-radius: 3px; margin: 1px; }
.chip.warm { background: #fff3d6; color: #8a5a00; }
.chip.none { background: #fde8e8; color: #a01; }
.chip.bad { background: #a01; color: #fff; }
.adj { margin-top: 8px; font-size: 12px; }
.adj summary { cursor: pointer; color: #2748a0; font-size: 11px; }
.cell-form { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.cell-form .scores { display: flex; gap: 6px; }
.cell-form label { font-size: 11px; color: var(--mut); }
.cell-form input[type=number] { width: 38px; }
.cell-form select { font-size: 11px; }
.cell-form textarea { width: 100%; height: 36px; font: inherit; font-size: 11px; }
.cell-form .decision { display: flex; gap: 10px; }
.block { margin-top: 8px; }
.block-title { font-weight: 600; font-size: 12px; margin-bottom: 2px; }
.block-tbl th, .block-tbl td { font-size: 12px; padding: 4px 6px; }
.legend { color: var(--mut); font-size: 12px; margin-top: 24px; border-top: 1px solid var(--line); padding-top: 12px; }
[data-hidden="1"] { display: none !important; }
.patient-banner { background: #f0f6ff; border: 1px solid #c7d6f5; border-radius: 8px; padding: 8px 14px; margin: 0 0 14px; font-size: 13px; }
.patient-banner .pt-id { font-family: ui-monospace, monospace; font-weight: 700; }
.patient-banner .pt-name { font-weight: 600; }
.patient-banner a { color: #2748a0; font-weight: 600; text-decoration: none; margin-left: 8px; }
.patient-banner a:hover { text-decoration: underline; }
.patient-banner .pt-block + .pt-block { margin-top: 8px; border-top: 1px solid #d7e3fb; padding-top: 8px; }
.patient-banner .pt-head { font-size: 13px; }
.patient-banner .pt-demo { color: var(--mut); }
.patient-banner .pt-line { margin-top: 3px; font-size: 12px; color: #2a2a2a; }
.patient-banner .pt-lab { font-weight: 600; color: var(--mut); }
.patient-banner .pt-counts { color: var(--mut); }
.tile { position: relative; }
.tiles-wrap { position: relative; min-width: 0; }
.scroll-arrow { position: absolute; top: 0; bottom: 0; width: 30px; display: flex; align-items: center; justify-content: center; border: none; cursor: pointer; z-index: 5; font-size: 15px; color: #2748a0; background: rgba(255,255,255,.9); box-shadow: 0 0 8px rgba(0,0,0,.15); }
.scroll-arrow.left { left: -2px; } .scroll-arrow.right { right: -2px; }
.scroll-arrow.disabled { color: #cfcfcf; cursor: default; box-shadow: none; background: rgba(255,255,255,.4); pointer-events: none; }
.fs-btn { position: absolute; top: 8px; right: 8px; font-size: 12px; color: #2748a0; cursor: pointer; background: #eef3ff; border: 1px solid #c7d6f5; border-radius: 6px; padding: 2px 7px; line-height: 1; }
.fs-btn:hover { background: #dce6fb; }
.fs-overlay { display: none; position: fixed; inset: 0; background: rgba(20,20,20,.55); z-index: 100; }
.fs-overlay.open { display: flex; align-items: center; justify-content: center; }
.fs-modal { background: #fff; width: 92vw; height: 92vh; border-radius: 12px; padding: 18px 24px; overflow: auto; box-shadow: 0 8px 40px rgba(0,0,0,.35); }
.fs-close { float: right; font: inherit; font-weight: 600; cursor: pointer; background: #f3f3f3; border: 1px solid var(--line); border-radius: 6px; padding: 4px 12px; }
.fs-body { clear: both; }
.fs-body .ans { max-height: none; overflow: visible; font-size: 15px; line-height: 1.6; }

/* Print / Save-as-PDF: drop the interactive chrome, expand answers, keep tiles whole. */
@media print {
  .controls label, .controls select, .controls input, .controls button, .controls fieldset, .controls .spacer { display: none !important; }
  .adj, .expand { display: none !important; }
  .topbar { position: static; }
  .tiles { overflow: visible; }
  .tile { break-inside: avoid; }
  .ans { max-height: none !important; overflow: visible !important; }
  body { background: #fff; }
}
"""


# Vanilla-JS shell. Reads the inert JSON blob, renders the active run (run select
# swaps the whole <main>), and wires filter/toggle/drag/localStorage/export.
# Markdown/escaping already happened server-side; the JS injects the rendered HTML.
_SCRIPT = r"""
const DATA = JSON.parse(document.getElementById('report-data').textContent);
const RANK_KEY = 'validate-rankings';
// Optional feedback-capture endpoint. Empty = client-side download (default, never blocks). Set this
// (here, or via a served config) and adjudication/ranking exports POST to it instead — download stays
// the fallback on error. A same-origin path like '/api/feedback' lets a service live on this subdomain.
const FEEDBACK_ENDPOINT = '';
let activeRunId = (DATA.runs[0] || {}).run_id;

function runById(id){ return DATA.runs.find(r => r.run_id === id); }
function el(tag, cls){ const e = document.createElement(tag); if(cls) e.className = cls; return e; }

function loadAllRanks(){ try { return JSON.parse(localStorage.getItem(RANK_KEY)) || {}; } catch(e) { return {}; } }
function saveAllRanks(o){ localStorage.setItem(RANK_KEY, JSON.stringify(o)); }
function savedRankFor(group){ return loadAllRanks()[group] || null; }
function saveRanking(tilesEl){
  const order = [...tilesEl.querySelectorAll('.tile')].map(t => t.dataset.backend).filter(Boolean);
  const all = loadAllRanks(); all[tilesEl.dataset.rankgroup] = order; saveAllRanks(all);
}

function renderRunMeta(run){
  const m = run.meta;
  return 'run ' + m.run_id + ' · ' + m.component + ' · git ' + m.git_sha +
         ' · ' + m.dataset_id + ' · provider ' + m.provider + ' · ' + m.generated_at;
}

function renderSummary(run){
  const sec = el('section', 'summary-section');
  sec.innerHTML = '<h2>comparison summary</h2>';
  const rows = run.summary.map(s =>
    "<tr><td class='b'>" + htmlEsc(s.backend_id) + "<span class='model'>" + htmlEsc(s.label) + "</span></td>" +
    '<td>' + s.turns + '</td><td>' + s.avg_latency_ms + ' ms</td><td>' + s.max_latency_ms + ' ms</td>' +
    '<td>' + s.total_chart_refs + '</td><td>' + s.degraded + '</td><td>' + s.errors + '</td></tr>'
  ).join('');
  const tbl = el('table', 'summary');
  tbl.innerHTML = '<thead><tr><th>backend</th><th>turns</th><th>avg latency</th>' +
    '<th>max latency</th><th>total chart refs</th><th>degraded</th><th>errors</th></tr></thead>' +
    '<tbody>' + rows + '</tbody>';
  sec.appendChild(tbl);
  return sec;
}

function bpShort(b){ return b.replace('med-agent-team-','').replace('-baseline','-base'); }
function bpNiceCeil(v){ if(v<=0) return 1; var p=Math.pow(10,Math.floor(Math.log10(v))); var f=v/p; var nf=f<=1?1:(f<=2?2:(f<=5?5:10)); return nf*p; }
function bpFmt(v){ v=Math.round(v); return v>=1000?((v/1000).toFixed(v>=10000?0:1)+'k'):String(v); }
function boxPlotSVG(label, series){
  var W=Math.max(320, 70+series.length*92), H=232, padL=46, padR=12, padT=22, padB=40, plotH=H-padT-padB;
  var maxV=0, i, s, o;
  for(i=0;i<series.length;i++){ s=series[i]; maxV=Math.max(maxV, s.whisker_hi, s.max); for(o=0;o<(s.outliers||[]).length;o++) maxV=Math.max(maxV, s.outliers[o]); }
  var nm=bpNiceCeil(maxV);
  function Y(v){ return padT + plotH - (v/nm)*plotH; }
  var step=(W-padL-padR)/series.length;
  var g='<svg viewBox="0 0 '+W+' '+H+'" class="boxplot" role="img" aria-label="'+htmlEsc(label)+'">';
  g+='<text x="'+padL+'" y="13" class="bp-title">'+htmlEsc(label)+'</text>';
  var ticks=[0,0.25,0.5,0.75,1], t, yy, val;
  for(t=0;t<ticks.length;t++){ val=nm*ticks[t]; yy=Y(val); g+='<line x1="'+padL+'" y1="'+yy+'" x2="'+(W-padR)+'" y2="'+yy+'" class="bp-grid"/>'; g+='<text x="'+(padL-5)+'" y="'+(yy+3)+'" class="bp-ytick">'+bpFmt(val)+'</text>'; }
  for(i=0;i<series.length;i++){
    s=series[i];
    var cx=padL+step*i+step/2, bw=Math.min(42, step*0.52), x0=cx-bw/2, x1=cx+bw/2;
    g+='<line x1="'+cx+'" y1="'+Y(s.whisker_lo)+'" x2="'+cx+'" y2="'+Y(s.whisker_hi)+'" class="bp-whisker"/>';
    g+='<line x1="'+(x0+7)+'" y1="'+Y(s.whisker_hi)+'" x2="'+(x1-7)+'" y2="'+Y(s.whisker_hi)+'" class="bp-cap"/>';
    g+='<line x1="'+(x0+7)+'" y1="'+Y(s.whisker_lo)+'" x2="'+(x1-7)+'" y2="'+Y(s.whisker_lo)+'" class="bp-cap"/>';
    g+='<rect x="'+x0+'" y="'+Y(s.q3)+'" width="'+bw+'" height="'+Math.max(1,Y(s.q1)-Y(s.q3))+'" class="bp-box"/>';
    g+='<line x1="'+x0+'" y1="'+Y(s.median)+'" x2="'+x1+'" y2="'+Y(s.median)+'" class="bp-median"/>';
    g+='<line x1="'+x0+'" y1="'+Y(s.mean)+'" x2="'+x1+'" y2="'+Y(s.mean)+'" class="bp-mean"/>';
    for(o=0;o<(s.outliers||[]).length;o++){ g+='<circle cx="'+cx+'" cy="'+Y(s.outliers[o])+'" r="2.1" class="bp-out"/>'; }
    g+='<text x="'+cx+'" y="'+(H-24)+'" class="bp-xtick">'+htmlEsc(bpShort(s.backend))+'</text>';
    g+='<text x="'+cx+'" y="'+(H-13)+'" class="bp-xn">n'+s.n+' · md '+bpFmt(s.median)+'</text>';
  }
  g+='</svg>';
  var wrap=el('div','boxplot-wrap'); wrap.innerHTML=g; return wrap;
}
function renderMetrics(run){
  var sec=el('section','metrics-section');
  sec.innerHTML='<h2>metric distributions</h2><p class="metrics-legend"><b>What each is:</b> latency = end-to-end response time (ms) · chart references = citations per answer (a grounding-density proxy) · answer length = characters. <b>Reading a box:</b> the box spans the middle 50% of scenarios (q1–q3), the solid line is the median, the dashed line the mean, whiskers reach 1.5×IQR, dots are outliers. Successful turns only.</p>';
  var m=run.metrics||{}, keys=['latency_ms','citation_count','answer_chars'], k, md;
  var grid=el('div','metrics-grid'), any=false;
  for(k=0;k<keys.length;k++){ md=m[keys[k]]; if(md&&md.series&&md.series.length){ grid.appendChild(boxPlotSVG(md.label, md.series)); any=true; } }
  if(!any){ sec.innerHTML+='<p class="muted">no successful turns to chart yet.</p>'; }
  sec.appendChild(grid);
  return sec;
}

function fmt10(v){ return v==null ? '—' : (Math.round(v*10)/10); }
function judgeBarsSVG(series){
  var arms=[]; for(var k=0;k<series.length;k++){ if(series[k].n>0) arms.push(series[k]); }
  var W=Math.max(380, 60+arms.length*112), H=212, padL=30, padR=12, padT=20, padB=46, plotH=H-padT-padB;
  function Y(v){ return padT+plotH-(v/10)*plotH; }
  var step=(W-padL-padR)/Math.max(1,arms.length);
  var g='<svg viewBox="0 0 '+W+' '+H+'" class="boxplot" role="img" aria-label="Scout quality by arm">';
  g+='<text x="'+padL+'" y="13" class="bp-title">accuracy (blue) · completeness (green) · relevance (orange) — 0–10</text>';
  var ticks=[0,2.5,5,7.5,10], t, yy;
  for(t=0;t<ticks.length;t++){ yy=Y(ticks[t]); g+='<line x1="'+padL+'" y1="'+yy+'" x2="'+(W-padR)+'" y2="'+yy+'" class="bp-grid"/>'; g+='<text x="'+(padL-4)+'" y="'+(yy+3)+'" class="bp-ytick">'+ticks[t]+'</text>'; }
  for(var i=0;i<arms.length;i++){
    var s=arms[i], cx=padL+step*i+step/2, bw=Math.min(13, step*0.17);
    var vals=[[s.accuracy_mean||0,'jb-acc'],[s.completeness_mean||0,'jb-comp'],[s.relevance_mean||0,'jb-rel']];
    for(var v=0;v<3;v++){ var x=cx+(v-1)*(bw+2)-bw/2; g+='<rect x="'+x+'" y="'+Y(vals[v][0])+'" width="'+bw+'" height="'+((vals[v][0]/10)*plotH)+'" class="'+vals[v][1]+'"/>'; }
    g+='<text x="'+cx+'" y="'+(H-26)+'" class="bp-xtick">'+htmlEsc(bpShort(s.backend))+'</text>';
    g+='<text x="'+cx+'" y="'+(H-14)+'" class="bp-xn">A'+fmt10(s.accuracy_mean)+' C'+fmt10(s.completeness_mean)+' R'+fmt10(s.relevance_mean)+'</text>';
  }
  g+='</svg>';
  var wrap=el('div','boxplot-wrap'); wrap.innerHTML=g; return wrap;
}
function judgeHeatmap(run){
  var jr=run.judge_rows||[]; if(!jr.length) return null;
  var idx={}; for(var i=0;i<jr.length;i++){ idx[jr[i].scenario_id+'|'+jr[i].backend_id]=jr[i]; }
  var arms=run.backends||[];
  var h='<h3 class="jh-title">per-scenario evaluation — accuracy/completeness/relevance (click a cell for the note)</h3>';
  h+='<table class="jheat"><thead><tr><th>scenario</th>';
  for(var a=0;a<arms.length;a++){ h+='<th>'+htmlEsc(bpShort(arms[a]))+'</th>'; }
  h+='</tr></thead><tbody>';
  var scen=(run.scenarios||[]).map(function(s){return s.scenario_id;});
  for(var sI=0;sI<scen.length;sI++){
    var sid=scen[sI];
    h+='<tr><th class="jh-scen">'+htmlEsc(sid)+'</th>';
    for(var aI=0;aI<arms.length;aI++){
      var r=idx[sid+'|'+arms[aI]];
      if(!r){ h+='<td class="jh-na">·</td>'; continue; }
      var acc=(r.accuracy==null?0:r.accuracy);
      var cls=acc>=7.5?'jh-good':(acc>=5?'jh-mid':'jh-bad');
      var flag=(r.abstention_outcome==='failed-to-abstain'?' ⚑':'')+(r.citation_groundedness==='unsupported'?' ✗':'')+(r.harm?' ☠':'');
      var det='accuracy '+r.accuracy+' · completeness '+r.completeness+' · relevance '+r.relevance+' · abstention '+r.abstention_outcome+' · citations '+r.citation_groundedness+(r.harm?' · HARM':'');
      h+='<td class="jh '+cls+'" title="'+htmlEsc(det+(r.note?' — '+r.note:''))+'" data-det="'+htmlEsc(det)+'" data-note="'+htmlEsc(r.note||'')+'" data-sid="'+htmlEsc(sid)+'" data-arm="'+htmlEsc(arms[aI])+'">'+fmt10(r.accuracy)+'/'+fmt10(r.completeness)+'/'+fmt10(r.relevance)+flag+'</td>';
    }
    h+='</tr>';
  }
  h+='</tbody></table><div class="jh-note" id="jh-note">click any cell to read the reviewer’s note. ⚑ = failed to abstain · ✗ = unsupported citation · ☠ = harm</div>';
  var wrap=el('div','judge-heatmap-wrap'); wrap.innerHTML=h;
  var cells=wrap.querySelectorAll('td.jh');
  for(var c=0;c<cells.length;c++){
    cells[c].onclick=(function(td){ return function(){
      wrap.querySelector('#jh-note').innerHTML='<b>'+htmlEsc(td.dataset.sid)+' · '+htmlEsc(bpShort(td.dataset.arm))+'</b><br>'+htmlEsc(td.dataset.det)+'<br>'+htmlEsc(td.dataset.note||'(no note)');
    }; })(cells[c]);
  }
  return wrap;
}
function renderJudge(run){
  var sec=el('section','judge-section'), j=run.judge||[], has=false;
  for(var i=0;i<j.length;i++){ if(j[i].n>0){ has=true; break; } }
  if(!has){ return sec; }
  sec.innerHTML='<h2>quality — reviewer judgment (Scout rubric)</h2>'
   +'<p class="metrics-legend">Each answer scored against the patient’s chart by a strong LLM reviewer (advisory). <b>accuracy</b> = stated facts correct · <b>completeness</b> = includes the needed info · <b>relevance</b> = on-question, no padding (each 0–10). <b>abstain ✓/✗</b> = correctly said "not documented" vs failed-to-abstain. <b>grounding s/p/u</b> = supported / partly / unsupported. <b>fab refs</b> = references that don’t resolve to a real chart record (deterministic). <b>temporal</b> — date ✗ = wrong date↔value or fabricated date · win-over = window claimed beyond the data span · trend-fab = trend asserted from too few points / wrong direction. <b>Drill down:</b> the heatmap is every scenario × arm (green=accurate, amber, red) — click a cell for the note. Caveat: small N, one patient, single judge — directional, not a benchmark.</p>';
  var fab={}, jr=run.judge_rows||[];
  for(var x=0;x<jr.length;x++){ var cr=jr[x].citation_resolution||{}; fab[jr[x].backend_id]=(fab[jr[x].backend_id]||0)+(cr.n_unresolved||0); }
  var rows=j.map(function(s){ var ab=s.abstention||{}, gr=s.groundedness||{}, t=s.temporal||{};
    return "<tr><td class='b'>"+htmlEsc(bpShort(s.backend))+"</td><td>"+s.n+"</td>"
      +"<td>"+fmt10(s.accuracy_mean)+"</td><td>"+fmt10(s.completeness_mean)+"</td><td>"+fmt10(s.relevance_mean)+"</td>"
      +"<td>"+(ab['correct']||0)+" / "+(ab['failed-to-abstain']||0)+"</td>"
      +"<td>"+(gr['supported']||0)+" / "+(gr['partly']||0)+" / "+(gr['unsupported']||0)+"</td>"
      +"<td>"+(s.harm_count||0)+"</td><td>"+(fab[s.backend]||0)+"</td>"
      +"<td>"+(t.date_wrong||0)+"</td><td>"+(t.window_over||0)+"</td><td>"+(t.trend_fab||0)+"</td></tr>"; }).join('');
  var tbl=el('table','summary');
  tbl.innerHTML='<thead><tr><th>backend</th><th>judged</th><th>acc</th><th>comp</th><th>rel</th><th>abstain ✓/✗</th><th>grounding s/p/u</th><th>harm</th><th>fab refs</th><th>date ✗</th><th>win over</th><th>trend fab</th></tr></thead><tbody>'+rows+'</tbody>';
  sec.appendChild(tbl);
  sec.appendChild(judgeBarsSVG(j));
  var hm=judgeHeatmap(run); if(hm) sec.appendChild(hm);
  return sec;
}

function buildTile(run, backend, cell, turn, scenarioId){
  const tile = el('article', 'tile');
  tile.draggable = true;
  tile.dataset.backend = backend;
  tile.dataset.run = run.run_id;
  tile.dataset.scenario = scenarioId;
  tile.dataset.turn = turn;

  const head = el('div', 'tile-head');
  head.innerHTML = "<span class='rank-badge'></span><span class='backend'></span><span class='label'></span>";
  head.querySelector('.backend').textContent = backend;
  head.querySelector('.label').textContent = run.labels[backend] || '';
  tile.appendChild(head);

  if (!cell){
    tile.classList.add('empty');
    tile.draggable = false;
    const dash = el('div'); dash.textContent = '—'; tile.appendChild(dash);
    return tile;
  }

  const body = el('div');
  if (cell.error){
    body.innerHTML = "<div class='err'></div>";
    body.querySelector('.err').textContent = 'HTTP ' + (cell.http_status == null ? '' : cell.http_status) +
                                             ': ' + String(cell.error).slice(0, 400);
  } else {
    body.innerHTML = "<div class='ans'>" + cell.answer_html + '</div>' + cell.refs_html + cell.blocks_html;
  }
  tile.appendChild(body);

  const fsBtn = el('button', 'fs-btn');
  fsBtn.textContent = '⛶';
  fsBtn.title = 'view full screen';
  fsBtn.addEventListener('click', (e) => { e.stopPropagation(); openFullscreen(tile); });
  tile.appendChild(fsBtn);

  const expand = el('button', 'expand');
  expand.textContent = 'expand';
  expand.addEventListener('click', () => {
    tile.classList.toggle('expanded');
    expand.textContent = tile.classList.contains('expanded') ? 'collapse' : 'expand';
  });
  tile.appendChild(expand);

  const chips = el('div', 'chips');
  chips.innerHTML = cell.chips_html;
  tile.appendChild(chips);

  const tmpl = document.getElementById('rubric-template');
  tile.appendChild(tmpl.content.cloneNode(true));
  // Unique radio group per tile — otherwise every tile shares name='decision', so a
  // pass/fail pick in one tile deselects the others (one global group).
  tile.querySelectorAll("input[name='decision']").forEach(r => { r.name = 'decision-' + backend + '-' + turn; });
  wireTile(tile);
  return tile;
}

function renderRun(runId){
  const run = runById(runId);
  if (!run) return;
  document.getElementById('run-meta').textContent = renderRunMeta(run);

  // scenario filter options
  const sf = document.getElementById('scenario-filter');
  sf.innerHTML = "<option value=''>all scenarios</option>" +
    run.scenarios.map(s => "<option></option>").join('');
  run.scenarios.forEach((s, i) => { const o = sf.options[i + 1]; o.value = s.scenario_id; o.textContent = s.scenario_id; });

  // backend toggle checkboxes (all on)
  const tg = document.getElementById('backend-toggles');
  tg.innerHTML = '<legend>backends</legend>';
  run.backends.forEach(b => {
    const lab = el('label');
    const cb = el('input'); cb.type = 'checkbox'; cb.checked = true; cb.value = b;
    cb.addEventListener('change', () => applyBackendToggle(b, cb.checked));
    lab.appendChild(cb); lab.appendChild(document.createTextNode(b));
    tg.appendChild(lab);
  });

  const main = document.getElementById('report');
  main.innerHTML = '';
  const pbanner = renderPatientBanner(run);
  if (pbanner) main.appendChild(pbanner);
  main.appendChild(renderSummary(run));
  main.appendChild(renderMetrics(run));
  main.appendChild(renderJudge(run));

  run.scenarios.forEach(sc => {
    const sec = el('section', 'scenario');
    sec.dataset.scenario = sc.scenario_id;
    const h = el('h2'); h.textContent = sc.scenario_id; sec.appendChild(h);

    sc.turns.forEach(tn => {
      const band = el('div', 'qband');
      band.dataset.run = run.run_id; band.dataset.scenario = sc.scenario_id; band.dataset.turn = tn.turn;

      const qhead = el('div', 'qhead');
      qhead.innerHTML = "<span class='n'></span><div class='q'></div>";
      qhead.querySelector('.n').textContent = 'T' + tn.turn;
      qhead.querySelector('.q').textContent = tn.question || '';
      band.appendChild(qhead);

      const tilesEl = el('div', 'tiles');
      const group = run.run_id + '|' + sc.scenario_id + '|' + tn.turn;
      tilesEl.dataset.rankgroup = group;

      const saved = savedRankFor(group);
      const ordered = saved
        ? saved.filter(b => run.backends.includes(b)).concat(run.backends.filter(b => !saved.includes(b)))
        : run.backends.slice();
      ordered.forEach(b => tilesEl.appendChild(buildTile(run, b, tn.cells[b], tn.turn, sc.scenario_id)));

      wireGroup(tilesEl);
      renumber(tilesEl);
      const wrap = el('div', 'tiles-wrap');
      const aL = el('button', 'scroll-arrow left'); aL.textContent = '◀'; aL.setAttribute('aria-label', 'scroll left');
      const aR = el('button', 'scroll-arrow right'); aR.textContent = '▶'; aR.setAttribute('aria-label', 'scroll right');
      wrap.appendChild(aL); wrap.appendChild(tilesEl); wrap.appendChild(aR);
      wireScroll(tilesEl, aL, aR);
      band.appendChild(wrap);
      sec.appendChild(band);
    });
    main.appendChild(sec);
  });

  applyFilters();
}

/* ---- filter + toggle (attribute flips, no re-render) ---- */
function applyScenarioFilter(){
  const v = document.getElementById('scenario-filter').value;
  document.querySelectorAll('#report .scenario').forEach(sec => {
    sec.dataset.hidden = (v && sec.dataset.scenario !== v) ? '1' : '0';
  });
}
function applyQuestionSearch(){
  const raw = document.getElementById('q-search').value.trim();
  let re = null;
  if (raw){ try { re = new RegExp(raw, 'i'); } catch(e) { re = null; } }
  document.querySelectorAll('#report .qband').forEach(band => {
    if (!raw){ band.dataset.hidden = '0'; return; }
    const q = band.querySelector('.qhead .q').textContent || '';
    const tiles = [...band.querySelectorAll('.tile')].map(t => t.textContent).join(' ');
    const hay = q + ' ' + tiles;
    const hit = re ? re.test(hay) : hay.toLowerCase().includes(raw.toLowerCase());
    band.dataset.hidden = hit ? '0' : '1';
  });
}
function applyBackendToggle(backend, on){
  document.querySelectorAll("#report .tile[data-backend='" + cssEsc(backend) + "']").forEach(t => {
    t.dataset.hidden = on ? '0' : '1';
  });
}
function cssEsc(s){ return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/'/g, "\\'"); }
function htmlEsc(s){ const d = document.createElement('div'); d.textContent = (s == null ? '' : String(s)); return d.innerHTML; }
function applyFilters(){
  applyScenarioFilter();
  applyQuestionSearch();
  document.querySelectorAll('#backend-toggles input[type=checkbox]').forEach(cb => applyBackendToggle(cb.value, cb.checked));
}

/* ---- drag-rank (native DnD, constrained within one band) ---- */
let dragged = null;
function wireTile(tile){
  tile.addEventListener('dragstart', () => { dragged = tile; requestAnimationFrame(() => tile.classList.add('dragging')); });
  tile.addEventListener('dragend', () => {
    tile.classList.remove('dragging'); const g = tile.closest('.tiles'); dragged = null;
    if (g){ renumber(g); saveRanking(g); }
  });
}
function wireGroup(tilesEl){
  tilesEl.addEventListener('dragover', e => {
    e.preventDefault();
    if (!dragged || dragged.closest('.tiles') !== tilesEl) return;
    const after = getDragAfterElementX(tilesEl, e.clientX);
    if (after == null) tilesEl.appendChild(dragged); else tilesEl.insertBefore(dragged, after);
  });
}
function getDragAfterElementX(container, x){
  const tiles = [...container.querySelectorAll('.tile:not(.dragging)')];
  return tiles.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = x - box.left - box.width / 2;
    return (offset < 0 && offset > closest.offset) ? { offset, element: child } : closest;
  }, { offset: -Infinity, element: null }).element;
}
function renumber(tilesEl){
  [...tilesEl.querySelectorAll('.tile')].forEach((t, i) => {
    const b = t.querySelector('.rank-badge'); if (b) b.textContent = (i + 1);
  });
}

/* ---- patient grounding banner (links to the live OpenMRS chart) ---- */
function renderPatientBanner(run){
  const pts = run.patients || [];
  if (!pts.length) return null;
  const card = el('div', 'patient-banner');
  pts.forEach(pt => {
    const blk = el('div', 'pt-block');
    const head = el('div', 'pt-head');
    head.appendChild(document.createTextNode('Patient — '));
    const id = el('span', 'pt-id');
    id.textContent = pt.identifier ? ('OpenMRS ID ' + pt.identifier) : ('UUID ' + (pt.uuid || '').slice(0, 8));
    head.appendChild(id);
    if (pt.display){ const nm = el('span', 'pt-name'); nm.textContent = ' ' + pt.display; head.appendChild(nm); }
    const demo = [pt.gender, (pt.age != null ? pt.age + 'y' : ''), (pt.birthdate ? 'b.' + pt.birthdate : '')].filter(Boolean).join(', ');
    if (demo){ const d = el('span', 'pt-demo'); d.textContent = ' (' + demo + ')'; head.appendChild(d); }
    if (pt.chart_url){ const a = el('a'); a.href = pt.chart_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'open chart ↗'; head.appendChild(a); }
    blk.appendChild(head);

    if (pt.medications && pt.medications.length){
      const ln = el('div', 'pt-line');
      const lab = el('span', 'pt-lab'); lab.textContent = 'Active regimen: '; ln.appendChild(lab);
      ln.appendChild(document.createTextNode(pt.medications.join('  ·  ')));
      blk.appendChild(ln);
    }
    if (pt.vitals && Object.keys(pt.vitals).length){
      const ln = el('div', 'pt-line');
      const lab = el('span', 'pt-lab'); lab.textContent = 'Recent vitals: '; ln.appendChild(lab);
      ln.appendChild(document.createTextNode(Object.keys(pt.vitals).map(k => k + ' ' + pt.vitals[k]).join('  ·  ')));
      blk.appendChild(ln);
    }
    const counts = [];
    if (pt.encounter_count != null) counts.push(pt.encounter_count + ' encounters');
    if (pt.observation_count != null) counts.push(pt.observation_count + ' observations');
    if (counts.length){
      const ln = el('div', 'pt-line pt-counts');
      ln.textContent = 'Chart: ' + counts.join('  ·  ');
      blk.appendChild(ln);
    }
    card.appendChild(blk);
  });
  return card;
}

/* ---- horizontal scroll affordance: greyed ◀▶ arrows show when tiles run off-screen ---- */
function wireScroll(tilesEl, aL, aR){
  function update(){
    const max = tilesEl.scrollWidth - tilesEl.clientWidth;
    aL.classList.toggle('disabled', tilesEl.scrollLeft <= 1);
    aR.classList.toggle('disabled', max <= 1 || tilesEl.scrollLeft >= max - 1);
  }
  aL.addEventListener('click', () => tilesEl.scrollBy({ left: -tilesEl.clientWidth * 0.85, behavior: 'smooth' }));
  aR.addEventListener('click', () => tilesEl.scrollBy({ left: tilesEl.clientWidth * 0.85, behavior: 'smooth' }));
  tilesEl.addEventListener('scroll', update);
  window.addEventListener('resize', update);
  update();
  requestAnimationFrame(update);
}

/* ---- per-tile fullscreen: read one backend's answer full-screen ---- */
function openFullscreen(tile){
  let ov = document.querySelector('.fs-overlay');
  if (!ov){
    ov = el('div', 'fs-overlay');
    ov.innerHTML = "<div class='fs-modal'><button class='fs-close'>✕ close</button><div class='fs-body'></div></div>";
    ov.addEventListener('click', e => { if (e.target === ov) closeFullscreen(); });
    ov.querySelector('.fs-close').addEventListener('click', closeFullscreen);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeFullscreen(); });
    document.body.appendChild(ov);
  }
  const body = ov.querySelector('.fs-body');
  body.innerHTML = '';
  const clone = tile.cloneNode(true);
  clone.classList.add('expanded');
  clone.querySelectorAll('.fs-btn, .adj, .expand, .rank-badge').forEach(x => x.remove());
  body.appendChild(clone);
  ov.classList.add('open');
}
function closeFullscreen(){ const ov = document.querySelector('.fs-overlay'); if (ov) ov.classList.remove('open'); }

/* ---- exports: two files, two grains ---- */
function n(v){ v = (v || '').trim(); return v === '' ? null : Number(v); }
function collectFeedback(){
  const out = [];
  const reviewer = document.getElementById('rev').value || 'unknown';
  document.querySelectorAll("#report .tile:not(.empty)").forEach(tile => {
    const f = tile.querySelector('.cell-form'); if (!f) return;
    const g = s => f.querySelector(s);
    const acc = g('[name=accuracy]').value, comp = g('[name=completeness]').value, rel = g('[name=relevance]').value;
    const abst = g('[name=abstention_outcome]').value, grnd = g('[name=citation_groundedness]').value;
    const harm = g('[name=harm_fail]').checked;
    const dec = f.querySelector('input[name^="decision"]:checked');
    const txt = g('[name=free_text]').value.trim();
    const touched = acc || comp || rel || txt || harm || dec || abst !== 'n-a' || grnd !== 'n-a';
    if (!touched) return;
    out.push(JSON.stringify({
      run_id: activeRunId, scenario_id: tile.dataset.scenario, turn: Number(tile.dataset.turn),
      backend_id: tile.dataset.backend, reviewer: reviewer,
      scores: { accuracy: n(acc), completeness: n(comp), relevance: n(rel) },
      abstention_outcome: abst, citation_groundedness: grnd, harm_fail: harm,
      decision: dec ? dec.value : null, free_text: txt, created_at: new Date().toISOString()
    }));
  });
  if (!out.length){ alert('No adjudications filled in yet.'); return; }
  submit(out.join('\n') + '\n', 'feedback.jsonl', 'application/x-ndjson');
}
function exportRankings(){
  const payload = {
    run_set: DATA.runs.map(r => r.run_id),
    exported_at: new Date().toISOString(),
    rankings: loadAllRanks()
  };
  submit(JSON.stringify(payload, null, 2), 'rankings.json', 'application/json');
}
function resetRanking(){
  const all = loadAllRanks();
  Object.keys(all).forEach(k => { if (k.startsWith(activeRunId + '|')) delete all[k]; });
  saveAllRanks(all);
  renderRun(activeRunId);
}
function download(text, name, mime){
  const b = new Blob([text], { type: mime });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
}
function submit(text, name, mime){
  // Feedback-capture seam: POST to the configured endpoint if set, else fall back to the download.
  if (!FEEDBACK_ENDPOINT){ download(text, name, mime); return; }
  fetch(FEEDBACK_ENDPOINT, { method: 'POST', headers: { 'Content-Type': mime, 'X-Report-Artifact': name }, body: text })
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); alert(name + ' submitted'); })
    .catch(e => { alert('submit failed (' + e + ') — downloading instead'); download(text, name, mime); });
}

/* ---- boot ---- */
function boot(){
  const rs = document.getElementById('run-select');
  rs.innerHTML = DATA.runs.map(() => '<option></option>').join('');
  DATA.runs.forEach((r, i) => { const o = rs.options[i]; o.value = r.run_id; o.textContent = r.run_id; });
  rs.value = activeRunId;
  rs.addEventListener('change', () => { activeRunId = rs.value; renderRun(activeRunId); });

  document.getElementById('scenario-filter').addEventListener('change', applyScenarioFilter);
  const search = document.getElementById('q-search');
  search.addEventListener('input', applyQuestionSearch);
  search.addEventListener('keydown', e => { if (e.key === 'Escape'){ search.value = ''; applyQuestionSearch(); } });
  document.getElementById('reset-rank').addEventListener('click', resetRanking);
  document.getElementById('export-rankings').addEventListener('click', exportRankings);
  document.getElementById('export-feedback').addEventListener('click', collectFeedback);
  document.getElementById('print-pdf').addEventListener('click', () => window.print());

  if (activeRunId) renderRun(activeRunId);
}
boot();
"""


def _embed_json(blob: dict[str, Any]) -> str:
    """Serialise the blob and neutralise the three chars that could break out of
    the <script type="application/json"> element (a model answer containing
    </script> must not escape). \\uXXXX escapes are JSON-valid, so JSON.parse
    reverses them transparently."""
    s = json.dumps(blob, ensure_ascii=False)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _document(blob: dict[str, Any]) -> str:
    legend = (
        "<div class='legend'>⏱ latency (orange = first turn per backend, carries model warmup). "
        "chart refs = count of chart records cited — a COUNT, not a grounding/quality signal; "
        "the authoritative call is the human adjudication on each tile. tokens / finish_reasons / "
        "response model are not surfaced by /chat (OTel-deferred). Deterministic metrics only — no LLM judge. "
        "Drag tiles within a question to rank backends; rank + adjudication export to separate files.</div>"
    )
    title = blob["runs"][0]["run_id"] if blob.get("runs") else ""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>validation report · {_esc(title)}</title><style>{_STYLE}</style></head>"
        "<body>"
        "<header class='topbar'><h1>Validation report</h1>"
        "<div class='controls'>"
        "<label>run <select id='run-select'></select></label>"
        "<div id='run-meta' class='meta'></div>"
        "<label>scenario <select id='scenario-filter'></select></label>"
        "<input id='q-search' type='search' placeholder='filter questions… (Esc clears)'>"
        "<fieldset id='backend-toggles' class='toggles'></fieldset>"
        "<span class='spacer'></span>"
        "<button id='reset-rank' title='restore default backend order'>reset ranking</button>"
        "<button id='export-rankings'>Export rankings.json</button>"
        "<input id='rev' placeholder='you@example.org'>"
        "<button id='export-feedback'>Download feedback.jsonl</button>"
        "<button id='print-pdf' title='print / save as PDF'>Download PDF</button>"
        "</div></header>"
        "<main id='report'></main>"
        f"<template id='rubric-template'>{_RUBRIC_FORM}</template>"
        f"{legend}"
        f"<script type='application/json' id='report-data'>{_embed_json(blob)}</script>"
        f"<script>{_SCRIPT}</script>"
        "</body></html>"
    )


def _assemble(run_dirs: list[Path]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": [_run_blob(Path(d)) for d in run_dirs],
    }


def build_report(run_dir: Path | str) -> Path:
    """Single-run report (N=1 case). Reads run_manifest.json + results.jsonl +
    events.jsonl from run_dir; writes run_dir/report.html. Unchanged signature."""
    run_dir = Path(run_dir)
    blob = _assemble([run_dir])
    out = run_dir / "report.html"
    out.write_text(_document(blob), encoding="utf-8")
    return out


def build_multi_report(run_dirs: list[Path | str], out_path: Path | str) -> Path:
    """Aggregate report embedding N runs (run selector picks the active one).
    Each run dir is read with the same three files; missing run_manifest.json
    raises (contract), missing results/events tolerated."""
    blob = _assemble([Path(d) for d in run_dirs])
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_document(blob), encoding="utf-8")
    return out
