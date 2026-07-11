from pathlib import Path

from harness.validate.models import load_comparison_set, load_scenario
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
    assert cset.backend_ids == ["product-e4b-checked", "product-12b-checked"]

    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    assert {backend.model_name for backend in backends} == {
        "single-e4b-checked",
        "single-12b-checked",
    }
    assert all(backend.indepth_model is None for backend in backends)
    assert not any("team" in backend.id or "2call" in backend.id for backend in backends)
