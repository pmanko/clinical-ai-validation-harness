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
    pending = {**final, "inDepth": {"status": "pending", "answer": ""}}
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
                    f"data: {json.dumps(pending)}\n".encode(),
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
    assert result["in_depth_terminal_event"] == "indepth_done"
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
    pending = {**final, "inDepth": {"status": "pending", "answer": ""}}
    response = FakeResponse(
        [
            b"event: answer_done\n",
            f"data: {json.dumps(answer)}\n".encode(),
            b"\n",
            b"event: indepth_pending\n",
            f"data: {json.dumps(pending)}\n".encode(),
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
    pending = {**final, "inDepth": {"status": "pending", "answer": ""}}
    chunks: list[bytes] = []
    for event, payload in [
        ("answer_done", answer),
        ("answer_validation", final),
        ("indepth_pending", pending),
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


def test_stream_probe_accepts_reasoned_terminal_safety_withholding(monkeypatch):
    answer = {
        "session": "session-1",
        "messageId": "message-1",
        "auditLogId": 42,
        "answer": "The model answer needs review.",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "validating"},
        "references": [],
    }
    final = {
        **answer,
        "answerValidation": {
            "status": "needs_review",
            "label": "Needs review",
            "issues": [{"id": "citation_scope", "reason": "Citations were ambiguous."}],
        },
        "inDepth": {
            "status": "needs_review",
            "answer": "",
            "error": "In-Depth was withheld because evidence checks rejected every claim.",
            "validation": {"status": "needs_review"},
        },
    }
    pending = {**final, "inDepth": {"status": "pending", "answer": ""}}
    chunks: list[bytes] = []
    for event, payload in [
        ("answer_done", answer),
        ("answer_validation", final),
        ("indepth_pending", pending),
        ("indepth_error", final),
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

    result = probe._stream_turn(
        "http://openmrs/chat/stream",
        patient="patient-1",
        profile="single-e4b-checked",
        question="Latest visit?",
        username="admin",
        password="secret",
        timeout=30,
    )

    assert result["final_answer_validation"]["status"] == "needs_review"
    assert result["in_depth_terminal_event"] == "indepth_error"
    assert result["final_in_depth"]["status"] == "needs_review"


def test_stream_probe_rejects_unavailable_indepth_review(monkeypatch):
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
        "inDepth": {
            "status": "needs_review",
            "answer": "",
            "error": "In-Depth review was unavailable.",
            "validation": {"status": "needs_review", "review_status": "unavailable"},
        },
    }
    pending = {**final, "inDepth": {"status": "pending", "answer": ""}}
    chunks: list[bytes] = []
    for event, payload in [
        ("answer_done", answer),
        ("answer_validation", final),
        ("indepth_pending", pending),
        ("indepth_error", final),
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

    with pytest.raises(RuntimeError, match="review was unavailable"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def _terminal_chunks(answer, final, *, terminal_event="indepth_done", phase=None):
    pending = {**final, "inDepth": {"status": "pending", "answer": ""}}
    events = [
        ("answer_done", answer),
        ("answer_validation", phase or final),
        ("indepth_pending", pending),
        (terminal_event, final),
        ("done", final),
    ]
    chunks: list[bytes] = []
    for event, payload in events:
        chunks.extend(
            [
                f"event: {event}\n".encode(),
                f"data: {json.dumps(payload)}\n".encode(),
                b"\n",
            ]
        )
    return chunks


def _answer_and_final(*, grounding_status="verified", include_index=True):
    answer = {
        "session": "session-1",
        "messageId": "message-1",
        "auditLogId": 42,
        "answer": "Answer [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "validating"},
        "references": [{"index": 1}],
    }
    reference = {
        "resolutionStatus": "resolved",
        "groundingStatus": grounding_status,
    }
    if include_index:
        reference["index"] = 1
    final = {
        **answer,
        "answerValidation": {"status": "checked", "label": "Checked"},
        "references": [reference],
        "inDepth": {"status": "complete", "answer": "Detail [1]."},
    }
    return answer, final


def test_stream_probe_rejects_checked_answer_with_unsupported_evidence(monkeypatch):
    answer, final = _answer_and_final(grounding_status="unsupported")
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(_terminal_chunks(answer, final)),
    )

    with pytest.raises(RuntimeError, match="checked answer retained"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def test_stream_probe_rejects_phase_update_to_different_row(monkeypatch):
    answer, final = _answer_and_final()
    wrong_phase = {**final, "messageId": "message-2"}
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            _terminal_chunks(answer, final, phase=wrong_phase)
        ),
    )

    with pytest.raises(RuntimeError, match="different assistant row"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def test_stream_probe_rejects_withholding_without_validation_metadata(monkeypatch):
    answer, final = _answer_and_final()
    final["answerValidation"] = {
        "status": "needs_review",
        "issues": [{"reason": "Answer citations need review."}],
    }
    final["inDepth"] = {
        "status": "needs_review",
        "answer": "",
        "error": "In-Depth was withheld.",
        "validation": {},
    }
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            _terminal_chunks(answer, final, terminal_event="indepth_error")
        ),
    )

    with pytest.raises(RuntimeError, match="lost needs-review validation metadata"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def test_stream_probe_rejects_reference_without_positive_index(monkeypatch):
    answer, final = _answer_and_final(include_index=False)
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(_terminal_chunks(answer, final)),
    )

    with pytest.raises(RuntimeError, match="positive integer index"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def test_stream_probe_rejects_malformed_needs_review_issues(monkeypatch):
    answer, final = _answer_and_final()
    final["answerValidation"] = {"status": "needs_review", "issues": ["ambiguous"]}
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(_terminal_chunks(answer, final)),
    )

    with pytest.raises(RuntimeError, match="descriptive issues"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def test_stream_probe_rejects_stale_answer_validation_content(monkeypatch):
    answer, final = _answer_and_final()
    stale_phase = {**final, "answer": "Unsafe original Answer [1]."}
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            _terminal_chunks(answer, final, phase=stale_phase)
        ),
    )

    with pytest.raises(RuntimeError, match="final Answer-side envelope"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def test_stream_probe_rejects_unresolved_reference_still_checking(monkeypatch):
    answer, final = _answer_and_final()
    final["answerValidation"] = {
        "status": "needs_review",
        "issues": [{"reason": "The source could not be resolved."}],
    }
    final["references"] = [
        {"index": 1, "resolutionStatus": "unresolved", "groundingStatus": "checking"}
    ]
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(_terminal_chunks(answer, final)),
    )

    with pytest.raises(RuntimeError, match="terminal unchecked grounding"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def test_stream_probe_rejects_boolean_reference_index(monkeypatch):
    answer, final = _answer_and_final()
    final["references"] = [
        {"index": True, "resolutionStatus": "resolved", "groundingStatus": "verified"}
    ]
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(_terminal_chunks(answer, final)),
    )

    with pytest.raises(RuntimeError, match="positive integer index"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )


