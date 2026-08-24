from pathlib import Path
import json
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_SOURCE = (ROOT / "scripts" / "validate-dashboard.py").read_text(
    encoding="utf-8"
)


def test_dashboard_shows_single_and_multi_actor_judgments_honestly():
    assert '<section><h2>Judged scores</h2><div id=judges></div></section>' in DASHBOARD_SOURCE
    assert "no judged score yet" in DASHBOARD_SOURCE
    assert "Score from one independent judge" in DASHBOARD_SOURCE
    assert "Combined = each cell averaged across independent judges" in DASHBOARD_SOURCE
    assert "(s.n_actors||0)>=1" in DASHBOARD_SOURCE
    assert "no multi-judge score yet" not in DASHBOARD_SOURCE


def test_dashboard_keeps_flagged_model_output_visible_for_manual_review():
    assert "confidence inversion" not in DASHBOARD_SOURCE
    assert "Removed In-Depth claims" in DASHBOARD_SOURCE
    assert "not part of the final clinical response" in DASHBOARD_SOURCE
    assert "<details open class=reviewdraft>" not in DASHBOARD_SOURCE
    assert "function indepthReviewDraft" not in DASHBOARD_SOURCE
    assert "const draft=(t.review_draft||'').trim()" in DASHBOARD_SOURCE
    assert "renderOriginalAnswer(validation,currentAnswer)" in DASHBOARD_SOURCE
    assert "current answer above remains flagged for review" in DASHBOARD_SOURCE
    assert "Original-answer sources (not final evidence)" in DASHBOARD_SOURCE
    assert '"answer_confidence_display": answer_confidence_display' in DASHBOARD_SOURCE
    assert "const answerConf=t.answer_confidence_display" in DASHBOARD_SOURCE
    assert "<details class=collapse><summary>show '+title.toLowerCase()" not in DASHBOARD_SOURCE


def test_dashboard_renderer_shows_flagged_output_and_citation_only_original():
    esc_line = "const esc=" + DASHBOARD_SOURCE.split("const esc=", 1)[1].split("\n", 1)[0]
    confidence_js = DASHBOARD_SOURCE[
        DASHBOARD_SOURCE.index("const CONF_COLORS=") : DASHBOARD_SOURCE.index(
            "function renderReviewDraft"
        )
    ]
    original_js = DASHBOARD_SOURCE[
        DASHBOARD_SOURCE.index("function renderOriginalAnswer") : DASHBOARD_SOURCE.index(
            "function renderTrace"
        )
    ]
    script = f"""
{esc_line}
{confidence_js}
const renderBlocks=()=>'';
{original_js}
const flagged=confSection(
  'Answer',
  'Flagged model output [1].',
  {{level:'red',label:'Self-check low',note:'Check the date.',note_treatment:'prominent'}},
  {{status:'needs_review',label:'Needs review',tone:'danger'}}
);
const original=renderOriginalAnswer(
  {{status:'edited',originalAnswer:'Flagged model output [1].',originalReferences:[{{index:1}}]}},
  'Flagged model output [1].'
);
process.stdout.write(JSON.stringify({{flagged,original}}));
"""
    rendered = json.loads(subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    ).stdout)

    assert "Check the date." in rendered["flagged"]
    assert "Flagged model output [1]." in rendered["flagged"]
    assert "<details" not in rendered["flagged"]
    assert "show answer" not in rendered["flagged"].lower()
    assert rendered["flagged"].index("Check the date.") < rendered["flagged"].index(
        "Flagged model output [1]."
    )
    assert "Original model answer" in rendered["original"]
    assert "answer or its supporting citations was changed" in rendered["original"]


