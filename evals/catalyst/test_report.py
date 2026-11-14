"""Offline Catalyst report tests for pure `openclinai.report.v2` JSON packets."""

from __future__ import annotations

import ast
import json
import shutil
import socket
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalyst-notebook-golden"
ROOT = Path(__file__).resolve().parents[2]


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("network blocked in catalyst report tests")

    monkeypatch.setattr(socket, "socket", _raise)


def test_build_report_offline_contains_required_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_report

    run_dir = tmp_path / "golden"
    shutil.copytree(FIXTURE, run_dir)
    if (run_dir / "report.html").exists():
        (run_dir / "report.html").unlink()
    out = build_report(run_dir)
    assert out == run_dir / "report-data.json"
    assert (run_dir / "run-summary.json").is_file()
    assert (run_dir / "dashboard-data.json").is_file()
    assert not (run_dir / "report.html").exists()

    raw = out.read_text(encoding="utf-8")
    packet = json.loads(raw)
    assert packet["schema"] == "openclinai.report.v2"
    assert packet["family"] == "catalyst"

    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    assertion_names = sorted(
        {a["name"] for row in results["results"] for a in row["assertions"]}
    )
    for row in results["results"]:
        assert row["scenarioId"] in raw
    for name in assertion_names:
        assert name in raw

    assert "gold-fail-high-judge" in raw
    assert "row_set mismatch" in raw
    assert "scenarios/gold-fail-high-judge/repetition-01/15-gold-execution-match-base.json" in raw
    assert "FAIL" in raw
    assert "intent_fidelity" in raw
    assert "Synthetic fixture: SQL projection/filters align" in raw
    assert "mid revision" in raw
    assert "result_status = 'final'" in raw
    assert "@@" in raw


def test_gold_fail_with_perfect_judge_still_reports_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_catalyst_report_packet

    packet = build_catalyst_report_packet(FIXTURE)
    run0 = packet["runs"][0]
    scen = next(s for s in run0["scenarios"] if s["scenario_id"] == "gold-fail-high-judge")
    cell = next(iter(scen["turns"][0]["cells"].values()))
    assert cell["catalyst_turn"]["passed"] is False
    assert "FAIL" in cell["catalyst_turn"]["reported"]
    assert "100" in cell["catalyst_turn"]["reported"]


def test_import_boundary_rejects_harness_validate() -> None:
    src = (ROOT / "harness" / "catalyst" / "report.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "harness.validate" or alias.name.startswith(
                    "harness.validate."
                ):
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "harness.validate" or node.module.startswith(
                "harness.validate."
            ):
                bad.append(node.module)
    assert bad == [], bad


def test_report_carries_narrative_context_not_just_the_gate_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_catalyst_report_packet

    packet = build_catalyst_report_packet(FIXTURE)
    raw = json.dumps(packet)

    results = json.loads((FIXTURE / "results.json").read_text(encoding="utf-8"))
    suite = json.loads((FIXTURE / "suite.json").read_text(encoding="utf-8"))

    assert f"{results['passedCount']}/{results['resultCount']}" in raw
    assert packet["runs"][0]["catalyst"]["dataset"]["patients"] == results["dataset"]["patients"]

    for scenario in suite["scenarios"]:
        assert scenario["initialQuestion"] in raw
        if scenario.get("followupInstruction"):
            assert scenario["followupInstruction"] in raw

    execute = json.loads(
        (
            FIXTURE
            / "scenarios/narrowing-unchanged-base/repetition-01/13-execute-successor.json"
        ).read_text(encoding="utf-8")
    )
    body = (execute.get("response") or {}).get("body") or execute
    result = body.get("result") or body
    row_count = result.get("rowCount") or len(result.get("rows") or [])
    narrow_scen = next(
        s for s in packet["runs"][0]["scenarios"] if s["scenario_id"] == "narrowing-unchanged-base"
    )
    narrow_cell = next(iter(narrow_scen["turns"][0]["cells"].values()))
    assert narrow_cell["catalyst_turn"]["result_preview"]["row_count"] == row_count


def test_catalyst_pages_can_actually_sort_their_tables() -> None:
    from evals.validate._test_shell import report_shell_js

    script = report_shell_js()
    assert "function htmlEsc" in script
    assert "function makeSortable(" in script


def test_a_failed_check_carries_its_assertion_class() -> None:
    from harness.catalyst.notebook_validation import assertion_class

    assert assertion_class("writer_outcome-t1") == "evaluation"
    assert assertion_class("writer_model") == "conformance"
    assert assertion_class("base_gold_execution_match") == "evaluation"


