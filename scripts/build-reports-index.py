#!/usr/bin/env python3
"""Regenerate artifacts/reports/index.html by auto-discovering EVERY published report.

One card per directory under artifacts/reports/ that has an index.html — discovery never
gates on meta.json (curation sets order, not visibility). For each card we resolve the
run_id (meta.json, else the dominant UUID in the rendered report), locate the run dir, and
pull set / cells / arms / patients + the per-arm Scout means via the harness's own
reconcile.scout_summary (no reimplementation). Runs that can't be mapped to a run dir
(e.g. a standalone methodology dashboard) still get a card with its links.

Usage: uv run python scripts/build-reports-index.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.validate.reconcile import scout_summary  # noqa: E402
from harness.validate.report import _load_judge  # noqa: E402

REPORTS = ROOT / "artifacts" / "reports"
VALIDATE = ROOT / "artifacts" / "validate"
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _resolve_run_id(slug_dir: Path) -> str | None:
    meta = slug_dir / "meta.json"
    if meta.exists():
        try:
            rid = json.loads(meta.read_text()).get("run_id")
            if rid:
                return rid
        except Exception:
            pass
    # Else mine the rendered report for UUIDs and pick the one that IS a run dir — the
    # run_id is stamped in the page alongside patient/concept uuids, so existence in
    # artifacts/validate disambiguates it (modal frequency would pick the patient).
    html = (slug_dir / "index.html").read_text(encoding="utf-8", errors="ignore")
    hits = _UUID.findall(html)
    if not hits:
        return None
    for u in sorted(set(hits), key=lambda x: -hits.count(x)):
        if (VALIDATE / u / "results.jsonl").exists():
            return u
    return max(set(hits), key=hits.count)


def _run_dir(run_id: str) -> Path | None:
    exact = VALIDATE / run_id
    if exact.exists():
        return exact
    for d in VALIDATE.glob(f"{run_id.split('-')[0]}*"):
        if (d / "results.jsonl").exists():
            return d
    return None


def _set_id(run_dir: Path) -> str:
    ev = run_dir / "events.jsonl"
    if ev.exists():
        for line in ev.read_text().splitlines():
            try:
                o = json.loads(line)
                if o.get("event_type") == "run" and o.get("comparison_set"):
                    return o["comparison_set"]
            except Exception:
                pass
    return run_dir.name[:8]


def _patient_names(run_dir: Path, uuids: set[str]) -> str:
    names: list[str] = []
    man = run_dir / "run_manifest.json"
    book: dict[str, str] = {}
    if man.exists():
        try:
            pats = (json.loads(man.read_text()).get("patients") or {})
            for u, p in pats.items():
                disp = (p or {}).get("display")
                if disp:
                    # "Aloice Mukangu" from "10000X - Aloice Mukangu" or raw display
                    book[u] = disp.split(" - ")[-1].strip()
        except Exception:
            pass
    for u in sorted(uuids):
        names.append(book.get(u, u[:8]))
    return " + ".join(names) if names else "—"


def collect() -> list[dict]:
    cards = []
    for slug_dir in sorted(REPORTS.iterdir()):
        if not slug_dir.is_dir() or not (slug_dir / "index.html").exists():
            continue
        slug = slug_dir.name
        has_dash = (slug_dir / "dashboard.html").exists()
        # meta.run_dir is authoritative (handles judged siblings whose data run_id != dir);
        # fall back to mining the rendered report for a UUID that is a real run dir.
        rdir = None
        meta = slug_dir / "meta.json"
        mobj: dict = {}
        if meta.exists():
            try:
                mobj = json.loads(meta.read_text())
            except Exception:
                mobj = {}
        rd = mobj.get("run_dir") or mobj.get("run_id")
        if rd and (VALIDATE / rd / "results.jsonl").exists():
            rdir = VALIDATE / rd
        if rdir is None:
            run_id = _resolve_run_id(slug_dir)
            rdir = _run_dir(run_id) if run_id else None

        card: dict = {
            "slug": slug,
            "dashboard": has_dash,
            "ts": (slug_dir / "index.html").stat().st_mtime,
            "title": slug,
            "set": None, "cells": None, "arms": [], "patients": None, "scout": [],
            "date": None,
        }
        if mobj.get("generated_at"):
            card["date"] = str(mobj["generated_at"])[:16].replace("T", " ")

        if rdir:
            rows = [json.loads(l) for l in (rdir / "results.jsonl").read_text().splitlines() if l.strip()]
            arms = sorted({r.get("backend_id") for r in rows if r.get("backend_id")})
            pts = {(r.get("request") or {}).get("patient") for r in rows if (r.get("request") or {}).get("patient")}
            card["set"] = _set_id(rdir)
            card["title"] = card["set"]
            card["cells"] = len(rows)
            card["arms"] = arms
            card["patients"] = _patient_names(rdir, pts)
            judge = _load_judge(rdir)
            if judge:
                summ = [s for s in scout_summary(judge, arms) if s["n"]]
                summ.sort(key=lambda s: (s["accuracy_mean"] or 0), reverse=True)
                card["scout"] = summ
            if not card["date"]:
                card["date"] = datetime.fromtimestamp(
                    (rdir / "results.jsonl").stat().st_mtime, timezone.utc
                ).strftime("%Y-%m-%d %H:%M UTC")
        cards.append(card)
    cards.sort(key=lambda c: c["ts"], reverse=True)
    return cards


def _scout_table(scout: list[dict]) -> str:
    if not scout:
        return '<div class="unscored">not scored (answer comparison only)</div>'
    head = ('<table class="scout"><thead><tr><th class="arm">arm</th><th>n</th>'
            '<th>acc</th><th>comp</th><th>rel</th><th>harm</th></tr></thead><tbody>')
    body = []
    for s in scout:
        def f(v):
            return f"{v:.2f}" if isinstance(v, (int, float)) else "—"
        harm = s["harm_count"]
        harm_cell = f'<td class="harm">{harm}</td>' if harm else f"<td>{harm}</td>"
        body.append(
            f'<tr><td class="arm">{escape(s["backend"])}</td><td>{s["n"]}</td>'
            f'<td>{f(s["accuracy_mean"])}</td><td>{f(s["completeness_mean"])}</td>'
            f'<td>{f(s["relevance_mean"])}</td>{harm_cell}</tr>'
        )
    return head + "".join(body) + "</tbody></table>"


def _card_html(c: dict) -> str:
    links = [f'<a class="btn" href="{escape(c["slug"])}/index.html">Report</a>']
    if c["dashboard"]:
        links.append(f'<a class="btn ghost" href="{escape(c["slug"])}/dashboard.html">Dashboard</a>')
    meta = []
    if c["date"]:
        meta.append(f'<div><span class="k">generated</span><span class="v">{escape(c["date"])}</span></div>')
    if c["patients"]:
        meta.append(f'<div><span class="k">patients</span><span class="v">{escape(c["patients"])}</span></div>')
    if c["cells"] is not None:
        meta.append(f'<div><span class="k">cells</span><span class="v">{c["cells"]}</span></div>')
    if c["arms"]:
        meta.append(f'<div><span class="k">arms</span><span class="v">{len(c["arms"])}</span></div>')
    chips = "".join(f'<span class="arm-chip">{escape(a)}</span>' for a in c["arms"])
    return f"""  <article class="card">
  <header class="card-head">
    <div class="titles"><h2>{escape(c["title"])}</h2><div class="slug">{escape(c["slug"])}</div></div>
    <div class="links">{"".join(links)}</div>
  </header>
  <div class="meta-grid">{"".join(meta)}</div>
  <div class="arms">{chips}</div>
  {_scout_table(c["scout"])}
  </article>"""


STYLE = (REPORTS / "index.html").read_text().split("<style>")[1].split("</style>")[0] \
    if (REPORTS / "index.html").exists() else ""


def main() -> None:
    cards = collect()
    n = len(cards)
    body = "\n".join(_card_html(c) for c in cards)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenClinAI — validation runs</title>
<style>{STYLE}
  .unscored {{ color: var(--muted); font-size: 13px; font-style: italic; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="page">
    <h1>OpenClinAI — validation runs</h1>
    <div class="sub"><b>{n}</b> published run{"s" if n != 1 else ""}, newest first.</div>
  </header>
{body}
  <footer class="page">Auto-generated from artifacts/reports/* — every published report appears. Rebuild: scripts/build-reports-index.py</footer>
</div>
</body>
</html>
"""
    out = REPORTS / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({n} cards)")
    for c in cards:
        scored = f"{len(c['scout'])} arms scored" if c["scout"] else "unscored"
        print(f"  {c['slug']:38} {c['set'] or '-':20} {scored}")


if __name__ == "__main__":
    main()
