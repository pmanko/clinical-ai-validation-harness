"""Comparative judging: build blinded comparisons, aggregate returned ranks.

Pointwise scores saturated on run 9ae123db (every axis median 3), so they
could not separate teams that all passed. A ranking cannot saturate; these
tests pin the deterministic halves of it.
"""

from __future__ import annotations

from harness.catalyst.judge_ranking import (
    aggregate_rankings,
    ranking_worklist,
)


def jrow(team, scenario="A1", turn=0, version=None, sql="SELECT 1"):
    return {
        "team": team,
        "scenario_id": scenario,
        "turn": turn,
        "version_id": version or f"{team}-{scenario}-{turn}",
        "sql": sql,
        "evidence_paths": [f"scenarios/{team}/{scenario}/x.json"],
    }


def test_a_comparison_carries_every_team_that_answered_the_same_question():
    work = ranking_worklist([jrow("t1"), jrow("t2"), jrow("t3")])

    assert len(work) == 1
    assert work[0]["scenario_id"] == "A1"
    assert {answer["team"] for answer in work[0]["answers"]} == {"t1", "t2", "t3"}
    # Each answer carries what the judge needs to rank it.
    first = work[0]["answers"][0]
    assert first["sql"] and first["evidence_paths"] and first["cell"]


def test_teams_are_blinded_and_the_labels_are_not_in_team_order():
    """A judge must not be able to learn that label A is one fixed team."""
    work = ranking_worklist(
        [jrow("aaa", scenario=s) for s in ("A1", "A2", "A3")]
        + [jrow("bbb", scenario=s) for s in ("A1", "A2", "A3")]
        + [jrow("ccc", scenario=s) for s in ("A1", "A2", "A3")]
    )

    label_of_aaa = {
        comparison["scenario_id"]: next(
            answer["label"]
            for answer in comparison["answers"]
            if answer["team"] == "aaa"
        )
        for comparison in work
    }
    # The same team does not sit under the same label in every comparison.
    assert len(set(label_of_aaa.values())) > 1


def test_the_blinded_order_is_stable_across_runs():
    """The worklist is replayable evidence, so the shuffle must be derived
    from content rather than randomness."""
    rows = [jrow("t1"), jrow("t2"), jrow("t3")]

    first = ranking_worklist(rows)
    second = ranking_worklist(list(reversed(rows)))

    assert [a["team"] for a in first[0]["answers"]] == [
        a["team"] for a in second[0]["answers"]
    ]


def test_a_cell_only_one_team_reached_is_not_a_comparison():
    work = ranking_worklist([jrow("t1", scenario="U9")])

    assert work == []


def test_mean_rank_leads_the_standing_and_wins_are_reported_alongside():
    result = aggregate_rankings(
        [
            {"scenario_id": "A1", "turn": 0, "ranks": {"a": 1, "b": 2, "c": 3}},
            {"scenario_id": "A2", "turn": 0, "ranks": {"a": 2, "b": 1, "c": 3}},
            {"scenario_id": "A3", "turn": 0, "ranks": {"a": 1, "b": 2, "c": 3}},
        ]
    )

    standing = result["standing"]
    assert [entry["team"] for entry in standing] == ["a", "b", "c"]
    assert standing[0]["mean_rank"] == round((1 + 2 + 1) / 3, 2)
    assert standing[0]["wins"] == 2
    assert standing[2]["wins"] == 0
    assert result["ranked_comparisons"] == 3
    assert result["separates_teams"] is True


def test_a_tie_for_first_gives_both_teams_the_win():
    result = aggregate_rankings(
        [{"scenario_id": "A1", "turn": 0, "ranks": {"a": 1, "b": 1, "c": 3}}]
    )

    wins = {entry["team"]: entry["wins"] for entry in result["standing"]}
    assert wins["a"] == 1 and wins["b"] == 1 and wins["c"] == 0


def test_a_standing_where_every_team_ties_says_it_does_not_separate_them():
    result = aggregate_rankings(
        [
            {"scenario_id": "A1", "turn": 0, "ranks": {"a": 1, "b": 1}},
            {"scenario_id": "A2", "turn": 0, "ranks": {"a": 1, "b": 1}},
        ]
    )

    assert result["separates_teams"] is False


def test_an_incomparable_comparison_is_recorded_with_its_reason_not_ranked():
    """M2 turn 1 on run 9ae123db: the suite checked an intermediate turn
    against the final reference, so no ordering would have meant anything."""
    result = aggregate_rankings(
        [
            {
                "scenario_id": "M2",
                "turn": 1,
                "comparable": False,
                "reason": "reference describes the final turn, not this one",
            },
            {"scenario_id": "A1", "turn": 0, "ranks": {"a": 1, "b": 2}},
        ]
    )

    assert result["ranked_comparisons"] == 1
    assert result["incomparable"][0]["scenario_id"] == "M2"
    assert "final turn" in result["incomparable"][0]["reason"]
