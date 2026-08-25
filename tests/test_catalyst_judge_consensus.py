"""Cross-actor agreement and human adjudication for the catalyst judge.

Both exist so a report can state what it does NOT have: three passes of one
model measure stability rather than validity, and an unadjudicated run has
no human anchor. Silence on either would read as consensus.
"""

from __future__ import annotations

import json

from harness.catalyst.judge_consensus import (
    ADJUDICATION_NAME,
    actor_id,
    agreement,
    cell_key,
    consensus,
    load_adjudication,
)


def row(
    *,
    scenario="A1",
    turn=0,
    version="v1",
    model="claude-fable-5",
    intent=3,
    craft=3,
    schema=3,
    composite=100,
):
    return {
        "scenario_id": scenario,
        "turn": turn,
        "version_id": version,
        "provider": "anthropic",
        "model": model,
        "model_version": model,
        "intent_fidelity": intent,
        "sql_quality": craft,
        "schema_discipline": schema,
        "composite": composite,
    }


def test_one_actor_is_reported_as_one_actor_not_as_consensus():
    view = consensus([row(), row(scenario="A2", version="v2")])

    assert view["single_actor"] is True
    assert view["actors"] == ["anthropic/claude-fable-5/claude-fable-5"]
    # Nothing to disagree about — and nothing invented.
    assert view["disagreements"] == []


def test_two_actors_surface_their_widest_disagreement():
    shared = {"scenario": "B3", "turn": 1, "version": "v9"}
    view = consensus(
        [
            row(**shared, intent=3, craft=3),
            row(**shared, model="other-model", intent=1, craft=2),
        ]
    )

    assert view["single_actor"] is False
    assert view["cells_scored_by_all"] == 1
    worst = view["disagreements"][0]
    # intent spread (2) beats sql_quality spread (1), so it leads.
    assert worst["axis"] == "intent_fidelity"
    assert worst["spread"] == 2
    assert set(worst["scores"].values()) == {1, 3}


def test_disagreements_are_ordered_widest_first():
    a = {"scenario": "X", "turn": 0, "version": "vx"}
    b = {"scenario": "Y", "turn": 0, "version": "vy"}
    view = consensus(
        [
            row(**a, intent=3),
            row(**a, model="m2", intent=2),
            row(**b, intent=3),
            row(**b, model="m2", intent=0),
        ]
    )

    spreads = [item["spread"] for item in view["disagreements"]]
    assert spreads == sorted(spreads, reverse=True)


def test_no_adjudication_file_means_no_anchor_not_a_perfect_score(tmp_path):
    rows = [row()]

    assert load_adjudication(tmp_path) == {}
    # None, never 1.0: an unreviewed run has no agreement rate at all.
    assert agreement(rows, load_adjudication(tmp_path)) is None


def test_adjudicated_cells_report_their_agreement_rate(tmp_path):
    rows = [row(), row(scenario="B3", turn=1, version="v9", intent=1, composite=55)]
    (tmp_path / ADJUDICATION_NAME).write_text(
        json.dumps(
            {
                "verdicts": {
                    cell_key(rows[0]): {"agree": True},
                    cell_key(rows[1]): {"agree": False, "note": "harsh; B3 is ambiguous"},
                    "Z9:0:missing": {"agree": True},
                }
            }
        ),
        encoding="utf-8",
    )

    result = agreement(rows, load_adjudication(tmp_path))

    assert result["reviewed"] == 2
    assert result["agreed"] == 1
    assert result["rate"] == 0.5
    # A verdict naming a cell this run never judged is surfaced, not counted.
    assert result["unknown_cells"] == ["Z9:0:missing"]
    assert "harsh" in result["notes"][cell_key(rows[1])]


def test_actor_identity_distinguishes_model_versions():
    assert actor_id(row(model="a")) != actor_id(row(model="b"))
    assert actor_id(row()) == "anthropic/claude-fable-5/claude-fable-5"


def test_a_corrupt_adjudication_file_is_ignored_rather_than_fatal(tmp_path):
    (tmp_path / ADJUDICATION_NAME).write_text("{not json", encoding="utf-8")

    assert load_adjudication(tmp_path) == {}
