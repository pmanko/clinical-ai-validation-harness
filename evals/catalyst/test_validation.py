from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.catalyst.validation import (
    CatalystScenario,
    evaluate_result,
    load_suite,
    run_suite,
)


def _preview() -> dict:
    return {
        "contractVersion": "catalyst.preview.v1",
        "previewId": "preview-1",
        "queryDigest": "digest-1",
        "parameters": [
            {"name": "test_name", "value": "Viral Load", "type": "text"}
        ],
        "expectedColumns": [
            {"name": "patient_id"},
            {"name": "result_value"},
            {"name": "result_unit"},
            {"name": "observed_at"},
        ],
        "reasoningTrace": {
            "traceId": "trace-1",
            "profileId": "catalyst-query-gemma-e4b",
            "status": "passed",
            "stages": [
                "context",
                "query_generate",
                "query_lint",
                "query_review",
                "query_finalize",
            ],
            "roleModels": {
                "query_generate": "google/gemma-4-e4b",
                "query_review": "google/gemma-4-e4b",
            },
            "checks": [
                {"name": "query_lint_attempt_1", "status": "warned"},
                {"name": "query_lint_attempt_2", "status": "passed"},
            ],
        },
    }


def _table() -> dict:
    return {
        "contractVersion": "catalyst.table.v1",
        "table": {
            "columns": [
                {"name": "patient_id"},
                {"name": "result_value"},
                {"name": "result_unit"},
                {"name": "observed_at"},
            ],
            "rows": [
                [
                    {"type": "string", "value": "patient-2"},
                    {"type": "decimal", "value": "120"},
                    {"type": "string", "value": "copies/ml"},
                    {"type": "date-time", "value": "2026-04-01T00:00:00Z"},
                ],
                [
                    {"type": "string", "value": "patient-1"},
                    {"type": "decimal", "value": "80"},
                    {"type": "string", "value": "copies/ml"},
                    {"type": "date-time", "value": "2026-04-02T00:00:00Z"},
                ],
            ],
            "rowCount": {"returned": 2, "truncated": False},
        },
    }


class FakeClient:
    def profiles(self) -> dict:
        return {
            "profiles": [
                {
                    "id": "catalyst-query-gemma-e4b",
                    "available": True,
                    "roleModels": {
                        "query_generate": "google/gemma-4-e4b",
                        "query_review": "google/gemma-4-e4b",
                    },
                }
            ]
        }

    def submit(self, question: str, profile_id: str) -> tuple[int, dict]:
        assert question
        assert profile_id == "catalyst-query-gemma-e4b"
        return 201, _preview()

    def execute(self, preview: dict) -> tuple[int, dict]:
        assert preview["previewId"] == "preview-1"
        return 200, _table()


def _write_suite(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "id": "test-suite",
                "datasetId": "test-data",
                "datasetVersion": "1",
                "catalogVersion": "catalog-v1",
                "profileId": "catalyst-query-gemma-e4b",
                "repetitions": 2,
                "scenarios": [
                    {
                        "id": "viral",
                        "question": "Show viral load results",
                        "expectedOutcome": "ready",
                        "tags": ["happy-path"],
                        "assertions": {
                            "requiredParameterValues": ["Viral Load"],
                            "requiredColumns": ["patient_id", "result_unit"],
                            "requiredStages": ["query_lint", "query_review"],
                            "roleModels": {
                                "query_generate": "google/gemma-4-e4b"
                            },
                            "minReturned": 2,
                            "maxReturned": 2,
                            "expectedUnits": ["copies/ml"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_load_suite_rejects_duplicate_scenarios(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path)
    payload = json.loads(suite_path.read_text())
    payload["scenarios"].append(payload["scenarios"][0])
    suite_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="duplicate"):
        load_suite(suite_path)


def test_evaluate_result_requires_final_clean_lint() -> None:
    scenario = CatalystScenario(
        id="viral",
        question="Show viral load results",
        expected_outcome="ready",
        execute=True,
        assertions={"requiredColumns": ["patient_id"]},
        tags=(),
    )
    preview = _preview()
    preview["reasoningTrace"]["checks"][-1]["status"] = "failed"

    assertions = evaluate_result(
        scenario,
        preview,
        _table(),
        query_status=201,
        table_status=200,
    )

    by_name = {item["name"]: item for item in assertions}
    assert by_name["final_lint_passed"]["passed"] is False
    assert by_name["execution_contract"]["passed"] is True


def test_evaluate_result_checks_numeric_result_semantics() -> None:
    scenario = CatalystScenario(
        id="turnaround",
        question="Show turnaround over 24 hours",
        expected_outcome="ready",
        execute=True,
        assertions={
            "requiredColumns": ["receipt_to_release_minutes"],
            "numericColumnMinExclusive": {"receipt_to_release_minutes": 1440},
            "distinctColumnCount": {"patient_id": 2},
        },
        tags=(),
    )
    preview = _preview()
    preview["expectedColumns"].append({"name": "receipt_to_release_minutes"})
    table = _table()
    table["table"]["columns"].append({"name": "receipt_to_release_minutes"})
    table["table"]["rows"][0].append({"type": "integer", "value": 2880})
    table["table"]["rows"][1].append({"type": "integer", "value": 60})

    assertions = evaluate_result(
        scenario,
        preview,
        table,
        query_status=201,
        table_status=200,
    )

    by_name = {item["name"]: item for item in assertions}
    threshold = by_name["numeric_min_exclusive.receipt_to_release_minutes"]
    assert threshold["passed"] is False
    assert threshold["evidence"]["observed_minimum"] == 60
    assert by_name["distinct_count.patient_id"]["passed"] is True


def test_run_suite_writes_versioned_evidence(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path)

    result = run_suite(
        suite_path=suite_path,
        client=FakeClient(),
        output_dir=tmp_path / "artifacts",
        project_root=Path(__file__).parents[2],
    )

    assert result.result_count == 2
    assert result.passed_count == 2
    manifest = json.loads((result.run_dir / "run_manifest.json").read_text())
    assert manifest["component"] == "catalyst-query-validation"
    assert manifest["target_provenance"][0]["suite_sha256"]
    results = [
        json.loads(line)
        for line in (result.run_dir / "results.jsonl").read_text().splitlines()
    ]
    assert [item["repetition"] for item in results] == [1, 2]
    assert results[0]["record_evidence"] == ["patient-1", "patient-2"]
    assert all(item["passed"] for item in results)
    events = [
        json.loads(line)
        for line in (result.run_dir / "events.jsonl").read_text().splitlines()
    ]
    assert [item["event_type"] for item in events] == [
        "run",
        "evaluation",
        "evaluation",
    ]
