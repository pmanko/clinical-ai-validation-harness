"""Generate a standalone, self-contained HTML validation report from a run's
results.jsonl + run_manifest.json (spec 006 SC-006.4).

No build step, no server, no ESM import — open report.html in a browser. Layout:
a per-backend comparison summary, then one grid per scenario (rows = turns/the
question, columns = backends, each cell = answer + citations + metric chips).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _ordered_unique(values: list[Any]) -> list[Any]:
    seen: dict[Any, None] = {}
    for v in values:
        seen.setdefault(v, None)
    return list(seen)


def _backend_models(events: list[dict[str, Any]]) -> dict[str, str]:
    return {
        e["backend_id"]: e.get("modelName", "")
        for e in events
        if e.get("event_type") == "backend_selected"
    }


def _avg(nums: list[int]) -> int:
    return round(sum(nums) / len(nums)) if nums else 0


def _summary_table(results: list[dict[str, Any]], backends: list[str], models: dict[str, str]) -> str:
    rows = []
    for b in backends:
        rs = [r for r in results if r.get("backend_id") == b]
        lat = [r["metrics"]["latency_ms"] for r in rs if r.get("metrics")]
        cites = sum(r["metrics"].get("citation_count", 0) for r in rs if r.get("metrics"))
        empty = sum(1 for r in rs if r.get("metrics", {}).get("references_empty"))
        errs = sum(1 for r in rs if r.get("error"))
        rows.append(
            f"<tr><td class='b'>{_esc(b)}<span class='model'>{_esc(models.get(b,''))}</span></td>"
            f"<td>{len(rs)}</td><td>{_avg(lat)} ms</td><td>{max(lat) if lat else 0} ms</td>"
            f"<td>{cites}</td><td>{empty}</td><td>{errs}</td></tr>"
        )
    return (
        "<table class='summary'><thead><tr><th>backend</th><th>turns</th><th>avg latency</th>"
        "<th>max latency</th><th>total citations</th><th>no-refs turns</th><th>errors</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _cell(r: dict[str, Any] | None) -> str:
    if r is None:
        return "<td class='empty'>—</td>"
    m = r.get("metrics", {})
    if r.get("error"):
        body = f"<div class='err'>HTTP {_esc(m.get('http_status'))}: {_esc(r['error'])[:400]}</div>"
    else:
        resp = r.get("response") or {}
        body = f"<div class='ans'>{_esc(resp.get('answer'))}</div>"
        refs = resp.get("references") or []
        if refs:
            shown = " ".join(
                f"<span class='ref'>[{_esc(x.get('index'))}] {_esc(x.get('resourceType'))}</span>"
                for x in refs[:8]
            )
            more = f" <span class='more'>+{len(refs) - 8}</span>" if len(refs) > 8 else ""
            body += f"<div class='refs'>{shown}{more}</div>"
    chips = [
        f"<span class='chip{' warm' if m.get('first_turn') else ''}'>⏱ {_esc(m.get('latency_ms'))}ms</span>",
        f"<span class='chip'>cites {_esc(m.get('citation_count'))}</span>",
    ]
    if m.get("references_empty"):
        chips.append("<span class='chip none'>∅ no refs</span>")
    if not m.get("json_valid", True):
        chips.append("<span class='chip bad'>invalid</span>")
    return f"<td>{body}<div class='chips'>{''.join(chips)}</div></td>"


def _scenario_grid(results: list[dict[str, Any]], scenario_id: str, backends: list[str]) -> str:
    rs = [r for r in results if r.get("scenario_id") == scenario_id]
    turns = _ordered_unique([r.get("turn") for r in rs])
    index = {(r.get("turn"), r.get("backend_id")): r for r in rs}
    questions = {r.get("turn"): r.get("request", {}).get("question", "") for r in rs}

    header = "".join(f"<th>{_esc(b)}</th>" for b in backends)
    body_rows = []
    for t in turns:
        cells = "".join(_cell(index.get((t, b))) for b in backends)
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
.wrap { max-width: 1400px; margin: 0 auto; padding: 24px; }
h1 { font-size: 20px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 28px 0 8px; font-family: ui-monospace, monospace; }
.meta { color: var(--mut); font-size: 12px; font-family: ui-monospace, monospace; margin-bottom: 16px; }
table { border-collapse: collapse; width: 100%; background: #fff; }
th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #f3f3f3; font-weight: 600; font-size: 12px; }
.summary td, .summary th { text-align: center; }
.summary td.b { text-align: left; font-family: ui-monospace, monospace; }
.summary .model { display: block; color: var(--mut); font-size: 11px; }
.grid .turncol, .grid .turn { width: 22%; }
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
.legend { color: var(--mut); font-size: 12px; margin-top: 24px; border-top: 1px solid var(--line); padding-top: 12px; }
"""


def build_report(run_dir: Path | str) -> Path:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    results = _read_jsonl(run_dir / "results.jsonl")
    events = _read_jsonl(run_dir / "events.jsonl")
    models = _backend_models(events)

    backends = _ordered_unique([r.get("backend_id") for r in results])
    scenarios = _ordered_unique([r.get("scenario_id") for r in results])

    otel = manifest.get("otel", {})
    meta = (
        f"run {manifest.get('run_id')} · {manifest.get('component')} · git {manifest.get('git_sha','?')[:10]} · "
        f"{manifest.get('dataset_id')} · provider {otel.get('gen_ai.provider.name','?')} · {manifest.get('generated_at','')}"
    )

    grids = "".join(_scenario_grid(results, s, backends) for s in scenarios)
    legend = (
        "<div class='legend'>⏱ latency (orange = first turn per backend, carries model warmup). "
        "cites = chart records cited. ∅ no refs = the answer cited nothing (a references_empty "
        "PROXY for abstention — chartsearchai emits no abstention flag; the authoritative call is "
        "human adjudication). tokens / finish_reasons / response model are not surfaced by /chat "
        "(OTel-deferred). Deterministic metrics only — no LLM judge.</div>"
    )

    doc = (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>validation report · {_esc(manifest.get('run_id'))}</title><style>{_STYLE}</style></head>"
        f"<body><div class='wrap'><h1>Validation report — {_esc(' vs '.join(backends))}</h1>"
        f"<div class='meta'>{_esc(meta)}</div>"
        f"<h2>comparison summary</h2>{_summary_table(results, backends, models)}"
        f"{grids}{legend}</div></body></html>"
    )
    out = run_dir / "report.html"
    out.write_text(doc, encoding="utf-8")
    return out
