#!/usr/bin/env python3
"""Tiny local dashboard for a live validate run — stdlib only, no installs.

    python3 scripts/validate-dashboard.py        # then open http://localhost:8099

Auto-refreshes every 2s: overall progress, per-arm stats, the GGUF models the
llama-router has resident right now (lsof — the LM-Studio-style view), a
scenario x arm status grid, and a recent feed. Click any grid cell or feed row to
drill into that (scenario, arm): the expected behaviour + every turn's question,
full answer, citations, and metrics. Reads the newest artifacts/validate run.
"""
import datetime as _datetime
import glob
import http.server
import json
import os
import re
import socketserver
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasets" / "validation"
TRACE_FILE = ROOT / "artifacts" / "hub-trace" / "trace.jsonl"
PORT = int(os.environ.get("DASH_PORT", "8099"))


def _parse_iso(s):
    try:
        return _datetime.datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _match_trace(traces, backend, started_at, ended_at):
    """Correlate a results cell to its hub reasoning-trace: same level_id (== backend id) and the
    trace ts inside the cell's [started_at, ended_at] window (the runner is strictly sequential).
    A few seconds of slack absorbs container/host clock rounding. Returns the latest match, or None."""
    st, en = _parse_iso(started_at), _parse_iso(ended_at)
    if not st or not en:
        return None
    slack = _datetime.timedelta(seconds=5)
    lo, hi = st - slack, en + slack
    best = None
    for tr in traces:
        if tr.get("level_id") != backend:
            continue
        ts = _parse_iso(tr.get("ts", ""))
        if ts and lo <= ts <= hi:
            best = tr  # keep the latest match within the window
    return best


