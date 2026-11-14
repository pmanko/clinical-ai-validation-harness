import json
from pathlib import Path

import pytest

from harness.validate.execution import validate_execution_contract
from harness.validate.models import load_backends, load_comparison_set


def _write_inputs(
    tmp_path: Path, *, transport: str, kind: str | None, model: str, provider: str | None = None
):
    data = tmp_path / "validation"
    (data / "comparison_sets").mkdir(parents=True)
    comparison = {
        "id": "mini",
        "transport": transport,
        "scenario_ids": ["s1"],
        "backend_ids": ["arm"],
    }
    backend = {
        "label": "Test arm",
        "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
        "modelName": model,
    }
    if kind is not None:
        backend["kind"] = kind
    if provider is not None:
        backend["provider"] = provider
    (data / "comparison_sets" / "mini.json").write_text(
        json.dumps(comparison), encoding="utf-8"
    )
    (data / "backends.json").write_text(
        json.dumps({"arm": backend}), encoding="utf-8"
    )
    return data


def test_chartsearchai_transport_rejects_low_level_leg_before_run(tmp_path):
    data = _write_inputs(
        tmp_path,
        transport="chartsearchai",
        kind=None,
        model="answer:gemma-e4b@synthesis-answer~off~temp0",
    )
    comparison = load_comparison_set(data / "comparison_sets" / "mini.json")
    backends = load_backends(data / "backends.json")

    with pytest.raises(ValueError, match="product_profile"):
        validate_execution_contract(comparison, [backends["arm"]])


def test_chartsearchai_transport_accepts_product_profile(tmp_path):
    data = _write_inputs(
        tmp_path,
        transport="chartsearchai",
        kind="product_profile",
        model="single-e4b-checked",
    )
    comparison = load_comparison_set(data / "comparison_sets" / "mini.json")
    backends = load_backends(data / "backends.json")

    validate_execution_contract(comparison, [backends["arm"]])


def test_hub_transport_accepts_low_level_leg(tmp_path):
    data = _write_inputs(
        tmp_path,
        transport="med-agent-hub",
        kind=None,
        model="answer:gemma-e4b@synthesis-answer~off~temp0",
    )
    comparison = load_comparison_set(data / "comparison_sets" / "mini.json")
    backends = load_backends(data / "backends.json")

    validate_execution_contract(comparison, [backends["arm"]])


def test_hub_transport_rejects_a_provider_pinned_backend(tmp_path):
    """MedAgentHubClient.chat() has no `provider` kwarg — a provider_arm backend on
    med-agent-hub transport would only fail later, inside run_comparison, once the
    runner's own client-capability check trips. The upfront `validate check` gate
    exists specifically to catch exactly this kind of misconfiguration before that
    point, so it must reject here too, not just for chartsearchai transport."""
    data = _write_inputs(
        tmp_path,
        transport="med-agent-hub",
        kind="provider_arm",
        provider="hub",
        model="single-e4b-checked",
    )
    comparison = load_comparison_set(data / "comparison_sets" / "mini.json")
    backends = load_backends(data / "backends.json")

    with pytest.raises(ValueError, match="provider"):
        validate_execution_contract(comparison, [backends["arm"]])


def test_comparison_rejects_unknown_transport(tmp_path):
    data = _write_inputs(
        tmp_path,
        transport="magic",
        kind=None,
        model="single-e4b-checked",
    )

    with pytest.raises(ValueError, match="transport"):
        load_comparison_set(data / "comparison_sets" / "mini.json")


def test_openai_compatible_transport_accepts_arbitrary_model_arm(tmp_path):
    data = _write_inputs(
        tmp_path,
        transport="openai-compatible",
        kind=None,
        model="Qwen/Qwen2.5-14B-Instruct",
    )
    comparison = load_comparison_set(data / "comparison_sets" / "mini.json")
    backends = load_backends(data / "backends.json")

    validate_execution_contract(comparison, [backends["arm"]])


def test_openai_compatible_transport_rejects_provider_pinned_backend(tmp_path):
    data = _write_inputs(
        tmp_path,
        transport="openai-compatible",
        kind="provider_arm",
        provider="bundled",
        model="gemma-e4b",
    )
    comparison = load_comparison_set(data / "comparison_sets" / "mini.json")
    backends = load_backends(data / "backends.json")

    with pytest.raises(ValueError, match="provider"):
        validate_execution_contract(comparison, [backends["arm"]])


