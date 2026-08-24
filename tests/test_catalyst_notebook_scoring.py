"""The scorer turns a recorded run into the numbers the comparison reports.

It reads only what the runner already wrote, so scoring a finished run is a
pure function of its evidence: the same run scored twice must produce the same
bytes, or the comparison cannot be checked by anyone else.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness.catalyst.notebook_scoring import score_run, wilson_interval


def _write_run(tmp_path: Path, results: dict[str, Any]) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "results.json").write_text(json.dumps(results), encoding="utf-8")
    return run_dir


def _row(
    scenario: str,
    *,
    passed: bool,
    outcomes: list[str],
    status: str = "completed",
    answer: bool | None = None,
    expected: list[str] | None = None,
) -> dict[str, Any]:
    turns = [
        {
            "observedOutcome": outcome,
            "expectedOutcome": (expected or outcomes)[index],
        }
        for index, outcome in enumerate(outcomes)
    ]
    row: dict[str, Any] = {
        "scenarioId": scenario,
        "status": status,
        "passed": passed,
        "turns": turns,
        "assertions": [],
    }
    if answer is not None:
        row["assertions"] = [
            {"name": "successor_gold_execution_match", "passed": answer}
        ]
    return row


def test_wilson_interval_brackets_the_observed_rate() -> None:
    low, high = wilson_interval(9, 10)
    assert 0.0 < low < 0.9 < high < 1.0
    # Pinned to the roots of the quadratic the Wilson interval solves,
    # (n+z²)p² − (2np̂+z²)p + np̂² = 0, computed independently of the
    # implementation's algebra so a refactor cannot quietly move the statistics.
    assert (round(low, 6), round(high, 6)) == (0.59585, 0.982124)


def test_wilson_interval_of_no_observations_is_the_whole_range() -> None:
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_scoring_counts_scenarios_and_rates(tmp_path: Path) -> None:
    run_dir = _write_run(
        tmp_path,
        {
            "runId": "run-1",
            "suiteId": "suite-1",
            "results": [
                _row("A1", passed=True, outcomes=["ready"], answer=True),
                _row("A1", passed=True, outcomes=["ready"], answer=True),
                _row("A1", passed=False, outcomes=["ready"], answer=False),
                _row("U1", passed=True, outcomes=["unsupported"]),
            ],
            "infrastructureFailures": [],
        },
    )
    scored = score_run(run_dir)

    assert scored["totals"]["scored"] == 4
    assert scored["totals"]["passed"] == 3
    a1 = scored["scenarios"]["A1"]
    assert a1["scored"] == 3
    assert a1["passed"] == 2
    assert a1["answerMatched"] == 2
    assert a1["rate"] == pytest.approx(2 / 3)
    assert scored["scenarios"]["U1"]["outcomes"] == {"unsupported": 1}


def test_infrastructure_failures_stay_out_of_the_denominator(tmp_path: Path) -> None:
    run_dir = _write_run(
        tmp_path,
        {
            "runId": "run-1",
            "suiteId": "suite-1",
            "results": [
                _row("A1", passed=True, outcomes=["ready"]),
                _row("A1", passed=False, outcomes=[], status="infrastructure_failed"),
                {"scenarioId": "M9", "status": "skipped"},
            ],
            "infrastructureFailures": [{"scenarioId": "A1", "repetition": 2}],
        },
    )
    scored = score_run(run_dir)

    assert scored["totals"]["scored"] == 1
    assert scored["totals"]["infrastructureFailed"] == 1
    assert scored["totals"]["skipped"] == 1
    assert scored["scenarios"]["A1"]["scored"] == 1


def test_outcome_accuracy_is_measured_against_what_was_expected(
    tmp_path: Path,
) -> None:
    """A clarification that arrives as a ready query is a wrong answer kind."""
    run_dir = _write_run(
        tmp_path,
        {
            "runId": "run-1",
            "suiteId": "suite-1",
            "results": [
                _row(
                    "B1",
                    passed=False,
                    outcomes=["ready"],
                    expected=["needs_clarification"],
                ),
                _row("B1", passed=True, outcomes=["needs_clarification"]),
            ],
            "infrastructureFailures": [],
        },
    )
    scored = score_run(run_dir)

    accuracy = scored["outcomeAccuracy"]["needs_clarification"]
    assert accuracy == {"expected": 2, "observed": 1}


def test_scoring_the_same_run_twice_produces_identical_bytes(
    tmp_path: Path,
) -> None:
    run_dir = _write_run(
        tmp_path,
        {
            "runId": "run-1",
            "suiteId": "suite-1",
            "results": [
                _row("A2", passed=True, outcomes=["ready"], answer=True),
                _row("A1", passed=False, outcomes=["ready"], answer=False),
            ],
            "infrastructureFailures": [],
        },
    )

    first = score_run(run_dir, as_json=True)
    second = score_run(run_dir, as_json=True)

    assert first == second
    assert isinstance(first, str)

    # Two independent guarantees, each checked on its own because together
    # they mask each other: the report itself is ordered by scenario id...
    assert list(score_run(run_dir)["scenarios"]) == ["A1", "A2"]
    # ...and the serialization is canonical, so every key is sorted too.
    top_level = [
        line.strip().split('"')[1]
        for line in first.splitlines()
        if line.startswith("  \"")
    ]
    assert top_level == sorted(top_level)
