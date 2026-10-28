"""Scoring the product's checks against the judge, on a trimmed run built from
5ac27952 (tests/fixtures/check_precision_run; the per-point verdicts in its judge.jsonl
are hand-assigned test data, see its README.json)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from harness.validate import report
from harness.validate.check_precision import (
    answer_marks,
    indepth_point_marks,
    judged_answer_faults,
    load_scores,
    point_verdicts,
    score_run,
    table_html,
    table_text,
    write_scores,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "check_precision_run"
CELLS = json.loads((FIXTURE / "README.json").read_text(encoding="utf-8"))["cells"]


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _final_response(role):
    cell = CELLS[role]
    rows = [r for r in _rows(FIXTURE / "results.jsonl")
            if r["scenario_id"] == cell["scenario_id"] and r["backend_id"] == cell["backend_id"]]
    return max(rows, key=lambda r: r["turn"])["response"]


def _copy_run(tmp_path):
    run = tmp_path / "run"
    shutil.copytree(FIXTURE, run)
    return run


def test_answer_marks_read_each_check_from_the_envelope():
    hit = answer_marks(_final_response("hit"))
    assert hit["citation"] is True and hit["needs_review"] is True
    assert hit["record"] is False and hit["date"] is False
    date_hit = answer_marks(_final_response("date_hit"))
    assert date_hit["date"] is True
    assert not any(answer_marks(_final_response("miss")).values()), "an unchecked arm marks nothing"
    # The new contract: only a contradicted citation marks; not addressed never does.
    assert answer_marks({"references": [{"support": "contradicted", "groundingStatus": "unsupported"}]})["citation"]
    assert not answer_marks({"references": [{"support": "not_addressed", "groundingStatus": "unsupported"}]})["citation"]
    # Info entries are neutral notes, never marks.
    assert not answer_marks({"answerValidation": {"status": "checked", "issues": [
        {"id": "citation_grounding", "status": "info", "reason": "[21] does not hold 52 kg"}]}})["citation"]
    assert answer_marks({"answerValidation": {"status": "checked", "issues": [
        {"wrong": "stage 3", "chart": "stage 1 [53]"}]}})["review"]


def test_judged_faults_follow_the_threshold_and_every_axis():
    row = {"accuracy": 6, "citation_groundedness": "supported", "harm": False}
    assert judged_answer_faults(row, 7) == {
        "citation": False, "accuracy": True, "harm": False, "temporal": False, "any": True}
    assert judged_answer_faults(row, 6)["any"] is False
    assert judged_answer_faults({"accuracy": 10, "citation_groundedness": "partly"}, 7)["citation"]
    assert judged_answer_faults({"accuracy": 10, "temporal_window": "over-claimed"}, 7)["temporal"]
    assert judged_answer_faults({"accuracy": 10, "harm": True}, 7)["harm"]


def test_in_depth_marks_and_verdicts_join_on_turn_and_point():
    marks = indepth_point_marks(_final_response("hit"))
    assert marks and all(set(m) == {"date", "citation", "review", "marked"} for m in marks.values())
    assert any(m["citation"] for m in marks.values())
    assert indepth_point_marks({"inDepth": {"validation": {"claims": []}}}) == {}
    judge = {r["scenario_id"]: r for r in _rows(FIXTURE / "judge.jsonl") if r["backend_id"] == CELLS["hit"]["backend_id"]}
    verdicts = point_verdicts(judge[CELLS["hit"]["scenario_id"]])
    assert set(verdicts) == {(1, n) for n in marks}
    assert point_verdicts({"background": {"claims": [{"turn": 1, "n": 1, "verdict": "made-up"}]}}) == {}


def test_a_judged_run_scores_every_check_overall_and_per_arm(tmp_path):
    data = score_run(_copy_run(tmp_path))

    assert data["reference"]["headline"] == "canonical"
    assert data["reference"]["actors"] == ["canonical", "codex-gpt-6-astra-high-p1"]
    assert data["reference"]["thresholds"] == {"accuracy_error_below": 7}
    answer = data["answer"]
    assert answer["cells"] == 6 and answer["unmatched_cells"] == 0
    overall = answer["overall"]
    assert set(overall) == {"date", "date_patched", "record", "citation", "review", "needs_review"}
    # Two citation marks on final turns, one of which the judge also faulted.
    assert overall["citation"]["marked"] == 2 and overall["citation"]["hits"] == 1
    assert overall["citation"]["precision"] == 0.5
    assert overall["citation"]["judged_errors"] == 4 and overall["citation"]["recall"] == 0.25
    assert overall["citation"]["by_reference"]["citation"]["hits"] == 1
    # The date check's two marks were both judged temporal faults.
    assert overall["date"] == {**overall["date"], "marked": 2, "hits": 2, "precision": 1.0}
    # A check that never marked has no precision, not a zero.
    assert overall["record"]["marked"] == 0 and overall["record"]["precision"] is None
    # A review mark on an earlier turn of a conversation is counted, not scored.
    assert overall["review"]["marked"] == 0 and overall["review"]["marked_any_turn"] == 1
    assert set(answer["by_arm"]) == {c["backend_id"] for c in CELLS.values()}
    bundled = answer["by_arm"]["engine-parity-bundled-12b"]
    assert bundled["citation"]["n"] == 1 and bundled["citation"]["judged_errors"] == 1
    assert bundled["citation"]["marked"] == 0 and bundled["citation"]["recall"] == 0.0


def test_in_depth_points_score_against_the_per_point_verdicts(tmp_path):
    data = score_run(_copy_run(tmp_path))
    indepth = data["indepth"]

    assert indepth["available"] is True
    assert indepth["points"] == 30 and indepth["judged_points"] == 11
    assert indepth["unjudged_points"] == 19 and indepth["unmatched_verdicts"] == 0
    citation = indepth["overall"]["citation"]
    assert citation["marked"] == 7 and citation["judged_errors"] == 5 and citation["hits"] == 4
    assert citation["precision"] == 0.571 and citation["recall"] == 0.8
    # The confusion names every verdict on each side of the mark.
    assert citation["by_verdict"]["marked"] == {
        "correct": 3, "wrong_fact": 0, "wrong_citation": 4, "unsupported": 0, "guidance": 0}
    assert citation["by_verdict"]["unmarked"]["wrong_fact"] == 1
    assert citation["by_verdict"]["unmarked"]["guidance"] == 3
    checked = indepth["by_arm"]["hub-profile-single-12b-checked"]["citation"]
    assert checked["marked"] == 2 and checked["hits"] == 0 and checked["precision"] == 0.0
    # The pass judged without per-point verdicts says so instead of inventing numbers.
    actor = data["actors"]["codex-gpt-6-astra-high-p1"]["indepth"]
    assert actor["available"] is False and actor["points"] == 30
    assert actor["marked"]["citation"] == 17


def test_a_run_judged_without_per_point_verdicts_reports_them_absent(tmp_path):
    run = _copy_run(tmp_path)
    rows = _rows(run / "judge.jsonl")
    for row in rows:
        row.pop("background", None)
    (run / "judge.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    data = score_run(run)
    assert data["indepth"]["available"] is False
    assert data["indepth"]["marked"]["marked"] == 18
    text = table_text(data)
    assert "no per-point verdicts" in text
    assert "Precision" in text and "Recall" in text


def test_the_script_writes_the_file_and_prints_the_table(tmp_path):
    run = _copy_run(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-precision.py"), str(run)],
        check=True, capture_output=True, text=True, cwd=ROOT,
    )
    data = load_scores(run)
    assert data and data["run_id"] == "run" and data["schema_version"] == "check_precision.v1"
    assert data["generated_at"]
    assert "Citation support" in proc.stdout and "0.50" in proc.stdout
    assert str(run / "judges" / "check-precision.json") in proc.stdout


def test_the_script_leaves_an_unjudged_run_alone_and_exits_clean(tmp_path):
    run = _copy_run(tmp_path)
    (run / "judge.jsonl").unlink()
    shutil.rmtree(run / "judges")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-precision.py"), str(run)],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0
    assert "no judge rows" in proc.stdout
    assert load_scores(run) is None
    assert score_run(run) is None


def test_a_human_adjudication_joins_as_one_more_reference(tmp_path):
    run = _copy_run(tmp_path)
    cell = CELLS["hit"]
    (run / "adjudication.jsonl").write_text(json.dumps({
        "scenario_id": cell["scenario_id"], "backend_id": cell["backend_id"],
        "reviewer_tier": "owner", "axes": {"accuracy": 4, "citation_groundedness": "unsupported"}, "harm": False,
    }) + "\n", encoding="utf-8")

    data = score_run(run)
    assert "adjudication" in data["reference"]["actors"]
    human = data["actors"]["adjudication"]["answer"]
    assert human["cells"] == 1 and human["overall"]["citation"]["hits"] == 1
    assert data["reference"]["headline"] == "canonical"


def test_the_table_renders_from_the_written_file(tmp_path):
    run = _copy_run(tmp_path)
    write_scores(run, score_run(run))
    html = table_html(load_scores(run), {"engine-parity-bundled-12b": "Bundled <engine>"})

    data = load_scores(run)
    expected = 2 + len(data["answer"]["by_arm"]) + 1 + len(data["indepth"]["by_arm"])
    assert html.count("<table") == expected, "overall, per arm, In-Depth overall, by verdict, per arm"
    assert "Precision: of the items a check marked" in html
    assert "Bundled &lt;engine&gt;" in html
    assert "Citation support" in html and "wrong_citation" in html
    assert "<details class='checkprec-arms'>" in html


def test_the_report_carries_the_table_once_the_run_is_scored(tmp_path):
    run = _copy_run(tmp_path)
    before = report._run_blob(run)
    assert before["check_precision"] is None and before["check_precision_html"] == ""

    write_scores(run, score_run(run))
    after = report._run_blob(run)
    assert after["check_precision"]["answer"]["cells"] == 6
    assert "<table" in after["check_precision_html"]
    assert "Label for engine-parity-bundled-12b" in after["check_precision_html"]


def test_a_patched_answer_is_counted_apart_from_date_check_marks():
    from harness.validate.check_precision import answer_marks

    patched = answer_marks({"temporalGate": {"status": "fail", "applied": "patch"}, "answerValidation": {"status": "edited", "issues": []}})
    flagged = answer_marks({"temporalGate": {"status": "fail", "applied": "none"}, "answerValidation": {"status": "needs_review", "issues": []}})

    assert (patched["date"], patched["date_patched"]) == (False, True)
    assert (flagged["date"], flagged["date_patched"]) == (True, False)
