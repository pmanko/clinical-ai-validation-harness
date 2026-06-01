"""Generate a standalone, self-contained HTML validation report from a run's
results.jsonl + run_manifest.json (spec 006 SC-006.4/5).

No build step, no server, no ESM import — open report.html in a browser. Layout:
a per-backend comparison summary, then one grid per scenario (rows = turns/the
question, columns = backends, each cell = answer + citations + metric chips +
a per-cell Scout-rubric adjudication form). A "Download feedback.jsonl" button
serialises the filled forms into the feedback shape the repository expects
(client-side; no server needed — drop the file into the run dir).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


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


def _summary_table(results: list[dict[str, Any]], backends: list[str], labels: dict[str, str]) -> str:
    rows = []
    for b in backends:
        rs = [r for r in results if r.get("backend_id") == b]
        lat = [r["metrics"]["latency_ms"] for r in rs if r.get("metrics")]
        cites = sum(r["metrics"].get("citation_count", 0) for r in rs if r.get("metrics"))
        degraded = sum(1 for r in rs if _is_degraded(r))
        errs = sum(1 for r in rs if r.get("error"))
        rows.append(
            f"<tr><td class='b'>{_esc(b)}<span class='model'>{_esc(labels.get(b,''))}</span></td>"
            f"<td>{len(rs)}</td><td>{_avg(lat)} ms</td><td>{max(lat) if lat else 0} ms</td>"
            f"<td>{cites}</td><td>{degraded}</td><td>{errs}</td></tr>"
        )
    return (
        "<table class='summary'><thead><tr><th>backend</th><th>turns</th><th>avg latency</th>"
        "<th>max latency</th><th>total chart refs</th><th>degraded</th>"
        "<th>errors</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _form(scenario_id: str, turn: Any, backend_id: str) -> str:
    score = lambda name: (
        f"<label>{name[:3]}<input type='number' min='0' max='10' step='1' name='{name}'></label>"
    )
    return (
        f"<details class='adj'><summary>adjudicate</summary>"
        f"<div class='cell-form' data-scenario='{_esc(scenario_id)}' data-turn='{_esc(turn)}' "
        f"data-backend='{_esc(backend_id)}'>"
        f"<div class='scores'>{score('accuracy')}{score('completeness')}{score('relevance')}</div>"
        f"<label>abstention<select name='abstention_outcome'>"
        f"<option value='n-a'>n/a</option><option value='correct'>correct</option>"
        f"<option value='over-abstained'>over-abstained</option>"
        f"<option value='failed-to-abstain'>failed-to-abstain</option></select></label>"
        f"<label>citations<select name='citation_groundedness'>"
        f"<option value='n-a'>n/a</option><option value='supported'>supported</option>"
        f"<option value='partly'>partly</option><option value='unsupported'>unsupported</option></select></label>"
        f"<label class='harm'><input type='checkbox' name='harm_fail'> harm hard-fail</label>"
        f"<div class='decision'><label><input type='radio' name='decision-{_esc(scenario_id)}-{_esc(turn)}-{_esc(backend_id)}' value='pass'> pass</label>"
        f"<label><input type='radio' name='decision-{_esc(scenario_id)}-{_esc(turn)}-{_esc(backend_id)}' value='fail'> fail</label></div>"
        f"<textarea name='free_text' placeholder='notes'></textarea>"
        f"</div></details>"
    )


def _cell(r: dict[str, Any] | None, scenario_id: str, turn: Any, backend_id: str) -> str:
    if r is None:
        return "<td class='empty'>—</td>"
    m = r.get("metrics", {})
    if r.get("error"):
        body = f"<div class='err'>HTTP {_esc(m.get('http_status'))}: {_esc(r['error'])[:400]}</div>"
    else:
        resp = r.get("response") or {}
        body = f"<div class='ans'>{_render_answer(resp.get('answer'))}</div>"
        refs = resp.get("references") or []
        if refs:
            shown = " ".join(
                f"<span class='ref'>[{_esc(x.get('index'))}] {_esc(x.get('resourceType'))}</span>"
                for x in refs[:8]
            )
            more = f" <span class='more'>+{len(refs) - 8}</span>" if len(refs) > 8 else ""
            body += f"<div class='refs'>{shown}{more}</div>"
        body += _render_blocks(resp.get("blocks"))
    chips = [
        f"<span class='chip{' warm' if m.get('first_turn') else ''}'>⏱ {_esc(m.get('latency_ms'))}ms</span>",
        f"<span class='chip'>{_esc(m.get('citation_count'))} chart refs</span>",
    ]
    if not m.get("json_valid", True):
        chips.append("<span class='chip bad'>invalid</span>")
    if _is_degraded(r):
        chips.append("<span class='chip bad'>⚠ degraded</span>")
    return f"<td>{body}<div class='chips'>{''.join(chips)}</div>{_form(scenario_id, turn, backend_id)}</td>"


def _scenario_grid(results: list[dict[str, Any]], scenario_id: str, backends: list[str]) -> str:
    rs = [r for r in results if r.get("scenario_id") == scenario_id]
    turns = _ordered_unique([r.get("turn") for r in rs])
    index = {(r.get("turn"), r.get("backend_id")): r for r in rs}
    questions = {r.get("turn"): r.get("request", {}).get("question", "") for r in rs}

    header = "".join(f"<th>{_esc(b)}</th>" for b in backends)
    body_rows = []
    for t in turns:
        cells = "".join(_cell(index.get((t, b)), scenario_id, t, b) for b in backends)
        body_rows.append(
            f"<tr><td class='turn'><span class='n'>T{_esc(t)}</span>"
            f"<div class='q'>{_esc(questions.get(t))}</div></td>{cells}</tr>"
        )
    return (
        f"<section><h2>{_esc(scenario_id)}</h2>"
        f"<table class='grid'><thead><tr><th class='turncol'>turn / question</th>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></section>"
    )


_STYLE = """
:root { --fg:#1a1a1a; --mut:#666; --line:#e2e2e2; --bg:#fafafa; }
* { box-sizing: border-box; }
body { font: 14px/1.5 -apple-system, system-ui, sans-serif; color: var(--fg); margin: 0; background: var(--bg); }
.wrap { max-width: 1500px; margin: 0 auto; padding: 24px 24px 120px; }
h1 { font-size: 20px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 28px 0 8px; font-family: ui-monospace, monospace; }
.meta { color: var(--mut); font-size: 12px; font-family: ui-monospace, monospace; margin-bottom: 16px; }
table { border-collapse: collapse; width: 100%; background: #fff; }
th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #f3f3f3; font-weight: 600; font-size: 12px; }
.summary td, .summary th { text-align: center; }
.summary td.b { text-align: left; font-family: ui-monospace, monospace; }
.summary .model { display: block; color: var(--mut); font-size: 11px; }
.grid .turncol, .grid .turn { width: 20%; }
.turn .n { font-family: ui-monospace, monospace; font-weight: 700; color: var(--mut); }
.turn .q { margin-top: 2px; }
.ans { white-space: pre-wrap; }
.refs { margin-top: 6px; }
.ref { display: inline-block; font-size: 10px; font-family: ui-monospace, monospace; background: #eef3ff; color: #2748a0; padding: 1px 4px; border-radius: 3px; margin: 1px; }
.more { color: var(--mut); font-size: 10px; }
.err { color: #a01; font-family: ui-monospace, monospace; font-size: 12px; }
.chips { margin-top: 6px; }
.chip { display: inline-block; font-size: 10px; font-family: ui-monospace, monospace; background: #eee; color: #444; padding: 1px 5px; border-radius: 3px; margin: 1px; }
.chip.warm { background: #fff3d6; color: #8a5a00; }
.chip.none { background: #fde8e8; color: #a01; }
.chip.bad { background: #a01; color: #fff; }
.empty { color: #bbb; text-align: center; }
.adj { margin-top: 8px; font-size: 12px; }
.adj summary { cursor: pointer; color: #2748a0; font-size: 11px; }
.cell-form { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.cell-form .scores { display: flex; gap: 6px; }
.cell-form label { font-size: 11px; color: var(--mut); }
.cell-form input[type=number] { width: 38px; }
.cell-form select { font-size: 11px; }
.cell-form textarea { width: 100%; height: 36px; font: inherit; font-size: 11px; }
.cell-form .decision { display: flex; gap: 10px; }
.bar { position: fixed; bottom: 0; left: 0; right: 0; background: #1a1a1a; color: #fff; padding: 10px 24px; display: flex; gap: 12px; align-items: center; }
.bar input { font: inherit; padding: 4px 8px; }
.bar button { font: inherit; font-weight: 600; padding: 6px 14px; cursor: pointer; }
.legend { color: var(--mut); font-size: 12px; margin-top: 24px; border-top: 1px solid var(--line); padding-top: 12px; }
"""


def _script(run_id: str) -> str:
    return (
        "<script>const RUN_ID=" + json.dumps(run_id) + ";"
        "function n(v){v=(v||'').trim();return v===''?null:Number(v);}"
        "function collect(){const out=[];"
        "document.querySelectorAll('.cell-form').forEach(function(f){"
        "const g=function(s){return f.querySelector(s);};"
        "const acc=g('[name=accuracy]').value,comp=g('[name=completeness]').value,rel=g('[name=relevance]').value;"
        "const abst=g('[name=abstention_outcome]').value,grnd=g('[name=citation_groundedness]').value;"
        "const harm=g('[name=harm_fail]').checked;const dec=f.querySelector('input[type=radio]:checked');"
        "const txt=g('[name=free_text]').value.trim();"
        "const touched=acc||comp||rel||txt||harm||dec||abst!=='n-a'||grnd!=='n-a';if(!touched)return;"
        "out.push(JSON.stringify({run_id:RUN_ID,scenario_id:f.dataset.scenario,turn:Number(f.dataset.turn),"
        "backend_id:f.dataset.backend,reviewer:document.getElementById('rev').value||'unknown',"
        "scores:{accuracy:n(acc),completeness:n(comp),relevance:n(rel)},abstention_outcome:abst,"
        "citation_groundedness:grnd,harm_fail:harm,decision:dec?dec.value:null,free_text:txt,"
        "created_at:new Date().toISOString()}));});"
        "if(!out.length){alert('No adjudications filled in yet.');return;}"
        "const blob=new Blob([out.join('\\n')+'\\n'],{type:'application/x-ndjson'});"
        "const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='feedback.jsonl';a.click();"
        "}</script>"
    )


def build_report(run_dir: Path | str) -> Path:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    results = _read_jsonl(run_dir / "results.jsonl")
    events = _read_jsonl(run_dir / "events.jsonl")
    labels = _backend_labels(events)

    backends = _ordered_unique([r.get("backend_id") for r in results])
    scenarios = _ordered_unique([r.get("scenario_id") for r in results])
    run_id = manifest.get("run_id", "")

    otel = manifest.get("otel", {})
    meta = (
        f"run {run_id} · {manifest.get('component')} · git {manifest.get('git_sha','?')[:10]} · "
        f"{manifest.get('dataset_id')} · provider {otel.get('gen_ai.provider.name','?')} · {manifest.get('generated_at','')}"
    )

    grids = "".join(_scenario_grid(results, s, backends) for s in scenarios)
    legend = (
        "<div class='legend'>⏱ latency (orange = first turn per backend, carries model warmup). "
        "chart refs = count of chart records cited — a COUNT, not a grounding/quality signal; "
        "the authoritative call is the human adjudication below each cell. tokens / finish_reasons / "
        "response model are not surfaced by /chat (OTel-deferred). Deterministic metrics only — no LLM judge.</div>"
    )
    bar = (
        "<div class='bar'>reviewer <input id='rev' placeholder='you@example.org'>"
        "<button onclick='collect()'>Download feedback.jsonl</button>"
        "<span style='color:#aaa;font-size:12px'>fills the feedback collection; drop it into the run dir</span></div>"
    )

    doc = (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>validation report · {_esc(run_id)}</title><style>{_STYLE}</style></head>"
        f"<body><div class='wrap'><h1>Validation report — {_esc(' vs '.join(backends))}</h1>"
        f"<div class='meta'>{_esc(meta)}</div>"
        f"<h2>comparison summary</h2>{_summary_table(results, backends, labels)}"
        f"{grids}{legend}</div>{bar}{_script(run_id)}</body></html>"
    )
    out = run_dir / "report.html"
    out.write_text(doc, encoding="utf-8")
    return out