def _two_team_run(
    tmp_path: Path,
    *,
    team_b_passed: bool = True,
    team_b_conformant: bool = True,
    gates: dict | None = None,
) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "run_manifest.json").write_text("{}", encoding="utf-8")
    (run / "suite.json").write_text(
        json.dumps(
            {
                "id": "two-team-suite",
                "scenarios": [{"id": "S1", "initialQuestion": "How many?"}],
                "profiles": {
                    "team-a": {"writerModelId": "w"},
                    "team-b": {"writerModelId": "w", "reviewerModelId": "r"},
                },
            }
        ),
        encoding="utf-8",
    )
    b_assertions = [
        {"name": "base_gold_execution_match", "passed": team_b_passed},
    ]
    if not team_b_conformant:
        b_assertions.append(
            {"name": "gateway_persistence", "passed": False, "class": "conformance"}
        )
    rows = [
        {
            "scenarioId": "S1",
            "profileId": "team-a",
            "passed": True,
            "status": "completed",
            "repetition": 1,
            "family": "single-ready",
            "assertions": [{"name": "base_gold_execution_match", "passed": True}],
        },
        {
            "scenarioId": "S1",
            "profileId": "team-b",
            "passed": team_b_passed and team_b_conformant,
            "status": "completed",
            "repetition": 1,
            "family": "single-ready",
            "assertions": b_assertions,
        },
    ]
    passed_count = sum(1 for row in rows if row["passed"])
    (run / "results.json").write_text(
        json.dumps(
            {
                "results": rows,
                "passedCount": passed_count,
                "resultCount": len(rows),
                "skippedCount": 0,
            }
        ),
        encoding="utf-8",
    )
    judge_rows = [
        {
            "scenario_id": "S1",
            "turn": 0,
            "version_id": "version-a",
            "composite": 77,
            "intent_fidelity": 2,
            "sql_quality": 3,
            "schema_discipline": 3,
            "intent_fidelity_rationale": "team-a drifted from the ask",
            "evidence_paths": ["scenarios/team-a/S1/repetition-01/06-execute-base.json"],
        },
        {
            "scenario_id": "S1",
            "turn": 0,
            "version_id": "version-b",
            "composite": 55,
            "intent_fidelity": 1,
            "sql_quality": 3,
            "schema_discipline": 3,
            "intent_fidelity_rationale": "team-b answered a different question",
            "evidence_paths": ["scenarios/team-b/S1/repetition-01/06-execute-base.json"],
        },
    ]
    (run / "judge.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in judge_rows), encoding="utf-8"
    )
    if gates is not None:
        (run / "run-config.json").write_text(
            json.dumps({"gates": gates, "publish": {}}), encoding="utf-8"
        )
    return run


def test_judge_cells_join_by_team_not_by_scenario_and_turn(tmp_path: Path) -> None:
    from harness.catalyst.report import build_catalyst_report_packet

    run = _two_team_run(tmp_path)
    run0 = build_catalyst_report_packet(run)["runs"][0]
    by_team = {jr["backend_id"]: jr for jr in run0["judge_rows"] if jr["scenario_id"] == "S1"}
    assert by_team["team-a"]["benchmark_score"] == 77.0
    assert by_team["team-b"]["benchmark_score"] == 55.0
    assert "team-b answered a different question" in by_team["team-b"]["note"]


def test_verdict_states_the_frozen_gates_it_applied(tmp_path: Path) -> None:
    from harness.catalyst.report import build_catalyst_report_packet

    run = _two_team_run(
        tmp_path, team_b_passed=False, gates={"overall": 0.9, "per_scenario": 0.8}
    )
    gv = build_catalyst_report_packet(run)["runs"][0]["catalyst"]["gate_verdict"]
    assert gv["gates"] == {"overall": 0.9, "per_scenario": 0.8}
    assert "w (writer-only)" in gv["qualified_teams"]
    assert gv["qualified"] is True


def test_verdict_calls_a_conformance_broken_team_undecidable(tmp_path: Path) -> None:
    from harness.catalyst.report import build_catalyst_report_packet

    run = _two_team_run(
        tmp_path,
        team_b_passed=False,
        team_b_conformant=False,
        gates={"overall": 0.9, "per_scenario": 0.8},
    )
    gv = build_catalyst_report_packet(run)["runs"][0]["catalyst"]["gate_verdict"]
    assert "w (writer-only)" in gv["qualified_teams"]
    assert "w + r checker" in gv["undecidable_teams"]


def test_single_profile_run_keeps_its_headline_and_gets_no_gate_verdict() -> None:
    from harness.catalyst.report import build_catalyst_report_packet

    packet = build_catalyst_report_packet(FIXTURE)
    gv = packet["runs"][0]["catalyst"]["gate_verdict"]
    assert "gates" not in gv
    results = json.loads((FIXTURE / "results.json").read_text(encoding="utf-8"))
    assert f"{results['passedCount']}/{results['resultCount']}" in gv["verdict"]


