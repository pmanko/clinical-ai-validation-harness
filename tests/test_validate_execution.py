import json
from pathlib import Path

import pytest

from harness.validate.execution import validate_execution_contract
from harness.validate.models import load_backends, load_comparison_set


def _write_inputs(tmp_path: Path, *, transport: str, kind: str | None, model: str):
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


def test_comparison_rejects_unknown_transport(tmp_path):
    data = _write_inputs(
        tmp_path,
        transport="magic",
        kind=None,
        model="single-e4b-checked",
    )

    with pytest.raises(ValueError, match="transport"):
        load_comparison_set(data / "comparison_sets" / "mini.json")
