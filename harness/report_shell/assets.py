"""Shared CSS/JS string constants for report-family HTML shells."""

from __future__ import annotations

# --- Theme toggle (dashboard / index fixed control; report uses btn-ghost variant) ---

THEME_TOGGLE_CSS = (
    ".theme-toggle{position:fixed;top:14px;right:16px;z-index:50;width:34px;height:34px;"
    "border-radius:8px;border:1px solid var(--border, var(--line));"
    "background:var(--panel, var(--surface));color:var(--text, var(--fg));"
    "cursor:pointer;font-size:15px;line-height:1;display:flex;align-items:center;"
    "justify-content:center;}"
    ".theme-toggle:hover{border-color:var(--accent);}"
)

THEME_TOGGLE_BUTTON_HTML = (
    "<button id='theme-toggle' class='theme-toggle' type='button' "
    "aria-label='Toggle light or dark mode' title='Toggle light / dark'></button>"
)
# Alias used by dashboard/index theme marker tests.
THEME_TOGGLE_BUTTON = THEME_TOGGLE_BUTTON_HTML


def theme_bootstrap_js(storage_key: str) -> str:
    """Inline script: apply stored light/dark theme before first paint."""
    return (
        "(function(){try{var t=localStorage.getItem('"
        + storage_key
        + "');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;}"
        "catch(e){}})();"
    )


def theme_toggle_js(storage_key: str) -> str:
    """Inline script: wire #theme-toggle and persist preference."""
    return (
        "(function(){var b=document.getElementById('theme-toggle');if(!b)return;"
        "function s(){b.textContent=document.documentElement.dataset.theme==='dark'?'☀':'☾';}"
        "s();b.addEventListener('click',function(){"
        "var n=document.documentElement.dataset.theme==='dark'?'light':'dark';"
        "document.documentElement.dataset.theme=n;"
        "try{localStorage.setItem('"
        + storage_key
        + "',n);}catch(e){}s();});})();"
    )


THEME_CSS_VARS = """
html[data-theme="light"] { color-scheme:light; --fg:#1a1a1a; --mut:#666; --line:#e2e2e2; --bg:#fafafa; --surface:#fff; --surface2:#f3f3f3; --accent:#2748a0; --accent-bg:#eef3ff; --accent-bd:#c7d6f5; --accent-hover:#dce6fb; --banner-bg:#f0f6ff; --note-bg:#f6f8fa; --arrow-bg:rgba(255,255,255,.9); --bp-fill:rgba(39,72,160,.14); --bp-grid:#eef0f3; --err:#a01; }
html[data-theme="dark"] { color-scheme:dark; --fg:#c9d1d9; --mut:#8b949e; --line:#30363d; --bg:#0d1117; --surface:#161b22; --surface2:#1c2230; --accent:#79c0ff; --accent-bg:rgba(56,139,253,.13); --accent-bd:#30466b; --accent-hover:rgba(56,139,253,.22); --banner-bg:#11233f; --note-bg:#1c2230; --arrow-bg:rgba(22,27,34,.9); --bp-fill:rgba(121,192,255,.18); --bp-grid:#21262d; --err:#f85149; }
"""

SORTABLE_TABLE_CSS = """/* Sortable-table header affordances (UX research: W3C APG / Roselli). The label is a real
   <button> (free keyboard); the active column shows aria-sort + a solid ▲/▼; the glyph is
   aria-hidden (state lives in aria-sort). */
th button.th-sort { font: inherit; font-weight: 600; color: inherit; background: none; border: 0; padding: 0; margin: 0; cursor: pointer; display: inline-flex; align-items: baseline; gap: 4px; width: 100%; text-align: inherit; }
th button.th-sort:hover { color: var(--accent); }
th button.th-sort:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
th .sort-ind { font-size: 9px; color: var(--accent); min-width: .8em; }
th[aria-sort] { background: var(--accent-bg); }
th[aria-sort] button.th-sort { color: var(--accent); }
"""

BOXPLOT_CSS = """.boxplot-wrap { flex: 1 1 300px; min-width: 280px; max-width: 460px; border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px; background: var(--surface); }
.boxplot { width: 100%; height: auto; }
.bp-title { font-size: 12px; font-weight: 600; fill: var(--fg); }
.bp-grid { stroke: var(--bp-grid); stroke-width: 1; }
.bp-ytick { font-size: 9px; fill: var(--mut); text-anchor: end; }
.bp-xtick { font-size: 10px; fill: var(--fg); text-anchor: middle; }
.bp-xn { font-size: 8.5px; fill: var(--mut); text-anchor: middle; }
.bp-box { fill: var(--bp-fill); stroke: var(--accent); stroke-width: 1.3; }
.bp-median { stroke: var(--accent); stroke-width: 2.2; }
.bp-mean { stroke: #d9730d; stroke-width: 1.4; stroke-dasharray: 3 2; }
.bp-whisker, .bp-cap { stroke: var(--accent); stroke-width: 1; }
.bp-out { fill: none; stroke: #d9730d; stroke-width: 1; opacity: .85; }
.bp-clip { fill: #d9730d; }
.bp-clipnote { font-size: 8.5px; fill: #d9730d; }
"""

