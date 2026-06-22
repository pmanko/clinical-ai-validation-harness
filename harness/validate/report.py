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

from .hub_trace import load_traces, match_trace
from .model_registry import arm_card
from .reconcile import calibrated_summary, scout_summary

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
    """Render the chart-answer envelope's markdown body to HTML, escaping the untrusted model text
    FIRST so it can never inject markup, then upgrading the structural forms the synthesis emits:
    `**Answer**` / `**In Depth**` bold headers (-> <strong>) and `##` ATX headings (-> <h3>). The
    body is CLEAN of confidence text now — confidence renders separately as a chip heading each
    section (see _render_answer_sections / _conf_chip).
    Newlines (incl. a literal backslash-n a 4B may copy from the prompt) stay as line breaks under
    the .ans { pre-wrap } style, so the In-Depth `- …` claim bullets render as a readable list."""
    s = html.escape("" if text is None else str(text))
    s = s.replace("\\n", "\n")
    s = re.sub(r"^##\s+(.+?)\s*$", r"<h3>\1</h3>", s, flags=re.MULTILINE)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


_IN_DEPTH_RE = re.compile(r"\*\*In ?Depth\*\*", re.IGNORECASE)
_CONF = {"green": ("High confidence", "#196c2e"), "yellow": ("Medium confidence", "#9e6a03"),
         "red": ("Low confidence", "#8b1a1a")}


def _conf_chip(level: str) -> str:
    label, color = _CONF.get(level, ("Unrated", "#30363d"))
    return f"<span class='cchip' style='background:{color}'>{label}</span>"


def _render_section(label: str, body: str, conf: Any) -> str:
    """One answer section with the validate dashboard's confidence inversion (confSection):
    red -> show the validator note as a caveat + COLLAPSE the message behind "show <section>";
    yellow -> show the message + collapse the note behind "show review note"; green -> message."""
    if not body.strip():
        return ""
    level = (conf.get("level") if isinstance(conf, dict) else None) or "green"
    note = (conf.get("note") if isinstance(conf, dict) else "") or ""
    rendered = _render_answer(body)
    h = f"<div class='csec'><div class='ctitle'>{_esc(label)} {_conf_chip(level)}</div>"
    if level == "red":
        if note:
            h += f"<div class='caveat red'>{_esc(note)}</div>"
        h += (f"<details class='collapse'><summary>show {_esc(label.lower())}</summary>"
              f"<div class='secbody'>{rendered}</div></details>")
    elif level == "yellow":
        h += f"<div class='secbody'>{rendered}</div>"
        if note:
            h += (f"<details class='collapse'><summary>show review note</summary>"
                  f"<div class='caveat yellow'>{_esc(note)}</div></details>")
    else:
        h += f"<div class='secbody'>{rendered}</div>"
    return h + "</div>"


def _render_answer_sections(text: Any, trace: Any) -> str:
    """Render the answer split into its Answer / In-Depth sections, each headed by its validator
    confidence tag, with LOW sections withheld behind a reveal (parity with the OpenMRS chat).
    Falls back to a single plain answer when there's no per-section confidence (direct single-LLM
    arms / older runs carry no hub trace)."""
    answer = "" if text is None else str(text)
    a_conf = trace.get("answer_confidence") if isinstance(trace, dict) else None
    d_conf = trace.get("indepth_confidence") if isinstance(trace, dict) else None
    has_conf = (isinstance(a_conf, dict) and a_conf.get("level")) or (
        isinstance(d_conf, dict) and d_conf.get("level"))
    if not has_conf:
        return _render_answer(answer)
    m = _IN_DEPTH_RE.search(answer)
    strip_hdr = lambda s: re.sub(r"^\s*\*\*Answer\*\*\s*", "", s, flags=re.IGNORECASE).strip()  # noqa: E731
    if m:
        answer_body, indepth_body = strip_hdr(answer[: m.start()]), answer[m.end():].strip()
    else:
        answer_body, indepth_body = strip_hdr(answer), ""
    out = _render_section("Answer", answer_body, a_conf)
    if indepth_body:
        out += _render_section("In-Depth", indepth_body, d_conf)
    return out


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


def _load_adjudication(run_dir: Path) -> list[dict[str, Any]]:
    """Optional HUMAN adjudications at run_dir/adjudication.jsonl (adjudicate.adjudication_record
    shape: scenario_id/backend_id/reviewer_tier/axes/harm). These calibrate the LLM judge into a
    clinician-anchored Benchmark with a CI. Absent file -> [] (the default report path stays
    judge-only and renders exactly as before)."""
    path = run_dir / "adjudication.jsonl"
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


