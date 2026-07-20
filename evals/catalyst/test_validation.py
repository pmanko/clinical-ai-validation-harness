from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY

import pytest
import yaml

from harness.catalyst import validation as catalyst_validation
from harness.catalyst.validation import (
    CatalystHttpClient,
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
        "target": {
            "dataSource": "openelis-fhir-postgresql",
            "catalogVersion": "catalog-v1+schema.0123456789abcdef",
            "dialect": "postgresql",
        },
        "parameters": [{"name": "test_name", "value": "Viral Load", "type": "text"}],
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
        "source": {
            "dataSource": "openelis-fhir-postgresql",
            "catalogVersion": "catalog-v1+schema.0123456789abcdef",
            "freshness": {"pipelineRunId": "pipeline-42"},
        },
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
                    "profileEvidence": {
                        "profileId": "catalyst-query-gemma-e4b",
                        "writer": {"providerId": "test-provider"},
                        "reviewer": {"providerId": "test-provider"},
                    },
                }
            ]
        }

    def dataset_overview(self) -> dict:
        return {
            "contractVersion": "catalyst.dataset-overview.v1",
            "datasetId": "pipeline-42",
            "dataSource": "openelis-fhir-postgresql",
            "pipelineRunId": "pipeline-42",
            "patients": 2,
            "results": 2,
            "testTypes": 1,
            "firstObservedAt": "2026-04-01T00:00:00Z",
            "lastObservedAt": "2026-04-02T00:00:00Z",
        }

    def catalog(self) -> dict:
        return {
            "contractVersion": "catalyst.workbench.editor-catalog.v1",
            "catalogVersion": "catalog-v1+schema.0123456789abcdef",
            "schemaVersion": "schema-1",
            "dialect": "postgresql",
            "schemas": [{"name": "analytics", "views": []}],
        }

    def submit(self, question: str, profile_id: str) -> tuple[int, dict]:
        assert question
        assert profile_id == "catalyst-query-gemma-e4b"
        return 201, _preview()

    def execute(self, preview: dict) -> tuple[int, dict]:
        assert preview["previewId"] == "preview-1"
        return 200, _table()


class FailingProfileClient(FakeClient):
    def profiles(self) -> dict:
        raise RuntimeError("profile service unavailable")


class FakeHttpResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict | None,
        *,
        text: str = "",
        json_error: ValueError | None = None,
    ) -> None:
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.json_error = json_error
        self.raise_calls = 0

    def raise_for_status(self) -> None:
        self.raise_calls += 1

    def json(self) -> dict:
        if self.json_error is not None:
            raise self.json_error
        assert self.payload is not None
        return self.payload


class FakeHttpSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.profile_response = FakeHttpResponse(200, {"profiles": []})
        self.dataset_response = FakeHttpResponse(200, FakeClient().dataset_overview())
        self.catalog_response = FakeHttpResponse(200, FakeClient().catalog())
        self.submit_response = FakeHttpResponse(201, _preview())
        self.execute_response = FakeHttpResponse(200, _table())

    def get(self, url: str, **kwargs) -> FakeHttpResponse:
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/dataset"):
            return self.dataset_response
        if url.endswith("/workbench/catalog"):
            return self.catalog_response
        return self.profile_response

    def post(self, url: str, **kwargs) -> FakeHttpResponse:
        self.calls.append(("POST", url, kwargs))
        if "/queries" in url:
            return self.submit_response
        return self.execute_response


