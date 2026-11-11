#!/usr/bin/env python3
"""Live local HTTP monitor (`:8099`) for an active validation run.

    python3 scripts/validate-dashboard.py        # then open http://localhost:8099

Serves `/api/status` and `/api/detail` from `harness.validate.dashboard_data` and loads
`dashboard-shell.css` and `dashboard-shell.js` from `openclinai.org/reports/assets/`.
Static snapshots (`dashboard-data.json`) are generated directly by `harness.validate.dashboard_data`.
"""

from __future__ import annotations

import glob
import http.server
import json
import os
import socket
import socketserver
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.validate.dashboard_data import (  # noqa: E402
    CLASSIFIER_SOURCE,
    arm_models,
    assertion_class,
    blame_failure,
    build_dashboard_data,
    build_detail,
    build_status,
    catalyst_expectation,
    format_sql as _format_sql,
    profile_titles,
    read_judge_actors,
    run_family,
    write_dashboard_data,
)

PORT = int(os.environ.get("DASH_PORT", "8099"))
_RUN_OVERRIDE: str | None = None


def _assets_dir() -> Path:
    env_dir = os.environ.get("OPENCLINAI_ASSETS_DIR")
    if env_dir:
        return Path(env_dir)
    return ROOT.parent.parent / "reports" / "assets"


def _catalyst_runs_dir() -> Path:
    return ROOT / "artifacts" / "catalyst-notebook-validation"


def newest_run() -> str | None:
    if _RUN_OVERRIDE:
        return _RUN_OVERRIDE
    pin = os.environ.get("DASH_RUN")
    if pin:
        for base in (ROOT / "artifacts" / "validate", _catalyst_runs_dir()):
            p = pin if os.path.isabs(pin) or os.path.sep in pin else str(base / pin)
            if os.path.isdir(p):
                return p
    dirs = [d for d in glob.glob(str(ROOT / "artifacts" / "validate" / "*")) if os.path.isdir(d)]
    dirs += [d for d in glob.glob(str(_catalyst_runs_dir() / "*")) if os.path.isdir(d)]

    def _activity(d: str) -> float:
        rp = os.path.join(d, "results.jsonl")
        if os.path.exists(rp):
            return os.path.getmtime(rp)
        newest = max(
            (os.path.getmtime(p) for p in glob.glob(os.path.join(d, "**", "*.json"), recursive=True)),
            default=0.0,
        )
        return newest if newest else os.path.getmtime(d)

    return max(dirs, key=_activity) if dirs else None


def status() -> dict:
    return build_status(newest_run())


def detail(scenario: str, backend: str) -> dict:
    return build_detail(newest_run(), scenario, backend)


LIVE_SHELL_HTML = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>validate run · live monitor</title>
<link rel="stylesheet" href="/assets/dashboard-shell.css">
<script>(function(){try{var s=localStorage.getItem('oc-theme-dashboard');if(s==='light'||s==='dark'){document.documentElement.setAttribute('data-theme',s);return;}if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches){document.documentElement.setAttribute('data-theme','light');}}catch(e){}})();</script>
</head>
<body>
<button type="button" id="oc-theme-toggle" class="oc-theme-toggle" title="Switch color theme" aria-label="Switch color theme">◐ theme</button>
<h1 id="hdr">validate run</h1>
<div class="bar"><div id="fill" style="width:0%"></div></div>
<div id="prog" class="muted"></div>
<div id="warnbar" class="caveat red" style="display:none"></div>
<section><h2>Models and Hub profiles the arms call</h2><div id="models"></div></section>
<section><h2>Arms</h2><div class="row" id="arms"></div></section>
<section><h2>Judged scores</h2><div id="judges"></div></section>
<section id="checksec" style="display:none"><h2>Checks against the judge</h2><div id="checkprec"></div></section>
<section><h2>Scenario &times; arm &nbsp;<span class="muted">(click a cell)</span></h2><p id="legend" class="muted" style="margin:2px 0 6px"></p><div id="grid"></div></section>
<section><h2>Recent &nbsp;<span class="muted">(click a row)</span></h2><div class="feed" id="feed"></div></section>
<div id="modal" onclick="if(event.target===this)closeD()"><div id="mbody"></div></div>
<script src="/assets/dashboard-shell.js"></script>
</body>
</html>
"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a: object) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/detail"):
            q = parse_qs(parsed.query)
            payload = detail(q.get("scenario", [""])[0], q.get("backend", [""])[0])
            body = json.dumps(payload).encode("utf-8")
            ctype = "application/json"
        elif parsed.path.startswith("/api/status"):
            body = json.dumps(status()).encode("utf-8")
            ctype = "application/json"
        elif parsed.path in ("/assets/dashboard-shell.css", "/assets/dashboard-shell.js"):
            asset_path = _assets_dir() / Path(parsed.path).name
            if not asset_path.is_file():
                self.send_error(404, f"Missing asset: {asset_path}")
                return
            body = asset_path.read_bytes()
            ctype = "text/css; charset=utf-8" if parsed.path.endswith(".css") else "application/javascript; charset=utf-8"
        else:
            body = LIVE_SHELL_HTML.encode("utf-8")
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _ServerV6(_Server):
    address_family = socket.AF_INET6


def serve_dashboard() -> None:
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


if __name__ == "__main__":
    if "--run" in sys.argv:
        j = sys.argv.index("--run")
        if j + 1 < len(sys.argv):
            _RUN_OVERRIDE = os.path.abspath(sys.argv[j + 1])
    serve_dashboard()