def _load_dashboard_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_dashboard", ROOT / "scripts" / "validate-dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_catalyst_cell_shows_the_frozen_acceptance_criterion(tmp_path: Path):
    """What the dashboard displays as 'expected' is what the scorer enforces.

    The suite travels with the run, so the cell's expectation block comes
    from the run's own suite.json -- criterion prose, the answer each turn
    deserves, and the independent reference -- not from a chart-QA stub.
    """
    vd = _load_dashboard_module()
    run = tmp_path / "run"
    run.mkdir()
    (run / "suite.json").write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "id": "B2",
                        "comment": "'Poor' is undefined; the frozen answer supplies the rule.",
                        "initialQuestion": "Show patients with poor adherence.",
                        "expectedBaseOutcome": "needs_clarification",
                        "turns": [
                            {
                                "instruction": "Poor means latest adherence != All.",
                                "expectedOutcome": "ready",
                            }
                        ],
                        "successorGoldCheck": {
                            "mode": "row_set",
                            "referenceSql": "SELECT patient_id FROM x",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert vd.run_family(str(run)) == "catalyst"
    expected = vd.catalyst_expectation(str(run), "B2")
    assert expected["baseOutcome"] == "needs_clarification"
    assert "frozen answer" in expected["criterion"]
    assert expected["turns"][0]["expectedOutcome"] == "ready"
    assert expected["goldCheck"]["mode"] == "row_set"
    # An unknown scenario and a chart-QA run both answer with absence.
    assert vd.catalyst_expectation(str(run), "nope") is None
    chart_run = tmp_path / "chart"
    chart_run.mkdir()
    assert vd.run_family(str(chart_run)) == "chartsearchai"
    assert vd.catalyst_expectation(str(chart_run), "B2") is None


def test_the_comparison_grid_has_one_row_per_scenario(tmp_path: Path):
    """(team x scenario) cells collapse to one row per scenario.

    The manifest's cells repeat every scenario once per team; using their ids
    raw as grid rows rendered the suite once per team, mostly empty. Two
    scenarios and three teams here stand in for the real 12x3.
    """
    vd = _load_dashboard_module()
    run = tmp_path / "run"
    run.mkdir()
    cells = [
        {"scenario_id": s, "backend_id": b, "turns": 3}
        for b in ("team-a", "team-b", "team-c")
        for s in ("A1", "A2")
    ]
    events = [
        {"event_type": "run", "scenario_ids": [c["scenario_id"] for c in cells],
         "backend_ids": [c["backend_id"] for c in cells], "cells": cells}
    ]
    (run / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (run / "results.jsonl").write_text("", encoding="utf-8")
    (run / "suite.json").write_text(json.dumps({"scenarios": []}), encoding="utf-8")

    vd._RUN_OVERRIDE = str(run)
    try:
        status = vd.status()
    finally:
        vd._RUN_OVERRIDE = None

    assert status["scenarios"] == ["A1", "A2"]
    assert status["backends"] == ["team-a", "team-b", "team-c"]
    assert len(status["grid"]) == 6


def test_a_failure_is_reduced_to_one_blamed_root_cause(tmp_path: Path):
    """Four cascading red checks become one attributed explanation.

    A rejected writer answer also fails the terminal-status, selection and
    staleness checks; showing all four raw makes every red look like four
    mysteries. The root cause is picked by precedence and said in plain
    words, by the same module the triage gate and comparison page use.
    """
    vd = _load_dashboard_module()
    failed = [
        {"name": "followup_terminal_status", "class": "evaluation",
         "evidence": "failed"},
        {"name": "writer_outcome", "class": "evaluation",
         "evidence": '{"expected": "ready", "observed": "rejected"}'},
        {"name": "exact_selected_output", "class": "evaluation",
         "evidence": "[]"},
    ]

    verdict = vd.blame_failure(failed)

    assert verdict["kind"] == "judged"
    assert verdict["root"]["name"] == "writer_outcome"
    assert "answer" in verdict["root"]["human"].lower()
    assert verdict["consequences"] == 2

    # A check nobody classified cannot be vouched for.
    unknown = vd.blame_failure([{"name": "brand_new_check", "evidence": "?"}])
    assert unknown["kind"] == "invalid"


def _conformance_run(tmp_path: Path):
    """Four cells: a clean pass, a judged failure, a contract failure, and a
    judged failure recorded before the runner stamped classes."""
    run = tmp_path / "run"
    run.mkdir()
    cells = [{"scenario_id": s, "backend_id": "team-a", "turns": 1}
             for s in ("A1", "A2", "A3", "A4")]
    (run / "events.jsonl").write_text(
        json.dumps({"event_type": "run", "cells": cells,
                    "scenario_ids": [c["scenario_id"] for c in cells],
                    "backend_ids": ["team-a"]}) + "\n",
        encoding="utf-8",
    )
    (run / "suite.json").write_text(json.dumps({"scenarios": []}), encoding="utf-8")

    def row(sid, passed, failed):
        return {
            "scenario_id": sid, "backend_id": "team-a", "turn": 1,
            "request": {"question": "q"},
            "response": {"answer": "a", "failedAssertions": failed},
            "metrics": {"http_status": 200, "passed": passed, "answer_chars": 1},
        }

    rows = [
        row("A1", True, []),
        # The model refused where a query was due: an allowed path.
        row("A2", False, [{"name": "base_writer_outcome",
                           "class": "evaluation", "evidence": ""}]),
        # The gateway failed to persist its own echo: unexpected behaviour.
        row("A3", False, [{"name": "writer_model",
                           "class": "conformance", "evidence": ""}]),
        # Recorded before the stamp existed — classified by name.
        row("A4", False, [{"name": "successor_gold_execution_match",
                           "evidence": ""}]),
    ]
    (run / "results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return run


def test_only_unexpected_behaviour_turns_a_cell_red(tmp_path: Path):
    """The grid answers one question: did the system behave as designed?

    A refused query, a rejected revision, a wrong answer — all allowed
    paths, all green. Red is reserved for the contract breaking. How good
    the answers were is the report's job.
    """
    vd = _load_dashboard_module()
    run = _conformance_run(tmp_path)
    vd._RUN_OVERRIDE = str(run)
    try:
        status = vd.status()
    finally:
        vd._RUN_OVERRIDE = None

    by = {g["scenario"]: g["state"] for g in status["grid"]}
    assert by["A1"] == "done"
    assert by["A2"] == "done", "a judged failure is a result, not breakage"
    assert by["A3"] == "err"
    assert by["A4"] == "done", "legacy rows classify by name"

    # The judged tally is reported as a number, never as cell colour.
    assert status["conformant"] == 3
    assert status["unexpected"] == 1
    assert status["judged_passed"] == 1
    assert status["judged_scored"] == 4


def test_the_frozen_snapshot_can_open_every_cell_it_lets_you_click(
    tmp_path: Path,
):
    """A published snapshot is the only interactive surface a reader gets.

    The grid makes every non-pending cell clickable, so the freeze has to
    embed detail for exactly those; anything narrower ships a page whose
    cells open empty.
    """
    vd = _load_dashboard_module()
    run = _conformance_run(tmp_path)
    out = tmp_path / "dashboard.html"
    vd._RUN_OVERRIDE = str(run)
    try:
        status = vd.status()
        vd.freeze(str(out))
    finally:
        vd._RUN_OVERRIDE = None

    page = out.read_text(encoding="utf-8")
    embedded = json.loads(
        page.split("window.__DETAIL__=", 1)[1].split(";\n", 1)[0]
    )
    clickable = {
        f"{g['scenario']}|{g['backend']}"
        for g in status["grid"]
        if g["state"] != "pending"
    }
    assert clickable, "fixture should have clickable cells"
    assert set(embedded) == clickable
    assert all(embedded[k].get("turns") for k in clickable)
