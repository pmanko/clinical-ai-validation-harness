import json
from pathlib import Path


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
        "hub-e4b-verified",
        "speed-12b-answer-only",
        "speed-12b-deterministic-check",
        "hub-12b-verified",
    ]


def test_small_model_answer_paths_select_explicit_hub_modes():
    backends = resolve_backends(
        [
            "speed-e4b-answer-only",
            "speed-e4b-deterministic-check",
            "hub-e4b-verified",
            "speed-12b-answer-only",
            "speed-12b-deterministic-check",
            "hub-12b-verified",
        ],
        DATA / "backends.json",
    )

    assert [backend.model_name for backend in backends] == [
        "gemma-e4b",
        "gemma-e4b",
        "gemma-e4b",
        "gemma-4-12b",
        "gemma-4-12b",
        "gemma-4-12b",
    ]
    assert [backend.execution for backend in backends] == [
        {"mode": "bare_eval", "checks": {"temporal": "off"}},
        {"mode": "quick"},
        {"mode": "verified"},
        {"mode": "bare_eval", "checks": {"temporal": "off"}},
        {"mode": "quick"},
        {"mode": "verified"},
    ]
    assert all(
        backend.endpoint_url == "http://med-agent-hub:8080/v1/chat/completions"
        for backend in backends
    )
    assert all(backend.indepth_model is None for backend in backends)

    for backend in backends:
        card = arm_card(backend.id, backend=backend)
        assert card["title"] == backend.label
        assert card["models"] == [{"id": backend.model_name}]
        assert card["config"] == {}
        assert "stages" not in card
