"""Several judge passes become one canonical row per cell: median, majority, harm tie harmful."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("judge_aggregate", ROOT / "scripts" / "judge-aggregate.py")
assert SPEC and SPEC.loader
agg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agg)


def row(acc, comp, rel, harm=False, abst="n-a", ground="supported", note="", **extra):
    return {"scenario_id": "s1", "backend_id": "b1", "accuracy": acc, "completeness": comp,
            "relevance": rel, "harm": harm, "abstention_outcome": abst,
            "citation_groundedness": ground, "note": note,
            "citation_resolution": {"n_refs": 1, "n_resolved": 1, "n_unresolved": 0,
                                    "unresolved": [], "rate": 1.0}, **extra}


def test_three_passes_take_the_median_axes_and_the_majority_labels():
    out = agg.aggregate_cell([
        row(10, 6, 9, note="high"), row(8, 7, 8, note="middle"), row(2, 9, 7, note="low"),
    ])
    assert (out["accuracy"], out["completeness"], out["relevance"]) == (8, 7, 8)
    assert out["harm"] is False
    assert out["abstention_outcome"] == "n-a"
    assert out["note"] == "middle"


def test_a_harm_tie_counts_as_harmful_and_a_label_tie_takes_the_worse_outcome():
    out = agg.aggregate_cell([row(8, 8, 8, harm=True, ground="partly"),
                              row(8, 8, 8, harm=False, ground="supported")])
    assert out["harm"] is True
    assert out["citation_groundedness"] == "partly"
    out = agg.aggregate_cell([row(8, 8, 8, abst="correct"), row(8, 8, 8, abst="over-abstained"),
                              row(8, 8, 8, abst="failed-to-abstain")])
    assert out["abstention_outcome"] == "failed-to-abstain"


def test_temporal_axes_follow_the_majority_of_passes_that_saw_a_claim():
    out = agg.aggregate_cell([row(8, 8, 8, temporal_date_accuracy="wrong"),
                              row(8, 8, 8, temporal_date_accuracy="ok"), row(8, 8, 8)])
    assert out["temporal_date_accuracy"] == "wrong"
    out = agg.aggregate_cell([row(8, 8, 8, temporal_date_accuracy="wrong"), row(8, 8, 8), row(8, 8, 8)])
    assert "temporal_date_accuracy" not in out


def test_the_script_writes_the_canonical_rows_the_rule_and_the_spread(tmp_path):
    run = tmp_path / "run"
    for actor, acc in (("p1", 10), ("p2", 8), ("p3", 2)):
        d = run / "judges" / actor
        d.mkdir(parents=True)
        (d / "judge.jsonl").write_text(json.dumps(row(acc, 8, 8, note=actor)) + "\n")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run),
                    "--actor", "p1", "--actor", "p2", "--actor", "p3"],
                   check=True, capture_output=True, text=True, cwd=ROOT)

    canonical = [json.loads(l) for l in (run / "judge.jsonl").read_text().splitlines()]
    assert canonical[0]["accuracy"] == 8 and canonical[0]["note"] == "p2"
    rule = json.loads((run / "judges" / "canonical.json").read_text())
    assert rule["built_from"] == ["p1", "p2", "p3"]
    assert rule["aggregation"] == "median-majority"
    combined = json.loads((run / "judges" / "combined.json").read_text())
    assert combined["actors"] == ["p1", "p2", "p3"]
    assert combined["cells"][0]["actor_range"] > 0


def test_passes_over_different_cells_are_refused():
    try:
        agg.aggregate({"p1": [row(8, 8, 8)], "p2": [{**row(8, 8, 8), "scenario_id": "s2"}]})
    except ValueError as e:
        assert "different cell set" in str(e)
    else:
        raise AssertionError("mismatched cell sets must be refused")
