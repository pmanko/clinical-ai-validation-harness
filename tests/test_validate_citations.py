"""Citation scoring of a run directory against a gold file."""

import json
from pathlib import Path

from harness.cli import main
from harness.validate.citations import score_cell


def test_cells_score_on_off_and_unknown_citations_like_the_drift_metric():
    present = score_cell(["a", "f", "x"], True, {"a", "b"}, {"f"})
    assert (present["on"], present["off"], present["unk"]) == (["a"], ["f"], ["x"])
    assert round(present["prec"], 3) == 0.333 and present["rec"] == 0.5
    assert score_cell([], True, set(), {"f"})["f1"] is None
    assert score_cell([], False, set(), set())["abstain_ok"] is True
    assert score_cell(["f"], False, set(), {"f"}, off_adj=set(), on_adj=set())["abstain_ok"] is False
    assert score_cell(["z"], True, {"a"}, set(), on_adj={"z"})["on"] == ["z"]


def test_a_run_is_scored_per_backend_from_its_own_directory(tmp_path: Path, capsys):
    scenarios = tmp_path / "inputs" / "scenarios"
    scenarios.mkdir(parents=True)
    for sid, cell in (("p", "u|meds"), ("q", "u|eye")):
        (scenarios / f"{sid}.json").write_text(json.dumps({
            "id": sid, "patient_ref": "u", "turns": [{"n": 1, "question": "?"}],
            "expectations": {"gold_cell": cell}}))
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"u|meds": {"present": True, "ontopic": {"a": "", "b": ""},
                                           "focus_uuids": {}},
                                "u|eye": {"present": False, "ontopic": {}, "focus_uuids": {}}}))

    def row(sid, refs, backend="b1"):
        return {"scenario_id": sid, "backend_id": backend, "turn": 1,
                "response": {"answer": "x", "references": refs}}
    attached = {"resourceUuid": "b", "attachedByTheModule": True}
    rows = [row("p", [{"resourceUuid": "a"}, attached]), row("q", []),
            row("p", [{"resourceUuid": "a"}, {"resourceUuid": "b"}], "b2"),
            row("q", [{"resourceUuid": "c"}], "b2")]
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows))

    assert main(["validate", "score-citations", "--run-dir", str(tmp_path), "--gold", str(gold)]) == 0
    scores = json.loads((tmp_path / "citation_scores.json").read_text())
    assert scores["summary"]["b1"]["meanF1"] == 0.667
    assert scores["summary"]["b1"]["abstention_accuracy"] == 1.0
    assert scores["summary"]["b2"]["meanF1"] == 1.0
    assert scores["summary"]["b2"]["abstention_accuracy"] == 0.0
    assert (tmp_path / "inputs" / "gold" / "gold.json").exists()
