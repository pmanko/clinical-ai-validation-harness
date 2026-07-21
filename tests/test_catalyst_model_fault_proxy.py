from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "catalyst-model-fault-proxy.py"
SPEC = importlib.util.spec_from_file_location("catalyst_model_fault_proxy", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
fault_proxy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fault_proxy
SPEC.loader.exec_module(fault_proxy)


class _UpstreamState:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []


def _upstream_handler(state: _UpstreamState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0"))
            return self.rfile.read(length) if length else b""

        def _send(self, payload: dict[str, Any], *, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Upstream-Evidence", "forwarded")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            state.requests.append({"method": "GET", "path": self.path})
            self._send({"object": "list", "data": [{"id": "test-model"}]})

        def do_POST(self) -> None:  # noqa: N802
            body = self._body()
            state.requests.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "body": body,
                    "authorization": self.headers.get("Authorization"),
                }
            )
            self._send(
                {
                    "id": f"completion-{len(state.requests)}",
                    "received": json.loads(body),
                }
            )

    return Handler


@contextmanager
def _running_server(server: ThreadingHTTPServer) -> Iterator[ThreadingHTTPServer]:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextmanager
def _stack(*, fail_chat_call: int) -> Iterator[tuple[str, _UpstreamState, list[str]]]:
    state = _UpstreamState()
    events: list[str] = []
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _upstream_handler(state))
    with _running_server(upstream):
        upstream_url = f"http://127.0.0.1:{upstream.server_address[1]}"
        proxy = fault_proxy.FaultProxyServer(
            ("127.0.0.1", 0),
            upstream=upstream_url,
            fail_chat_call=fail_chat_call,
            event_sink=events.append,
        )
        with _running_server(proxy):
            yield f"http://127.0.0.1:{proxy.server_address[1]}", state, events


def _request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer test-secret",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.load(response), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error), dict(error.headers)


def test_forwards_models_and_ordinary_requests_without_logging_secrets() -> None:
    with _stack(fail_chat_call=99) as (proxy_url, upstream, events):
        status, models, headers = _request(proxy_url, "/v1/models?scope=available")
        ordinary_status, ordinary, _ = _request(
            proxy_url,
            "/v1/embeddings",
            method="POST",
            payload={"model": "test-model", "input": "not logged"},
        )

    assert status == 200
    assert models["data"] == [{"id": "test-model"}]
    assert headers["X-Upstream-Evidence"] == "forwarded"
    assert ordinary_status == 200
    assert ordinary["received"]["input"] == "not logged"
    assert upstream.requests == [
        {"method": "GET", "path": "/v1/models?scope=available"},
        {
            "method": "POST",
            "path": "/v1/embeddings",
            "body": b'{"model": "test-model", "input": "not logged"}',
            "authorization": "Bearer test-secret",
        },
    ]
    assert events == [
        "catalyst-model-fault-proxy method=GET path=/v1/models outcome=forwarded status=200",
        "catalyst-model-fault-proxy method=POST path=/v1/embeddings outcome=forwarded status=200",
    ]
    assert all(
        "test-secret" not in event and "not logged" not in event for event in events
    )


def test_fails_only_the_configured_second_chat_call_then_resumes_forwarding() -> None:
    with _stack(fail_chat_call=2) as (proxy_url, upstream, events):
        first = _request(
            proxy_url,
            "/v1/chat/completions",
            method="POST",
            payload={"model": "writer", "messages": []},
        )
        second = _request(
            proxy_url,
            "/v1/chat/completions",
            method="POST",
            payload={"model": "reviewer", "messages": []},
        )
        third = _request(
            proxy_url,
            "/v1/chat/completions",
            method="POST",
            payload={"model": "writer", "messages": []},
        )

    assert first[0] == 200
    assert second[0] == 502
    assert second[1] == {
        "error": {
            "type": "catalyst_validation_fault",
            "code": "configured_chat_failure",
            "message": "A bounded validation fault was injected for chat completion call 2.",
            "chatCall": 2,
            "retryable": False,
        }
    }
    assert third[0] == 200
    assert [request["body"] for request in upstream.requests] == [
        b'{"model": "writer", "messages": []}',
        b'{"model": "writer", "messages": []}',
    ]
    assert events == [
        "catalyst-model-fault-proxy method=POST path=/v1/chat/completions "
        "chat_call=1 outcome=forwarded status=200",
        "catalyst-model-fault-proxy method=POST path=/v1/chat/completions "
        "chat_call=2 outcome=injected status=502",
        "catalyst-model-fault-proxy method=POST path=/v1/chat/completions "
        "chat_call=3 outcome=forwarded status=200",
    ]


