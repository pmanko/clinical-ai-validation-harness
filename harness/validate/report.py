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

from .hub_trace import load_traces, match_trace, trace_model_for_result
from .model_registry import arm_model_name
from .model_registry import arm_card
from .reconcile import calibrated_summary, combined_judge_summary, scout_summary
from .review_presentation import (
    indepth_validation_display,
    score_formatter_js,
    section_confidence_displays,
    validation_display,
)
from .response_artifacts import (
    in_depth_artifact,
    prepare_answer_review,
    prepare_indepth_review,
    response_for_displayed_evidence,
    split_answer_sections,
)
from .sources import build_sources, load_scenario_chart, source_ref_labels
from .stage_timings import expected_stage_labels, extract_stage_timings, stage_timing_label

# The med-agent-team bridge gracefully degrades to a schema-valid envelope when
# its own LLM calls fail, so a degraded turn looks like a 200/json_valid/0-cites
# answer to the harness. Surface it from the answer text so a broken backend is
# visible instead of silently passing as an empty answer.
_FALLBACK_MARKER = "could not produce a complete answer"
_DATA_DIR = Path(__file__).resolve().parents[2] / "datasets" / "validation"


def _is_degraded(r: dict[str, Any]) -> bool:
    answer = (r.get("response") or {}).get("answer")
    return isinstance(answer, str) and _FALLBACK_MARKER in answer.lower()


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


_CONF_COLORS = {"green": "#196c2e", "yellow": "#9e6a03", "red": "#8b1a1a"}


def _conf_chip(display: Any) -> str:
    if not isinstance(display, dict):
        return ""
    color = _CONF_COLORS.get(display.get("level"), "#30363d")
    return (
        f"<span class='cchip' style='background:{color}'>"
        f"{_esc(display.get('label'))}</span>"
    )


def _validation_chip(display: Any) -> str:
    if not isinstance(display, dict):
        return ""
    cls = " bad" if display.get("tone") == "danger" else (
        " warm" if display.get("tone") == "warning" else ""
    )
    return f"<span class='chip{cls}'>{_esc(display.get('label'))}</span>"


def _render_section(
    label: str,
    body: str,
    confidence_display: Any,
    lifecycle_display: Any = None,
) -> str:
    """Render one answer section without hiding low-confidence output from reviewers."""
    if not body.strip():
        return ""
    rendered = _render_answer(body)
    title = (
        f"{_esc(label)} {_conf_chip(confidence_display)} "
        f"{_validation_chip(lifecycle_display)}"
    ).rstrip()
    h = f"<div class='csec'><div class='ctitle'>{title}</div>"
    if not isinstance(confidence_display, dict):
        return h + f"<div class='secbody'>{rendered}</div></div>"
    note = confidence_display.get("note") or ""
    treatment = confidence_display.get("note_treatment")
    if treatment == "prominent":
        if note:
            h += f"<div class='caveat red'>{_esc(note)}</div>"
        h += f"<div class='secbody'>{rendered}</div>"
    elif treatment == "collapsible":
        h += f"<div class='secbody'>{rendered}</div>"
        if note:
            h += (f"<details class='collapse'><summary>show review note</summary>"
                  f"<div class='caveat yellow'>{_esc(note)}</div></details>")
    else:
        h += f"<div class='secbody'>{rendered}</div>"
    return h + "</div>"


def _render_review_draft(indepth: Any) -> str:
    if not isinstance(indepth, dict):
        return ""
    draft = str(indepth.get("reviewDraft") or "").strip()
    if not draft:
        return ""
    review_sources = (indepth.get("reviewSources") or {}).get("sources") or []
    source_rows = "".join(
        "<li>"
        f"<b>[{_esc(source.get('citation_index') or source.get('record_index') or '?')}]</b> "
        f"{_esc(source.get('date'))} {_esc(source.get('resource_type'))} "
        f"{_esc(source.get('title'))} "
        f"<span>{_esc(source.get('resolution_status') or 'unknown')}</span>"
        f"<details><summary>open draft source</summary><pre>{_esc(source.get('source_text'))}</pre></details>"
        "</li>"
        for source in review_sources
    )
    sources = (
        "<div class='reviewrefs'><b>Draft sources for review (not final evidence)</b>"
        f"<ul>{source_rows}</ul></div>"
        if source_rows
        else ""
    )
    return (
        "<details class='reviewdraft'><summary>Removed In-Depth claims</summary>"
        "<div class='reviewdraft-note'>These model-generated claims were removed or withheld "
        "by checks. They are shown only for manual review and are not part of the final "
        "clinical response.</div>"
        f"<div class='secbody'>{_render_answer(draft)}</div>{sources}</details>"
    )


def _render_original_answer(validation: Any, current_answer: str) -> str:
    if not isinstance(validation, dict):
        return ""
    original = str(validation.get("originalAnswer") or "").strip()
    original_blocks = validation.get("originalBlocks") or []
    has_original_reference_artifact = (
        "originalReferences" in validation or "originalSources" in validation
    )
    current = re.sub(
        r"^\s*\*\*Answer\*\*\s*", "", str(current_answer), flags=re.IGNORECASE
    ).strip()
    if not original or (
        original == current
        and not original_blocks
        and not has_original_reference_artifact
    ):
        return ""
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
        f"{_esc(source.get('title'))} "
        f"<span>{_esc(source.get('resolution_status') or 'unknown')}</span>"
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


def _render_indepth_artifact(indepth: Any, confidence_display: Any = None) -> str:
    if not isinstance(indepth, dict):
        return ""
    body = indepth.get("answer") or ""
    lifecycle = indepth_validation_display(indepth)
    state = _validation_chip(lifecycle)
    review = _render_review_draft(indepth)
    if str(body).strip():
        if (
            indepth.get("source") == "answer"
            and confidence_display is None
            and lifecycle is None
        ):
            return _render_answer(f"**In Depth**\n{body}") + review
        return (
            _render_section("In-Depth", str(body), confidence_display, lifecycle)
            + review
        )
    if lifecycle is None:
        return ""
    error = indepth.get("error") or "No In-Depth content was displayed."
    tone = lifecycle.get("tone")
    return (
        "<div class='csec'><div class='ctitle'>In-Depth "
        f"{state}</div><div class='caveat{' red' if tone == 'danger' else ' yellow'}'>"
        f"{_esc(error)}</div>{review}</div>"
    )


def _render_answer_sections(
    text: Any,
    trace: Any,
    indepth: Any = None,
    answer_validation: Any = None,
    response_confidence: Any = None,
) -> str:
    """Render normalized Answer / In-Depth sections, each headed by its validator
    confidence tag, with flagged output visible for manual review.
    ``indepth`` is the normalized artifact from response_artifacts, covering the
    current hub envelope and historical separate-call runs. Falls back to a
    single plain answer for direct single-LLM arms and older combined answers."""
    answer = "" if text is None else str(text)
    a_conf, d_conf = section_confidence_displays(trace, response_confidence)
    answer_lifecycle = validation_display(answer_validation)
    indepth_lifecycle = indepth_validation_display(indepth)
    sep_indepth = ""
    if isinstance(indepth, dict):
        ia = indepth.get("answer") or ""
        sep_indepth = re.sub(r"^\s*\*\*In ?Depth\*\*\s*", "", str(ia), flags=re.IGNORECASE).strip()
    has_review_state = a_conf or d_conf or answer_lifecycle or indepth_lifecycle
    if not has_review_state:
        out = _render_answer(answer) + _render_original_answer(
            answer_validation, answer
        )
        if sep_indepth:
            out += _render_indepth_artifact({**indepth, "answer": sep_indepth}, None)
        elif isinstance(indepth, dict) and indepth.get("status"):
            out += _render_indepth_artifact(indepth, None)
        return out
    strip_hdr = lambda s: re.sub(r"^\s*\*\*Answer\*\*\s*", "", s, flags=re.IGNORECASE).strip()  # noqa: E731
    answer_body = strip_hdr(answer)
    out = _render_section("Answer", answer_body, a_conf, answer_lifecycle)
    out += _render_original_answer(answer_validation, answer_body)
    if sep_indepth:
        out += _render_indepth_artifact({**indepth, "answer": sep_indepth}, d_conf)
    elif isinstance(indepth, dict) and indepth.get("status"):
        out += _render_indepth_artifact(indepth, d_conf)
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
        status = s.get("resolution_status") or "unknown"
        status_cls = " ok" if status == "resolved" else (" bad" if status == "unresolved" else "")
        citation_index = s.get("citation_index") or s.get("record_index") or "?"
        chart_index = s.get("chart_record_index") or s.get("record_index") or "?"
        support = s.get("support_status") or "unchecked"
        support_cls = " ok" if support == "verified" else (" bad" if support in {"unsupported", "mixed"} else "")
        return (
            "<article class='source-card'>"
            f"<div class='source-head'><b>{_esc(s.get('source_id'))}</b> "
            f"<span>cite [{_esc(citation_index)}] · chart [{_esc(chart_index)}] {_esc(s.get('title'))}</span></div>"
            f"<div class='source-meta'>{meta} <span class='source-status{status_cls}'>chart ref {_esc(status)}</span>"
            f" <span class='source-status{support_cls}' title='Hub record-to-claim grounding result; not a whole-answer quality verdict'>hub grounding {_esc(support)}</span></div>"
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
        trace_model_for_result(r, arm_model_name(r.get("backend_id"))),
        r.get("started_at"),
        r.get("ended_at"),
        question=request.get("question"),
        session=request.get("session"),
        request_id=request.get("request_id"),
    )