def _write_suite(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "id": "test-suite",
                "datasetId": "test-data",
                "datasetVersion": "1",
                "catalogVersion": "catalog-v1",
                "profileId": "catalyst-query-gemma-e4b",
                "providerName": "test-provider",
                "datasetOverview": {
                    "patients": 2,
                    "results": 2,
                    "testTypes": 1,
                    "firstObservedDate": "2026-04-01",
                    "lastObservedDate": "2026-04-02",
                },
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
                            "roleModels": {"query_generate": "google/gemma-4-e4b"},
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


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing_required", "Catalyst suite is missing: providerName"),
        ("zero_repetitions", "repetitions must be at least one"),
        ("overview_not_object", "datasetOverview must be an object"),
        ("overview_missing_field", "datasetOverview is missing: patients"),
        ("overview_count_not_integer", "datasetOverview.patients must be an integer"),
        ("overview_date_invalid", "datasetOverview.firstObservedDate must be YYYY-MM-DD"),
        ("invalid_outcome", "invalid expected outcome"),
        ("no_scenarios", "must contain scenarios"),
    ],
)
def test_load_suite_rejects_invalid_contracts(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path)
    payload = json.loads(suite_path.read_text(encoding="utf-8"))

    if case == "missing_required":
        del payload["providerName"]
    elif case == "zero_repetitions":
        payload["repetitions"] = 0
    elif case == "overview_not_object":
        payload["datasetOverview"] = []
    elif case == "overview_missing_field":
        del payload["datasetOverview"]["patients"]
    elif case == "overview_count_not_integer":
        payload["datasetOverview"]["patients"] = "2"
    elif case == "overview_date_invalid":
        payload["datasetOverview"]["firstObservedDate"] = "2026/04/01"
    elif case == "invalid_outcome":
        payload["scenarios"][0]["expectedOutcome"] = "maybe"
    elif case == "no_scenarios":
        payload["scenarios"] = []
    else:  # pragma: no cover - the parameter table is exhaustive
        raise AssertionError(f"unknown case {case}")

    suite_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_suite(suite_path)


def test_http_client_uses_gateway_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeHttpSession()
    monkeypatch.setattr(catalyst_validation.requests, "Session", lambda: session)

    client = CatalystHttpClient("http://gateway.example///", timeout_seconds=17)

    assert client.profiles() == {"profiles": []}
    assert client.dataset_overview() == FakeClient().dataset_overview()
    assert client.catalog() == FakeClient().catalog()
    query_status, query = client.submit("Show viral load results", "profile-1")
    table_status, table = client.execute(_preview())

    assert client.base_url == "http://gateway.example"
    assert query_status == 201
    assert query == _preview()
    assert table_status == 200
    assert table == _table()
    assert session.profile_response.raise_calls == 1
    assert session.dataset_response.raise_calls == 1
    assert session.catalog_response.raise_calls == 1
    assert session.calls[0] == (
        "GET",
        "http://gateway.example/v1/catalyst/query-options",
        {"timeout": 17},
    )
    assert session.calls[1] == (
        "GET",
        "http://gateway.example/v1/catalyst/dataset",
        {"timeout": 17},
    )
    assert session.calls[2] == (
        "GET",
        "http://gateway.example/v1/catalyst/workbench/catalog",
        {"timeout": 17},
    )
    assert session.calls[3] == (
        "POST",
        "http://gateway.example/v1/catalyst/queries",
        {
            "json": {
                "contractVersion": "catalyst.question.request.v1",
                "deploymentMode": "demo",
                "profileId": "profile-1",
                "question": "Show viral load results",
            },
            "timeout": 17,
        },
    )
    method, url, kwargs = session.calls[4]
    assert method == "POST"
    assert url == "http://gateway.example/v1/catalyst/previews/preview-1/execute"
    assert kwargs["timeout"] == 17
    assert kwargs["json"] == {
        "contractVersion": "catalyst.execute.request.v1",
        "previewId": "preview-1",
        "queryDigest": "digest-1",
        "accept": True,
        "idempotencyKey": kwargs["json"]["idempotencyKey"],
    }
    assert kwargs["json"]["idempotencyKey"].startswith("harness-")


