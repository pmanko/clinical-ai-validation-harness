"""Test-only helper for exercising canonical `openclinai.org/reports/assets/` shells
against pure `openclinai.report.v2` and `openclinai.dashboard.v2` JSON packets.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

REPORTS_ASSETS = Path(__file__).resolve().parents[4] / "reports" / "assets"
REPORT_SHELL_CSS = (REPORTS_ASSETS / "report-shell.css").read_text(encoding="utf-8")
REPORT_SHELL_JS = (REPORTS_ASSETS / "report-shell.js").read_text(encoding="utf-8")
DASHBOARD_SHELL_CSS = (REPORTS_ASSETS / "dashboard-shell.css").read_text(encoding="utf-8")
DASHBOARD_SHELL_JS = (REPORTS_ASSETS / "dashboard-shell.js").read_text(encoding="utf-8")


def embed_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return (
        raw.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def render_report_for_test(data_json_path: Path) -> Path:
    """Wrap a `report-data.json` packet in the canonical `report-shell.{css,js}` for browser/HTML tests."""
    payload = json.loads(data_json_path.read_text(encoding="utf-8"))
    html = (
        "<!doctype html><html data-theme='light'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Validation report — OpenClinAI</title>"
        f"<style>{REPORT_SHELL_CSS}</style>"
        "<script>(function(){try{var t=localStorage.getItem('oc-theme-report');"
        "if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;}catch(e){}})();</script>"
        "</head><body>"
        "<header class='topbar'><div class='topbar-id'><div class='id-main'>"
        "<div class='breadcrumb'><a href='../index.html' title='Back to all published validation reports'>← All Reports</a>"
        "<span class='bc-sep'>·</span>"
        "<a href='https://openclinai.org/validation-harness/' target='_blank' rel='noopener'>Validation Harness</a></div>"
        "<h1 id='report-title'></h1><div id='run-meta' class='meta'></div></div>"
        "<div class='id-actions'>"
        "<span id='run-switcher' class='run-switcher'><label for='run-switcher-sel'>view run</label>"
        "<select id='run-switcher-sel' aria-label='Switch to another published run'></select></span>"
        "<button id='print-pdf' class='btn-ghost' title='print / save as PDF'>Download PDF</button>"
        "<button id='theme-toggle' class='btn-ghost btn-icon' type='button' title='Toggle light / dark' aria-label='Toggle light or dark mode'></button>"
        "</div></div>"
        "<div class='controls'><label id='run-select-wrap' hidden>run <select id='run-select'></select></label></div>"
        "<nav id='toc' aria-label='On this page'></nav></header>"
        "<a class='skip-link' href='#report'>Skip to report</a>"
        "<main id='report'></main>"
        "<div id='sort-live' class='sr-only' aria-live='polite'></div>"
        "<div class='legend'><p class='legend-group-h'>Three-layer read-only evaluation reference</p>"
        "<dl class='legend-key'>"
        "<dt>Layer 1 · Deterministic</dt><dd>HTTP/schema validity, exact chart-reference UUID resolution, and temporal guardrail gate status.</dd>"
        "<dt>Layer 2 · LLM Judge</dt><dd>advisory Scout autorater composite (0–100) and Safety-Adjusted Benchmark.</dd>"
        "<dt>Layer 3 · Human &amp; PPI</dt><dd>clinician/human adjudication paired with Prediction-Powered Inference (PPI) calibration.</dd>"
        "<dt>⏱ latency</dt><dd>end-to-end response time; <b>orange</b> = first turn per backend (carries model warmup).</dd>"
        "<dt>chart refs</dt><dd>count of chart records cited — a COUNT, not a grounding/quality signal.</dd>"
        "</dl></div>"
        f"<script type='application/json' id='report-data'>{embed_json(payload)}</script>"
        f"<script>{REPORT_SHELL_JS}</script>"
        "</body></html>"
    )
    out = data_json_path.parent / "test-report.html"
    out.write_text(html, encoding="utf-8")
    return out


def render_dashboard_for_test(data_json_path: Path) -> Path:
    """Wrap a `dashboard-data.json` packet in the canonical `dashboard-shell.{css,js}` for browser/HTML tests."""
    payload = json.loads(data_json_path.read_text(encoding="utf-8"))
    html = (
        "<!doctype html><html lang='en' data-theme='dark'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>validate run · live monitor</title>"
        f"<style>{DASHBOARD_SHELL_CSS}</style>"
        "<script>(function(){try{var s=localStorage.getItem('oc-theme-dashboard');"
        "if(s==='light'||s==='dark'){document.documentElement.setAttribute('data-theme',s);return;}"
        "if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches){"
        "document.documentElement.setAttribute('data-theme','light');}}catch(e){}})();</script>"
        "</head><body>"
        "<button type='button' id='oc-theme-toggle' class='oc-theme-toggle' title='Switch color theme' aria-label='Switch color theme'>◐ theme</button>"
        "<h1 id='hdr'>validate run</h1>"
        "<div class='bar'><div id='fill' style='width:0%'></div></div>"
        "<div id='prog' class='muted'></div>"
        "<div id='warnbar' class='caveat red' style='display:none'></div>"
        "<section><h2>Models and Hub profiles the arms call</h2><div id='models'></div></section>"
        "<section><h2>Arms</h2><div class='row' id='arms'></div></section>"
        "<section><h2>Judged scores</h2><div id='judges'></div></section>"
        "<section id='checksec' style='display:none'><h2>Checks against the judge</h2><div id='checkprec'></div></section>"
        "<section><h2>Scenario &times; arm &nbsp;<span class='muted'>(click a cell)</span></h2>"
        "<p id='legend' class='muted' style='margin:2px 0 6px'></p><div id='grid'></div></section>"
        "<section><h2>Recent &nbsp;<span class='muted'>(click a row)</span></h2><div class='feed' id='feed'></div></section>"
        "<div id='modal' onclick='if(event.target===this)closeD()'><div id='mbody'></div></div>"
        f"<script type='application/json' id='dashboard-data'>{embed_json(payload)}</script>"
        f"<script>{DASHBOARD_SHELL_JS}</script>"
        "</body></html>"
    )
    out = data_json_path.parent / "test-dashboard.html"
    out.write_text(html, encoding="utf-8")
    return out


_CELL_RENDERER_JS_SLICE = (
    "function htmlEsc(s){\n"
    "  return (s == null ? '' : String(s))\n"
    "    .replace(/&/g, '&amp;')\n"
    "    .replace(/</g, '&lt;')\n"
    "    .replace(/>/g, '&gt;')\n"
    "    .replace(/\"/g, '&quot;')\n"
    "    .replace(/'/g, '&#x27;');\n"
    "}\n"
    + REPORT_SHELL_JS[
        REPORT_SHELL_JS.index("var TONE_CLASSES =") : REPORT_SHELL_JS.index("function bpNiceCeil(")
    ]
)


def render_cell_via_js(cell: dict[str, Any], run: dict[str, Any] | None = None) -> dict[str, str]:
    """Execute `report-shell.js`'s client-side cell renderers in Node on a `v2` JSON cell."""
    run_obj = run or {}
    script = (
        _CELL_RENDERER_JS_SLICE
        + f"\nconst run = {json.dumps(run_obj)};\n"
        + f"const cell = {json.dumps(cell)};\n"
        + "process.stdout.write(JSON.stringify({\n"
        + "  answer_html: renderCellAnswerHtml(run, cell),\n"
        + "  blocks_html: renderCellBlocksHtml(cell),\n"
        + "  chips_html: renderCellChipsHtml(cell),\n"
        + "  sources_html: resolveCellSourcesHtml(run, cell),\n"
        + "  refs_html: resolveCellRefsHtml(run, cell),\n"
        + "}));\n"
    )
    res = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(res.stdout)
