#!/usr/bin/env python3
"""Live local HTTP monitor (`:8099`) for an active validation run.

    python3 -m harness.validate.dashboard_server        # then open http://localhost:8099

Serves `/api/status`, `/api/runs`, `/api/stream` (SSE), and `/api/detail` from
`harness.validate.dashboard_data` and `harness.validate.run_index`, loading
`dashboard-shell.css` and `dashboard-shell.js` from `openclinai.org/reports/assets/`.
Static snapshots (`dashboard-data.json`) are generated directly by `harness.validate.dashboard_data`.
"""

from __future__ import annotations

import glob
import http.server
import json
import os
from pathlib import Path
import socket
import socketserver
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

if "ROOT" not in globals():
    _env_root = os.environ.get("OPENCLINAI_DASHBOARD_ROOT", "").strip()
    ROOT = Path(_env_root) if _env_root else Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
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
from harness.validate.run_index import GLOBAL_RUN_INDEX  # noqa: E402

PORT = int(os.environ.get("DASH_PORT", "8099"))
_RUN_OVERRIDE: str | None = None
_WATCH_ARTIFACTS_DIRS: set[str] = set()
_WATCH_OUTPUT_DIRS: set[str] = set()
_WATCH_RUN_DIRS: set[str] = set()
_ACTIVE_WINDOW_S = 120.0


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


def _all_search_bases() -> list[Path]:
    search_bases = _search_bases(ROOT / "artifacts")
    for extra in sorted(_WATCH_ARTIFACTS_DIRS):
        for b in _search_bases(Path(extra)):
            if b not in search_bases:
                search_bases.append(b)
    for od in sorted(_WATCH_OUTPUT_DIRS):
        od_path = Path(od)
        if od_path not in search_bases:
            search_bases.append(od_path)
    return search_bases


def _find_pinned_run(pin: str, search_bases: list[Path]) -> str | None:
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