def _gate_for_row(r: dict[str, Any], traces: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    tr = _trace_for_row(r, traces)
    gate = tr.get("temporal_gate") if isinstance(tr, dict) else None
    return gate if isinstance(gate, dict) else None


def _summary_rows(
    results: list[dict[str, Any]],
    backends: list[str],
    labels: dict[str, str],
    traces: list[dict[str, Any]] | None = None,
    arm_cards: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Per-backend aggregates (the old summary table rows), precomputed so the JS
    renders a table without re-deriving any contract."""
    rows = []
    for b in backends:
        rs = [r for r in results if r.get("backend_id") == b]
        lat = [r["metrics"]["latency_ms"] for r in rs if r.get("metrics")]
        cites = sum(r["metrics"].get("citation_count", 0) for r in rs if r.get("metrics"))
        gates = [_gate_for_row(r, traces) for r in rs]
        gates = [g for g in gates if g]
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
                "temporal_gate_warn": sum(1 for g in gates if g.get("status") == "warn"),
                "temporal_gate_fail": sum(1 for g in gates if g.get("status") == "fail"),
                "temporal_gate_applied": sum(1 for g in gates if g.get("applied") in {"patch", "fallback"}),
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
        )
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
    gate = trace.get("temporal_gate") if isinstance(trace, dict) else None
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
    sources_v1 = build_sources(evidence_response, chart_fixture)

    return {
        "error": r.get("error"),
        "http_status": m.get("http_status"),
        "conf_html": "",  # tags now head each answer section (see _render_answer_sections)
        "answer_html": _render_answer_sections(
            answer,
            trace,
            indepth,
            answer_validation,
            resp.get("confidence"),
        ),
        "answer_confidence_display": answer_confidence_display,
        "indepth_confidence_display": indepth_confidence_display,
        "answer_validation_display": validation_display(answer_validation),
        "indepth_validation_display": indepth_validation_display(indepth),
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
    def _resolve(b: str) -> dict[str, Any]:
        live = arm_card(b)
        if b in frozen:
            # Config (knobs/prompts/models) stays FROZEN — what actually ran. But the display name
            # (title/short_title/label) is refreshed from live so renaming/quant fixes show up in
            # already-run reports (e.g. "Gemma 4 12B" -> "Gemma 4 12B · Q8").
            return {**frozen[b], "title": live.get("title"),
                    "short_title": live.get("short_title"), "label": live.get("label")}
        return live
    return {b: _resolve(b) for b in backends}


def _run_blob(run_dir: Path) -> dict[str, Any]:
    """Assemble one run into the blob shape. Reads the same three files as before;
    a missing run_manifest.json still raises (contract), results/events tolerated."""
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    results = _read_jsonl(run_dir / "results.jsonl")
    events = _read_jsonl(run_dir / "events.jsonl")
    labels = _backend_labels(events)
    # Per-turn diagnostics also live in the hub artifact. New runs correlate by request session;
    # historical runs use level, exact question, and nearest completion time. artifacts/hub-trace
    # is a sibling of artifacts/validate/<run>, i.e. run_dir.parent.parent / hub-trace.
    traces = load_traces(run_dir.parent.parent / "hub-trace" / "trace.jsonl")

    backends = _ordered_unique([r.get("backend_id") for r in results])
    scenario_ids = _ordered_unique([r.get("scenario_id") for r in results])
    run_id = manifest.get("run_id", "")
    otel = manifest.get("otel", {})

    scenarios = []
    for sid in scenario_ids:
        chart_fixture = load_scenario_chart(sid, _DATA_DIR / "scenarios", _DATA_DIR / "charts")
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
                    cells[b] = _cell_blob(r, traces, chart_fixture)
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
    judge_rows = _load_judge(run_dir)
    judge_actors = _load_judge_actors(run_dir)
    arm_cards = _arm_cards_for(run_dir, backends)

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
        "summary": _summary_rows(results, backends, labels, traces, arm_cards),
        "metrics": _metric_distributions(results, backends),
        "judge": scout_summary(judge_rows, backends),
        "judge_rows": judge_rows,
        "judge_actors": sorted(judge_actors.keys()),
        "judge_combined": combined_judge_summary(judge_actors, backends),
        # WS4: adjudication-calibrated Benchmark. adjudication.jsonl is OPTIONAL — when
        # absent (the default) every calibrated block is judge-only (no CI / no κ) and the
        # judged-scores section renders exactly as before. When present, each reviewed arm
        # gains a PPI point ± 95% CI + agreement κ + the reviewer-tier badge.
        "calibrated": calibrated_summary(
            judge_rows, _load_adjudication(run_dir), backends),
        "patients": patients,
        # WS2: structured arm makeup (single and team med-agent-hub profiles +
        # role->model lineup) so the report's "what this run compares" section + badges render
        # from one resolver instead of parsing the label string. Best-effort: never blocks a render.
        # WS1: prefer the run's FROZEN cards (run_meta.json) over re-resolving the current static
        # files, so an old run renders the config it ACTUALLY used (see _arm_cards_for).
        "arm_cards": arm_cards,
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


# ChartSearchAI report CSS: shared shell pieces + domain layout.
_STYLE_BEFORE_SORT = """* { box-sizing: border-box; }
body { font: 14px/1.5 -apple-system, system-ui, sans-serif; color: var(--fg); margin: 0; background: var(--bg); }
.topbar { position: sticky; top: 0; z-index: 30; background: var(--surface); border-bottom: 1px solid var(--line); padding: 12px 24px; }
/* Identity band: data-derived title (left) vs. primary + overflow actions (right). */
.topbar-id { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.topbar-id .id-main { min-width: 0; }
.topbar h1 { font-size: 19px; font-weight: 700; margin: 0; letter-spacing: -.01em; line-height: 1.25; }
.topbar #run-meta { margin-top: 3px; }
.topbar-id .id-actions { display: flex; gap: 6px; align-items: center; flex-shrink: 0; }
/* Ghost button — readily-accessible but visually quiet (PDF, theme toggle, overflow). */
.btn-ghost { font: inherit; font-weight: 600; font-size: 12px; padding: 5px 12px; cursor: pointer; color: var(--fg); background: var(--surface); border: 1px solid var(--line); border-radius: 6px; line-height: 1.4; }
.btn-ghost:hover { background: var(--surface2); border-color: var(--accent-bd); }
.btn-ghost:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.btn-icon { padding: 5px 9px; }
/* Overflow menu: subdued summary trigger + an anchored disclosure panel (the rarely-used
   reviewer exports live here, grouped, so they don't dominate the header). */
.overflow { position: relative; }
.overflow > summary { list-style: none; display: inline-block; }
.overflow > summary::-webkit-details-marker { display: none; }
.overflow > summary::marker { content: ''; }
.overflow[open] > summary { background: var(--surface2); border-color: var(--accent-bd); }
.overflow-panel { position: absolute; right: 0; top: calc(100% + 6px); z-index: 40; min-width: 230px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 6px 24px rgba(0,0,0,.16); padding: 8px; display: flex; flex-direction: column; gap: 4px; }
.overflow-h { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--mut); margin: 2px 6px 4px; }
.menu-item { font: inherit; font-size: 12px; text-align: left; padding: 6px 8px; cursor: pointer; color: var(--fg); background: none; border: 0; border-radius: 5px; }
.menu-item:hover { background: var(--accent-bg); color: var(--accent); }
.menu-item:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.menu-field { display: flex; flex-direction: column; gap: 3px; font-size: 11px; color: var(--mut); padding: 4px 8px 2px; border-top: 1px solid var(--line); margin-top: 2px; }
.menu-field input { font: inherit; padding: 4px 6px; border: 1px solid var(--line); border-radius: 5px; background: var(--surface); color: var(--fg); }
.controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 12px; }
.controls:empty { display: none; }
.controls label { font-size: 12px; color: var(--mut); }
.controls select, .controls input[type=search], .controls input { font: inherit; padding: 3px 6px; }
.controls button { font: inherit; font-weight: 600; padding: 5px 12px; cursor: pointer; }
/* Topbar run-switcher: navigates to a SIBLING published run dir. Hidden by default —
   shown only after the sibling reports-index.json successfully loads (graceful
   degradation for a local file:// open / absent index). */
.run-switcher { display: none; align-items: center; gap: 5px; }
.run-switcher.ready { display: inline-flex; }
.run-switcher label { font-size: 12px; color: var(--mut); }
.run-switcher select { font: inherit; font-size: 12px; padding: 4px 8px; max-width: 360px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--fg); }
.toggles { display: flex; gap: 8px; align-items: center; border: 1px solid var(--line); border-radius: 6px; padding: 3px 8px; margin: 0; }
.toggles legend { font-size: 11px; color: var(--mut); padding: 0 4px; }
.toggles label { font-size: 12px; color: var(--fg); display: inline-flex; gap: 3px; align-items: center; }
.meta { color: var(--mut); font-size: 12px; font-family: ui-monospace, monospace; }

