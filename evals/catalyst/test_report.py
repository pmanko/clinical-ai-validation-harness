"""Offline Catalyst report tests (CVR-G11 / D8)."""

from __future__ import annotations

import ast
import json
import socket
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalyst-notebook-golden"
ROOT = Path(__file__).resolve().parents[2]


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("network blocked in catalyst report tests")

    monkeypatch.setattr(socket, "socket", _raise)


def test_build_report_offline_contains_required_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_report

    out = build_report(FIXTURE)
    assert out == FIXTURE / "report.html"
    html = out.read_text(encoding="utf-8")

    results = json.loads((FIXTURE / "results.json").read_text(encoding="utf-8"))
    assertion_names = sorted(
        {a["name"] for row in results["results"] for a in row["assertions"]}
    )
    for row in results["results"]:
        assert row["scenarioId"] in html
    for name in assertion_names:
        assert name in html

    assert "gold-fail-high-judge" in html
    assert "row_set mismatch" in html
    assert "scenarios/gold-fail-high-judge/repetition-01/15-gold-execution-match-base.json" in html
    assert "FAIL" in html
    assert "advisory" in html.lower() or "Judge" in html

    # Judge medians / rationales from finalized judge.jsonl
    assert "intent_fidelity" in html
    assert "Synthetic fixture: SQL projection/filters align" in html

    # Multi-version SQL unified diff hunk markers (line-level, rstrip)
    assert "mid revision" in html
    assert "result_status = 'final'" in html or "result_status = &#x27;final&#x27;" in html
    assert "@@" in html or "diff" in html.lower()

    assert "data-theme=" in html
    assert "theme-toggle" in html
    assert "th-sort" in html or "makeSortable" in html


def test_gold_fail_with_perfect_judge_still_reports_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_network(monkeypatch)
    from harness.catalyst.report import build_report

    html = build_report(FIXTURE).read_text(encoding="utf-8")
    # Scenario cell must remain FAIL despite composite 100 judge scores.
    idx = html.index("gold-fail-high-judge")
    window = html[idx : idx + 2500]
    assert "FAIL" in window
    assert "100" in window  # advisory judge composite still visible


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
    """The published report must read as evidence a human can follow — a
    headline verdict, what each scenario actually asked (question + follow-up
    instruction), and the executed row counts — not only the internal
    assertion matrix."""
    _block_network(monkeypatch)
    from harness.catalyst.report import build_report

    html = build_report(FIXTURE).read_text(encoding="utf-8")

    results = json.loads((FIXTURE / "results.json").read_text(encoding="utf-8"))
    suite = json.loads((FIXTURE / "suite.json").read_text(encoding="utf-8"))

    # Headline verdict from the run's own counts.
    assert f"{results['passedCount']}/{results['resultCount']}" in html
    # Dataset facts ground the run.
    assert str(results["dataset"]["patients"]) in html

    # Every scenario's question and follow-up instruction appear as narrative.
    for scenario in suite["scenarios"]:
        assert scenario["initialQuestion"] in html
        if scenario.get("followupInstruction"):
            assert scenario["followupInstruction"] in html

    # Executed row counts from the execution artifacts are surfaced.
    execute = json.loads(
        (
            FIXTURE
            / "scenarios/narrowing-unchanged-base/repetition-01/06-execute-base.json"
        ).read_text(encoding="utf-8")
    )
    body = (execute.get("response") or {}).get("body") or execute
    result = body.get("result") or body
    row_count = result.get("rowCount") or len(result.get("rows") or [])
    assert f"{row_count} rows" in html

    # The assertion-name dump collapses behind a pass-count summary instead of
    # dominating the matrix (names stay in the HTML for the marker tests).
    assert "passed</summary>" in html


def test_catalyst_pages_can_actually_sort_their_tables(tmp_path) -> None:
    """makeSortable rewrites each header through htmlEsc; without it the
    first table's header row is wiped and no table sorts."""
    from harness.catalyst import report as catalyst_report

    script = catalyst_report._SCRIPT
    assert "function htmlEsc" in script
    assert script.index("function htmlEsc") < script.index("makeSortable(")


