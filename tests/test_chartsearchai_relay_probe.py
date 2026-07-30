from __future__ import annotations

import importlib.util
import json
import sys
import urllib.parse
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


def test_probe_correlates_fast_stream_by_message_and_persistence_by_audit_row(monkeypatch):
    answer = {
        "session": "session-1",
        "messageId": "message-1",
        "provider": "hub",
        "answer": "The latest visit was 2026-07-10 [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "checking"},
        "references": [{"index": 1}],
    }
    final = {
        **answer,
        "answer": "The checked latest visit was 2026-07-10 [1].",
        "answerValidation": {"status": "checked", "label": "Checked"},
        "references": [
            {
                "index": 1,
                "source": "querystore",
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
                    b"event: turn_started\n",
                    b"data: {}\n",
                    b"\n",
                    b"event: answer_done\n",
                    f"data: {json.dumps(answer)}\n".encode(),
                    b"\n",
                    b"event: ping\n",
                    b"data:\n",
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
                    b"event: turn_done\n",
                    b'data: {"session":"session-1","messageId":"message-1","provider":"hub"}\n',
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
    assert result["provider"] == "hub"
    assert result["profile"] == "single-e4b-checked"
    assert result["audit_log_id"] == 42
    assert result["answer_validation"] == {"status": "checked", "label": "Checked"}
    assert result["reference_count"] == 1
    assert result["reference_sources"] == ["querystore"]
    assert result["querystore_reference_count"] == 1
    assert result["in_depth_status"] == "complete"
    assert result["in_depth_terminal_event"] == "indepth_done"
    assert result["final_envelope_sha256"] == result["hydrated_envelope_sha256"]
    assert result["events"] == [
        "turn_started",
        "answer_done",
        "answer_validation",
        "indepth_pending",
        "indepth_done",
        "turn_done",
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
    assert json.loads(requests[0][0].data) == {
        "patient": "patient-1",
        "provider": "hub",
        "profile": "single-e4b-checked",
        "question": "Latest visit?",
    }


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


def test_probe_rejects_turn_without_live_querystore_evidence(monkeypatch):
    monkeypatch.setattr(
        probe,
        "_stream_turn",
        lambda *_args, **_kwargs: {"querystore_reference_count": 0},
    )

    with pytest.raises(RuntimeError, match="live Querystore patient source"):
        probe.probe_relay(
            "http://openmrs/openmrs",
            patient="patient-1",
            profile="single-e4b-checked",
            question="Latest visit?",
            username="admin",
            password="secret",
            timeout=30,
            clear_after=False,
        )


def test_stream_probe_rejects_incomplete_review_sequence(monkeypatch):
    answer = {
        "session": "session-1",
        "messageId": "message-1",
        "provider": "hub",
        "auditLogId": 42,
        "answer": "Answer [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "checking"},
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
            b"event: turn_started\n",
            b"data: {}\n",
            b"\n",
            b"event: answer_done\n",
            f"data: {json.dumps(answer)}\n".encode(),
            b"\n",
            b"event: indepth_pending\n",
            f"data: {json.dumps(pending)}\n".encode(),
            b"\n",
            b"event: indepth_done\n",
            f"data: {json.dumps(final)}\n".encode(),
            b"\n",
                b"event: turn_done\n",
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
        "provider": "hub",
        "auditLogId": 42,
        "answer": "Answer [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "checking"},
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
        ("turn_started", {}),
        ("answer_done", answer),
        ("answer_validation", final),
        ("indepth_pending", pending),
        ("indepth_done", final),
        ("turn_done", final),
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
        "provider": "hub",
        "auditLogId": 42,
        "answer": "The model answer needs review.",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "checking"},
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
        ("turn_started", {}),
        ("answer_done", answer),
        ("answer_validation", final),
        ("indepth_pending", pending),
        ("indepth_error", final),
            ("turn_done", final),
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
        "provider": "hub",
        "auditLogId": 42,
        "answer": "Answer [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "checking"},
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
        ("turn_started", {}),
        ("answer_done", answer),
        ("answer_validation", final),
        ("indepth_pending", pending),
        ("indepth_error", final),
            ("turn_done", final),
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
        ("turn_started", {}),
        ("answer_done", answer),
        ("answer_validation", phase or final),
        ("indepth_pending", pending),
        (terminal_event, final),
        (
            "turn_done",
            {
                "session": answer["session"],
                "messageId": answer["messageId"],
                "provider": "hub",
            },
        ),
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
        "provider": "hub",
        "auditLogId": 42,
        "answer": "Answer [1].",
        "model": "single-e4b-checked",
        "answerValidation": {"status": "checking"},
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


def test_stream_probe_rejects_inconsistent_optional_stream_audit_ids(monkeypatch):
    answer, final = _answer_and_final()
    final["auditLogId"] = 43
    monkeypatch.setattr(
        probe.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(_terminal_chunks(answer, final)),
    )

    with pytest.raises(RuntimeError, match="different audit row"):
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


def test_artifact_content_rejects_missing_path(tmp_path):
    with pytest.raises(RuntimeError, match="artifact does not exist"):
        probe._artifact_content(tmp_path / "missing")


def test_runtime_identity_binds_built_and_deployed_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    chartsearchai = tmp_path / "targets" / "chartsearchai"
    querystore = tmp_path / "targets" / "querystore"
    esm_repo = tmp_path / "targets" / "chartsearchai-esm"
    hub_repo = tmp_path / "targets" / "med-agent-hub"
    for repo in (chartsearchai, querystore, esm_repo, hub_repo):
        repo.mkdir(parents=True)

    omod = tmp_path / "artifacts/openmrs/modules/chartsearchai-1.0.0-SNAPSHOT.omod"
    omod.parent.mkdir(parents=True)
    omod.write_bytes(b"omod")
    querystore_omod = (
        tmp_path / "artifacts/openmrs/modules/querystore-1.0.0-SNAPSHOT.omod"
    )
    querystore_omod.write_bytes(b"querystore-omod")
    esm = tmp_path / "artifacts/openmrs/spa-custom"
    esm.mkdir(parents=True)
    (esm / "app.js").write_bytes(b"esm")

    def write_provenance(repo, artifact, path):
        content = probe._artifact_content(artifact)
        payload = {
            "source_commit": f"{repo.name}-commit",
            "source_tree": "tree-sha",
            "source_tree_clean": True,
            "artifact_kind": content["kind"],
            "artifact_sha256": content["sha256"],
            "artifact_size_bytes": content["size_bytes"],
            "artifact_files": content.get("files"),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    omod_manifest = Path(f"{omod}.provenance.json")
    omod_provenance = write_provenance(chartsearchai, omod, omod_manifest)
    deployed_manifest = (
        tmp_path / "artifacts/chartsearchai-local/deployed-chartsearchai-omod.json"
    )
    deployed_manifest.parent.mkdir(parents=True)
    deployed_manifest.write_text(json.dumps(omod_provenance), encoding="utf-8")
    querystore_manifest = Path(f"{querystore_omod}.provenance.json")
    querystore_provenance = write_provenance(
        querystore, querystore_omod, querystore_manifest
    )
    deployed_querystore_manifest = (
        tmp_path / "artifacts/chartsearchai-local/deployed-querystore-omod.json"
    )
    deployed_querystore_manifest.write_text(
        json.dumps(querystore_provenance), encoding="utf-8"
    )
    (esm / "importmap.json").write_text(
        json.dumps(
            {
                "imports": {
                    "@openmrs/esm-chartsearchai-app": (
                        "./openmrs-esm-chartsearchai-app-multiturn/"
                        "openmrs-esm-chartsearchai-app.js"
                    )
                }
            }
        ),
        encoding="utf-8",
    )
    esm_manifest = tmp_path / "artifacts/openmrs/chartsearchai-esm.provenance.json"
    write_provenance(esm_repo, esm, esm_manifest)
    (hub_repo / "server").mkdir()
    (hub_repo / "server/levels.yaml").write_text("profiles: {}\n", encoding="utf-8")
    (tmp_path / "compose").mkdir()
    (tmp_path / "compose/openmrs-2.8-refapp.yml").write_text("services: {}\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/chartsearch-configure.sh").write_text("#!/bin/sh\n")

    monkeypatch.setattr(
        probe,
        "_git_identity",
        lambda repo: {"commit": f"{repo.name}-commit", "tree_clean": True},
    )

    def check_output(args, **_kwargs):
        if args[:3] == ["git", "rev-parse", "HEAD^{tree}"]:
            return "tree-sha\n"
        if args[:2] == ["docker", "inspect"]:
            return json.dumps([{"Id": "container-id", "Image": "sha256:image"}])
        if args[:3] == ["docker", "image", "inspect"]:
            return json.dumps(
                [
                    {
                        "Config": {
                            "Labels": {
                                "org.opencontainers.image.revision": (
                                    "med-agent-hub-commit"
                                )
                            }
                        }
                    }
                ]
            )
        if args[:2] == ["docker", "exec"]:
            mounted = querystore_omod if "querystore" in args[-1] else omod
            return f"{probe._sha256(mounted)}  {mounted.name}\n"
        raise AssertionError(args)

    monkeypatch.setattr(probe.subprocess, "check_output", check_output)
    def urlopen(url, **_kwargs):
        relative = urllib.parse.unquote(url.rsplit("/spa/", 1)[1])
        return FakeResponse((esm / relative).read_bytes())

    monkeypatch.setattr(probe.urllib.request, "urlopen", urlopen)

    identity = probe._runtime_identity("http://openmrs/openmrs")

    assert identity["deployment"] == {
        "container_id": "container-id",
        "image_id": "sha256:image",
        "revision": "med-agent-hub-commit",
    }
    assert identity["artifacts"]["chartsearchai_omod"]["mounted_sha256"] == probe._sha256(omod)
    assert identity["querystore"] == {
        "commit": "querystore-commit",
        "tree_clean": True,
    }
    assert identity["artifacts"]["querystore_omod"]["mounted_sha256"] == probe._sha256(
        querystore_omod
    )
    assert identity["artifacts"]["querystore_omod"]["deployed_provenance_path"] == (
        "artifacts/chartsearchai-local/deployed-querystore-omod.json"
    )
    assert identity["artifacts"]["chartsearchai_esm"]["served_files"] == {
        "app.js": probe._sha256(esm / "app.js"),
        "importmap.json": probe._sha256(esm / "importmap.json"),
    }


def test_probe_cli_writes_requested_output(tmp_path, monkeypatch, capsys):
    result = {"schema_version": "chartsearchai_relay_probe.v2", "hydrated": True}
    calls = []
    monkeypatch.setattr(
        probe,
        "discover_default_profile",
        lambda openmrs_url, **kwargs: calls.append(("discover", openmrs_url, kwargs))
        or "single-e4b-checked",
    )
    monkeypatch.setattr(
        probe,
        "probe_relay",
        lambda openmrs_url, **kwargs: calls.append(("probe", openmrs_url, kwargs))
        or result,
    )
    output = tmp_path / "probe.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe-chartsearchai-relay.py",
            "--patient",
            "patient-1",
            "--output",
            str(output),
        ],
    )

    assert probe.main() == 0
    assert calls[0] == (
        "discover",
        "http://127.0.0.1:8088/openmrs",
        {"username": "admin", "password": "Admin123", "timeout": 300},
    )
    assert calls[1][0:2] == ("probe", "http://127.0.0.1:8088/openmrs")
    assert calls[1][2]["provider"] == "hub"
    assert calls[1][2]["profile"] == "single-e4b-checked"
    assert json.loads(output.read_text(encoding="utf-8")) == result
    assert json.loads(capsys.readouterr().out) == result


def test_probe_discovers_the_openmrs_relayed_product_default(monkeypatch):
    calls = []

    def get_json(url, **kwargs):
        calls.append((url, kwargs))
        return {
            "data": [
                {
                    "id": "hub-default",
                    "visibility": "product",
                    "available": True,
                    "default": True,
                }
            ]
        }

    monkeypatch.setattr(probe, "_get_json", get_json)

    assert (
        probe.discover_default_profile(
            "http://openmrs/openmrs",
            username="admin",
            password="secret",
            timeout=9,
        )
        == "hub-default"
    )
    assert calls == [
        (
            "http://openmrs/openmrs/ws/rest/v1/chartsearchai/models",
            {"username": "admin", "password": "secret", "timeout": 9},
        )
    ]


def test_probe_rejects_ambiguous_openmrs_product_defaults(monkeypatch):
    monkeypatch.setattr(
        probe,
        "_get_json",
        lambda *_args, **_kwargs: {
            "data": [
                {
                    "id": profile,
                    "visibility": "product",
                    "available": True,
                    "default": True,
                }
                for profile in ("one", "two")
            ]
        },
    )

    with pytest.raises(RuntimeError, match="exactly one available default product profile"):
        probe.discover_default_profile(
            "http://openmrs/openmrs",
            username="admin",
            password="secret",
            timeout=9,
        )
