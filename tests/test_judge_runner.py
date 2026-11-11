"""Unit tests for `harness.validate.judge_runner` blind-session and multi-judge orchestration."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
import pytest

from harness.validate.judge_runner import (
    _prepare_blind_session_dir,
    _reserve_judge_passes,
    _validate_session_rows,
    last_json,
    parse_judges,
)


def test_last_json_parses_trailing_comma_and_preserves_strings() -> None:
    text = """Here is my evaluation:
```json
[
  {
    "scenario_id": "s1",
    "backend_id": "arm_a",
    "accuracy": 9,
    "note": "has a comma, inside string }",
  },
]
```
"""
    rows = last_json(text)
    assert len(rows) == 1
    assert rows[0]["accuracy"] == 9
    assert rows[0]["note"] == "has a comma, inside string }"


def test_parse_judges_supports_multi_judge_specs_and_defaults() -> None:
    args = Namespace(
        judges=["claude:claude-sonnet-5-5:medium:2", "codex:gpt-6.1-sol:high"],
        judge_passes=1,
        agent="claude",
    )
    specs = parse_judges(args)
    assert specs == [
        {"agent": "claude", "model": "claude-sonnet-5-5", "effort": "medium", "passes": 2},
        {"agent": "codex", "model": "gpt-6.1-sol", "effort": "high", "passes": 1},
    ]


def test_reserve_judge_passes_allocates_contiguous_ranges(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    judges = [{"agent": "claude", "model": "claude-sonnet-5-5", "effort": "medium", "passes": 2}]
    first = _reserve_judge_passes(run_dir, judges)
    second = _reserve_judge_passes(run_dir, judges)
    assert first == [(judges[0], 0, 2)]
    assert second == [(judges[0], 2, 4)]


def test_validate_session_rows_enforces_schema_and_cell_coverage() -> None:
    expected = [("s1", "arm_a"), ("s1", "arm_b")]
    valid_rows = [
        {"scenario_id": "s1", "backend_id": "arm_a", "accuracy": 8, "completeness": 8, "relevance": 9, "harm": False},
        {"scenario_id": "s1", "backend_id": "arm_b", "accuracy": 7, "completeness": 7, "relevance": 8, "harm": False},
    ]
    assert _validate_session_rows(valid_rows, expected) == valid_rows

    with pytest.raises(ValueError, match="cell coverage mismatch"):
        _validate_session_rows(valid_rows[:1], expected)

    with pytest.raises(ValueError, match="must be numeric"):
        _validate_session_rows(
            [{"scenario_id": "s1", "backend_id": "arm_a", "accuracy": True}],
            [("s1", "arm_a")],
        )


def test_prepare_blind_session_dir_copies_only_bundle_and_charts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "charts").mkdir(parents=True)
    (run_dir / "charts" / "patient-1.txt").write_text("Chart text", encoding="utf-8")
    (run_dir / "results.jsonl").write_text("unblinded results", encoding="utf-8")
    bundle = tmp_path / "bundle-s1.jsonl"
    bundle.write_text(json.dumps({"scenario_id": "s1", "backend_id": "arm_a"}) + "\n", encoding="utf-8")

    out_dir = tmp_path / "judge_work"
    session_dir, staged_bundle = _prepare_blind_session_dir(run_dir, out_dir, "judge-p1", bundle)

    assert staged_bundle.is_file()
    assert (session_dir / "charts" / "patient-1.txt").is_file()
    assert not (session_dir / "results.jsonl").exists()
