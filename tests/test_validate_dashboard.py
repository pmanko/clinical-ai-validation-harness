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


FIXTURE_ROWS = json.loads(
    (ROOT / "tests" / "fixtures" / "review_presentation_rows.json").read_text(encoding="utf-8")
)


def _run_js(body: str) -> dict:
    """Run the dashboard's section renderers in node on the given views."""
    esc_line = "const esc=" + DASHBOARD_SOURCE.split("const esc=", 1)[1].split("\n", 1)[0]
    tone_lines = DASHBOARD_SOURCE[
        DASHBOARD_SOURCE.index("const TONE_CLS=") : DASHBOARD_SOURCE.index("let LAST_STATUS=")
    ]
    renderers = DASHBOARD_SOURCE[
        DASHBOARD_SOURCE.index("function statusChip") : DASHBOARD_SOURCE.index(
            "function renderTrace"
        )
    ]
    script = f"""
{esc_line}
{tone_lines}
const renderBlocks=()=>'';
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
const indepth=sectionHtml('In-Depth',v.i,v.i.body_html,renderClaims(v.i)+renderDraft(v.i,{{}})+renderRawCheck(v.i));
const answer=sectionHtml('Answer',v.a,'Answer body [21].');
process.stdout.write(JSON.stringify({{indepth,answer}}));
""")

    indepth = rendered["indepth"]
    assert indepth.count("class=\"schip") == 1, "one status chip per section"
    assert "self-check" not in (indepth + rendered["answer"]).lower()
    # The note naming the checks precedes the visible In-Depth body.
    assert indepth.index(turn["indepth_view"]["note"]) < indepth.index("<ul class='md-list'>")
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
