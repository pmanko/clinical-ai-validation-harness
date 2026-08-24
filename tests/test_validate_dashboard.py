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
    """(team x scenario) cells collapse to a 12-row, 3-column matrix.

    The manifest's cells repeat every scenario once per team; using their ids
    raw as grid rows rendered the suite three times over, two thirds empty.
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
