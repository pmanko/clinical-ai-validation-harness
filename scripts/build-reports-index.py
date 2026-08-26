#!/usr/bin/env python3
"""Regenerate artifacts/reports/index.html from the CURATED manifest reports-index.json.

This is a hand-curated showcase, not an auto-discovered listing: only the runs named in
reports-index.json appear, in the order given, with human-written titles/summaries. Scores
and arm lists are still pulled from each run's data (via the harness's own
reconcile.scout_summary) so the numbers can't drift from the manifest prose — but jargon
(arm ids like `a4b-baseline`, columns like `acc`) is translated to plain language here.

Edit reports-index.json to add/remove/reorder runs or change the copy, then rerun:
  uv run python scripts/build-reports-index.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.common.text import esc  # noqa: E402
from harness.report_shell.assets import (  # noqa: E402
    THEME_TOGGLE_BUTTON_HTML,
    THEME_TOGGLE_CSS,
    theme_bootstrap_js,
    theme_toggle_js,
)
from harness.validate.reconcile import scout_summary  # noqa: E402
from harness.catalyst.attribution import conformed as _conformed
from harness.validate.report import _load_judge  # noqa: E402
from harness.validate.model_registry import arm_card  # noqa: E402

REPORTS = ROOT / "artifacts" / "reports"
VALIDATE = ROOT / "artifacts" / "validate"
MANIFEST = ROOT / "reports-index.json"
BACKENDS = ROOT / "datasets" / "validation" / "backends.json"


def _backend_labels() -> dict[str, str]:
    try:
        d = json.loads(BACKENDS.read_text())
        return {k: (v or {}).get("label", k) for k, v in d.items() if isinstance(v, dict)}
    except Exception:
        return {}


_RAW = _backend_labels()


def human_arm(arm: str) -> tuple[str, str]:
    """(plain-language name, hover detail). Detail = the arm's resolved makeup from the shared
    resolver — a single model's family·size·quant, or a team's role→model lineup — so the index
    hover matches the report; falls back to the backend's engineering label."""
    card = arm_card(arm)
    if card.get("kind") == "team":
        makeup = " · ".join(f"{r}={m['id']}" for r, m in (card.get("roles") or {}).items())
    else:
        m = (card.get("models") or [{}])[0]
        makeup = " · ".join(x for x in [m.get("id"), m.get("params"), m.get("quant")] if x)
    detail = makeup or _RAW.get(arm, arm)
    a = arm.lower()
    if a.startswith("med-agent-team"):
        # match the tier token AFTER the prefix — "med-agent" itself contains "med".
        rest = a[len("med-agent-team"):]
        if "parity" in rest:
            tier = "matched to baseline"
        elif "high" in rest:
            tier = "Advanced"
        elif "med" in rest:
            tier = "Standard"
        elif "low" in rest:
            tier = "Basic"
        elif "12b" in rest:
            tier = "12B"
        else:
            tier = "team"
        checker = " + checker" if "validated" in rest else ""
        indepth = " + in-depth" if "indepth" in rest else ""
        return (f"AI team — {tier}{checker}{indepth}", detail)
    # The In-Depth-parity single arm routes through the hub but is a single model emitting an
    # In-Depth section; name it as such (before the generic "12b" single-model match below).
    if "single-12b-indepth" in a:
        return ("Gemma 12B (single + in-depth)", detail)
    # All other single arms: use the resolved card's short title (family · size · quant), so every
    # size/quant variant is distinct AND correctly named — the old substring matching mislabeled new
    # arms (e.g. mistral-nemo-12b matched "12b" and rendered as "Gemma 12B") and could not tell a Q8
    # arm from its Q4 twin.
    return (card.get("short_title") or _RAW.get(arm, arm), detail)


