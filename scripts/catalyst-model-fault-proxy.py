#!/usr/bin/env python3
"""Local one-shot model fault proxy for Catalyst validation runs.

The proxy forwards requests to one configured OpenAI-compatible upstream.  It can
replace exactly one numbered ``POST /v1/chat/completions`` request with a typed
502 response, which lets the live Catalyst validation matrix exercise bounded
Hub failure without changing product code or stopping the shared model router.
"""

from __future__ import annotations

import argparse
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable


CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
LOOPBACK_HOST = "127.0.0.1"
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
REQUEST_HEADERS_TO_REBUILD = HOP_BY_HOP_HEADERS | {"content-length", "host"}
RESPONSE_HEADERS_TO_REBUILD = HOP_BY_HOP_HEADERS | {"content-length"}


def _event_line(
    *,
    method: str,
    path: str,
    outcome: str,
    status: int,
    chat_call: int | None = None,
) -> str:
    fields = [
        "catalyst-model-fault-proxy",
        f"method={method}",
        f"path={path}",
    ]
    if chat_call is not None:
        fields.append(f"chat_call={chat_call}")
    fields.extend((f"outcome={outcome}", f"status={status}"))
    return " ".join(fields)


def _typed_failure(chat_call: int) -> bytes:
    return json.dumps(
        {
            "error": {
                "type": "catalyst_validation_fault",
                "code": "configured_chat_failure",
                "message": (
                    "A bounded validation fault was injected for chat completion "
                    f"call {chat_call}."
                ),
                "chatCall": chat_call,
                "retryable": False,
            }
        },
        separators=(",", ":"),
    ).encode("utf-8")


class FaultProxyServer(ThreadingHTTPServer):
    """Thread-safe forwarding server with a process-local chat call counter."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        upstream: str,
        fail_chat_call: int,
        timeout_seconds: float = 120.0,
        event_sink: Callable[[str], None] | None = None,
    ) -> None:
        parsed = urllib.parse.urlsplit(upstream)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("upstream must be an absolute http(s) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(
                "upstream credentials must be supplied by headers, not the URL"
            )
        if fail_chat_call < 1:
            raise ValueError("fail_chat_call must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.upstream = upstream.rstrip("/")
        self.fail_chat_call = fail_chat_call
        self.timeout_seconds = timeout_seconds
        self._chat_calls = 0
        self._chat_calls_lock = threading.Lock()
        self._event_sink = event_sink or (lambda line: print(line, flush=True))
        super().__init__(server_address, FaultProxyHandler)

    def next_chat_call(self) -> int:
        with self._chat_calls_lock:
            self._chat_calls += 1
            return self._chat_calls

    def emit(self, line: str) -> None:
        self._event_sink(line)


class FaultProxyHandler(BaseHTTPRequestHandler):
    server: FaultProxyServer

    def log_message(self, format: str, *args: Any) -> None:
        # BaseHTTPRequestHandler includes client/request detail.  The explicit
        # event below is the only evidence emitted by this validation utility.
        return

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        *,
        headers: Any = None,
        content_type: str | None = None,
    ) -> None:
        self.send_response(status)
        if headers is not None:
            for name, value in headers.items():
                if name.lower() not in RESPONSE_HEADERS_TO_REBUILD:
                    self.send_header(name, value)
        if content_type is not None:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _request_body(self) -> bytes | None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return None
        return self.rfile.read(content_length)

    def _forward(self, *, path: str, chat_call: int | None) -> None:
        body = self._request_body()
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in REQUEST_HEADERS_TO_REBUILD
        }
        request = urllib.request.Request(
            f"{self.server.upstream}{self.path}",
            data=body,
            headers=headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.server.timeout_seconds,
            ) as response:
                response_body = response.read()
                status = response.status
                self._send_bytes(status, response_body, headers=response.headers)
        except urllib.error.HTTPError as error:
            response_body = error.read()
            status = error.code
            self._send_bytes(status, response_body, headers=error.headers)
        except (urllib.error.URLError, TimeoutError, OSError):
            status = 502
            response_body = json.dumps(
                {
                    "error": {
                        "type": "catalyst_validation_proxy_error",
                        "code": "upstream_unavailable",
                        "message": "The configured model upstream was unavailable.",
                        "retryable": True,
                    }
                },
                separators=(",", ":"),
            ).encode("utf-8")
            self._send_bytes(
                status,
                response_body,
                content_type="application/json",
            )

        self.server.emit(
            _event_line(
                method=self.command,
                path=path,
                chat_call=chat_call,
                outcome="forwarded" if status != 502 else "upstream_error",
                status=status,
            )
        )

    def _handle(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        chat_call = None
        if self.command == "POST" and path == CHAT_COMPLETIONS_PATH:
            chat_call = self.server.next_chat_call()
            if chat_call == self.server.fail_chat_call:
                # Drain the request before replying so a keep-alive client cannot
                # mistake its body for the next request on the connection.
                self._request_body()
                body = _typed_failure(chat_call)
                self._send_bytes(502, body, content_type="application/json")
                self.server.emit(
                    _event_line(
                        method=self.command,
                        path=path,
                        chat_call=chat_call,
                        outcome="injected",
                        status=502,
                    )
                )
                return

        self._forward(path=path, chat_call=chat_call)

    do_DELETE = _handle
    do_GET = _handle
    do_HEAD = _handle
    do_OPTIONS = _handle
    do_PATCH = _handle
    do_POST = _handle
    do_PUT = _handle


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upstream", required=True, help="OpenAI-compatible upstream base URL"
    )
    parser.add_argument(
        "--port", type=int, default=18078, help="localhost port (default: 18078)"
    )
    parser.add_argument(
        "--fail-chat-call",
        type=_positive_int,
        required=True,
        help="one-based POST /v1/chat/completions call number to fail exactly once",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=_positive_float,
        default=120.0,
        help="upstream request timeout (default: 120)",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    server = FaultProxyServer(
        (LOOPBACK_HOST, args.port),
        upstream=args.upstream,
        fail_chat_call=args.fail_chat_call,
        timeout_seconds=args.timeout_seconds,
    )
    host, port = server.server_address
    print(
        "catalyst-model-fault-proxy "
        f"listening=http://{host}:{port} fail_chat_call={args.fail_chat_call}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
