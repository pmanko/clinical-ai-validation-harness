"""Tests for harness.profile.ciel_import_errors.

Covers the response-parser (item projection + OCL URL identity extraction +
referenced-concept extraction), the gate-rate computation, and the paginator
against a stdlib http.server fixture — same shape as test_bootstrap.py's
multipart-body test.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


# --- 1. URL identity + referenced-concept extraction ----------------------


def test_parse_ocl_url_extracts_source_and_code():
    from harness.profile.ciel_import_errors import _parse_ocl_url

    ident = _parse_ocl_url(
        "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/mappings/13127663/"
    )
    assert ident == {"org": "CIEL", "source": "CIEL", "kind": "mappings", "code": "13127663"}


def test_parse_ocl_url_returns_empty_for_non_match():
    from harness.profile.ciel_import_errors import _parse_ocl_url

    assert _parse_ocl_url("") == {}
    assert _parse_ocl_url(None) == {}
    assert _parse_ocl_url("https://example.com/other") == {}


def test_extract_referred_concept_from_error_message():
    from harness.profile.ciel_import_errors import _extract_referred_concept

    msg = (
        "Cannot save mapping https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/mappings/13127663/ "
        "[CAUSE]: Cannot create mapping from concept with URL "
        "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/concepts/78200/, "
        "because the concept has not been imported"
    )
    referred = _extract_referred_concept(msg)
    assert referred == {"source": "CIEL", "code": "78200"}


def test_extract_referred_concept_none_when_absent():
    from harness.profile.ciel_import_errors import _extract_referred_concept

    assert _extract_referred_concept(None) is None
    assert _extract_referred_concept("plain error, no URL") is None


# --- 2. project_item shape -------------------------------------------------


def test_project_item_preserves_evidence_and_adds_identity():
    from harness.profile.ciel_import_errors import _project_item

    raw = {
        "uuid": "2c42635e-07a9-428d-bd82-8b4e03a130f7",
        "type": "MAPPING",
        "state": "ERROR",
        "url": "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/mappings/13127663/",
        "versionUrl": "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/mappings/13127663/",
        "hashedUrl": "NfT6HqQ4+7FdaLxI3ZBd6w==",
        "updatedOn": "2026-04-28T07:49:56.000+0000",
        "errorMessage": (
            "Cannot save mapping [CAUSE]: Cannot create mapping from concept with URL "
            "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/concepts/78200/, "
            "because the concept has not been imported"
        ),
    }
    out = _project_item(raw)
    assert out["uuid"] == raw["uuid"]
    assert out["type"] == "MAPPING"
    assert out["identity"] == {
        "org": "CIEL", "source": "CIEL", "kind": "mappings", "code": "13127663",
    }
    assert out["referenced_concept"] == {"source": "CIEL", "code": "78200"}
    assert out["error_message"] == raw["errorMessage"]


# --- 3. build_payload + gate -----------------------------------------------


def test_build_payload_gate_passes_under_threshold():
    from harness.profile.ciel_import_errors import build_payload, GATE_THRESHOLD

    payload = build_payload(
        import_uuid="abc",
        all_items_count=358026,
        error_items_count=133,
        errors=[],
        generated_at="2026-05-14T12:00:00Z",
    )
    assert payload["gate_threshold"] == GATE_THRESHOLD
    assert payload["error_rate"] < GATE_THRESHOLD
    assert payload["gate_passed"] is True
    assert payload["generated_at"] == "2026-05-14T12:00:00Z"


def test_build_payload_gate_fails_over_threshold():
    from harness.profile.ciel_import_errors import build_payload

    payload = build_payload(
        import_uuid="abc",
        all_items_count=1000,
        error_items_count=5,  # 0.5%
        errors=[],
    )
    assert payload["gate_passed"] is False


def test_build_payload_handles_zero_items():
    from harness.profile.ciel_import_errors import build_payload

    payload = build_payload(
        import_uuid="empty", all_items_count=0, error_items_count=0, errors=[]
    )
    assert payload["error_rate"] == 0.0
    assert payload["gate_passed"] is True


# --- 4. paginator against a stdlib http.server fixture --------------------


class _PaginatedHandler(BaseHTTPRequestHandler):
    """Serves two pages of error items with a `next` link, then nothing."""

    pages_by_start: dict = {}

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        start = int(qs.get("startIndex", ["0"])[0])
        body = json.dumps(_PaginatedHandler.pages_by_start[start]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs):
        pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_iter_error_items_follows_next_link(monkeypatch):
    port = _free_port()
    base = f"http://127.0.0.1:{port}/openmrs/ws/rest/v1/openconceptlab/import"
    uuid = "the-uuid"

    page0_next = (
        f"{base}/{uuid}/item?state=ERROR&v=full&limit=2&startIndex=2"
    )
    _PaginatedHandler.pages_by_start = {
        0: {
            "results": [
                {"uuid": "a", "type": "MAPPING", "state": "ERROR",
                 "url": "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/mappings/1/",
                 "errorMessage": "boom"},
                {"uuid": "b", "type": "MAPPING", "state": "ERROR",
                 "url": "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/mappings/2/",
                 "errorMessage": "boom"},
            ],
            "links": [{"rel": "next", "uri": page0_next}],
        },
        2: {
            "results": [
                {"uuid": "c", "type": "CONCEPT", "state": "ERROR",
                 "url": "https://api.openconceptlab.org/orgs/CIEL/sources/CIEL/concepts/3/",
                 "errorMessage": "nope"},
            ],
            "links": [],
        },
    }

    server = HTTPServer(("127.0.0.1", port), _PaginatedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from harness.ocl import bootstrap as b
        from harness.profile import ciel_import_errors as cie

        monkeypatch.setattr(b, "_IMP_URL", base)
        monkeypatch.setattr(b, "_USER", "admin")
        monkeypatch.setattr(b, "_PASS", "Admin123")

        items = list(cie._iter_error_items(uuid, page_size=2))
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert [it["uuid"] for it in items] == ["a", "b", "c"]
    assert items[-1]["type"] == "CONCEPT"


# --- 5. write_payload roundtrip -------------------------------------------


def test_write_payload_creates_file(tmp_path):
    from harness.profile.ciel_import_errors import build_payload, write_payload

    payload = build_payload(
        import_uuid="u",
        all_items_count=10,
        error_items_count=0,
        errors=[],
    )
    out = write_payload(payload, run_id="dev-test", root=tmp_path)
    assert out.exists()
    assert out.name == "ciel-import-errors.json"
    assert out.parent.name == "profile"
    on_disk = json.loads(out.read_text())
    assert on_disk["import_uuid"] == "u"
    assert on_disk["gate_passed"] is True
