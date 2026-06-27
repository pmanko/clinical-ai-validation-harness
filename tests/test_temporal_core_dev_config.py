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
