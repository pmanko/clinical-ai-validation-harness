"""Turn checks against a run directory's frozen scenarios and results."""

import json
from pathlib import Path

from harness.cli import main
from harness.validate.expectations import check_turn


def _row(answer="", refs=(), error=None, scenario="s1", turn=1):
    return {"scenario_id": scenario, "backend_id": "b1", "turn": turn, "error": error,
            "response": None if error else {"answer": answer,
                                            "references": [{"index": i, "resourceType": t}
                                                           for i, t in enumerate(refs, 1)]}}


def test_each_check_passes_and_fails_on_the_answer():
    checks = {"cite_types": ["MedicationRequest"], "answer_includes": ["efavirenz"],
              "answer_excludes": ["warfarin"]}
    assert check_turn(checks, _row("On Efavirenz.", ["MedicationRequest"])) == []
    failures = check_turn(checks, _row("On warfarin.", ["Observation"]))
    assert failures == ["no MedicationRequest reference (cited: Observation)",
                        "answer does not match /efavirenz/",
                        "answer matches excluded /warfarin/"]
    assert check_turn({"cite_nothing": True}, _row("Not recorded.")) == []
    assert check_turn({"cite_nothing": True}, _row("A+", ["Observation"])) == [
        "1 reference(s) on a question the chart cannot answer"]


def test_an_error_or_an_unknown_check_fails_rather_than_passes():
    assert check_turn({"cite_nothing": True}, _row(error="timeout")) == ["no answer: timeout"]
    assert check_turn({"cite_typo": ["X"]}, _row("x")) == ["unknown check(s): cite_typo"]


def test_expect_reads_the_run_directory_and_exits_non_zero_on_a_failure(tmp_path: Path, capsys):
    scenarios = tmp_path / "inputs" / "scenarios"
    scenarios.mkdir(parents=True)
    (scenarios / "s1.json").write_text(json.dumps({
        "id": "s1", "patient_ref": "p", "turns": [
            {"n": 1, "question": "Meds?", "checks": {"cite_types": ["MedicationRequest"]}},
            {"n": 2, "question": "Thanks", "checks": {}}]}))
    rows = [_row("ok", ["MedicationRequest"]), _row("ok", turn=2),
            {**_row("none", []), "backend_id": "b2"}]
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    assert main(["validate", "expect", "--run-dir", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "1 of 2 checked turns passed" in out and "FAIL s1 turn 1 b2" in out
    lines = (tmp_path / "expectations.jsonl").read_text().splitlines()
    assert [json.loads(l)["passed"] for l in lines] == [True, False]
