from pathlib import Path

import pytest

from harness.validate.models import (
    Backend,
    ComparisonSet,
    Scenario,
    load_comparison_set,
    load_scenario,
    load_backends,
)

DATA = Path("datasets/validation")


def test_scenario_from_dict_parses_turns():
    s = Scenario.from_dict(
        {
            "id": "x",
            "patient_ref": "p",
            "turns": [{"n": 1, "question": "q1"}, {"n": 2, "question": "q2"}],
            "tags": ["t"],
            "expectations": {"should_abstain": False},
        }
    )
    assert s.id == "x" and s.patient_ref == "p"
    assert [t.n for t in s.turns] == [1, 2]
    assert s.turns[1].question == "q2"


def test_scenario_requires_nonempty_turns():
    with pytest.raises(ValueError):
        Scenario.from_dict({"id": "x", "patient_ref": "p", "turns": []})


def test_scenario_missing_patient_ref_raises():
    with pytest.raises(ValueError):
        Scenario.from_dict({"id": "x", "turns": [{"n": 1, "question": "q"}]})


def test_comparison_set_from_dict():
    c = ComparisonSet.from_dict({"id": "demo", "scenario_ids": ["a"], "backend_ids": ["b1", "b2"]})
    assert c.scenario_ids == ["a"] and c.backend_ids == ["b1", "b2"]


def test_comparison_set_requires_nonempty_lists():
    with pytest.raises(ValueError):
        ComparisonSet.from_dict({"id": "demo", "scenario_ids": [], "backend_ids": ["b"]})


def test_backend_from_dict_requires_url_and_model():
    b = Backend.from_dict(
        "gemma-local",
        {"label": "G", "endpointUrl": "http://x/v1/chat/completions", "modelName": "m"},
    )
    assert b.id == "gemma-local" and b.model_name == "m"
    with pytest.raises(ValueError):
        Backend.from_dict("bad", {"endpointUrl": "http://x"})  # missing modelName


def test_shipped_demo_fixtures_are_valid_and_consistent():
    # The checked-in demo comparison set must reference scenarios + backends that
    # actually exist and validate — catches a malformed/dangling fixture.
    cset = load_comparison_set(DATA / "comparison_sets" / "demo.json")
    backends = load_backends(DATA / "backends.json")
    for bid in cset.backend_ids:
        assert bid in backends, f"demo references unknown backend {bid!r}"
    for sid in cset.scenario_ids:
        scenario = load_scenario(DATA / "scenarios" / f"{sid}.json")
        assert scenario.turns, f"scenario {sid!r} has no turns"