def _structured_answer_phases():
    answer, final = _answer_and_final()
    block_reference = {
        "index": 1,
        "resolutionStatus": "resolved",
        "groundingStatus": "verified",
        "usage": [{"location": "block", "path": "blocks[0].rows[0]"}],
    }
    indepth_reference = {
        "index": 2,
        "resolutionStatus": "resolved",
        "groundingStatus": "verified",
        "usage": [{"location": "indepth", "path": "claims[0]"}],
    }
    final["blocks"] = [
        {
            "kind": "table",
            "title": "Results",
            "rows": [{"cells": {"result": {"text": "Observed", "refs": [1]}}}],
        }
    ]
    final["references"] = [block_reference, indepth_reference]
    phase = {**final, "references": [block_reference]}
    return answer, final, phase


def test_stream_probe_accepts_block_reference_and_final_only_indepth_reference(monkeypatch):
    answer, final, phase = _structured_answer_phases()
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            _terminal_chunks(answer, final, phase=phase)
        ),
    )

    result = probe._stream_turn(
        "http://openmrs/chat/stream",
        patient="patient-1",
        profile="single-e4b-checked",
        question="Latest visit?",
        username="admin",
        password="secret",
        timeout=30,
    )

    assert result["final_reference_count"] == 2


def test_stream_probe_rejects_missing_block_reference_during_validation(monkeypatch):
    answer, final, phase = _structured_answer_phases()
    phase["references"] = []
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            _terminal_chunks(answer, final, phase=phase)
        ),
    )

    with pytest.raises(RuntimeError, match="final Answer references"):
        probe._stream_turn(
            "http://openmrs/chat/stream",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
        )
