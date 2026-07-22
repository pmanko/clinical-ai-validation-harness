"""Red-first tests for provider arms (engine-parity AC-5): a Backend may pin the
ChartSearchAI provider (bundled|hub); the runner routes it per request and omits
the hub product profile for the bundled provider (which takes none)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.validate.client import ChatResult
from harness.validate.execution import validate_execution_contract
from harness.validate.models import Backend, ComparisonSet
from harness.validate.runner import run_comparison


def test_backend_parses_optional_provider():
    b = Backend.from_dict("x", {
        "endpointUrl": "http://e", "modelName": "m", "provider": "bundled",
        "kind": "provider_arm",
    })
    assert b.provider == "bundled"
    assert Backend.from_dict("y", {"endpointUrl": "http://e", "modelName": "m"}).provider == ""


def test_execution_contract_accepts_provider_arms_on_chartsearchai_transport():
    comparison = ComparisonSet(id="c", scenario_ids=["s"], backend_ids=["a", "b"])
    arms = [
        Backend(id="a", label="a", endpoint_url="http://e", model_name="gemma-e4b",
                kind="provider_arm", provider="bundled"),
        Backend(id="b", label="b", endpoint_url="http://e", model_name="single-e4b-checked",
                kind="provider_arm", provider="hub"),
    ]
    validate_execution_contract(comparison, arms)  # must not raise


def test_execution_contract_rejects_provider_arm_without_provider():
    comparison = ComparisonSet(id="c", scenario_ids=["s"], backend_ids=["a"])
    arms = [Backend(id="a", label="a", endpoint_url="http://e", model_name="m",
                    kind="provider_arm", provider="")]
    with pytest.raises(ValueError, match="provider"):
        validate_execution_contract(comparison, arms)


class ProviderAwareClient:
    """Fake client that accepts provider routing on both entry points."""

    def __init__(self):
        self.new_session_calls = []
        self.chat_calls = []

    def new_session(self, patient, provider=None):
        self.new_session_calls.append({"patient": patient, "provider": provider})
        return "sess-1"

    def chat(self, patient, session, question, *, profile=None, provider=None):
        self.chat_calls.append({
            "patient": patient, "session": session, "question": question,
            "profile": profile, "provider": provider,
        })
        return ChatResult(
            status=200,
            envelope={"answer": "a [1]", "references": [{"index": 1}], "session": "sess-1"},
            latency_ms=5,
        )


class ProfileOnlyClient(ProviderAwareClient):
    """Fake client that CANNOT route providers (no provider kwarg)."""

    def new_session(self, patient):
        self.new_session_calls.append({"patient": patient})
        return "sess-1"

    def chat(self, patient, session, question, *, profile=None):
        self.chat_calls.append({
            "patient": patient, "session": session, "question": question, "profile": profile,
        })
        return ChatResult(
            status=200,
            envelope={"answer": "a [1]", "references": [{"index": 1}], "session": "sess-1"},
            latency_ms=5,
        )


def _write_provider_fixtures(root: Path):
    (root / "scenarios").mkdir(parents=True)
    (root / "comparison_sets").mkdir(parents=True)
    (root / "scenarios" / "sc.json").write_text(
        json.dumps({"id": "sc", "patient_ref": "pat", "turns": [{"n": 1, "question": "q1"}]}),
        encoding="utf-8",
    )
    (root / "comparison_sets" / "cs.json").write_text(
        json.dumps({"id": "cs", "scenario_ids": ["sc"], "backend_ids": ["arm-bundled", "arm-hub"]}),
        encoding="utf-8",
    )
    (root / "backends.json").write_text(json.dumps({
        "arm-bundled": {"label": "Bundled", "kind": "provider_arm", "provider": "bundled",
                        "endpointUrl": "http://tap:8078/v1/chat/completions", "modelName": "gemma-e4b"},
        "arm-hub": {"label": "Hub", "kind": "provider_arm", "provider": "hub",
                    "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
                    "modelName": "single-e4b-checked"},
    }), encoding="utf-8")


def test_runner_routes_provider_and_omits_profile_for_bundled(tmp_path):
    data = tmp_path / "data"
    _write_provider_fixtures(data)
    client = ProviderAwareClient()

    run_comparison(
        comparison_set_id="cs", client=client, data_root=data,
        output_dir=tmp_path / "art", git_sha="t", router_policy=lambda backend: None,
    )

    by_provider = {c["provider"]: c for c in client.chat_calls}
    assert set(by_provider) == {"bundled", "hub"}
    # bundled: provider routed, NO hub product profile
    assert by_provider["bundled"]["profile"] is None
    # hub: provider routed AND the profile is the arm's modelName
    assert by_provider["hub"]["profile"] == "single-e4b-checked"
    # the conversation itself is provider-bound at open
    session_providers = {c.get("provider") for c in client.new_session_calls}
    assert session_providers == {"bundled", "hub"}


def test_runner_rejects_provider_arm_when_client_cannot_route(tmp_path):
    data = tmp_path / "data"
    _write_provider_fixtures(data)
    client = ProfileOnlyClient()

    with pytest.raises(ValueError, match="provider"):
        run_comparison(
            comparison_set_id="cs", client=client, data_root=data,
            output_dir=tmp_path / "art", git_sha="t", router_policy=lambda backend: None,
        )
    # No silent fallback: the failure happened before any turn ran.
    assert client.chat_calls == []