def test_http_client_preserves_non_json_gateway_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeHttpSession()
    long_body = "upstream unavailable: " + ("x" * 2_100)
    session.submit_response = FakeHttpResponse(
        502,
        None,
        text=long_body,
        json_error=ValueError("not JSON"),
    )
    session.execute_response = FakeHttpResponse(
        503,
        None,
        text="maintenance",
        json_error=ValueError("not JSON"),
    )
    monkeypatch.setattr(catalyst_validation.requests, "Session", lambda: session)

    client = CatalystHttpClient("http://gateway.example")
    query_status, query = client.submit("Show viral load results", "profile-1")
    table_status, table = client.execute(_preview())

    assert query_status == 502
    assert query == {
        "contractVersion": "harness.http-response-error.v1",
        "status": "http_error",
        "httpStatus": 502,
        "message": "Gateway returned a non-JSON object response.",
        "bodySnippet": long_body[:2_000],
        "bodyTruncated": True,
    }
    assert table_status == 503
    assert table == {
        "contractVersion": "harness.http-response-error.v1",
        "status": "http_error",
        "httpStatus": 503,
        "message": "Gateway returned a non-JSON object response.",
        "bodySnippet": "maintenance",
        "bodyTruncated": False,
    }


def test_evaluate_result_stops_after_invalid_execution_contract() -> None:
    scenario = CatalystScenario(
        id="viral",
        question="Show viral load results",
        expected_outcome="ready",
        execute=True,
        assertions={"expectedUnits": ["copies/ml"]},
        tags=(),
    )
    table = {
        "contractVersion": "harness.http-response-error.v1",
        "status": "http_error",
        "httpStatus": 503,
    }

    assertions = evaluate_result(
        scenario,
        _preview(),
        table,
        query_status=201,
        table_status=503,
    )

    by_name = {item["name"]: item for item in assertions}
    assert by_name["execution_contract"]["passed"] is False
    assert "expected_units" not in by_name


def test_validation_cli_runs_selected_scenarios(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    captured: dict = {}

    class CliClient:
        def __init__(self, base_url: str) -> None:
            captured["base_url"] = base_url

    def fake_run_suite(**kwargs):
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            run_id="run-1",
            run_dir=tmp_path / "run-1",
            passed_count=1,
            result_count=1,
        )

    monkeypatch.setattr(catalyst_validation, "CatalystHttpClient", CliClient)
    monkeypatch.setattr(catalyst_validation, "run_suite", fake_run_suite)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-catalyst-validation.py",
            "--suite",
            "suite.json",
            "--gateway-url",
            "http://gateway.example",
            "--output-dir",
            str(tmp_path),
            "--scenario",
            "viral",
            "--scenario",
            "turnaround",
            "--repetitions",
            "2",
        ],
    )

    script_path = Path(__file__).parents[2] / "scripts" / "run-catalyst-validation.py"
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(script_path), run_name="__main__")

    assert exit_info.value.code == 0
    assert captured["base_url"] == "http://gateway.example"
    assert captured["kwargs"] == {
        "suite_path": Path("suite.json"),
        "client": ANY,
        "output_dir": tmp_path,
        "scenario_ids": {"viral", "turnaround"},
        "repetitions": 2,
    }
    assert json.loads(capsys.readouterr().out) == {
        "run_id": "run-1",
        "run_dir": str(tmp_path / "run-1"),
        "passed": 1,
        "total": 1,
    }


def test_validation_cli_help_works_outside_repository(tmp_path: Path) -> None:
    script_path = Path(__file__).parents[2] / "scripts" / "run-catalyst-validation.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--gateway-url" in result.stdout


def test_mvp_suite_uses_hub_canonical_model_ids() -> None:
    suite_path = (
        Path(__file__).parents[2]
        / "datasets"
        / "validation"
        / "catalyst"
        / "catalyst-mvp-v1.json"
    )

    payload = json.loads(suite_path.read_text(encoding="utf-8"))
    role_models = payload["scenarios"][0]["assertions"]["roleModels"]

    assert role_models == {
        "query_generate": "gemma-4-12b",
        "query_review": "qwen2.5-14b",
    }
    assert payload["datasetOverview"] == {
        "patients": 96,
        "results": 1152,
        "testTypes": 9,
        "firstObservedDate": "2025-07-15",
        "lastObservedDate": "2026-04-27",
    }


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


