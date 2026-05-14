"""Tests for harness.ocl bootstrap + credentials.

Closes H7 from the PR #5 remediation plan (constitution Principle V: behavioral
changes MUST add or update tests). Covers:
  - basic auth header encoding + non-logging,
  - parse_progress against a fixture import record,
  - marker-file based idempotency (read/write/check),
  - upload multipart-body shape (against a stdlib http.server fixture),
  - credentials resolution priority (env > keychain),
  - no token appears in stdout/stderr around module use.

These are unit-level tests — they do NOT hit a real OpenMRS or OCL. The
multipart-body test spins up a one-shot localhost HTTP server in a thread.
"""

from __future__ import annotations

import base64
import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest


# --- 1. basic auth header --------------------------------------------------


def test_basic_auth_header_encodes_correctly(monkeypatch):
    from harness.ocl import bootstrap as b

    monkeypatch.setattr(b, "_USER", "admin")
    monkeypatch.setattr(b, "_PASS", "Admin123")
    header = b._basic_auth_header()
    assert header.startswith("Basic ")
    decoded = base64.b64decode(header[len("Basic "):]).decode()
    assert decoded == "admin:Admin123"


def test_basic_auth_header_handles_special_chars(monkeypatch):
    # Password with a colon (RFC 7617 says user MUST NOT contain colon; password may).
    from harness.ocl import bootstrap as b

    monkeypatch.setattr(b, "_USER", "admin")
    monkeypatch.setattr(b, "_PASS", "pa:ss:word")
    decoded = base64.b64decode(b._basic_auth_header()[len("Basic "):]).decode()
    assert decoded == "admin:pa:ss:word"


# --- 2. parse_progress fixture ---------------------------------------------


def test_parse_progress_from_fixture():
    from harness.ocl.bootstrap import parse_progress

    fixture_path = Path(__file__).parent / "fixtures" / "import-record-sample.json"
    data = json.loads(fixture_path.read_text())
    prog = parse_progress(data)

    assert prog.uuid == "abc-123-test-uuid"
    assert prog.progress_pct == 100
    assert prog.status == "import-done"
    assert prog.all_items == 49612
    assert prog.added == 49612
    assert prog.errors == 0
    assert prog.error_message is None
    assert prog.is_finished is True
    assert prog.is_success is True


def test_parse_progress_running_state():
    from harness.ocl.bootstrap import parse_progress

    running = {
        "uuid": "running-uuid",
        "localDateStarted": "2026-04-29T10:15:00.000-0700",
        "localDateStopped": None,
        "importProgress": "42",
        "status": "running",
        "allItemsCount": 50000,
        "addedItemsCount": 21000,
        "errorItemsCount": 0,
        "errorMessage": None,
    }
    prog = parse_progress(running)
    assert prog.is_finished is False
    assert prog.is_success is False
    assert prog.progress_pct == 42


# --- 3. marker-file idempotency --------------------------------------------


def test_marker_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from harness.ocl.bootstrap import read_marker, write_marker

    assert read_marker("v2026-04-28") is None
    path = write_marker("v2026-04-28", "imp-uuid-xyz")
    assert path.exists()
    payload = read_marker("v2026-04-28")
    assert payload["version"] == "v2026-04-28"
    assert payload["import_uuid"] == "imp-uuid-xyz"
    assert "imported_at" in payload


def test_marker_handles_corrupt_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from harness.ocl.bootstrap import _marker_path, read_marker

    p = _marker_path("v9999-99-99")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ not valid json")
    assert read_marker("v9999-99-99") is None


def test_is_already_bootstrapped_requires_live_subscription(tmp_path, monkeypatch):
    """Marker alone is not enough — live subscription URL must match."""
    monkeypatch.chdir(tmp_path)
    from harness.ocl import bootstrap as b

    b.write_marker("v2026-04-28", "imp-uuid")

    # Subscription returns the wrong URL → not bootstrapped.
    monkeypatch.setattr(b, "get_subscription", lambda: {"url": "https://other.example/CIEL/v2025-01-01/"})
    assert b.is_already_bootstrapped("v2026-04-28") is False

    # Subscription returns the right URL → bootstrapped.
    monkeypatch.setattr(
        b, "get_subscription",
        lambda: {"url": "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/v2026-04-28/"},
    )
    assert b.is_already_bootstrapped("v2026-04-28") is True

    # Subscription call throws → defensive: not bootstrapped (don't short-circuit on transient failure).
    def boom():
        raise RuntimeError("connection refused")
    monkeypatch.setattr(b, "get_subscription", boom)
    assert b.is_already_bootstrapped("v2026-04-28") is False


