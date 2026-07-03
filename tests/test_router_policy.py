from __future__ import annotations

import json
from pathlib import Path

from harness.validate.client import ChatResult
from harness.validate.models import Backend
from harness.validate.router_policy import effective_llama_router_models_max


def test_backend_parses_explicit_llama_router_models_max():
    backend = Backend.from_dict(
        "high",
        {
            "label": "High team",
            "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
            "modelName": "med-agent-team-high",
            "llamaRouterModelsMax": 1,
        },
    )

    assert backend.llama_router_models_max == 1
    assert effective_llama_router_models_max(backend) == 1


def test_llama_backed_backend_defaults_to_warm_cache_cap():
    backend = Backend.from_dict(
        "normal",
        {
            "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
            "modelName": "answer:gemma-4-12b",
        },
    )

    assert backend.llama_router_models_max is None
    assert effective_llama_router_models_max(backend) == 4


class _StubClient:
    def new_session(self, patient: str) -> str:
        return f"sess-{patient}"

    def chat(
        self,
        patient: str,
        session: str | None,
        question: str,
        *,
        endpoint_url: str | None = None,
        model_name: str | None = None,
    ) -> ChatResult:
        return ChatResult(
            status=200,
            envelope={"answer": f"answer from {model_name}", "session": session},
            latency_ms=1,
            raw_text="ok",
        )


def _write_mini_data(root: Path) -> None:
    (root / "comparison_sets").mkdir(parents=True)
    (root / "scenarios").mkdir()
    (root / "comparison_sets" / "mini.json").write_text(
        json.dumps({
            "id": "mini",
            "scenario_ids": ["s1"],
            "backend_ids": ["normal", "high"],
        }),
        encoding="utf-8",
    )
    (root / "scenarios" / "s1.json").write_text(
        json.dumps({
            "id": "s1",
            "patient_ref": "patient-1",
            "turns": [{"n": 1, "question": "What happened?"}],
        }),
        encoding="utf-8",
    )
    (root / "backends.json").write_text(
        json.dumps({
            "normal": {
                "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
                "modelName": "answer:gemma-4-12b",
            },
            "high": {
                "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
                "modelName": "med-agent-team-high",
                "llamaRouterModelsMax": 1,
            },
        }),
        encoding="utf-8",
    )


def test_runner_records_router_policy_event_per_backend(tmp_path):
    from harness.validate.runner import run_comparison

    data = tmp_path / "data"
    _write_mini_data(data)
    calls: list[tuple[str, int | None]] = []

    def policy(backend: Backend) -> dict:
        requested = effective_llama_router_models_max(backend)
        calls.append((backend.id, requested))
        return {
            "schema_version": "llama_router_policy.v1",
            "action": "noop",
            "status": "ready",
            "requested_models_max": requested,
        }

    res = run_comparison(
        comparison_set_id="mini",
        client=_StubClient(),
        data_root=data,
        output_dir=tmp_path / "runs",
        router_policy=policy,
    )

    assert calls == [("normal", 4), ("high", 1)]
    events = [
        json.loads(line)
        for line in (res.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    policy_events = [e for e in events if e["event_type"] == "llama_router_policy"]
    assert [(e["backend_id"], e["requested_models_max"]) for e in policy_events] == [
        ("normal", 4),
        ("high", 1),
    ]
