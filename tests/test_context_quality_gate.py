from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-context-quality.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_context_quality", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_source_indices_walks_nested_temporal_fact_shapes():
    module = _load_module()

    assert module._source_indices(
        {
            "index": 3,
            "nested": [{"indices": [4, "bad", 5]}, {"index": 6}],
        }
    ) == {3, 4, 5, 6}


def test_bootstrap_prefers_the_parent_gate_environment():
    module = _load_module()

    assert module._bootstrap_pythons()[0] == ROOT / ".gates-hub-venv/bin/python"


def test_context_cases_require_explicit_nonempty_labels():
    module = _load_module()
    comparison = {
        "scenario_ids": ["missing"],
        "context_quality": {"required_source_indices": {}},
    }

    with pytest.raises(ValueError, match="Missing required-source labels"):
        list(module._iter_cases(comparison))


def test_evaluate_binds_current_inputs_and_measures_all_cells(monkeypatch):
    module = _load_module()

    class FakeCounter:
        def __init__(self, *_args, **_kwargs):
            pass

    class FakeState:
        def __init__(self, messages):
            self.messages = messages
            self.view = None
            self.temporal_facts = None
            self.ledger = SimpleNamespace(records=())

    def fake_request(**kwargs):
        return SimpleNamespace(**kwargs)

    async def fake_prepare(_request, state):
        state.view = SimpleNamespace(
            record_indices=tuple(range(1, 1000)),
            mode="full",
            input_tokens=100,
            input_limit=200,
            included=(SimpleNamespace(stable_id="record-1", reason="full_context"),),
            excluded=(),
        )
        state.temporal_facts = {}

    monkeypatch.setattr(module, "RouterTokenCounter", FakeCounter)
    monkeypatch.setattr(module, "ExecutionRequest", fake_request)
    monkeypatch.setattr(module, "_State", FakeState)
    monkeypatch.setattr(module, "_prepare_context", fake_prepare)
    monkeypatch.setattr(
        module,
        "get_profile",
        lambda profile_id: SimpleNamespace(
            id=profile_id,
            exact_tokenizer=True,
            models={"answer": "fixture-model"},
        ),
    )

    result = asyncio.run(
        module._evaluate(
            argparse.Namespace(
                comparison_set="datasets/validation/comparison_sets/context-supply-dev.json",
                router_url="http://router.test",
                timeout=1.0,
            )
        )
    )

    assert result["status"] == "pass"
    assert result["cases"] == 12
    assert result["required_sources"] == 48
    assert result["missing_sources"] == 0
    assert result["required_source_recall"] == 1.0
    assert len(result["hub_code_sha256"]) == 64
    assert len(result["router_config_sha256"]) == 64
    assert all(row["input_tokens"] <= row["input_limit"] for row in result["results"])
    assert all(row["included"] == [{"source_id": "record-1", "reason": "full_context"}] for row in result["results"])


def test_main_writes_requested_artifact_and_returns_gate_status(tmp_path, monkeypatch):
    module = _load_module()
    module.ROOT = tmp_path

    async def fake_evaluate(_args):
        return {
            "status": "pass",
            "required_source_recall": 1.0,
            "cases": 2,
        }

    monkeypatch.setattr(module, "_evaluate", fake_evaluate)
    monkeypatch.setattr(
        sys,
        "argv",
        ["verify-context-quality.py", "--output", "proof/context.json"],
    )

    assert module.main() == 0
    assert json.loads((tmp_path / "proof/context.json").read_text()) == {
        "status": "pass",
        "required_source_recall": 1.0,
        "cases": 2,
    }