def test_execution_spec_contract_by_transport(tmp_path):
    data = tmp_path / "validation"
    (data / "comparison_sets").mkdir(parents=True)
    for transport, kind in (
        ("chartsearchai", "product_profile"),
        ("openai-compatible", None),
        ("med-agent-hub", None),
    ):
        backend = {
            "label": "Mode arm",
            "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
            "modelName": "gemma-4-12b",
            "execution": {"mode": "verified"},
        }
        if kind is not None:
            backend["kind"] = kind
        (data / "comparison_sets" / "mini.json").write_text(
            json.dumps(
                {
                    "id": "mini",
                    "transport": transport,
                    "scenario_ids": ["s1"],
                    "backend_ids": ["arm"],
                }
            ),
            encoding="utf-8",
        )
        (data / "backends.json").write_text(
            json.dumps({"arm": backend}), encoding="utf-8"
        )
        comparison = load_comparison_set(data / "comparison_sets" / "mini.json")
        backends = load_backends(data / "backends.json")
        if transport == "med-agent-hub":
            validate_execution_contract(comparison, [backends["arm"]])
        else:
            with pytest.raises(ValueError, match="execution"):
                validate_execution_contract(comparison, [backends["arm"]])


def test_runner_and_concurrency_forward_and_record_execution_spec(tmp_path):
    from harness.validate.bundle import review_results
    from harness.validate.client import ChatResult
    from harness.validate.concurrency import run_concurrency_benchmark
    from harness.validate.runner import run_comparison

    class _HubClient:
        def __init__(self):
            self.calls = []

        def new_session(self, patient):
            return f"sess-{patient}"

        def chat(self, patient, session, question, *, profile=None, execution=None, request_id=None, endpoint_url=None):
            self.calls.append(
                {
                    "profile": profile,
                    "execution": execution,
                    "endpoint_url": endpoint_url,
                }
            )
            return ChatResult(
                status=200,
                envelope={"answer": "Reviewed chart answer [1].", "citations": [1], "blocks": [], "session": session},
                latency_ms=12,
            )

    data = tmp_path / "validation"
    (data / "comparison_sets").mkdir(parents=True)
    (data / "scenarios").mkdir()
    (data / "comparison_sets" / "mini.json").write_text(
        json.dumps(
            {
                "id": "mini",
                "transport": "med-agent-hub",
                "scenario_ids": ["s1"],
                "backend_ids": ["arm"],
            }
        ),
        encoding="utf-8",
    )
    (data / "scenarios" / "s1.json").write_text(
        json.dumps(
            {
                "id": "s1",
                "patient_ref": "p1",
                "turns": [{"n": 1, "question": "Check labs"}],
            }
        ),
        encoding="utf-8",
    )
    (data / "backends.json").write_text(
        json.dumps(
            {
                "arm": {
                    "label": "Verified 12B",
                    "endpointUrl": "http://med-agent-hub:8080/v1/chat/completions",
                    "modelName": "gemma-4-12b",
                    "execution": {"mode": "verified", "indepth": False},
                }
            }
        ),
        encoding="utf-8",
    )

    seq_client = _HubClient()
    seq_res = run_comparison(
        comparison_set_id="mini",
        client=seq_client,
        data_root=data,
        output_dir=tmp_path / "runs-seq",
    )
    assert seq_client.calls[0]["profile"] == "gemma-4-12b"
    assert seq_client.calls[0]["execution"] == {"mode": "verified", "indepth": False}
    meta = json.loads((seq_res.run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["backends"]["arm"]["execution"] == {"mode": "verified", "indepth": False}
    reviewed = review_results(seq_res.run_dir)
    assert reviewed[0]["request"]["execution"] == {"mode": "verified", "indepth": False}
    events = [json.loads(line) for line in (seq_res.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    selected = next(e for e in events if e.get("event_type") == "backend_selected")
    assert selected["execution"] == {"mode": "verified", "indepth": False}

    conc_clients = []

    def _factory(_user, _password):
        c = _HubClient()
        conc_clients.append(c)
        return c

    conc_res = run_concurrency_benchmark(
        comparison_set_id="mini",
        backend_id="arm",
        client_factory=_factory,
        accounts=[("u1", "p1")],
        n_users=1,
        turns_per_user=1,
        data_root=data,
        output_dir=tmp_path / "runs-conc",
    )
    assert conc_clients[0].calls[0]["execution"] == {"mode": "verified", "indepth": False}
    conc_rows = [json.loads(line) for line in conc_res.results_path.read_text(encoding="utf-8").splitlines()]
    assert conc_rows[0]["request"]["execution"] == {"mode": "verified", "indepth": False}