def test_a_failed_check_chip_says_which_kind_it_is() -> None:
    """A broken contract and a judged miss are different findings; the
    matrix chip carries the split the runner stamped."""
    from harness.catalyst.report import _fail_chip

    judged = _fail_chip({"name": "writer_outcome-t1", "class": "evaluation"})
    broken = _fail_chip({"name": "writer_model", "class": "conformance"})

    assert "judged" in judged and "writer_outcome-t1" in judged
    assert "contract" in broken and "chip-invalid" in broken
    # Legacy rows without the stamp classify by name.
    assert "judged" in _fail_chip({"name": "base_gold_execution_match"})


def test_the_scenario_card_reads_as_the_conversation_it_ran() -> None:
    """Question, then each turn's instruction and what the writer answered
    -- the words of a question or refusal, in place."""
    from harness.catalyst.report import _scenario_card

    scenario = {
        "id": "B1",
        "initialQuestion": "Show recent HIV results.",
        "expectedBaseOutcome": "needs_clarification",
    }
    completed = [{
        "scenarioId": "B1",
        "baseOutcome": "needs_clarification",
        "baseAnswerText": "Which window, and which result types?",
        "assertions": [{"name": "x", "passed": True}],
        "turns": [{
            "turnIndex": 1,
            "instruction": "The last 90 days, CD4 only.",
            "expectedOutcome": "ready",
            "observedOutcome": "ready",
        }],
    }]

    html = _scenario_card(Path("/nonexistent"), scenario, "team × B1", completed)

    assert "Show recent HIV results." in html
    assert "Which window, and which result types?" in html
    assert "The last 90 days, CD4 only." in html
    order = [html.index("Show recent"), html.index("Which window"),
             html.index("The last 90 days")]
    assert order == sorted(order)


def _two_team_run(
    tmp_path: Path,
    *,
    team_b_passed: bool = True,
    team_b_conformant: bool = True,
    gates: dict | None = None,
) -> Path:
    """A minimal comparison run: two teams answering the same scenario, with
    judge rows whose only team attribution is their evidence layout."""
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


def _matrix_row(html: str, marker: str) -> str:
    start = html.index(marker)
    return html[html.rindex("<tr>", 0, start): html.index("</tr>", start)]


def test_judge_cells_join_by_team_not_by_scenario_and_turn(tmp_path) -> None:
    """Two teams share every scenario id; each matrix row must carry ITS
    team's composite, not whichever judge row came last in the file."""
    from harness.catalyst.report import build_report

    run = _two_team_run(tmp_path)
    html = build_report(run).read_text(encoding="utf-8")

    row_a = _matrix_row(html, "team-a · S1")
    row_b = _matrix_row(html, "team-b · S1")
    assert ">77<" in row_a and ">55<" not in row_a
    assert ">55<" in row_b and ">77<" not in row_b


def test_judge_summary_reports_each_team_with_floor_and_flagged_links(tmp_path) -> None:
    from harness.catalyst.report import build_report

    run = _two_team_run(tmp_path)
    html = build_report(run).read_text(encoding="utf-8")

    assert "Judge summary" in html
    # Teams are named by what distinguishes them, not their profile slugs.
    assert "writer-only" in html and "r-checked" in html
    # Both composites sit under the flag threshold, so both are called out
    # and linked into the detail section.
    assert "S1·turn 0 — 77" in html
    assert "S1·turn 0 — 55" in html
    assert "#judge-team-a-S1-t0" in html
    assert "#judge-team-b-S1-t0" in html
    # The all-teams row names the team on each flagged case.
    assert "writer-only: S1·turn 0" in html
    # The rationale text is reachable in the detail blocks.
    assert "team-b answered a different question" in html


def test_flagged_judge_detail_renders_open_at_its_anchor(tmp_path) -> None:
    from harness.catalyst.report import build_report

    run = _two_team_run(tmp_path)
    html = build_report(run).read_text(encoding="utf-8")

    start = html.index("id='judge-team-b-S1-t0'")
    tag = html[html.rindex("<details", 0, start): html.index(">", start) + 1]
    assert " open" in tag


