"""The comparison v2 JSON packet over ONE frozen comparison run."""

from __future__ import annotations

import json
from pathlib import Path

from harness.catalyst.report import (
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

    packet = build_comparison_report(entries_from_comparison_run(run_dir))
    entries = {e["profile_id"]: e for e in packet["runs"][0]["catalyst"]["comparison_entries"]}

    assert entries["team-a"]["passed_count"] == "2/2"
    assert entries["team-b"]["passed_count"] == "0/1"


def test_a_scenario_that_passed_by_expecting_its_failure_stays_passed(
    tmp_path: Path,
) -> None:
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

    packet = build_comparison_report(entries_from_comparison_run(run_dir))
    entries = {e["profile_id"]: e for e in packet["runs"][0]["catalyst"]["comparison_entries"]}

    assert entries["team-a"]["passed_count"] == "1/1"


def _write_taxonomy_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = [
        {"scenarioId": "A1", "profileId": "team-pass", "status": "completed",
         "passed": True, "assertions": [{"name": "session_created",
                                         "class": "conformance",
                                         "passed": True}],
         "timing": {"unadjustedGenerationWallMs": 1000}},
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
    run_dir = _write_taxonomy_run(tmp_path)

    packet = build_comparison_report(entries_from_comparison_run(run_dir))
    gv = packet["runs"][0]["catalyst"]["gate_verdict"]

    assert gv["invalid"] == 1
    assert any("4 rows" in b and "6" in b for b in gv["blockers"])
    assert any("wrong model answered" in b for b in gv["blockers"])


def test_the_page_states_the_verdict_and_the_gates_it_applied(
    tmp_path: Path,
) -> None:
    run_dir = _write_taxonomy_run(tmp_path)

    packet = build_comparison_report(
        entries_from_comparison_run(run_dir),
        gates={"overall": 0.90, "per_scenario": 0.80},
    )
    gv = packet["runs"][0]["catalyst"]["gate_verdict"]

    assert gv["qualified"] is False
    assert gv["gates"] == {"overall": 0.90, "per_scenario": 0.80}
    assert "team-broken" in gv["undecidable_teams"]


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

    packet = build_comparison_report(
        entries_from_comparison_run(run_dir),
        gates={"overall": 0.90, "per_scenario": 0.80},
    )
    gv = packet["runs"][0]["catalyst"]["gate_verdict"]

    assert gv["verdict"] == "Qualified: team-a"
    assert gv["qualified"] is True