def _run_meta(slug: str) -> dict:
    meta = REPORTS / slug / "meta.json"
    if not meta.is_file():
        return {}
    try:
        payload = json.loads(meta.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _run_dir_for(slug: str) -> Path | None:
    """Resolve new root-relative metadata or the legacy validate-only key."""

    meta = _run_meta(slug)
    family = str(meta.get("report_family") or "chartsearchai")
    run_path = meta.get("run_path")
    if isinstance(run_path, str) and run_path:
        candidate = (ROOT / run_path).resolve()
        if not candidate.is_relative_to(ROOT.resolve()):
            return None
        sentinel = "results.json" if family == "catalyst" else "results.jsonl"
        return candidate if (candidate / sentinel).is_file() else None

    # Backward compatibility: old metadata stored a bare directory name and
    # was intentionally confined to artifacts/validate.
    rd = meta.get("run_dir") or meta.get("run_id")
    if rd:
        candidate = (VALIDATE / str(rd)).resolve()
        if candidate.is_relative_to(VALIDATE.resolve()) and (
            candidate / "results.jsonl"
        ).is_file():
            return candidate
    return None


def _patient_names(run_dir: Path, uuids: set[str]) -> str:
    man = run_dir / "run_manifest.json"
    book: dict[str, str] = {}
    if man.exists():
        try:
            for u, p in (json.loads(man.read_text()).get("patients") or {}).items():
                disp = (p or {}).get("display")
                if disp:
                    book[u] = disp.split(" - ")[-1].strip()
        except Exception:
            pass
    names = [book.get(u, "a patient") for u in sorted(uuids)]
    return " + ".join(dict.fromkeys(names)) if names else ""


def gather(slug: str) -> dict:
    """Pull the score table + subtitle facts for one curated run from its data."""
    meta = _run_meta(slug)
    family = str(meta.get("report_family") or "chartsearchai")
    out: dict = {
        "family": family,
        "reader_led": False,
        "cells": None,
        "patients": "",
        "date": None,
        "scout": [],
        "scoreline": str(meta.get("scoreline") or ""),
    }
    rdir = _run_dir_for(slug)
    if not rdir:
        return out
    if family == "catalyst":
        suite_path = rdir / "suite.json"
        suite = (
            json.loads(suite_path.read_text(encoding="utf-8"))
            if suite_path.is_file()
            else {}
        )
        reader_led = suite.get("reportMode") == "reader-led"
        out["reader_led"] = reader_led
        results = json.loads((rdir / "results.json").read_text(encoding="utf-8"))
        rows = list(results.get("results") or [])
        out["cells"] = int(results.get("resultCount") or len(rows))
        out["date"] = datetime.fromtimestamp(
            (rdir / "results.json").stat().st_mtime, timezone.utc
        ).strftime("%-d %b %Y")
        teams: dict[str, list[dict]] = {}
        for row in rows:
            team = row.get("profileId")
            if isinstance(team, str):
                teams.setdefault(team, []).append(row)
        if reader_led:
            parts = [
                f"{len(teams)} model teams",
                f"{len(rows)} conversations",
                "full-evidence reader review",
            ]
            incomplete = sum(
                row.get("measurementValid") is not True for row in rows
            )
            if incomplete:
                parts.append(f"{incomplete} with incomplete evidence")
            out["scoreline"] = " · ".join(parts)
            return out
        if len(teams) > 1:
            # A comparison's headline is how the teams did, not how many
            # gold checks ran across all of them at once.
            scores = [
                f"{team.split('catalyst-query-')[-1]} "
                f"{sum(1 for r in rs if r.get('passed'))}/{len(rs)}"
                for team, rs in teams.items()
            ]
            parts = [f"{len(teams)} teams · " + " · ".join(scores)]
            invalid = sum(
                1
                for row in rows
                if not _conformed(row.get("assertions") or [])
            )
            if invalid:
                parts.append(
                    f"{invalid} invalid measurement" + ("s" if invalid > 1 else "")
                )
        else:
            gold = [
                assertion
                for row in rows
                for assertion in (row.get("assertions") or [])
                if "gold_execution_match" in str(assertion.get("name") or "")
            ]
            passed = sum(bool(assertion.get("passed")) for assertion in gold)
            parts = [f"Gold checks: {passed}/{len(gold)} passed"] if gold else []
        judge_path = rdir / "judge.jsonl"
        if judge_path.is_file():
            judge_rows = [
                json.loads(line)
                for line in judge_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            composites = [
                float(row["composite"])
                for row in judge_rows
                if isinstance(row.get("composite"), (int, float))
            ]
            if composites:
                parts.append(f"Advisory judge median: {median(composites):g}/100")
        out["scoreline"] = " · ".join(parts) or out["scoreline"]
        return out

    rows = [json.loads(l) for l in (rdir / "results.jsonl").read_text().splitlines() if l.strip()]
    arms = sorted({r.get("backend_id") for r in rows if r.get("backend_id")})
    pts = {(r.get("request") or {}).get("patient") for r in rows if (r.get("request") or {}).get("patient")}
    out["cells"] = len(rows)
    out["patients"] = _patient_names(rdir, pts)
    out["date"] = datetime.fromtimestamp(
        (rdir / "results.jsonl").stat().st_mtime, timezone.utc).strftime("%-d %b %Y")
    judge = _load_judge(rdir)
    if judge:
        summ = [s for s in scout_summary(judge, arms) if s["n"]]
        summ.sort(key=lambda s: (s.get("benchmark_score") or 0), reverse=True)
        out["scout"] = summ
    return out


def _scout_table(scout: list[dict]) -> str:
    if not scout:
        return '<div class="unscored">This run is an answer comparison only — not yet scored.</div>'
    # best (max) per column, to highlight the winner. Benchmark is the headline.
    best = {}
    for key in ("benchmark_score", "accuracy_mean", "completeness_mean", "relevance_mean"):
        vals = [s[key] for s in scout if isinstance(s.get(key), (int, float))]
        best[key] = max(vals) if vals else None
    head = ('<table class="scout"><thead><tr>'
            '<th class="arm">AI setup</th><th>Questions</th>'
            '<th class="bench">Benchmark<br>/100</th>'
            '<th>Accuracy</th><th>Completeness</th><th>Relevance</th>'
            '<th>Unsafe<br>answers</th></tr></thead><tbody>')
    body = []
    for s in scout:
        name, detail = human_arm(s["backend"])

        def cell(key):
            v = s.get(key)
            classes = ["bench"] if key == "benchmark_score" else []
            if isinstance(v, (int, float)) and best[key] is not None and abs(v - best[key]) < 1e-9:
                classes.append("best")
            cls = f' class="{" ".join(classes)}"' if classes else ""
            txt = f"{v:.1f}" if isinstance(v, (int, float)) else "—"
            return f"<td{cls}>{txt}</td>"
        harm = s.get("harm_count", 0)
        flags = (f'harm: {harm} · confabulations: {s.get("confabulation_count", 0)} · '
                 f'fabricated citations: {s.get("fabricated_citation_count", 0)}')
        harm_cls = ' class="harm"' if harm else ""
        harm_cell = f'<td{harm_cls} title="{esc(flags)}">{harm}</td>'
        body.append(
            f'<tr><td class="arm" title="{esc(detail)}">{esc(name)}</td>'
            f'<td>{s["n"]}</td>{cell("benchmark_score")}{cell("accuracy_mean")}'
            f'{cell("completeness_mean")}{cell("relevance_mean")}{harm_cell}</tr>'
        )
    table = head + "".join(body) + "</tbody></table>"
    # In-Depth — its own parity Benchmark, shown (NOT hidden) for ANY arm that ships one (single-model
    # two-call or team), in a clearly separate block so the elaboration scores never sit in the
    # head-to-head Answer grid above. Sorted by the In-Depth Benchmark.
    bg = [s for s in scout if (s.get("background") or {}).get("n_background")]
    if bg:
        bg.sort(key=lambda s: ((s.get("background") or {}).get("benchmark_score") or 0), reverse=True)
        rows = []
        for s in bg:
            name, _ = human_arm(s["backend"])
            b = s["background"]
            ben = "—" if b.get("benchmark_score") is None else f'{b["benchmark_score"]:.1f}'
            sup = "—" if b.get("support_mean") is None else f'{b["support_mean"]:.1f}'
            val = "—" if b.get("added_value_mean") is None else f'{b["added_value_mean"]:.1f}'
            rows.append(f'<tr><td class="arm">{esc(name)}</td><td class="bench">{ben}</td>'
                        f'<td>{b["n_background"]}</td><td>{sup}</td><td>{val}</td>'
                        f'<td>{b.get("new_harm_count", 0)}</td><td>{b.get("padded_count", 0)}</td></tr>')
        table += ('<h3 style="margin:20px 0 6px;font-size:15px;font-weight:600">In-Depth — scored separately on '
                  'its own axes (its own parity Benchmark)</h3>'
                  '<table class="scout"><thead><tr><th class="arm">AI setup</th><th>In-Depth Benchmark</th>'
                  '<th>In-depth answers</th><th>Support</th><th>Added value</th><th>Unsafe</th><th>Padded</th>'
                  '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>')
    return table


def _card(entry: dict) -> str:
    slug = entry["slug"]
    g = gather(slug)
    facts = []
    if g["patients"]:
        facts.append(esc(g["patients"]))
    if g["cells"] is not None:
        unit = "conversations" if g.get("family") == "catalyst" else "graded answers"
        facts.append(f'{g["cells"]} {unit}')
    if g["date"]:
        facts.append(esc(g["date"]))
    subtitle = " · ".join(facts)
    family = str(g.get("family") or "chartsearchai")
    if family == "catalyst":
        # Labels name the question each page answers, not the artifact kind.
        links = [f'<a class="btn" href="{esc(slug)}/index.html">Read the report</a>']
        if (REPORTS / slug / "comparison.html").exists():
            # The decision document: verdict, gates and the failure inventory.
            links.append(f'<a class="btn ghost" href="{esc(slug)}/comparison.html">Compare the teams</a>')
        if (REPORTS / slug / "dashboard.html").exists():
            links.append(f'<a class="btn ghost" href="{esc(slug)}/dashboard.html">Inspect every conversation</a>')
        if (REPORTS / slug / "run-config.json").exists():
            links.append(f'<a class="btn ghost" href="{esc(slug)}/run-config.json">Run seed (JSON)</a>')
    else:
        links = [f'<a class="btn" href="{esc(slug)}/index.html">Full report</a>']
        if (REPORTS / slug / "comparison.html").exists():
            links.append(f'<a class="btn ghost" href="{esc(slug)}/comparison.html">Team comparison</a>')
        if (REPORTS / slug / "dashboard.html").exists():
            links.append(f'<a class="btn ghost" href="{esc(slug)}/dashboard.html">Interactive dashboard</a>')
    takeaway = (f'<p class="takeaway"><span class="tk">Takeaway</span>{esc(entry["takeaway"])}</p>'
                if entry.get("takeaway") else "")
    family_label = "Catalyst SQL" if family == "catalyst" else "ChartSearchAI"
    return f"""  <article class="card">
  <header class="card-head">
    <div class="titles"><span class="family {esc(family)}">{esc(family_label)}</span><h2>{esc(entry["title"])}</h2><div class="slug">{subtitle}</div></div>
    <div class="links">{"".join(links)}</div>
  </header>
  <p class="summary">{esc(entry.get("summary", ""))}</p>
  {f'<div class="unscored">{esc(g.get("scoreline", ""))}</div>' if (g.get("scoreline") and not g["scout"]) else _scout_table(g["scout"])}
  {takeaway}
  </article>"""


_STYLE_CORE = """
  html[data-theme="light"]{color-scheme:light;--bg:#f6f8fa;--panel:#ffffff;--panel2:#ffffff;--text:#1f2328;--muted:#656d76;
    --accent:#0969da;--border:#d0d7de;--harm:#cf222e;--best:#1a7f37;
    --ink:#1f2328;--btn-fg:#ffffff;--th-bg:#f6f8fa;--bench-bg:rgba(9,105,218,.08);--takeaway-bg:rgba(9,105,218,.06);}
  html[data-theme="dark"]{color-scheme:dark;--bg:#0d1117;--panel:#161b22;--panel2:#1c2230;--text:#c9d1d9;--muted:#8b949e;
    --accent:#79c0ff;--border:#30363d;--harm:#f85149;--best:#3fb950;
    --ink:#ffffff;--btn-fg:#0d1117;--th-bg:rgba(255,255,255,.02);--bench-bg:rgba(121,192,255,.10);--takeaway-bg:rgba(121,192,255,.06);}
  *{box-sizing:border-box;} body{margin:0;background:var(--bg);color:var(--text);
    font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;padding:36px 24px 72px;}
  .wrap{max-width:960px;margin:0 auto;}
  header.page h1{font-size:27px;margin:0 0 10px;color:var(--ink);font-weight:600;}
  .intro{color:var(--text);font-size:15px;margin:0 0 20px;max-width:760px;}
  .intro b{color:var(--ink);}
  .legend{background:var(--panel2);border:1px solid var(--border);border-radius:10px;
    padding:14px 18px;font-size:13.5px;color:var(--muted);margin-bottom:30px;max-width:760px;}
  .legend b{color:var(--text);}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:22px 24px;margin-bottom:22px;}
  .card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:6px;}
  .titles h2{margin:0;font-size:20px;color:var(--ink);font-weight:600;line-height:1.3;}
  .family{display:inline-block;margin:0 0 6px;padding:2px 7px;border:1px solid var(--border);
    border-radius:999px;color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;}
  .family.catalyst{color:var(--accent);border-color:var(--accent);}
  .titles .slug{color:var(--muted);font-size:13px;margin-top:4px;}
  .links{display:flex;gap:8px;flex-wrap:wrap;}
  .btn{display:inline-block;text-decoration:none;background:var(--accent);color:var(--btn-fg);
    font-weight:600;font-size:13px;padding:7px 14px;border-radius:6px;border:1px solid var(--accent);white-space:nowrap;}
  .btn.ghost{background:transparent;color:var(--accent);}
  .btn:hover{filter:brightness(1.1);}
  .summary{color:var(--text);font-size:14.5px;margin:10px 0 16px;max-width:760px;}
  table.scout{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--panel2);
    border:1px solid var(--border);border-radius:8px;overflow:hidden;}
  table.scout th,table.scout td{padding:8px 12px;text-align:right;border-bottom:1px solid var(--border);}
  table.scout th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;
    letter-spacing:.04em;background:var(--th-bg);vertical-align:bottom;}
  table.scout th.arm,table.scout td.arm{text-align:left;}
  table.scout td.arm{color:var(--ink);cursor:help;}
  table.scout tr:last-child td{border-bottom:none;}
  table.scout td.best{color:var(--best);font-weight:700;}
  table.scout td.harm{color:var(--harm);font-weight:700;}
  /* Benchmark = the headline aggregate: framed + tinted column so it reads as the focal point. */
  table.scout th.bench,table.scout td.bench{background:var(--bench-bg);
    border-left:2px solid var(--accent);border-right:2px solid var(--accent);}
  table.scout th.bench{color:var(--accent);font-size:11.5px;}
  table.scout td.bench{color:var(--ink);font-weight:800;font-size:16px;}
  table.scout td.bench.best{color:var(--best);}
  table.scout tbody tr:last-child td.bench{border-bottom:2px solid var(--accent);}
  .unscored{color:var(--muted);font-size:13.5px;font-style:italic;}
  .takeaway{font-size:14px;color:var(--text);margin:14px 0 0;background:var(--takeaway-bg);
    border-left:3px solid var(--accent);padding:10px 14px;border-radius:0 6px 6px 0;}
  .takeaway .tk{display:inline-block;font-size:11px;text-transform:uppercase;letter-spacing:.05em;
    color:var(--accent);font-weight:700;margin-right:8px;}
  footer.page{color:var(--muted);font-size:12px;margin-top:36px;text-align:center;}
"""

STYLE = _STYLE_CORE + THEME_TOGGLE_CSS


def main(
    argv: list[str] | None = None,
) -> None:
    global ROOT, REPORTS, VALIDATE, MANIFEST, BACKENDS, _RAW
    if argv is not None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--root", type=Path, default=ROOT)
        parser.add_argument("--reports-root", type=Path)
        parser.add_argument("--manifest", type=Path)
        args = parser.parse_args(argv)
        ROOT = args.root.resolve()
        REPORTS = (args.reports_root or ROOT / "artifacts" / "reports").resolve()
        VALIDATE = ROOT / "artifacts" / "validate"
        MANIFEST = (args.manifest or ROOT / "reports-index.json").resolve()
        BACKENDS = ROOT / "datasets" / "validation" / "backends.json"
        _RAW = _backend_labels()
    manifest = json.loads(MANIFEST.read_text())
    runs = manifest.get("runs", [])
    # Loud, not silent: a run whose report is staged under artifacts/reports/ but absent from the
    # curated manifest gets DEPLOYED (rsync, no --delete) yet never LISTED. Warn so a missed
    # publish-time upsert is visible instead of quietly producing a deployed-but-unlisted run.
    listed = {r.get("slug") for r in runs}
    staged = {p.parent.name for p in REPORTS.glob("*/meta.json")}
    for slug in sorted(staged - listed):
        print(f"warn: {slug} is staged under artifacts/reports/ but NOT in reports-index.json "
              f"(deployed but unlisted) — add it to the manifest to list it.", file=sys.stderr)
    cards = "\n".join(_card(r) for r in runs)
    run_summaries = [gather(r["slug"]) for r in runs]
    has_reader_led = any(summary.get("reader_led") for summary in run_summaries)
    has_other_reports = any(
        not summary.get("reader_led") for summary in run_summaries
    )
    scoring_note = str(manifest.get("scoring_note", ""))
    if has_reader_led and has_other_reports:
        scoring_note = (
            "The numerical explanation below applies only to reports that "
            "show score tables. Reader-led Catalyst comparisons show database "
            "facts and prose review without numerical grading. "
            + scoring_note
        )
    elif has_reader_led:
        scoring_note = (
            "Reader-led Catalyst comparisons present the database facts, the "
            "complete conversation evidence, and the attached prose review "
            "for the reader to assess."
        )
    html = f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenClinAI — clinical AI validation runs</title>
<script>{theme_bootstrap_js("oc-theme-index")}</script>
<style>{STYLE}</style>
</head>
<body>
{THEME_TOGGLE_BUTTON_HTML}
<div class="wrap">
  <header class="page">
    <h1>Clinical AI validation runs</h1>
    <p class="intro">{manifest.get("intro", "")}</p>
  </header>
  <div class="legend"><b>How to read these reports.</b> {scoring_note}</div>
{cards}
  <footer class="page">Curated index — edit reports-index.json to change what appears. Hover an AI setup name for its exact model lineup.</footer>
</div>
<script>{theme_toggle_js("oc-theme-index")}</script>
</body>
</html>
"""
    out = REPORTS / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(runs)} curated runs)")
    for r in runs:
        g = gather(r["slug"])
        detail = (
            "reader-led comparison"
            if g.get("reader_led")
            else f"{len(g['scout'])} setups scored"
        )
        print(f"  {r['slug']:38} {detail} — {r['title']}")


if __name__ == "__main__":
    main(sys.argv[1:])
