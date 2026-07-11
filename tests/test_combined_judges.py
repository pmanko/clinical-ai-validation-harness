import importlib.util
import json
from pathlib import Path

import pytest

from harness.validate.reconcile import combined_judge_summary


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "combine_judge_actors", ROOT / "scripts" / "combine-judge-actors.py"
)
assert SPEC and SPEC.loader
COMBINER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMBINER)


def jrow(scenario, backend, accuracy, completeness=None, relevance=None):
    return {
        "scenario_id": scenario,
        "backend_id": backend,
        "accuracy": accuracy,
        "completeness": accuracy if completeness is None else completeness,
        "relevance": accuracy if relevance is None else relevance,
        "abstention_outcome": "n-a",
        "citation_groundedness": "supported",
        "harm": False,
    }


def test_combined_judge_summary_averages_per_cell_and_keeps_cell_n():
    actors = {
        "judge-a": [jrow("s1", "b1", 10), jrow("s2", "b1", 6)],
        "judge-b": [jrow("s1", "b1", 8), jrow("s2", "b1", 2)],
    }

    row = combined_judge_summary(actors, ["b1"])[0]

    assert row["n_cells"] == 2
    assert row["n_actors"] == 2
    assert row["benchmark_score"] == 65.0
    assert row["actor_scores"] == {"judge-a": 80.0, "judge-b": 50.0}
    assert row["actor_range"] == {"min": 50.0, "max": 80.0}
    assert row["mean_abs_delta"] == 30.0
    assert row["max_cell_delta_scenario"] == "s2"


def test_combined_actor_artifact_is_recomputed_per_cell(tmp_path):
    paths = {}
    for actor, rows in {
        "judge-a": [jrow("s1", "b1", 10), jrow("s2", "b1", 6)],
        "judge-b": [jrow("s1", "b1", 8), jrow("s2", "b1", 2)],
    }.items():
        path = tmp_path / f"{actor}.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        paths[actor] = path

    result = COMBINER.build(paths)

    assert result["schema_version"] == "combined_judgment.v1"
    assert result["actors"] == ["judge-a", "judge-b"]
    assert result["cells"][0]["actor_scores"] == {
        "judge-a": 100.0,
        "judge-b": 80.0,
    }
    assert result["cells"][0]["consensus_score"] == 90.0
    assert result["backend_summary"][0]["benchmark_score"] == 65.0


def test_combined_actor_artifact_rejects_different_cell_matrices(tmp_path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(json.dumps(jrow("s1", "b1", 10)) + "\n")
    b.write_text(json.dumps(jrow("s2", "b1", 10)) + "\n")

    with pytest.raises(ValueError, match="same cell matrix"):
        COMBINER.build({"a": a, "b": b})
