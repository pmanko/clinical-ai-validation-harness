"""Tests for CatalystClient (feature 011): the harness adapter's `_Client`
Protocol implementation for driving Catalyst through validate-run.

Mirrors evals/validate/test_client.py's conventions (fake requests.Session
response objects, no real network) — see
specs/011-catalyst-fhir-sidecar-poc/contracts/catalyst_adapter_client.profile.md
for the contract this client implements.
"""

from __future__ import annotations

from harness.validate.catalyst_client import CatalystClient
from harness.validate.runner import _Client


class FakeResp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _client(**kwargs):
    return CatalystClient(
        endpoint_url="http://localhost:8000/v1/chat/completions",
        max_retries=2,
        retry_wait_s=0,
        **kwargs,
    )


def test_catalyst_client_satisfies_the_runner_client_protocol():
    """Structural check: CatalystClient must satisfy the same Protocol
    ChartSearchAiClient does — this is the actual reusable interface point
    (research.md item 1), not harness/adapters/*.py."""
    client: _Client = _client()  # type: ignore[assignment]
    assert hasattr(client, "new_session")
    assert hasattr(client, "chat")


def test_new_session_is_a_local_no_op_returning_an_id():
    """Catalyst's gateway is stateless per request — there is no server-side
    session to create."""
    client = _client()
    session_id = client.new_session("some-patient")
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    # Two calls never collide.
    assert client.new_session("some-patient") != session_id


def test_chat_posts_openai_shaped_body_to_the_configured_endpoint(monkeypatch):
    client = _client()
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp(
            200,
            payload={
                "answer": "Patient has one order [1].",
                "citations": [{"index": 1, "resourceType": "ServiceRequest", "id": "sr1", "url": "x", "display": "CBC"}],
                "provenance": {"fhir_surface": "embedded", "fhir_base_url": "x", "tools_called": [], "resource_ids": []},
                "id": "c1",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Patient has one order [1]."}, "finish_reason": "stop"}],
            },
        )

    monkeypatch.setattr(client._session, "post", fake_post)

    result = client.chat("E2E-PAT-001", None, "What tests were ordered?")

    assert captured["url"] == "http://localhost:8000/v1/chat/completions"
    assert captured["json"]["messages"] == [{"role": "user", "content": "What tests were ordered?"}]
    assert result.status == 200
    assert result.envelope["answer"] == "Patient has one order [1]."
    assert result.envelope["citations"][0]["resourceType"] == "ServiceRequest"


def test_chat_never_raises_on_non_200_records_status_instead():
    client = _client()

    def fake_post(url, json=None, timeout=None):
        return FakeResp(500, text="internal error")

    client._session.post = fake_post  # type: ignore[method-assign]

    result = client.chat("E2E-PAT-001", None, "What tests were ordered?")

    assert result.status == 500
    assert result.envelope is None
    assert "internal error" in result.raw_text


def test_chat_retries_a_retryable_status_before_succeeding():
    client = _client()
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResp(503, text="starting up")
        return FakeResp(
            200,
            payload={
                "answer": "ok",
                "citations": [],
                "provenance": {"fhir_surface": "embedded", "fhir_base_url": "x", "tools_called": [], "resource_ids": []},
            },
        )

    client._session.post = fake_post  # type: ignore[method-assign]

    result = client.chat("E2E-PAT-001", None, "q")

    assert calls["n"] == 2
    assert result.status == 200


def test_chat_profile_kwarg_is_accepted_and_ignored():
    """Protocol compatibility only — Catalyst has no product-profile concept."""
    client = _client()

    def fake_post(url, json=None, timeout=None):
        return FakeResp(
            200,
            payload={
                "answer": "ok",
                "citations": [],
                "provenance": {"fhir_surface": "embedded", "fhir_base_url": "x", "tools_called": [], "resource_ids": []},
            },
        )

    client._session.post = fake_post  # type: ignore[method-assign]

    result = client.chat("E2E-PAT-001", None, "q", profile="some-profile")
    assert result.status == 200