CHIP_CSS = """.chips { margin-top: 6px; }
.chip { display: inline-block; font-size: 10px; font-family: ui-monospace, monospace; background: var(--surface2); color: var(--mut); padding: 1px 5px; border-radius: 3px; margin: 1px; }
.chip.warm { background: #fff3d6; color: #8a5a00; }
.chip.none { background: #fde8e8; color: #a01; }
.chip.bad { background: #a01; color: #fff; }
"""

SHARED_JS_DEPS = r"""/* Helpers the shared JS below calls. They used to be defined only by one
   caller, so every other page that shipped SORTABLE_TABLE_JS threw a
   ReferenceError mid-sort -- after the header had been emptied. A page that
   defines its own keeps it; this is a no-op there. */
if (typeof htmlEsc !== 'function') {
  function htmlEsc(s){ return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;'); }
}
"""

SORTABLE_TABLE_JS = r"""/* ---- sortable tables (every data table) ----
   UX research (W3C APG sortable-table, Adrian Roselli, NN/g): each header label
   wraps a real <button> (free keyboard + focus), aria-sort sits ONLY on the active
   <th> (omit "none" — inconsistently announced), the ▲/▼ glyph is aria-hidden (state
   lives in aria-sort), columns auto-detect numeric vs text, missing/"—"/"n/a" cells
   always sink to the bottom regardless of direction, and a polite live-region
   announces the new sort for the screen readers that don't auto-read aria-sort. */
function sortAnnounce(msg){
  var lr=document.getElementById('sort-live'); if(!lr) return;
  lr.textContent=''; setTimeout(function(){ lr.textContent=msg; }, 30);
}
function cellSortVal(td){
  var raw=((td&&td.textContent)||'').trim();
  if(raw===''||raw==='—'||raw==='-'||raw==='n/a'||raw==='N/A') return {missing:true, num:NaN, txt:''};
  // a leading number (handles "123 ms", "89.8", "1.2k" via the k-suffix) drives numeric sort
  var m=raw.replace(/,/g,'').match(/^[+-]?\d*\.?\d+/);
  var num=m?parseFloat(m[0])*(/\dk\b/i.test(raw)?1000:1):NaN;
  return {missing:false, num:num, txt:raw.toLowerCase()};
}
function makeSortable(t){
  var heads=t.querySelectorAll('thead th');
  // Detect, per column, whether the body cells are predominantly numeric.
  var bodyRows=Array.prototype.slice.call(t.querySelectorAll('tbody tr'));
  for(var ci=0;ci<heads.length;ci++){ (function(th, col){
    var label=th.textContent; th.innerHTML='';
    var btn=document.createElement('button'); btn.type='button'; btn.className='th-sort';
    btn.innerHTML=htmlEsc(label)+" <span class='sort-ind' aria-hidden='true'></span>";
    th.appendChild(btn);
    btn.addEventListener('click', function(){
      var tb=t.querySelector('tbody'), rows=Array.prototype.slice.call(tb.querySelectorAll('tr'));
      var asc=th.getAttribute('aria-sort')==='ascending' ? false : true;   // toggle; new column -> ascending
      // numeric column if every present cell parses to a number
      var numeric=rows.length>0 && rows.every(function(r){ var v=cellSortVal(r.children[col]); return v.missing||!isNaN(v.num); });
      rows.sort(function(a,b){
        var x=cellSortVal(a.children[col]), y=cellSortVal(b.children[col]);
        if(x.missing&&y.missing) return 0;
        if(x.missing) return 1;   // missing always sinks to the bottom...
        if(y.missing) return -1;  // ...regardless of asc/desc
        var r = numeric ? (x.num-y.num) : x.txt.localeCompare(y.txt, undefined, {numeric:true});
        return asc?r:-r;
      });
      rows.forEach(function(r){ tb.appendChild(r); });
      // clear every header's sort state, then mark only this one
      for(var h=0;h<heads.length;h++){ heads[h].removeAttribute('aria-sort'); var si=heads[h].querySelector('.sort-ind'); if(si) si.textContent=''; }
      th.setAttribute('aria-sort', asc?'ascending':'descending');
      var ind=th.querySelector('.sort-ind'); if(ind) ind.textContent=asc?'▲':'▼';
      sortAnnounce(label.trim()+', sorted '+(asc?'ascending':'descending'));
    });
  })(heads[ci], ci); }
}

"""