def test_is_already_bootstrapped_no_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from harness.ocl import bootstrap as b

    monkeypatch.setattr(b, "get_subscription", lambda: {"url": "anything"})
    assert b.is_already_bootstrapped("v2026-04-28") is False


# --- 4. multipart body shape -----------------------------------------------


class _CaptureHandler(BaseHTTPRequestHandler):
    captured: dict = {}

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        _CaptureHandler.captured = {
            "content_type": self.headers.get("Content-Type", ""),
            "authorization": self.headers.get("Authorization", ""),
            "body": body,
        }
        resp = json.dumps({"uuid": "test-import-uuid"}).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, *args, **kwargs):  # silence stderr
        pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_upload_import_zip_multipart_body_shape(tmp_path, monkeypatch):
    """Spin up a one-shot HTTP server, point bootstrap at it, verify the upload."""
    port = _free_port()
    from harness.ocl import bootstrap as b

    # Patch the module-level URL constants so we don't depend on import order.
    monkeypatch.setattr(b, "_IMP_URL", f"http://127.0.0.1:{port}/openmrs/ws/rest/v1/openconceptlab/import")
    monkeypatch.setattr(b, "_USER", "admin")
    monkeypatch.setattr(b, "_PASS", "Admin123")

    zip_path = tmp_path / "CIEL_test.zip"
    zip_bytes = b"PK\x03\x04this-is-not-a-real-zip-but-bytes-suffice"
    zip_path.write_bytes(zip_bytes)

    server = HTTPServer(("127.0.0.1", port), _CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        uuid = b.upload_import_zip(zip_path)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert uuid == "test-import-uuid"
    captured = _CaptureHandler.captured
    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    assert captured["authorization"].startswith("Basic ")
    body = captured["body"]
    assert b'name="file"' in body
    assert b'filename="CIEL_test.zip"' in body
    assert zip_bytes in body  # the raw bytes are present verbatim


# --- 5. credentials resolution ---------------------------------------------


def test_get_token_env_wins_over_keychain(monkeypatch):
    monkeypatch.setenv("OCL_TOKEN", "env-token-xyz")
    # Even if the keychain function returns something, env wins.
    from harness.ocl import credentials

    monkeypatch.setattr(credentials, "_get_from_macos_keychain", lambda s: "keychain-token-abc")
    assert credentials.get_token() == "env-token-xyz"


def test_get_token_falls_back_to_keychain(monkeypatch):
    monkeypatch.delenv("OCL_TOKEN", raising=False)
    from harness.ocl import credentials

    monkeypatch.setattr(credentials, "_get_from_macos_keychain", lambda s: "keychain-token-abc")
    assert credentials.get_token() == "keychain-token-abc"


def test_get_token_raises_when_unresolved(monkeypatch):
    monkeypatch.delenv("OCL_TOKEN", raising=False)
    from harness.ocl import credentials
    from harness.ocl.credentials import OCLTokenError

    monkeypatch.setattr(credentials, "_get_from_macos_keychain", lambda s: None)
    with pytest.raises(OCLTokenError):
        credentials.get_token()


# --- 6. token never logged -------------------------------------------------


def test_token_does_not_leak_to_stdout_on_import(monkeypatch, capsys):
    sentinel = "DO_NOT_LEAK_THIS_TOKEN_VALUE_42"
    monkeypatch.setenv("OCL_TOKEN", sentinel)
    sys.modules.pop("harness.ocl", None)
    sys.modules.pop("harness.ocl.credentials", None)
    sys.modules.pop("harness.ocl.bootstrap", None)
    import harness.ocl  # noqa: F401
    from harness.ocl import get_token

    _ = get_token()
    out = capsys.readouterr()
    assert sentinel not in out.out
    assert sentinel not in out.err