def test_evaluate_result_rejects_table_columns_that_drift_from_preview() -> None:
    scenario = CatalystScenario(
        id="viral",
        question="Show viral load results",
        expected_outcome="ready",
        execute=True,
        assertions={"requiredColumns": ["patient_id", "result_value"]},
        tags=(),
    )
    table = _table()
    table["table"]["columns"][1]["name"] = "unexpected_value"

    assertions = evaluate_result(
        scenario,
        _preview(),
        table,
        query_status=201,
        table_status=200,
    )

    by_name = {item["name"]: item for item in assertions}
    assert by_name["table_columns_match_preview"]["passed"] is False
    assert by_name["table_required_columns"]["passed"] is False


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


def test_evaluate_result_checks_runtime_query_and_table_identity() -> None:
    scenario = CatalystScenario(
        id="viral",
        question="Show viral load results",
        expected_outcome="ready",
        execute=True,
        assertions={},
        tags=(),
    )
    preview = _preview()
    preview["target"]["catalogVersion"] = "stale-catalog"
    table = _table()
    table["source"]["freshness"]["pipelineRunId"] = "stale-pipeline"

    assertions = evaluate_result(
        scenario,
        preview,
        table,
        query_status=201,
        table_status=200,
        runtime_data_source="openelis-fhir-postgresql",
        runtime_catalog_version="catalog-v1+schema.0123456789abcdef",
        runtime_pipeline_run_id="pipeline-42",
    )

    by_name = {item["name"]: item for item in assertions}
    assert by_name["query_data_source"]["passed"] is True
    assert by_name["query_catalog_version"]["passed"] is False
    assert by_name["table_data_source"]["passed"] is True
    assert by_name["table_catalog_version"]["passed"] is True
    assert by_name["table_pipeline_run"]["passed"] is False


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
    assert manifest["otel"]["gen_ai.provider.name"] == "test-provider"
    assert manifest["otel"]["gen_ai.operation.name"] == "chat"
    assert manifest["schema_mapping_version"] == ("catalog-v1+schema.0123456789abcdef")
    provenance_by_id = {
        item["target_id"]: item for item in manifest["target_provenance"]
    }
    assert set(provenance_by_id) == {"catalyst", "med-agent-hub"}
    contract_path = (
        Path(__file__).parents[2]
        / "specs"
        / "001-harness-control-plane-foundation"
        / "contracts"
        / "run-manifest-control-plane.schema.yaml"
    )
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    required_target_fields = set(contract["target_provenance"]["items"]["required"])
    assert all(
        required_target_fields <= set(item) for item in manifest["target_provenance"]
    )
    assert all(
        item["target_source"] == "reviewed_submodule"
        and item["target_actual_sha"] == item["target_reviewed_sha"]
        and item["target_dirty"] is False
        and item["target_override"] is False
        for item in manifest["target_provenance"]
    )
    catalyst_provenance = provenance_by_id["catalyst"]
    assert catalyst_provenance["suite_sha256"]
    assert catalyst_provenance["dataset_overview_sha256"]
    assert catalyst_provenance["catalog_sha256"]
    assert catalyst_provenance["runtime_dataset_id"] == "pipeline-42"
    assert catalyst_provenance["data_source"] == "openelis-fhir-postgresql"
    assert catalyst_provenance["pipeline_run_id"] == "pipeline-42"
    assert catalyst_provenance["catalog_version"] == (
        "catalog-v1+schema.0123456789abcdef"
    )
    hub_provenance = provenance_by_id["med-agent-hub"]
    assert hub_provenance["profile_discovery_sha256"]
    assert hub_provenance["provider_name"] == "test-provider"
    results = [
        json.loads(line)
        for line in (result.run_dir / "results.jsonl").read_text().splitlines()
    ]
    assert [item["repetition"] for item in results] == [1, 2]
    assert [item["patient_id"] for item in results[0]["record_evidence"]] == [
        "patient-2",
        "patient-1",
    ]
    assert all(len(item["row_sha256"]) == 64 for item in results[0]["record_evidence"])
    assert all(item["passed"] for item in results)
    events = [
        json.loads(line)
        for line in (result.run_dir / "events.jsonl").read_text().splitlines()
    ]
    assert [item["event_type"] for item in events] == [
        "run",
        "runtime_identity",
        "evaluation",
        "evaluation",
    ]


