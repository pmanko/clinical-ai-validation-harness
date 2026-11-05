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
import re
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_FORWARD_HEADERS = ("Content-Type", "Accept", "Authorization")
_seq = itertools.count()
_seq_lock = threading.Lock()
_REFERENCE_RECORD_RE = re.compile(
    r"(?m)^\[\d+\]\s*(?:\([^)]*\)\s*)?(?:Drug reference|Safety finding)\s*(?:—|--|-)"
)


def has_reference_records(messages: list[dict[str, Any]]) -> bool:
    """Match LocalLlmEngine's ReferenceRecords.in(referenceSlice) check on user messages."""
    for message in messages or []:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if (
            _REFERENCE_RECORD_RE.search(content)
            or "Drug reference — " in content
            or "Safety finding — " in content
        ):
            return True
    return False


def apply_local_engine_dry_policy(body: bytes) -> tuple[bytes, dict[str, Any]]:
    """Inject LocalLlmEngine.buildRequestBody()'s exact conditional DRY sampler settings.

    Out-of-the-box LocalLlmEngine sends samplers=["dry", "temperature"] and
    dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=8, dry_penalty_last_n=-1
    on every chat completion except when drug-safety reference records are present
    (ReferenceRecords.PRESENT), where it sends samplers=["temperature"] alone.
    """
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body, {"simulated_local_engine_dry": False}
    if not isinstance(payload, dict) or "messages" not in payload:
        return body, {"simulated_local_engine_dry": False}

    messages = payload.get("messages")
    present = has_reference_records(messages if isinstance(messages, list) else [])
    if present:
        payload["samplers"] = ["temperature"]
        for key in (
            "dry_multiplier",
            "dry_base",
            "dry_allowed_length",
            "dry_penalty_last_n",
        ):
            payload.pop(key, None)
    else:
        payload["samplers"] = ["dry", "temperature"]
        payload["dry_multiplier"] = 0.8
        payload["dry_base"] = 1.75
        payload["dry_allowed_length"] = 8
        payload["dry_penalty_last_n"] = -1

    updated = json.dumps(payload).encode("utf-8")
    return updated, {
        "simulated_local_engine_dry": True,
        "reference_records": "present" if present else "absent",
        "dry_multiplier": 0.0 if present else 0.8,
    }


def extract_upstream_telemetry(raw_response: bytes) -> dict[str, Any]:
    """Extract llama-server timings and OpenAI usage from a JSON or SSE response body."""
    text = raw_response.decode("utf-8", errors="replace")
    candidates: list[dict[str, Any]] = []
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                candidates.append(parsed)
        except ValueError:
            pass
    for line in reversed(text.splitlines()):
        if not line.startswith("data:"):
            continue
        data = line.split(":", 1)[1].strip()
        if not data or data == "[DONE]":
            continue
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                candidates.append(parsed)
        except ValueError:
            continue

    telemetry: dict[str, Any] = {}
    for obj in candidates:
        timings = obj.get("timings")
        if isinstance(timings, dict) and "timings" not in telemetry:
            telemetry["timings"] = {
                k: timings[k]
                for k in (
                    "prompt_n",
                    "cache_n",
                    "predicted_n",
                    "prompt_ms",
                    "predicted_ms",
                    "prompt_per_second",
                    "predicted_per_second",
                )
                if k in timings
            }
        usage = obj.get("usage")
        if isinstance(usage, dict) and "usage" not in telemetry:
            telemetry["usage"] = {
                k: usage[k]
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                if k in usage
            }
        if "timings" in telemetry and "usage" in telemetry:
            break
    return telemetry


def _capture(
    capture_dir: Path,
    arm: str,
    method: str,
    path: str,
    body: bytes,
    *,
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    with _seq_lock:
        seq = next(_seq)
    stem = f"{time.time_ns()}-{seq:04d}-{arm}"
    capture_dir.mkdir(parents=True, exist_ok=True)
    body_file = capture_dir / f"{stem}.body.json"
    body_file.write_bytes(body)
    meta: dict[str, Any] = {
        "arm": arm,
        "path": path,
        "method": method,
        "body_file": body_file.name,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_meta:
        meta.update(extra_meta)
    meta_path = capture_dir / f"{stem}.meta.json"
    meta_path.write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta_path


def _update_capture_meta(meta_path: Path, updates: dict[str, Any]) -> None:
    if not updates or not meta_path.is_file():
        return
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.update(updates)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception:
        pass


def _make_handler(
    arm: str,
    upstream: str,
    capture_dir: Path,
    *,
    simulate_local_engine_dry: bool = False,
):
    parts = urlsplit(upstream)
    upstream_host = parts.hostname or "127.0.0.1"
    upstream_port = parts.port or (443 if parts.scheme == "https" else 80)
    conn_cls = (
        http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    )

    class TapHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _relay(self, body: bytes | None, meta_path: Path | None = None) -> None:
            conn = conn_cls(upstream_host, upstream_port, timeout=2400)
            try:
                headers = {
                    name: value
                    for name in _FORWARD_HEADERS
                    if (value := self.headers.get(name)) is not None
                }
                if body is not None:
                    headers["Content-Length"] = str(len(body))
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
                response_chunks: list[bytes] = []
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    response_chunks.append(chunk)
                    self.wfile.write(f"{len(chunk):x}\r\n".encode())
                    self.wfile.write(chunk)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
                if meta_path is not None and response_chunks:
                    telemetry = extract_upstream_telemetry(b"".join(response_chunks))
                    if telemetry:
                        _update_capture_meta(meta_path, telemetry)
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
            extra_meta: dict[str, Any] = {}
            if simulate_local_engine_dry and self.path.endswith("/chat/completions"):
                body, extra_meta = apply_local_engine_dry_policy(body)
            meta_path = _capture(
                capture_dir, arm, "POST", self.path, body, extra_meta=extra_meta
            )
            self._relay(body, meta_path=meta_path)

        def do_GET(self):  # noqa: N802 - health checks relay uncaptured
            self._relay(None)

        def log_message(self, *args):
            pass

    return TapHandler


def create_servers(
    arms: list[tuple[str, int]],
    upstream: str,
    capture_dir: Path | str,
    *,
    simulate_local_engine_dry: bool = False,
    dry_arms: set[str] | None = None,
) -> list[ThreadingHTTPServer]:
    """One ThreadingHTTPServer per (arm, port), all forwarding to the same upstream.
    Callers run each server's serve_forever() (thread or blocking) and shutdown() it."""
    capture_dir = Path(capture_dir)
    servers = []
    for arm, port in arms:
        use_dry = simulate_local_engine_dry or bool(dry_arms and arm in dry_arms)
        handler = _make_handler(
            arm, upstream, capture_dir, simulate_local_engine_dry=use_dry
        )
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
    parser.add_argument(
        "--simulate-local-engine-dry",
        action="store_true",
        help="Inject LocalLlmEngine's out-of-the-box conditional DRY sampler settings on chat completions",
    )
    parser.add_argument(
        "--dry-arm",
        action="append",
        default=[],
        metavar="NAME",
        help="Enable LocalLlmEngine conditional DRY simulation for a specific arm name (repeatable)",
    )
    args = parser.parse_args()

    arms = []
    for spec in args.arm:
        name, _, port = spec.partition("=")
        if not name or not port.isdigit():
            parser.error(f"--arm must be NAME=PORT, got {spec!r}")
        arms.append((name, int(port)))

    servers = create_servers(
        arms,
        args.upstream,
        args.capture_dir,
        simulate_local_engine_dry=args.simulate_local_engine_dry,
        dry_arms=set(args.dry_arm),
    )
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