def _run_activity(d: str) -> float:
    stream_mtimes: list[float] = []
    for name in ("results.jsonl", "events.jsonl"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            stream_mtimes.append(os.path.getmtime(p))
    if stream_mtimes:
        return max(stream_mtimes)
    shallow_mtimes: list[float] = []
    for name in (
        "run_manifest.json",
        "run_meta.json",
        "summary.json",
        "run-summary.json",
        "dashboard-data.json",
    ):
        p = os.path.join(d, name)
        if os.path.exists(p):
            shallow_mtimes.append(os.path.getmtime(p))
    if shallow_mtimes:
        return max(shallow_mtimes)
    return os.path.getmtime(d)


def _discover_run_dirs() -> list[str]:
    seen: dict[str, str] = {}
    for base in _all_search_bases():
        for d in glob.glob(str(base / "*")):
            if os.path.isdir(d):
                rp = os.path.realpath(d)
                seen.setdefault(rp, d)
    for rd in sorted(_WATCH_RUN_DIRS):
        if os.path.isdir(rd):
            rp = os.path.realpath(rd)
            seen.setdefault(rp, rd)
    if _RUN_OVERRIDE and os.path.isdir(_RUN_OVERRIDE):
        rp = os.path.realpath(_RUN_OVERRIDE)
        seen.setdefault(rp, _RUN_OVERRIDE)
    dirs = list(seen.values())
    dirs.sort(key=_run_activity, reverse=True)
    return dirs


def _read_small_json(path: Path) -> dict:
    try:
        if path.is_file() and path.stat().st_size <= 2_000_000:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def discover_runs() -> list[dict]:
    dirs = _discover_run_dirs()
    now = time.time()
    out: list[dict] = []
    for d in dirs:
        mtime = _run_activity(d)
        loaded = GLOBAL_RUN_INDEX.get_if_loaded(d)
        if loaded is not None:
            st = loaded.get_status(since_seq=None)
            out.append(
                {
                    "run_id": Path(d).name,
                    "run_dir": d,
                    "family": st.get("family"),
                    "completed": st.get("done", 0),
                    "expected": st.get("total", 0),
                    "active": bool(st.get("active")),
                    "finished": bool(st.get("finished")),
                    "mtime": mtime,
                }
            )
            continue

        rdir = Path(d)
        manifest = _read_small_json(rdir / "run_manifest.json")
        summary = _read_small_json(rdir / "summary.json")
        run_sum = _read_small_json(rdir / "run-summary.json")
        family = str(
            manifest.get("family")
            or manifest.get("report_family")
            or run_sum.get("family")
            or ""
        )
        if not family:
            family = run_family(rdir)
        expected = manifest.get("expected_cells")
        exp_count = (
            len(expected)
            if isinstance(expected, list)
            else int(manifest.get("total_cells") or 0)
        )
        if not exp_count:
            exp_count = int(summary.get("total_cells") or run_sum.get("total_cells") or 0)
        completed = int(summary.get("total_cells") or run_sum.get("total_cells") or 0)
        res_p = rdir / "results.jsonl"
        res_active = False
        if res_p.is_file():
            try:
                res_mtime = res_p.stat().st_mtime
                res_active = (now - res_mtime) < _ACTIVE_WINDOW_S
            except OSError:
                pass
        finished = bool(exp_count and completed >= exp_count)
        out.append(
            {
                "run_id": rdir.name,
                "run_dir": d,
                "family": family,
                "completed": completed,
                "expected": exp_count,
                "active": bool(res_active and not finished),
                "finished": finished,
                "mtime": mtime,
            }
        )
    return out


def _matches_run(candidate: str, want: str, want_abs: str) -> bool:
    return (
        Path(candidate).name == want
        or os.path.abspath(candidate) == want_abs
        or candidate == want
    )


def newest_run() -> str | None:
    if _RUN_OVERRIDE:
        return _RUN_OVERRIDE
    pin = os.environ.get("DASH_RUN")
    if pin:
        return _find_pinned_run(pin, _all_search_bases())
    dirs = _discover_run_dirs()
    return dirs[0] if dirs else None


def resolve_run(run_param: str | None = None) -> str | None:
    if not run_param:
        return newest_run()
    want = str(run_param).strip()
    if not want:
        return newest_run()
    want_abs = os.path.abspath(want)
    if _RUN_OVERRIDE:
        return _RUN_OVERRIDE if _matches_run(_RUN_OVERRIDE, want, want_abs) else None
    pin = os.environ.get("DASH_RUN")
    if pin:
        pinned = _find_pinned_run(pin, _all_search_bases())
        return pinned if pinned and _matches_run(pinned, want, want_abs) else None
    for d in _discover_run_dirs():
        if _matches_run(d, want, want_abs):
            return d
    return None


def runs_payload() -> dict:
    active = newest_run()
    return {
        "active_run": Path(active).name if active else None,
        "active_run_dir": active,
        "runs": discover_runs(),
    }


def status(run_param: str | None = None, *, since_seq: int | None = None) -> dict:
    return build_status(resolve_run(run_param), since_seq=since_seq)


def detail(scenario: str, backend: str, run_param: str | None = None) -> dict:
    return build_detail(resolve_run(run_param), scenario, backend)


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
<div id="live-controls" class="live-controls" style="display:none"></div>
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
    protocol_version = "HTTP/1.1"
    timeout = 5.0

    def log_message(self, *a: object) -> None:
        pass

    def _send_bytes(
        self,
        body: bytes,
        ctype: str,
        *,
        status_code: int = 200,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True

    def _send_json(self, payload: dict, *, status_code: int = 200) -> None:
        self._send_bytes(
            json.dumps(payload).encode("utf-8"),
            "application/json; charset=utf-8",
            status_code=status_code,
            extra_headers={"Cache-Control": "no-store"},
        )

    def _serve_sse_stream(self, run_param: str | None, since_seq: int | None) -> None:
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        stop_ev: threading.Event | None = getattr(self.server, "stop_event", None)
        last_seq: int | None = since_seq
        sent_initial = False
        last_heartbeat = time.monotonic()

        def _write_sse(chunk: str) -> bool:
            try:
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                return False

        while stop_ev is None or not stop_ev.is_set():
            run_dir = resolve_run(run_param)
            if run_dir is None:
                if not sent_initial:
                    payload = build_status(None)
                    if not _write_sse(f"id: 0\nevent: status\ndata: {json.dumps(payload)}\n\n"):
                        return
                    sent_initial = True
            else:
                idx = GLOBAL_RUN_INDEX.get(run_dir)
                req_since = last_seq if sent_initial else since_seq
                payload = idx.get_status(since_seq=req_since)
                cur_seq = int(payload.get("seq") or 0)
                if not sent_initial or not payload.get("unchanged"):
                    if not _write_sse(
                        f"id: {cur_seq}\nevent: status\ndata: {json.dumps(payload)}\n\n"
                    ):
                        return
                    sent_initial = True
                    last_seq = cur_seq
                    last_heartbeat = time.monotonic()

            now = time.monotonic()
            if now - last_heartbeat >= 15.0:
                if not _write_sse(": keepalive\n\n"):
                    return
                last_heartbeat = now

            if stop_ev is not None:
                if stop_ev.wait(0.4):
                    return
            else:
                time.sleep(0.4)

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
            self._send_json({"ok": True, "active_run": newest_run()})
            return
        self.send_error(404)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        run_param = (q.get("run") or [""])[0].strip() or None
        raw_since = (q.get("since_seq") or [""])[0].strip()
        since_seq: int | None = None
        if raw_since:
            try:
                since_seq = int(raw_since)
            except ValueError:
                since_seq = None

        if parsed.path == "/api/runs":
            self._send_json(runs_payload())
            return
        if parsed.path == "/api/stream":
            self._serve_sse_stream(run_param, since_seq)
            return
        if parsed.path.startswith("/api/detail"):
            payload = detail(
                q.get("scenario", [""])[0],
                q.get("backend", [""])[0],
                run_param=run_param,
            )
            self._send_json(payload)
            return
        if parsed.path.startswith("/api/status"):
            self._send_json(status(run_param=run_param, since_seq=since_seq))
            return
        if parsed.path in ("/assets/dashboard-shell.css", "/assets/dashboard-shell.js"):
            asset_path = _assets_dir() / Path(parsed.path).name
            if not asset_path.is_file():
                self.send_error(
                    404,
                    f"Missing viewer asset: {asset_path}. Set OPENCLINAI_ASSETS_DIR to openclinai.org/reports/assets.",
                )
                return
            body = asset_path.read_bytes()
            ctype = (
                "text/css; charset=utf-8"
                if parsed.path.endswith(".css")
                else "application/javascript; charset=utf-8"
            )
            self._send_bytes(body, ctype, extra_headers={"Cache-Control": "no-cache"})
            return
        if not _assets_available():
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
            self._send_bytes(body, "text/html; charset=utf-8")
            return
        self._send_bytes(LIVE_SHELL_HTML.encode("utf-8"), "text/html; charset=utf-8")


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate: bool = True):
        self.stop_event = threading.Event()
        super().__init__(server_address, RequestHandlerClass, bind_and_activate=bind_and_activate)

    def shutdown(self) -> None:
        self.stop_event.set()
        super().shutdown()

    def server_close(self) -> None:
        self.stop_event.set()
        super().server_close()


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


def main(argv: list[str] | None = None) -> int:
    global _RUN_OVERRIDE
    args = list(sys.argv[1:] if argv is None else argv)
    if "--ensure" in args:
        from harness.validate.live_dashboard import ensure_live_dashboard

        url = ensure_live_dashboard(ROOT, port=PORT, force=True)
        return 0 if url else 1
    if "--run" in args:
        j = args.index("--run")
        if j + 1 < len(args):
            _RUN_OVERRIDE = os.path.abspath(args[j + 1])
    serve_dashboard()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