def test_pin_mismatch_fails_before_profile_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path)
    monkeypatch.setattr(
        catalyst_validation, "read_superproject_gitlink", lambda *_: "reviewed"
    )
    monkeypatch.setattr(catalyst_validation, "read_submodule_head", lambda *_: "other")

    class NeverContacted(FakeClient):
        def profiles(self) -> dict:
            pytest.fail("profile discovery must not run before pin preflight")

    with pytest.raises(ValueError, match="reviewed gitlink"):
        run_suite(
            suite_path=suite_path,
            client=NeverContacted(),
            output_dir=tmp_path / "artifacts",
            project_root=tmp_path,
        )

    assert not (tmp_path / "artifacts").exists()


def test_dirty_pin_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        catalyst_validation, "read_superproject_gitlink", lambda *_: "same"
    )
    monkeypatch.setattr(catalyst_validation, "read_submodule_head", lambda *_: "same")
    monkeypatch.setattr(
        catalyst_validation, "submodule_worktree_dirty", lambda *_: True
    )

    with pytest.raises(ValueError, match="uncommitted changes"):
        catalyst_validation._target_provenance(tmp_path)


def test_profile_provider_must_match_suite_evidence(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path)
    suite = load_suite(suite_path)
    profile = FakeClient().profiles()["profiles"][0]
    profile["profileEvidence"]["reviewer"]["providerId"] = "other-provider"

    with pytest.raises(ValueError, match="one provider"):
        catalyst_validation._profile_provider(profile, suite)


def test_runtime_identity_mismatch_fails_before_query_submission(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "suite.json"
    _write_suite(suite_path)

    class MismatchedRuntime(FakeClient):
        def dataset_overview(self) -> dict:
            overview = super().dataset_overview()
            overview["results"] = 3
            return overview

        def submit(self, question: str, profile_id: str) -> tuple[int, dict]:
            pytest.fail("query submission must not run before runtime preflight")

    output_dir = tmp_path / "artifacts"
    with pytest.raises(ValueError, match="results is 3; expected 2"):
        run_suite(
            suite_path=suite_path,
            client=MismatchedRuntime(),
            output_dir=output_dir,
            project_root=Path(__file__).parents[2],
        )

    run_dir = next(output_dir.iterdir())
    events = [
        json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()
    ]
    assert [item["event_type"] for item in events] == [
        "run",
        "runtime_identity_failed",
    ]


def test_profile_discovery_failure_still_writes_run_evidence(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    output_dir = tmp_path / "artifacts"
    _write_suite(suite_path)

    with pytest.raises(RuntimeError, match="profile service unavailable"):
        run_suite(
            suite_path=suite_path,
            client=FailingProfileClient(),
            output_dir=output_dir,
            project_root=Path(__file__).parents[2],
        )

    run_dirs = list(output_dir.iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "run_manifest.json").is_file()
    manifest = json.loads((run_dirs[0] / "run_manifest.json").read_text())
    assert manifest["otel"]["gen_ai.provider.name"] == "unresolved"
    events = [
        json.loads(line)
        for line in (run_dirs[0] / "events.jsonl").read_text().splitlines()
    ]
    assert [item["event_type"] for item in events] == [
        "run",
        "profile_discovery_failed",
    ]
