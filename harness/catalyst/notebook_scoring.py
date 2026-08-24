"""Score a recorded notebook-validation run.

The runner writes evidence; this reads it. Scoring is a pure function of a
finished run directory so the same run scored twice produces the same bytes,
which is what lets someone else check a published comparison instead of
trusting it.

This is not a second runner: it never talks to Catalyst and never creates a
session. It consumes `results.json` exactly as `notebook_validation` wrote it.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

SCORING_CONTRACT_VERSION = "harness.catalyst-notebook.scoring.v1"

_Z_95 = 1.959963984540054
"""Standard normal quantile for a two-sided 95% interval."""

_PRECISION = 6
"""Rates are rounded so the report is byte-stable across machines."""


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    """The 95% Wilson score interval for a proportion.

    Wilson rather than the normal approximation because these denominators are
    three to five runs, where the naive interval leaves the unit range and
    collapses to zero width at 0% and 100%.
    """
    if total <= 0:
        return (0.0, 1.0)
    proportion = successes / total
    denominator = 1 + _Z_95**2 / total
    center = (proportion + _Z_95**2 / (2 * total)) / denominator
    margin = (
        _Z_95
        * math.sqrt(
            proportion * (1 - proportion) / total + _Z_95**2 / (4 * total**2)
        )
        / denominator
    )
    return (max(0.0, center - margin), min(1.0, center + margin))


def _rate(successes: int, total: int) -> float | None:
    return round(successes / total, _PRECISION) if total else None


def _interval(successes: int, total: int) -> list[float]:
    low, high = wilson_interval(successes, total)
    return [round(low, _PRECISION), round(high, _PRECISION)]


def _score_rows(scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The aggregate view of a set of scored rows: totals, per-scenario
    rates, and outcome accuracy. Used pooled and once per compared team."""
    scenarios: dict[str, dict[str, Any]] = {}
    expected_outcomes: Counter[str] = Counter()
    observed_outcomes: Counter[str] = Counter()

    for row in scored_rows:
        scenario_id = str(row.get("scenarioId"))
        bucket = scenarios.setdefault(
            scenario_id,
            {"scored": 0, "passed": 0, "answerChecked": 0, "answerMatched": 0,
             "outcomes": Counter()},
        )
        bucket["scored"] += 1
        if row.get("passed") is True:
            bucket["passed"] += 1
        # The opening question is a scored user turn like the rest: for a
        # clarification or a refusal it is the only answer the scenario has.
        base_observed = row.get("baseOutcome")
        if base_observed is not None:
            base_expected = str(row.get("expectedBaseOutcome") or base_observed)
            bucket["outcomes"][str(base_observed)] += 1
            expected_outcomes[base_expected] += 1
            if str(base_observed) == base_expected:
                observed_outcomes[base_expected] += 1
        for turn in row.get("turns") or []:
            observed = str(turn.get("observedOutcome"))
            expected = str(turn.get("expectedOutcome") or observed)
            bucket["outcomes"][observed] += 1
            expected_outcomes[expected] += 1
            if observed == expected:
                observed_outcomes[expected] += 1
        for assertion in row.get("assertions") or []:
            if str(assertion.get("name", "")).endswith("gold_execution_match"):
                bucket["answerChecked"] += 1
                if assertion.get("passed"):
                    bucket["answerMatched"] += 1

    # Sorted so a run recorded in a different order scores identically.
    scenario_report = {
        scenario_id: {
            "scored": bucket["scored"],
            "passed": bucket["passed"],
            "rate": _rate(bucket["passed"], bucket["scored"]),
            "interval": _interval(bucket["passed"], bucket["scored"]),
            "answerChecked": bucket["answerChecked"],
            "answerMatched": bucket["answerMatched"],
            "outcomes": dict(sorted(bucket["outcomes"].items())),
        }
        for scenario_id, bucket in sorted(scenarios.items())
    }

    passed_total = sum(bucket["passed"] for bucket in scenarios.values())
    scored_total = sum(bucket["scored"] for bucket in scenarios.values())
    worst = min(
        (entry["rate"] for entry in scenario_report.values() if entry["rate"] is not None),
        default=None,
    )
    return {
        "totals": {
            "scored": scored_total,
            "passed": passed_total,
            "rate": _rate(passed_total, scored_total),
            "interval": _interval(passed_total, scored_total),
            "worstScenarioRate": worst,
        },
        "outcomeAccuracy": {
            outcome: {
                "expected": expected_outcomes[outcome],
                "observed": observed_outcomes[outcome],
            }
            for outcome in sorted(expected_outcomes)
        },
        "scenarios": scenario_report,
    }


def score_run(run_dir: Path | str, *, as_json: bool = False) -> dict[str, Any] | str:
    """Score one run directory.

    The pooled view stays at the top level; a run whose rows carry a
    profileId -- the frozen comparison -- is also scored once per team under
    ``profiles``, because the absolute gates and the selection ordering both
    read per-team numbers and a pooled rate would let one team's weakness
    hide in another's strength.

    Set ``as_json`` for the canonical serialization used when publishing or
    comparing two replays.
    """
    results_path = Path(run_dir) / "results.json"
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    rows = list(payload.get("results") or [])

    scored_rows = [
        row
        for row in rows
        if row.get("status") not in {"skipped", "infrastructure_failed"}
    ]
    report: dict[str, Any] = {
        "contractVersion": SCORING_CONTRACT_VERSION,
        "runId": payload.get("runId"),
        "suiteId": payload.get("suiteId"),
        **_score_rows(scored_rows),
    }
    report["totals"]["skipped"] = sum(row.get("status") == "skipped" for row in rows)
    report["totals"]["infrastructureFailed"] = sum(
        row.get("status") == "infrastructure_failed" for row in rows
    )
    team_ids = sorted(
        {str(row["profileId"]) for row in scored_rows if row.get("profileId")}
    )
    report["profiles"] = {
        team: _score_rows([row for row in scored_rows if row.get("profileId") == team])
        for team in team_ids
    }
    if as_json:
        return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return report
