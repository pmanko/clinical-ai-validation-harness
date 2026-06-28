from harness.validate.reconcile import combined_judge_summary


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
