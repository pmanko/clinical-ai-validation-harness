"""Repeatable real-path experiments for Catalyst governed text-to-SQL."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import requests

from ..metadata import RunManifest, append_event, write_manifest
from ..submodules import read_harness_git_sha


_MAX_ERROR_BODY_CHARS = 2_000


@dataclass(frozen=True)
class CatalystScenario:
    id: str
    question: str
    expected_outcome: str
    execute: bool
    assertions: dict[str, Any]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class CatalystSuite:
    id: str
    dataset_id: str
    dataset_version: str
    catalog_version: str
    profile_id: str
    repetitions: int
    scenarios: tuple[CatalystScenario, ...]


@dataclass(frozen=True)
class CatalystRunResult:
    run_id: str
    run_dir: Path
    result_count: int
    passed_count: int


class CatalystTransport(Protocol):
    def profiles(self) -> dict[str, Any]: ...

    def submit(self, question: str, profile_id: str) -> tuple[int, dict[str, Any]]: ...

    def execute(self, preview: dict[str, Any]) -> tuple[int, dict[str, Any]]: ...


class CatalystHttpClient:
    def __init__(self, base_url: str, *, timeout_seconds: int = 240) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def profiles(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/v1/catalyst/query-options",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def submit(self, question: str, profile_id: str) -> tuple[int, dict[str, Any]]:
        response = self.session.post(
            f"{self.base_url}/v1/catalyst/queries",
            json={
                "contractVersion": "catalyst.question.request.v1",
                "deploymentMode": "demo",
                "profileId": profile_id,
                "question": question,
            },
            timeout=self.timeout_seconds,
        )
        return response.status_code, _response_payload(response)

    def execute(self, preview: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        preview_id = preview["previewId"]
        response = self.session.post(
            f"{self.base_url}/v1/catalyst/previews/{preview_id}/execute",
            json={
                "contractVersion": "catalyst.execute.request.v1",
                "previewId": preview_id,
                "queryDigest": preview["queryDigest"],
                "accept": True,
                "idempotencyKey": f"harness-{uuid4()}",
            },
            timeout=self.timeout_seconds,
        )
        return response.status_code, _response_payload(response)


def _response_payload(response: requests.Response) -> dict[str, Any]:
    """Decode a Gateway response without discarding its real HTTP status."""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        return payload

    body = response.text
    return {
        "contractVersion": "harness.http-response-error.v1",
        "status": "http_error" if response.status_code >= 400 else "invalid_response",
        "httpStatus": response.status_code,
        "message": "Gateway returned a non-JSON object response.",
        "bodySnippet": body[:_MAX_ERROR_BODY_CHARS],
        "bodyTruncated": len(body) > _MAX_ERROR_BODY_CHARS,
    }


def load_suite(path: Path | str) -> CatalystSuite:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "id",
        "datasetId",
        "datasetVersion",
        "catalogVersion",
        "profileId",
        "repetitions",
        "scenarios",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Catalyst suite is missing: {', '.join(missing)}")
    repetitions = int(payload["repetitions"])
    if repetitions < 1:
        raise ValueError("Catalyst suite repetitions must be at least one")
    scenarios = []
    seen = set()
    for item in payload["scenarios"]:
        scenario_id = str(item["id"])
        if scenario_id in seen:
            raise ValueError(f"duplicate Catalyst scenario id {scenario_id!r}")
        seen.add(scenario_id)
        outcome = str(item["expectedOutcome"])
        if outcome not in {"ready", "needs_clarification", "unsupported", "rejected"}:
            raise ValueError(f"scenario {scenario_id!r} has invalid expected outcome")
        scenarios.append(
            CatalystScenario(
                id=scenario_id,
                question=str(item["question"]),
                expected_outcome=outcome,
                execute=bool(item.get("execute", outcome == "ready")),
                assertions=dict(item.get("assertions") or {}),
                tags=tuple(str(tag) for tag in item.get("tags", [])),
            )
        )
    if not scenarios:
        raise ValueError("Catalyst suite must contain scenarios")
    return CatalystSuite(
        id=str(payload["id"]),
        dataset_id=str(payload["datasetId"]),
        dataset_version=str(payload["datasetVersion"]),
        catalog_version=str(payload["catalogVersion"]),
        profile_id=str(payload["profileId"]),
        repetitions=repetitions,
        scenarios=tuple(scenarios),
    )


def _actual_outcome(query: dict[str, Any]) -> str:
    if query.get("contractVersion") == "catalyst.preview.v1":
        return "ready"
    return str(query.get("status") or "invalid_response")


def _parameter_values(query: dict[str, Any]) -> dict[str, Any]:
    return {
        str(parameter.get("name")): parameter.get("value")
        for parameter in query.get("parameters", [])
    }


def _record_evidence(table: dict[str, Any] | None) -> list[str]:
    if not table:
        return []
    columns = [item.get("name") for item in table.get("table", {}).get("columns", [])]
    if "patient_id" not in columns:
        return []
    patient_index = columns.index("patient_id")
    return sorted(
        {
            str(row[patient_index].get("value"))
            for row in table.get("table", {}).get("rows", [])
            if len(row) > patient_index and row[patient_index].get("value")
        }
    )


def evaluate_result(
    scenario: CatalystScenario,
    query: dict[str, Any],
    table: dict[str, Any] | None,
    *,
    query_status: int | None = None,
    table_status: int | None = None,
) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []

    def check(name: str, passed: bool, evidence: Any) -> None:
        assertions.append({"name": name, "passed": passed, "evidence": evidence})

    actual = _actual_outcome(query)
    check("outcome", actual == scenario.expected_outcome, actual)
    if query_status is not None:
        check("query_transport", query_status < 500, query_status)
    expected = scenario.assertions
    if actual == "ready":
        parameters = _parameter_values(query)
        for name, value in expected.get("parameterValues", {}).items():
            check(f"parameter.{name}", parameters.get(name) == value, parameters.get(name))
        required_parameter_values = list(expected.get("requiredParameterValues", []))
        if required_parameter_values:
            actual_parameter_values = list(parameters.values())
            check(
                "required_parameter_values",
                all(value in actual_parameter_values for value in required_parameter_values),
                actual_parameter_values,
            )
        columns = [item.get("name") for item in query.get("expectedColumns", [])]
        required_columns = list(expected.get("requiredColumns", []))
        if required_columns:
            check(
                "required_columns",
                all(column in columns for column in required_columns),
                columns,
            )
        exact_columns = expected.get("exactColumns")
        if exact_columns is not None:
            check("exact_columns", columns == list(exact_columns), columns)
        trace = query.get("reasoningTrace", {})
        required_stages = set(expected.get("requiredStages", []))
        if required_stages:
            check(
                "required_stages",
                required_stages <= set(trace.get("stages", [])),
                trace.get("stages", []),
            )
        for role, model in expected.get("roleModels", {}).items():
            actual_model = trace.get("roleModels", {}).get(role)
            check(f"role_model.{role}", actual_model == model, actual_model)
        lint_checks = [
            item
            for item in trace.get("checks", [])
            if str(item.get("name", "")).startswith("query_lint_attempt_")
        ]
        check(
            "deterministic_lint_present",
            bool(lint_checks),
            [item.get("name") for item in lint_checks],
        )
        if lint_checks:
            check(
                "final_lint_passed",
                lint_checks[-1].get("status") == "passed",
                lint_checks[-1],
            )
            check(
                "bounded_generation_attempts",
                len(lint_checks) <= int(expected.get("maxLintAttempts", 3)),
                len(lint_checks),
            )
    if table is not None:
        execution_contract_valid = (
            table_status == 200
            and table.get("contractVersion") == "catalyst.table.v1"
        )
        check(
            "execution_contract",
            execution_contract_valid,
            {
                "http_status": table_status,
                "contract_version": table.get("contractVersion"),
            },
        )
        if not execution_contract_valid:
            return assertions
        row_count = table.get("table", {}).get("rowCount", {})
        returned = int(row_count.get("returned", 0))
        if "minReturned" in expected:
            check("min_returned", returned >= int(expected["minReturned"]), returned)
        if "maxReturned" in expected:
            check("max_returned", returned <= int(expected["maxReturned"]), returned)
        expected_units = set(expected.get("expectedUnits", []))
        if expected_units:
            columns = [item.get("name") for item in table["table"]["columns"]]
            units = set()
            if "result_unit" in columns:
                unit_index = columns.index("result_unit")
                units = {
                    str(row[unit_index].get("value"))
                    for row in table["table"]["rows"]
                    if row[unit_index].get("value") is not None
                }
            check("expected_units", units == expected_units, sorted(units))
        numeric_minimums = expected.get("numericColumnMinExclusive", {})
        if numeric_minimums:
            columns = [item.get("name") for item in table["table"]["columns"]]
            for column_name, minimum in numeric_minimums.items():
                values: list[float] = []
                if column_name in columns:
                    column_index = columns.index(column_name)
                    for row in table["table"]["rows"]:
                        value = row[column_index].get("value")
                        if value is not None:
                            try:
                                values.append(float(value))
                            except (TypeError, ValueError):
                                values = []
                                break
                check(
                    f"numeric_min_exclusive.{column_name}",
                    bool(values) and all(value > float(minimum) for value in values),
                    {
                        "minimum_exclusive": minimum,
                        "observed_minimum": min(values) if values else None,
                    },
                )
        distinct_counts = expected.get("distinctColumnCount", {})
        if distinct_counts:
            columns = [item.get("name") for item in table["table"]["columns"]]
            for column_name, expected_count in distinct_counts.items():
                values: set[str] = set()
                if column_name in columns:
                    column_index = columns.index(column_name)
                    values = {
                        str(row[column_index].get("value"))
                        for row in table["table"]["rows"]
                        if row[column_index].get("value") is not None
                    }
                check(
                    f"distinct_count.{column_name}",
                    len(values) == int(expected_count),
                    len(values),
                )
    return assertions


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


def run_suite(
    *,
    suite_path: Path | str,
    client: CatalystTransport,
    output_dir: Path | str = "artifacts/catalyst-validation",
    project_root: Path | str = ".",
    scenario_ids: set[str] | None = None,
    repetitions: int | None = None,
) -> CatalystRunResult:
    suite_path = Path(suite_path)
    suite = load_suite(suite_path)
    selected = [
        scenario
        for scenario in suite.scenarios
        if scenario_ids is None or scenario.id in scenario_ids
    ]
    if not selected:
        raise ValueError("no Catalyst scenarios selected")
    repeat_count = repetitions if repetitions is not None else suite.repetitions
    if repeat_count < 1:
        raise ValueError("repetitions must be at least one")

    run_id = str(uuid4())
    run_dir = Path(output_dir) / run_id
    events_path = run_dir / "events.jsonl"
    results_path = run_dir / "results.jsonl"
    profiles = client.profiles()
    profile = next(
        (item for item in profiles.get("profiles", []) if item.get("id") == suite.profile_id),
        None,
    )
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component="catalyst-query-validation",
        git_sha=read_harness_git_sha(Path(project_root)),
        dataset_id=suite.dataset_id,
        dataset_version=suite.dataset_version,
        schema_mapping_version=suite.catalog_version,
        gen_ai_provider_name="lmstudio",
        decision_rationale=(
            "Measure governed text-to-SQL behavior through real Catalyst and "
            "Med-Agent Hub paths with deterministic result assertions."
        ),
        target_provenance=[
            {
                "target": "catalyst",
                "profile_id": suite.profile_id,
                "profile": profile,
                "suite_id": suite.id,
                "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
            }
        ],
    )
    write_manifest(run_dir / "run_manifest.json", manifest)
    append_event(
        events_path,
        {
            "event_type": "run",
            "run_id": run_id,
            "component": manifest.component,
            "suite_id": suite.id,
            "profile_id": suite.profile_id,
            "scenario_ids": [item.id for item in selected],
            "repetitions": repeat_count,
        },
    )

    result_count = 0
    passed_count = 0
    for scenario in selected:
        for repetition in range(1, repeat_count + 1):
            started = time.monotonic()
            try:
                query_status, query = client.submit(scenario.question, suite.profile_id)
            except Exception as error:
                query_status = 599
                query = {
                    "contractVersion": "harness.transport-error.v1",
                    "status": "transport_error",
                    "message": f"{type(error).__name__}: {error}",
                }
            latency_ms = round((time.monotonic() - started) * 1000)
            table_status = None
            table = None
            if _actual_outcome(query) == "ready" and scenario.execute:
                try:
                    table_status, table = client.execute(query)
                except Exception as error:
                    table_status = 599
                    table = {
                        "contractVersion": "harness.transport-error.v1",
                        "message": f"{type(error).__name__}: {error}",
                    }
            assertions = evaluate_result(
                scenario,
                query,
                table,
                query_status=query_status,
                table_status=table_status,
            )
            passed = all(item["passed"] for item in assertions)
            passed_count += int(passed)
            result_count += 1
            result = {
                "run_id": run_id,
                "suite_id": suite.id,
                "scenario_id": scenario.id,
                "repetition": repetition,
                "question": scenario.question,
                "tags": list(scenario.tags),
                "expected_outcome": scenario.expected_outcome,
                "actual_outcome": _actual_outcome(query),
                "passed": passed,
                "latency_ms": latency_ms,
                "query_http_status": query_status,
                "table_http_status": table_status,
                "assertions": assertions,
                "record_evidence": _record_evidence(table),
                "query": query,
                "table": table,
            }
            _append_jsonl(results_path, result)
            append_event(
                events_path,
                {
                    "event_type": "evaluation",
                    "run_id": run_id,
                    "scenario_id": scenario.id,
                    "repetition": repetition,
                    "profile_id": suite.profile_id,
                    "actual_outcome": result["actual_outcome"],
                    "passed": passed,
                    "latency_ms": latency_ms,
                    "trace_id": (
                        query.get("reasoningTrace", {}).get("traceId")
                        or query.get("provenance", {}).get("traceId")
                    ),
                    "assertions": assertions,
                    "record_evidence_count": len(result["record_evidence"]),
                },
            )
    return CatalystRunResult(
        run_id=run_id,
        run_dir=run_dir,
        result_count=result_count,
        passed_count=passed_count,
    )
