from __future__ import annotations

import importlib.util
import json
from email.message import Message
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "probe_chartsearchai_relay", ROOT / "scripts" / "probe-chartsearchai-relay.py"
)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class FakeResponse:
    def __init__(self, body: bytes | list[bytes], headers: dict[str, str] | None = None):
        self._body = body
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def __iter__(self):
        assert isinstance(self._body, list)
        return iter(self._body)

    def read(self):
        assert isinstance(self._body, bytes)
        return self._body


def test_probe_requires_answer_done_and_hydrated_same_row(monkeypatch):
    answer = {
        "session": "session-1",
        "messageId": "message-1",
        "auditLogId": 42,
        "answer": "The latest visit was 2026-07-10 [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "validating"},
        "references": [{"index": 1}],
    }
    final = {
        **answer,
        "answer": "The checked latest visit was 2026-07-10 [1].",
        "answerValidation": {"status": "checked", "label": "Checked"},
        "references": [
            {
                "index": 1,
                "resolutionStatus": "resolved",
                "groundingStatus": "verified",
            }
        ],
        "blocks": [{"kind": "paragraph", "text": "Summary"}],
        "safetyWarnings": [{"type": "interaction", "detail": "Check therapy"}],
        "confidence": {"answer": {"level": "green"}},
        "inDepth": {"status": "complete", "answer": "Supporting detail [1]."},
    }
    history = {
        "session": "session-1",
        "messages": [
            {
                "messageId": "message-1",
                "auditLogId": 42,
                "role": "assistant",
                "content": final["answer"],
                "references": final["references"],
                "blocks": final["blocks"],
                "safetyWarnings": final["safetyWarnings"],
                "confidence": final["confidence"],
                "answerValidation": final["answerValidation"],
                "inDepth": final["inDepth"],
            }
        ],
    }
    responses = iter(
        [
            FakeResponse(
                [
                    b"event: answer_done\n",
                    f"data: {json.dumps(answer)}\n".encode(),
                    b"\n",
                    b"event: answer_validation\n",
                    f"data: {json.dumps(final)}\n".encode(),
                    b"\n",
                    b"event: indepth_pending\n",
                    f"data: {json.dumps(final)}\n".encode(),
                    b"\n",
                    b"event: indepth_done\n",
                    f"data: {json.dumps(final)}\n".encode(),
                    b"\n",
                    b"event: done\n",
                    f"data: {json.dumps(final)}\n".encode(),
                    b"\n",
                ],
                {"X-ChartSearchAi-Session": "session-1"},
            ),
            FakeResponse(json.dumps(history).encode()),
            FakeResponse(json.dumps({"session": "session-2"}).encode()),
            FakeResponse(json.dumps({"session": "session-2", "messages": []}).encode()),
        ]
    )
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return next(responses)

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        probe,
        "_runtime_identity",
        lambda _openmrs_url: {
            "harness": {"commit": "harness-sha", "tree_clean": True},
            "deployment": {"revision": "hub-sha"},
        },
    )

    result = probe.probe_relay(
        "http://openmrs/openmrs",
        patient="patient-1",
        profile="single-e4b-checked",
        question="Latest visit?",
        username="admin",
        password="secret",
        timeout=30,
        clear_after=True,
    )

    assert result["hydrated"] is True
    assert result["schema_version"] == "chartsearchai_relay_probe.v2"
    assert result["session"] == "session-1"
    assert result["message_id"] == "message-1"
    assert result["profile"] == "single-e4b-checked"
    assert result["audit_log_id"] == 42
    assert result["answer_validation"] == {"status": "checked", "label": "Checked"}
    assert result["reference_count"] == 1
    assert result["in_depth_status"] == "complete"
    assert result["final_envelope_sha256"] == result["hydrated_envelope_sha256"]
    assert result["events"] == [
        "answer_done",
        "answer_validation",
        "indepth_pending",
        "indepth_done",
        "done",
    ]
    assert result["cleared_after"] is True
    assert result["runtime_identity"]["harness"]["commit"] == "harness-sha"
    assert [request.full_url for request, _ in requests] == [
        "http://openmrs/openmrs/ws/rest/v1/chartsearchai/chat/stream",
        "http://openmrs/openmrs/ws/rest/v1/chartsearchai/chat?patient=patient-1",
        "http://openmrs/openmrs/ws/rest/v1/chartsearchai/chat/new",
        "http://openmrs/openmrs/ws/rest/v1/chartsearchai/chat?patient=patient-1",
    ]
    assert all(request.get_header("Authorization") for request, _ in requests)


def test_stream_probe_rejects_error_event(monkeypatch):
    response = FakeResponse(
        [b"event: error\n", b"data: context source unavailable\n", b"\n"]
    )
    monkeypatch.setattr(probe.urllib.request, "urlopen", lambda *_args, **_kwargs: response)

    try:
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )
    except RuntimeError as exc:
        assert "context source unavailable" in str(exc)
    else:
        raise AssertionError("expected relay error")


def test_stream_probe_rejects_incomplete_review_sequence(monkeypatch):
    answer = {
        "session": "session-1",
        "messageId": "message-1",
        "auditLogId": 42,
        "answer": "Answer [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "validating"},
        "references": [{"index": 1}],
    }
    final = {
        **answer,
        "answerValidation": {"status": "checked"},
        "references": [
            {
                "index": 1,
                "resolutionStatus": "resolved",
                "groundingStatus": "verified",
            }
        ],
        "inDepth": {"status": "complete", "answer": "Detail [1]."},
    }
    response = FakeResponse(
        [
            b"event: answer_done\n",
            f"data: {json.dumps(answer)}\n".encode(),
            b"\n",
            b"event: indepth_pending\n",
            f"data: {json.dumps(final)}\n".encode(),
            b"\n",
            b"event: indepth_done\n",
            f"data: {json.dumps(final)}\n".encode(),
            b"\n",
            b"event: done\n",
            f"data: {json.dumps(final)}\n".encode(),
            b"\n",
        ]
    )
    monkeypatch.setattr(probe.urllib.request, "urlopen", lambda *_args, **_kwargs: response)

    with pytest.raises(RuntimeError, match="lifecycle was incomplete"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def test_stream_probe_rejects_resolved_reference_without_grounding(monkeypatch):
    answer = {
        "session": "session-1",
        "messageId": "message-1",
        "auditLogId": 42,
        "answer": "Answer [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "validating"},
        "references": [{"index": 1}],
    }
    final = {
        **answer,
        "answerValidation": {"status": "checked"},
        "references": [{"index": 1, "resolutionStatus": "resolved"}],
        "inDepth": {"status": "complete", "answer": "Detail [1]."},
    }
    chunks: list[bytes] = []
    for event, payload in [
        ("answer_done", answer),
        ("answer_validation", final),
        ("indepth_pending", final),
        ("indepth_done", final),
        ("done", final),
    ]:
        chunks.extend(
            [
                f"event: {event}\n".encode(),
                f"data: {json.dumps(payload)}\n".encode(),
                b"\n",
            ]
        )
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(chunks),
    )

    with pytest.raises(RuntimeError, match="lacked a terminal grounding verdict"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )
