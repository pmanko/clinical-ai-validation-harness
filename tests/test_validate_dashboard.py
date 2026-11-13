from pathlib import Path
import json
import subprocess

import pytest

from evals.validate._test_shell import dashboard_shell_js


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_SOURCE = (ROOT / "harness" / "validate" / "dashboard_server.py").read_text(
    encoding="utf-8"
)


def test_dashboard_shows_single_and_multi_actor_judgments_honestly():
    assert '<section><h2>Judged scores</h2><div id="judges"></div></section>' in DASHBOARD_SOURCE
    shell_js = dashboard_shell_js()
    assert "no judged score yet" in shell_js
    assert "Score from one independent judge" in shell_js
    assert "Combined = each cell averaged across independent judges" in shell_js
    assert "(s.n_actors || 0) >= 1" in shell_js
    assert "no multi-judge score yet" not in shell_js


FIXTURE_ROWS = json.loads(
    (ROOT / "tests" / "fixtures" / "review_presentation_rows.json").read_text(encoding="utf-8")
)


def _run_js(body: str) -> dict:
    """Run the dashboard's section renderers in node on the given views."""
    shell_js = dashboard_shell_js()
    helpers = shell_js[
        shell_js.index("var esc =") : shell_js.index("var KNOB_ORDER =")
    ]
    open_details = shell_js[
        shell_js.index("function restoreOpenDetails(") : shell_js.index("function gridCell(")
    ]
    renderers = shell_js[
        shell_js.index("function resolveSourcesList(") : shell_js.index(
            "function renderTrace"
        )
    ]
    script = f"""
var STATIC_DASHBOARD = null;
var ARM_CARDS = {{}};
var ARM_LABELS = {{}};
var OPEN_DETAILS = new Set();
var armTitle = function(b) {{ return String(b); }};
{helpers}
{open_details}
{renderers}
{body}
"""
    return json.loads(
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout
    )


