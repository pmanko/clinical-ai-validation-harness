import json

from harness.validate.report import write_summary_export


def test_write_summary_export_uses_scout_summary(tmp_path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "results.jsonl").write_text(
        json.dumps({"backend_id": "team-arm"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "judge.jsonl").write_text(
        json.dumps(
            {
                "backend_id": "team-arm",
                "accuracy": 8,
                "completeness": 6,
                "relevance": 10,
                "harm": False,
                "citation_resolution": {"n_refs": 2, "n_resolved": 1, "n_unresolved": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = write_summary_export(run_dir)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == 1
    assert payload["runId"] == "run-1"
    assert payload["aggregates"] == [
        {
            "armId": "team-arm",
            "answerMeans": {"accuracy": 8.0, "completeness": 6.0, "relevance": 10.0},
            "benchmark": 0.8,
            "confabCount": 1,
            "harmCount": 0,
            "source": "harness.validate.reconcile.scout_summary",
        }
    ]