def test_safety_adjusted_benchmark_score_caps_failed_gold_cell_in_arm_mean() -> None:
    from harness.catalyst.report import build_catalyst_report_packet

    packet = build_catalyst_report_packet(FIXTURE)
    run0 = packet["runs"][0]
    failed_jr = next(
        jr for jr in run0["judge_rows"] if jr["scenario_id"] == "gold-fail-high-judge"
    )
    assert failed_jr["raw_benchmark_score"] == 100.0
    assert failed_jr["benchmark_score"] == 40.0
    assert failed_jr["safety_adjusted_benchmark_score"] == 40.0

    arm_summary = run0["judge"][0]
    # 5 passing scenarios at 100.0 + 1 failed gold scenario capped at 40.0 => 540 / 6 = 90.0
    assert arm_summary["composite_mean"] == 100.0
    assert arm_summary["raw_benchmark_score"] == 100.0
    assert arm_summary["benchmark_score"] == 90.0
    assert arm_summary["safety_adjusted_benchmark_score"] == 90.0


def test_multi_repetition_preserves_earlier_failure_and_scopes_sql_versions(
    tmp_path: Path,
) -> None:
    from harness.catalyst.report import build_report

    run = tmp_path / "multi-rep"
    (run / "scenarios" / "S1" / "repetition-01").mkdir(parents=True)
    (run / "scenarios" / "S1" / "repetition-02").mkdir(parents=True)
    (run / "scenarios" / "S1" / "repetition-01" / "01-base-sql.sql").write_text(
        "SELECT bad_col FROM wrong_table", encoding="utf-8"
    )
    (run / "scenarios" / "S1" / "repetition-02" / "01-base-sql.sql").write_text(
        "SELECT good_col FROM right_table", encoding="utf-8"
    )
    (run / "scenarios" / "S1" / "repetition-01" / "06-execute-base.json").write_text(
        json.dumps({"result": {"columns": ["bad_col"], "rows": [], "rowCount": 0}}),
        encoding="utf-8",
    )
    (run / "scenarios" / "S1" / "repetition-02" / "06-execute-base.json").write_text(
        json.dumps({"result": {"columns": ["good_col"], "rows": [{"good_col": 7}], "rowCount": 1}}),
        encoding="utf-8",
    )
    (run / "run_manifest.json").write_text("{}", encoding="utf-8")
    (run / "suite.json").write_text(
        json.dumps(
            {
                "id": "multi-rep-suite",
                "profileId": "team-a",
                "scenarios": [{"id": "S1", "initialQuestion": "Count active patients"}],
                "profiles": {"team-a": {"writerModelId": "w"}},
            }
        ),
        encoding="utf-8",
    )
    rows = [
        {
            "scenarioId": "S1",
            "profileId": "team-a",
            "passed": False,
            "status": "completed",
            "repetition": 1,
            "timing": {"unadjustedGenerationWallMs": 1200},
            "assertions": [
                {
                    "name": "base_gold_execution_match",
                    "passed": False,
                    "evidence": "rep1 mismatch",
                }
            ],
        },
        {
            "scenarioId": "S1",
            "profileId": "team-a",
            "passed": True,
            "status": "completed",
            "repetition": 2,
            "timing": {"unadjustedGenerationWallMs": 800},
            "assertions": [{"name": "base_gold_execution_match", "passed": True}],
        },
    ]
    (run / "results.json").write_text(
        json.dumps({"results": rows, "passedCount": 1, "resultCount": 2, "skippedCount": 0}),
        encoding="utf-8",
    )

    build_report(run)
    packet = json.loads((run / "report-data.json").read_text(encoding="utf-8"))
    dash = json.loads((run / "dashboard-data.json").read_text(encoding="utf-8"))

    run0 = packet["runs"][0]
    scen = run0["scenarios"][0]
    assert len(scen["turns"]) == 2
    rep1_cell = scen["turns"][0]["cells"]["team-a"]["catalyst_turn"]
    rep2_cell = scen["turns"][1]["cells"]["team-a"]["catalyst_turn"]

    assert rep1_cell["passed"] is False
    assert rep1_cell["failed_assertions"][0]["evidence"] == "rep1 mismatch"
    assert [v["sql"] for v in rep1_cell["sql_versions"]] == ["SELECT bad_col FROM wrong_table"]
    assert rep1_cell["result_preview"]["returned"] == 0

    assert rep2_cell["passed"] is True
    assert [v["sql"] for v in rep2_cell["sql_versions"]] == ["SELECT good_col FROM right_table"]
    assert rep2_cell["result_preview"]["returned"] == 1

    assert run0["summary"][0]["avg_latency_ms"] == 1000
    assert dash["status"]["grid"][0]["passed"] is False
    assert dash["status"]["grid"][0]["turns_total"] == 2
    assert dash["details"] == {}
    shard_rel = dash["detail_shards"]["team-a"]
    shard_payload = json.loads((run / shard_rel).read_text(encoding="utf-8"))
    assert len(shard_payload["S1|team-a"]["turns"]) == 2