def _cell_detail(tmp_path: Path, names: list[str]):
    """A chart-answer run of captured rows, served through status() and detail()."""
    vd = _load_dashboard_module()
    run = tmp_path / "run"
    (run / "inputs" / "scenarios").mkdir(parents=True)
    rows = [FIXTURE_ROWS[name] for name in names]
    scenarios = list(dict.fromkeys(r["scenario_id"] for r in rows))
    backends = list(dict.fromkeys(r["backend_id"] for r in rows))
    for sid in scenarios:
        turns = max(r["turn"] for r in rows if r["scenario_id"] == sid)
        (run / "inputs" / "scenarios" / f"{sid}.json").write_text(
            json.dumps({"turns": [{}] * turns}), encoding="utf-8"
        )
    events = [{"event_type": "run", "scenario_ids": scenarios, "backend_ids": backends}]
    events += [
        {"event_type": "backend_selected", "backend_id": b, "label": f"Label for {b}"}
        for b in backends
    ]
    (run / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (run / "results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    vd._RUN_OVERRIDE = str(run)
    return vd


def test_section_renderers_show_one_status_the_note_and_every_claim_verdict(tmp_path: Path):
    vd = _cell_detail(tmp_path, ["checked"])
    try:
        turn = vd.detail("am-weight-trend", "hub-profile-single-12b-checked")["turns"][0]
    finally:
        vd._RUN_OVERRIDE = None
    views = json.dumps({"a": turn["answer_view"], "i": turn["indepth_view"]})
    rendered = _run_js(f"""
const v={views};
const indepth=sectionHtml('In-Depth',v.i,renderMarkdown(v.i.body_text),renderClaims(v.i)+renderDraft(v.i,{{}})+renderRawCheck(v.i));
const answer=sectionHtml('Answer',v.a,'Answer body [21].');
process.stdout.write(JSON.stringify({{indepth,answer}}));
""")

    indepth = rendered["indepth"]
    assert indepth.count("class=\"schip") == 1, "one status chip per section"
    assert "self-check" not in (indepth + rendered["answer"]).lower()
    # The note naming the checks precedes the visible In-Depth body.
    assert indepth.index(turn["indepth_view"]["note"]) < indepth.index("<ul class=\"md-list\">")
    assert indepth.count("<tr") == 1 + len(turn["indepth_view"]["claims"])
    assert indepth.count("t-bad") >= 2
    # The raw check record stays available, collapsed.
    assert "<details class=rawrefs>" in indepth
    assert "draftbox" not in indepth


def test_a_draft_differing_only_in_citation_format_is_not_shown(tmp_path: Path):
    vd = _cell_detail(tmp_path, ["citation_format_draft"])
    try:
        turns = vd.detail("convo-safety-escalation", "hub-profile-single-12b-checked")["turns"]
    finally:
        vd._RUN_OVERRIDE = None
    view = json.dumps(turns[0]["indepth_view"])
    rendered = _run_js(f"process.stdout.write(JSON.stringify({{d:renderDraft({view},{{}})}}));")

    assert turns[0]["indepth_view"]["draft"] is None
    assert rendered["d"] == ""


def test_the_grid_carries_answer_and_in_depth_status_per_cell(tmp_path: Path):
    vd = _cell_detail(tmp_path, ["checked", "answer_only", "bundled"])
    try:
        status = vd.status()
    finally:
        vd._RUN_OVERRIDE = None
    grid = {g["backend"]: g for g in status["grid"]}

    checked = grid["hub-profile-single-12b-checked"]
    assert checked["state"] == "done"
    assert checked["answer"]["status"] == "edited"
    assert checked["indepth"]["status"] == "needs_review"
    assert checked["marked"] == 1
    assert grid["engine-parity-hub-answer-12b"]["indepth"]["status"] == "not_in_profile"
    assert grid["engine-parity-bundled-12b"]["answer"]["status"] == "not_checked"
    assert {entry["status"] for entry in status["status_legend"]} >= {"checked", "needs_review"}
    assert status["finished"] is True


def test_a_hub_arm_carries_the_product_profile_title_from_captured_inputs(tmp_path: Path):
    vd = _cell_detail(tmp_path, ["checked", "bundled"])
    run = Path(vd._RUN_OVERRIDE)
    (run / "inputs" / "backends.json").write_text(json.dumps({
        "hub-profile-single-12b-checked": {"label": "Arm label", "provider": "hub", "modelName": "single-12b-checked"},
        "engine-parity-bundled-12b": {"label": "Bundled", "provider": "bundled", "modelName": "single-12b-checked"},
        "single-12b-checked": {"label": "Checked answer (12B profile)", "kind": "product_profile", "modelName": "single-12b-checked"},
    }), encoding="utf-8")
    try:
        status = vd.status()
    finally:
        vd._RUN_OVERRIDE = None

    assert status["profile_titles"] == {"hub-profile-single-12b-checked": "Checked answer (12B profile)"}
    assert status["arm_cards"]["hub-profile-single-12b-checked"] is None


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

    The grid makes every non-pending cell clickable, so dashboard-data.json has to
    embed detail for exactly those; anything narrower ships a page whose
    cells open empty.
    """
    vd = _load_dashboard_module()
    run = _conformance_run(tmp_path)
    vd._RUN_OVERRIDE = str(run)
    try:
        status = vd.status()
        out = vd.write_dashboard_data(run)
    finally:
        vd._RUN_OVERRIDE = None

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["details"] == {}
    embedded: dict[str, Any] = {}
    for rel in payload["detail_shards"].values():
        embedded.update(json.loads((run / rel).read_text(encoding="utf-8")))
    clickable = {
        f"{g['scenario']}|{g['backend']}"
        for g in status["grid"]
        if g["state"] != "pending"
    }
    assert clickable, "fixture should have clickable cells"
    assert set(embedded) == clickable
    assert all(embedded[k].get("turns") for k in clickable)


def test_a_transport_error_is_red_whatever_the_assertions_say(tmp_path: Path):
    """A 599 is how a dead gateway reaches the feed.

    The row may carry no failing assertion at all — there was no answer to
    check — so the conformance rule alone would call the cell fine. The
    status is decisive.
    """
    vd = _load_dashboard_module()
    run = tmp_path / "run"
    run.mkdir()
    (run / "events.jsonl").write_text(
        json.dumps({"event_type": "run",
                    "cells": [{"scenario_id": "A1", "backend_id": "team-a",
                               "turns": 1}],
                    "scenario_ids": ["A1"], "backend_ids": ["team-a"]}) + "\n",
        encoding="utf-8",
    )
    (run / "suite.json").write_text(json.dumps({"scenarios": []}), encoding="utf-8")
    (run / "results.jsonl").write_text(
        json.dumps({
            "scenario_id": "A1", "backend_id": "team-a", "turn": 1,
            "request": {"question": "q"},
            "response": {"answer": "", "failedAssertions": []},
            "metrics": {"http_status": 599, "passed": False,
                        "answer_chars": 0},
        }) + "\n",
        encoding="utf-8",
    )
    vd._RUN_OVERRIDE = str(run)
    try:
        status = vd.status()
    finally:
        vd._RUN_OVERRIDE = None

    assert status["grid"][0]["state"] == "err"
    assert status["unexpected"] == 1


def test_single_line_sql_is_formatted_for_reading_and_nothing_else_is():
    """Models often emit a query as one long line; the detail view breaks it
    at clause boundaries so a reader can follow it. A query the model
    formatted itself, prose, and keywords inside string literals are left
    exactly as recorded — this is display, never evidence.
    """
    vd = _load_dashboard_module()
    f = vd._format_sql

    flat = ("SELECT a, b FROM t1 JOIN t2 ON t1.id = t2.id "
            "WHERE x = 'keep FROM here' GROUP BY a ORDER BY b LIMIT 5")
    pretty = f(flat)
    assert "\nFROM t1" in pretty
    assert "\n  ON t1.id" in pretty
    assert "\nWHERE x" in pretty
    assert "'keep FROM here'" in pretty, "string literals stay verbatim"
    assert "\nGROUP BY a" in pretty and "\nORDER BY b" in pretty

    already = "SELECT a\nFROM t"
    assert f(already) == already, "the model's own layout is respected"
    prose = "The data records no home address."
    assert f(prose) == prose
    assert f(None) is None


def test_the_checks_against_the_judge_section_appears_once_the_run_is_scored(tmp_path: Path):
    """The dashboard renders check_precision.table_html from judges/check-precision.json
    and the page shows it only when the file exists."""
    import shutil

    from harness.validate.check_precision import score_run, write_scores

    vd = _load_dashboard_module()
    run = tmp_path / "run"
    shutil.copytree(ROOT / "tests" / "fixtures" / "check_precision_run", run)
    vd._RUN_OVERRIDE = str(run)
    try:
        before = vd.status()
        write_scores(run, score_run(run))
        after = vd.status()
    finally:
        vd._RUN_OVERRIDE = None

    assert before["check_precision"] is None
    assert after["check_precision"] is not None
    assert "answer" in after["check_precision"]
    rendered = _run_js(f"""
const d={json.dumps({"check_precision": after["check_precision"]})};
const nodes={{}};
global.document={{
  getElementById:id=>nodes[id]||(nodes[id]={{style:{{}},innerHTML:'',querySelectorAll:()=>[]}}),
  querySelectorAll:()=>[]
}};
renderCheckPrecision({{}});
const hidden=nodes.checksec.style.display;
renderCheckPrecision(d);
const firstHtml=nodes.checkprec.innerHTML;
// Simulate browser quote normalization on innerHTML; re-polling same payload must not reset DOM.
nodes.checkprec.innerHTML='normalized-dom-stays-intact';
renderCheckPrecision(d);
process.stdout.write(JSON.stringify({{hidden,shown:nodes.checksec.style.display,html:firstHtml,afterPoll:nodes.checkprec.innerHTML}}));
""")
    assert rendered["hidden"] == "none" and rendered["shown"] == ""
    assert "Citation support" in rendered["html"]
    assert "Precision: of the items a check marked" in rendered["html"]
    assert rendered["afterPoll"] == "normalized-dom-stays-intact"


def test_a_withdrawn_confidence_level_lists_findings_instead_of_a_chip():
    view = {
        "status": "needs_review", "label": "Needs review", "tone": "danger", "confidence": None,
        "note": "Citation support: [311] states CD4 341, not 72.",
        "findings": [
            {"check": "citation", "name": "Citation support", "where": "answer", "says": "[311] states CD4 341, not 72", "tone": "neutral"},
            {"check": "citation", "name": "Citation support", "where": "answer", "says": "[21] does not hold 52 kg", "tone": "neutral"},
        ],
    }
    rendered = _run_js(f"""
const v={json.dumps(view)};
process.stdout.write(JSON.stringify({{h:sectionHtml('Answer',v,'body')}}));
""")
    html = rendered["h"]
    assert html.count("class=\"schip") == 1 and "sconf" not in html
    assert html.count("<li") == 2 and "does not hold 52 kg" in html
    assert html.index("<ul class=findings>") < html.index("<div class=ans>")


def test_dashboard_judge_scores_display_canonical_median_and_label_combined_mean_separately(
    tmp_path: Path,
):
    import sys

    vd = _load_dashboard_module()
    run = tmp_path / "dashboard-median"
    run.mkdir()
    row = {
        "scenario_id": "s1", "backend_id": "b1", "accuracy": 8, "completeness": 8,
        "relevance": 8, "harm": False, "abstention_outcome": "n-a",
        "citation_groundedness": "supported", "note": "fine",
    }
    (run / "events.jsonl").write_text(
        json.dumps({"event_type": "run", "backend_ids": ["b1"], "scenario_ids": ["s1"]}) + "\n",
        encoding="utf-8",
    )
    for i, score in enumerate((10, 8, 2), 1):
        d = run / "judges" / f"p{i}"
        d.mkdir(parents=True)
        (d / "judge.jsonl").write_text(
            json.dumps({**row, "accuracy": score, "completeness": score, "relevance": score}) + "\n",
            encoding="utf-8",
        )
        (d / "manifest.json").write_text(
            json.dumps({"model": "model", "pass_index": i}), encoding="utf-8"
        )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run),
         "--actor", "p1", "--actor", "p2", "--actor", "p3"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    )
    vd._RUN_OVERRIDE = str(run)
    try:
        status = vd.status()
    finally:
        vd._RUN_OVERRIDE = None

    assert status["judge"][0]["benchmark_score"] == 80.0
    assert status["judge_combined"][0]["benchmark_score"] == 66.7

    shell_js = dashboard_shell_js()
    fn = shell_js.split("function renderJudgeScores(d) {", 1)[1].split("var OPEN_DETAILS =", 1)[0]
    js = (
        "const esc=s=>String(s), fmt10=s=>Number(s).toFixed(1), armTitle=s=>s;\n"
        "function renderJudgeScores(d) {" + fn + "\n"
        "process.stdout.write(renderJudgeScores(" + json.dumps(status) + "));\n"
    )
    rendered = subprocess.run(
        ["node", "-e", js], check=True, capture_output=True, text=True
    ).stdout

    assert "<span class=score>80.0</span>" in rendered
    assert "<span class=score>66.7</span>" not in rendered
    assert "<th>mean across actors</th>" in rendered
    assert "<td>66.7</td>" in rendered


def test_withheld_response_indepth_is_not_repopulated_from_trace_in_depth_claims(tmp_path: Path):
    from harness.validate.report import build_report
    import re

    vd = _load_dashboard_module()
    run = tmp_path / "withheld-indepth"
    (run / "inputs" / "scenarios").mkdir(parents=True)
    (run / "inputs" / "scenarios" / "s1.json").write_text(
        json.dumps({"id": "s1", "turns": [{"n": 1, "question": "q1"}]}), encoding="utf-8"
    )
    (run / "run_manifest.json").write_text(
        json.dumps({
            "run_id": "r1",
            "component": "validate",
            "git_sha": "abc123",
            "dataset_id": "demo",
            "otel": {"gen_ai.provider.name": "lmstudio"},
            "generated_at": "2026-05-30",
        }),
        encoding="utf-8",
    )
    (run / "events.jsonl").write_text(
        json.dumps({"event_type": "run", "scenario_ids": ["s1"], "backend_ids": ["b1"]}) + "\n"
        + json.dumps({"event_type": "backend_selected", "backend_id": "b1", "modelName": "b1"}) + "\n",
        encoding="utf-8",
    )
    (run / "run_meta.json").write_text(
        json.dumps({"backends": {"b1": {"modelName": "b1"}}}), encoding="utf-8"
    )
    row = {
        "run_id": "r1",
        "scenario_id": "s1",
        "backend_id": "b1",
        "turn": 1,
        "started_at": "2026-05-30T10:00:00",
        "ended_at": "2026-05-30T10:00:30",
        "request": {"question": "q1", "session": "s-1", "request_id": "req-1"},
        "response": {
            "answer": "Delivered answer [1].",
            "references": [{"index": 1, "resourceType": "obs", "resourceUuid": "u1"}],
            "inDepth": {
                "status": "needs_review",
                "answer": "",
                "reviewDraft": "- Withheld claim [99].",
                "error": "In-Depth was withheld.",
                "validation": {"status": "needs_review", "claims": ["Withheld claim [99]."]},
            },
        },
        "metrics": {"http_status": 200, "latency_ms": 100, "answer_chars": 20, "citation_count": 1},
    }
    trace = {
        "level_id": "b1",
        "ts": "2026-05-30T10:00:15",
        "question": "q1",
        "correlation": {"session": "s-1", "request_id": "req-1"},
        "in_depth_claims": {
            "text": "- Withheld claim [99].",
            "status": "needs_review",
            "validation": {"status": "needs_review", "claims": ["Withheld claim [99]."]},
        },
    }
    (run / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (run / "trace.jsonl").write_text(json.dumps(trace) + "\n", encoding="utf-8")

    vd._RUN_OVERRIDE = str(run)
    try:
        dash_turn = vd.detail("s1", "b1")["turns"][0]
    finally:
        vd._RUN_OVERRIDE = None

    report_cell = json.loads(build_report(run).read_text(encoding="utf-8"))["runs"][0]["scenarios"][0]["turns"][0]["cells"]["b1"]

    assert dash_turn["indepth_view"]["body_text"] == ""
    assert dash_turn["indepth_view"]["draft"]["kind"] == "withheld"
    assert dash_turn["indepth_view"] == report_cell["indepth_view"]


def test_historical_trace_indepth_dict_is_normalized_across_dashboard_and_report_and_grid_counts_flagged(tmp_path: Path):
    from harness.validate.report import build_report
    from harness.validate.review_presentation import SECTION_STATUS, row_review_summary, status_legend
    import re

    assert {item["status"] for item in status_legend()} == set(SECTION_STATUS)
    summary = row_review_summary({
        "response": {
            "answer": "Ans",
            "inDepth": {
                "answer": "- Claim 1\n- Claim 2",
                "validation": {"status": "needs_review", "flagged": [2], "marked": [1]},
            },
        }
    })
    assert summary["marked"] == 2

    vd = _load_dashboard_module()
    run = tmp_path / "historical-trace-indepth"
    (run / "inputs" / "scenarios").mkdir(parents=True)
    (run / "inputs" / "scenarios" / "s1.json").write_text(
        json.dumps({"id": "s1", "turns": [{"n": 1, "question": "q1"}]}), encoding="utf-8"
    )
    (run / "run_manifest.json").write_text(
        json.dumps({
            "run_id": "r-hist",
            "component": "validate",
            "git_sha": "abc123",
            "dataset_id": "demo",
            "otel": {"gen_ai.provider.name": "lmstudio"},
            "generated_at": "2026-05-30",
        }),
        encoding="utf-8",
    )
    (run / "events.jsonl").write_text(
        json.dumps({"event_type": "run", "scenario_ids": ["s1"], "backend_ids": ["b1"]}) + "\n"
        + json.dumps({"event_type": "backend_selected", "backend_id": "b1", "modelName": "b1"}) + "\n",
        encoding="utf-8",
    )
    (run / "run_meta.json").write_text(
        json.dumps({"backends": {"b1": {"modelName": "b1"}}}), encoding="utf-8"
    )
    row = {
        "run_id": "r-hist",
        "scenario_id": "s1",
        "backend_id": "b1",
        "turn": 1,
        "started_at": "2026-05-30T10:00:00",
        "ended_at": "2026-05-30T10:00:30",
        "request": {"question": "q1", "session": "s-1", "request_id": "req-1"},
        "response": {
            "answer": "Delivered answer [1].",
            "references": [{"index": 1, "resourceType": "obs", "resourceUuid": "u1"}],
        },
        "metrics": {"http_status": 200, "latency_ms": 100, "answer_chars": 20, "citation_count": 1},
    }
    trace = {
        "level_id": "b1",
        "ts": "2026-05-30T10:00:15",
        "question": "q1",
        "correlation": {"session": "s-1", "request_id": "req-1"},
        "in_depth_claims": {
            "text": "- Historical trace claim [1].",
            "status": "checked",
            "validation": {"status": "checked", "claims": ["Historical trace claim [1]."]},
        },
    }
    (run / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (run / "trace.jsonl").write_text(json.dumps(trace) + "\n", encoding="utf-8")

    vd._RUN_OVERRIDE = str(run)
    try:
        dash_turn = vd.detail("s1", "b1")["turns"][0]
    finally:
        vd._RUN_OVERRIDE = None

    report_cell = json.loads(build_report(run).read_text(encoding="utf-8"))["runs"][0]["scenarios"][0]["turns"][0]["cells"]["b1"]

    assert "Historical trace claim [1]." in dash_turn["indepth_view"]["body_text"]
    assert "<li>text</li>" not in dash_turn["indepth_view"]["body_text"]
    assert dash_turn["indepth_view"] == report_cell["indepth_view"]


def test_validate_dashboard_http_routes_with_and_without_viewer_assets(
    tmp_path: Path, monkeypatch
) -> None:
    import http.client
    import threading

    vd = _load_dashboard_module()
    run = tmp_path / "run"
    run.mkdir()
    (run / "results.jsonl").write_text(
        json.dumps(
            {
                "scenario_id": "s1",
                "backend_id": "b1",
                "turn": 1,
                "request": {"question": "q1"},
                "response": {"answer": "ok", "references": []},
                "metrics": {"http_status": 200, "latency_ms": 50},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    vd._RUN_OVERRIDE = str(run)
    srv = vd._Server(("127.0.0.1", 0), vd.H)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        # 1) Standalone mode (no umbrella assets): `/` serves diagnostic HTML and `/api/status` works.
        monkeypatch.setenv("OPENCLINAI_DISABLE_UMBRELLA_ASSETS", "1")
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        assert resp.status == 200
        assert "OPENCLINAI_ASSETS_DIR" in resp.read().decode("utf-8")

        conn.request("GET", "/assets/dashboard-shell.js")
        resp_missing = conn.getresponse()
        resp_missing.read()
        assert resp_missing.status == 404

        conn.request("GET", "/api/status")
        resp_api = conn.getresponse()
        assert resp_api.status == 200
        assert json.loads(resp_api.read())["done"] == 1

        conn.request("GET", "/api/detail?scenario=s1&backend=b1")
        resp_det = conn.getresponse()
        assert resp_det.status == 200
        assert json.loads(resp_det.read())["turns"][0]["answer"] == "ok"

        # 2) Explicit OPENCLINAI_ASSETS_DIR: `/` serves LIVE_SHELL_HTML and `/assets/*` serves files.
        fake_assets = tmp_path / "assets"
        fake_assets.mkdir()
        (fake_assets / "dashboard-shell.css").write_text("body{}", encoding="utf-8")
        (fake_assets / "dashboard-shell.js").write_text("console.log(1);", encoding="utf-8")
        monkeypatch.delenv("OPENCLINAI_DISABLE_UMBRELLA_ASSETS", raising=False)
        monkeypatch.setenv("OPENCLINAI_ASSETS_DIR", str(fake_assets))

        conn.request("GET", "/")
        resp_shell = conn.getresponse()
        assert resp_shell.status == 200
        html = resp_shell.read().decode("utf-8")
        assert 'id="theme-toggle"' in html

        conn.request("GET", "/assets/dashboard-shell.js")
        resp_js = conn.getresponse()
        assert resp_js.status == 200
        assert resp_js.read().decode("utf-8") == "console.log(1);"

        # 3) POST /api/watch registers extra worktree artifacts dirs; invalid JSON & unknown paths handled.
        wt_artifacts = tmp_path / "wt_artifacts"
        wt_run = wt_artifacts / "wahs_stage4" / "run-watch-1"
        wt_run.mkdir(parents=True)
        (wt_run / "results.jsonl").write_text(
            json.dumps({"scenario_id": "s1", "backend_id": "b1", "turn": 1}) + "\n",
            encoding="utf-8",
        )
        watch_body = json.dumps({"artifacts_dir": str(wt_artifacts)}).encode("utf-8")
        conn.request(
            "POST",
            "/api/watch",
            body=watch_body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(watch_body))},
        )
        resp_watch = conn.getresponse()
        assert resp_watch.status == 200
        watch_json = json.loads(resp_watch.read())
        assert watch_json["ok"] is True
        assert str(wt_artifacts) in vd._WATCH_ARTIFACTS_DIRS

        # 3b) POST /api/watch with external run_dir/output_dir clears stale _RUN_OVERRIDE and tracks new run.
        ext_runs = tmp_path / "external_runs"
        ext_run = ext_runs / "run-ext-99"
        ext_run.mkdir(parents=True)
        (ext_run / "events.jsonl").write_text(
            json.dumps({"event_type": "run", "run_id": "run-ext-99"}) + "\n",
            encoding="utf-8",
        )
        watch_ext = json.dumps(
            {"run_dir": str(ext_run), "output_dir": str(ext_runs)}
        ).encode("utf-8")
        conn.request(
            "POST",
            "/api/watch",
            body=watch_ext,
            headers={"Content-Type": "application/json", "Content-Length": str(len(watch_ext))},
        )
        resp_ext = conn.getresponse()
        assert resp_ext.status == 200
        resp_ext_json = json.loads(resp_ext.read())
        assert resp_ext_json["ok"] is True
        assert resp_ext_json["active_run"] == str(ext_run)
        assert vd._RUN_OVERRIDE is None
        assert str(ext_run) in vd._WATCH_RUN_DIRS
        assert str(ext_runs) in vd._WATCH_OUTPUT_DIRS

        bad_body = b"{invalid-json"
        conn.request(
            "POST",
            "/api/watch",
            body=bad_body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(bad_body))},
        )
        resp_bad = conn.getresponse()
        resp_bad.read()
        assert resp_bad.status == 200

        conn.request("POST", "/api/unknown", body=b"{}", headers={"Content-Length": "2"})
        resp_404 = conn.getresponse()
        resp_404.read()
        assert resp_404.status == 404
        conn.close()

        # Verify _WATCH_ARTIFACTS_DIRS/_WATCH_RUN_DIRS discovery and _assets_dir() candidate probing.
        vd._RUN_OVERRIDE = None
        monkeypatch.setattr(vd, "ROOT", tmp_path / "isolated_root")
        monkeypatch.delenv("DASH_RUN", raising=False)
        assert vd.newest_run() == str(ext_run)

        monkeypatch.delenv("OPENCLINAI_ASSETS_DIR", raising=False)
        assert vd._assets_dir() == (tmp_path / "isolated_root").parent.parent / "reports" / "assets"
        cand_assets = (tmp_path / "isolated_root").parent / "openclinai.org" / "reports" / "assets"
        cand_assets.mkdir(parents=True)
        (cand_assets / "dashboard-shell.css").write_text("body{}", encoding="utf-8")
        assert vd._assets_dir() == cand_assets
    finally:
        vd._RUN_OVERRIDE = None
        vd._WATCH_ARTIFACTS_DIRS.clear()
        vd._WATCH_OUTPUT_DIRS.clear()
        vd._WATCH_RUN_DIRS.clear()
        srv.shutdown()
        srv.server_close()


def test_wahs_run_discovery_and_ensure_live_dashboard(
    tmp_path: Path, monkeypatch
) -> None:
    import importlib.util
    import os
    import signal
    import socket
    import subprocess
    import urllib.request

    from harness.validate.live_dashboard import (
        _register_watch,
        _status_payload,
        ensure_live_dashboard,
    )

    # Default under pytest without force/HARNESS_FORCE_DASHBOARD is a no-op.
    monkeypatch.delenv("HARNESS_FORCE_DASHBOARD", raising=False)
    assert ensure_live_dashboard(project_root=tmp_path) is None
    with pytest.raises(RuntimeError):
        _register_watch(9, artifacts_dir=tmp_path, timeout=0.2)

    wahs_run = tmp_path / "artifacts" / "wahs_stage4" / "run-123"
    wahs_run.mkdir(parents=True)
    (wahs_run / "results.jsonl").write_text(
        json.dumps(
            {
                "scenario_id": "s_wahs",
                "backend_id": "wahs-engine-kb:gemma-e4b@4k",
                "turn": 1,
                "request": {"question": "q"},
                "response": {"answer": "ok", "references": []},
                "metrics": {"http_status": 200, "latency_ms": 12},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    vd = _load_dashboard_module()
    vd._RUN_OVERRIDE = None
    monkeypatch.delenv("DASH_RUN", raising=False)
    monkeypatch.setattr(vd, "ROOT", tmp_path)
    assert vd.newest_run() == str(wahs_run)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    monkeypatch.setenv("HARNESS_FORCE_DASHBOARD", "1")
    monkeypatch.setenv("DASH_PORT", str(free_port))
    # HARNESS_NO_DASHBOARD escape hatch must be ignored (still fail-closed).
    monkeypatch.setenv("HARNESS_NO_DASHBOARD", "1")

    # Missing dashboard module raises RuntimeError (fail-closed).
    with monkeypatch.context() as mp:
        mp.setattr(importlib.util, "find_spec", lambda _name: None)
        with pytest.raises(RuntimeError, match="not found"):
            ensure_live_dashboard(project_root=tmp_path / "missing_mod", port=free_port)

    # Wheel install root without scripts/ succeeds using packaged harness.validate.dashboard_server.
    wheel_root = tmp_path / "wheel_root_no_scripts"
    wheel_root.mkdir()

    # Popen OSError raises RuntimeError (fail-closed).
    def _boom(*_a, **_kw):
        raise OSError("spawn failed")

    with monkeypatch.context() as mp:
        mp.setattr(subprocess, "Popen", _boom)
        with pytest.raises(RuntimeError, match="Failed to launch live validation dashboard"):
            ensure_live_dashboard(project_root=wheel_root, port=free_port)

    # Mismatched active run (e.g. pre-existing server pinned to DASH_RUN=other_run) fails closed.
    wrong_run = tmp_path / "wrong_run"
    wrong_run.mkdir()
    with monkeypatch.context() as mp:
        mp.setattr("harness.validate.live_dashboard._status_alive", lambda *_a, **_kw: True)
        mp.setattr("harness.validate.live_dashboard._register_watch", lambda *_a, **_kw: {"ok": True})
        mp.setattr("harness.validate.live_dashboard._status_payload", lambda *_a, **_kw: {"run": "other_pinned_run"})
        with pytest.raises(RuntimeError, match="other_pinned_run"):
            ensure_live_dashboard(project_root=wheel_root, run_dir=wrong_run, port=free_port)

    try:
        url = ensure_live_dashboard(
            project_root=wheel_root,
            run_dir=wahs_run,
            port=free_port,
        )
        assert url == f"http://localhost:{free_port}"
        # Packaged server handles /api/status?run=<name>, /api/detail?run=<name>, and root HTML.
        st = _status_payload(free_port, run=wahs_run.name)
        assert st is not None and st["run"] == wahs_run.name
        with urllib.request.urlopen(
            f"http://127.0.0.1:{free_port}/api/detail?scenario=s_wahs&backend=wahs-engine-kb:gemma-e4b@4k&run={wahs_run.name}",
            timeout=2.0,
        ) as resp:
            assert resp.status == 200
        with urllib.request.urlopen(f"http://127.0.0.1:{free_port}/", timeout=2.0) as resp:
            assert resp.status == 200
        # Second call hits already-alive branch and notifies /api/watch for secondary worktree.
        wt2 = tmp_path / "wt2"
        (wt2 / "artifacts").mkdir(parents=True)
        url2 = ensure_live_dashboard(project_root=wt2, run_dir=wahs_run, port=free_port)
        assert url2 == f"http://localhost:{free_port}"
    finally:
        pid_file = wheel_root / "artifacts" / "validate-dashboard" / "dashboard.pid"
        if pid_file.is_file():
            try:
                os.kill(int(pid_file.read_text().strip()), signal.SIGTERM)
            except OSError:
                pass

    # resolve_run rejects mismatched DASH_RUN pin and mismatched _RUN_OVERRIDE.
    other_run = tmp_path / "artifacts" / "wahs_stage4" / "run-other"
    other_run.mkdir(parents=True)
    with monkeypatch.context() as mp:
        mp.setenv("DASH_RUN", str(other_run))
        assert vd.resolve_run(wahs_run.name) is None
        assert vd.resolve_run(other_run.name) == str(other_run)
    with monkeypatch.context() as mp:
        mp.setattr(vd, "_RUN_OVERRIDE", str(other_run))
        assert vd.resolve_run(wahs_run.name) is None
        assert vd.resolve_run(other_run.name) == str(other_run)


def test_packaged_dashboard_server_module_and_cli_shim(tmp_path: Path, monkeypatch) -> None:
    import os
    import signal
    import socket
    import subprocess
    import sys

    from harness.validate import dashboard_server as ds
    from harness.validate import live_dashboard as ld

    # Exercise live_dashboard helpers (_tail_log, HTTP non-200, _register_watch errors, early-exit poll).
    assert "no dashboard.log" in ld._tail_log(tmp_path / "missing.log")
    empty_log = tmp_path / "empty.log"
    empty_log.write_text("", encoding="utf-8")
    assert "empty" in ld._tail_log(empty_log)
    assert ld._status_payload(9, timeout=0.1) is None

    class _MockResp:
        def __init__(self, status: int, body: bytes):
            self.status = status
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    with monkeypatch.context() as mp:
        mp.setattr(ld.urllib.request, "urlopen", lambda *_a, **_kw: _MockResp(500, b"{}"))
        assert ld._status_payload(8099) is None
        with pytest.raises(RuntimeError, match="HTTP 500"):
            ld._register_watch(8099, artifacts_dir=tmp_path)
        mp.setattr(ld.urllib.request, "urlopen", lambda *_a, **_kw: _MockResp(200, b"{bad"))
        with pytest.raises(RuntimeError, match="invalid JSON"):
            ld._register_watch(8099, artifacts_dir=tmp_path)
        mp.setattr(ld.urllib.request, "urlopen", lambda *_a, **_kw: _MockResp(200, b'{"ok":false}'))
        with pytest.raises(RuntimeError, match="rejected"):
            ld._register_watch(8099, artifacts_dir=tmp_path)

    with monkeypatch.context() as mp:
        mp.setattr("harness.validate.live_dashboard._status_alive", lambda *_a, **_kw: True)
        mp.setattr("harness.validate.live_dashboard._register_watch", lambda *_a, **_kw: {"ok": True})
        mp.setattr("harness.validate.live_dashboard._status_payload", lambda *_a, **_kw: {"run": None})
        assert ld.ensure_live_dashboard(project_root=tmp_path / "nonexistent_wheel_root", port=8099, force=True) == "http://localhost:8099"

    # Exercise harness.validate.dashboard_server directly (resolve_run, status, detail, main).
    run_dir = tmp_path / "artifacts" / "validate" / "run-pkg"
    run_dir.mkdir(parents=True)
    (run_dir / "results.jsonl").write_text(
        json.dumps(
            {
                "scenario_id": "s1",
                "backend_id": "b1",
                "turn": 1,
                "request": {"question": "q"},
                "response": {"answer": "ok", "references": []},
                "metrics": {"http_status": 200, "latency_ms": 10},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as mp:
        mp.setattr(ds, "ROOT", tmp_path)
        mp.setattr(ds, "_RUN_OVERRIDE", None)
        mp.delenv("DASH_RUN", raising=False)
        assert ds.newest_run() == str(run_dir)
        assert ds.resolve_run(run_dir.name) == str(run_dir)
        assert ds.status(run_dir.name)["run"] == run_dir.name
        assert ds.detail("s1", "b1", run_dir.name)

    with monkeypatch.context() as mp:
        mp.setattr(ld, "ensure_live_dashboard", lambda *_a, **_kw: "http://localhost:8099")
        assert ds.main(["--ensure"]) == 0
        mp.setattr(ld, "ensure_live_dashboard", lambda *_a, **_kw: None)
        assert ds.main(["--ensure"]) == 1

    seen_serve: list[str | None] = []
    with monkeypatch.context() as mp:
        mp.setattr(ds, "serve_dashboard", lambda: seen_serve.append(ds._RUN_OVERRIDE))
        assert ds.main(["--run", str(run_dir)]) == 0
        assert seen_serve == [str(run_dir)]

    # Exercise _git_common_repo_root worktree detection & _assets_dir candidate lookup.
    wt_root = tmp_path / "wt_git"
    wt_root.mkdir()
    (wt_root / ".git").write_text("gitdir: ../repo/.git/worktrees/wt1\n", encoding="utf-8")
    assert ds._git_common_repo_root(wt_root) == (tmp_path / "repo").resolve()
    (wt_root / ".git").write_text("gitdir: ../plain_repo/.git\n", encoding="utf-8")
    assert ds._git_common_repo_root(wt_root) == (tmp_path / "plain_repo").resolve()
    with monkeypatch.context() as mp:
        mp.setattr(ds, "ROOT", wt_root)
        mp.delenv("OPENCLINAI_DISABLE_UMBRELLA_ASSETS", raising=False)
        mp.delenv("OPENCLINAI_ASSETS_DIR", raising=False)
        _ = ds._assets_dir()

    # Exercise serve_dashboard() normal start + bind-failure SystemExit without keeping real sockets open.
    closed: list[str] = []

    class _OkSrv:
        def __init__(self, addr, _h):
            self.addr = addr

        def serve_forever(self):
            return None

        def server_close(self):
            closed.append(self.addr[0])

    with monkeypatch.context() as mp:
        mp.setattr(ds, "_Server", _OkSrv)
        mp.setattr(ds, "_ServerV6", _OkSrv)
        ds.serve_dashboard()
        assert closed == ["127.0.0.1", "::1"]

    class _FailSrv:
        def __init__(self, *_a):
            raise OSError("port busy")

    with monkeypatch.context() as mp:
        mp.setattr(ds, "_Server", _FailSrv)
        mp.setattr(ds, "_ServerV6", _FailSrv)
        with pytest.raises(SystemExit, match="could not bind dashboard"):
            ds.serve_dashboard()

    # Exercise live_dashboard wheel fallback (missing project_root) & bind timeout failure.
    alive_seq = iter([False, True])

    class _FakeProc:
        pid = 12345

        def poll(self):
            return None

    with monkeypatch.context() as mp:
        mp.setattr(ld, "_status_alive", lambda *_a, **_kw: next(alive_seq, True))
        mp.setattr(ld.subprocess, "Popen", lambda *_a, **_kw: _FakeProc())
        mp.setattr(ld, "_register_watch", lambda *_a, **_kw: {"ok": True})
        out_wheel = tmp_path / "wheel_out"
        out_wheel.mkdir()
        assert (
            ld.ensure_live_dashboard(
                project_root=tmp_path / "missing_wheel_root",
                output_dir=out_wheel,
                port=8099,
                force=True,
            )
            == "http://localhost:8099"
        )

    class _EarlyExitProc:
        pid = 12346

        def poll(self):
            return 0

    alive_early = iter([False, True])
    with monkeypatch.context() as mp:
        mp.setattr(ld, "_status_alive", lambda *_a, **_kw: next(alive_early, True))
        mp.setattr(ld.subprocess, "Popen", lambda *_a, **_kw: _EarlyExitProc())
        mp.setattr(ld, "_register_watch", lambda *_a, **_kw: {"ok": True})
        assert (
            ld.ensure_live_dashboard(
                project_root=tmp_path / "missing_wheel_root",
                output_dir=tmp_path / "wheel_out",
                port=8099,
                force=True,
            )
            == "http://localhost:8099"
        )

    mono_seq = iter([0.0, 0.0, 9.0])
    with monkeypatch.context() as mp:
        mp.setattr(ld, "_status_alive", lambda *_a, **_kw: False)
        mp.setattr(ld.subprocess, "Popen", lambda *_a, **_kw: _FakeProc())
        mp.setattr(ld.time, "monotonic", lambda: next(mono_seq, 9.0))
        with pytest.raises(RuntimeError, match="failed to bind/respond"):
            ld.ensure_live_dashboard(
                project_root=tmp_path / "missing_wheel_root",
                output_dir=tmp_path / "wheel_out",
                port=8099,
                force=True,
            )

    # Exercise scripts/validate-dashboard.py __main__ CLI shim.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        shim_port = s.getsockname()[1]
    env = dict(os.environ)
    env["DASH_PORT"] = str(shim_port)
    env["OPENCLINAI_DASHBOARD_ROOT"] = str(tmp_path)
    env["HARNESS_FORCE_DASHBOARD"] = "1"
    env.pop("PYTEST_CURRENT_TEST", None)
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate-dashboard.py"), "--ensure"],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
    finally:
        pid_file = tmp_path / "artifacts" / "validate-dashboard" / "dashboard.pid"
        if pid_file.is_file():
            try:
                os.kill(int(pid_file.read_text().strip()), signal.SIGTERM)
            except OSError:
                pass


def test_direct_python_runner_outside_artifacts_enforces_live_dashboard(
    tmp_path: Path, monkeypatch
) -> None:
    import os
    import signal
    import socket
    import subprocess
    import urllib.request

    from harness.wahs.evaluator import run_wahs_suite

    cases_path = tmp_path / "wahs_cases.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "wahs_direct_1",
                "patient_id": "p1",
                "use_case": "use_case_b1_summary",
                "prompt": "Summarize active medications.",
                "sharing_posture": "patient_self",
                "target_token_budgets": [4096],
                "expected_target_uuids": ["uuid-med-1"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class _StubClient:
        def evaluate_case(self, case, *, budget_tokens, **_kw):
            return {
                "answer": "Active medication: Atorvastatin 20 mg [1].",
                "actual_tokens": 120,
                "references": [
                    {"index": 1, "resourceUuid": "uuid-med-1", "resourceType": "MedicationRequest"}
                ],
                "metrics": {"http_status": 200, "latency_ms": 15},
            }

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    external_runs = tmp_path / "external_runs"
    monkeypatch.setenv("HARNESS_FORCE_DASHBOARD", "1")
    monkeypatch.setenv("DASH_PORT", str(free_port))
    monkeypatch.setenv("OPENCLINAI_DISABLE_UMBRELLA_ASSETS", "1")

    pid_file = ROOT / "artifacts" / "validate-dashboard" / "dashboard.pid"
    try:
        res = run_wahs_suite(
            cases_path,
            client=_StubClient(),
            output_dir=external_runs,
            budgets=[4096],
            profiles=["wahs-engine-kb:stub@4k"],
        )
        with urllib.request.urlopen(f"http://127.0.0.1:{free_port}/api/status", timeout=2.0) as resp:
            assert resp.status == 200
            status_json = json.loads(resp.read().decode("utf-8"))
        assert status_json["run"] == res.run_id
        assert status_json["done"] == 1
    finally:
        if pid_file.is_file():
            try:
                os.kill(int(pid_file.read_text().strip()), signal.SIGTERM)
            except OSError:
                pass
            pid_file.unlink(missing_ok=True)
        log_file = ROOT / "artifacts" / "validate-dashboard" / "dashboard.log"
        log_file.unlink(missing_ok=True)

    # Confirm fail-closed behavior if direct Python runner cannot start the dashboard.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
        s2.bind(("127.0.0.1", 0))
        dead_port = s2.getsockname()[1]
    monkeypatch.setenv("DASH_PORT", str(dead_port))

    def _fail_popen(*_a, **_kw):
        raise OSError("cannot launch dashboard")

    with monkeypatch.context() as mp:
        mp.setattr(subprocess, "Popen", _fail_popen)
        with pytest.raises(RuntimeError, match="Failed to launch live validation dashboard"):
            run_wahs_suite(
                cases_path,
                client=_StubClient(),
                output_dir=external_runs,
                budgets=[4096],
                profiles=["wahs-engine-kb:stub@4k"],
            )



