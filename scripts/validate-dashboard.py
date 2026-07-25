#!/usr/bin/env python3
"""Tiny local dashboard for a live validate run — stdlib only, no installs.

    python3 scripts/validate-dashboard.py        # then open http://localhost:8099

Auto-refreshes every 2s: overall progress, per-arm stats, the GGUF models the
llama-router has resident right now, a
scenario x arm status grid, and a recent feed. Click any grid cell or feed row to
drill into that (scenario, arm): the expected behaviour + every turn's question,
full answer, citations, and metrics. Reads the newest artifacts/validate run.
"""
import glob
import http.server
import json
import os
import re
import socket
import socketserver
import subprocess
import threading
import time
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.validate.model_registry import arm_card, arm_model_name  # noqa: E402  (sys.path set above)
from harness.validate.hub_trace import match_trace, trace_model_for_result  # noqa: E402
from harness.validate.reconcile import combined_judge_summary  # noqa: E402
from harness.validate.review_presentation import (  # noqa: E402
    indepth_validation_display,
    score_formatter_js,
    section_confidence_displays,
    validation_display,
)
from harness.validate.response_artifacts import (  # noqa: E402
    in_depth_artifact,
    prepare_answer_review,
    prepare_indepth_review,
    response_for_displayed_evidence,
    split_answer_sections,
)
from harness.validate.sources import build_sources, load_scenario_chart  # noqa: E402
from harness.validate.stage_timings import extract_stage_timings  # noqa: E402
DATA = ROOT / "datasets" / "validation"
TRACE_FILE = ROOT / "artifacts" / "hub-trace" / "trace.jsonl"
PORT = int(os.environ.get("DASH_PORT", "8099"))


# When set (by --freeze --run), pin the dashboard to one run instead of "newest".
_RUN_OVERRIDE = None


def newest_run():
    if _RUN_OVERRIDE:
        return _RUN_OVERRIDE
    # DASH_RUN pins the dashboard to a specific run (id or path) instead of "newest by mtime" —
    # so side runs (1-cell verifies) don't hijack the view away from the real run being watched.
    pin = os.environ.get("DASH_RUN")
    if pin:
        p = pin if os.path.isabs(pin) or os.path.sep in pin else str(ROOT / "artifacts" / "validate" / pin)
        if os.path.isdir(p):
            return p
    # Rank by when results were last WRITTEN (results.jsonl mtime), not the dir mtime —
    # rebuilding a report.html into an old run dir bumps the dir mtime and would otherwise
    # hijack the live view.
    dirs = [d for d in glob.glob(str(ROOT / "artifacts" / "validate" / "*")) if os.path.isdir(d)]

    def _activity(d):
        rp = os.path.join(d, "results.jsonl")
        return os.path.getmtime(rp) if os.path.exists(rp) else os.path.getmtime(d)

    return max(dirs, key=_activity) if dirs else None


def resident_models():
    try:
        out = subprocess.run(["lsof", "-c", "llama-server"], capture_output=True,
                             text=True, timeout=4).stdout
    except Exception:
        return []
    return sorted(set(re.findall(r"[A-Za-z0-9._-]+\.gguf", out)))


def read_jsonl(p):
    rows = []
    try:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return rows


def read_judge_actors(run):
    actors = {}
    judges_dir = Path(run) / "judges"
    if judges_dir.exists():
        for path in sorted(judges_dir.glob("*/judge.jsonl")):
            rows = read_jsonl(path)
            if rows:
                actors[path.parent.name] = rows
    if not actors:
        rows = read_jsonl(Path(run) / "judge.jsonl")
        if rows:
            actors["canonical"] = rows
    return actors


