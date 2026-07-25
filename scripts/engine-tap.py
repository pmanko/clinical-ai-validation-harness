#!/usr/bin/env python3
"""Per-arm recording proxy at the LLM-engine ingress (engine-parity instrument, D2).

Each listener port is one parity arm's ingress; every POST body is captured
byte-for-byte before being forwarded to the shared upstream engine, so attribution
is by ingress port — no content sniffing, no code changes in either module. GETs
(health checks like /v1/models) relay without being captured.

Capture layout (two files per request, so the body artifact stays replayable verbatim):
  <capture_dir>/<t_ns>-<seq>-<arm>.body.json   exact request bytes as received
  <capture_dir>/<t_ns>-<seq>-<arm>.meta.json   {arm, path, method, body_file, received_at}
Authorization headers are forwarded upstream but never persisted.

Usage:
  scripts/engine-tap.py --arm bundled=8078 --arm hub=8079 \
      --upstream http://127.0.0.1:8077 --capture-dir artifacts/parity-engine/captures
"""

from __future__ import annotations

import argparse
import http.client
import itertools
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

_FORWARD_HEADERS = ("Content-Type", "Accept", "Authorization")
_seq = itertools.count()
_seq_lock = threading.Lock()


def _capture(capture_dir: Path, arm: str, method: str, path: str, body: bytes) -> None:
    with _seq_lock:
        seq = next(_seq)
    stem = f"{time.time_ns()}-{seq:04d}-{arm}"
    capture_dir.mkdir(parents=True, exist_ok=True)
    body_file = capture_dir / f"{stem}.body.json"
    body_file.write_bytes(body)
    meta = {
        "arm": arm,
        "path": path,
        "method": method,
        "body_file": body_file.name,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    (capture_dir / f"{stem}.meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def _make_handler(arm: str, upstream: str, capture_dir: Path):
    parts = urlsplit(upstream)
    upstream_host = parts.hostname or "127.0.0.1"
    upstream_port = parts.port or (443 if parts.scheme == "https" else 80)
    conn_cls = (
        http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    )

    class TapHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _relay(self, body: bytes | None) -> None:
            conn = conn_cls(upstream_host, upstream_port, timeout=2400)
            try:
                headers = {
                    name: value
                    for name in _FORWARD_HEADERS
                    if (value := self.headers.get(name)) is not None
                }
                conn.request(self.command, self.path, body=body, headers=headers)
                resp = conn.getresponse()
                self.send_response(resp.status)
                content_type = resp.getheader("Content-Type")
                if content_type:
                    self.send_header("Content-Type", content_type)
                # Always chunk the relayed body: works for both buffered JSON and
                # SSE streams without knowing the length up front.
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(f"{len(chunk):x}\r\n".encode())
                    self.wfile.write(chunk)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except OSError as exc:
                payload = json.dumps(
                    {"error": f"engine-tap: upstream {upstream} unreachable: {exc}"}
                ).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            finally:
                conn.close()

        def do_POST(self):  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            _capture(capture_dir, arm, "POST", self.path, body)
            self._relay(body)

        def do_GET(self):  # noqa: N802 - health checks relay uncaptured
            self._relay(None)

        def log_message(self, *args):
            pass

    return TapHandler


def create_servers(
    arms: list[tuple[str, int]], upstream: str, capture_dir: Path | str
) -> list[ThreadingHTTPServer]:
    """One ThreadingHTTPServer per (arm, port), all forwarding to the same upstream.
    Callers run each server's serve_forever() (thread or blocking) and shutdown() it."""
    capture_dir = Path(capture_dir)
    servers = []
    for arm, port in arms:
        handler = _make_handler(arm, upstream, capture_dir)
        servers.append(ThreadingHTTPServer(("0.0.0.0", port), handler))
    return servers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm",
        action="append",
        required=True,
        metavar="NAME=PORT",
        help="arm ingress, e.g. bundled=8078 (repeatable)",
    )
    parser.add_argument("--upstream", default="http://127.0.0.1:8077")
    parser.add_argument("--capture-dir", default="artifacts/parity-engine/captures")
    args = parser.parse_args()

    arms = []
    for spec in args.arm:
        name, _, port = spec.partition("=")
        if not name or not port.isdigit():
            parser.error(f"--arm must be NAME=PORT, got {spec!r}")
        arms.append((name, int(port)))

    servers = create_servers(arms, args.upstream, args.capture_dir)
    for (name, port), server in zip(arms, servers):
        print(f"engine-tap: arm {name!r} listening on :{port} -> {args.upstream}")
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"engine-tap: capturing POST bodies to {args.capture_dir}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        for server in servers:
            server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
