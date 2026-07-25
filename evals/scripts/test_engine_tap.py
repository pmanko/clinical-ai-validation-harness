"""Red-first tests for scripts/engine-tap.py — the per-arm recording proxy at the
LLM-engine ingress (engine-parity instrument, AC-2/D2).

The tap must be byte-faithful: what the client sent is exactly what the upstream
receives AND exactly what lands in the capture file — the captured artifact is later
replayed verbatim against the engine, so any mutation breaks the instrument.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "engine-tap.py"


def _load():
    spec = importlib.util.spec_from_file_location("engine_tap", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _UpstreamState:
    def __init__(self) -> None:
        self.bodies: list[bytes] = []
        self.paths: list[str] = []
        self.auth_headers: list[str | None] = []


def _start_upstream(state: _UpstreamState, *, sse: bool = False) -> tuple[ThreadingHTTPServer, int]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length", "0"))
            state.bodies.append(self.rfile.read(length))
            state.paths.append(self.path)
            state.auth_headers.append(self.headers.get("Authorization"))
            if sse:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for i in range(3):
                    frame = f"data: {{\"n\": {i}}}\n\n".encode()
                    self.wfile.write(frame)
                    self.wfile.flush()
                    time.sleep(0.02)
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                payload = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        def do_GET(self):  # noqa: N802
            payload = json.dumps({"data": [{"id": "gemma-e4b"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):  # silence
            pass

    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def _start_tap(mod, arm: str, upstream_port: int, capture_dir: Path) -> tuple[object, int]:
    port = _free_port()
    servers = mod.create_servers(
        [(arm, port)], f"http://127.0.0.1:{upstream_port}", capture_dir
    )
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    return servers[0], port


def test_post_body_is_byte_faithful_upstream_and_captured(tmp_path):
    mod = _load()
    state = _UpstreamState()
    upstream, upstream_port = _start_upstream(state)
    tap, tap_port = _start_tap(mod, "bundled", upstream_port, tmp_path)
    try:
        # Non-ASCII, embedded newline, and NO trailing newline: any normalization shows up.
        body = ('{"model": "gemma-e4b", "messages": [{"role": "user", '
                '"content": "Comment ça va?\\nWeight 70 kg"}], "temperature": 0.2}').encode()
        resp = requests.post(
            f"http://127.0.0.1:{tap_port}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer sekret"},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json()["choices"][0]["message"]["content"] == "ok"

        # Upstream received the exact bytes, on the exact path, with auth forwarded.
        assert state.bodies == [body]
        assert state.paths == ["/v1/chat/completions"]
        assert state.auth_headers == ["Bearer sekret"]

        # Capture: exactly one body file, byte-identical, with meta naming the arm+path.
        bodies = sorted(tmp_path.glob("*.body.json"))
        metas = sorted(tmp_path.glob("*.meta.json"))
        assert len(bodies) == 1 and len(metas) == 1
        assert bodies[0].read_bytes() == body
        meta = json.loads(metas[0].read_text(encoding="utf-8"))
        assert meta["arm"] == "bundled"
        assert meta["path"] == "/v1/chat/completions"
        assert meta["method"] == "POST"
        assert meta["body_file"] == bodies[0].name
        # The API key must never be persisted in the capture.
        assert "sekret" not in metas[0].read_text(encoding="utf-8")
    finally:
        tap.shutdown()
        upstream.shutdown()


def test_sse_stream_passes_through_and_request_is_captured(tmp_path):
    mod = _load()
    state = _UpstreamState()
    upstream, upstream_port = _start_upstream(state, sse=True)
    tap, tap_port = _start_tap(mod, "hub", upstream_port, tmp_path)
    try:
        body = b'{"model": "gemma-e4b", "stream": true, "messages": []}'
        resp = requests.post(
            f"http://127.0.0.1:{tap_port}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"].startswith("text/event-stream")
        lines = [ln for ln in resp.iter_lines() if ln]
        assert lines == [b'data: {"n": 0}', b'data: {"n": 1}', b'data: {"n": 2}', b"data: [DONE]"]
        assert state.bodies == [body]
        captured = sorted(tmp_path.glob("*.body.json"))
        assert len(captured) == 1 and captured[0].read_bytes() == body
        meta = json.loads(sorted(tmp_path.glob("*.meta.json"))[0].read_text(encoding="utf-8"))
        assert meta["arm"] == "hub"
    finally:
        tap.shutdown()
        upstream.shutdown()


def test_upstream_down_returns_502_and_still_captures(tmp_path):
    mod = _load()
    # Reserve the port bound-but-never-listening: connections are refused
    # deterministically AND nothing else can grab the port mid-test.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        dead_port = reserved.getsockname()[1]
        tap, tap_port = _start_tap(mod, "bundled", dead_port, tmp_path)
        try:
            body = b'{"model": "gemma-e4b", "messages": []}'
            resp = requests.post(
                f"http://127.0.0.1:{tap_port}/v1/chat/completions", data=body, timeout=10
            )
            assert resp.status_code == 502
            captured = sorted(tmp_path.glob("*.body.json"))
            assert len(captured) == 1 and captured[0].read_bytes() == body
        finally:
            tap.shutdown()


def test_get_passthrough_is_not_captured(tmp_path):
    """Health checks (GET /v1/models) must relay but not pollute the capture ledger."""
    mod = _load()
    state = _UpstreamState()
    upstream, upstream_port = _start_upstream(state)
    tap, tap_port = _start_tap(mod, "hub", upstream_port, tmp_path)
    try:
        resp = requests.get(f"http://127.0.0.1:{tap_port}/v1/models", timeout=10)
        assert resp.status_code == 200
        assert resp.json()["data"][0]["id"] == "gemma-e4b"
        assert list(tmp_path.glob("*.body.json")) == []
    finally:
        tap.shutdown()
        upstream.shutdown()
