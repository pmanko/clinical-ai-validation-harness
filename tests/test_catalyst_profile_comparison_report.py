"""The comparison page over ONE frozen comparison run.

The comparison is one run with every row stamped by the team that produced
it, so the page groups rows per team from a single run directory rather than
joining one directory per profile.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.catalyst.profile_comparison_report import (
    build_comparison_report,
    entries_from_comparison_run,
)


def _write_comparison_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = [
        {"scenarioId": "A1", "profileId": "team-a", "status": "completed",
         "passed": True, "assertions": [{"name": "x", "passed": True}],
         "timing": {"unadjustedGenerationWallMs": 1000}},
        {"scenarioId": "A1", "profileId": "team-b", "status": "completed",
         "passed": False, "assertions": [{"name": "x", "passed": False}],
         "timing": {"unadjustedGenerationWallMs": 3000}},
        {"scenarioId": "U1", "profileId": "team-a", "status": "completed",
         "passed": True, "assertions": [{"name": "x", "passed": True}],
         "timing": {"unadjustedGenerationWallMs": 1200}},
    ]
    (run_dir / "results.json").write_text(
        json.dumps({"runId": "run-1", "suiteId": "suite-1", "results": rows,
                    "passedCount": 2, "resultCount": 3}),
        encoding="utf-8",
    )
    return run_dir


def test_one_comparison_run_becomes_one_entry_per_team(tmp_path: Path) -> None:
    run_dir = _write_comparison_run(tmp_path)

    entries = entries_from_comparison_run(run_dir)

    assert [e["profile_id"] for e in entries] == ["team-a", "team-b"]
    assert all(e["run_dir"] == run_dir for e in entries)


def test_each_team_is_scored_on_its_own_rows_alone(tmp_path: Path) -> None:
    """team-b must not inherit team-a's passes from the shared run dir."""
    run_dir = _write_comparison_run(tmp_path)

    html = build_comparison_report(entries_from_comparison_run(run_dir))

    assert "2/2" in html   # team-a: A1 + U1 both passed
    assert "0/1" in html   # team-b: its single A1 row failed
    assert "PASS" in html and "FAIL" in html


def test_a_scenario_that_passed_by_expecting_its_failure_stays_passed(
    tmp_path: Path,
) -> None:
    """The runner's verdict outranks the status heuristic.

    A bounded-failure scenario ends with status "failed" and passed: true;
    recomputing from status would quietly regress its pass."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "results.json").write_text(
        json.dumps(
            {
                "results": [
                    {"scenarioId": "bounded", "profileId": "team-a",
                     "status": "failed", "passed": True,
                     "assertions": [{"name": "x", "passed": True}],
                     "timing": {"unadjustedGenerationWallMs": 10}},
                ]
            }
        ),
        encoding="utf-8",
    )

    html = build_comparison_report(entries_from_comparison_run(run_dir))

    assert "1/1" in html
    assert "PASS" in html


def _write_taxonomy_run(tmp_path: Path) -> Path:
    """Three teams on one scenario: a pass, a judged failure with structured
    gold evidence, and a run that broke its own contract."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = [
        {"scenarioId": "A1", "profileId": "team-pass", "status": "completed",
         "passed": True, "assertions": [{"name": "session_created",
                                         "class": "conformance",
                                         "passed": True}],
         "timing": {"unadjustedGenerationWallMs": 1000}},
        # The same team misses a second scenario, so nobody clears the gates.
        {"scenarioId": "A2", "profileId": "team-pass", "status": "completed",
         "passed": False,
         "assertions": [{"name": "base_writer_outcome", "class": "evaluation",
                         "passed": False,
                         "evidence": {"observed": "ready",
                                      "expected": "unsupported"}}],
         "timing": {"unadjustedGenerationWallMs": 1000}},
        {"scenarioId": "A1", "profileId": "team-judged", "status": "completed",
         "passed": False,
         "assertions": [{"name": "successor_gold_execution_match-t1",
                         "class": "evaluation", "passed": False,
                         "evidence": {"modelRowCount": 4,
                                      "referenceRowCount": 6}}],
         "timing": {"unadjustedGenerationWallMs": 1000}},
        {"scenarioId": "A1", "profileId": "team-broken", "status": "completed",
         "passed": False,
         "assertions": [{"name": "writer_model", "class": "conformance",
                         "passed": False, "evidence": "wrong model answered"}],
         "timing": {"unadjustedGenerationWallMs": 1000}},
    ]
    (run_dir / "results.json").write_text(
        json.dumps({"results": rows}), encoding="utf-8"
    )
    return run_dir


def test_a_broken_run_is_not_reported_as_a_result(tmp_path: Path) -> None:
    """An invalid measurement must never be presented as a team's score.

    A judged failure is a finding and says why in one sentence; a cell whose
    contract broke measured nothing and has to say that instead.
    """
    run_dir = _write_taxonomy_run(tmp_path)

    html = build_comparison_report(entries_from_comparison_run(run_dir))

    assert "FAIL" in html and "INVALID" in html
    assert ("the answer returned 4 rows; the independent reference "
            "returns 6") in html
    assert "wrong model answered" in html


def test_the_page_states_the_verdict_and_the_gates_it_applied(
    tmp_path: Path,
) -> None:
    """A frozen page has to be readable a year later without the roadmap."""
    run_dir = _write_taxonomy_run(tmp_path)

    html = build_comparison_report(
        entries_from_comparison_run(run_dir),
        gates={"overall": 0.90, "per_scenario": 0.80},
    )

    assert "No team qualified" in html
    assert "90" in html and "80" in html
    # The broken team is undecidable, not merely beaten.
    assert "invalid measurement" in html


def test_a_team_that_meets_every_gate_is_named(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "results.json").write_text(json.dumps({"results": [
        {"scenarioId": "A1", "profileId": "team-a", "status": "completed",
         "passed": True, "assertions": [{"name": "session_created",
                                         "class": "conformance",
                                         "passed": True}],
         "timing": {"unadjustedGenerationWallMs": 10}},
    ]}), encoding="utf-8")

    html = build_comparison_report(
        entries_from_comparison_run(run_dir),
        gates={"overall": 0.90, "per_scenario": 0.80},
    )

    assert "Qualified: team-a" in html
    assert "No team qualified" not in html


def test_a_failure_with_nothing_recorded_still_reports_a_verdict(
    tmp_path: Path,
) -> None:
    """A row can be marked failed with no failing assertion behind it (an
    older runner, a truncated record). The page must still say FAIL rather
    than silently claim a pass."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "results.json").write_text(json.dumps({"results": [
        {"scenarioId": "A1", "profileId": "team-a", "status": "completed",
         "passed": False, "assertions": [],
         "timing": {"unadjustedGenerationWallMs": 10}},
    ]}), encoding="utf-8")

    html = build_comparison_report(entries_from_comparison_run(run_dir))

    assert "FAIL" in html
