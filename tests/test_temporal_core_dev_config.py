import json
from pathlib import Path

from harness.validate.models import load_comparison_set, load_scenario
from harness.validate.model_registry import arm_card
from harness.validate.resolver import resolve_backends


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "validation"


def test_temporal_core_dev_comparison_set_loads_and_is_compact():
    cset = load_comparison_set(DATA / "comparison_sets" / "temporal-core-dev.json")
    assert cset.id == "temporal-core-dev"
    assert len(cset.scenario_ids) == 8
    assert len(cset.backend_ids) == 5
    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    assert {b.model_name for b in backends} == {
        "answer:gemma-4-12b@synthesis-chartsearchai~off",
        "answer:gemma-4-12b@synthesis-chartsearchai~warn",
        "answer:gemma-4-12b@synthesis-chartsearchai~enforce",
        "answer:gemma-26b@synthesis-chartsearchai~off",
        "answer:gemma-26b@synthesis-chartsearchai~enforce",
    }


def test_am_upcoming_expectation_matches_fixed_temporal_anchor():
    scen = load_scenario(DATA / "scenarios" / "am-upcoming-appointments.json")
    assert scen.expectations["should_abstain"] is True
    assert "2026-06-20" in scen.expectations["notes"]
    assert "2026-01-07" in scen.expectations["notes"]


def test_temporal_wide_31b_team_set_loads_and_covers_wider_surface():
    cset = load_comparison_set(DATA / "comparison_sets" / "temporal-wide-31b-team.json")
    assert cset.id == "temporal-wide-31b-team"
    assert len(cset.scenario_ids) == 12
    assert len(cset.backend_ids) == 7
    assert {
        "date-zabella-weight-table",
        "am-upcoming-appointments",
        "ek-growth",
        "abstain-out-of-chart",
    } <= set(cset.scenario_ids)

    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    assert {b.model_name for b in backends} == {
        "answer:gemma-4-12b@synthesis-chartsearchai~warn",
        "answer:gemma-4-12b@synthesis-date-output-contract~warn",
        "answer:gemma-26b@synthesis-date-output-contract~warn",
        "answer:gemma-31b@synthesis-chartsearchai~warn",
        "answer:gemma-31b@synthesis-date-output-contract~warn",
        "med-agent-team-12b-date-warn",
        "med-agent-team-high-date-warn",
    }
    high = next(b for b in backends if b.id == "wide-team-high-contract-warn")
    assert high.llama_router_models_max == 1


def test_temporal_wide_31b_team_2call_set_loads_with_high_router_cap():
    cset = load_comparison_set(DATA / "comparison_sets" / "temporal-wide-31b-team-2call.json")
    assert cset.id == "temporal-wide-31b-team-2call"
    assert len(cset.scenario_ids) == 12
    assert len(cset.backend_ids) == 7

    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    high = next(b for b in backends if b.id == "wide-team-high-contract-warn-2call")
    assert high.model_name == "med-agent-team-high-date-warn"
    assert high.indepth_model == "indepth-only:gemma-31b"
    assert high.llama_router_models_max == 1


def test_temporal_simple_candidate_2call_quarantines_high_team():
    cset = load_comparison_set(DATA / "comparison_sets" / "temporal-simple-candidate-2call.json")
    assert cset.id == "temporal-simple-candidate-2call"
    assert len(cset.scenario_ids) == 12
    assert len(cset.backend_ids) == 3
    assert not any("high" in bid for bid in cset.backend_ids)

    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    assert {b.model_name for b in backends} == {
        "answer:gemma-4-12b@synthesis-chartsearchai~enforce",
        "answer:gemma-4-12b@synthesis-date-output-contract~enforce~temp0.5",
        "answer:gemma-26b@synthesis-date-output-contract~enforce~temp0.5",
    }
    assert all(b.indepth_model for b in backends)