def _esc(s):
    return (s or "").replace("\n", " ").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def status():
    run = newest_run()
    if not run:
        return {"run": None}
    events = read_jsonl(Path(run) / "events.jsonl")
    run_ev = next((e for e in events if e.get("event_type") == "run"), {})
    set_id = run_ev.get("comparison_set")
    scen_ids = run_ev.get("scenario_ids", [])
    back_ids = run_ev.get("backend_ids", [])
    labels = {e["backend_id"]: e.get("label", "")
              for e in events if e.get("event_type") == "backend_selected"}

    turns = {}
    for sid in scen_ids:
        try:
            turns[sid] = len(json.load(open(DATA / "scenarios" / f"{sid}.json"))["turns"])
        except Exception:
            turns[sid] = 1
    total = sum(turns.values()) * len(back_ids) if back_ids else 0

    results = read_jsonl(Path(run) / "results.jsonl")
    # "Active" = results written recently OR the runner process is still alive. The mtime check
    # alone misses slow tiers — a HIGH cell runs ~17 min writing NOTHING, so results.jsonl looks
    # stale and the run appears dead with no running cell. The process check keeps the frontier
    # cell painted yellow across long per-cell gaps.
    _rp = Path(run) / "results.jsonl"
    try:
        _runner_alive = subprocess.run(
            ["pgrep", "-f", "harness-cli validate run"], capture_output=True).returncode == 0
    except Exception:
        _runner_alive = False
    active = _runner_alive or (_rp.exists() and (time.time() - _rp.stat().st_mtime) < 120)
    arms = {}
    for b in back_ids:
        rs = [r for r in results if r.get("backend_id") == b]
        errs = [r for r in rs if (r.get("metrics") or {}).get("http_status") != 200]
        lat = [(r.get("metrics") or {}).get("latency_ms", 0) for r in rs]
        ch = [(r.get("metrics") or {}).get("answer_chars", 0) for r in rs]
        arms[b] = {"label": labels.get(b, b), "rows": len(rs), "errors": len(errs),
                   "avg_latency_ms": (sum(lat) // len(lat)) if lat else 0,
                   "avg_chars": (sum(ch) // len(ch)) if ch else 0,
                   "last": rs[-1]["scenario_id"] if rs else ""}

    # Cell state per (scenario, backend), aggregating ALL turns of a (multi-turn) scenario:
    #   done    = every expected turn answered (200 + non-empty)  -> green
    #   err     = a turn failed or came back empty                -> red
    #   running = the cell the runner is currently on (active frontier, or a partially
    #             completed multi-turn)                           -> yellow
    #   pending = not started yet                                 -> grey
    cell_rows = {}
    for r in results:
        cell_rows.setdefault((r.get("scenario_id"), r.get("backend_id")), []).append(r)

    def _good(r):
        m = r.get("metrics") or {}
        return m.get("http_status") == 200 and (m.get("answer_chars") or 0) > 0

    states = {}
    for s in scen_ids:
        exp = turns.get(s, 1)
        for b in back_ids:
            rs = cell_rows.get((s, b), [])
            good = sum(1 for r in rs if _good(r))
            bad = sum(1 for r in rs if (r.get("metrics") or {}).get("http_status") not in (200, None))
            if good >= exp:
                st = "done"
            elif bad > 0 or len(rs) >= exp:
                st = "err"          # a failure, or all turns present but some empty
            elif len(rs) > 0:
                st = "running" if active else "err"   # partial: in-flight if active, else abandoned
            else:
                st = "pending"
            states[(s, b)] = st

    # While the run is in progress, the single active cell is the first incomplete one in
    # backend-major order (mirrors the runner) — show it yellow even before its first row lands.
    if total and len(results) < total and active:
        marked = False
        for b in back_ids:
            for s in scen_ids:
                if states[(s, b)] in ("pending", "running"):
                    states[(s, b)] = "running"
                    marked = True
                    break
            if marked:
                break

    grid_list = [{"scenario": s, "backend": b, "state": states[(s, b)]}
                 for s in scen_ids for b in back_ids]

    feed = []
    for r in results[-14:]:
        m = r.get("metrics") or {}
        ind = r.get("indepth") or {}
        iresp = ind.get("response") or {}
        if isinstance(iresp, str):
            try:
                iresp = json.loads(iresp)
            except Exception:
                iresp = {"answer": iresp}
        feed.append({"scenario": r.get("scenario_id"), "backend": r.get("backend_id"),
                     "turn": r.get("turn"), "status": m.get("http_status"),
                     "chars": m.get("answer_chars"),
                     "indepth_status": ind.get("http_status"),
                     "indepth_chars": len((iresp or {}).get("answer") or ""),
                     "ans": _esc(((r.get("response") or {}).get("answer", "") or "")[:90])})

    # Structured arm makeup + config (single and team med-agent-hub profiles) —
    # resolved by the shared resolver, REUSED from the report. Carries the real sampler knobs,
    # per-role system prompts, and retrieval GPs so the dashboard can render the path badge,
    # role->model makeup, and the "how this arm is configured" panel.
    arm_cards = {}
    for b in back_ids:
        try:
            arm_cards[b] = arm_card(b)
        except Exception:
            arm_cards[b] = {"backend_id": b, "label": b, "kind": "unknown",
                            "path": None, "models": [], "roles": {}, "config": {}}

    judge_actors = read_judge_actors(run)

    return {"run": os.path.basename(run), "set": set_id, "done": len(results), "total": total,
            "scenarios": scen_ids, "backends": back_ids, "arms": arms, "arm_cards": arm_cards,
            "judge_actors": sorted(judge_actors.keys()),
            "judge_combined": combined_judge_summary(judge_actors, back_ids),
            "grid": grid_list, "feed": feed, "models": resident_models()}


def detail(scenario, backend):
    run = newest_run()
    if not run or not scenario or not backend:
        return {"turns": []}
    rows = [r for r in read_jsonl(Path(run) / "results.jsonl")
            if r.get("scenario_id") == scenario and r.get("backend_id") == backend]
    rows.sort(key=lambda r: r.get("turn", 0))
    exp = {}
    try:
        exp = json.load(open(DATA / "scenarios" / f"{scenario}.json")).get("expectations", {})
    except Exception:
        pass
    chart_fixture = load_scenario_chart(scenario, DATA / "scenarios", DATA / "charts")
    traces = read_jsonl(TRACE_FILE)
    turns = []
    for r in rows:
        m = r.get("metrics") or {}
        resp = r.get("response") or {}
        request = r.get("request") or {}
        tr = match_trace(
            traces,
            trace_model_for_result(r, arm_model_name(backend)),
            r.get("started_at"),
            r.get("ended_at"),
            question=request.get("question"),
            session=request.get("session"),
            request_id=request.get("request_id"),
        )
        direct_answer, embedded_indepth = split_answer_sections(resp.get("answer"))
        review_artifact = prepare_indepth_review(
            in_depth_artifact(r, resp, embedded_indepth), tr, chart_fixture
        )
        answer_validation = prepare_answer_review(
            resp.get("answerValidation"),
            direct_answer,
            tr,
            chart_fixture,
        )
        evidence_response = response_for_displayed_evidence(
            resp, direct_answer, review_artifact, embedded_indepth
        )
        sources_v1 = build_sources(evidence_response, chart_fixture)
        refs = evidence_response.get("references") or evidence_response.get("citations") or []
        answer_confidence_display, indepth_confidence_display = section_confidence_displays(
            tr, resp.get("confidence")
        )
        ind = r.get("indepth") or {}
        iresp = ind.get("response") or {}
        if isinstance(iresp, str):
            try:
                iresp = json.loads(iresp)
            except Exception:
                iresp = {"answer": iresp}
        turns.append({"turn": r.get("turn"),
                      "question": (r.get("request") or {}).get("question", ""),
                      "answer": direct_answer,
                      "confidence": resp.get("confidence"),
                      "answer_validation": answer_validation,
                      "answer_confidence_display": answer_confidence_display,
                      "indepth_confidence_display": indepth_confidence_display,
                      "answer_validation_display": validation_display(answer_validation),
                      "indepth_validation_display": indepth_validation_display(review_artifact),
                      "product_in_depth": (
                          review_artifact if isinstance(resp.get("inDepth"), dict) else None
                      ),
                      "review_draft": review_artifact.get("reviewDraft") or "",
                      "review_sources": review_artifact.get("reviewSources") or {},
                      "indepth": ({"answer": iresp.get("answer") or "", "status": ind.get("http_status"),
                                   "latency_ms": ind.get("latency_ms")} if ind else None),
                      "blocks": resp.get("blocks") or [],
                      "sources": sources_v1,
                      "refs": refs,
                      "status": m.get("http_status"), "latency_ms": m.get("latency_ms"),
                      "chars": m.get("answer_chars"), "citations": m.get("citation_count"),
                      "error": r.get("error"),
                      "trace": {"answer_confidence": tr.get("answer_confidence"),
                                "indepth_confidence": tr.get("indepth_confidence"),
                                "answer_text": tr.get("answer_text", ""),
                                "in_depth_claims": tr.get("in_depth_claims") or [],
                                "steps": tr.get("steps") or [],
                                "stage_timings": extract_stage_timings(tr),
                                "models": tr.get("models") or {}} if tr else None})
    return {"scenario": scenario, "backend": backend, "expectations": exp, "turns": turns}


PAGE = r"""<!doctype html><html data-theme="dark"><head><meta charset=utf-8><title>validate run</title><style>
html[data-theme="dark"]{color-scheme:dark;--bg:#0d1117;--surface:#161b22;--surface2:#1f2937;--sunken:#0b0f14;--text:#c9d1d9;--muted:#8b949e;--faint:#586069;--border:#30363d;--border2:#21262d;--accent:#79c0ff;--accent2:#58a6ff;--purple:#d2a8ff;--ok:#3fb950;--err:#f85149;--flag:#f0883e;--pend-bg:#1a1f27;--pend-fg:#484f58;--cav-red-bg:#3d1416;--cav-red-bd:#8b1a1a;--cav-red-fg:#ffd0d0;--cav-yel-bg:#3a2e08;--cav-yel-bd:#9e6a03;--cav-yel-fg:#ffe9b3}
html[data-theme="light"]{color-scheme:light;--bg:#f6f8fa;--surface:#ffffff;--surface2:#eef1f5;--sunken:#f0f2f5;--text:#1f2328;--muted:#656d76;--faint:#8c959f;--border:#d0d7de;--border2:#e2e6ea;--accent:#0969da;--accent2:#0969da;--purple:#8250df;--ok:#1a7f37;--err:#cf222e;--flag:#bc4c00;--pend-bg:#eef1f5;--pend-fg:#8c959f;--cav-red-bg:#fff1f1;--cav-red-bd:#cf222e;--cav-red-fg:#a2191f;--cav-yel-bg:#fcf4d6;--cav-yel-bd:#d4a72c;--cav-yel-fg:#684e00}
.theme-toggle{position:fixed;top:14px;right:16px;z-index:50;width:32px;height:32px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;font-size:14px;line-height:1;display:flex;align-items:center;justify-content:center}
.theme-toggle:hover{border-color:var(--accent)}
body{background:var(--bg);color:var(--text);font:13px/1.5 -apple-system,BlinkMacSystemFont,Menlo,monospace;margin:0;padding:18px}
h1{font-size:15px;margin:0 0 6px}.muted{color:var(--muted)}.ok{color:var(--ok)}.err{color:var(--err)}
.bar{height:20px;background:var(--surface);border-radius:10px;overflow:hidden;margin:8px 0}
.bar>div{height:100%;background:linear-gradient(90deg,#1f6feb,#388bfd);transition:width .4s}
.row{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 12px;min-width:160px}
.card b{font-size:13px;color:var(--accent)}
.chip{display:inline-block;background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:2px 11px;margin:3px;color:var(--accent)}
table.grid{border-collapse:collapse;margin-top:6px;font-size:11px;table-layout:fixed}
.grid td,.grid th{border:1px solid var(--border2);padding:3px 6px;text-align:center}
.grid th{color:var(--muted);font-weight:400}
.grid th:first-child,.grid td:first-child{width:210px;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grid th:not(:first-child){width:120px;text-align:center;white-space:normal;vertical-align:bottom;line-height:1.25;font-size:10.5px}
.grid td:not(:first-child){width:120px;text-align:center}
.grid td{cursor:pointer}.grid td:hover{outline:2px solid var(--accent2)}
.c200{background:#196c2e;color:#e6ffe9}.cerr{background:#8b1a1a;color:#ffe9e9}.cpend{background:var(--pend-bg);color:var(--pend-fg);cursor:default}
.crun{background:#9e6a03;color:#ffe9b3;animation:pulse 1.1s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.feed div{padding:2px 0;border-bottom:1px solid var(--border2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.feed div:hover{background:var(--surface)}
section{margin:18px 0}h2{font-size:12px;color:var(--muted);margin:0 0 4px;text-transform:uppercase;letter-spacing:.05em}
#modal{display:none;position:fixed;inset:0;background:rgba(1,4,9,.7);z-index:10;align-items:flex-start;justify-content:center}
#mbody{background:var(--surface);border:1px solid var(--border);border-radius:10px;max-width:820px;width:92%;max-height:88vh;overflow:auto;padding:18px;margin-top:3vh}
.mhead{font-size:14px;margin-bottom:8px}.mhead .x{float:right;cursor:pointer;color:var(--muted);font-size:16px}
.exp{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 10px;margin-bottom:10px;color:var(--purple)}
.turn{border-top:1px solid var(--border2);padding:10px 0}.q{color:var(--accent);margin-bottom:4px}
.meta{font-size:11px;color:var(--muted);margin-bottom:6px}
.ans{white-space:pre-wrap;background:var(--sunken);border:1px solid var(--border2);border-radius:6px;padding:10px}
.refs{font-size:11px;color:var(--muted);margin-top:6px}
.rawrefs{margin-top:7px;border:1px solid var(--border2);border-radius:6px;background:var(--sunken)}
.rawrefs summary{cursor:pointer;color:var(--muted);font-size:11px;padding:5px 8px;list-style:none}
.rawrefs div{padding:0 8px 7px}
.block{margin-top:8px}.btitle{font-size:11px;color:var(--muted);margin-bottom:3px}
table.btbl{border-collapse:collapse;font-size:11px;width:100%}
.btbl td,.btbl th{border:1px solid var(--border2);padding:3px 7px;text-align:left;vertical-align:top}
.btbl th{color:var(--muted);font-weight:400;white-space:nowrap}
.rowrefs{margin-top:2px;color:var(--muted);font-size:10px}
.rowrefs span{display:inline-block;margin-left:3px;padding:0 4px;border-radius:7px;background:var(--surface2);color:var(--accent);font-family:Menlo,monospace}
.sources{margin-top:9px;border-top:1px solid var(--border2);padding-top:7px}
.stitle{font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.sgrid{display:grid;gap:6px}
.scard{border:1px solid var(--border2);border-radius:7px;background:var(--sunken);padding:7px 8px}
.shead{font-size:11px}.shead b{color:var(--accent);font-family:Menlo,monospace}.smeta{font-size:10px;color:var(--muted);margin-top:2px}
.sstat{display:inline-block;margin-left:4px;padding:0 5px;border-radius:8px;background:var(--surface2);color:var(--muted)}
.sstat.ok{color:var(--ok)}.sstat.bad{color:var(--err)}
.scard ul{margin:4px 0 0 16px;padding:0;font-size:11px}.scard details{margin-top:4px;color:var(--muted)}.scard summary{cursor:pointer;font-size:10px}.scard pre{white-space:pre-wrap;font-size:10px;margin:4px 0 0;color:var(--muted)}
.sdiag{margin-top:5px;color:var(--muted);font-size:10px}
.reviewdraft{margin-top:8px;border-left:3px solid var(--err);padding-left:10px}
.reviewdraft>summary{cursor:pointer;color:var(--text);font-size:11px;font-weight:700;padding:4px 0}
.reviewdraft>summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.reviewdraft-note{background:var(--cav-red-bg);color:var(--cav-red-fg);padding:7px 9px;margin:4px 0;font-size:11px}
.reviewdraft.edited{border-left-color:var(--flag)}
.reviewdraft.edited .reviewdraft-note{background:var(--cav-yel-bg);color:var(--cav-yel-fg)}
.reviewrefs{margin-top:7px;color:var(--muted);font-size:10px}.reviewrefs ul{margin:4px 0 0 16px;padding:0}.reviewrefs li{margin:4px 0}.reviewrefs details{margin-top:2px}.reviewrefs summary{cursor:pointer;color:var(--accent)}.reviewrefs pre{white-space:pre-wrap;margin:3px 0 6px}
.tracebox{margin-top:8px;border:1px solid var(--border2);border-radius:6px;background:var(--sunken)}
.tracebox summary{cursor:pointer;color:var(--muted);font-size:11px;padding:6px 10px;list-style:none}
.tracebox summary::-webkit-details-marker{display:none}
.tracebox[open] summary{border-bottom:1px solid var(--border2)}
.trace{padding:8px 10px}
.tdisp{font-size:11px;color:var(--purple);margin-bottom:6px}
.tstep{border:1px solid var(--border2);border-radius:6px;padding:6px 8px;background:var(--bg)}
.trole{font-size:10px;color:var(--accent);text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px}
.trole.flag{color:var(--flag)}.trole.ok{color:var(--ok)}
.tmodel{color:var(--faint);text-transform:none;letter-spacing:0;margin-left:5px}
.tbody{font-size:11px;white-space:pre-wrap;color:var(--text)}
.tarrow{text-align:center;color:var(--border);font-size:11px;line-height:1.1;margin:1px 0}
.notrace{font-size:11px;color:var(--faint);padding:8px 10px}
.stage-timings{margin:7px 0;border:1px solid var(--border2);border-radius:6px;background:var(--sunken)}
.stage-timings summary{cursor:pointer;color:var(--accent);font-size:11px;padding:5px 8px}
.stage-timings table{width:100%;border-collapse:collapse;font-size:11px}
.stage-timings td,.stage-timings th{padding:3px 8px;border-top:1px solid var(--border2);text-align:left}
.cchip{display:inline-block;padding:1px 7px;border-radius:10px;color:#fff;font-size:10px;margin-left:6px;vertical-align:middle}
.csec{margin-top:8px}
.ctitle{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.caveat{border-radius:6px;padding:8px 10px;font-size:12px;margin:4px 0}
.caveat.red{background:var(--cav-red-bg);border:1px solid var(--cav-red-bd);color:var(--cav-red-fg)}
.caveat.yellow{background:var(--cav-yel-bg);border:1px solid var(--cav-yel-bd);color:var(--cav-yel-fg)}
.collapse summary{cursor:pointer;color:var(--muted);font-size:11px;padding:3px 0;list-style:revert}
.idl{margin:2px 0 0 0;padding-left:18px}.idl li{margin:2px 0}
.arm-cards{display:flex;flex-wrap:wrap;gap:10px}
.arm-card{flex:1 1 240px;min-width:220px;border:1px solid var(--border);border-radius:8px;padding:10px 12px;background:var(--surface)}
.arm-head{display:flex;align-items:center;gap:7px;margin-bottom:4px}
.arm-name{font-weight:600;color:var(--accent);font-size:12px;line-height:1.25;white-space:normal}
.arm-id{font-family:ui-monospace,Menlo,monospace;font-size:10px;color:var(--faint);margin:0 0 4px}
.badge{display:inline-block;font-size:9px;font-weight:700;letter-spacing:.05em;padding:1px 6px;border-radius:9px;border:1px solid var(--border);color:var(--muted)}
.badge.team{background:#3a2e08;border-color:#9e6a03;color:#ffe9b3}
.badge.single{background:#13304a;border-color:#1f6feb;color:#cfe6ff}
.arm-path{font-size:10px;color:var(--muted);margin-bottom:5px}
.arm-stats{font-size:11px;color:var(--text);margin-bottom:6px}
table.makeup{width:100%;font-size:11px;background:transparent;border-collapse:collapse}
.makeup td{padding:2px 4px;border:none;text-align:left}
.makeup .role{color:var(--muted);width:28%}
.makeup .mdl{font-family:ui-monospace,Menlo,monospace}
.makeup .mq{color:var(--muted)}
.makeup-single{font-size:12px;color:var(--muted);font-family:ui-monospace,Menlo,monospace;margin-top:4px}
details.arm-config{margin-top:8px;border-top:1px dashed var(--border);padding-top:6px}
details.arm-config>summary{cursor:pointer;color:var(--accent);font-size:11px;font-weight:600;list-style:revert}
.arm-config .ac-tease{color:var(--muted);font-weight:400;font-size:10px;font-family:ui-monospace,Menlo,monospace}
.arm-config .ac-body{margin-top:8px}
.arm-config .ac-h{font-size:11px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:.03em;margin:10px 0 4px}
.arm-config .ac-h:first-child{margin-top:0}
.arm-config .ac-sub,.arm-config .ac-src{font-weight:400;text-transform:none;color:var(--muted);font-size:10px;font-family:ui-monospace,Menlo,monospace;letter-spacing:0}
table.ac-knobs{border-collapse:collapse;font-size:10.5px;margin-top:2px}
.ac-knobs td,.ac-knobs th{border:1px solid var(--border2);padding:2px 7px;text-align:left}
.ac-knobs th{color:var(--muted);font-weight:400;white-space:nowrap}
.ac-knobs .ac-k{color:var(--muted)}
.judge-table{border-collapse:collapse;font-size:11px;background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden;min-width:min(900px,100%)}
.judge-table th,.judge-table td{border:1px solid var(--border2);padding:5px 8px;text-align:left;vertical-align:top}
.judge-table th{color:var(--muted);font-weight:600;background:var(--sunken)}
.judge-table .score{font-weight:700;color:var(--accent);font-size:12px}
.judge-note{font-size:11px;color:var(--muted);margin:0 0 6px;max-width:88ch}
.arm-config .ac-prompt{margin:4px 0 8px}
.arm-config .ac-plabel{font-size:11px;font-weight:600}
.arm-config .ac-psum{font-size:11px;color:var(--muted);margin:2px 0;max-width:60ch}
.arm-config .ac-pfull>summary{cursor:pointer;color:var(--accent);font-size:10px;list-style:revert}
.arm-config pre.ac-pre{white-space:pre-wrap;font:10.5px/1.45 ui-monospace,Menlo,monospace;background:var(--sunken);border:1px solid var(--border2);border-radius:6px;padding:8px 10px;margin:4px 0 0;max-height:16em;overflow:auto}
.arm-config .ac-retr{font-size:11px;font-family:ui-monospace,Menlo,monospace;color:var(--text)}
</style><script>(function(){try{var t=localStorage.getItem('oc-theme-dashboard');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;}catch(e){}})();</script></head><body>
<button id=theme-toggle class=theme-toggle type=button aria-label="Toggle light or dark mode" title="Toggle light / dark"></button>
<h1 id=hdr>validate run</h1>
<div class=bar><div id=fill style=width:0%></div></div>
<div id=prog class=muted></div>
<section><h2>Models resident (llama-router)</h2><div id=models></div></section>
<section><h2>Arms</h2><div class=row id=arms></div></section>
<section><h2>Judged scores</h2><div id=judges></div></section>
<section><h2>Scenario &times; arm &nbsp;<span class=muted>(click a cell)</span></h2><div id=grid></div></section>
<section><h2>Recent &nbsp;<span class=muted>(click a row)</span></h2><div class=feed id=feed></div></section>
<div id=modal onclick="if(event.target===this)closeD()"><div id=mbody></div></div>
<script>
const cls=s=>({done:'c200',err:'cerr',running:'crun',pending:'cpend'}[s]||'cpend');
const sym=s=>({done:'✓',err:'×',running:'●',pending:'·'}[s]||'·');
// Human-readable arm titles from the resolver's arm_cards (model_registry), never the raw dashed
// backend id. Filled each tick from the latest /api/status. armTitle = full; armShort = tight
// grid/column variant. Fall back to the raw id only if a card is missing.
let ARM_CARDS={};
const armTitle=b=>{const c=ARM_CARDS[b];return (c&&c.title)||b;};
const armShort=b=>{const c=ARM_CARDS[b];return (c&&(c.short_title||c.title))||b;};
const shortB=b=>armShort(b);
const esc=s=>(s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
__SHARED_SCORE_FORMATTER__
// sampler-knob display order + labels (mirrors report.py's KNOB_ORDER/KNOB_LABELS).
const KNOB_ORDER=['temp','top_p','top_k','ctx_size','seed','max_tokens','reasoning_budget','dry'];
const KNOB_LABELS={temp:'temperature',top_p:'top-p',top_k:'top-k',ctx_size:'ctx-size',seed:'seed',max_tokens:'max-tokens',reasoning_budget:'reasoning-budget',dry:'DRY'};
// "how this arm is configured" panel: sampling knobs + system prompt(s) + retrieval line.
// Mirrors report.py::renderArmConfig — fed the REAL arm_card(b).config from the resolver.
// `key` is a STABLE per-arm id (the backend_id) so OPEN_DETAILS can re-apply the open state
// across the background re-render that would otherwise collapse the panel.
function renderArmConfig(cfg,key){
 if(!cfg) return '';
 const knobs=cfg.knobs||{};
 const models=Object.keys(knobs);
 const k0=(models.length?knobs[models[0]]:{})||{};
 const tease=[];
 if(k0.temp!=null)tease.push('temp '+k0.temp);
 if(k0.seed!=null)tease.push('seed '+k0.seed);
 if(k0.dry!=null)tease.push('DRY on');
 if(k0.ctx_size!=null)tease.push('ctx '+k0.ctx_size);
 const np=(cfg.prompts||[]).length;
 if(np)tease.push(np+' system prompt'+(np>1?'s':''));
 const teaseTxt=tease.length?(' — '+tease.join(' · ')):'';
 let h="<details class=arm-config data-okey='cfg:"+esc(key)+"'><summary>how this arm is configured<span class=ac-tease>"+esc(teaseTxt)+"</span></summary><div class=ac-body>";
 if(models.length){
  const present=KNOB_ORDER.filter(k=>models.some(m=>(knobs[m]||{})[k]!=null));
  h+="<div class=ac-h>sampling knobs <span class=ac-sub>(llama-router.ini)</span></div>";
  h+="<table class=ac-knobs><thead><tr><th>knob</th>";
  models.forEach(m=>{h+="<th>"+esc(m)+"</th>";});
  h+="</tr></thead><tbody>";
  present.forEach(k=>{
   h+="<tr><td class=ac-k>"+esc(KNOB_LABELS[k]||k)+"</td>";
   models.forEach(m=>{const v=(knobs[m]||{})[k];h+="<td>"+(v==null?'—':esc(v))+"</td>";});
   h+="</tr>";
  });
  h+="</tbody></table>";
 }
 const prompts=cfg.prompts||[];
 if(prompts.length){
  h+="<div class=ac-h>system prompt"+(prompts.length>1?'s':'')+"</div>";
  prompts.forEach((p,i)=>{
   h+="<div class=ac-prompt>";
   h+="<div class=ac-plabel>"+esc(p.label)+" <span class=ac-src>"+esc(p.source)+"</span></div>";
   if(p.summary)h+="<div class=ac-psum>"+esc(p.summary)+"</div>";
   h+="<details class=ac-pfull data-okey='prompt:"+esc(key)+":"+i+"'><summary>full prompt</summary><pre class=ac-pre>"+esc(p.text)+"</pre></details>";
   h+="</div>";
  });
 }
 const r=cfg.retrieval;
 if(r){
  h+="<div class=ac-h>retrieval <span class=ac-sub>(chartsearchai GPs)</span></div>";
  h+="<div class=ac-retr>pipeline "+esc(r.pipeline)+" · embedding top-k "+esc(r.embedding_topk)+
     " · querystore top-k "+esc(r.querystore_topk)+" · threshold "+esc(r.threshold)+"</div>";
 }
 h+="</div></details>";
 return h;
}
// Per-arm card: single/team path badge + makeup (team role->model; single family·params·quant)
// + the config panel. Mirrors report.py::renderArms. Fed status().arm_cards (REUSED resolver).
function renderArmCards(d){
 const cards=d.arm_cards||{};
 const stats=d.arms||{};
 let h="<div class=arm-cards>";
 (d.backends||[]).forEach(b=>{
  const c=cards[b]||{kind:'unknown',path:'',models:[],roles:{}};
  const a=stats[b]||{};
  const team=c.kind==='team';
  const badge=team
   ?"<span class='badge team'>TEAM</span>"
   :(c.kind==='single'?"<span class='badge single'>SINGLE</span>":"<span class=badge>?</span>");
  // Headline = the resolver's human-readable title; the raw backend_id survives only as a
  // tiny muted monospace sub-label under it, never as the headline.
  const title=c.title||b;
  h+="<div class=arm-card>";
  h+="<div class=arm-head>"+badge+"<span class=arm-name>"+esc(title)+"</span></div>";
  h+="<div class=arm-id>"+esc(b)+"</div>";
  if(c.path)h+="<div class=arm-path>"+esc(c.path)+"</div>";
  h+="<div class=arm-stats>"+(a.rows||0)+" rows · <span class='"+(a.errors?'err':'ok')+"'>"+(a.errors||0)+" err</span>"
    +" · <span class=muted>~"+(a.avg_latency_ms||0)+"ms · "+(a.avg_chars||0)+"c"+(a.last?(' · '+esc(a.last)):'')+"</span></div>";
  if(team){
   // Makeup = role → readable family·params·quant; the raw dashed model id column is dropped.
   h+="<table class=makeup><tbody>";
   Object.keys(c.roles||{}).forEach(role=>{
    const m=c.roles[role]||{};
    const mq=[m.family,m.params,m.quant].filter(Boolean).join(' · ');
    h+="<tr><td class=role>"+esc(role)+"</td><td class=mq>"+esc(mq)+"</td></tr>";
   });
   h+="</tbody></table>";
  }else{
   const m=(c.models||[])[0]||{};
   const mq=[m.family,m.params,m.quant].filter(Boolean).join(' · ');
   h+="<div class=makeup-single>"+esc(mq)+"</div>";
  }
  h+=renderArmConfig(c.config,b);
  h+="</div>";
 });
 return h+"</div>";
}
function renderJudgeScores(d){
 const rows=(d.judge_combined||[]).filter(s=>(s.n_actors||0)>=1&&s.benchmark_score!=null)
  .sort((a,b)=>(b.benchmark_score||0)-(a.benchmark_score||0));
 if(!rows.length)return '<span class=muted>no judged score yet</span>';
 const actors=(d.judge_actors||[]).join(', ');
 const multi=rows.some(s=>(s.n_actors||0)>1);
 let note=multi
  ?'Combined = each cell averaged across independent judges, then averaged per arm. Range and max Δ show judge disagreement.'
  :'Score from one independent judge. Add another judge to show disagreement ranges.';
 let h='<p class=judge-note>'+note+' Actors: '+esc(actors)+'</p>';
 h+='<table class=judge-table><thead><tr><th>setup</th><th>score</th><th>actors</th><th>cell range</th><th>actor range</th><th>mean Δ/cell</th><th>max Δ cell</th></tr></thead><tbody>';
 rows.forEach(s=>{
  const ar=s.actor_range||{}, sp=s.benchmark_spread||{};
  const maxCell=s.max_cell_delta_scenario?(esc(s.max_cell_delta_scenario)+' · '+fmt10(s.max_cell_delta)):'—';
  h+='<tr><td title="'+esc(s.backend)+'">'+esc(armTitle(s.backend))+'</td>'
   +'<td><span class=score>'+fmt10(s.benchmark_score)+'</span></td>'
   +'<td>'+(s.n_actors||0)+'</td>'
   +'<td>'+(sp.min==null?'—':fmt10(sp.min)+'–'+fmt10(sp.max))+'</td>'
   +'<td>'+(ar.min==null?'—':fmt10(ar.min)+'–'+fmt10(ar.max))+'</td>'
   +'<td>'+fmt10(s.mean_abs_delta)+'</td><td>'+maxCell+'</td></tr>';
 });
 return h+'</tbody></table>';
}
// The background poll re-renders #arms wholesale; that wipes the user's expanded <details>.
// Track which panels are open by their STABLE data-okey (arm backend_id, NOT a DOM index),
// updated on every toggle, and re-apply after each re-render so an open config / full-prompt
// panel survives auto-refresh. Parallel: the data refresh no longer clobbers UI state.
const OPEN_DETAILS=new Set();
document.addEventListener('toggle',e=>{
 const d=e.target;
 if(!d||d.tagName!=='DETAILS')return;
 const k=d.getAttribute&&d.getAttribute('data-okey');
 if(!k)return;
 if(d.open)OPEN_DETAILS.add(k);else OPEN_DETAILS.delete(k);
},true);
function restoreOpenDetails(root){
 (root||document).querySelectorAll('details[data-okey]').forEach(d=>{
  d.open=OPEN_DETAILS.has(d.getAttribute('data-okey'));
 });
}
async function tick(){
 let d; try{d=await(await fetch('/api/status')).json()}catch(e){return}
 if(!d.run){hdr.textContent='waiting for a run...';return}
 ARM_CARDS=d.arm_cards||{};
 const pct=d.total?Math.round(100*d.done/d.total):0;
 hdr.textContent='run '+d.run.slice(0,8)+'  ·  set '+(d.set||'')+'  ·  '+pct+'%';
 fill.style.width=pct+'%'; prog.textContent=d.done+' / '+d.total+' results';
 models.innerHTML=(d.models||[]).map(m=>'<span class=chip>'+m+'</span>').join('')||'<span class=muted>none resident</span>';
 arms.innerHTML=renderArmCards(d);
 restoreOpenDetails(arms);   // re-apply the user's expanded config/full-prompt panels after the re-render
 judges.innerHTML=renderJudgeScores(d);
 const gm={};(d.grid||[]).forEach(g=>gm[g.scenario+'|'+g.backend]=g.state);
 let h='<table class=grid><tr><th></th>'+(d.backends||[]).map(b=>'<th title="'+esc(b)+'">'+esc(armTitle(b))+'</th>').join('')+'</tr>';
 (d.scenarios||[]).forEach(s=>{h+='<tr><th>'+s+'</th>'+(d.backends||[]).map(b=>{const st=gm[s+'|'+b];
   const oc=(st==null||st==='pending')?'':' onclick="openD(\''+s+'\',\''+b+'\')"';
   return '<td class='+cls(st)+oc+'>'+sym(st)+'</td>'}).join('')+'</tr>'});
 grid.innerHTML=h+'</table>';
 feed.innerHTML=(d.feed||[]).slice().reverse().map(f=>'<div onclick="openD(\''+f.scenario+'\',\''+f.backend+'\')"><span class="'
   +(f.status===200?'ok':'err')+'">'+f.status+'</span> '+f.scenario+'/'+shortB(f.backend)+' t'+f.turn
   +' <span class=muted>'+f.chars+'c</span>'
   +(f.indepth_status!=null?' <span class="'+(f.indepth_status===200&&f.indepth_chars>0?'ok':'err')+'" title="In-Depth (separate call)">+ID '+f.indepth_chars+'c</span>':'')
   +' '+f.ans+'</div>').join('');
}
function srcLabels(sources){
 const out={}; ((sources&&sources.sources)||[]).forEach(s=>{ if(s.record_index!=null) out[s.record_index]=s.source_id; });
 return out;
}
function rowRefLabels(row, labels){
 const seen={}, out=[]; const cells=(row&&row.cells)||{};
 Object.keys(cells).forEach(k=>((cells[k]&&cells[k].refs)||[]).forEach(r=>{ const x=labels[r]||('['+r+']'); if(!seen[x]){seen[x]=1;out.push(x);} }));
 return out;
}
function renderBlocks(blocks,sources){
 if(!blocks||!blocks.length)return '';
 const labels=srcLabels(sources);
 return blocks.map(bl=>{
  if(bl.kind!=='table')return '';
  const cols=bl.columns||[];
  const head=cols.map(c=>'<th>'+esc(c.label||c.key||'')+'</th>').join('');
  const body=(bl.rows||[]).map(row=>{
   const cells=row.cells||{};
   const rr=rowRefLabels(row,labels);
   const rf=rr.length?'<div class=rowrefs>sources '+rr.map(x=>'<span>'+esc(x)+'</span>').join('')+'</div>':'';
   return '<tr>'+cols.map((c,i)=>{
    const cell=cells[c.key]||{};
    const txt=esc(cell.text!=null?String(cell.text):'');
    return '<td>'+txt+(i===0?rf:'')+'</td>';
   }).join('')+'</tr>';
  }).join('');
  const title=bl.title?'<div class=btitle>'+esc(bl.title)+'</div>':'';
  return '<div class=block>'+title+'<table class=btbl><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>';
 }).join('');
}
function renderSources(sources){
 const ss=(sources&&sources.sources)||[], d=(sources&&sources.diagnostics)||{};
 if(!ss.length&&!(d.malformed_tokens&&d.malformed_tokens.length))return '';
 function card(s){
  const meta=[s.resource_type,s.date].filter(Boolean).map(esc).join(' · ');
  const facts=(s.facts_used&&s.facts_used.length?s.facts_used:[s.source_text||s.title||'']).slice(0,4);
  const st=s.resolution_status||'unknown';
  const cite=s.citation_index||s.record_index||'?';
  const chart=s.chart_record_index||s.record_index||'?';
  const support=s.support_status||'unchecked';
  return '<div class=scard><div class=shead><b>'+esc(s.source_id||'')+'</b> cite ['+esc(cite)+'] · chart ['+esc(chart)+'] '+esc(s.title||'')+'</div>'
   +'<div class=smeta>'+meta+' <span class="sstat '+(st==='resolved'?'ok':(st==='unresolved'?'bad':''))+'">chart ref '+esc(st)+'</span> <span class=sstat>support '+esc(support)+'</span></div>'
   +'<ul>'+facts.map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul>'
   +'<details><summary>open source record</summary><pre>'+esc(s.source_text||'')+'</pre></details></div>';
 }
 let h='<div class=sources><div class=stitle>Evidence Used</div><div class=sgrid>'+ss.slice(0,5).map(card).join('')+'</div>';
 if(ss.length>5)h+='<details><summary>show all sources</summary>'+ss.slice(5).map(card).join('')+'</details>';
 const bits=[]; ['unresolved_refs','unused_top_refs','nested_only_refs','malformed_tokens'].forEach(k=>{ if(d[k]&&d[k].length)bits.push(k+': '+JSON.stringify(d[k])); });
 if(bits.length)h+='<div class=sdiag>'+esc(bits.join(' · '))+'</div>';
 return h+'</div>';
}
function renderRawRefs(refs){
 if(!refs||!refs.length)return '';
 return '<details class=rawrefs><summary>raw resolved refs</summary><div>'+esc(refs.map(r=>typeof r==='object'?('['+(r.index!=null?r.index:'?')+'] '+(r.resourceType||'')):('['+r+']')).join('  '))+'</div></details>';
}
const CONF_COLORS={green:'#196c2e',yellow:'#9e6a03',red:'#8b1a1a'};
function chip(display){
 if(!display) return '';
 const color=CONF_COLORS[display.level]||'#30363d';
 return '<span class=cchip style="background:'+color+'">'+esc(display.label||'Unrated')+'</span>';
}
function validationChip(display){
 if(!display) return '';
 const cls=display.tone==='danger'?' bad':(display.tone==='warning'?' warm':'');
 return '<span class="chip'+cls+'">'+esc(display.label||display.status||'')+'</span>';
}
// A confidence flag adds context but never hides the model output a reviewer needs to inspect.
function confSection(title, bodyHtml, display, lifecycle){
 const note=(display&&display.note)||'', treatment=(display&&display.note_treatment)||'none';
 let h='<div class=csec><div class=ctitle>'+title+' '+chip(display)+' '+validationChip(lifecycle)+'</div>';
 if(treatment==='prominent'){
  if(note) h+='<div class="caveat red">'+esc(note)+'</div>';
  h+='<div class=ans>'+bodyHtml+'</div>';
 }else if(treatment==='collapsible'){
  h+='<div class=ans>'+bodyHtml+'</div>';
  if(note) h+='<details class=collapse><summary>show review note</summary><div class="caveat yellow">'+esc(note)+'</div></details>';
 }else{
  h+='<div class=ans>'+bodyHtml+'</div>';
 }
 return h+'</div>';
}
function renderReviewDraft(draft, sourcesV1){
 if(!draft) return '';
 const sources=(sourcesV1&&sourcesV1.sources)||[];
 const sourceRows=sources.map(s=>{
  const idx=s.citation_index!=null?s.citation_index:(s.record_index!=null?s.record_index:'?');
  const label=[s.date,s.resource_type,s.title,s.resolution_status].filter(Boolean).join(' · ');
  const record=s.source_text?'<details><summary>open draft source</summary><pre>'+esc(s.source_text)+'</pre></details>':'';
  return '<li><b>['+esc(String(idx))+']</b> '+esc(label)+record+'</li>';
 }).join('');
 const sourceHtml=sourceRows?'<div class=reviewrefs><b>Draft sources for review (not final evidence)</b><ul>'+sourceRows+'</ul></div>':'';
 return '<details class=reviewdraft><summary>Removed In-Depth claims</summary>'
  +'<div class=reviewdraft-note>These model-generated claims were removed or withheld by checks. They are shown only for manual review and are not part of the final clinical response.</div>'
  +'<div class=ans>'+esc(draft)+'</div>'+sourceHtml+'</details>';
}
function renderOriginalAnswer(validation,currentAnswer){
 const originalBlocks=(validation&&validation.originalBlocks)||[];
 const hasOriginalReferenceArtifact=!!validation&&(
  Object.prototype.hasOwnProperty.call(validation,'originalReferences')||
  Object.prototype.hasOwnProperty.call(validation,'originalSources')
 );
 if(!validation||!validation.originalAnswer||(validation.originalAnswer.trim()===(currentAnswer||'').trim()&&!originalBlocks.length&&!hasOriginalReferenceArtifact)) return '';
 const edited=validation.status==='edited';
 const notice=edited
  ?'This answer or its supporting citations was changed by the answer check. The checked answer above is the current result.'
  :'This was the model output before checking. The current answer above remains flagged for review.';
 const sources=((validation.originalSources||{}).sources)||[];
 const sourceRows=sources.map(s=>{
  const idx=s.citation_index!=null?s.citation_index:(s.record_index!=null?s.record_index:'?');
  const label=[s.date,s.resource_type,s.title,s.resolution_status].filter(Boolean).join(' · ');
  const record=s.source_text?'<details><summary>open original source</summary><pre>'+esc(s.source_text)+'</pre></details>':'';
  return '<li><b>['+esc(String(idx))+']</b> '+esc(label)+record+'</li>';
 }).join('');
 const sourceHtml=sourceRows?'<div class=reviewrefs><b>Original-answer sources (not final evidence)</b><ul>'+sourceRows+'</ul></div>':'';
 return '<details open class="reviewdraft'+(edited?' edited':'')+'"><summary>Original model answer</summary>'
  +'<div class=reviewdraft-note>'+notice+'</div>'
  +'<div class=ans>'+esc(validation.originalAnswer)+renderBlocks(originalBlocks,validation.originalSources||{})+'</div>'+sourceHtml+'</details>';
}
function renderTrace(tr){
 if(!tr) return '<div class=notrace>no reasoning trace captured for this turn (hub trace off, or older run)</div>';
 const fmt=s=>{
  if(s.role==='orchestrator') return ['orchestrator','tools: '+((s.tool_calls||[]).join(', ')||'(none — straight to synthesis)')];
  if(s.role==='kb_search') return ['kb_search',(s.hit?'HIT':'miss')+(s.fallback?' (deterministic fallback)':'')+' · '+esc(s.query||'')+' · '+(s.chars||0)+'c'];
  if(s.role==='medical_expert') return ['medical_expert',esc(s.note||'')];
  if(s.role==='answer_synth') return ['answer synth',esc(s.output||'')+(s.citations&&s.citations.length?'  ['+s.citations.join(',')+']':'')];
  if(s.role==='answer_resynth') return ['answer re-synth',esc(s.output||'')];
  if(s.role==='answer_validator') return ['answer validator'+(s.attempt?' #'+s.attempt:''),(s.answer_ok?'PASS':'FLAG')+(s.answer_issues?' · '+esc(s.answer_issues):''),s.answer_ok?'ok':(s.answer_issues?'flag':'')];
  if(s.role==='indepth_synth') return ['in-depth synth',((s.claims||[]).map(c=>'• '+esc(c)).join('<br>')||'(no claims)')];
  if(s.role==='indepth_resynth') return ['in-depth re-synth',((s.claims||[]).map(c=>'• '+esc(c)).join('<br>')||'(no claims)')];
  if(s.role==='indepth_validator') return ['in-depth validator'+(s.attempt?' #'+s.attempt:''),'drop '+JSON.stringify(s.drop||[])+' of '+(s.claims_in||0)+(s.issues?' · '+esc(s.issues):''),(s.drop&&s.drop.length)?'flag':'ok'];
  return [s.role,esc(JSON.stringify(s))];
 };
 const steps=(tr.steps||[]).filter(s=>s.role!=='stage_timing').map(s=>{
  const [label,body,tone]=fmt(s);
  const cls='trole'+(tone==='flag'?' flag':(tone==='ok'?' ok':''));
  const m=s.model?'<span class=tmodel>'+esc(s.model)+'</span>':'';
  return '<div class=tstep><div class="'+cls+'">'+esc(label)+m+'</div><div class=tbody>'+body+'</div></div>';
 }).join('<div class=tarrow>↓</div>');
 return '<div class=trace>'+(steps||'<div class=notrace>no steps</div>')+'</div>';
}
function renderStageTimings(rows){
 if(!rows||!rows.length) return '';
 const body=rows.map(r=>'<tr><td>'+esc(String(r.stage||'').replaceAll('_',' ')+(r.occurrence>1?' '+r.occurrence:''))+'</td><td>'+r.duration_ms+' ms</td><td>'+esc(r.status||'completed')+'</td></tr>').join('');
 return '<details class=stage-timings open><summary>stage timing breakdown</summary><table><thead><tr><th>stage</th><th>elapsed</th><th>status</th></tr></thead><tbody>'+body+'</tbody></table></details>';
}
async function openD(s,b){
 const d=await(await fetch('/api/detail?scenario='+encodeURIComponent(s)+'&backend='+encodeURIComponent(b))).json();
 const e=d.expectations||{};
 let h='<div class=mhead><b>'+s+'</b> &nbsp;·&nbsp; '+b+'<span class=x onclick="closeD()">✕</span></div>';
 h+='<div class=exp><b>Expected:</b> '+(e.should_abstain?'ABSTAIN':'retrieve')+(e.should_cite_resource_types?' ['+e.should_cite_resource_types.join(', ')+']':'')+'<br>'+esc(e.notes||'')+'</div>';
 (d.turns||[]).forEach(t=>{
  const tr=t.trace;
  const answerConf=t.answer_confidence_display;
  const indepthConf=t.indepth_confidence_display;
  const answerLifecycle=t.answer_validation_display;
  const indepthLifecycle=t.indepth_validation_display;
  h+='<div class=turn><div class=q>Turn '+t.turn+': '+esc(t.question)+'</div>';
  h+='<div class=meta><span class="'+(t.status===200?'ok':'err')+'">status '+t.status+'</span> · '+(t.latency_ms||0)+'ms · '+(t.chars||0)+' chars · '+(t.citations||0)+' source refs</div>';
  h+=renderStageTimings(tr&&tr.stage_timings);
  if(t.error){
   h+='<div class="ans err">'+esc(t.error)+'</div>';
  }else if(answerConf||indepthConf||answerLifecycle||indepthLifecycle){
   // Structured render with confidence and lifecycle details kept adjacent to visible output.
   const blocksHtml=renderBlocks(t.blocks,t.sources);
   h+=confSection('Answer', esc(t.answer||(tr&&tr.answer_text)||'')+blocksHtml, answerConf, answerLifecycle);
   h+=renderOriginalAnswer(t.answer_validation,t.answer||(tr&&tr.answer_text)||'');
   // In-Depth: two-call arms carry it as a SEPARATE call (row.indepth), single-pass, no validator —
   // render THAT, not the Answer trace's empty in_depth_claims + the Answer's verdict as a stray chip.
   if(t.indepth){
    const ia=(t.indepth.answer||'').trim();
    const body=ia?esc(ia):'<span class=muted>(no elaboration — e.g. an abstain)</span>';
    h+='<div class=csec><div class=ctitle>In Depth <span class=muted>(separate call'+(t.indepth.latency_ms?', '+Math.round(t.indepth.latency_ms/1000)+'s':'')+')</span></div><div class=ans>'+body+'</div></div>';
   }else if(t.product_in_depth){
    const native=t.product_in_depth, finalDraft=(native.answer||'').trim();
    if(finalDraft){
     h+=confSection('In Depth',esc(finalDraft),indepthConf,indepthLifecycle);
    }else if(native.status){
     h+='<div class=csec><div class=ctitle>In Depth '+validationChip(indepthLifecycle)+'</div>'
      +'<div class="caveat red">'+esc(native.error||'No In-Depth content was displayed.')+'</div></div>';
    }
    const draft=(t.review_draft||'').trim();
    if(draft&&draft!==finalDraft) h+=renderReviewDraft(draft,t.review_sources);
   }else{
    const cl=(tr&&tr.in_depth_claims)||[];
    const idConf=indepthConf||{};
    const showId=cl.length||idConf.note||(idConf.level&&idConf.level!=='green');
    if(showId){
     const idb=cl.length?'<ul class=idl>'+cl.map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul>':'<span class=muted>(none)</span>';
     h+=confSection('In Depth', idb, indepthConf, indepthLifecycle);
    }
   }
  }else{
   h+='<div class=ans>'+esc(t.answer)+'</div>';   // Answer (raw envelope / non-team backend)
   h+=renderOriginalAnswer(t.answer_validation,t.answer||'');
   if(t.product_in_depth){
    const native=t.product_in_depth, finalDraft=(native.answer||'').trim();
    if(finalDraft) h+='<div class=csec><div class=ctitle>In Depth</div><div class=ans>'+esc(finalDraft)+'</div></div>';
    else if(native.status) h+='<div class=csec><div class=ctitle>In Depth</div><div class="caveat red">'+esc(native.error||native.status)+'</div></div>';
    const draft=(t.review_draft||'').trim();
    if(draft&&draft!==finalDraft) h+=renderReviewDraft(draft,t.review_sources);
   }
   if(t.indepth&&t.indepth.answer){               // two-call arms: the separate In-Depth call
    h+='<div style="margin-top:8px;font-size:11px;font-weight:600;color:var(--accent)">In Depth <span class=muted>(separate call'+(t.indepth.latency_ms?', '+Math.round(t.indepth.latency_ms/1000)+'s':'')+')</span></div>';
    h+='<div class=ans>'+esc(t.indepth.answer)+'</div>';
   }
   h+=renderBlocks(t.blocks,t.sources);
  }
  h+=renderSources(t.sources);
  h+=renderRawRefs(t.refs);
  h+='<details class=tracebox><summary>▸ reasoning trace</summary>'+renderTrace(tr)+'</details>';
  h+='</div>';
 });
 mbody.innerHTML=h; modal.style.display='flex';
}
function closeD(){modal.style.display='none'}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeD()});
tick();setInterval(tick,2000);
(function(){var b=document.getElementById('theme-toggle');function s(){b.textContent=document.documentElement.dataset.theme==='dark'?'☀':'☾';}s();b.addEventListener('click',function(){var n=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=n;try{localStorage.setItem('oc-theme-dashboard',n);}catch(e){}s();});})();
</script></body></html>"""
PAGE = PAGE.replace("__SHARED_SCORE_FORMATTER__", score_formatter_js())


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/api/detail"):
            q = parse_qs(urlparse(self.path).query)
            payload = detail(q.get("scenario", [""])[0], q.get("backend", [""])[0])
            body = json.dumps(payload).encode()
            ctype = "application/json"
        elif self.path.startswith("/api/status"):
            body = json.dumps(status()).encode()
            ctype = "application/json"
        else:
            body = PAGE.encode()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Server(socketserver.ThreadingTCPServer):
    # Threaded + daemon threads: a slow request (e.g. a cell-click detail() that reads the growing
    # trace) must never block the 2s /api/status poll — that single-threaded stall made the live
    # page look frozen / "down".
    allow_reuse_address = True
    daemon_threads = True


class _ServerV6(_Server):
    address_family = socket.AF_INET6


def serve_dashboard():
    servers = []
    for cls, addr in ((_Server, "127.0.0.1"), (_ServerV6, "::1")):
        try:
            servers.append(cls((addr, PORT), H))
        except OSError as exc:
            print(f"warn: could not bind dashboard on {addr}:{PORT}: {exc}", file=sys.stderr)
    if not servers:
        raise SystemExit(f"could not bind dashboard on port {PORT}")
    print(f"validate dashboard -> http://localhost:{PORT}   (Ctrl-C to stop)")
    for srv in servers[1:]:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        servers[0].serve_forever()
    finally:
        for srv in servers:
            srv.server_close()


def freeze(out_path):
    """Write a SELF-CONTAINED snapshot of the dashboard for the current run: the exact live
    page, but with the /api/status payload + every cell's /api/detail payload embedded inline
    and window.fetch shimmed to serve them. The grid, click-to-drill detail, reasoning traces,
    confidence chips — full functionality — work offline from a single .html (no server). The
    2s auto-refresh just re-renders the frozen data (no network)."""
    st = status()
    if not st.get("run"):
        raise SystemExit("no run to snapshot")
    details = {}
    for g in st.get("grid", []):
        if g.get("state") in ("done", "err", "running"):  # cells that have results
            s, b = g["scenario"], g["backend"]
            details[f"{s}|{b}"] = detail(s, b)
    shim = (
        "<script>\n"
        "window.__STATUS__=" + json.dumps(st) + ";\n"
        "window.__DETAIL__=" + json.dumps(details) + ";\n"
        "(function(){var of=window.fetch;window.fetch=function(u,o){u=String(u);\n"
        "  if(u.indexOf('/api/status')>-1){return Promise.resolve({json:function(){return Promise.resolve(window.__STATUS__);}});}\n"
        "  if(u.indexOf('/api/detail')>-1){var q=new URLSearchParams((u.split('?')[1]||''));\n"
        "    var k=q.get('scenario')+'|'+q.get('backend');\n"
        "    return Promise.resolve({json:function(){return Promise.resolve(window.__DETAIL__[k]||{turns:[]});}});}\n"
        "  return of?of(u,o):Promise.reject('offline snapshot');};})();\n"
        "</script>\n"
    )
    # Inject the shim BEFORE the page's own <script> so the fetch override is in place first.
    html = PAGE.replace("<script>", shim + "<script>", 1)
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"frozen dashboard snapshot -> {out_path}  ({st['done']}/{st['total']} results, {len(details)} cells embedded)")


if __name__ == "__main__":
    import sys
    if "--freeze" in sys.argv:
        i = sys.argv.index("--freeze")
        out = sys.argv[i + 1] if i + 1 < len(sys.argv) else "dashboard-snapshot.html"
        if "--run" in sys.argv:
            j = sys.argv.index("--run")
            _RUN_OVERRIDE = os.path.abspath(sys.argv[j + 1])
        freeze(out)
    else:
        serve_dashboard()