BOXPLOT_JS = r"""function bpNiceCeil(v){ if(v<=0) return 1; var p=Math.pow(10,Math.floor(Math.log10(v))); var f=v/p; var nf=f<=1?1:(f<=2?2:(f<=5?5:10)); return nf*p; }
function bpFmt(v){ v=Math.round(v); return v>=1000?((v/1000).toFixed(v>=10000?0:1)+'k'):String(v); }
// Box plot with a ROBUST, outlier-clipped y-axis (UX research: clip to the Tukey
// fence / p95 so one extreme value can't squish every box — Observable/Datawrapper/
// ggplot2). axisMax (precomputed server-side as the max upper-whisker, ≥ global p95)
// is the clip ceiling; any point above it is CLAMPED to the top edge as a ▲ caret
// (visually distinct from the in-range ○ outlier dots) and counted into a "N beyond X
// not shown" footnote — clipped honestly, never silently dropped.
function boxPlotSVG(label, md){
  var series=md.series||[];
  var H=232, padL=46, padR=12, padT=22, padB=52, plotH=H-padT-padB;
  var W=Math.max(320, 70+series.length*92);
  var i, s, o;
  // Robust ceiling from the server, with safe fallbacks; round up to a nice tick value.
  var rawMax=md.axis_max||0;
  if(rawMax<=0){ for(i=0;i<series.length;i++){ s=series[i]; rawMax=Math.max(rawMax, s.whisker_hi||0, s.median||0); } }
  var nm=bpNiceCeil(rawMax||1);
  function Y(v){ var c=Math.min(v, nm); return padT + plotH - (c/nm)*plotH; }
  var step=(W-padL-padR)/series.length;
  var g='<svg viewBox="0 0 '+W+' '+H+'" class="boxplot" role="img" aria-label="'+htmlEsc(label)+'">';
  g+='<text x="'+padL+'" y="13" class="bp-title">'+htmlEsc(label)+'</text>';
  var ticks=[0,0.25,0.5,0.75,1], t, yy, val;
  for(t=0;t<ticks.length;t++){ val=nm*ticks[t]; yy=Y(val); g+='<line x1="'+padL+'" y1="'+yy+'" x2="'+(W-padR)+'" y2="'+yy+'" class="bp-grid"/>'; g+='<text x="'+(padL-5)+'" y="'+(yy+3)+'" class="bp-ytick">'+bpFmt(val)+'</text>'; }
  var clipN=0, clipMax=0;   // count + furthest value clamped above the axis ceiling
  for(i=0;i<series.length;i++){
    s=series[i];
    var cx=padL+step*i+step/2, bw=Math.min(42, step*0.52), x0=cx-bw/2, x1=cx+bw/2;
    g+='<line x1="'+cx+'" y1="'+Y(s.whisker_lo)+'" x2="'+cx+'" y2="'+Y(s.whisker_hi)+'" class="bp-whisker"/>';
    g+='<line x1="'+(x0+7)+'" y1="'+Y(s.whisker_hi)+'" x2="'+(x1-7)+'" y2="'+Y(s.whisker_hi)+'" class="bp-cap"/>';
    g+='<line x1="'+(x0+7)+'" y1="'+Y(s.whisker_lo)+'" x2="'+(x1-7)+'" y2="'+Y(s.whisker_lo)+'" class="bp-cap"/>';
    g+='<rect x="'+x0+'" y="'+Y(s.q3)+'" width="'+bw+'" height="'+Math.max(1,Y(s.q1)-Y(s.q3))+'" class="bp-box"/>';
    g+='<line x1="'+x0+'" y1="'+Y(s.median)+'" x2="'+x1+'" y2="'+Y(s.median)+'" class="bp-median"/>';
    g+='<line x1="'+x0+'" y1="'+Y(s.mean)+'" x2="'+x1+'" y2="'+Y(s.mean)+'" class="bp-mean"/>';
    for(o=0;o<(s.outliers||[]).length;o++){
      var ov=s.outliers[o];
      if(ov>nm){ clipN++; clipMax=Math.max(clipMax, ov);
        // off-scale: a ▲ caret pinned just inside the top edge, distinct from the in-range dot
        g+='<path d="M'+(cx-3.4)+' '+(padT+5)+' L'+(cx+3.4)+' '+(padT+5)+' L'+cx+' '+(padT-0.5)+' Z" class="bp-clip"><title>'+htmlEsc(bpShort(s.backend)+': '+bpFmt(ov)+' (off scale)')+'</title></path>';
      } else {
        g+='<circle cx="'+cx+'" cy="'+Y(ov)+'" r="2.1" class="bp-out"/>';
      }
    }
    g+='<text x="'+cx+'" y="'+(H-26)+'" class="bp-xtick">'+htmlEsc(bpShort(s.backend))+'</text>';
    g+='<text x="'+cx+'" y="'+(H-15)+'" class="bp-xn">n'+s.n+' · md '+bpFmt(s.median)+'</text>';
  }
  if(clipN>0){
    g+='<text x="'+padL+'" y="'+(H-3)+'" class="bp-clipnote">▲ '+clipN+' outlier'+(clipN>1?'s':'')+' beyond '+bpFmt(nm)+' (max '+bpFmt(clipMax)+') — axis clipped, not shown to scale</text>';
  }
  g+='</svg>';
  var wrap=el('div','boxplot-wrap'); wrap.innerHTML=g; return wrap;
}
"""

SHARED_CSS = THEME_CSS_VARS + SORTABLE_TABLE_CSS + BOXPLOT_CSS + CHIP_CSS
SHARED_JS = SORTABLE_TABLE_JS + BOXPLOT_JS
