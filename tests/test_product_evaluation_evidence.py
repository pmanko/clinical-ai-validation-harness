import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "build-product-evaluation-evidence.py"
SPEC = importlib.util.spec_from_file_location("product_evidence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_substantive_answer_rejects_product_fallback():
    assert MODULE._is_substantive("A documented visit occurred.")
    assert not MODULE._is_substantive("")
    assert not MODULE._is_substantive(MODULE.FALLBACK_ANSWER)


def test_expected_candidate_matrix_is_exactly_24_cells():
    pairs = MODULE._expected_pairs()
    assert len(pairs) == 24
    assert {backend for _scenario, backend in pairs} == {
        "product-e4b-checked",
        "product-12b-checked",
    }


def test_evidence_builder_rejects_an_incomplete_run(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "results.jsonl").write_text(
        json.dumps(
            {
                "scenario_id": "date-zabella-weight-table",
                "backend_id": "product-e4b-checked",
                "reference_date": "2026-06-20",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    trace = tmp_path / "trace.jsonl"
    trace.write_text("", encoding="utf-8")

    try:
        MODULE.build_evidence(run, trace, tmp_path / "out")
    except RuntimeError as error:
        assert "Run matrix mismatch" in str(error)
    else:
        raise AssertionError("incomplete run unexpectedly accepted")


def _valid_candidate_fixture(tmp_path):
    run = tmp_path / "candidate-run"
    run.mkdir()
    traces = []
    results = []
    start = datetime(2026, 7, 11, tzinfo=timezone.utc)
    for offset, (scenario, backend) in enumerate(sorted(MODULE._expected_pairs())):
        ts = start + timedelta(minutes=offset)
        results.append(
            {
                "scenario_id": scenario,
                "backend_id": backend,
                "reference_date": MODULE.EXPECTED_REFERENCE_DATE,
                "started_at": ts.isoformat(),
                "ended_at": (ts + timedelta(seconds=30)).isoformat(),
                "metrics": {"http_status": 200},
                "response": {
                    "answer": "The documented result is 500 on 2006-04-24.",
                    "answerValidation": {"status": "checked"},
                    "references": [
                        {
                            "index": 1,
                            "resolutionStatus": "resolved",
                            "groundingStatus": "verified",
                        }
                    ],
                    "inDepth": {
                        "status": "complete",
                        "answer": "The chart contains a supporting observation.",
                    },
                },
            }
        )
        traces.append(
            {
                "ts": (ts + timedelta(seconds=1)).isoformat(),
                "level_id": MODULE.arm_model_name(backend),
                "reference_date": MODULE.EXPECTED_REFERENCE_DATE,
                "temporal_gate": {"mode": "enforce", "status": "pass"},
                "indepth_temporal_gate": {"mode": "enforce", "status": "checked"},
            }
        )
    results_path = run / "results.jsonl"
    results_path.write_text(
        "".join(json.dumps(row) + "\n" for row in results), encoding="utf-8"
    )
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "".join(json.dumps(row) + "\n" for row in traces), encoding="utf-8"
    )
    return run, trace_path, results, traces


def _build_and_read(tmp_path, results, traces):
    run = tmp_path / "candidate-run"
    (run / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in results), encoding="utf-8"
    )
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "".join(json.dumps(row) + "\n" for row in traces), encoding="utf-8"
    )
    _, audit_path = MODULE.build_evidence(run, trace_path, tmp_path / "out")
    return json.loads(audit_path.read_text(encoding="utf-8"))


def test_evidence_builder_accepts_the_complete_24_cell_contract(tmp_path):
    run, trace_path, _results, _traces = _valid_candidate_fixture(tmp_path)

    selected_path, audit_path = MODULE.build_evidence(
        run, trace_path, tmp_path / "out"
    )

    assert len(selected_path.read_text().splitlines()) == 24
    audit = json.loads(audit_path.read_text())
    assert audit["status"] == "pass"
    assert audit["blockers"] == []


def test_evidence_builder_blocks_every_release_safety_failure(tmp_path):
    _run, _trace_path, results, traces = _valid_candidate_fixture(tmp_path)
    results[0]["response"]["answer"] = "The visit was 2025-10-//13."
    results[1]["response"]["references"][0]["resolutionStatus"] = "unresolved"
    results[2]["response"]["references"][0]["groundingStatus"] = "checking"
    results[3]["response"]["inDepth"]["answer"] = ""
    traces[4]["temporal_gate"] = {"mode": "warn", "status": "pass"}
    traces[5]["temporal_gate"] = {"mode": "enforce", "status": "fail"}
    traces[6]["indepth_temporal_gate"] = {"mode": "warn", "status": "pass"}
    results[7]["response"]["answerValidation"] = {"status": "needs_review"}
    results[8]["response"]["references"][0]["groundingStatus"] = "unsupported"
    results[9]["response"]["inDepth"]["answer"] = "The follow-up was 2026-0-[59]."
    results[10]["response"]["inDepth"] = {
        "status": "needs_review",
        "answer": "This text must not remain visible.",
    }
    traces[10]["indepth_temporal_gate"] = {
        "mode": "enforce",
        "status": "needs_review",
    }
    traces[11]["temporal_gate"] = {"mode": "enforce"}

    audit = _build_and_read(tmp_path, results, traces)

    assert audit["status"] == "fail"
    blocker_ids = {row["id"] for row in audit["blockers"]}
    assert {
        "malformed_dates",
        "references_resolved",
        "grounding_terminal",
        "indepth_substantive",
        "answer_temporal_enforce",
        "answer_gate_terminal",
        "indepth_temporal_enforce",
        "answer_validation_terminal",
        "grounding_supported",
        "indepth_withheld_empty",
    } <= blocker_ids
    assert any(
        row["id"] == "malformed_dates" and "2026-0-[59]" in str(row["evidence"])
        for row in audit["blockers"]
    )


def test_malformed_date_audit_ignores_safely_withheld_diagnostic_claims(tmp_path):
    run, trace_path, results, _traces = _valid_candidate_fixture(tmp_path)
    results[0]["response"]["inDepth"]["validation"] = {
        "status": "edited",
        "checks": [{"claim": "Rejected malformed date 2026-0-[59]."}],
    }
    (run / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in results), encoding="utf-8"
    )

    _, audit_path = MODULE.build_evidence(run, trace_path, tmp_path / "out")

    audit = json.loads(audit_path.read_text())
    assert audit["status"] == "pass"


def test_evidence_builder_blocks_missing_trace_and_nonterminal_indepth(tmp_path):
    _run, _trace_path, results, traces = _valid_candidate_fixture(tmp_path)
    traces.pop(0)
    results[1]["response"]["inDepth"] = {"status": "pending", "answer": ""}

    audit = _build_and_read(tmp_path, results, traces)

    blocker_ids = {row["id"] for row in audit["blockers"]}
    assert "trace_resolved" in blocker_ids
    assert "indepth_terminal_status" in blocker_ids
