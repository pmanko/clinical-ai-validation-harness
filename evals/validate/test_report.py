import json
from pathlib import Path

from harness.validate.report import build_report

_DEGRADED_ANSWER = "I could not produce a complete answer for this turn. Please try again."


def _write_run(run_dir: Path, results):
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
                    "modelName": "med-agent-team"}) + "\n"
        + json.dumps({"event_type": "backend_selected", "backend_id": "gemma-local",
                      "modelName": "gemma-4-e2b-it"}) + "\n",
        encoding="utf-8",
    )
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")


def _result(backend, answer, refs, **metrics):
    base = {"latency_ms": 10, "http_status": 200, "json_valid": True,
            "citation_count": len(refs), "references_empty": not refs, "first_turn": True}
    base.update(metrics)
    return {"run_id": "r1", "scenario_id": "s", "backend_id": backend, "turn": 1,
            "request": {"question": "q"}, "response": {"answer": answer, "references": refs},
            "metrics": base}


def test_report_flags_the_degraded_fallback_envelope(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", _DEGRADED_ANSWER, []),
        _result("gemma-local", "Lisinopril 10 mg [1]",
                [{"index": 1, "resourceType": "MedicationRequest"}]),
    ])

    html = build_report(run_dir).read_text(encoding="utf-8")

    # The team's graceful-fallback envelope (200/valid/0-cites) is flagged degraded
    # exactly once; the real gemma answer is not.
    assert "⚠ degraded" in html
    assert html.count("⚠ degraded") == 1
