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
_WATCH_ARTIFACTS_DIRS: set[str] = set()
_WATCH_OUTPUT_DIRS: set[str] = set()
_WATCH_RUN_DIRS: set[str] = set()


def _git_common_repo_root(root: Path) -> Path | None:
    dot_git = root / ".git"
    if not dot_git.is_file():
        return None
    try:
        for line in dot_git.read_text(encoding="utf-8").splitlines():
            if line.startswith("gitdir:"):
                raw = line.split(":", 1)[1].strip()
                gitdir = Path(raw)
                if not gitdir.is_absolute():
                    gitdir = (root / gitdir).resolve()
                else:
                    gitdir = gitdir.resolve()
                if gitdir.parent.name == "worktrees":
                    return gitdir.parent.parent.parent
                return gitdir.parent
    except OSError:
        return None
    return None


def _assets_dir() -> Path:
    if os.environ.get("OPENCLINAI_DISABLE_UMBRELLA_ASSETS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return ROOT / "_standalone_no_assets"
    env_dir = os.environ.get("OPENCLINAI_ASSETS_DIR")
    if env_dir:
        return Path(env_dir)
    candidates = [
        ROOT.parent.parent / "reports" / "assets",
        ROOT.parent / "openclinai.org" / "reports" / "assets",
        ROOT.parent.parent / "openclinai.org" / "reports" / "assets",
    ]
    common_root = _git_common_repo_root(ROOT)
    if common_root is not None:
        candidates.extend(
            [
                common_root.parent / "openclinai.org" / "reports" / "assets",
                common_root.parent.parent / "reports" / "assets",
            ]
        )
    for cand in candidates:
        if (cand / "dashboard-shell.css").is_file():
            return cand
    return candidates[0]


def _assets_available() -> bool:
    assets = _assets_dir()
    return (assets / "dashboard-shell.css").is_file() and (
        assets / "dashboard-shell.js"
    ).is_file()


def _search_bases(artifacts_root: Path) -> list[Path]:
    wahs_dirs = [
        Path(p)
        for p in glob.glob(str(artifacts_root / "wahs*"))
        if os.path.isdir(p)
    ]
    return [
        artifacts_root / "validate",
        artifacts_root / "catalyst-validation",
        artifacts_root / "catalyst-notebook-validation",
        *wahs_dirs,
    ]


def newest_run() -> str | None:
    if _RUN_OVERRIDE:
        return _RUN_OVERRIDE
    search_bases = _search_bases(ROOT / "artifacts")
    for extra in sorted(_WATCH_ARTIFACTS_DIRS):
        for b in _search_bases(Path(extra)):
            if b not in search_bases:
                search_bases.append(b)
    for od in sorted(_WATCH_OUTPUT_DIRS):
        od_path = Path(od)
        if od_path not in search_bases:
            search_bases.append(od_path)
    pin = os.environ.get("DASH_RUN")
    if pin:
        for rd in sorted(_WATCH_RUN_DIRS):
            if os.path.isdir(rd) and (
                pin == rd or os.path.abspath(pin) == rd or Path(rd).name == pin
            ):
                return rd
        for base in search_bases:
            p = pin if os.path.isabs(pin) or os.path.sep in pin else str(base / pin)
            if os.path.isdir(p):
                return p
        return None
    dirs: list[str] = []
    for base in search_bases:
        dirs.extend(d for d in glob.glob(str(base / "*")) if os.path.isdir(d))
    for rd in sorted(_WATCH_RUN_DIRS):
        if os.path.isdir(rd) and rd not in dirs:
            dirs.append(rd)

    def _activity(d: str) -> float:
        stream_mtimes: list[float] = []
        for name in ("results.jsonl", "events.jsonl"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                stream_mtimes.append(os.path.getmtime(p))
        if stream_mtimes:
            return max(stream_mtimes)
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
<script>(function(){try{var s=localStorage.getItem('oc-theme-validate-dash')||localStorage.getItem('oc-theme-dashboard');if(s==='light'||s==='dark'){document.documentElement.setAttribute('data-theme',s);return;}if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches){document.documentElement.setAttribute('data-theme','light');}}catch(e){}})();</script>
</head>
<body>
<button type="button" id="theme-toggle" class="oc-theme-toggle" title="Switch color theme" aria-label="Switch color theme">◐ theme</button>
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

    def do_POST(self) -> None:
        global _RUN_OVERRIDE
        parsed = urlparse(self.path)
        if parsed.path == "/api/watch":
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
                ad = str(payload.get("artifacts_dir") or "").strip()
                if ad and os.path.isabs(ad):
                    _WATCH_ARTIFACTS_DIRS.add(ad)
                od = str(payload.get("output_dir") or "").strip()
                if od and os.path.isabs(od):
                    _WATCH_OUTPUT_DIRS.add(od)
                rd = str(payload.get("run_dir") or "").strip()
                if rd and os.path.isabs(rd):
                    _WATCH_RUN_DIRS.add(rd)
                    _WATCH_OUTPUT_DIRS.add(str(Path(rd).parent))
                    if _RUN_OVERRIDE and _RUN_OVERRIDE != rd:
                        _WATCH_RUN_DIRS.add(_RUN_OVERRIDE)
                        _RUN_OVERRIDE = None
            except Exception:
                pass
            body = json.dumps({"ok": True, "active_run": newest_run()}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

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
                self.send_error(
                    404,
                    f"Missing viewer asset: {asset_path}. Set OPENCLINAI_ASSETS_DIR to openclinai.org/reports/assets.",
                )
                return
            body = asset_path.read_bytes()
            ctype = "text/css; charset=utf-8" if parsed.path.endswith(".css") else "application/javascript; charset=utf-8"
        elif not _assets_available():
            body = (
                "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                "<title>validate run · live monitor (JSON API active)</title></head><body>"
                "<h1>validate run · live JSON API active</h1>"
                "<p>Viewer assets (<code>dashboard-shell.css</code> / <code>dashboard-shell.js</code>) were not found at "
                f"<code>{_assets_dir()}</code>.</p>"
                "<p>Set <code>OPENCLINAI_ASSETS_DIR=/path/to/openclinai.org/reports/assets</code> for the browser UI, "
                "or query <a href='/api/status'><code>/api/status</code></a> directly.</p>"
                "</body></html>"
            ).encode("utf-8")
            ctype = "text/html; charset=utf-8"
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
    if "--ensure" in sys.argv:
        from harness.validate.live_dashboard import ensure_live_dashboard

        url = ensure_live_dashboard(ROOT, port=PORT, force=True)
        raise SystemExit(0 if url else 1)
    if "--run" in sys.argv:
        j = sys.argv.index("--run")
        if j + 1 < len(sys.argv):
            _RUN_OVERRIDE = os.path.abspath(sys.argv[j + 1])
    serve_dashboard()