def newest_run():
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
    # A run is "active" only if its results were written in the last ~2 min; a stopped run
    # shouldn't paint any cell yellow.
    _rp = Path(run) / "results.jsonl"
    active = _rp.exists() and (time.time() - _rp.stat().st_mtime) < 120
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
        feed.append({"scenario": r.get("scenario_id"), "backend": r.get("backend_id"),
                     "turn": r.get("turn"), "status": m.get("http_status"),
                     "chars": m.get("answer_chars"),
                     "ans": _esc(((r.get("response") or {}).get("answer", "") or "")[:90])})

    return {"run": os.path.basename(run), "set": set_id, "done": len(results), "total": total,
            "scenarios": scen_ids, "backends": back_ids, "arms": arms,
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
    traces = read_jsonl(TRACE_FILE)
    turns = []
    for r in rows:
        m = r.get("metrics") or {}
        resp = r.get("response") or {}
        refs = resp.get("references") or resp.get("citations") or []
        tr = _match_trace(traces, backend, r.get("started_at"), r.get("ended_at"))
        turns.append({"turn": r.get("turn"),
                      "question": (r.get("request") or {}).get("question", ""),
                      "answer": resp.get("answer", ""),
                      "blocks": resp.get("blocks") or [],
                      "refs": refs,
                      "status": m.get("http_status"), "latency_ms": m.get("latency_ms"),
                      "chars": m.get("answer_chars"), "citations": m.get("citation_count"),
                      "error": r.get("error"),
                      "trace": {"answer_confidence": tr.get("answer_confidence"),
                                "indepth_confidence": tr.get("indepth_confidence"),
                                "answer_text": tr.get("answer_text", ""),
                                "in_depth_claims": tr.get("in_depth_claims") or [],
                                "steps": tr.get("steps") or [],
                                "models": tr.get("models") or {}} if tr else None})
    return {"scenario": scenario, "backend": backend, "expectations": exp, "turns": turns}


PAGE = r"""<!doctype html><html><head><meta charset=utf-8><title>validate run</title><style>
body{background:#0d1117;color:#c9d1d9;font:13px/1.5 -apple-system,BlinkMacSystemFont,Menlo,monospace;margin:0;padding:18px}
h1{font-size:15px;margin:0 0 6px}.muted{color:#8b949e}.ok{color:#3fb950}.err{color:#f85149}
.bar{height:20px;background:#161b22;border-radius:10px;overflow:hidden;margin:8px 0}
.bar>div{height:100%;background:linear-gradient(90deg,#1f6feb,#388bfd);transition:width .4s}
.row{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 12px;min-width:160px}
.card b{font-size:13px;color:#79c0ff}
.chip{display:inline-block;background:#1f2937;border:1px solid #30363d;border-radius:12px;padding:2px 11px;margin:3px;color:#79c0ff}
table.grid{border-collapse:collapse;margin-top:6px;font-size:11px;table-layout:fixed}
.grid td,.grid th{border:1px solid #21262d;padding:3px 6px;text-align:center}
.grid th{color:#8b949e;font-weight:400;white-space:nowrap}
.grid th:first-child,.grid td:first-child{width:210px;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grid th:not(:first-child),.grid td:not(:first-child){width:84px;text-align:center}
.grid td{cursor:pointer}.grid td:hover{outline:2px solid #58a6ff}
.c200{background:#196c2e;color:#e6ffe9}.cerr{background:#8b1a1a;color:#ffe9e9}.cpend{background:#1a1f27;color:#484f58;cursor:default}
.crun{background:#9e6a03;color:#ffe9b3;animation:pulse 1.1s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.feed div{padding:2px 0;border-bottom:1px solid #161b22;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.feed div:hover{background:#161b22}
section{margin:18px 0}h2{font-size:12px;color:#8b949e;margin:0 0 4px;text-transform:uppercase;letter-spacing:.05em}
#modal{display:none;position:fixed;inset:0;background:rgba(1,4,9,.7);z-index:10;align-items:flex-start;justify-content:center}
#mbody{background:#0d1117;border:1px solid #30363d;border-radius:10px;max-width:820px;width:92%;max-height:88vh;overflow:auto;padding:18px;margin-top:3vh}
.mhead{font-size:14px;margin-bottom:8px}.mhead .x{float:right;cursor:pointer;color:#8b949e;font-size:16px}
.exp{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 10px;margin-bottom:10px;color:#d2a8ff}
.turn{border-top:1px solid #21262d;padding:10px 0}.q{color:#79c0ff;margin-bottom:4px}
.meta{font-size:11px;color:#8b949e;margin-bottom:6px}
.ans{white-space:pre-wrap;background:#0b0f14;border:1px solid #21262d;border-radius:6px;padding:10px}
.refs{font-size:11px;color:#8b949e;margin-top:6px}
.block{margin-top:8px}.btitle{font-size:11px;color:#8b949e;margin-bottom:3px}
table.btbl{border-collapse:collapse;font-size:11px;width:100%}
.btbl td,.btbl th{border:1px solid #21262d;padding:3px 7px;text-align:left;vertical-align:top}
.btbl th{color:#8b949e;font-weight:400;white-space:nowrap}
.btbl .cref{color:#586069;font-size:10px;margin-left:3px}
.tracebox{margin-top:8px;border:1px solid #21262d;border-radius:6px;background:#0b0f14}
.tracebox summary{cursor:pointer;color:#8b949e;font-size:11px;padding:6px 10px;list-style:none}
.tracebox summary::-webkit-details-marker{display:none}
.tracebox[open] summary{border-bottom:1px solid #21262d}
.trace{padding:8px 10px}
.tdisp{font-size:11px;color:#d2a8ff;margin-bottom:6px}
.tstep{border:1px solid #21262d;border-radius:6px;padding:6px 8px;background:#0d1117}
.trole{font-size:10px;color:#79c0ff;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px}
.trole.flag{color:#f0883e}.trole.ok{color:#3fb950}
.tmodel{color:#586069;text-transform:none;letter-spacing:0;margin-left:5px}
.tbody{font-size:11px;white-space:pre-wrap;color:#c9d1d9}
.tarrow{text-align:center;color:#30363d;font-size:11px;line-height:1.1;margin:1px 0}
.notrace{font-size:11px;color:#586069;padding:8px 10px}
.cchip{display:inline-block;padding:1px 7px;border-radius:10px;color:#fff;font-size:10px;margin-left:6px;vertical-align:middle}
.csec{margin-top:8px}
.ctitle{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.caveat{border-radius:6px;padding:8px 10px;font-size:12px;margin:4px 0}
.caveat.red{background:#3d1416;border:1px solid #8b1a1a;color:#ffd0d0}
.caveat.yellow{background:#3a2e08;border:1px solid #9e6a03;color:#ffe9b3}
.collapse summary{cursor:pointer;color:#8b949e;font-size:11px;padding:3px 0;list-style:revert}
.idl{margin:2px 0 0 0;padding-left:18px}.idl li{margin:2px 0}
</style></head><body>
<h1 id=hdr>validate run</h1>
<div class=bar><div id=fill style=width:0%></div></div>
<div id=prog class=muted></div>
<section><h2>Models resident (llama-router)</h2><div id=models></div></section>
<section><h2>Arms</h2><div class=row id=arms></div></section>
<section><h2>Scenario &times; arm &nbsp;<span class=muted>(click a cell)</span></h2><div id=grid></div></section>
<section><h2>Recent &nbsp;<span class=muted>(click a row)</span></h2><div class=feed id=feed></div></section>
<div id=modal onclick="if(event.target===this)closeD()"><div id=mbody></div></div>
<script>
const cls=s=>({done:'c200',err:'cerr',running:'crun',pending:'cpend'}[s]||'cpend');
const sym=s=>({done:'✓',err:'×',running:'●',pending:'·'}[s]||'·');
const shortB=b=>b.replace('med-agent-team-','').replace('-baseline','-base');
const esc=s=>(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
async function tick(){
 let d; try{d=await(await fetch('/api/status')).json()}catch(e){return}
 if(!d.run){hdr.textContent='waiting for a run...';return}
 const pct=d.total?Math.round(100*d.done/d.total):0;
 hdr.textContent='run '+d.run.slice(0,8)+'  ·  set '+(d.set||'')+'  ·  '+pct+'%';
 fill.style.width=pct+'%'; prog.textContent=d.done+' / '+d.total+' results';
 models.innerHTML=(d.models||[]).map(m=>'<span class=chip>'+m+'</span>').join('')||'<span class=muted>none resident</span>';
 arms.innerHTML=(d.backends||[]).map(b=>{const a=d.arms[b]||{};
   return '<div class=card><b>'+b+'</b><br>'+(a.rows||0)+' rows · <span class="'+(a.errors?'err':'ok')+'">'+(a.errors||0)+' err</span>'
   +'<br><span class=muted>~'+(a.avg_latency_ms||0)+'ms · '+(a.avg_chars||0)+' chars</span>'
   +'<br><span class=muted>'+(a.last||'')+'</span></div>'}).join('');
 const gm={};(d.grid||[]).forEach(g=>gm[g.scenario+'|'+g.backend]=g.state);
 let h='<table class=grid><tr><th></th>'+(d.backends||[]).map(b=>'<th>'+shortB(b)+'</th>').join('')+'</tr>';
 (d.scenarios||[]).forEach(s=>{h+='<tr><th>'+s+'</th>'+(d.backends||[]).map(b=>{const st=gm[s+'|'+b];
   const oc=(st==null||st==='pending')?'':' onclick="openD(\''+s+'\',\''+b+'\')"';
   return '<td class='+cls(st)+oc+'>'+sym(st)+'</td>'}).join('')+'</tr>'});
 grid.innerHTML=h+'</table>';
 feed.innerHTML=(d.feed||[]).slice().reverse().map(f=>'<div onclick="openD(\''+f.scenario+'\',\''+f.backend+'\')"><span class="'
   +(f.status===200?'ok':'err')+'">'+f.status+'</span> '+f.scenario+'/'+shortB(f.backend)+' t'+f.turn
   +' <span class=muted>'+f.chars+'c</span> '+f.ans+'</div>').join('');
}
function renderBlocks(blocks){
 if(!blocks||!blocks.length)return '';
 return blocks.map(bl=>{
  if(bl.kind!=='table')return '';
  const cols=bl.columns||[];
  const head=cols.map(c=>'<th>'+esc(c.label||c.key||'')+'</th>').join('');
  const body=(bl.rows||[]).map(row=>{
   const cells=row.cells||{};
   return '<tr>'+cols.map(c=>{
    const cell=cells[c.key]||{};
    const txt=esc(cell.text!=null?String(cell.text):'');
    const rf=(cell.refs&&cell.refs.length)?'<span class=cref>['+cell.refs.join('][')+']</span>':'';
    return '<td>'+txt+rf+'</td>';
   }).join('')+'</tr>';
  }).join('');
  const title=bl.title?'<div class=btitle>'+esc(bl.title)+'</div>':'';
  return '<div class=block>'+title+'<table class=btbl><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>';
 }).join('');
}
const CONF={green:['High confidence','#196c2e'],yellow:['Medium confidence','#9e6a03'],red:['Low confidence','#8b1a1a']};
function chip(level){const c=CONF[level]||['unrated','#30363d'];return '<span class=cchip style="background:'+c[1]+'">'+c[0]+'</span>';}
// Per-section render with the confidence inversion: red -> caveat shown, message collapsed;
// yellow -> message shown, caveat collapsed; green -> message, no caveat.
function confSection(title, bodyHtml, conf){
 const level=(conf&&conf.level)||'green', note=(conf&&conf.note)||'';
 let h='<div class=csec><div class=ctitle>'+title+' '+chip(level)+'</div>';
 if(level==='red'){
  if(note) h+='<div class="caveat red">'+esc(note)+'</div>';
  h+='<details class=collapse><summary>show '+title.toLowerCase()+'</summary><div class=ans>'+bodyHtml+'</div></details>';
 }else if(level==='yellow'){
  h+='<div class=ans>'+bodyHtml+'</div>';
  if(note) h+='<details class=collapse><summary>show review note</summary><div class="caveat yellow">'+esc(note)+'</div></details>';
 }else{
  h+='<div class=ans>'+bodyHtml+'</div>';
 }
 return h+'</div>';
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
 const steps=(tr.steps||[]).map(s=>{
  const [label,body,tone]=fmt(s);
  const cls='trole'+(tone==='flag'?' flag':(tone==='ok'?' ok':''));
  const m=s.model?'<span class=tmodel>'+esc(s.model)+'</span>':'';
  return '<div class=tstep><div class="'+cls+'">'+esc(label)+m+'</div><div class=tbody>'+body+'</div></div>';
 }).join('<div class=tarrow>↓</div>');
 return '<div class=trace>'+(steps||'<div class=notrace>no steps</div>')+'</div>';
}
async function openD(s,b){
 const d=await(await fetch('/api/detail?scenario='+encodeURIComponent(s)+'&backend='+encodeURIComponent(b))).json();
 const e=d.expectations||{};
 let h='<div class=mhead><b>'+s+'</b> &nbsp;·&nbsp; '+b+'<span class=x onclick="closeD()">✕</span></div>';
 h+='<div class=exp><b>Expected:</b> '+(e.should_abstain?'ABSTAIN':'retrieve')+(e.should_cite_resource_types?' ['+e.should_cite_resource_types.join(', ')+']':'')+'<br>'+esc(e.notes||'')+'</div>';
 (d.turns||[]).forEach(t=>{
  const tr=t.trace;
  h+='<div class=turn><div class=q>Turn '+t.turn+': '+esc(t.question)+'</div>';
  h+='<div class=meta><span class="'+(t.status===200?'ok':'err')+'">status '+t.status+'</span> · '+(t.latency_ms||0)+'ms · '+(t.chars||0)+' chars · '+(t.citations||0)+' citations</div>';
  if(t.error){
   h+='<div class="ans err">'+esc(t.error)+'</div>';
  }else if(tr&&(tr.answer_confidence||tr.indepth_confidence)){
   // structured render with the per-section confidence inversion (chips + collapse)
   h+=confSection('Answer', esc(tr.answer_text||''), tr.answer_confidence);
   const cl=tr.in_depth_claims||[];
   const idb=cl.length?'<ul class=idl>'+cl.map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul>':'<span class=muted>(none)</span>';
   h+=confSection('In Depth', idb, tr.indepth_confidence);
  }else{
   h+='<div class=ans>'+esc(t.answer)+'</div>';   // fallback: raw envelope (non-team backend / older run)
  }
  h+=renderBlocks(t.blocks);
  if(t.refs&&t.refs.length)h+='<div class=refs>refs: '+esc(t.refs.map(r=>typeof r==='object'?('['+(r.index!=null?r.index:'?')+'] '+(r.resourceType||'')):('['+r+']')).join('  '))+'</div>';
  h+='<details class=tracebox><summary>▸ reasoning trace</summary>'+renderTrace(tr)+'</details>';
  h+='</div>';
 });
 mbody.innerHTML=h; modal.style.display='flex';
}
function closeD(){modal.style.display='none'}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeD()});
tick();setInterval(tick,2000);
</script></body></html>"""


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


if __name__ == "__main__":
    print(f"validate dashboard -> http://localhost:{PORT}   (Ctrl-C to stop)")
    _Server(("127.0.0.1", PORT), H).serve_forever()
