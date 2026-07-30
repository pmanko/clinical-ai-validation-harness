"""Per-section confidence presentation in the validate report (parity with the dashboard).

The med-agent-hub writes a per-turn reasoning trace (answer/in-depth confidence
{level, note}) to a sibling ``artifacts/.../hub-trace/trace.jsonl``; the report
correlates it to a cell by ``level_id == backend_id`` within the cell's
``[started_at, ended_at]`` window and heads each answer section with a confidence
chip and review state per level:

- red    -> show the validator note as a caveat + keep the flagged body visible
- yellow -> show the body + collapse the note behind "show review note"
- green  -> show the body plainly

These assert the rendered ``answer_html`` (pulled from the inert JSON blob the
report embeds), not source strings.
"""

import importlib.util
import json
import re
from pathlib import Path

from harness.validate.report import build_report

_ANSWER = "**Answer**\nRegimen is current [1].\n\n**In Depth**\nStavudine-free per WHO [1]."


def _write_run(run_dir: Path, results, traces=None, judge=None):
    """Write a run two levels under tmp so run_dir.parent.parent/hub-trace is a sibling."""
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({
            "run_id": "r1", "component": "validate", "git_sha": "abc123",
            "dataset_id": "demo", "otel": {"gen_ai.provider.name": "lmstudio"},
            "generated_at": "2026-05-30",
        }),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event_type": "backend_selected", "backend_id": "med-agent-team",
                    "modelName": "med-agent-team"}) + "\n",
        encoding="utf-8",
    )
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    if judge is not None:
        with (run_dir / "judge.jsonl").open("w", encoding="utf-8") as f:
            for j in judge:
                f.write(json.dumps(j) + "\n")
    if traces is not None:
        trace_dir = run_dir.parent.parent / "hub-trace"
        trace_dir.mkdir(parents=True, exist_ok=True)
        # `traces` entries may be dicts (serialized) or raw strings (malformed lines).
        lines = [t if isinstance(t, str) else json.dumps(t) for t in traces]
        (trace_dir / "trace.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _result(answer, backend="med-agent-team", refs=(({"index": 1, "resourceType": "MedicationRequest"}),)):
    return {
        "run_id": "r1", "scenario_id": "s", "backend_id": backend, "turn": 1,
        "started_at": "2026-05-30T10:00:00", "ended_at": "2026-05-30T10:00:30",
        "request": {"question": "q"},
        "response": {"answer": answer, "references": list(refs)},
        "metrics": {"latency_ms": 10, "http_status": 200, "json_valid": True,
                    "citation_count": len(refs), "first_turn": True},
    }


def _trace(answer_conf, indepth_conf, backend="med-agent-team"):
    return {"level_id": backend, "ts": "2026-05-30T10:00:15",
            "answer_confidence": answer_conf, "indepth_confidence": indepth_conf}


def _report_cell(run_dir: Path) -> dict:
    html = build_report(run_dir).read_text(encoding="utf-8")
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    return json.loads(body)["runs"][0]["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]


def _answer_html(run_dir: Path) -> str:
    return _report_cell(run_dir)["answer_html"]


def _dashboard_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "validate-dashboard.py"
    spec = importlib.util.spec_from_file_location("validate_dashboard_for_parity", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_red_answer_section_keeps_body_visible_with_caveat(tmp_path):
    run_dir = tmp_path / "validate" / "run"
    _write_run(
        run_dir, [_result(_ANSWER)],
        traces=[_trace({"level": "red", "note": "claim unsupported by chart"},
                       {"level": "yellow", "note": "partly supported"})],
    )
    ans = _answer_html(run_dir)

    # Answer section: red -> low self-check chip, the note rendered as a caveat, and the
    # flagged body remains visible so a reviewer can inspect it.
    assert "Self-check low" in ans
    assert "<div class='caveat red'>claim unsupported by chart</div>" in ans
    assert "Regimen is current" in ans
    assert "<summary>show answer</summary>" not in ans
    # In-Depth section: yellow -> medium self-check chip, body shown, note collapsed.
    assert "Self-check medium" in ans
    assert "<summary>show review note</summary>" in ans
    assert "<div class='caveat yellow'>partly supported</div>" in ans
    assert "Stavudine-free per WHO" in ans


def test_green_answer_section_renders_body_plainly(tmp_path):
    run_dir = tmp_path / "validate" / "run"
    # No In-Depth header -> only the Answer section is rendered.
    _write_run(
        run_dir, [_result("**Answer**\nRegimen is current [1].")],
        traces=[_trace({"level": "green", "note": ""}, None)],
    )
    ans = _answer_html(run_dir)

    assert "Self-check high" in ans
    assert "Regimen is current" in ans
    # green never caveats or collapses.
    assert "caveat" not in ans
    assert "<details" not in ans


def test_empty_answer_section_is_dropped(tmp_path):
    run_dir = tmp_path / "validate" / "run"
    # Answer body empty (header only), In-Depth has content -> Answer section drops out.
    _write_run(
        run_dir, [_result("**Answer**\n\n**In Depth**\nOnly the in-depth body [1].")],
        traces=[_trace({"level": "green", "note": ""}, {"level": "green", "note": ""})],
    )
    ans = _answer_html(run_dir)

    assert "Only the in-depth body" in ans
    # The empty Answer section produced no body block before the In-Depth one.
    assert ans.count("secbody") == 1


def test_malformed_trace_line_is_tolerated(tmp_path):
    run_dir = tmp_path / "validate" / "run"
    # A garbage line in trace.jsonl must not crash the report; the valid trace still applies.
    _write_run(
        run_dir, [_result(_ANSWER)],
        traces=["", "{ this is not json",
                _trace({"level": "red", "note": "bad"}, {"level": "green", "note": ""})],
    )
    ans = _answer_html(run_dir)
    assert "Self-check low" in ans
    assert "<div class='caveat red'>bad</div>" in ans


def test_no_trace_falls_back_to_plain_answer(tmp_path):
    run_dir = tmp_path / "validate" / "run"
    # No hub-trace at all (direct single-LLM arm / older run) -> plain answer, no chips.
    _write_run(run_dir, [_result(_ANSWER)], traces=None)
    ans = _answer_html(run_dir)
    assert "confidence" not in ans.lower()
    assert "<strong>Answer</strong>" in ans  # still markdown-rendered, just unsectioned


def test_report_and_dashboard_share_flagged_output_semantics(tmp_path):
    run_dir = tmp_path / "validate" / "run"
    result = _result("**Answer**\nFlagged answer [1].")
    result["request"] = {
        "question": "q",
        "session": "session-1",
        "request_id": "turn-1",
    }
    result["response"]["answerValidation"] = {"status": "needs_review"}
    result["response"]["inDepth"] = {
        "status": "needs_review",
        "answer": "",
        "error": "In-Depth was withheld.",
    }
    trace = _trace(
        {"level": "red", "note": "Check the chart date."},
        {"level": "red", "note": "In-Depth was withheld."},
    )
    trace["question"] = "q"
    trace["correlation"] = {"session": "session-1", "request_id": "turn-1"}
    _write_run(run_dir, [result], traces=[trace])

    report_cell = _report_cell(run_dir)
    dashboard = _dashboard_module()
    dashboard._RUN_OVERRIDE = str(run_dir)
    dashboard.TRACE_FILE = run_dir.parent.parent / "hub-trace" / "trace.jsonl"
    dashboard.DATA = tmp_path / "missing-validation-data"
    dashboard_turn = dashboard.detail("s", "med-agent-team")["turns"][0]

    for key in (
        "answer_confidence_display",
        "indepth_confidence_display",
        "answer_validation_display",
        "indepth_validation_display",
    ):
        assert report_cell[key] == dashboard_turn[key]
    assert report_cell["answer_confidence_display"]["show_output"] is True
    assert "Flagged answer [1]." in report_cell["answer_html"]
    assert "show answer" not in report_cell["answer_html"]
    assert "function fmt10(v)" in dashboard.PAGE
    assert "function fmt10(v)" in build_report(run_dir).read_text(encoding="utf-8")


def test_temporal_gate_metadata_reaches_cell_chip_and_summary(tmp_path):
    run_dir = tmp_path / "validate" / "run"
    tr = _trace({"level": "yellow", "note": "patched"}, None)
    tr["temporal_gate"] = {
        "schema_version": "temporal_gate.v1",
        "mode": "enforce",
        "status": "fail",
        "checks": [{"id": "upcoming_date", "status": "fail"}],
        "applied": "patch",
    }
    tr["temporal_facts_summary"] = {"reference_date": "2026-06-20"}
    _write_run(run_dir, [_result("**Answer**\nNo upcoming appointment [1].")], traces=[tr])

    html = build_report(run_dir).read_text(encoding="utf-8")
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    run = json.loads(body)["runs"][0]
    cell = run["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]
    assert cell["temporal_gate"]["mode"] == "enforce"
    assert "temporal gate enforce: fail patch" in cell["chips_html"]
    assert run["summary"][0]["temporal_gate_fail"] == 1
    assert run["summary"][0]["temporal_gate_applied"] == 1


def test_judge_scores_are_loaded_when_present(tmp_path):
    run_dir = tmp_path / "validate" / "run"
    # A judge.jsonl present exercises the loader's read path (vs the absent -> [] branch).
    _write_run(
        run_dir, [_result(_ANSWER)],
        judge=[{"scenario_id": "s", "backend_id": "med-agent-team", "turn": 1,
                "scores": {"accuracy": 8, "completeness": 7, "relevance": 9}}],
    )
    # The loaded scores must reach the blob's judge_rows (the JS heatmap reads them);
    # red-when-broken if _load_judge drops a present file. Keyed on the value, not the
    # word "accuracy", which already appears in the static rubric legend.
    html = build_report(run_dir).read_text(encoding="utf-8")
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    rows = json.loads(body)["runs"][0]["judge_rows"]
    assert rows and rows[0]["scores"]["accuracy"] == 8