def test_report_leads_with_plain_abstract_then_verdict_then_judge(tmp_path) -> None:
    """The page order is takeaways-first: plain-language abstract, the gate
    verdict, the judge summary — and only then the evidence detail."""
    from harness.catalyst.report import build_report

    run = _two_team_run(
        tmp_path, team_b_passed=False, gates={"overall": 0.9, "per_scenario": 0.8}
    )
    html = build_report(run).read_text(encoding="utf-8")

    order = [
        html.index("In plain terms"),
        html.index("Against the gates in force at publication"),
        html.index("Judge summary"),
        html.index("Scenario matrix"),
        html.index("Judge detail"),
        html.index("Methods &amp; provenance"),
    ]
    assert order == sorted(order)
    # The abstract speaks plainly and states the winner by its short name.
    assert "row for row" in html
    # The abstract carries relative performance and the failure anatomy —
    # never a pass/fail gate, which is publication policy and lives in the
    # Result section with the policy that set it.
    assert "acceptance bar" not in html.split("<h2>Result</h2>")[0]
    assert "practical tie" in html
    # This fixture's one miss is team-specific, so the cluster sentence says so.
    assert "No miss was shared by every team" in html


def test_verdict_states_the_frozen_gates_it_applied(tmp_path) -> None:
    from harness.catalyst.report import build_report

    run = _two_team_run(
        tmp_path, team_b_passed=False, gates={"overall": 0.9, "per_scenario": 0.8}
    )
    html = build_report(run).read_text(encoding="utf-8")
    assert "≥90% overall" in html and "≥80% per scenario" in html
    # team-a passed 1/1 (meets both gates); team-b failed its only scenario.
    assert "qualified — writer-only" in html


def test_verdict_calls_a_conformance_broken_team_undecidable(tmp_path) -> None:
    """An invalid measurement is not a loss: the verdict says no decision."""
    from harness.catalyst.report import build_report

    run = _two_team_run(
        tmp_path,
        team_b_passed=False,
        team_b_conformant=False,
        gates={"overall": 0.9, "per_scenario": 0.8},
    )
    html = build_report(run).read_text(encoding="utf-8")
    # team-a still qualifies; team-b's broken measurement is undecided, not lost.
    assert "qualified — writer-only" in html
    assert "no decision for r-checked (invalid measurements)" in html


def test_single_profile_run_keeps_its_headline_and_gets_no_gate_verdict() -> None:
    """The golden fixture is a single-profile run: its abstract renders, the
    old passed/total headline stays, and no cross-team verdict is invented."""
    from harness.catalyst.report import build_report

    html = build_report(FIXTURE).read_text(encoding="utf-8")
    assert "In plain terms" in html
    assert "Against the gates in force" not in html
    results = json.loads((FIXTURE / "results.json").read_text(encoding="utf-8"))
    assert f"{results['passedCount']}/{results['resultCount']}" in html


def test_abstract_reports_relative_performance_and_failure_clusters(tmp_path) -> None:
    """No thresholds in the abstract: how the teams did against each other,
    which questions the misses landed on, and what kind of errors they were."""
    from harness.catalyst.report import build_report

    run = _two_team_run(
        tmp_path, team_b_passed=False, gates={"overall": 0.9, "per_scenario": 0.8}
    )
    html = build_report(run).read_text(encoding="utf-8")
    abstract = html[html.index("In plain terms"): html.index("<h2>Result</h2>")]

    # Relative scores for every team, by short name.
    assert "writer-only 1 of 1" in abstract
    assert "r-checked 0 of 1" in abstract
    # The miss is located (S1, one team only) and characterized from the
    # judge's axes: craft at ceiling, intent dropped.
    assert "S1" in abstract
    assert "misreadings, not broken queries" in abstract
    # Gates appear only in the Result section.
    assert "gates in force" not in abstract
    assert "Against the gates in force at publication" in html