def test_hub_profile_candidate_uses_only_real_checked_product_profiles():
    cset = load_comparison_set(DATA / "comparison_sets" / "hub-profile-candidate.json")
    assert cset.id == "hub-profile-candidate"
    assert len(cset.scenario_ids) == 12
    assert cset.backend_ids == ["single-12b-checked"]

    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    assert [backend.model_name for backend in backends] == ["single-12b-checked"]
    assert all(backend.indepth_model is None for backend in backends)
    assert not any("team" in backend.id or "2call" in backend.id for backend in backends)
    raw = json.loads(
        (DATA / "comparison_sets" / "hub-profile-candidate.json").read_text()
    )
    assert len(raw["temporal_scenario_ids"]) == 11
    assert set(raw["temporal_scenario_ids"]) < set(cset.scenario_ids)


def test_hub_profile_appointment_smoke_targets_both_appointment_cases():
    cset = load_comparison_set(
        DATA / "comparison_sets" / "hub-profile-appointment-smoke.json"
    )
    assert cset.scenario_ids == [
        "single-upcoming-appointments",
        "am-upcoming-appointments",
    ]
    assert cset.backend_ids == ["single-12b-checked"]

    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    assert [backend.model_name for backend in backends] == ["single-12b-checked"]
    assert backends[0].indepth_model is None


def test_hub_profile_team_focus_has_one_team_and_two_single_profiles():
    cset = load_comparison_set(
        DATA / "comparison_sets" / "hub-profile-team-focus.json"
    )
    assert cset.scenario_ids == [
        "date-zabella-weight-table",
        "date-aloice-orders-table",
        "single-upcoming-appointments",
        "am-weight-trend",
        "am-orders-6mo",
        "abstain-out-of-chart",
    ]
    assert cset.backend_ids == [
        "single-e4b-checked",
        "single-12b-checked",
        "team-med-checked",
    ]

    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    assert [backend.model_name for backend in backends] == [
        "single-e4b-checked",
        "single-12b-checked",
        "team-med-checked",
    ]
    assert all(backend.indepth_model is None for backend in backends)
    cards = {backend.id: arm_card(backend.id) for backend in backends}
    assert cards["single-e4b-checked"]["kind"] == "single"
    assert cards["single-12b-checked"]["kind"] == "single"
    team = cards["team-med-checked"]
    assert team["kind"] == "team"
    assert team["title"] == (
        "Gemma 4B coord · MedGemma 4B expert · Qwen 14B writer · Gemma 12B val"
    )
    assert team["stages"] == [
        "context",
        "gather",
        "answer",
        "gate",
        "resolve_refs",
        "review",
        "gate",
        "final_resolve_refs",
        "ground_verdicts",
        "indepth",
        "indepth_gate",
    ]


def test_backend_registry_has_no_orphans_and_product_ids_are_hub_ids():
    registry = json.loads((DATA / "backends.json").read_text(encoding="utf-8"))
    used = set()
    for path in (DATA / "comparison_sets").glob("*.json"):
        used.update(json.loads(path.read_text(encoding="utf-8")).get("backend_ids", []))

    assert set(registry) == used
    products = {
        backend_id: config
        for backend_id, config in registry.items()
        if config.get("kind") == "product_profile"
    }
    assert set(products) == {
        "single-e4b-checked",
        "single-12b-checked",
        "team-med-checked",
    }
    for backend_id, config in products.items():
        assert config["modelName"] == backend_id
        assert config["endpointUrl"] == (
            "http://med-agent-hub:8080/v1/chat/completions"
        )
        assert "indepthEndpointUrl" not in config
        assert "indepthModelName" not in config


def test_product_comparison_sets_only_use_product_profiles():
    registry = json.loads((DATA / "backends.json").read_text(encoding="utf-8"))
    for path in (DATA / "comparison_sets").glob("hub-profile-*.json"):
        comparison = json.loads(path.read_text(encoding="utf-8"))
        assert comparison["backend_ids"]
        assert all(
            registry[backend_id].get("kind") == "product_profile"
            for backend_id in comparison["backend_ids"]
        ), path.name
