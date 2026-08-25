"""Comparative judging: rank the teams' answers to the same question.

Pointwise scores saturate. On run 9ae123db every axis median was 3 and 40
of 44 composites landed at or above 84, so the scale could describe
failures but could not separate teams that all passed — the comparison the
programme exists to make. A ranking cannot saturate: asked which of three
answers to one question is best, a judge has to choose.

This module owns the deterministic halves of that: building the comparisons
a judge is asked to rank (blinded, so a ranking cannot be anchored to a
model name), and aggregating returned rankings into a per-team standing.
The judging itself is the `catalyst-judge-rank-v1` rubric.
"""

from __future__ import annotations

import hashlib
from statistics import mean
from typing import Any

# Opaque labels shown to the judge, in place of team names.
_LABELS = "ABCDEFGH"


def _blind_order(scenario_id: str, turn: int, teams: list[str]) -> list[str]:
    """A stable, content-derived shuffle of the teams for one comparison.

    Deterministic so a re-run produces the identical worklist (the run is
    replayable evidence), but varying per comparison so a judge cannot
    learn that label A is always the same team.
    """
    digest = hashlib.sha256(f"{scenario_id}:{turn}".encode()).hexdigest()
    return sorted(teams, key=lambda team: hashlib.sha256(
        f"{digest}:{team}".encode()
    ).hexdigest())


def ranking_worklist(judge_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One comparison per (scenario, turn) that more than one team answered.

    A cell only one team reached is not a comparison and is skipped rather
    than ranked against nothing.
    """
    from harness.catalyst.judge_consensus import cell_key  # local: avoid cycle

    grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for row in judge_rows:
        team = row.get("team")
        if not isinstance(team, str) or not team:
            continue
        key = (str(row.get("scenario_id")), int(row.get("turn") or 0))
        grouped.setdefault(key, {})[team] = row

    comparisons: list[dict[str, Any]] = []
    for (scenario_id, turn), by_team in sorted(grouped.items()):
        if len(by_team) < 2:
            continue
        order = _blind_order(scenario_id, turn, sorted(by_team))
        comparisons.append(
            {
                "schema": "catalyst-judge-rank-v1",
                "scenario_id": scenario_id,
                "turn": turn,
                "answers": [
                    {
                        "label": _LABELS[index],
                        "team": team,
                        "cell": cell_key(by_team[team]),
                        "version_id": by_team[team].get("version_id"),
                        "sql": by_team[team].get("sql"),
                        "evidence_paths": by_team[team].get("evidence_paths") or [],
                    }
                    for index, team in enumerate(order)
                ],
            }
        )
    return comparisons


def aggregate_rankings(rank_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn returned rankings into a standing.

    `rank_rows` are the judge's answers: one per comparison, carrying
    `ranks` as {team: rank} with competition-style ties, or
    `comparable: false` with a reason. Mean rank is the headline because it
    survives ties and cannot saturate; wins are reported alongside because
    a reader thinks in wins.
    """
    per_team_ranks: dict[str, list[int]] = {}
    wins: dict[str, int] = {}
    incomparable: list[dict[str, Any]] = []
    ranked = 0

    for row in rank_rows:
        if row.get("comparable") is False:
            incomparable.append(
                {
                    "scenario_id": row.get("scenario_id"),
                    "turn": row.get("turn"),
                    "reason": str(row.get("reason") or ""),
                }
            )
            continue
        ranks = row.get("ranks") or {}
        if not ranks:
            continue
        ranked += 1
        best = min(int(rank) for rank in ranks.values())
        for team, rank in ranks.items():
            per_team_ranks.setdefault(team, []).append(int(rank))
            if int(rank) == best:
                wins[team] = wins.get(team, 0) + 1

    standing = sorted(
        (
            {
                "team": team,
                "comparisons": len(ranks),
                "mean_rank": round(mean(ranks), 2),
                "wins": wins.get(team, 0),
                "best": min(ranks),
                "worst": max(ranks),
            }
            for team, ranks in per_team_ranks.items()
        ),
        key=lambda entry: (entry["mean_rank"], -entry["wins"], entry["team"]),
    )
    return {
        "ranked_comparisons": ranked,
        "incomparable": incomparable,
        "standing": standing,
        # A standing where every team shares one mean rank is a tie, and
        # saying so beats printing an order the data does not support.
        "separates_teams": len({entry["mean_rank"] for entry in standing}) > 1,
    }
