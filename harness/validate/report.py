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

from harness.common.jsonl import read_jsonl as _read_jsonl
from harness.common.text import esc as _esc
from harness.report_shell.assets import (
    BOXPLOT_CSS,
    BOXPLOT_JS,
    CHIP_CSS,
    SORTABLE_TABLE_CSS,
    SORTABLE_TABLE_JS,
    THEME_CSS_VARS,
    theme_toggle_js,
)
from harness.report_shell.document import render_document
from harness.report_shell.stats import avg, box_stats, ordered_unique, percentile, robust_axis_max

from .bundle import frozen_arm_cards, review_results, run_chart
from .check_precision import load_scores as load_check_precision, table_html as check_precision_html
from .hub_trace import load_traces, match_trace, trace_model_for_result, trace_transport_for_result

from .adjudicate import _human_cell_score
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
from .review_presentation import (
    CLAIM_CHECKS,
    annotate_sources,
    answer_section_view,
    format_latency,
    indepth_section_view,
    score_formatter_js,
    section_confidence_displays,
)
from .response_artifacts import (
    in_depth_artifact,
    prepare_answer_review,
    prepare_indepth_review,
    response_for_displayed_evidence,
    split_answer_sections,
)
from .sources import build_sources, source_ref_labels
from .stage_timings import expected_stage_labels, extract_stage_timings, stage_timing_label

# The med-agent-team bridge gracefully degrades to a schema-valid envelope when
# its own LLM calls fail, so a degraded turn looks like a 200/json_valid/0-cites
# answer to the harness. Surface it from the answer text so a broken backend is
# visible instead of silently passing as an empty answer.
_FALLBACK_MARKER = "could not produce a complete answer"



def _is_degraded(r: dict[str, Any]) -> bool:
    answer = (r.get("response") or {}).get("answer")
    return isinstance(answer, str) and _FALLBACK_MARKER in answer.lower()


def _render_answer(text: Any) -> str:
    """Render the chart-answer envelope's markdown body to HTML, escaping the untrusted model text
    FIRST so it can never inject markup, then upgrading the structural forms the synthesis emits:
    `**Answer**` / `**In Depth**` bold headers (-> <strong>) and `##` ATX headings (-> <h3>). The
    body is CLEAN of confidence text now — confidence renders separately as a chip heading each
    section (see _render_answer_sections / _status_chip).
    Newlines (incl. a literal backslash-n a 4B may copy from the prompt) stay as line breaks under
    the .ans { pre-wrap } style, so the In-Depth `- …` claim bullets render as a readable list."""
    s = html.escape("" if text is None else str(text))
    s = s.replace("\\n", "\n")
    s = re.sub(r"^##\s+(.+?)\s*$", r"<h3>\1</h3>", s, flags=re.MULTILINE)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


_TONE_CLASSES = {"success": "t-ok", "warning": "t-warn", "danger": "t-bad", "neutral": "t-neutral"}


def _tone(tone: Any) -> str:
    return _TONE_CLASSES.get(str(tone or ""), "t-neutral")


def _status_chip(view: Any) -> str:
    """One status chip per section; the product's confidence level follows as text."""
    if not isinstance(view, dict):
        return ""
    chip = f"<span class='schip {_tone(view.get('tone'))}'>{_esc(view.get('label'))}</span>"
    if view.get("confidence"):
        chip += f"<span class='sconf'>{_esc(view.get('confidence'))}</span>"
    return chip


def _render_findings(view: Any) -> str:
    """The findings listed under a section's status when its confidence label is withdrawn."""
    findings = (view or {}).get("findings") if isinstance(view, dict) else None
    if not findings:
        return ""
    items = "".join(
        f"<li class='{_tone(f.get('tone'))}'><b>{_esc(f.get('name'))}</b>"
        + (f" <span class='fwhere'>({_esc(f.get('where'))})</span>" if f.get("where") else "")
        + (f": {_esc(f.get('says'))}" if f.get("says") else "")
        + "</li>"
        for f in findings
        if isinstance(f, dict)
    )
    return f"<ul class='findings'>{items}</ul>"


