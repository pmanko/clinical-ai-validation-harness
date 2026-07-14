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


def test_expected_candidate_matrix_is_exactly_12_cells():
    pairs = MODULE._expected_pairs()
    assert len(pairs) == 12
    assert {backend for _scenario, backend in pairs} == {"single-12b-checked"}


def test_run_contract_resolves_historical_comparison_set_at_recorded_git_sha(
    tmp_path, monkeypatch
):
    run = tmp_path / "historical-run"
    run.mkdir()
    (run / "run_manifest.json").write_text(
        json.dumps({"git_sha": "a" * 40}), encoding="utf-8"
    )
    (run / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "run",
                "comparison_set": "retired-candidate-name",
                "reference_date": "2026-06-20",
                "scenario_ids": ["scenario-a"],
                "backend_ids": ["retired-backend-name"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "run_meta.json").write_text(
        json.dumps({"arm_cards": {"retired-backend-name": {"stages": ["answer"]}}}),
        encoding="utf-8",
    )
    calls = []

    def repository_output(args, **kwargs):
        calls.append((args, kwargs))
        if args[-1].endswith("datasets/validation/backends.json"):
            return json.dumps(
                {
                    "retired-backend-name": {
                        "modelName": MODULE.EXPECTED_PRODUCT_PROFILE
                    }
                }
            )
        return json.dumps(
            {
                "id": "retired-candidate-name",
                "scenario_ids": ["scenario-a"],
                "backend_ids": ["retired-backend-name"],
            }
        )

    monkeypatch.setattr(MODULE.subprocess, "check_output", repository_output)

    comparison, reference_date, expected, stages, profiles = MODULE._run_contract(run)

    assert comparison == "retired-candidate-name"
    assert reference_date == "2026-06-20"
    assert expected == {("scenario-a", "retired-backend-name")}
    assert stages == {"retired-backend-name": ["answer"]}
    assert profiles == {"retired-backend-name": MODULE.EXPECTED_PRODUCT_PROFILE}
    assert calls[0][0] == [
        "git",
        "show",
        ("a" * 40)
        + ":datasets/validation/comparison_sets/retired-candidate-name.json",
    ]
    assert calls[1][0] == [
        "git",
        "show",
        ("a" * 40) + ":datasets/validation/backends.json",
    ]


def test_evidence_builder_rejects_an_incomplete_run(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "run",
                "comparison_set": MODULE.EXPECTED_SET,
                "reference_date": MODULE.EXPECTED_REFERENCE_DATE,
                "scenario_ids": [scenario for scenario, _ in sorted(MODULE._expected_pairs())],
                "backend_ids": ["single-12b-checked"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "run_meta.json").write_text(
        json.dumps({"arm_cards": {}}) + "\n", encoding="utf-8"
    )
    (run / "results.jsonl").write_text(
        json.dumps(
            {
                "scenario_id": "date-zabella-weight-table",
                "backend_id": "single-12b-checked",
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
    pairs = sorted(MODULE._expected_pairs())
    scenario_ids = list(dict.fromkeys(scenario for scenario, _ in pairs))
    backend_ids = list(dict.fromkeys(backend for _, backend in pairs))
    stages = ["context", "answer", "gate", "resolve_refs"]
    (run / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "run",
                "comparison_set": MODULE.EXPECTED_SET,
                "reference_date": MODULE.EXPECTED_REFERENCE_DATE,
                "scenario_ids": scenario_ids,
                "backend_ids": backend_ids,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "run_meta.json").write_text(
        json.dumps(
            {"arm_cards": {backend: {"stages": stages} for backend in backend_ids}}
        )
        + "\n",
        encoding="utf-8",
    )
    start = datetime(2026, 7, 11, tzinfo=timezone.utc)
    for offset, (scenario, backend) in enumerate(pairs):
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
                "level_id": MODULE.EXPECTED_PRODUCT_PROFILE,
                "reference_date": MODULE.EXPECTED_REFERENCE_DATE,
                "temporal_gate": {"mode": "enforce", "status": "pass"},
                "indepth_temporal_gate": {"mode": "enforce", "status": "checked"},
                "steps": [
                    {
                        "role": "stage_timing",
                        "stage": stage,
                        "occurrence": 1,
                        "duration_ms": 10,
                        "status": "completed",
                    }
                    for stage in stages
                ],
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


def test_evidence_builder_accepts_the_complete_12_cell_contract(tmp_path):
    run, trace_path, _results, _traces = _valid_candidate_fixture(tmp_path)

    selected_path, audit_path = MODULE.build_evidence(
        run, trace_path, tmp_path / "out"
    )

    assert len(selected_path.read_text().splitlines()) == 12
    audit = json.loads(audit_path.read_text())
    assert audit["status"] == "pass"
    assert audit["blockers"] == []
    assert audit["profiles_by_backend"] == {
        "single-12b-checked": MODULE.EXPECTED_PRODUCT_PROFILE
    }


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


def test_safe_temporal_fallback_is_a_terminal_gate_but_not_a_substantive_answer(
    tmp_path,
):
    _run, _trace_path, results, traces = _valid_candidate_fixture(tmp_path)
    results[0]["response"]["answer"] = MODULE.TEMPORAL_FALLBACK_ANSWER
    results[0]["response"]["answerValidation"] = {"status": "needs_review"}
    traces[0]["temporal_gate"] = {
        "mode": "enforce",
        "status": "fail",
        "applied": "fallback",
    }

    audit = _build_and_read(tmp_path, results, traces)

    first = [
        row
        for row in audit["blockers"]
        if row["scenario_id"] == results[0]["scenario_id"]
        and row["backend_id"] == results[0]["backend_id"]
    ]
    assert {row["id"] for row in first} == {
        "substantive_answer",
        "answer_validation_terminal",
    }


def test_evidence_builder_blocks_missing_trace_and_nonterminal_indepth(tmp_path):
    _run, _trace_path, results, traces = _valid_candidate_fixture(tmp_path)
    traces.pop(0)
    results[1]["response"]["inDepth"] = {"status": "pending", "answer": ""}

    audit = _build_and_read(tmp_path, results, traces)

    blocker_ids = {row["id"] for row in audit["blockers"]}
    assert "trace_resolved" in blocker_ids
    assert "indepth_terminal_status" in blocker_ids
