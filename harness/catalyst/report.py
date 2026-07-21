"""Offline Catalyst notebook validation report (report family: catalyst)."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from harness.common.jsonl import read_jsonl
from harness.common.text import esc
from harness.catalyst.reconcile import merge_gold_and_judge
from harness.report_shell.assets import (
    SHARED_CSS,
    SHARED_JS,
    THEME_TOGGLE_BUTTON_HTML,
    theme_toggle_js,
)
from harness.report_shell.document import render_document

_STYLE = (
    SHARED_CSS
    + """
body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: var(--bg); color: var(--fg); }
header.topbar { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; padding:18px 24px; border-bottom:1px solid var(--line); background: var(--surface); }
header.topbar h1 { margin:0; font-size:20px; }
.meta { color: var(--mut); font-size: 12px; margin-top: 4px; }
main { padding: 18px 24px 48px; max-width: 1200px; }
section { margin: 22px 0; }
h2 { font-size: 16px; margin: 0 0 10px; }
table.data { width:100%; border-collapse:collapse; font-size:13px; background:var(--surface); }
table.data th, table.data td { border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
table.data th { background: var(--surface2); }
.pass { color: #0a7; font-weight: 600; }
.fail { color: var(--err); font-weight: 700; }
.adv { color: var(--mut); font-size: 12px; }
.note { background: var(--note-bg); border:1px solid var(--line); padding:10px 12px; border-radius:8px; font-size:13px; }
pre.diff, pre.sql, pre.rationale { white-space: pre-wrap; font-family: ui-monospace, monospace; font-size: 12px; background: var(--surface2); border:1px solid var(--line); padding:10px; border-radius:8px; }
a.ev { color: var(--accent); }
.chip-fail { display:inline-block; background:#a01; color:#fff; font-size:11px; padding:1px 6px; border-radius:3px; }
.chip-pass { display:inline-block; background:#0a7; color:#fff; font-size:11px; padding:1px 6px; border-radius:3px; }
"""
)

_SCRIPT = SHARED_JS + theme_toggle_js("oc-theme-report") + """
document.querySelectorAll('table.data').forEach(makeSortable);
"""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _rstrip_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines()]


def unified_sql_diff(before: str, after: str, *, fromfile: str, tofile: str) -> str:
    """Line-level unified diff; strip trailing whitespace per line, keep boundaries."""
    return "\n".join(
        difflib.unified_diff(
            _rstrip_lines(before),
            _rstrip_lines(after),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )


def _extract_sql(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.suffix == ".sql":
        return path.read_text(encoding="utf-8")
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(blob.get("sql"), str):
        return blob["sql"]
    body = ((blob.get("response") or {}).get("body")) or {}
    if isinstance(body.get("sql"), str):
        return body["sql"]
    req = ((blob.get("request") or {}).get("body")) or {}
    if isinstance(req.get("sql"), str):
        return req["sql"]
    return None


def _scenario_sql_versions(run_dir: Path, scenario_id: str) -> list[tuple[str, str]]:
    """Return ordered (label, sql) pairs discovered under the scenario evidence tree."""
    root = run_dir / "scenarios" / scenario_id
    if not root.exists():
        return []
    candidates: list[tuple[int, str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".json", ".sql"}:
            continue
        if "version" not in path.name and "save-base-version" not in path.name and path.suffix != ".sql":
            # Prefer explicit version artifacts and top-level SQL files.
            if path.name not in {"01-base-sql.sql", "02-successor-sql.sql"}:
                continue
        sql = _extract_sql(path)
        if not sql:
            continue
        # Ordinal hint from filename for stable ordering.
        ordinal = 50
        name = path.name
        if "base" in name or name.startswith("01-"):
            ordinal = 1
        elif "version-01" in name or name == "version-01.json":
            ordinal = 2
        elif "version-02" in name or name == "version-02.json" or "successor" in name:
            ordinal = 3
        rel = path.relative_to(run_dir).as_posix()
        candidates.append((ordinal, rel, sql))
    candidates.sort(key=lambda t: (t[0], t[1]))
    # Deduplicate identical consecutive SQL.
    out: list[tuple[str, str]] = []
    for _, rel, sql in candidates:
        if out and out[-1][1] == sql:
            continue
        out.append((rel, sql))
    return out


def _judge_index(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    idx: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        idx[(str(row["scenario_id"]), int(row["turn"]))] = row
    return idx


def _gold_passed(assertions: list[dict[str, Any]]) -> bool:
    gold = [
        a
        for a in assertions
        if "gold_execution_match" in str(a.get("name", ""))
    ]
    if not gold:
        return all(bool(a.get("passed")) for a in assertions)
    return all(bool(a.get("passed")) for a in gold)


def _assertion_fail_details(
    run_dir: Path,
    scenario_id: str,
    assertion: dict[str, Any],
) -> str:
    evidence = assertion.get("evidence")
    rationale = ""
    rel: str | None = None
    if isinstance(evidence, dict):
        rationale = str(
            evidence.get("mismatch_rationale") or evidence.get("rationale") or ""
        )
        path_val = evidence.get("path")
        if isinstance(path_val, str):
            rel = path_val
    name = str(assertion.get("name") or "")
    if not rel and "gold_execution_match" in name:
        stem = (
            "15-gold-execution-match-base.json"
            if "base_" in name
            else "16-gold-execution-match-successor.json"
        )
        candidate = f"scenarios/{scenario_id}/repetition-01/{stem}"
        if (run_dir / candidate).exists():
            rel = candidate
    chunks: list[str] = []
    if rel:
        abs_path = run_dir / rel
        if abs_path.exists() and abs_path.suffix == ".json":
            blob = _load_json(abs_path)
            file_rationale = blob.get("mismatch_rationale")
            if file_rationale:
                rationale = str(file_rationale)
        chunks.append(f'<a class="ev" href="{esc(rel)}">{esc(rel)}</a>')
    if rationale:
        chunks.insert(0, esc(rationale))
    return "<br>".join(chunks) if chunks else ""


def _render_judge_block(row: dict[str, Any] | None) -> str:
    if row is None:
        return '<span class="adv">Judge not available</span>'
    axes = [
        "intent_fidelity",
        "sql_quality",
        "schema_discipline",
        "followup_coherence",
    ]
    bits = [
        f"<div><b>advisory composite</b>: {esc(row.get('composite'))}</div>",
        "<ul>",
    ]
    for axis in axes:
        if axis not in row:
            continue
        rationale = row.get(f"{axis}_rationale", "")
        bits.append(
            f"<li><code>{esc(axis)}</code>={esc(row.get(axis))} — {esc(rationale)}</li>"
        )
    bits.append("</ul>")
    paths = row.get("evidence_paths") or []
    if paths:
        bits.append("<div class='adv'>evidence: ")
        bits.append(
            ", ".join(
                f'<a class="ev" href="{esc(p)}">{esc(p)}</a>' for p in paths
            )
        )
        bits.append("</div>")
    return "".join(bits)


def _build_body(run_dir: Path, blob: dict[str, Any]) -> str:
    manifest = blob["manifest"]
    suite = blob["suite"]
    results = blob["results"]
    judges = blob["judges"]
    jidx = _judge_index(judges)

    suite_id = suite.get("id") or results.get("suiteId") or manifest.get("run_id")
    title = f"Catalyst notebook report · {suite_id}"
    meta_bits = [
        f"run_id={manifest.get('run_id')}",
        f"evidence_status={manifest.get('evidence_status', 'development')}",
        f"dataset={manifest.get('dataset_id')}",
        f"catalog={suite.get('catalogVersion') or manifest.get('schema_mapping_version')}",
        f"provider={suite.get('providerName') or (manifest.get('otel') or {}).get('gen_ai.provider.name')}",
    ]
    profiles = suite.get("profiles") or {}
    if profiles:
        meta_bits.append("profiles=" + ",".join(sorted(profiles)))

    rows_html: list[str] = []
    for row in results.get("results") or []:
        sid = row["scenarioId"]
        assertions = row.get("assertions") or []
        gold_ok = _gold_passed(assertions)
        judge0 = jidx.get((sid, 0))
        judge1 = jidx.get((sid, 1))
        merged = merge_gold_and_judge(gold_passed=gold_ok, judge_row=judge0 or judge1)
        verdict = merged["reported"]
        v_cls = "pass" if verdict == "PASS" else "fail"
        fail_bits = []
        for a in assertions:
            if a.get("passed"):
                continue
            detail = _assertion_fail_details(run_dir, sid, a)
            fail_bits.append(
                f"<div><span class='chip-fail'>{esc(a.get('name'))}</span> {detail}</div>"
            )
        assertion_names = ", ".join(esc(a.get("name")) for a in assertions)
        rows_html.append(
            "<tr>"
            f"<td><code>{esc(sid)}</code><div class='adv'>{esc(row.get('family'))}</div></td>"
            f"<td class='{v_cls}'>{esc(verdict)}</td>"
            f"<td>{'yes' if gold_ok else 'no'}</td>"
            f"<td class='adv'>{esc((judge0 or {}).get('composite', '—'))}"
            f" / {esc((judge1 or {}).get('composite', '—'))}<div>advisory</div></td>"
            f"<td>{assertion_names}</td>"
            f"<td>{''.join(fail_bits) if fail_bits else '—'}</td>"
            "</tr>"
        )

    timeline: list[str] = []
    for row in results.get("results") or []:
        sid = row["scenarioId"]
        timeline.append(
            "<tr>"
            f"<td><code>{esc(sid)}</code></td>"
            f"<td>{esc(row.get('sessionId'))}</td>"
            f"<td>{esc(row.get('baseVersionId'))} → {esc(row.get('selectedVersionId'))}</td>"
            f"<td>{esc(row.get('baseExecutionId'))} / {esc(row.get('successorExecutionId'))}</td>"
            f"<td>{esc((row.get('timing') or {}).get('unadjustedGenerationWallMs'))} ms</td>"
            "</tr>"
        )

    diff_sections: list[str] = []
    for row in results.get("results") or []:
        sid = row["scenarioId"]
        versions = _scenario_sql_versions(run_dir, sid)
        if len(versions) < 2:
            continue
        chunks = [f"<h3><code>{esc(sid)}</code> SQL versions</h3>"]
        for i in range(len(versions) - 1):
            a_label, a_sql = versions[i]
            b_label, b_sql = versions[i + 1]
            diff = unified_sql_diff(a_sql, b_sql, fromfile=a_label, tofile=b_label)
            if not diff.strip():
                continue
            chunks.append(
                f"<pre class='diff'>{esc(diff)}</pre>"
            )
        if len(chunks) > 1:
            diff_sections.append("".join(chunks))

    judge_sections: list[str] = []
    if not judges:
        judge_sections.append(
            "<div class='note'>Judge not available for this run (development / no-judge path).</div>"
        )
    else:
        for row in judges:
            judge_sections.append(
                "<div class='note'>"
                f"<div><code>{esc(row.get('scenario_id'))}</code> turn={esc(row.get('turn'))} "
                f"version={esc(row.get('version_id'))}</div>"
                f"{_render_judge_block(row)}"
                "</div>"
            )

    empty_diff = "<div class='note'>No multi-version SQL diffs found.</div>"
    diff_html = "".join(diff_sections) or empty_diff

    body = (
        "<header class='topbar'>"
        "<div>"
        f"<h1>{esc(title)}</h1>"
        f"<div class='meta'>{esc(' · '.join(meta_bits))}</div>"
        "<div class='meta'>Development fixture evidence — not a release claim.</div>"
        "</div>"
        f"{THEME_TOGGLE_BUTTON_HTML}"
        "</header>"
        "<main id='report'>"
        "<section>"
        "<h2>Scenario matrix</h2>"
        "<table class='data'>"
        "<thead><tr>"
        "<th>scenario</th><th>reported</th><th>gold ok</th>"
        "<th>judge medians (base/succ)</th><th>assertions</th><th>gold FAIL detail</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
        "</section>"
        "<section>"
        "<h2>Turn / version / execution timeline</h2>"
        "<table class='data'>"
        "<thead><tr><th>scenario</th><th>session</th><th>versions</th>"
        "<th>executions</th><th>gen wall</th></tr></thead>"
        f"<tbody>{''.join(timeline)}</tbody></table>"
        "</section>"
        "<section>"
        "<h2>SQL diffs</h2>"
        f"{diff_html}"
        "</section>"
        "<section>"
        "<h2>Finalized judge (advisory)</h2>"
        f"{''.join(judge_sections)}"
        "</section>"
        "</main>"
        "<div id='sort-live' class='sr-only' aria-live='polite'></div>"
    )
    return body


def build_report(run_dir: Path | str) -> Path:
    """Render self-contained ``report.html`` from a notebook validation run directory."""
    run_dir = Path(run_dir)
    manifest = _load_json(run_dir / "run_manifest.json")
    suite = _load_json(run_dir / "suite.json")
    results = _load_json(run_dir / "results.json")
    judges = read_jsonl(run_dir / "judge.jsonl", strict=True)
    blob = {
        "report_family": "catalyst",
        "manifest": manifest,
        "suite": suite,
        "results": results,
        "judges": judges,
    }
    body = _build_body(run_dir, blob)
    suite_id = suite.get("id") or results.get("suiteId") or manifest.get("run_id") or "catalyst"
    html = render_document(
        title=f"catalyst report · {suite_id}",
        body_html=body,
        embedded_data=blob,
        style=_STYLE,
        script=_SCRIPT,
        theme_storage_key="oc-theme-report",
    )
    out = run_dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out