def _render_section(label: str, body_html: str, view: Any = None, extra: str = "") -> str:
    """Render one section with its status, note and body; output is never hidden."""
    title = f"{_esc(label)} {_status_chip(view)}".rstrip()
    h = f"<div class='csec'><div class='ctitle'>{title}</div>"
    if isinstance(view, dict) and view.get("note"):
        h += f"<div class='snote {_tone(view.get('tone'))}'>{_esc(view.get('note'))}</div>"
    h += _render_findings(view)
    if body_html.strip():
        h += f"<div class='secbody'>{body_html}</div>"
    return h + extra + "</div>"


def _render_claims(view: Any) -> str:
    rows = (view or {}).get("claims") or [] if isinstance(view, dict) else []
    if not rows:
        return ""
    names = view.get("check_names") or {}

    def cell(verdict: dict[str, Any]) -> str:
        reason = (
            f"<div class='creason'>{_esc(verdict.get('reason'))}</div>"
            if verdict.get("reason")
            else ""
        )
        return f"<td class='{_tone(verdict.get('tone'))}'>{_esc(verdict.get('verdict'))}{reason}</td>"

    head = "".join(f"<th>{_esc(names.get(k, k))}</th>" for k in CLAIM_CHECKS)
    def row_html(row: dict[str, Any]) -> str:
        marked = " class='marked'" if row.get("marked") else ""
        cited = " ".join(f"[{i}]" for i in row.get("cited") or []) or "<span class='mut'>none</span>"
        checks = row["checks"]
        cells = "".join(cell(checks[k]) for k in CLAIM_CHECKS)
        return (
            f"<tr{marked}><td>{row['index']}</td><td>{_esc(row.get('text'))}</td><td>{cited}</td>"
            f"{cells}</tr>"
        )

    body = "".join(row_html(row) for row in rows)
    return (
        "<table class='claims'><thead><tr><th>#</th><th>point</th><th>cites</th>"
        f"{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def _render_draft(view: Any, indepth: Any) -> str:
    draft = (view or {}).get("draft") if isinstance(view, dict) else None
    if not isinstance(draft, dict):
        return ""
    review_sources = ((indepth or {}).get("reviewSources") or {}).get("sources") or []
    source_rows = "".join(
        "<li>"
        f"<b>[{_esc(source.get('citation_index') or source.get('record_index') or '?')}]</b> "
        f"{_esc(source.get('date'))} {_esc(source.get('resource_type'))} "
        f"{_esc(source.get('title'))}"
        f"<details><summary>open draft source</summary><pre>{_esc(source.get('source_text'))}</pre></details>"
        "</li>"
        for source in review_sources
    )
    sources = (
        "<div class='reviewrefs'><b>Draft sources (not delivered evidence)</b>"
        f"<ul>{source_rows}</ul></div>"
        if source_rows
        else ""
    )
    return (
        f"<details class='draftbox' data-kind='{_esc(draft.get('kind'))}'>"
        f"<summary>{_esc(draft.get('title'))}</summary>"
        f"<div class='draftnote'>{_esc(draft.get('note'))}</div>"
        f"<div class='secbody'>{_render_answer(draft.get('text'))}</div>{sources}</details>"
    )


def _render_raw_check(view: Any) -> str:
    validation = (view or {}).get("validation") if isinstance(view, dict) else None
    if not validation:
        return ""
    return (
        "<details class='raw-refs'><summary>raw check record</summary>"
        f"<pre class='rawcheck'>{_esc(json.dumps(validation, indent=1))}</pre></details>"
    )


def _render_original_answer(validation: Any, view: Any = None) -> str:
    """The answer before checking, only when it differs in substance."""
    if not isinstance(validation, dict) or not (isinstance(view, dict) and view.get("show_original")):
        return ""
    original = str(validation.get("originalAnswer") or "").strip()
    original_blocks = validation.get("originalBlocks") or []
    edited = validation.get("status") == "edited"
    css_class = "reviewdraft edited" if edited else "reviewdraft"
    notice = (
        "This answer or its supporting citations was changed by the answer check. The checked answer above is the current result."
        if edited
        else "This was the model output before checking. The current answer above remains flagged for review."
    )
    original_sources = (validation.get("originalSources") or {}).get("sources") or []
    source_rows = "".join(
        "<li>"
        f"<b>[{_esc(source.get('citation_index') or source.get('record_index') or '?')}]</b> "
        f"{_esc(source.get('date'))} {_esc(source.get('resource_type'))} "
        f"{_esc(source.get('title'))}"
        f"<details><summary>open original source</summary><pre>{_esc(source.get('source_text'))}</pre></details>"
        "</li>"
        for source in original_sources
    )
    sources = (
        "<div class='reviewrefs'><b>Original-answer sources (not final evidence)</b>"
        f"<ul>{source_rows}</ul></div>"
        if source_rows
        else ""
    )
    return (
        f"<details open class='{css_class}'><summary>Original model answer</summary>"
        f"<div class='reviewdraft-note'>{notice}</div>"
        f"<div class='secbody'>{_render_answer(original)}"
        f"{_render_blocks(original_blocks, validation.get('originalSources'))}</div>"
        f"{sources}</details>"
    )


def _render_answer_sections(
    text: Any,
    answer_view: Any,
    indepth: Any = None,
    indepth_view: Any = None,
    answer_validation: Any = None,
) -> str:
    """Render the Answer and In-Depth sections from the shared section views.

    Each section carries one status and one note naming the checks that marked
    it (review_presentation owns the policy). An arm that reports no checks
    shows its answer plainly; the In-Depth says neutrally when the profile has
    none. Marked output is always visible.
    """
    answer = "" if text is None else str(text)
    if isinstance(answer_view, dict):
        answer = re.sub(r"^\s*\*\*Answer\*\*\s*", "", answer, flags=re.IGNORECASE).strip()
        out = _render_section("Answer", _render_answer(answer), answer_view)
        out += _render_original_answer(answer_validation, answer_view)
    else:
        out = _render_answer(answer)
    if isinstance(indepth_view, dict):
        out += _render_section(
            "In-Depth",
            indepth_view.get("body_html") or "",
            indepth_view,
            _render_claims(indepth_view)
            + _render_draft(indepth_view, indepth)
            + _render_raw_check(indepth_view),
        )
    return out


def _render_blocks(blocks: Any, sources_v1: Any = None) -> str:
    """Render the bridge's `blocks[]` (kind:"table" enumerations the chart-answer
    envelope carries alongside the prose answer) as HTML tables. Cell refs are
    preserved in the raw envelope but collapsed here to row-level source labels
    so the default UX does not repeat citation chips in every cell."""
    out = []
    labels = source_ref_labels(sources_v1 if isinstance(sources_v1, dict) else None)
    for b in blocks or []:
        if not isinstance(b, dict) or b.get("kind") != "table":
            continue
        cols = b.get("columns") or []
        head = "".join(f"<th>{_esc(c.get('label'))}</th>" for c in cols)
        rows_html = []
        for row in b.get("rows") or []:
            cells = row.get("cells") or {}
            row_refs: list[int] = []
            for cell in cells.values():
                if isinstance(cell, dict):
                    row_refs.extend(i for i in (cell.get("refs") or []) if isinstance(i, int))
            row_source_html = ""
            sids = _ordered_unique([labels.get(i, f"[{i}]") for i in row_refs])
            if sids:
                row_source_html = (
                    "<div class='row-sources'>sources "
                    + " ".join(f"<span>{_esc(s)}</span>" for s in sids)
                    + "</div>"
                )
            tds = []
            for ci, c in enumerate(cols):
                cell = cells.get(c.get("key")) or {}
                source_html = row_source_html if ci == 0 else ""
                tds.append(f"<td>{_esc(cell.get('text'))}{source_html}</td>")
            rows_html.append("<tr>" + "".join(tds) + "</tr>")
        title = f"<div class='block-title'>{_esc(b.get('title'))}</div>" if b.get("title") else ""
        out.append(
            f"<div class='block'>{title}<table class='block-tbl'>"
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>"
        )
    return "".join(out)


def _render_refs(references: Any) -> str:
    """Raw resolved references, kept as a debug disclosure instead of default evidence UX."""
    refs = references or []
    if not refs:
        return ""
    shown = " ".join(
        f"<span class='ref'>[{_esc(x.get('index'))}] {_esc(x.get('resourceType'))}</span>"
        for x in refs[:8]
    )
    more = f" <span class='more'>+{len(refs) - 8}</span>" if len(refs) > 8 else ""
    return f"<details class='raw-refs'><summary>raw resolved refs</summary><div class='refs'>{shown}{more}</div></details>"


def _render_sources(sources_v1: Any) -> str:
    """Render canonical sources as clinician-facing evidence tiles."""
    if not isinstance(sources_v1, dict):
        return ""
    sources = sources_v1.get("sources") or []
    diagnostics = sources_v1.get("diagnostics") or {}
    if not sources and not diagnostics.get("malformed_tokens"):
        return ""

    def card(s: dict[str, Any]) -> str:
        meta = " · ".join(_esc(x) for x in [s.get("resource_type"), s.get("date")] if x)
        facts = "".join(f"<li>{_esc(f)}</li>" for f in (s.get("facts_used") or [])[:4])
        if not facts and s.get("source_text"):
            facts = f"<li>{_esc(s.get('source_text'))}</li>"
        tone_cls = {"success": " ok", "danger": " bad", "warning": " warn"}
        citation_index = s.get("citation_index") or s.get("record_index") or "?"
        chart_index = s.get("chart_record_index") or s.get("record_index") or "?"
        sections = "".join(
            f"<span class='source-section'>{_esc(name)}</span>" for name in s.get("sections") or []
        ) or "<span class='source-status'>not cited in the text</span>"
        record = s.get("record_label") or s.get("resolution_status") or "unknown"
        support = s.get("support_label") or s.get("support_status") or "unchecked"
        return (
            "<article class='source-card'>"
            f"<div class='source-head'><b>{_esc(s.get('source_id'))}</b> "
            f"<span>cite [{_esc(citation_index)}] · chart [{_esc(chart_index)}] {_esc(s.get('title'))}</span></div>"
            f"<div class='source-meta'>cited by {sections} · {meta} "
            f"<span class='source-status{tone_cls.get(s.get('record_tone'), '')}'>{_esc(record)}</span>"
            f" <span class='source-status{tone_cls.get(s.get('support_tone'), '')}' title='Hub record-to-claim grounding result; not a whole-answer quality verdict'>{_esc(support)}</span></div>"
            f"<ul>{facts}</ul>"
            f"<details><summary>open source record</summary><pre>{_esc(s.get('source_text'))}</pre></details>"
            "</article>"
        )

    shown = "".join(card(s) for s in sources[:5])
    more = ""
    if len(sources) > 5:
        more = (
            "<details class='source-more'><summary>show all sources</summary>"
            + "".join(card(s) for s in sources[5:])
            + "</details>"
        )
    diag_bits = []
    for key, label in (
        ("unresolved_refs", "unresolved"),
        ("unused_top_refs", "unused top-level"),
        ("nested_only_refs", "nested only"),
        ("malformed_tokens", "malformed tokens"),
    ):
        if diagnostics.get(key):
            diag_bits.append(f"{label}: {_esc(diagnostics.get(key))}")
    diag = f"<div class='source-diag'>{' · '.join(diag_bits)}</div>" if diag_bits else ""
    return f"<section class='sources'><div class='sources-title'>Evidence Used</div><div class='source-grid'>{shown}</div>{more}{diag}</section>"


def _render_chips(r: dict[str, Any]) -> str:
    """The deterministic metric chips: latency (warm on first turn), chart-refs
    COUNT (never a grounding signal), optional streaming/stage chips (TTFT,
    answer_done, TPOT), invalid-json, and the degraded-fallback flag."""
    m = r.get("metrics") or {}
    chips = [
        f"<span class='chip{' warm' if m.get('first_turn') else ''}'>⏱ {_esc(format_latency(m.get('latency_ms')))}</span>",
        f"<span class='chip'>{_esc(m.get('citation_count'))} chart refs</span>",
    ]
    if m.get("ttft_ms") is not None:
        chips.append(
            f"<span class='chip'>TTFT {_esc(format_latency(m.get('ttft_ms')))}</span>"
        )
    if (
        m.get("answer_done_ms") is not None
        and m.get("answer_done_ms") != m.get("latency_ms")
    ):
        chips.append(
            f"<span class='chip'>answer {_esc(format_latency(m.get('answer_done_ms')))}</span>"
        )
    if m.get("tpot_ms") is not None:
        chips.append(
            f"<span class='chip'>TPOT {_esc(m.get('tpot_ms'))}ms/tok</span>"
        )
    if not m.get("json_valid", True):
        chips.append("<span class='chip bad'>invalid</span>")
    if _is_degraded(r):
        chips.append("<span class='chip bad'>⚠ degraded</span>")
    return "".join(chips)


# Private aliases — public implementations live in harness.report_shell.stats.
_ordered_unique = ordered_unique
_avg = avg
_box_stats = box_stats
_percentile = percentile
_robust_axis_max = robust_axis_max


def _backend_labels(events: list[dict[str, Any]]) -> dict[str, str]:
    # The backend's config descriptor (prompt variant + orchestrator/expert models),
    # carried on the backend_selected event so report columns are self-describing.
    # Falls back to modelName for runs recorded before the label was emitted.
    return {
        e["backend_id"]: (e.get("label") or e.get("modelName", ""))
        for e in events
        if e.get("event_type") == "backend_selected"
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
    successful turns only. Shape: {metric_key: {label, axis_max, series:[{backend,
    ...stats}]}}. axis_max is the robust (outlier-clipped) y-axis ceiling the SVG
    clamps to — see _robust_axis_max."""
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
    """Optional reviewer scores at run_dir/judge.jsonl: one line per (scenario_id,
    backend_id) carrying faithfulness + correctness in [0,1] and a short note — the
    LLM-dependent quality layer the raw metrics can't capture. Absent file -> no layer."""
    path = run_dir / "judge.jsonl"
    if not path.exists():
        return []
    return _read_jsonl(path)


def _load_judge_actors(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Independent judge actor passes stored under run_dir/judges/<actor>/judge.jsonl."""
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
    """Optional HUMAN adjudications at run_dir/adjudication.jsonl (adjudicate.adjudication_record
    shape: scenario_id/backend_id/reviewer_tier/axes/harm). These calibrate the LLM judge into a
    clinician-anchored Benchmark with a CI. Absent file -> [] (the default report path stays
    judge-only and renders exactly as before)."""
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
    """Per-backend aggregates (operational + Layer-1 deterministic verification counts),
    precomputed so the JS renders both tables without re-deriving any contract."""
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


def _render_temporal_gate_chip(gate: Any) -> str:
    if not isinstance(gate, dict):
        return ""
    mode = gate.get("mode") or "off"
    status = gate.get("status") or "not_applicable"
    if mode == "off" or status == "not_applicable":
        return f"<span class='chip'>temporal gate {html.escape(str(mode))}</span>"
    cls = " bad" if status == "fail" else " warm"
    applied = gate.get("applied")
    suffix = f" {html.escape(str(applied))}" if applied and applied != "none" else ""
    return (
        f"<span class='chip{cls}'>temporal gate {html.escape(str(mode))}: "
        f"{html.escape(str(status))}{suffix}</span>"
    )


def _cell_blob(
    r: dict[str, Any],
    traces: list[dict[str, Any]] | None = None,
    chart_fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One rendered cell for the blob. Answer/block HTML is rendered in Python
    (escape-FIRST) so the injection contract is enforced and testable; the JS
    just injects the strings. Carries only the surfaced metric subset + the
    precomputed degraded flag, plus the per-section confidence tags from the hub trace."""
    m = r.get("metrics") or {}
    resp = r.get("response") or {}
    trace = _trace_for_row(r, traces)
    gate = _gate_for_row(r, traces)
    answer, embedded_indepth = split_answer_sections(resp.get("answer"))
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

    return {
        "error": r.get("error"),
        "http_status": m.get("http_status"),
        "conf_html": "",  # status heads each answer section (see _render_answer_sections)
        "answer_html": _render_answer_sections(
            answer, answer_view, indepth, indepth_view, answer_validation
        ),
        "answer_view": answer_view,
        "indepth_view": indepth_view,
        "answer_validation_status": (
            answer_validation.get("status") if isinstance(answer_validation, dict) else None
        ),
        "sources": sources_v1,
        "sources_html": _render_sources(sources_v1),
        "refs_html": _render_refs(evidence_response.get("references")),
        "blocks_html": _render_blocks(resp.get("blocks"), sources_v1),
        "chips_html": _render_chips(r) + _render_temporal_gate_chip(gate),
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


def _arm_cards_for(run_dir: Path, backends: list[str]) -> dict[str, Any]:
    """Read captured arm cards only; unavailable cards remain explicitly absent."""
    return frozen_arm_cards(run_dir, backends)


def _comparison_context(
    run_dir: Path,
    events: list[dict[str, Any]],
    manifest: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    """The reader context the run's captured comparison set links to, if it names one.

    Only an https link is kept, with its label and a sentence introducing it.
    """
    context: Any = None
    set_id = next(
        (e.get("comparison_set") for e in events
         if e.get("event_type") == "run" and e.get("comparison_set")),
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


def _run_blob(run_dir: Path) -> dict[str, Any]:
    """Assemble one run into the blob shape. Reads the same three files as before;
    a missing run_manifest.json still raises (contract), results/events tolerated."""
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    results = review_results(run_dir)
    events = _read_jsonl(run_dir / "events.jsonl")
    labels = _backend_labels(events)
    traces = load_traces(run_dir / "trace.jsonl")

    backends = _ordered_unique([r.get("backend_id") for r in results])
    scenario_ids = _ordered_unique([r.get("scenario_id") for r in results])
    run_id = manifest.get("run_id", "")
    otel = manifest.get("otel", {})

    patient_meta = manifest.get("patients", {})
    scenarios = []
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
        scenarios.append({"scenario_id": sid, "turns": turns})

    # Patient grounding: the chart-QA runs are about a real OpenMRS patient. Surface the
    # patient(s) the run actually hit (results' request.patient) with a deep link to the live
    # chart, plus name/identifier when the manifest carries a `patients` map (uuid -> meta;
    # the runner can populate it from OpenMRS — falls back to UUID + chart link without it).
    chart_base = manifest.get(
        "openmrs_chart_base", "https://openmrs.openclinai.org/openmrs/spa/patient")
    patient_uuids = _ordered_unique(
        [(r.get("request") or {}).get("patient") for r in results if (r.get("request") or {}).get("patient")])
    patients = []
    for u in patient_uuids:
        profile = dict(patient_meta.get(u) or {})  # display/identifier/medications/vitals/counts...
        profile["uuid"] = u
        profile.setdefault("chart_url", f"{chart_base}/{u}/chart")
        patients.append(profile)

    # Reference date = the resolved temporal anchor the hub ran under (the "now" for
    # recency/most-recent/series), written into each trace by team._write_trace. Scope to
    # THIS run's cells via per-cell trace matching (trace.jsonl is append-only across runs, so
    # a whole-file scan would pick up stale anchors). A run is one time reality, so
    # collapse to one value; direct (non-hub) backends carry no trace -> excluded.
    _ref_dates = _ordered_unique([
        (_trace_for_row(r, traces) or {}).get("reference_date")
        for r in results
    ])
    _ref_dates = [d for d in _ref_dates if d]
    reference_date = (_ref_dates[0] if len(_ref_dates) == 1
                      else (", ".join(_ref_dates) if _ref_dates else None))
    judge_rows_raw = _load_judge(run_dir)
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
    judge_actors = _load_judge_actors(run_dir)
    judge_actor_cells: dict[str, list[dict[str, Any]]] = {}
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
    # The product's checks scored against the judge (judges/check-precision.json, written
    # by scripts/check-precision.py after judging); absent until a run is judged.
    check_precision = load_check_precision(run_dir)

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
        "summary": _summary_rows(
            results, backends, labels, traces, arm_cards, scenarios, judge_rows
        ),
        "metrics": _metric_distributions(results, backends),
        "judge": scout_summary(judge_rows_raw, backends),
        "judge_rows": judge_rows,
        "judge_actors": sorted(judge_actors.keys()),
        "judge_actor_cells": judge_actor_cells,
        # Who judged: the cards under judges/*/manifest.json, named on every judged score.
        "judging": judge_summary(run_dir),
        # Every pass's rows, so a cell can be opened to each judge's scores and note.
        "judge_passes": judge_actors,
        "judge_combined": combined_judge_summary(judge_actors, backends),
        # WS4: adjudication-calibrated Benchmark. adjudication.jsonl is OPTIONAL — when
        # absent (the default) every calibrated block is judge-only (no CI / no κ) and the
        # dedicated Section 05 (#sec-adjudication) is omitted cleanly. When present, each
        # reviewed arm gains a PPI point ± 95% CI + agreement κ + the reviewer-tier badge.
        "calibrated": calibrated_summary(judge_rows_raw, adj_raw, backends),
        "adjudication_rows": adj_rows,
        "check_precision": check_precision,
        "check_precision_html": (
            check_precision_html(check_precision, {b: labels.get(b) or b for b in backends})
            if check_precision
            else ""
        ),
        "patients": patients,
        "context": context,
        # WS2: structured arm makeup (single and team med-agent-hub profiles +
        # role->model lineup) so the report's "what this run compares" section + badges render
        # from one resolver instead of parsing the label string. Best-effort: never blocks a render.
        # WS1: prefer the run's FROZEN cards (run_meta.json) over re-resolving the current static
        # files, so an old run renders the config it ACTUALLY used (see _arm_cards_for).
        "arm_cards": arm_cards,
        **(
            {"hardware": _load_hardware_meta(run_dir)}
            if _load_hardware_meta(run_dir)
            else {}
        ),
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


# Presentation shell CSS and JS live as first-class static files in `harness/report_shell/`.
from harness.report_shell.assets import (  # noqa: E402
    load_report_shell_css,
    load_report_shell_js,
    report_shell_version,
)
from .report_data import enrich_and_deduplicate_run, write_report_data  # noqa: E402

_STYLE = load_report_shell_css()
_SCRIPT = load_report_shell_js()


def _embed_json(blob: dict[str, Any]) -> str:
    """Serialise the blob and neutralise the three chars that could break out of
    the <script type="application/json"> element (a model answer containing
    </script> must not escape). \\uXXXX escapes are JSON-valid, so JSON.parse
    reverses them transparently."""
    s = json.dumps(blob, ensure_ascii=False)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _document(
    blob: dict[str, Any],
    *,
    external_shell_prefix: str | None = None,
    shell_version: str | None = None,
) -> str:
    legend = (
        "<div class='legend'>"
        "<p class='legend-group-h'>Three-layer read-only evaluation reference</p>"
        "<dl class='legend-key'>"
        "<dt>Layer 1 · Deterministic</dt><dd>HTTP/schema validity, exact chart-reference UUID resolution, and temporal guardrail gate status — computed without an LLM judge.</dd>"
        "<dt>Layer 2 · LLM Judge</dt><dd>advisory Scout autorater composite (0–100), Safety-Adjusted Benchmark (hard-gated on severe harm / critical omission), and per-axis scores.</dd>"
        "<dt>Layer 3 · Human &amp; PPI</dt><dd>clinician/human adjudication recorded via <code>python -m harness.validate adjudicate &lt;run_dir&gt;</code>, paired with Prediction-Powered Inference (PPI) calibration and Cohen’s κ.</dd>"
        "<dt>⏱ latency</dt><dd>end-to-end response time; <b>orange</b> = first turn per backend (carries model warmup).</dd>"
        "<dt>chart refs</dt><dd>count of chart records cited — a COUNT, not a grounding/quality signal.</dd>"
        "<dt>not surfaced</dt><dd>tokens / finish_reasons / response model — not returned by <code>/chat</code> (OTel-deferred).</dd>"
        "</dl></div>"
    )
    first = (blob.get("runs") or [{}])[0]
    _ds = (first.get("meta") or {}).get("dataset_id")
    title = " · ".join(p for p in (_ds, first.get("run_id")) if p)
    body = (
        "<header class='topbar'>"
        # Identity band: the data-derived run title (JS fills #report-title from the
        # blob) on the left; the readily-accessible primary actions (PDF, theme) on
        # the right. The run sub-line (dataset/git/date) sits under the title as muted meta.
        "<div class='topbar-id'>"
        "<div class='id-main'>"
        "<div class='breadcrumb'><a href='../index.html' title='Back to all published validation reports'>← All Reports</a><span class='bc-sep'>·</span><a href='https://openclinai.org/validation-harness/' target='_blank' rel='noopener'>Validation Harness</a></div>"
        "<h1 id='report-title'>Validation report</h1>"
        "<div id='run-meta' class='meta'></div>"
        "</div>"
        "<div class='id-actions'>"
        "<span id='run-switcher' class='run-switcher'>"
        "<label for='run-switcher-sel'>view run</label>"
        "<select id='run-switcher-sel' aria-label='Switch to another published run'></select>"
        "</span>"
        "<button id='print-pdf' class='btn-ghost' title='print / save as PDF'>Download PDF</button>"
        "<button id='theme-toggle' class='btn-ghost btn-icon' type='button' title='Toggle light / dark' aria-label='Toggle light or dark mode'></button>"
        "</div>"
        "</div>"
        "<div class='controls'>"
        "<label id='run-select-wrap' hidden>run <select id='run-select'></select></label>"
        "</div>"
        "<nav id='toc' aria-label='On this page'></nav>"
        "</header>"
        "<a class='skip-link' href='#report'>Skip to report</a>"
        "<main id='report'></main>"
        "<div id='sort-live' class='sr-only' aria-live='polite'></div>"
        f"{legend}"
    )
    ver_q = f"?v={shell_version}" if shell_version else ""
    ext_css = f"{external_shell_prefix.rstrip('/')}/report-shell.css{ver_q}" if external_shell_prefix else None
    ext_js = f"{external_shell_prefix.rstrip('/')}/report-shell.js{ver_q}" if external_shell_prefix else None
    return render_document(
        title=f"validation report · {_esc(title)}",
        body_html=body,
        embedded_data=blob,
        style=_STYLE,
        script=_SCRIPT,
        external_css_href=ext_css,
        external_js_src=ext_js,
    )





def _assemble(run_dirs: list[Path]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": [_run_blob(Path(d)) for d in run_dirs],
    }


def build_report(
    run_dir: Path | str,
    *,
    deduplicate: bool = False,
    write_data_json: bool = False,
    external_shell_prefix: str | None = None,
    shell_version: str | None = None,
) -> Path:
    """Single-run report (N=1 case). Reads run_manifest.json + results.jsonl +
    events.jsonl from run_dir; writes run_dir/report.html (and optional report-data.json)."""
    run_dir = Path(run_dir)
    blob = _assemble([run_dir])
    if deduplicate:
        for r in blob.get("runs") or []:
            enrich_and_deduplicate_run(r, force_pool=True)
    if write_data_json:
        write_report_data(run_dir, blob)
    ver = shell_version or (report_shell_version(_STYLE, _SCRIPT) if external_shell_prefix else None)
    out = run_dir / "report.html"
    out.write_text(
        _document(blob, external_shell_prefix=external_shell_prefix, shell_version=ver),
        encoding="utf-8",
    )
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
