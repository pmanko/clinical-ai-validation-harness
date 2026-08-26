"""Human-readable, full-evidence report for the Phase 1 model-team comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.common.text import esc
from harness.report_shell.assets import (
    SHARED_CSS,
    SHARED_JS,
    SHARED_JS_DEPS,
    THEME_TOGGLE_BUTTON_HTML,
    theme_toggle_js,
)
from harness.report_shell.document import render_document

from .phase1_evidence import case_records, collection_summary, load_json
from .notebook_validation import validate_notebook_evidence
from .reader_review import prepare_reader_review, validate_reader_reviews

_STYLE = (
    SHARED_CSS
    + """
body { font-family:ui-sans-serif,system-ui,sans-serif; margin:0; background:var(--bg); color:var(--fg); }
header.topbar { display:flex; justify-content:space-between; gap:16px; padding:18px 24px; border-bottom:1px solid var(--line); background:var(--surface); }
header.topbar h1 { margin:0; font-size:21px; }
main { max-width:1280px; padding:20px 24px 56px; }
section { margin:24px 0; }
h2 { font-size:17px; margin:0 0 10px; }
h3 { font-size:15px; }
.meta,.muted { color:var(--mut); font-size:12px; }
.note { border:1px solid var(--line); background:var(--note-bg); border-radius:8px; padding:10px 12px; }
.case { border:1px solid var(--line); background:var(--surface); border-radius:10px; padding:12px 14px; margin:10px 0; }
.turn { border-top:1px solid var(--line); margin-top:10px; padding-top:8px; }
.ok { color:#087f5b; font-weight:600; }
.different { color:var(--err); font-weight:600; }
.unknown { color:var(--mut); font-weight:600; }
table.data { width:100%; border-collapse:collapse; background:var(--surface); font-size:13px; }
table.data th,table.data td { border:1px solid var(--line); padding:7px 8px; vertical-align:top; text-align:left; }
table.data th { background:var(--surface2); }
pre { white-space:pre-wrap; overflow-wrap:anywhere; background:var(--surface2); border:1px solid var(--line); border-radius:6px; padding:9px; font-size:12px; }
details { margin:7px 0; }
details > summary { cursor:pointer; }
.review { border-left:4px solid var(--accent); padding-left:12px; }
.links a { margin-right:10px; }
.sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
"""
)

_SCRIPT = SHARED_JS_DEPS + SHARED_JS + theme_toggle_js("oc-theme-report") + """
document.querySelectorAll('table.data').forEach(makeSortable);
"""


def _pretty(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str)


def _profile_label(profile_id: str, suite: dict[str, Any]) -> str:
    profile = (suite.get("profiles") or {}).get(profile_id) or {}
    writer = profile.get("writerModelId") or "unknown writer"
    reviewer = profile.get("reviewerModelId")
    return (
        f"{writer} writer + {reviewer} checker"
        if reviewer
        else f"{writer} writer only"
    )


def _turn_fact(turn: dict[str, Any]) -> tuple[str, str]:
    expected = str(turn.get("expectedOutcome") or "")
    observed = str(turn.get("observedOutcome") or "")
    answer_check = (turn.get("evidence") or {}).get("independentAnswerCheck")
    execution = (turn.get("evidence") or {}).get("execution") or {}
    if isinstance(answer_check, dict) and answer_check:
        if answer_check.get("passed") is True:
            return "database answer matched", "ok"
        if answer_check.get("passed") is False:
            return "database answer differed", "different"
    if isinstance(execution, dict) and execution:
        status = execution.get("status")
        if status and status != "succeeded":
            return f"PostgreSQL returned {status}", "different"
    if expected and observed:
        if expected == observed:
            return "outcome was as expected", "ok"
        return f"expected {expected}; observed {observed}", "different"
    return "no automated factual conclusion", "unknown"


def _matrix_cell(record: dict[str, Any]) -> str:
    turns = record.get("turns") or []
    expected = sum(
        str(turn.get("expectedOutcome") or "")
        == str(turn.get("observedOutcome") or "")
        for turn in turns
    )
    checked = 0
    matched = 0
    diagnostics = 0
    for turn in turns:
        evidence = turn.get("evidence") or {}
        answer_check = evidence.get("independentAnswerCheck")
        if isinstance(answer_check, dict) and answer_check:
            checked += 1
            matched += answer_check.get("passed") is True
        execution = evidence.get("execution") or {}
        if isinstance(execution, dict) and execution.get("status") not in {
            None,
            "succeeded",
        }:
            diagnostics += 1
    validity = (
        "evidence complete"
        if record.get("measurementValid") is True
        else "evidence incomplete"
    )
    cls = "ok" if record.get("measurementValid") is True else "different"
    bits = [f"<span class='{cls}'>{esc(validity)}</span>"]
    bits.append(f"<div>{expected}/{len(turns)} expected outcomes</div>")
    if checked:
        bits.append(f"<div>{matched}/{checked} database answers matched</div>")
    if diagnostics:
        bits.append(f"<div>{diagnostics} database diagnostic(s)</div>")
    return "".join(bits)


def _matrix(suite: dict[str, Any], records: list[dict[str, Any]]) -> str:
    teams = [str(value) for value in suite.get("comparisonProfiles") or []]
    scenarios = [
        str(item.get("id"))
        for item in suite.get("scenarios") or []
        if isinstance(item, dict) and item.get("id")
    ]
    by_key = {
        (str(record.get("profileId")), str(record.get("scenarioId"))): record
        for record in records
    }
    heads = "".join(
        f"<th>{esc(_profile_label(team, suite))}<div class='meta'>{esc(team)}</div></th>"
        for team in teams
    )
    rows = []
    for scenario in scenarios:
        cells = []
        for team in teams:
            record = by_key.get((team, scenario))
            cells.append(f"<td>{_matrix_cell(record) if record else 'missing'}</td>")
        rows.append(f"<tr><th>{esc(scenario)}</th>{''.join(cells)}</tr>")
    return (
        "<table class='data'><thead><tr><th>scenario</th>"
        f"{heads}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _evidence_details(turn: dict[str, Any]) -> str:
    chunks: list[str] = []
    for label, title in (
        ("validation", "Advisory validator"),
        ("execution", "PostgreSQL result or diagnostic"),
        ("postgresCrosscheck", "Independent execution cross-check"),
        ("independentAnswerCheck", "Question-specific database answer check"),
        ("generation", "Model context, calls, tokens, and exact requests"),
    ):
        value = (turn.get("evidence") or {}).get(label)
        if value is None:
            continue
        chunks.append(
            f"<details><summary>{esc(title)}</summary>"
            f"<pre>{esc(_pretty(value))}</pre></details>"
        )
    links = turn.get("evidencePaths") or {}
    if links:
        anchors = "".join(
            f"<a href='{esc(path)}'>{esc(label)}</a>"
            for label, path in sorted(links.items())
        )
        chunks.append(f"<div class='links meta'>Raw evidence: {anchors}</div>")
    return "".join(chunks)


def _case_card(record: dict[str, Any], suite: dict[str, Any]) -> str:
    profile_id = str(record.get("profileId") or "")
    turns_html: list[str] = []
    for turn in record.get("turns") or []:
        fact, fact_class = _turn_fact(turn)
        sql = turn.get("sql")
        retained_sql = turn.get("retainedSql")
        answer = turn.get("answerText")
        response = ""
        if answer:
            response += f"<p><b>Writer text:</b> {esc(answer)}</p>"
        if sql:
            response += (
                "<details open><summary>Newly selected SQL</summary>"
                f"<pre>{esc(sql)}</pre></details>"
            )
        if retained_sql:
            response += (
                "<details><summary>Prior SQL still in the editor — not generated "
                "by this turn</summary>"
                f"<pre>{esc(retained_sql)}</pre></details>"
            )
        turns_html.append(
            "<div class='turn'>"
            f"<h3>Turn {esc(turn.get('turn'))}</h3>"
            f"<p><b>User:</b> {esc(turn.get('instruction'))}</p>"
            f"<p><b>Outcome:</b> expected {esc(turn.get('expectedOutcome'))}; "
            f"observed {esc(turn.get('observedOutcome'))} · "
            f"<span class='{fact_class}'>{esc(fact)}</span></p>"
            f"{response}{_evidence_details(turn)}</div>"
        )
    return (
        "<article class='case'>"
        f"<h3>{esc(record.get('scenarioId'))} · "
        f"{esc(_profile_label(profile_id, suite))}</h3>"
        f"<div class='meta'>{esc(profile_id)} · {esc(record.get('family'))} · "
        f"evidence {'complete' if record.get('measurementValid') else 'incomplete'}</div>"
        f"{''.join(turns_html)}</article>"
    )


def _reviews(run_dir: Path) -> str:
    review_dir = run_dir / "reader-reviews"
    if not review_dir.is_dir():
        return (
            "<div class='note'>No reader review has been attached yet. The "
            "report still exposes all factual evidence; a chosen reviewer "
            "should receive <code>reader-review-input.json</code>.</div>"
        )
    chunks: list[str] = []
    for path in sorted(review_dir.glob("*.md")):
        meta = load_json(path.with_suffix(".json"))
        identity = " · ".join(
            str(meta.get(key))
            for key in ("reviewer", "provider", "model", "modelVersion", "reviewedAt")
            if meta.get(key)
        )
        chunks.append(
            "<article class='review'>"
            f"<h3>{esc(path.stem)}</h3>"
            f"<div class='meta'>{esc(identity)}</div>"
            f"<pre>{esc(path.read_text(encoding='utf-8'))}</pre>"
            "</article>"
        )
    return "".join(chunks) or "<div class='note'>Reader-review directory is empty.</div>"


def build_phase1_report(run_dir: Path | str) -> Path:
    run_dir = Path(run_dir)
    suite = load_json(run_dir / "suite.json")
    results = load_json(run_dir / "results.json")
    manifest = load_json(run_dir / "run_manifest.json")
    prepare_reader_review(run_dir)
    validate_reader_reviews(run_dir)
    evidence_index = validate_notebook_evidence(run_dir)
    records = case_records(
        run_dir,
        suite=suite,
        results=results,
        evidence_index=evidence_index,
    )
    collection = collection_summary(suite, results)
    collection_class = "ok" if collection["complete"] else "different"
    case_html = "".join(_case_card(record, suite) for record in records)
    body = (
        "<header class='topbar'><div>"
        "<h1>Catalyst Phase 1 model-team comparison</h1>"
        f"<div class='meta'>run {esc(results.get('runId') or manifest.get('run_id'))} · "
        f"suite {esc(suite.get('id'))} · dataset {esc(manifest.get('dataset_id'))} · "
        f"catalog {esc(results.get('catalogVersion'))}</div>"
        "</div>"
        f"{THEME_TOGGLE_BUTTON_HTML}</header><main>"
        "<section><h2>What this report does</h2>"
        "<p>This is an exploratory comparison of three complete model setups. "
        "Automated checks establish what happened; they do not rank teams or "
        "choose a winner. Wrong queries and database errors remain visible as "
        "model results.</p>"
        f"<p class='{collection_class}'>Collection: "
        f"{esc(collection['recordedConversations'])}/"
        f"{esc(collection['expectedConversations'])} conversations · "
        f"{'complete' if collection['complete'] else 'needs attention'}</p>"
        + (
            f"<pre>{esc(_pretty(collection))}</pre>"
            if not collection["complete"]
            else ""
        )
        + "</section><section><h2>Side-by-side factual observations</h2>"
        "<p class='muted'>These counts summarize expected outcomes and "
        "question-specific database checks. They are not acceptance thresholds.</p>"
        f"{_matrix(suite, records)}</section>"
        "<section><h2>Reader review</h2>"
        f"{_reviews(run_dir)}</section>"
        "<section><h2>Complete case evidence</h2>"
        f"{case_html}</section>"
        "<section><h2>Provenance</h2><div class='links'>"
        "<a href='run_manifest.json'>run manifest</a>"
        "<a href='suite.json'>frozen suite</a>"
        "<a href='run-config.json'>run configuration</a>"
        "<a href='reader-review-input.json'>reader-review input</a>"
        "<a href='evidence-index.json'>evidence index</a>"
        "</div></section></main>"
        "<div id='sort-live' class='sr-only' aria-live='polite'></div>"
    )
    html = render_document(
        title="Catalyst Phase 1 model-team comparison",
        body_html=body,
        style=_STYLE,
        script=_SCRIPT,
        theme_storage_key="oc-theme-report",
        embedded_data={"collection": collection, "suiteId": suite.get("id")},
    )
    out = run_dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out