def test_forwards_upstream_http_errors_verbatim() -> None:
    class ErrorHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            body = json.dumps({"error": {"code": "model_not_found"}}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), ErrorHandler)
    events: list[str] = []
    with _running_server(upstream):
        proxy = fault_proxy.FaultProxyServer(
            ("127.0.0.1", 0),
            upstream=f"http://127.0.0.1:{upstream.server_address[1]}",
            fail_chat_call=99,
            event_sink=events.append,
        )
        with _running_server(proxy):
            status, body, _ = _request(
                f"http://127.0.0.1:{proxy.server_address[1]}", "/v1/models/none"
            )

    assert status == 404
    assert body == {"error": {"code": "model_not_found"}}
    assert events == [
        "catalyst-model-fault-proxy method=GET path=/v1/models/none "
        "outcome=forwarded status=404",
    ]


def test_reports_typed_error_when_upstream_is_unreachable() -> None:
    # Bind then close a socket so the port is guaranteed dead.
    dead = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    dead_url = f"http://127.0.0.1:{dead.server_address[1]}"
    dead.server_close()

    events: list[str] = []
    proxy = fault_proxy.FaultProxyServer(
        ("127.0.0.1", 0),
        upstream=dead_url,
        fail_chat_call=99,
        timeout_seconds=1.0,
        event_sink=events.append,
    )
    with _running_server(proxy):
        status, body, _ = _request(
            f"http://127.0.0.1:{proxy.server_address[1]}", "/v1/models"
        )

    assert status == 502
    assert body["error"]["code"] == "upstream_unavailable"
    assert events == [
        "catalyst-model-fault-proxy method=GET path=/v1/models "
        "outcome=upstream_error status=502",
    ]


def test_server_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="absolute http"):
        fault_proxy.FaultProxyServer(
            ("127.0.0.1", 0), upstream="ftp://x", fail_chat_call=1
        )
    with pytest.raises(ValueError, match="credentials"):
        fault_proxy.FaultProxyServer(
            ("127.0.0.1", 0),
            upstream="http://user:pass@example.com",
            fail_chat_call=1,
        )
    with pytest.raises(ValueError, match="at least 1"):
        fault_proxy.FaultProxyServer(
            ("127.0.0.1", 0), upstream="http://example.com", fail_chat_call=0
        )
    with pytest.raises(ValueError, match="positive"):
        fault_proxy.FaultProxyServer(
            ("127.0.0.1", 0),
            upstream="http://example.com",
            fail_chat_call=1,
            timeout_seconds=0,
        )


def test_argument_validators_reject_out_of_range_values() -> None:
    assert fault_proxy._positive_int("2") == 2
    assert fault_proxy._positive_float("0.5") == 0.5
    with pytest.raises(argparse.ArgumentTypeError):
        fault_proxy._positive_int("0")
    with pytest.raises(argparse.ArgumentTypeError):
        fault_proxy._positive_float("0")


def test_main_starts_a_configured_server_and_stops_on_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "catalyst-model-fault-proxy.py",
            "--upstream",
            "http://127.0.0.1:9",
            "--port",
            "0",
            "--fail-chat-call",
            "2",
            "--timeout-seconds",
            "5",
        ],
    )
    monkeypatch.setattr(
        fault_proxy.FaultProxyServer,
        "serve_forever",
        lambda self: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    assert fault_proxy.main() == 0
    banner = capsys.readouterr().out
    assert "catalyst-model-fault-proxy listening=http://127.0.0.1:" in banner
    assert "fail_chat_call=2" in banner