/* Section-local filter bar (UX research: filters live next to the data they affect —
   Pencil&Paper / LogRocket / Aufait: component-level filters for discrepant sections;
   only global dimensions belong in a page toolbar). Sits at the top of the Answers
   section, sticky just under the topbar so it stays reachable while scrolling tiles. */
.answers-filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; position: sticky; top: var(--topbar-h, 64px); z-index: 20; background: var(--bg); padding: 8px 0; margin: 0 0 6px; border-bottom: 1px solid var(--line); }
.answers-filters label { font-size: 12px; color: var(--mut); }
.answers-filters select, .answers-filters input[type=search] { font: inherit; padding: 4px 7px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--fg); }
.answers-filters input[type=search] { min-width: 220px; }

/* Multi-select "Filter setups ▾" dropdown (UX research: NN/g listbox-vs-dropdown — a
   checkbox listbox holds many options compactly; UX Patterns / Baymard — select-all +
   clear-all + a count badge for reporting filters). A <details> disclosure anchors a
   scrollable checkbox panel; the trigger shows an "N of M" badge. Scales to 11+ setups. */
.setup-filter { position: relative; display: inline-block; }
.setup-filter > summary { list-style: none; display: inline-flex; align-items: center; gap: 7px; cursor: pointer; font: inherit; font-weight: 600; font-size: 12px; padding: 5px 11px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--fg); }
.setup-filter > summary::-webkit-details-marker { display: none; }
.setup-filter > summary::marker { content: ''; }
.setup-filter > summary:hover { border-color: var(--accent-bd); background: var(--surface2); }
.setup-filter[open] > summary { border-color: var(--accent-bd); background: var(--surface2); }
.setup-filter > summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.setup-count { font: 11px ui-monospace, monospace; background: var(--accent-bg); color: var(--accent); border: 1px solid var(--accent-bd); border-radius: 10px; padding: 0 7px; }
.setup-count.count-badge.partial { background: #fff3d6; color: #8a5a00; border-color: #f1c21b; }
.setup-panel { position: absolute; left: 0; top: calc(100% + 6px); z-index: 50; min-width: 260px; max-width: 380px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 6px 24px rgba(0,0,0,.18); padding: 8px; }
.setup-panel-acts { display: flex; gap: 6px; padding: 2px 2px 8px; border-bottom: 1px solid var(--line); margin-bottom: 6px; }
.setup-panel-acts button { font: inherit; font-size: 11px; font-weight: 600; padding: 3px 9px; cursor: pointer; color: var(--accent); background: var(--accent-bg); border: 1px solid var(--accent-bd); border-radius: 5px; }
.setup-panel-acts button:hover { background: var(--accent-hover); }
.setup-list { max-height: 280px; overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
.setup-list label { display: flex; gap: 7px; align-items: center; font-size: 12px; color: var(--fg); padding: 5px 6px; border-radius: 5px; cursor: pointer; }
.setup-list label:hover { background: var(--accent-bg); }
.setup-list input { margin: 0; flex-shrink: 0; }
main { max-width: none; margin: 0 auto; padding: 16px 24px 120px; }
.intro { color: var(--mut); font-size: 13px; margin: 4px 0 14px; max-width: 84ch; }
section.intro-led > .intro:first-child { margin-top: 0; }

/* Skip-link + visually-hidden (screen-reader-only) helper (a11y). */
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.skip-link { position: absolute; left: 8px; top: -48px; z-index: 60; background: var(--accent); color: #fff; padding: 8px 14px; border-radius: 0 0 8px 8px; font-weight: 600; transition: top .15s; }
.skip-link:focus { top: 0; }

/* Sticky in-page table of contents (scrollspy). Sits in the sticky topbar so the section
   anchors are always one click away; the active link is highlighted as you scroll. */
#toc { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 10px; border-top: 1px solid var(--line); padding-top: 8px; }
#toc .toc-link { font-size: 12px; font-weight: 600; color: var(--mut); text-decoration: none; padding: 4px 10px; border-radius: 6px; border: 1px solid transparent; white-space: nowrap; }
#toc .toc-link:hover { background: var(--accent-bg); color: var(--accent); }
#toc .toc-link[aria-current="location"] { background: var(--accent-bg); color: var(--accent); border-color: var(--accent-bd); }

/* Distinct, numbered, divider-led sections (UX research: numbered headings + dividers +
   whitespace so stacked sections read as separate blocks). scroll-margin-top keeps an
   anchored heading clear of the sticky header. */
#report > section.rsec { counter-increment: rsec; border-top: 2px solid var(--line); margin-top: 34px; padding-top: 22px; scroll-margin-top: 128px; }
#report > section.rsec:first-of-type { border-top: 0; margin-top: 8px; }
#report > section.rsec > h2 { font-size: 17px; margin: 0 0 10px; font-family: -apple-system, system-ui, sans-serif; font-weight: 700; display: flex; align-items: baseline; gap: 10px; }
#report > section.rsec > h2 .sec-h::before { content: counter(rsec, decimal-leading-zero) " "; color: var(--accent); font-family: ui-monospace, monospace; font-weight: 700; margin-right: 6px; }
#report > section.rsec > h2 .sec-note { font-size: 11px; font-weight: 600; color: var(--mut); text-transform: uppercase; letter-spacing: .04em; background: var(--surface2); border: 1px solid var(--line); border-radius: 10px; padding: 2px 8px; }
.scenario-h { font-size: 14px; margin: 22px 0 6px; font-family: ui-monospace, monospace; color: var(--fg); }
/* Engineering = visible but de-emphasized (operational, not answer quality). */
#sec-engineering { opacity: .92; }
#sec-engineering > h2 .sec-h { color: var(--mut); }

"""
_STYLE_BEFORE_BP = """.arms-section { margin: 8px 24px 0; }
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
table { border-collapse: collapse; width: 100%; background: var(--surface); }
th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: var(--surface2); font-weight: 600; font-size: 12px; }
.summary td, .summary th { text-align: center; }
.summary td.b { text-align: left; font-family: ui-monospace, monospace; }
.summary .model { display: block; color: var(--mut); font-size: 11px; }
.metrics-section { margin-top: 18px; }
.metrics-legend { color: var(--mut); font-size: 12px; margin: 2px 0 10px; }

/* Scannable grading-key / legend: a definition grid (term -> concise definition) instead
   of a dense prose wall. <dl> keeps the term↔definition pairing semantic + screen-reader
   navigable (W3C H40 / WCAG). Long secondary detail nests in a <details> disclosure
   (progressive disclosure, NN/g). */
.legend-key { display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px; margin: 6px 0 0; font-size: 12px; align-items: baseline; }
.legend-key dt { font-weight: 700; color: var(--fg); font-size: 11.5px; }
.legend-key dd { margin: 0; color: var(--mut); }
.legend-key dd b, .legend-key dt b { color: var(--fg); font-weight: 700; }
.legend-key code { font-family: ui-monospace, monospace; font-size: 11px; background: var(--surface2); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; color: var(--fg); }
/* When several short keys sit side by side (e.g. box-plot glyphs), let the grid wrap as
   chips rather than one tall column. */
.legend-chips { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 6px 0 0; font-size: 12px; }
.legend-chips .lk { display: inline-flex; gap: 5px; align-items: baseline; color: var(--mut); }
.legend-chips .lk b { color: var(--fg); font-weight: 700; }
.legend-detail { margin: 8px 0 4px; }
.legend-detail > summary { cursor: pointer; color: var(--accent); font-size: 12px; font-weight: 600; list-style: none; display: inline-flex; align-items: center; gap: 4px; }
.legend-detail > summary::-webkit-details-marker { display: none; }
.legend-detail > summary::after { content: '▾'; font-size: 10px; transition: transform .15s; }
.legend-detail[open] > summary::after { transform: rotate(180deg); }
.legend-detail > summary:hover { text-decoration: underline; }
.legend-detail > summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 3px; }
.legend-detail .legend-body { margin-top: 8px; padding: 10px 12px; background: var(--note-bg); border: 1px solid var(--line); border-radius: 8px; }
.legend-detail .legend-body p { margin: 0 0 6px; color: var(--mut); font-size: 12px; }
.legend-detail .legend-body p:last-child { margin-bottom: 0; }
.legend-caveat { font-size: 11.5px; color: var(--mut); margin: 8px 0 0; font-style: italic; }
.legend-group-h { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--mut); margin: 12px 0 2px; }
.legend-group-h:first-child { margin-top: 6px; }
.metrics-grid { display: flex; flex-wrap: wrap; gap: 16px; }
"""
_STYLE_BEFORE_CHIP = """.judge-section { margin-top: 18px; }
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
.tile:has(.reviewdraft[open]) .ans { max-height: none; }
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
.reviewdraft { margin-top: 8px; border-left: 3px solid #da1e28; padding-left: 10px; }
.reviewdraft > summary { cursor: pointer; color: var(--fg); font-size: 12px; font-weight: 650; padding: 4px 0; }
.reviewdraft > summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.reviewdraft-note { background: #fff1f1; color: #a2191f; font-size: 12px; padding: 7px 9px; margin: 4px 0; }
.reviewdraft.edited { border-left-color: #f1c21b; }
.reviewdraft.edited .reviewdraft-note { background: #fcf4d6; color: #684e00; }
.reviewrefs { margin-top: 8px; font-size: 11px; color: var(--mut); }
.reviewrefs ul { margin: 5px 0 0 18px; padding: 0; }
.reviewrefs li { margin: 4px 0; }
.reviewrefs li > span { margin-left: 4px; }
.reviewrefs details { margin-top: 2px; }
.reviewrefs summary { cursor: pointer; color: var(--accent); }
.reviewrefs pre { white-space: pre-wrap; margin: 3px 0 6px; }
.secbody { margin-top: 4px; }
.raw-refs { margin-top: 6px; color: var(--mut); font-size: 11px; }
.raw-refs summary { cursor: pointer; color: var(--mut); }
.refs { margin-top: 6px; }
.ref { display: inline-block; font-size: 10px; font-family: ui-monospace, monospace; background: var(--accent-bg); color: var(--accent); padding: 1px 4px; border-radius: 3px; margin: 1px; }
.more { color: var(--mut); font-size: 10px; }
.sources { margin-top: 10px; border-top: 1px solid var(--line); padding-top: 8px; }
.sources-title { font-size: 11px; font-weight: 700; color: var(--mut); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 5px; }
.source-grid { display: grid; gap: 6px; }
.source-card { border: 1px solid var(--line); background: var(--surface2); border-radius: 7px; padding: 7px 8px; }
.source-head { display: flex; gap: 6px; align-items: baseline; font-size: 11px; }
.source-head b { color: var(--accent); font-family: ui-monospace, monospace; }
.source-meta { color: var(--mut); font-size: 10px; margin-top: 2px; }
.source-status { display: inline-block; margin-left: 4px; padding: 0 5px; border-radius: 8px; background: var(--line); color: var(--mut); }
.source-status.ok { background: #e6f5ea; color: #196c2e; }
.source-status.bad { background: #fde8e8; color: #a01; }
.source-card ul { margin: 4px 0 0 16px; padding: 0; color: var(--fg); font-size: 11px; }
.source-card details { margin-top: 4px; color: var(--mut); }
.source-card summary { cursor: pointer; font-size: 10px; }
.source-card pre { white-space: pre-wrap; margin: 4px 0 0; font-size: 10px; color: var(--mut); }
.source-more { margin-top: 6px; }
.source-more > summary { cursor: pointer; color: var(--accent); font-size: 11px; }
.source-diag { margin-top: 5px; color: var(--mut); font-size: 10px; }
.err { color: var(--err); font-family: ui-monospace, monospace; font-size: 12px; }
"""
_STYLE_AFTER_CHIP = """.adj { margin-top: 8px; font-size: 12px; }
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
.row-sources { margin-top: 3px; color: var(--mut); font-size: 10px; }
.row-sources span { display: inline-block; margin-left: 3px; padding: 0 4px; border-radius: 6px; background: var(--accent-bg); color: var(--accent); font-family: ui-monospace, monospace; }
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

/* Smooth in-page jumps, but honour reduced-motion. */
html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }

/* Print / Save-as-PDF: drop the interactive chrome, expand answers, keep tiles whole. */
@media print {
  .controls, .id-actions, .answers-filters { display: none !important; }
  #toc, .skip-link { display: none !important; }
  .adj, .expand { display: none !important; }
  .topbar { position: static; }
  .answers-filters { position: static; }
  #report > section.rsec { scroll-margin-top: 0; break-inside: avoid-page; }
  .tiles { overflow: visible; }
  .tile { break-inside: avoid; }
  .ans { max-height: none !important; overflow: visible !important; }
  body { background: #fff; }
}
"""
_STYLE = (
    THEME_CSS_VARS
    + _STYLE_BEFORE_SORT
    + SORTABLE_TABLE_CSS
    + _STYLE_BEFORE_BP
    + BOXPLOT_CSS
    + _STYLE_BEFORE_CHIP
    + CHIP_CSS
    + _STYLE_AFTER_CHIP
)


# Vanilla-JS shell. Reads the inert JSON blob, renders the active run (run select
# swaps the whole <main>), and wires filter/toggle/drag/localStorage/export.
# Markdown/escaping already happened server-side; the JS injects the rendered HTML.
# ChartSearchAI report JS: shared sortable/boxplot + domain shell + theme toggle.
_SCRIPT_PREFIX = r"""
const DATA = JSON.parse(document.getElementById('report-data').textContent);
const RANK_KEY = 'validate-rankings';
// Optional feedback-capture endpoint. Empty = client-side download (default, never blocks). Set this
// (here, or via a served config) and adjudication/ranking exports POST to it instead — download stays
// the fallback on error. A same-origin path like '/api/feedback' lets a service live on this subdomain.
const FEEDBACK_ENDPOINT = '';
let activeRunId = (DATA.runs[0] || {}).run_id;

function runById(id){ return DATA.runs.find(r => r.run_id === id); }
function el(tag, cls){ const e = document.createElement(tag); if(cls) e.className = cls; return e; }

"""
_SCRIPT_MIDDLE = r"""function loadAllRanks(){ try { return JSON.parse(localStorage.getItem(RANK_KEY)) || {}; } catch(e) { return {}; } }
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

// A real run identity for the header, built from the embedded run data instead of a
// constant "Validation report". Leads with the comparison shape (N setups over M
// question sets), then the dataset + patient cohort + date — so the header says what
// THIS run actually was. Counts are derived from the blob; missing pieces are skipped.
function buildTitle(run){
  const m = run.meta || {};
  const nArms = (run.backends || []).length;
  let nQ = 0;
  (run.scenarios || []).forEach(s => { nQ += (s.turns || []).length; });
  const nP = (run.patients || []).length;
  const parts = [];
  if (nArms) parts.push(nArms + ' setup' + (nArms === 1 ? '' : 's'));
  if (nQ) parts.push(nQ + ' question' + (nQ === 1 ? '' : 's'));
  if (nP) parts.push(nP + ' patient' + (nP === 1 ? '' : 's'));
  // "11 setups · 32 questions · 3 patients" — the comparison shape, compactly.
  let title = parts.length ? parts.join(' · ') : 'Validation report';
  return { title: title, dataset: m.dataset_id || '', date: (m.generated_at || '').slice(0, 10) };
}

function renderSummary(run){
  const sec = el('section', 'summary-section');
  sec.innerHTML =
    "<p class='intro'>One row per setup: how many questions it answered, how fast, and how often it cited the chart or fell back. These are operational counts (speed and volume), not a measure of whether the answers were right. Click any column header to sort.</p>";
  const rows = run.summary.map(s =>
    "<tr><td class='b'>" + htmlEsc(armTitle(s.backend_id)) + "<span class='model'>" + htmlEsc(s.backend_id) + "</span></td>" +
    '<td>' + s.turns + '</td><td>' + s.avg_latency_ms + ' ms</td><td>' + s.max_latency_ms + ' ms</td>' +
    '<td>' + s.total_chart_refs + '</td><td>' + s.degraded + '</td><td>' + s.errors + '</td>' +
    '<td>' + (s.temporal_gate_warn || 0) + '</td><td>' + (s.temporal_gate_fail || 0) + '</td>' +
    '<td>' + (s.temporal_gate_applied || 0) + '</td></tr>'
  ).join('');
  const tbl = el('table', 'summary');
  tbl.innerHTML = '<thead><tr><th>backend</th><th>turns</th><th>avg latency</th>' +
    '<th>max latency</th><th>total chart refs</th><th>degraded</th><th>errors</th>' +
    '<th>gate warn</th><th>gate fail</th><th>gate applied</th></tr></thead>' +
    '<tbody>' + rows + '</tbody>';
  sec.appendChild(tbl);
  makeSortable(tbl);
  const stages=[];
  run.summary.forEach(s => Object.keys(s.stage_latency_ms||{}).forEach(k => {
    if(!stages.includes(k)) stages.push(k);
  }));
  if(stages.length){
    const sh=el('h3'); sh.textContent='Average latency by stage'; sec.appendChild(sh);
    const st=el('table','summary');
    st.innerHTML='<thead><tr><th>backend</th>'+stages.map(k=>'<th>'+htmlEsc(k)+'</th>').join('')+'</tr></thead>'+
      '<tbody>'+run.summary.map(s=>'<tr><td class="b">'+htmlEsc(armTitle(s.backend_id))+'</td>'+stages.map(k=>{
        const v=(s.stage_latency_ms||{})[k];
        if(!v) return '<td>—</td>';
        const flags=[];
        if(v.failed) flags.push(v.failed+' failed @ '+v.avg_failed_ms+' ms');
        if(v.cancelled) flags.push(v.cancelled+' cancelled @ '+v.avg_cancelled_ms+' ms');
        const avg=v.avg_ms==null?'—':v.avg_ms+' ms';
        return '<td>'+avg+' ('+v.observed+'/'+v.expected+(flags.length?' · '+flags.join(', '):'')+')</td>';
      }).join('')+'</tr>').join('')+'</tbody>';
    sec.appendChild(st); makeSortable(st);
  }
  return sec;
}

function renderStageTimings(rows){
  if(!rows||!rows.length) return '';
  const body=rows.map(r=>'<tr><td>'+htmlEsc(String(r.stage||'').replaceAll('_',' ')+(r.occurrence>1?' '+r.occurrence:''))+'</td><td>'+r.duration_ms+' ms</td><td>'+htmlEsc(r.status||'completed')+'</td></tr>').join('');
  return '<details class="stage-timings"><summary>stage timing</summary><table class="summary"><thead><tr><th>stage</th><th>elapsed</th><th>status</th></tr></thead><tbody>'+body+'</tbody></table></details>';
}

// Human-readable arm titles for headers/labels — resolved from the active run's arm_cards
// (the model_registry resolver), never the raw dashed backend id. `armTitle` = full title
// ("Liquid coord · Qwen writer · validated"); `armShort` = the tight grid/SVG variant
// (drops " · validated"/" · single"). Fall back to the raw id only if a card is missing.
function armCardFor(b){ const r = runById(activeRunId); return (r && r.arm_cards && r.arm_cards[b]) || null; }
function armTitle(b){ const c = armCardFor(b); return (c && c.title) || b; }
function armShort(b){ const c = armCardFor(b); return (c && (c.short_title || c.title)) || b; }
function bpShort(b){ return armShort(b); }
"""
_SCRIPT_REST = r"""function renderMetrics(run){
  var sec=el('section','metrics-section');
  sec.innerHTML='<p class="intro">How each setup behaves across all the questions, shown as a spread rather than a single number — so you can see typical speed, citation count, and answer length, plus the outliers. Wider boxes mean more variable behaviour.</p>'
   +'<dl class="legend-key">'
   +'<dt>latency</dt><dd>end-to-end response time, in ms.</dd>'
   +'<dt>chart references</dt><dd>resolved chart-reference count per answer — volume metadata, not a quality score.</dd>'
   +'<dt>answer length</dt><dd>characters.</dd>'
   +'</dl>'
   +'<div class="legend-chips" aria-label="how to read a box plot">'
   +'<span class="lk"><b>box</b> middle 50% (q1–q3)</span>'
   +'<span class="lk"><b>solid line</b> median</span>'
   +'<span class="lk"><b>dashed line</b> mean</span>'
   +'<span class="lk"><b>whiskers</b> reach 1.5×IQR</span>'
   +'<span class="lk"><b>○</b> outliers</span>'
   +'<span class="lk"><b>▲</b> clipped, above-axis</span>'
   +'</div>'
   +'<details class="legend-detail"><summary>About the robust axis</summary><div class="legend-body">'
   +'<p>The y-axis is clipped to a robust ceiling (the upper Tukey fence, ≥ the 95th percentile) so one extreme value can\'t squash every box. Points above it are pinned to the top edge as ▲ carets and counted in a footnote, never dropped.</p>'
   +'<p>Successful turns only.</p>'
   +'</div></details>';
  var m=run.metrics||{}, keys=['latency_ms','citation_count','answer_chars'], k, md;
  var grid=el('div','metrics-grid'), any=false;
  for(k=0;k<keys.length;k++){ md=m[keys[k]]; if(md&&md.series&&md.series.length){ grid.appendChild(boxPlotSVG(md.label, md)); any=true; } }
  if(!any){ sec.innerHTML+='<p class="muted">no successful turns to chart yet.</p>'; }
  sec.appendChild(grid);
  return sec;
}

__SHARED_SCORE_FORMATTER__
function renderJudgeCombined(run){
  var rows=(run.judge_combined||[]).slice().filter(function(s){return (s.n_actors||0)>1 && s.benchmark_score!=null;});
  if(!rows.length) return null;
  rows.sort(function(a,b){return (b.benchmark_score||0)-(a.benchmark_score||0);});
  var actorNames=(run.judge_actors||[]).join(', ');
  var h='<div class="judge-consensus"><h3>Reviewer consensus</h3>'
    +'<p class="intro">Combined score averages each scenario × setup across independent judge actors, then averages those cell means per setup. The range shows how far the actor-level arm scores spread; max Δ points to the cell with the largest judge disagreement.</p>'
    +'<table class="summary"><thead><tr><th>backend</th><th>combined Benchmark</th><th>actors</th><th>actor range</th><th>mean Δ/cell</th><th>max Δ cell</th></tr></thead><tbody>';
  h+=rows.map(function(s){
    var ar=s.actor_range||{}, sp=s.benchmark_spread||{};
    var maxCell=s.max_cell_delta_scenario?htmlEsc(s.max_cell_delta_scenario)+' · '+fmt10(s.max_cell_delta):'—';
    return "<tr><td class='b' title='"+htmlEsc(s.backend)+"'>"+htmlEsc(armTitle(s.backend))+"</td>"
      +"<td><b>"+fmt10(s.benchmark_score)+"</b>"+(sp.min==null?'':"<span style='opacity:.55;font-size:.85em'> "+fmt10(sp.min)+"–"+fmt10(sp.max)+"</span>")+"</td>"
      +"<td title='"+htmlEsc(actorNames)+"'>"+(s.n_actors||0)+"</td>"
      +"<td>"+(ar.min==null?'—':fmt10(ar.min)+'–'+fmt10(ar.max))+"</td>"
      +"<td>"+fmt10(s.mean_abs_delta)+"</td>"
      +"<td>"+maxCell+"</td></tr>";
  }).join('');
  h+='</tbody></table></div>';
  var wrap=el('div'); wrap.innerHTML=h;
  var tbl=wrap.querySelector('table'); if(tbl) makeSortable(tbl);
  return wrap;
}
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
  var nActors=(run.judge_actors||[]).length;
  var nPatients=(run.patients||[]).length;
  var patientScope=nPatients===1?'one patient':nPatients+' patients';
  var judgeScope=nActors>1?nActors+' judges':'one judge';
  sec.innerHTML='<p class="intro">The headline: how good each setup’s answers actually were. A strong AI reviewer graded every answer against the patient’s chart for correctness, completeness, and safety. The <b>Benchmark</b> column is the single 0–100 score to compare setups by; the per-scenario heatmap (below) shows it question-by-question. Click any column header to sort. Treat it as directional ('+patientScope+', '+judgeScope+'), not a final grade.'
   +(anyCal?' Where a human reviewer adjudicated cells, a <b>calibrated estimate ± 95% CI</b> sits under the judge number.':'')+'</p>'
   +'<dl class="legend-key">'
   +'<dt>Benchmark</dt><dd>soft 0–100 composite of the answer-only scores (accuracy/completeness weighted highest, minus bounded penalties for unsafe / abstention / citation / temporal flags — no hard gates). Read it with the harm, abstain ✗ and fab-refs counts in the same row, never alone.</dd>'
   +'<dt>accuracy</dt><dd>stated facts correct (0–10).</dd>'
   +'<dt>completeness</dt><dd>includes the needed info (0–10).</dd>'
   +'<dt>relevance</dt><dd>on-question, no padding (0–10).</dd>'
   +'<dt>abstain ✓/✗</dt><dd>correctly said “not documented” vs failed-to-abstain.</dd>'
   +'<dt>grounding s/p/u</dt><dd>supported / partly / unsupported.</dd>'
   +'<dt>harm</dt><dd>answers flagged unsafe by the reviewer.</dd>'
   +'<dt>fab refs</dt><dd>references that don’t resolve to a real chart record (deterministic).</dd>'
   +'<dt>temporal</dt><dd><b>date ✗</b> wrong date↔value or fabricated date · <b>win-over</b> window claimed beyond the data span · <b>trend-fab</b> trend asserted from too few points / wrong direction.</dd>'
   +(anyCal?'<dt>calibrated ± CI</dt><dd>Prediction-Powered Inference: the judge’s cheap score on every cell, bias-corrected by the human-adjudicated subset, with a 95% CI; <b>κ</b> = linearly-weighted judge↔human agreement on the ordinal axes; the <b>tier badge</b> names the most-trusted reviewer (owner → domain → clinician).</dd>':'')
   +'</dl>'
   +'<details class="legend-detail"><summary>How this is scored &amp; what to watch</summary><div class="legend-body">'
   +'<p>Each answer is scored against the patient’s chart by a strong LLM reviewer (advisory). The Benchmark is a soft composite — no single axis hard-gates it.</p>'
   +'<p><b>Caveat:</b> small N, '+patientScope+', '+judgeScope+' — directional, not a benchmark.</p>'
   +'<p><b>Note:</b> product arms are complete med-agent-hub profiles. Differences may include model roles and whether a gather stage is configured; inspect each arm’s configuration before attributing score changes to one factor.</p>'
   +'</div></details>';
  var consensus=renderJudgeCombined(run);
  if(consensus) sec.appendChild(consensus);
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
  tbl.innerHTML='<caption>Canonical judge pass'+(nActors>1?' (currently promoted actor)':'')+'</caption><thead><tr><th>backend</th><th>benchmark'+(anyCal?' <span class="th-sub">+ calibrated ± CI</span>':'')+'</th><th>judged</th><th>acc</th><th>comp</th><th>rel</th><th>abstain ✓/✗</th><th>grounding s/p/u</th><th>harm</th><th>fab refs</th><th>date ✗</th><th>win over</th><th>trend fab</th></tr></thead><tbody>'+rows+'</tbody>';
  sec.appendChild(tbl);
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
  sec.appendChild(judgeBarsSVG(j));
  return sec;
}

// In-Depth — its own parity Benchmark, scored separately from the Answer. Split into
// its own navigable section so the In-Depth axis is co-equal with the Answer headline,
// not buried inside the Quality table. Returns null when no arm shipped an In-Depth.
function renderInDepth(run){
  var j=(run.judge||[]).slice();
  var anyBg=false; for(var b=0;b<j.length;b++){ if((j[b].background||{}).n_background>0){ anyBg=true; break; } }
  if(!anyBg) return null;
  var sec=el('section','indepth-section');
  var bgRows=j.slice().sort(function(a,b){return ((b.background||{}).benchmark_score||0)-((a.background||{}).benchmark_score||0);}).map(function(s){ var bg=s.background||{}, bsp=bg.benchmark_spread||{};
    if(!bg.n_background){ return "<tr><td class='b'>"+htmlEsc(armTitle(s.backend))+"</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>"; }
    return "<tr><td class='b'>"+htmlEsc(armTitle(s.backend))+"</td>"
      +"<td><b>"+fmt10(bg.benchmark_score)+"</b>"+(bsp.min==null?'':"<span style='opacity:.55;font-size:.85em'> "+fmt10(bsp.min)+"–"+fmt10(bsp.max)+"</span>")+"</td>"
      +"<td>"+bg.n_background+"</td>"
      +"<td>"+fmt10(bg.support_mean)+"</td><td>"+fmt10(bg.added_value_mean)+"</td>"
      +"<td>"+(bg.new_harm_count||0)+"</td><td>"+(bg.padded_count||0)+"</td><td>"+(bg.claims_total||0)+"</td></tr>"; }).join('');
  var bgleg=el('div'); bgleg.innerHTML='<p class="intro">Every arm’s separate <b>In Depth</b> elaboration — single-model two-call AND team — scored on its OWN axes so it never inflates or deflates the Answer scores in the Quality section. An arm with no In-Depth shows “—”. Click any column header to sort.</p>'
   +'<dl class="legend-key">'
   +'<dt>In-Depth Benchmark</dt><dd>(support·0.5 + added-value·0.5)·10, minus 15 for an unsafe elaboration and 5 for padding — the In-Depth’s co-equal 0–100 headline.</dd>'
   +'<dt>support</dt><dd>substantiates the answer &amp; chart-grounded (0–10).</dd>'
   +'<dt>added value</dt><dd>useful context beyond the answer (0–10).</dd>'
   +'<dt>unsafe</dt><dd>In-Depth introduced a harm absent from the answer.</dd>'
   +'<dt>padded</dt><dd>bloated, low-signal elaboration.</dd>'
   +'</dl>';
  sec.appendChild(bgleg);
  var bgtbl=el('table','summary'); bgtbl.innerHTML='<thead><tr><th>backend</th><th>In-Depth Benchmark</th><th>In-Depth n</th><th>support</th><th>added value</th><th>unsafe</th><th>padded</th><th>claims</th></tr></thead><tbody>'+bgRows+'</tbody>';
  sec.appendChild(bgtbl); makeSortable(bgtbl);
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
    body.innerHTML = (cell.conf_html || '') + "<div class='ans'>" + cell.answer_html + '</div>' +
                     cell.blocks_html + (cell.sources_html || '') + cell.refs_html;
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
  const timing = el('div');
  timing.innerHTML = renderStageTimings(cell.stage_timings);
  tile.appendChild(timing);

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

  // 3) context/retrieval ownership and policy.
  const r = cfg.retrieval;
  if(r){
    const owner = r.owner || 'historical ChartSearchAI path';
    const fields = Object.entries(r).filter(([key]) => key !== 'owner').map(([key, value]) =>
      key.replaceAll('_', ' ') + ' ' + value
    );
    h += "<div class='ac-h'>context <span class='ac-sub'>(" + htmlEsc(owner) + ")</span></div>";
    h += "<div class='ac-retr'>" + fields.map(htmlEsc).join(' · ') + "</div>";
  }
  h += "</div></details>";
  return h;
}

function renderArms(run){
  const sec = el('section', 'arms-section');
  const cards = run.arm_cards || {};
  let h = "<p class='intro'>Every setup answers the same questions, graded against the patient's chart. " +
       "A <b>single profile</b> uses one writer with configured checks, review, grounding, and In-Depth stages. " +
       "A <b>team profile</b> adds an orchestrator/expert gather stage before the same checked answer path. " +
       "Historical direct-router arms are labeled separately.</p>";
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

// Wrap a render fn's <section> in the consistent, navigable shell: a stable id (the
// scroll-anchor + scrollspy target), a data-nav label (the TOC builds itself from these,
// so an absent section silently drops from the nav), and one consistent numbered <h2> at
// the top. `note` = an optional small de-emphasis tag (e.g. engineering = "operational").
function wrapSection(node, id, navLabel, heading, note){
  if(!node) return null;
  node.id = id;
  node.dataset.nav = navLabel;
  node.classList.add('rsec');
  const h = el('h2');
  h.innerHTML = "<span class='sec-h'>" + htmlEsc(heading) + "</span>" +
    (note ? " <span class='sec-note'>" + htmlEsc(note) + "</span>" : "");
  node.insertBefore(h, node.firstChild);
  return node;
}

// Build the sticky in-page table of contents from the sections actually present, then
// wire a scrollspy that highlights the active section (aria-current='location'). UX
// research favours IntersectionObserver, but a thin trigger band can't account for this
// report's VARIABLE sticky-header height (patient banner + per-run backend toggles), so we
// use a deterministic header-aware position check (rAF-throttled), which also makes the
// top and last-section edge cases trivial. Rebuilt each render (#report re-renders on run
// switch). _spyScroll is kept so a prior listener is removed before re-wiring.
let _spyScroll = null;
function buildNav(){
  const nav = document.getElementById('toc');
  if(!nav) return;
  const secs = [...document.querySelectorAll('#report > section.rsec[data-nav]')];
  nav.innerHTML = '';
  if(_spyScroll){ window.removeEventListener('scroll', _spyScroll); window.removeEventListener('resize', _spyScroll); _spyScroll = null; }
  if(!secs.length){ nav.style.display = 'none'; return; }
  nav.style.display = '';
  const byId = new Map();
  secs.forEach(s => {
    const a = el('a', 'toc-link');
    a.href = '#' + s.id;
    a.textContent = s.dataset.nav;
    a.addEventListener('click', e => {
      e.preventDefault();
      s.scrollIntoView({ behavior: 'smooth', block: 'start' });
      history.replaceState(null, '', '#' + s.id);
    });
    nav.appendChild(a);
    byId.set(s.id, a);
  });
  function setActive(id){ byId.forEach(l => l.removeAttribute('aria-current')); var l=byId.get(id); if(l) l.setAttribute('aria-current','location'); }
  function spy(){
    // The trigger line = just below the live sticky header (measured, not assumed), so the
    // active section flips as its heading clears the header.
    const header = document.querySelector('.topbar');
    const line = (header ? header.getBoundingClientRect().bottom : 0) + 12;
    let active = secs[0].id;
    for(let i=0;i<secs.length;i++){ if(secs[i].getBoundingClientRect().top <= line){ active = secs[i].id; } }
    // bottom-of-page → the last section is "current" even if it never reached the line.
    if(window.innerHeight + window.scrollY >= document.body.scrollHeight - 4){ active = secs[secs.length-1].id; }
    setActive(active);
  }
  let ticking = false;
  _spyScroll = function(){ if(ticking) return; ticking = true; requestAnimationFrame(function(){ spy(); ticking = false; }); };
  window.addEventListener('scroll', _spyScroll, { passive: true });
  window.addEventListener('resize', _spyScroll, { passive: true });
  spy();
}

// Section-local filter bar for the Answers section (UX research: filters sit next to
// the data they affect — Pencil&Paper / LogRocket / Aufait). Holds the scenario <select>,
// the question search, and the multi-select setup filter. Same ids the existing handlers
// (#scenario-filter / #q-search / applyBackendToggle) are wired to — behaviour preserved.
function buildAnswersFilters(run){
  const bar = el('div', 'answers-filters');
  // scenario <select>
  const sLab = el('label'); sLab.htmlFor = 'scenario-filter'; sLab.textContent = 'scenario';
  const sf = el('select'); sf.id = 'scenario-filter';
  sf.innerHTML = "<option value=''>all scenarios</option>" + run.scenarios.map(() => "<option></option>").join('');
  run.scenarios.forEach((s, i) => { const o = sf.options[i + 1]; o.value = s.scenario_id; o.textContent = s.scenario_id; });
  sf.addEventListener('change', applyScenarioFilter);
  bar.appendChild(sLab); bar.appendChild(sf);
  // question search
  const search = el('input'); search.id = 'q-search'; search.type = 'search';
  search.placeholder = 'filter questions… (Esc clears)';
  search.setAttribute('aria-label', 'filter questions');
  search.addEventListener('input', applyQuestionSearch);
  search.addEventListener('keydown', e => { if (e.key === 'Escape'){ search.value = ''; applyQuestionSearch(); } });
  bar.appendChild(search);
  // multi-select setup filter (the scalable replacement for the checkbox toggle list)
  bar.appendChild(buildSetupFilter(run));
  return bar;
}

// "Filter setups ▾" multi-select dropdown — the scalable replacement for the flat
// horizontal checkbox list (UX research: NN/g listbox-vs-dropdown holds many options
// compactly; UX Patterns / Baymard — select-all + clear-all + a count badge for
// reporting filters). A <details> anchors a scrollable checkbox panel; the trigger shows
// an "N of M" badge. Each checkbox drives the SAME applyBackendToggle show/hide as before.
function buildSetupFilter(run){
  const backends = run.backends || [];
  const total = backends.length;
  const wrap = el('details', 'setup-filter');
  const sum = el('summary');
  sum.innerHTML = "Filter setups <span aria-hidden='true'>▾</span> <span id='setup-count' class='setup-count count-badge'></span>";
  wrap.appendChild(sum);
  const panel = el('div', 'setup-panel'); panel.setAttribute('role', 'group'); panel.setAttribute('aria-label', 'Filter setups');
  const acts = el('div', 'setup-panel-acts');
  const allBtn = el('button'); allBtn.type = 'button'; allBtn.className = 'setup-all'; allBtn.textContent = 'Select all';
  const clrBtn = el('button'); clrBtn.type = 'button'; clrBtn.className = 'setup-clear'; clrBtn.textContent = 'Clear all';
  acts.appendChild(allBtn); acts.appendChild(clrBtn);
  panel.appendChild(acts);
  const list = el('div', 'setup-list');
  backends.forEach(b => {
    const lab = el('label');
    const cb = el('input'); cb.type = 'checkbox'; cb.checked = true; cb.value = b; cb.className = 'setup-cb';
    cb.addEventListener('change', () => { applyBackendToggle(b, cb.checked); updateSetupCount(wrap, total); });
    const txt = el('span'); txt.textContent = armShort(b);
    lab.appendChild(cb); lab.appendChild(txt); lab.title = b;
    list.appendChild(lab);
  });
  panel.appendChild(list);
  wrap.appendChild(panel);
  // select-all / clear-all flip every checkbox + re-apply (the count badge follows).
  function setAll(on){
    list.querySelectorAll('input.setup-cb').forEach(cb => { cb.checked = on; applyBackendToggle(cb.value, on); });
    updateSetupCount(wrap, total);
  }
  allBtn.addEventListener('click', () => setAll(true));
  clrBtn.addEventListener('click', () => setAll(false));
  // dismiss on outside-click / Escape (standard disclosure affordance). The document
  // listener no-ops once this filter is detached (run switch re-renders the bar), so a
  // stale closure from a prior render can't act on the live one.
  document.addEventListener('click', e => { if (wrap.isConnected && wrap.open && !wrap.contains(e.target)) wrap.open = false; });
  wrap.addEventListener('keydown', e => { if (e.key === 'Escape' && wrap.open){ wrap.open = false; sum.focus(); } });
  updateSetupCount(wrap, total);
  return wrap;
}
function updateSetupCount(wrap, total){
  const on = wrap.querySelectorAll('input.setup-cb:checked').length;
  const badge = wrap.querySelector('#setup-count');
  if (badge){ badge.textContent = on + ' of ' + total; badge.classList.toggle('partial', on < total); }
}

function renderRun(runId){
  const run = runById(runId);
  if (!run) return;
  // Header identity: the data-derived comparison-shape title + a one-line run sub-label
  // (dataset · date), with the full technical provenance kept as the element's tooltip.
  const t = buildTitle(run);
  const ttl = document.getElementById('report-title');
  if (ttl) ttl.textContent = t.title;
  const sub = [t.dataset, t.date].filter(Boolean).join('  ·  ');
  const meta = document.getElementById('run-meta');
  meta.textContent = sub;
  meta.title = renderRunMeta(run);

  const main = document.getElementById('report');
  main.innerHTML = '';
  const pbanner = renderPatientBanner(run);
  if (pbanner) main.appendChild(pbanner);

  // 1) Arms — what this run compares
  main.appendChild(wrapSection(renderArms(run), 'sec-arms', 'Arms', 'What this run compares'));
  // 2) Quality — the headline judge scores
  const judge = wrapSection(renderJudge(run), 'sec-quality', 'Quality', 'Quality — reviewer judgment (Scout rubric)');
  if (judge) main.appendChild(judge);
  // 3) In-Depth — its own co-equal Benchmark
  const indepth = wrapSection(renderInDepth(run), 'sec-indepth', 'In-Depth', 'In-Depth — its own parity Benchmark');
  if (indepth) main.appendChild(indepth);

  // 4) Per-scenario heatmap — the scenario × setup colour grid, now its OWN navigable
  // section (split from the answer tiles so each is independently reachable in the nav).
  const hm = judgeHeatmap(run);
  if (hm){
    const hmSec = el('section', 'heatmap-wrap');
    const hmIntro = el('p', 'intro');
    hmIntro.textContent = 'Every scenario × setup at a glance (green = accurate, amber, red) — click a cell to read the reviewer’s note. The full side-by-side answers are in the next section.';
    hmSec.appendChild(hmIntro);
    hmSec.appendChild(hm);
    main.appendChild(wrapSection(hmSec, 'sec-heatmap', 'Heatmap', 'Per-scenario heatmap'));
  }

  // 5) Per-scenario answers — the side-by-side answer tiles, its own navigable section
  // with a SECTION-LOCAL filter bar (scenario / question / setups) adjacent to the data
  // it filters (UX research: component-level filters belong next to discrepant sections).
  const scenSec = el('section', 'scenario-wrap');
  const scenIntro = el('p', 'intro');
  scenIntro.textContent = 'The actual answers, one column per setup, lined up question-by-question so you can read them side by side. Drag a tile to rank the setups; click ⛶ to read one full-screen. Use the filters below to narrow to a scenario, search questions, or hide setups.';
  scenSec.appendChild(scenIntro);
  scenSec.appendChild(buildAnswersFilters(run));
  run.scenarios.forEach(sc => {
    const sec = el('section', 'scenario');
    sec.dataset.scenario = sc.scenario_id;
    const h = el('h3', 'scenario-h'); h.textContent = sc.scenario_id; sec.appendChild(h);

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
    scenSec.appendChild(sec);
  });
  main.appendChild(wrapSection(scenSec, 'sec-answers', 'Answers', 'Per-scenario answers'));

  // 5) Engineering metrics — UN-HIDDEN (was a <details> collapse). Operational, not answer
  // quality, so it lives last and reads de-emphasized, but it's always visible + in the nav.
  const eng = el('section', 'eng-section');
  const engIntro = el('p', 'intro');
  engIntro.innerHTML = 'Operational behaviour, <b>not</b> answer quality: how fast each setup responded, how many chart records it cited, and how often it errored or fell back. Useful for cost/latency trade-offs, but it does not say whether the answers were right — that’s the Quality section.';
  eng.appendChild(engIntro);
  eng.appendChild(renderSummary(run));
  eng.appendChild(renderMetrics(run));
  main.appendChild(wrapSection(eng, 'sec-engineering', 'Engineering', 'Engineering metrics', 'operational, not answer quality'));

  buildNav();
  applyFilters();
}

/* ---- filter + toggle (attribute flips, no re-render) ----
   The scenario / question controls now live in the section-local Answers filter bar
   (rebuilt each render), so the lookups are null-guarded for the pre-render call. */
function applyScenarioFilter(){
  const sel = document.getElementById('scenario-filter'); if (!sel) return;
  const v = sel.value;
  document.querySelectorAll('#report .scenario').forEach(sec => {
    sec.dataset.hidden = (v && sec.dataset.scenario !== v) ? '1' : '0';
  });
}
function applyQuestionSearch(){
  const inp = document.getElementById('q-search'); if (!inp) return;
  const raw = inp.value.trim();
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
  // Setup show/hide now driven by the section-local multi-select checkboxes.
  document.querySelectorAll('.setup-filter input.setup-cb').forEach(cb => applyBackendToggle(cb.value, cb.checked));
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

/* ---- cross-run switcher ----
   Swaps between PUBLISHED runs. A published report lives at <reports>/<slug>/index.html,
   so its siblings + the curated reports-index.json are one level up. Fetch ../reports-index.json
   at runtime, list each run (slug → title), mark the current one (its slug = this report's
   parent dir), and navigate to ../<slug>/ on select. Graceful degradation: any fetch failure
   (a local file:// open, or the index absent — e.g. an un-published render) leaves the control
   hidden, so it is never a dead single-option select. */
function currentSlug(){
  // .../<slug>/  or  .../<slug>/index.html  → the slug is the parent dir of index.html
  var parts = location.pathname.split('/').filter(Boolean);
  if (!parts.length) return '';
  var last = parts[parts.length - 1];
  return (/\.html?$/i.test(last) || last === '') ? (parts[parts.length - 2] || '') : last;
}
function loadRunSwitcher(){
  var box = document.getElementById('run-switcher');
  var sel = document.getElementById('run-switcher-sel');
  if (!box || !sel) return;
  fetch('../reports-index.json', { cache: 'no-store' })
    .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function(idx){
      var runs = (idx && idx.runs) || [];
      if (!runs.length) throw new Error('no runs');
      var here = currentSlug();
      sel.innerHTML = '';
      runs.forEach(function(run){
        if (!run || !run.slug) return;
        var o = document.createElement('option');
        o.value = run.slug;
        var current = run.slug === here;
        o.textContent = (current ? '● ' : '') + (run.title || run.slug);
        if (current) o.selected = true;
        sel.appendChild(o);
      });
      if (!sel.options.length) throw new Error('no slugs');
      sel.addEventListener('change', function(){ if (sel.value) location.href = '../' + sel.value + '/'; });
      box.classList.add('ready');   // reveal only once it's a real, populated switcher
      syncTopbarHeight();
    })
    .catch(function(){ /* graceful degradation — leave the control hidden */ });
}

/* ---- boot ---- */
// Keep the section-local sticky filter bar tucked just under the live topbar (its height
// varies with the patient banner + toc), exposed as a CSS var the bar's `top` reads.
function syncTopbarHeight(){
  var tb = document.querySelector('.topbar');
  if (tb) document.documentElement.style.setProperty('--topbar-h', tb.getBoundingClientRect().height + 'px');
}
function boot(){
  // Embedded multi-run selector: only relevant (and only shown) when this single file
  // carries more than one run. The cross-run switcher above handles the published case.
  const rs = document.getElementById('run-select');
  const rsWrap = document.getElementById('run-select-wrap');
  if (rs){
    rs.innerHTML = DATA.runs.map(() => '<option></option>').join('');
    DATA.runs.forEach((r, i) => { const o = rs.options[i]; o.value = r.run_id; o.textContent = r.run_id; });
    rs.value = activeRunId;
    rs.addEventListener('change', () => { activeRunId = rs.value; renderRun(activeRunId); syncTopbarHeight(); });
    if (rsWrap && DATA.runs.length > 1) rsWrap.hidden = false;
  }

  document.getElementById('reset-rank').addEventListener('click', resetRanking);
  document.getElementById('export-rankings').addEventListener('click', exportRankings);
  document.getElementById('export-feedback').addEventListener('click', collectFeedback);
  document.getElementById('print-pdf').addEventListener('click', () => window.print());

  // Overflow menu: dismiss on outside-click / Escape, and collapse after a menu action
  // fires (standard menu affordance — the panel is a <details>, so toggling `open` works).
  const exMenu = document.getElementById('export-menu');
  if (exMenu){
    document.addEventListener('click', e => { if (exMenu.open && !exMenu.contains(e.target)) exMenu.open = false; });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && exMenu.open) exMenu.open = false; });
    exMenu.querySelectorAll('.menu-item').forEach(b => b.addEventListener('click', () => { exMenu.open = false; }));
  }

  loadRunSwitcher();
  if (activeRunId) renderRun(activeRunId);
  syncTopbarHeight();
  window.addEventListener('resize', syncTopbarHeight);
}
boot();
"""
_SCRIPT = (
    _SCRIPT_PREFIX
    + SORTABLE_TABLE_JS
    + _SCRIPT_MIDDLE
    + BOXPLOT_JS
    + _SCRIPT_REST
    + theme_toggle_js("oc-theme-report")
    + "\n"
)
_SCRIPT = _SCRIPT.replace("__SHARED_SCORE_FORMATTER__", score_formatter_js())


def _embed_json(blob: dict[str, Any]) -> str:
    """Serialise the blob and neutralise the three chars that could break out of
    the <script type="application/json"> element (a model answer containing
    </script> must not escape). \\uXXXX escapes are JSON-valid, so JSON.parse
    reverses them transparently."""
    s = json.dumps(blob, ensure_ascii=False)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _document(blob: dict[str, Any]) -> str:
    legend = (
        "<div class='legend'>"
        "<p class='legend-group-h'>Per-tile deterministic chips · no LLM judge</p>"
        "<dl class='legend-key'>"
        "<dt>⏱ latency</dt><dd>end-to-end response time; <b>orange</b> = first turn per backend (carries model warmup).</dd>"
        "<dt>chart refs</dt><dd>count of chart records cited — a COUNT, not a grounding/quality signal; the authoritative call is the human adjudication on each tile.</dd>"
        "<dt>not surfaced</dt><dd>tokens / finish_reasons / response model — not returned by <code>/chat</code> (OTel-deferred).</dd>"
        "<dt>ranking</dt><dd>drag tiles within a question to rank backends; rank + adjudication export to separate files.</dd>"
        "</dl></div>"
    )
    first = (blob.get("runs") or [{}])[0]
    _ds = (first.get("meta") or {}).get("dataset_id")
    title = " · ".join(p for p in (_ds, first.get("run_id")) if p)
    body = (
        "<header class='topbar'>"
        # Identity band: the data-derived run title (JS fills #report-title from the
        # blob) on the left; the readily-accessible primary actions (PDF, theme) +
        # the subdued export overflow on the right. The run sub-line (dataset/git/date)
        # sits under the title as muted meta.
        "<div class='topbar-id'>"
        "<div class='id-main'>"
        "<h1 id='report-title'>Validation report</h1>"
        "<div id='run-meta' class='meta'></div>"
        "</div>"
        "<div class='id-actions'>"
        # Run-switcher: swaps between PUBLISHED runs (fetched from the sibling
        # reports-index.json at runtime → navigate to ../<slug>/). Hidden until that
        # fetch succeeds (graceful degradation for a local file:// open / absent index)
        # so it is never a dead control. The current run is marked in the option list.
        "<span id='run-switcher' class='run-switcher'>"
        "<label for='run-switcher-sel'>view run</label>"
        "<select id='run-switcher-sel' aria-label='Switch to another published run'></select>"
        "</span>"
        "<button id='print-pdf' class='btn-ghost' title='print / save as PDF'>Download PDF</button>"
        "<button id='theme-toggle' class='btn-ghost btn-icon' type='button' title='Toggle light / dark' aria-label='Toggle light or dark mode'></button>"
        # Overflow menu (progressive disclosure): the rarely-used human-feedback /
        # adjudication exports + the reviewer-email input, grouped behind one subdued
        # "Export ▾" trigger so they don't dominate the header. Ids preserved — the
        # drag-to-rank + adjudication machinery is wired to them unchanged.
        "<details id='export-menu' class='overflow'>"
        "<summary class='btn-ghost' title='Reviewer exports — rankings & adjudication feedback'>Export <span aria-hidden='true'>▾</span></summary>"
        "<div class='overflow-panel' role='menu'>"
        "<p class='overflow-h'>Reviewer exports</p>"
        "<button id='export-rankings' class='menu-item'>Export rankings.json</button>"
        "<button id='export-feedback' class='menu-item'>Download feedback.jsonl</button>"
        "<button id='reset-rank' class='menu-item' title='restore default backend order'>Reset ranking</button>"
        "<label class='menu-field'>Reviewer <input id='rev' placeholder='you@example.org'></label>"
        "</div>"
        "</details>"
        "</div>"
        "</div>"
        # Page-level controls row: ONLY the embedded multi-run selector (when this single
        # file carries >1 run). The scenario / question / setup filters affect just the
        # Answers section, so they moved there (see #answers-filters). `.controls:empty`
        # hides this row entirely in the common single-run case.
        "<div class='controls'>"
        "<label id='run-select-wrap' hidden>run <select id='run-select'></select></label>"
        "</div>"
        "<nav id='toc' aria-label='On this page'></nav>"
        "</header>"
        "<a class='skip-link' href='#report'>Skip to report</a>"
        "<main id='report'></main>"
        "<div id='sort-live' class='sr-only' aria-live='polite'></div>"
        f"<template id='rubric-template'>{_RUBRIC_FORM}</template>"
        f"{legend}"
    )
    return render_document(
        title=f"validation report · {_esc(title)}",
        body_html=body,
        embedded_data=blob,
        style=_STYLE,
        script=_SCRIPT,
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
