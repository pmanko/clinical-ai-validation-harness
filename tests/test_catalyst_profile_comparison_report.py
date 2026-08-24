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
    assert "PASS (1/1)" in html and "FAIL (0/1)" in html
