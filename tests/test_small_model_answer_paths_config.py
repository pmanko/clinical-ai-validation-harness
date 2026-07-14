import json
from pathlib import Path

import yaml

from harness.validate.models import load_comparison_set
from harness.validate.model_registry import arm_card
from harness.validate.resolver import resolve_backends


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "validation"


def test_small_model_answer_paths_is_a_matched_e4b_12b_matrix():
    candidate = json.loads(
        (DATA / "comparison_sets" / "hub-profile-candidate.json").read_text(
            encoding="utf-8"
        )
    )
    comparison = json.loads(
        (DATA / "comparison_sets" / "small-model-answer-paths.json").read_text(
            encoding="utf-8"
        )
    )
    loaded = load_comparison_set(
        DATA / "comparison_sets" / "small-model-answer-paths.json"
    )

    assert loaded.id == "small-model-answer-paths"
    assert loaded.transport == "med-agent-hub"
    assert loaded.scenario_ids == candidate["scenario_ids"]
    assert comparison["temporal_scenario_ids"] == candidate["temporal_scenario_ids"]
    assert loaded.backend_ids == [
        "speed-e4b-answer-only",
        "speed-e4b-deterministic-check",
        "single-e4b-checked",
        "speed-12b-answer-only",
        "speed-12b-deterministic-check",
        "single-12b-checked",
    ]


def test_small_model_answer_paths_use_the_same_hub_prompt_and_three_depths():
    backends = resolve_backends(
        [
            "speed-e4b-answer-only",
            "speed-e4b-deterministic-check",
            "single-e4b-checked",
            "speed-12b-answer-only",
            "speed-12b-deterministic-check",
            "single-12b-checked",
        ],
        DATA / "backends.json",
    )

    assert [backend.model_name for backend in backends] == [
        "eval-e4b-answer-only",
        "eval-e4b-temporal-enforce",
        "single-e4b-checked",
        "eval-12b-answer-only",
        "eval-12b-temporal-enforce",
        "single-12b-checked",
    ]
    assert all(
        backend.endpoint_url == "http://med-agent-hub:8080/v1/chat/completions"
        for backend in backends
    )
    assert all(backend.indepth_model is None for backend in backends)

    cards = {backend.id: arm_card(backend.id) for backend in backends}
    assert cards["speed-e4b-answer-only"]["title"].endswith("single · answer only")
    assert cards["speed-e4b-deterministic-check"]["title"].endswith(
        "single · deterministic check"
    )
    assert cards["single-e4b-checked"]["title"].endswith(
        "single · fully checked"
    )
    assert cards["speed-12b-answer-only"]["title"].endswith("single · answer only")
    assert cards["speed-12b-deterministic-check"]["title"].endswith(
        "single · deterministic check"
    )
    assert cards["single-12b-checked"]["title"].endswith(
        "single · fully checked"
    )


def test_small_model_evaluation_profiles_share_the_product_context_budget():
    levels = yaml.safe_load(
        (ROOT / "targets" / "med-agent-hub" / "server" / "levels.yaml").read_text(
            encoding="utf-8"
        )
    )["profiles"]

    expected = {
        "eval-e4b-answer-only": ("gemma-e4b", "off"),
        "eval-e4b-temporal-enforce": ("gemma-e4b", "enforce"),
        "eval-12b-answer-only": ("gemma-4-12b", "off"),
        "eval-12b-temporal-enforce": ("gemma-4-12b", "enforce"),
    }
    product_context = levels["single-e4b-checked"]["context"]
    for profile_id, (model, gate) in expected.items():
        profile = levels[profile_id]
        assert profile["visibility"] == "evaluation"
        assert profile["stages"] == ["context", "answer", "gate"]
        assert profile["models"] == {"answer": model}
        assert profile["prompts"] == {"answer": "synthesis-answer"}
        assert profile["policies"]["temporal_gate"] == gate
        assert profile["context"] == product_context
        assert profile["knobs"]["answer"]["temperature"] == 0