def _cell_blob(r: dict[str, Any], traces: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """One rendered cell for the blob. Answer/block HTML is rendered in Python
    (escape-FIRST) so the injection contract is enforced and testable; the JS
    just injects the strings. Carries only the surfaced metric subset + the
    precomputed degraded flag, plus the per-section confidence tags from the hub trace."""
    m = r.get("metrics") or {}
    resp = r.get("response") or {}
    trace = match_trace(traces or [], r.get("backend_id"), r.get("started_at"), r.get("ended_at"))
    return {
        "error": r.get("error"),
        "http_status": m.get("http_status"),
        "conf_html": "",  # tags now head each answer section (see _render_answer_sections)
        "answer_html": _render_answer_sections(resp.get("answer"), trace),
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


def _arm_cards_for(run_dir: Path, backends: list[str]) -> dict[str, Any]:
    """Resolve the per-arm cards for the blob, preferring the run's FROZEN provenance.

    WS1: when `<run_dir>/run_meta.json` exists and carries `arm_cards`, use those — they were
    captured at run time, so the report reflects the config the run ACTUALLY used (knobs /
    prompts / retrieval), not whatever the static config files say now. A backend absent from
    the frozen set still resolves live (best-effort). When run_meta.json is absent (every
    existing run) this falls back to live `arm_card(b)` resolution byte-for-byte as before."""
    frozen: dict[str, Any] = {}
    meta_path = run_dir / "run_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(meta, dict) and isinstance(meta.get("arm_cards"), dict):
                frozen = meta["arm_cards"]
        except Exception:
            frozen = {}
    return {b: (frozen[b] if b in frozen else arm_card(b)) for b in backends}


def _run_blob(run_dir: Path) -> dict[str, Any]:
    """Assemble one run into the blob shape. Reads the same three files as before;
    a missing run_manifest.json still raises (contract), results/events tolerated."""
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    results = _read_jsonl(run_dir / "results.jsonl")
    events = _read_jsonl(run_dir / "events.jsonl")
    labels = _backend_labels(events)
    # Per-turn confidence/trace lives in the hub artifact (chartsearchai drops the envelope field);
    # correlate by level_id + the cell's started_at..ended_at window. artifacts/hub-trace is a sibling
    # of artifacts/validate/<run>, i.e. run_dir.parent.parent / hub-trace.
    traces = load_traces(run_dir.parent.parent / "hub-trace" / "trace.jsonl")

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
                    cells[b] = _cell_blob(r, traces)
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

    # Reference date = the resolved temporal anchor the hub ran under (the "now" for
    # recency/most-recent/series), written into each trace by team._write_trace. Scope to
    # THIS run's cells via the per-cell time-window match (trace.jsonl is append-only across
    # runs, so a whole-file scan would pick up stale anchors). A run is one time reality, so
    # collapse to one value; direct (non-hub) backends carry no trace -> excluded.
    _ref_dates = _ordered_unique([
        (match_trace(traces, r.get("backend_id"), r.get("started_at"), r.get("ended_at")) or {}).get("reference_date")
        for r in results
    ])
    _ref_dates = [d for d in _ref_dates if d]
    reference_date = (_ref_dates[0] if len(_ref_dates) == 1
                      else (", ".join(_ref_dates) if _ref_dates else None))

    return {
        "run_id": run_id,
        "meta": {
            "run_id": run_id,
            "component": manifest.get("component"),
            "git_sha": (manifest.get("git_sha") or "")[:10],
            "dataset_id": manifest.get("dataset_id"),
            "provider": otel.get("gen_ai.provider.name", "?"),
            "generated_at": manifest.get("generated_at", ""),
            "reference_date": reference_date,
        },
        "backends": backends,
        "labels": {b: labels.get(b, "") for b in backends},
        "scenarios": scenarios,
        "summary": _summary_rows(results, backends, labels),
        "metrics": _metric_distributions(results, backends),
        "judge": scout_summary(_load_judge(run_dir), backends),
        "judge_rows": _load_judge(run_dir),
        # WS4: adjudication-calibrated Benchmark. adjudication.jsonl is OPTIONAL — when
        # absent (the default) every calibrated block is judge-only (no CI / no κ) and the
        # judged-scores section renders exactly as before. When present, each reviewed arm
        # gains a PPI point ± 95% CI + agreement κ + the reviewer-tier badge.
        "calibrated": calibrated_summary(
            _load_judge(run_dir), _load_adjudication(run_dir), backends),
        "patients": patients,
        # WS2: structured arm makeup (single vanilla-chartsearchai vs med-agent-hub team +
        # role->model lineup) so the report's "what this run compares" section + badges render
        # from one resolver instead of parsing the label string. Best-effort: never blocks a render.
        # WS1: prefer the run's FROZEN cards (run_meta.json) over re-resolving the current static
        # files, so an old run renders the config it ACTUALLY used (see _arm_cards_for).
        "arm_cards": _arm_cards_for(run_dir, backends),
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
html[data-theme="light"] { color-scheme:light; --fg:#1a1a1a; --mut:#666; --line:#e2e2e2; --bg:#fafafa; --surface:#fff; --surface2:#f3f3f3; --accent:#2748a0; --accent-bg:#eef3ff; --accent-bd:#c7d6f5; --accent-hover:#dce6fb; --banner-bg:#f0f6ff; --note-bg:#f6f8fa; --arrow-bg:rgba(255,255,255,.9); --bp-fill:rgba(39,72,160,.14); --bp-grid:#eef0f3; --err:#a01; }
html[data-theme="dark"] { color-scheme:dark; --fg:#c9d1d9; --mut:#8b949e; --line:#30363d; --bg:#0d1117; --surface:#161b22; --surface2:#1c2230; --accent:#79c0ff; --accent-bg:rgba(56,139,253,.13); --accent-bd:#30466b; --accent-hover:rgba(56,139,253,.22); --banner-bg:#11233f; --note-bg:#1c2230; --arrow-bg:rgba(22,27,34,.9); --bp-fill:rgba(121,192,255,.18); --bp-grid:#21262d; --err:#f85149; }
* { box-sizing: border-box; }
body { font: 14px/1.5 -apple-system, system-ui, sans-serif; color: var(--fg); margin: 0; background: var(--bg); }
.topbar { position: sticky; top: 0; z-index: 30; background: var(--surface); border-bottom: 1px solid var(--line); padding: 12px 24px; }
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
.intro { color: var(--mut); font-size: 13px; margin: 4px 0 14px; max-width: 72ch; }
section.intro-led > .intro:first-child { margin-top: 0; }
.arms-section { margin: 8px 24px 0; }
.arm-cards { display: flex; flex-wrap: wrap; gap: 10px; }
.arm-card { flex: 1 1 240px; min-width: 220px; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; background: var(--surface); }
.arm-head { display: flex; align-items: center; gap: 8px; }
.arm-name { font-size: 13px; font-weight: 600; }
.arm-id { font-family: ui-monospace, monospace; font-size: 10px; color: var(--mut); margin: 2px 0 0; }
.badge { font-size: 10px; font-weight: 700; letter-spacing: .04em; padding: 2px 6px; border-radius: 4px; border: 1px solid var(--accent-bd); background: var(--accent-bg); color: var(--accent); }
.badge.single { background: var(--surface2); color: var(--mut); border-color: var(--line); }
.arm-path { color: var(--mut); font-size: 11px; margin: 3px 0 6px; }
.makeup { width: 100%; font-size: 11px; background: transparent; }
.makeup td { padding: 2px 4px; border: none; }
.makeup .role { color: var(--mut); width: 28%; }
.makeup .mdl { font-family: ui-monospace, monospace; }
.makeup .mq { color: var(--mut); }
.makeup-single { font-size: 12px; color: var(--mut); font-family: ui-monospace, monospace; margin-top: 4px; }
details.arm-config { margin-top: 8px; border-top: 1px dashed var(--line); padding-top: 6px; }
details.arm-config > summary { cursor: pointer; color: var(--accent); font-size: 11px; font-weight: 600; }
.arm-config .ac-tease { color: var(--mut); font-weight: 400; font-size: 10px; font-family: ui-monospace, monospace; }
.arm-config .ac-body { margin-top: 8px; }
.arm-config .ac-h { font-size: 11px; font-weight: 700; color: var(--fg); text-transform: uppercase; letter-spacing: .03em; margin: 10px 0 4px; }
.arm-config .ac-h:first-child { margin-top: 0; }
.arm-config .ac-sub, .arm-config .ac-src { font-weight: 400; text-transform: none; color: var(--mut); font-size: 10px; font-family: ui-monospace, monospace; letter-spacing: 0; }
table.ac-knobs { width: 100%; font-size: 11px; border-collapse: collapse; }
table.ac-knobs th, table.ac-knobs td { border: 1px solid var(--line); padding: 2px 6px; text-align: left; font-family: ui-monospace, monospace; }
table.ac-knobs th { background: var(--surface2); font-weight: 600; }
table.ac-knobs td.ac-k, table.ac-knobs th:first-child { color: var(--mut); font-family: inherit; }
.arm-config .ac-prompt { margin: 4px 0 8px; }
.arm-config .ac-plabel { font-size: 11px; font-weight: 600; }
.arm-config .ac-psum { font-size: 11px; color: var(--mut); margin: 2px 0; max-width: 60ch; }
.arm-config .ac-pfull > summary { cursor: pointer; color: var(--accent); font-size: 10px; }
.arm-config pre.ac-pre { white-space: pre-wrap; font: 10.5px/1.45 ui-monospace, monospace; background: var(--surface2); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; margin: 4px 0 0; max-height: 16em; overflow: auto; }
.arm-config .ac-retr { font-size: 11px; font-family: ui-monospace, monospace; color: var(--fg); }
details.eng { margin: 24px 24px 0; }
details.eng > summary { cursor: pointer; color: var(--mut); font-size: 13px; font-family: ui-monospace, monospace; padding: 6px 0; }
table { border-collapse: collapse; width: 100%; background: var(--surface); }
th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: var(--surface2); font-weight: 600; font-size: 12px; }
.summary td, .summary th { text-align: center; }
.summary td.b { text-align: left; font-family: ui-monospace, monospace; }
.summary .model { display: block; color: var(--mut); font-size: 11px; }
.metrics-section { margin-top: 18px; }
.metrics-legend { color: var(--mut); font-size: 12px; margin: 2px 0 10px; }
.metrics-grid { display: flex; flex-wrap: wrap; gap: 16px; }
.boxplot-wrap { flex: 1 1 300px; min-width: 280px; max-width: 460px; border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px; background: var(--surface); }
.boxplot { width: 100%; height: auto; }
.bp-title { font-size: 12px; font-weight: 600; fill: var(--fg); }
.bp-grid { stroke: var(--bp-grid); stroke-width: 1; }
.bp-ytick { font-size: 9px; fill: var(--mut); text-anchor: end; }
.bp-xtick { font-size: 10px; fill: var(--fg); text-anchor: middle; }
.bp-xn { font-size: 8.5px; fill: var(--mut); text-anchor: middle; }
.bp-box { fill: var(--bp-fill); stroke: var(--accent); stroke-width: 1.3; }
.bp-median { stroke: var(--accent); stroke-width: 2.2; }
.bp-mean { stroke: #d9730d; stroke-width: 1.4; stroke-dasharray: 3 2; }
.bp-whisker, .bp-cap { stroke: var(--accent); stroke-width: 1; }
.bp-out { fill: #d9730d; opacity: .75; }
.judge-section { margin-top: 18px; }
.th-sub { font-weight: 400; color: var(--mut); font-size: 10px; }
.cal { margin-top: 5px; font-size: 11px; line-height: 1.5; display: flex; flex-wrap: wrap; gap: 4px 6px; align-items: baseline; justify-content: center; }
.cal-pt { font-weight: 700; font-variant-numeric: tabular-nums; }
.cal .ci { color: var(--mut); font-variant-numeric: tabular-nums; }
.cal .kap { color: var(--accent); font-family: ui-monospace, monospace; }
.cal .cal-n, .cal-run .cal-n { color: var(--mut); font-size: 10px; }
.tier-badge { font-size: 9px; font-weight: 700; letter-spacing: .03em; padding: 1px 6px; border-radius: 10px; white-space: nowrap; border: 1px solid var(--line); }
.tier-badge.owner { background: var(--surface2); color: var(--mut); }
.tier-badge.domain { background: #fff3d6; color: #8a5a00; border-color: #f1c21b; }
.tier-badge.clinical { background: #d6f0d8; color: #103d1a; border-color: #2f9e44; }
.cal-run { margin: 10px 0 0; padding: 8px 12px; background: var(--note-bg); border: 1px solid var(--line); border-radius: 8px; font-size: 13px; }
.cal-run .ci { color: var(--mut); }
.jb-faith { fill: var(--accent); }
.jb-corr { fill: #d9730d; }
.jb-acc { fill: var(--accent); }
.jb-comp { fill: #2f9e44; }
.jb-rel { fill: #d9730d; }
.jh-title { font-size: 13px; margin: 16px 0 5px; color: var(--mut); }
table.jheat { border-collapse: collapse; font-size: 11px; }
.jheat th, .jheat td { border: 1px solid var(--line); padding: 3px 7px; text-align: center; }
.jheat th.jh-scen { text-align: left; font-weight: 400; font-family: ui-monospace, monospace; white-space: nowrap; }
.jh { cursor: pointer; font-variant-numeric: tabular-nums; }
.jh:hover { outline: 2px solid var(--accent); }
.jh-good { background: #d6f0d8; color: #103d1a; }
.jh-mid { background: #fdedc8; color: #5c4300; }
.jh-bad { background: #f6d2d2; color: #7d1a1a; }
.jh-na { color: #cbd5e1; }
.jh-note { margin-top: 8px; padding: 8px 10px; background: var(--note-bg); border: 1px solid var(--line); border-radius: 6px; font-size: 12px; color: var(--mut); min-height: 18px; }
.qband { display: grid; grid-template-columns: var(--qcol, 240px) 1fr; gap: 12px; align-items: start; border-top: 1px solid var(--line); padding: 12px 0; }
.qhead { position: sticky; left: 0; z-index: 1; background: var(--bg); align-self: start; }
.qhead .n { font-family: ui-monospace, monospace; font-weight: 700; color: var(--mut); }
.qhead .q { margin-top: 2px; }
.tiles { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(340px, 1fr); gap: 12px; align-items: stretch; overflow-x: auto; min-height: 60px; scroll-behavior: smooth; }
.tile { display: flex; flex-direction: column; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); padding: 10px 12px; cursor: grab; user-select: none; }
.tile.dragging { opacity: .4; cursor: grabbing; }
.tile.empty { color: var(--mut); align-items: center; justify-content: center; cursor: default; }
.tile-head { display: flex; gap: 6px; align-items: baseline; margin-bottom: 6px; }
.rank-badge { font: 11px ui-monospace, monospace; background: var(--accent-bg); color: var(--accent); border-radius: 4px; padding: 0 5px; }
.tile-head .backend { font-weight: 700; font-size: 12px; }
.tile-head .label { color: var(--mut); font-size: 11px; font-family: ui-monospace, monospace; }
.expand { font: 600 11px/1.2 ui-monospace, monospace; color: var(--accent); cursor: pointer; background: var(--accent-bg); border: 1px solid var(--accent-bd); border-radius: 6px; padding: 4px 11px; align-self: flex-start; margin-top: 6px; }
.expand:hover { background: var(--accent-hover); }
.ans { white-space: pre-wrap; max-height: 20em; overflow: auto; }
.tile.expanded .ans { max-height: none; }
.ctags { margin: 0 0 6px; display: flex; flex-wrap: wrap; gap: 4px; }
.ctag { display: inline-block; font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 10px; color: #fff; cursor: default; }
.ctag.green { background: #196c2e; }
.ctag.yellow { background: #9e6a03; }
.ctag.red { background: #8b1a1a; }
.csec { margin: 8px 0 0; }
.ctitle { font-size: 11px; color: var(--mut); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 4px; }
.cchip { display: inline-block; padding: 1px 7px; border-radius: 10px; color: #fff; font-size: 10px; margin-left: 6px; vertical-align: middle; }
.caveat { border-radius: 6px; padding: 8px 10px; font-size: 12px; margin: 4px 0; }
.caveat.red { background: #fff1f1; border: 1px solid #da1e28; color: #a2191f; }
.caveat.yellow { background: #fcf4d6; border: 1px solid #f1c21b; color: #684e00; }
.collapse > summary { cursor: pointer; color: var(--accent); font-size: 11px; padding: 3px 0; }
.secbody { margin-top: 4px; }
.refs { margin-top: 6px; }
.ref { display: inline-block; font-size: 10px; font-family: ui-monospace, monospace; background: var(--accent-bg); color: var(--accent); padding: 1px 4px; border-radius: 3px; margin: 1px; }
.more { color: var(--mut); font-size: 10px; }
.err { color: var(--err); font-family: ui-monospace, monospace; font-size: 12px; }
.chips { margin-top: 6px; }
.chip { display: inline-block; font-size: 10px; font-family: ui-monospace, monospace; background: var(--surface2); color: var(--mut); padding: 1px 5px; border-radius: 3px; margin: 1px; }
.chip.warm { background: #fff3d6; color: #8a5a00; }
.chip.none { background: #fde8e8; color: #a01; }
.chip.bad { background: #a01; color: #fff; }
.adj { margin-top: 8px; font-size: 12px; }
.adj summary { cursor: pointer; color: var(--accent); font-size: 11px; }
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
.patient-banner { background: var(--banner-bg); border: 1px solid var(--accent-bd); border-radius: 8px; padding: 8px 14px; margin: 0 0 14px; font-size: 13px; }
.patient-banner .pt-id { font-family: ui-monospace, monospace; font-weight: 700; }
.patient-banner .pt-name { font-weight: 600; }
.patient-banner a { color: var(--accent); font-weight: 600; text-decoration: none; margin-left: 8px; }
.patient-banner a:hover { text-decoration: underline; }
.patient-banner .pt-block + .pt-block { margin-top: 8px; border-top: 1px solid var(--accent-bd); padding-top: 8px; }
.patient-banner .pt-head { font-size: 13px; }
.patient-banner .pt-demo { color: var(--mut); }
.patient-banner .pt-line { margin-top: 3px; font-size: 12px; color: var(--fg); }
.patient-banner .pt-lab { font-weight: 600; color: var(--mut); }
.patient-banner .pt-counts { color: var(--mut); }
.tile { position: relative; }
.tiles-wrap { position: relative; min-width: 0; }
.scroll-arrow { position: absolute; top: 0; bottom: 0; width: 30px; display: flex; align-items: center; justify-content: center; border: none; cursor: pointer; z-index: 5; font-size: 15px; color: var(--accent); background: var(--arrow-bg); box-shadow: 0 0 8px rgba(0,0,0,.15); }
.scroll-arrow.left { left: -2px; } .scroll-arrow.right { right: -2px; }
.scroll-arrow.disabled { color: #cfcfcf; cursor: default; box-shadow: none; background: rgba(255,255,255,.4); pointer-events: none; }
.fs-btn { position: absolute; top: 8px; right: 8px; font-size: 12px; color: var(--accent); cursor: pointer; background: var(--accent-bg); border: 1px solid var(--accent-bd); border-radius: 6px; padding: 2px 7px; line-height: 1; }
.fs-btn:hover { background: var(--accent-hover); }
.fs-overlay { display: none; position: fixed; inset: 0; background: rgba(20,20,20,.55); z-index: 100; }
.fs-overlay.open { display: flex; align-items: center; justify-content: center; }
.fs-modal { background: var(--surface); width: 92vw; height: 92vh; border-radius: 12px; padding: 18px 24px; overflow: auto; box-shadow: 0 8px 40px rgba(0,0,0,.35); }
.fs-close { float: right; font: inherit; font-weight: 600; cursor: pointer; background: var(--surface2); border: 1px solid var(--line); border-radius: 6px; padding: 4px 12px; }
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
  const rd = m.reference_date ? ' · reference-date ' + m.reference_date : '';
  return 'run ' + m.run_id + ' · ' + m.component + ' · git ' + m.git_sha +
         ' · ' + m.dataset_id + ' · provider ' + m.provider + ' · ' + m.generated_at + rd;
}

function renderSummary(run){
  const sec = el('section', 'summary-section');
  sec.innerHTML = '<h2>comparison summary</h2>' +
    "<p class='intro'>One row per setup: how many questions it answered, how fast, and how often it cited the chart or fell back. These are operational counts (speed and volume), not a measure of whether the answers were right.</p>";
  const rows = run.summary.map(s =>
    "<tr><td class='b'>" + htmlEsc(armTitle(s.backend_id)) + "<span class='model'>" + htmlEsc(s.backend_id) + "</span></td>" +
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

// Human-readable arm titles for headers/labels — resolved from the active run's arm_cards
// (the model_registry resolver), never the raw dashed backend id. `armTitle` = full title
// ("Liquid coord · Qwen writer · validated"); `armShort` = the tight grid/SVG variant
// (drops " · validated"/" · single"). Fall back to the raw id only if a card is missing.
function armCardFor(b){ const r = runById(activeRunId); return (r && r.arm_cards && r.arm_cards[b]) || null; }
function armTitle(b){ const c = armCardFor(b); return (c && c.title) || b; }
function armShort(b){ const c = armCardFor(b); return (c && (c.short_title || c.title)) || b; }
function bpShort(b){ return armShort(b); }
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
  sec.innerHTML='<h2>metric distributions</h2><p class="intro">How each setup behaves across all the questions, shown as a spread rather than a single number — so you can see typical speed, citation count, and answer length, plus the outliers. Wider boxes mean more variable behaviour.</p><p class="metrics-legend"><b>What each is:</b> latency = end-to-end response time (ms) · chart references = citations per answer (a grounding-density proxy) · answer length = characters. <b>Reading a box:</b> the box spans the middle 50% of scenarios (q1–q3), the solid line is the median, the dashed line the mean, whiskers reach 1.5×IQR, dots are outliers. Successful turns only.</p>';
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
  for(var a=0;a<arms.length;a++){ h+='<th title="'+htmlEsc(arms[a])+'">'+htmlEsc(armTitle(arms[a]))+'</th>'; }
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
// WS4 calibrated benchmark: map run.calibrated (per-arm + a "__run__" row) by backend.
function calIndex(run){ var m={}, c=run.calibrated||[]; for(var i=0;i<c.length;i++){ m[c[i].backend]=c[i].calibrated||{}; } return m; }
// The reviewer-tier badge: a clinician sign-off outranks a domain review outranks an owner spot-check.
var TIER_BADGE={owner:{cls:'owner',txt:'owner-reviewed'}, domain:{cls:'domain',txt:'domain-reviewed'}, clinical:{cls:'clinical',txt:'✓ clinician-certified'}};
function tierBadge(tier){ var t=TIER_BADGE[tier]; return t?("<span class='tier-badge "+t.cls+"'>"+htmlEsc(t.txt)+"</span>"):''; }
// Per-cell calibrated render: judge-only -> nothing extra (default path, unchanged headline);
// adjudicated -> the human-anchored point ± 95% CI, the agreement κ, and the tier badge.
function calCell(cal){
  if(!cal || !cal.adjudicated) return '';
  var ci=(cal.ci_low==null||cal.ci_high==null)?'':(" <span class='ci'>95% CI "+fmt10(cal.ci_low)+"–"+fmt10(cal.ci_high)+"</span>");
  var kap=(cal.kappa==null)?'':(" <span class='kap' title='judge↔human agreement (linearly-weighted κ)'>κ "+(Math.round(cal.kappa*100)/100)+"</span>");
  return "<div class='cal'>"+tierBadge(cal.tier)+"<span class='cal-pt'>"+fmt10(cal.point)+"</span>"+ci+kap
    +"<span class='cal-n'> · n="+(cal.n_labeled||0)+" reviewed</span></div>";
}
function renderJudge(run){
  var sec=el('section','judge-section'), j=(run.judge||[]).slice().sort(function(a,b){return (b.benchmark_score||0)-(a.benchmark_score||0);}), has=false;
  for(var i=0;i<j.length;i++){ if(j[i].n>0){ has=true; break; } }
  if(!has){ return null; }
  var cal=calIndex(run);
  var anyCal=false; for(var ck in cal){ if(cal[ck] && cal[ck].adjudicated){ anyCal=true; break; } }
  sec.innerHTML='<h2>quality — reviewer judgment (Scout rubric)</h2>'
   +'<p class="intro">The headline: how good each setup’s answers actually were. A strong AI reviewer graded every answer against the patient’s chart for correctness, completeness, and safety. The <b>Benchmark</b> column is the single 0–100 score to compare setups by; the heatmap below shows it question-by-question. Treat it as directional (one patient, one judge), not a final grade.'
   +(anyCal?' Where a human reviewer adjudicated cells, a <b>calibrated estimate ± 95% CI</b> sits under the judge number — the judge’s score corrected by the human-labeled subset, with the judge↔human agreement κ and a reviewer-tier badge.':'')+'</p>'
   +'<p class="metrics-legend">Each answer scored against the patient’s chart by a strong LLM reviewer (advisory). <b>Benchmark</b> = a soft 0–100 composite of the answer-only scores (accuracy/completeness weighted highest, minus bounded penalties for unsafe / abstention / citation / temporal flags — no hard gates); read it together with the harm, abstain ✗ and fab-refs counts in the same row, never alone.'
   +(anyCal?' <b>Calibrated estimate</b> = Prediction-Powered Inference: the judge’s cheap score on every cell, bias-corrected by the human-adjudicated subset, with a 95% confidence interval; <b>κ</b> = linearly-weighted judge↔human agreement on the ordinal axes; the <b>tier badge</b> names the most-trusted reviewer (owner → domain → clinician).':'')
   +' <b>accuracy</b> = stated facts correct · <b>completeness</b> = includes the needed info · <b>relevance</b> = on-question, no padding (each 0–10). <b>abstain ✓/✗</b> = correctly said "not documented" vs failed-to-abstain. <b>grounding s/p/u</b> = supported / partly / unsupported. <b>fab refs</b> = references that don’t resolve to a real chart record (deterministic). <b>temporal</b> — date ✗ = wrong date↔value or fabricated date · win-over = window claimed beyond the data span · trend-fab = trend asserted from too few points / wrong direction. <b>Drill down:</b> the heatmap is every scenario × arm (green=accurate, amber, red) — click a cell for the note. Caveat: small N, one patient, single judge — directional, not a benchmark. Note: arms are NOT prompt-harmonized — the single-model path uses chartsearchai’s default prompt while the team path uses the orchestrator + synthesis prompts, so differences here confound orchestration with prompt; the next run harmonizes prompts to separate the two.</p>';
  var fab={}, jr=run.judge_rows||[];
  for(var x=0;x<jr.length;x++){ var cr=jr[x].citation_resolution||{}; fab[jr[x].backend_id]=(fab[jr[x].backend_id]||0)+(cr.n_unresolved||0); }
  var rows=j.map(function(s){ var ab=s.abstention||{}, gr=s.groundedness||{}, t=s.temporal||{}, sp=s.benchmark_spread||{};
    return "<tr><td class='b' title='"+htmlEsc(s.backend)+"'>"+htmlEsc(armTitle(s.backend))+"</td>"
      +"<td><b>"+fmt10(s.benchmark_score)+"</b>"+(sp.min==null?'':"<span style='opacity:.55;font-size:.85em'> "+fmt10(sp.min)+"–"+fmt10(sp.max)+"</span>")+calCell(cal[s.backend])+"</td>"
      +"<td>"+s.n+"</td>"
      +"<td>"+fmt10(s.accuracy_mean)+"</td><td>"+fmt10(s.completeness_mean)+"</td><td>"+fmt10(s.relevance_mean)+"</td>"
      +"<td>"+(ab['correct']||0)+" / "+(ab['failed-to-abstain']||0)+"</td>"
      +"<td>"+(gr['supported']||0)+" / "+(gr['partly']||0)+" / "+(gr['unsupported']||0)+"</td>"
      +"<td>"+(s.harm_count||0)+"</td><td>"+(fab[s.backend]||0)+"</td>"
      +"<td>"+(t.date_wrong||0)+"</td><td>"+(t.window_over||0)+"</td><td>"+(t.trend_fab||0)+"</td></tr>"; }).join('');
  var tbl=el('table','summary');
  tbl.innerHTML='<thead><tr><th>backend</th><th>benchmark'+(anyCal?' <span class="th-sub">+ calibrated ± CI</span>':'')+'</th><th>judged</th><th>acc</th><th>comp</th><th>rel</th><th>abstain ✓/✗</th><th>grounding s/p/u</th><th>harm</th><th>fab refs</th><th>date ✗</th><th>win over</th><th>trend fab</th></tr></thead><tbody>'+rows+'</tbody>';
  sec.appendChild(tbl);
  // Click any column header to re-sort the table (numeric or text, toggles asc/desc). Defaults
  // above are benchmark-descending; this is a lightweight inline sort (no external dependency).
  function makeSortable(t){
    var hs=t.querySelectorAll('thead th');
    for(var i=0;i<hs.length;i++){ (function(th,ci){
      th.style.cursor='pointer'; th.title='click to sort';
      th.onclick=function(){
        var tb=t.querySelector('tbody'), rs=Array.prototype.slice.call(tb.querySelectorAll('tr'));
        th._asc=!th._asc; var asc=th._asc;
        rs.sort(function(a,b){
          var x=((a.children[ci]||{}).textContent||'').trim(), y=((b.children[ci]||{}).textContent||'').trim();
          var nx=parseFloat(x), ny=parseFloat(y), num=!isNaN(nx)&&!isNaN(ny);
          var r=num?(nx-ny):x.localeCompare(y); return asc?r:-r;
        });
        rs.forEach(function(r){tb.appendChild(r);});
      };
    })(hs[i],i); }
  }
  makeSortable(tbl);
  // Run-level calibrated callout — only when at least one cell was adjudicated.
  var rc=cal['__run__'];
  if(rc && rc.adjudicated){
    var note=el('p','cal-run');
    note.innerHTML='<b>Run calibrated Benchmark:</b> '+fmt10(rc.point)
      +(rc.ci_low==null?'':' <span class="ci">(95% CI '+fmt10(rc.ci_low)+'–'+fmt10(rc.ci_high)+')</span>')
      +' '+tierBadge(rc.tier)+' <span class="cal-n">over '+(rc.n_labeled||0)+' human-reviewed cells of '+(rc.n_all||0)+'</span>';
    sec.appendChild(note);
  }
  var anyBg=false; for(var b=0;b<j.length;b++){ if((j[b].background||{}).n_background>0){ anyBg=true; break; } }
  if(anyBg){
    var bgRows=j.slice().sort(function(a,b){return ((b.background||{}).benchmark_score||0)-((a.background||{}).benchmark_score||0);}).map(function(s){ var bg=s.background||{}, bsp=bg.benchmark_spread||{};
      if(!bg.n_background){ return "<tr><td class='b'>"+htmlEsc(bpShort(s.backend))+"</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>"; }
      return "<tr><td class='b'>"+htmlEsc(bpShort(s.backend))+"</td>"
        +"<td><b>"+fmt10(bg.benchmark_score)+"</b>"+(bsp.min==null?'':"<span style='opacity:.55;font-size:.85em'> "+fmt10(bsp.min)+"–"+fmt10(bsp.max)+"</span>")+"</td>"
        +"<td>"+bg.n_background+"</td>"
        +"<td>"+fmt10(bg.support_mean)+"</td><td>"+fmt10(bg.added_value_mean)+"</td>"
        +"<td>"+(bg.new_harm_count||0)+"</td><td>"+(bg.padded_count||0)+"</td><td>"+(bg.claims_total||0)+"</td></tr>"; }).join('');
    var bgh=el('h3','jh-title'); bgh.textContent='In-Depth — its own parity Benchmark (any arm that ships one; scored separately from the Answer)';
    sec.appendChild(bgh);
    var bgleg=el('p','metrics-legend'); bgleg.innerHTML='Every arm’s separate <b>In Depth</b> elaboration — single-model two-call AND team — scored on its OWN axes so it never inflates or deflates the Answer scores above. <b>In-Depth Benchmark</b> = (support·0.5 + added-value·0.5)·10 minus 15 for an unsafe elaboration and 5 for padding — the In-Depth’s co-equal 0–100 headline. <b>support</b> = substantiates the answer & chart-grounded · <b>added value</b> = useful context beyond the answer (each 0–10) · <b>unsafe</b> = In-Depth introduced a harm absent from the answer · <b>padded</b> = bloated. An arm with no In-Depth shows “—”.';
    sec.appendChild(bgleg);
    var bgtbl=el('table','summary'); bgtbl.innerHTML='<thead><tr><th>backend</th><th>In-Depth Benchmark</th><th>In-Depth n</th><th>support</th><th>added value</th><th>unsafe</th><th>padded</th><th>claims</th></tr></thead><tbody>'+bgRows+'</tbody>';
    sec.appendChild(bgtbl); makeSortable(bgtbl);
  }
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
  head.querySelector('.backend').textContent = armShort(backend);
  head.querySelector('.label').textContent = backend;
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
    body.innerHTML = (cell.conf_html || '') + "<div class='ans'>" + cell.answer_html + '</div>' + cell.refs_html + cell.blocks_html;
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

// The "how this arm is configured" panel: sampler knobs (per model), the system
// prompt(s) (visible plain-language summary, full text behind a nested reveal), and the
// retrieval line. All values come from the resolver's c.config (llama-router.ini knobs +
// med-agent-hub prompt files / chartsearchai DEFAULT_SYSTEM_PROMPT + the chartsearchai
// retrieval GPs) — nothing is computed here.
const KNOB_LABELS = {temp:'temp', top_p:'top-p', top_k:'top-k', ctx_size:'ctx', seed:'seed',
                     max_tokens:'max-tokens', reasoning_budget:'reasoning-budget', dry:'dry'};
const KNOB_ORDER = ['temp','top_p','top_k','ctx_size','seed','max_tokens','reasoning_budget','dry'];
function renderArmConfig(cfg){
  if(!cfg) return '';
  const knobs = cfg.knobs || {};
  const models = Object.keys(knobs);
  // The summary names what's inside AND surfaces the headline knobs (temp/seed/dry/ctx) +
  // the prompt count, so the panel reads at a glance while collapsed (and the keywords are
  // visible even before expanding). Values are pulled from the first model's resolved knobs.
  const k0 = (models.length ? knobs[models[0]] : {}) || {};
  const tease = [];
  if(k0.temp != null) tease.push('temp ' + k0.temp);
  if(k0.seed != null) tease.push('seed ' + k0.seed);
  if(k0.dry != null) tease.push('DRY on');
  if(k0.ctx_size != null) tease.push('ctx ' + k0.ctx_size);
  const np = (cfg.prompts || []).length;
  if(np) tease.push(np + ' system prompt' + (np>1?'s':''));
  const teaseTxt = tease.length ? (' — ' + tease.join(' · ')) : '';
  let h = "<details class='arm-config'><summary>how this arm is configured" +
          "<span class='ac-tease'>" + htmlEsc(teaseTxt) + "</span></summary><div class='ac-body'>";

  // 1) sampler knobs — one column per model, one row per knob (only knobs that exist).
  if(models.length){
    const present = KNOB_ORDER.filter(k => models.some(m => (knobs[m]||{})[k] != null));
    h += "<div class='ac-h'>sampling knobs <span class='ac-sub'>(llama-router.ini)</span></div>";
    h += "<table class='ac-knobs'><thead><tr><th>knob</th>";
    models.forEach(m => { h += "<th>" + htmlEsc(m) + "</th>"; });
    h += "</tr></thead><tbody>";
    present.forEach(k => {
      h += "<tr><td class='ac-k'>" + htmlEsc(KNOB_LABELS[k] || k) + "</td>";
      models.forEach(m => { const v = (knobs[m]||{})[k]; h += "<td>" + (v==null?'—':htmlEsc(v)) + "</td>"; });
      h += "</tr>";
    });
    h += "</tbody></table>";
  }

  // 2) system prompt(s) — digestible summary visible, full text behind a reveal.
  const prompts = cfg.prompts || [];
  if(prompts.length){
    h += "<div class='ac-h'>system prompt" + (prompts.length>1?'s':'') + "</div>";
    prompts.forEach(p => {
      h += "<div class='ac-prompt'>";
      h += "<div class='ac-plabel'>" + htmlEsc(p.label) + " <span class='ac-src'>" + htmlEsc(p.source) + "</span></div>";
      if(p.summary) h += "<div class='ac-psum'>" + htmlEsc(p.summary) + "</div>";
      h += "<details class='ac-pfull'><summary>full prompt</summary><pre class='ac-pre'>" + htmlEsc(p.text) + "</pre></details>";
      h += "</div>";
    });
  }

  // 3) retrieval line (chartsearchai retrieval GPs, shared across arms).
  const r = cfg.retrieval;
  if(r){
    h += "<div class='ac-h'>retrieval <span class='ac-sub'>(chartsearchai GPs)</span></div>";
    h += "<div class='ac-retr'>pipeline " + htmlEsc(r.pipeline) + " · embedding top-k " + htmlEsc(r.embedding_topk) +
         " · querystore top-k " + htmlEsc(r.querystore_topk) + " · threshold " + htmlEsc(r.threshold) + "</div>";
  }
  h += "</div></details>";
  return h;
}

function renderArms(run){
  const sec = el('section', 'arms-section');
  const cards = run.arm_cards || {};
  let h = "<h2>what this run compares</h2>";
  h += "<p class='intro'>Every setup answers the same questions, graded against the patient's chart. " +
       "<b>Single</b> = one model reads the chart and answers (vanilla chartsearchAI); " +
       "<b>Team</b> = a med-agent-hub pipeline whose models search, consult a specialist, and cross-check before answering.</p>";
  h += "<div class='arm-cards'>";
  run.backends.forEach(b => {
    const c = cards[b] || {kind:'unknown', path:'', models:[], roles:{}};
    const team = c.kind === 'team';
    const badge = team
      ? "<span class='badge team'>TEAM</span>"
      : (c.kind === 'single' ? "<span class='badge single'>SINGLE</span>" : "<span class='badge'>?</span>");
    // Headline = the human-readable title (resolver); the raw backend_id survives only as a
    // tiny muted monospace sub-label under it, never as the headline.
    const title = c.title || b;
    h += "<div class='arm-card'>";
    h += "<div class='arm-head'>" + badge + "<span class='arm-name'>" + htmlEsc(title) + "</span></div>";
    h += "<div class='arm-id'>" + htmlEsc(b) + "</div>";
    if (c.path) h += "<div class='arm-path'>" + htmlEsc(c.path) + "</div>";
    if (team){
      // Makeup = role → readable family·params·quant; the raw dashed model id column is dropped.
      h += "<table class='makeup'><tbody>";
      Object.keys(c.roles || {}).forEach(role => {
        const m = c.roles[role] || {};
        const mq = [m.family, m.params, m.quant].filter(Boolean).join(' · ');
        h += "<tr><td class='role'>" + htmlEsc(role) + "</td><td class='mq'>" + htmlEsc(mq) + "</td></tr>";
      });
      h += "</tbody></table>";
    } else {
      const m = (c.models || [])[0] || {};
      const mq = [m.family, m.params, m.quant].filter(Boolean).join(' · ');
      h += "<div class='makeup-single'>" + htmlEsc(mq) + "</div>";
    }
    h += renderArmConfig(c.config);
    h += "</div>";
  });
  h += "</div>";
  sec.innerHTML = h;
  return sec;
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
  main.appendChild(renderArms(run));
  const judge = renderJudge(run);
  if (judge) main.appendChild(judge);

  run.scenarios.forEach(sc => {
    const sec = el('section', 'scenario');
    sec.dataset.scenario = sc.scenario_id;
    const h = el('h2'); h.textContent = sc.scenario_id; sec.appendChild(h);
    const intro = el('p', 'intro');
    intro.textContent = 'The actual answers for this scenario, one column per setup, lined up question-by-question so you can read them side by side. Drag a tile to rank the setups; click ⛶ to read one full-screen.';
    sec.appendChild(intro);

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

  // Declutter: engineering metrics (latency, chart refs, errors) collapse to the bottom — they
  // are operational, not answer-quality, so they don't lead.
  const eng = el('details', 'eng');
  eng.innerHTML = "<summary>engineering metrics — latency · chart refs · errors (operational, not answer quality)</summary>";
  eng.appendChild(renderSummary(run));
  eng.appendChild(renderMetrics(run));
  main.appendChild(eng);

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
(function(){var b=document.getElementById('theme-toggle');if(!b)return;function s(){b.textContent=document.documentElement.dataset.theme==='dark'?'☀':'☾';}s();b.addEventListener('click',function(){var n=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=n;try{localStorage.setItem('oc-theme-report',n);}catch(e){}s();});})();
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
        "<!doctype html><html data-theme='light'><head><meta charset='utf-8'>"
        f"<title>validation report · {_esc(title)}</title><style>{_STYLE}</style>"
        "<script>(function(){try{var t=localStorage.getItem('oc-theme-report');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;}catch(e){}})();</script></head>"
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
        "<button id='theme-toggle' type='button' title='Toggle light / dark' aria-label='Toggle light or dark mode'></button>"
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
