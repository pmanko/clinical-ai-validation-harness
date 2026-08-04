"""Repeatable real-path experiments for Catalyst governed text-to-SQL."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import requests

from ..common.jsonl import append_jsonl
from ..metadata import RunManifest, append_event, write_manifest
from ..submodules import (
    read_harness_git_sha,
    read_submodule_head,
    read_superproject_gitlink,
    submodule_worktree_dirty,
)


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
    provider_name: str
    dataset_overview: dict[str, Any]
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

    def dataset_overview(self) -> dict[str, Any]: ...

    def catalog(self) -> dict[str, Any]: ...

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

    def dataset_overview(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/v1/catalyst/dataset",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def catalog(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/v1/catalyst/workbench/catalog",
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
        "providerName",
        "datasetOverview",
        "repetitions",
        "scenarios",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Catalyst suite is missing: {', '.join(missing)}")
    repetitions = int(payload["repetitions"])
    if repetitions < 1:
        raise ValueError("Catalyst suite repetitions must be at least one")
    dataset_overview = payload["datasetOverview"]
    required_overview = {
        "patients",
        "results",
        "testTypes",
        "firstObservedDate",
        "lastObservedDate",
    }
    if not isinstance(dataset_overview, dict):
        raise ValueError("Catalyst suite datasetOverview must be an object")
    missing_overview = sorted(required_overview - dataset_overview.keys())
    if missing_overview:
        raise ValueError(
            "Catalyst suite datasetOverview is missing: " + ", ".join(missing_overview)
        )
    for field_name in ("patients", "results", "testTypes"):
        if not isinstance(dataset_overview[field_name], int):
            raise ValueError(
                f"Catalyst suite datasetOverview.{field_name} must be an integer"
            )
    for field_name in ("firstObservedDate", "lastObservedDate"):
        value = dataset_overview[field_name]
        if (
            not isinstance(value, str)
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None
        ):
            raise ValueError(
                f"Catalyst suite datasetOverview.{field_name} must be YYYY-MM-DD"
            )
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
        provider_name=str(payload["providerName"]),
        dataset_overview=dict(dataset_overview),
        repetitions=repetitions,
        scenarios=tuple(scenarios),
    )


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _target_provenance(project_root: Path) -> list[dict[str, Any]]:
    provenance: list[dict[str, Any]] = []
    for target_id, target_path in (
        ("catalyst", "targets/catalyst"),
        ("med-agent-hub", "targets/med-agent-hub"),
    ):
        reviewed_sha = read_superproject_gitlink(project_root, target_path)
        actual_sha = read_submodule_head(project_root, target_path)
        if reviewed_sha is None:
            raise ValueError(f"Harness has no reviewed gitlink for {target_path}")
        if actual_sha is None:
            raise ValueError(f"Harness target {target_path} is not initialized")
        if actual_sha != reviewed_sha:
            raise ValueError(
                f"Harness target {target_path} is at {actual_sha}; "
                f"the reviewed gitlink is {reviewed_sha}"
            )
        if submodule_worktree_dirty(project_root, target_path):
            raise ValueError(f"Harness target {target_path} has uncommitted changes")
        provenance.append(
            {
                "target_id": target_id,
                "target_source": "reviewed_submodule",
                "target_path": target_path,
                "target_reviewed_sha": reviewed_sha,
                "target_actual_sha": actual_sha,
                "target_dirty": False,
                "target_override": False,
                "target_metadata_version": 1,
                "evidence_status": "development",
                "decision_rationale": (
                    "The Catalyst validation run used the clean target checkout "
                    "at the harness-reviewed gitlink."
                ),
            }
        )
    return provenance


def _profile_provider(profile: dict[str, Any], suite: CatalystSuite) -> str:
    evidence = profile.get("profileEvidence")
    if isinstance(evidence, dict):
        if evidence.get("profileId") != suite.profile_id:
            raise ValueError(
                "Discovered profileEvidence.profileId does not match the suite"
            )
        providers = set()
        for role in ("writer", "reviewer"):
            role_evidence = evidence.get(role)
            provider = (
                role_evidence.get("providerId")
                if isinstance(role_evidence, dict)
                else None
            )
            if not isinstance(provider, str) or not provider:
                raise ValueError(
                    f"Discovered profileEvidence.{role}.providerId is missing"
                )
            providers.add(provider)
        if len(providers) != 1:
            raise ValueError(
                "Catalyst validation currently requires one provider across writer and "
                "reviewer roles"
            )
        provider_name = providers.pop()
    else:
        provenance = profile.get("provenance")
        if not isinstance(provenance, dict):
            raise ValueError(
                f"Catalyst profile {suite.profile_id!r} has no provenance"
            )
        if provenance.get("profileId") != suite.profile_id:
            raise ValueError("Discovered provenance.profileId does not match the suite")
        backend = provenance.get("backend")
        provider_name = (
            backend.get("provider") if isinstance(backend, dict) else None
        )
        if not isinstance(provider_name, str) or not provider_name:
            raise ValueError("Discovered provenance.backend.provider is missing")
    if provider_name != suite.provider_name:
        raise ValueError(
            f"Suite expected provider {suite.provider_name!r}, but profile discovery "
            f"reported {provider_name!r}"
        )
    return provider_name


def _runtime_identity(
    suite: CatalystSuite,
    dataset_overview: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    if dataset_overview.get("contractVersion") != "catalyst.dataset-overview.v1":
        raise ValueError("Gateway returned an unsupported Catalyst dataset overview")
    for field_name in ("datasetId", "dataSource", "pipelineRunId"):
        if (
            not isinstance(dataset_overview.get(field_name), str)
            or not dataset_overview[field_name]
        ):
            raise ValueError(f"Dataset overview {field_name} is required")
    if dataset_overview["datasetId"] != dataset_overview["pipelineRunId"]:
        raise ValueError("Dataset overview is not bound to its current pipeline run")

    for field_name in ("patients", "results", "testTypes"):
        actual = dataset_overview.get(field_name)
        expected = suite.dataset_overview[field_name]
        if actual != expected:
            raise ValueError(
                f"Dataset overview {field_name} is {actual!r}; expected {expected!r}"
            )
    for actual_name, expected_name in (
        ("firstObservedAt", "firstObservedDate"),
        ("lastObservedAt", "lastObservedDate"),
    ):
        actual = dataset_overview.get(actual_name)
        expected = suite.dataset_overview[expected_name]
        if not isinstance(actual, str) or actual[:10] != expected:
            raise ValueError(
                f"Dataset overview {actual_name} is {actual!r}; expected date {expected}"
            )

    if catalog.get("contractVersion") != "catalyst.workbench.editor-catalog.v1":
        raise ValueError("Gateway returned an unsupported Catalyst editor catalog")
    catalog_version = catalog.get("catalogVersion")
    if not isinstance(catalog_version, str) or not catalog_version:
        raise ValueError("Runtime Catalyst catalogVersion is required")
    allowed_version = re.fullmatch(
        rf"{re.escape(suite.catalog_version)}(?:\+schema\.[a-f0-9]{{16}})?",
        catalog_version,
    )
    if allowed_version is None:
        raise ValueError(
            f"Runtime catalog {catalog_version!r} does not derive from suite base "
            f"{suite.catalog_version!r}"
        )
    for field_name in ("schemaVersion", "dialect"):
        if not isinstance(catalog.get(field_name), str) or not catalog[field_name]:
            raise ValueError(f"Runtime Catalyst catalog {field_name} is required")
    if not isinstance(catalog.get("schemas"), list) or not catalog["schemas"]:
        raise ValueError("Runtime Catalyst catalog must contain readable schemas")

    return {
        "runtime_dataset_id": dataset_overview["datasetId"],
        "data_source": dataset_overview["dataSource"],
        "pipeline_run_id": dataset_overview["pipelineRunId"],
        "catalog_version": catalog_version,
        "catalog_schema_version": catalog["schemaVersion"],
        "catalog_dialect": catalog["dialect"],
        "dataset_overview": dataset_overview,
        "dataset_overview_sha256": _canonical_sha256(dataset_overview),
        "catalog": catalog,
        "catalog_sha256": _canonical_sha256(catalog),
    }


def _actual_outcome(query: dict[str, Any]) -> str:
    if query.get("contractVersion") == "catalyst.preview.v1":
        return "ready"
    return str(query.get("status") or "invalid_response")


def _parameter_values(query: dict[str, Any]) -> dict[str, Any]:
    return {
        str(parameter.get("name")): parameter.get("value")
        for parameter in query.get("parameters", [])
    }


def _record_evidence(table: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not table:
        return []
    columns = [item.get("name") for item in table.get("table", {}).get("columns", [])]
    patient_index = columns.index("patient_id") if "patient_id" in columns else None
    evidence = []
    for row_index, row in enumerate(table.get("table", {}).get("rows", [])):
        canonical_row = json.dumps(row, sort_keys=True, separators=(",", ":"))
        item: dict[str, Any] = {
            "row_index": row_index,
            "row_sha256": hashlib.sha256(canonical_row.encode("utf-8")).hexdigest(),
        }
        if (
            patient_index is not None
            and len(row) > patient_index
            and row[patient_index].get("value") is not None
        ):
            item["patient_id"] = str(row[patient_index]["value"])
        evidence.append(item)
    return evidence


def evaluate_result(
    scenario: CatalystScenario,
    query: dict[str, Any],
    table: dict[str, Any] | None,
    *,
    query_status: int | None = None,
    table_status: int | None = None,
    runtime_data_source: str | None = None,
    runtime_catalog_version: str | None = None,
    runtime_pipeline_run_id: str | None = None,
) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    query_columns: list[Any] = []

    def check(name: str, passed: bool, evidence: Any) -> None:
        assertions.append({"name": name, "passed": passed, "evidence": evidence})

    actual = _actual_outcome(query)
    check("outcome", actual == scenario.expected_outcome, actual)
    if query_status is not None:
        check("query_transport", query_status < 500, query_status)
    expected = scenario.assertions
    if actual == "ready":
        target = query.get("target", {})
        if runtime_data_source is not None:
            check(
                "query_data_source",
                target.get("dataSource") == runtime_data_source,
                target.get("dataSource"),
            )
        if runtime_catalog_version is not None:
            check(
                "query_catalog_version",
                target.get("catalogVersion") == runtime_catalog_version,
                target.get("catalogVersion"),
            )
        parameters = _parameter_values(query)
        for name, value in expected.get("parameterValues", {}).items():
            check(
                f"parameter.{name}", parameters.get(name) == value, parameters.get(name)
            )
        required_parameter_values = list(expected.get("requiredParameterValues", []))
        if required_parameter_values:
            actual_parameter_values = list(parameters.values())
            check(
                "required_parameter_values",
                all(
                    value in actual_parameter_values
                    for value in required_parameter_values
                ),
                actual_parameter_values,
            )
        query_columns = [item.get("name") for item in query.get("expectedColumns", [])]
        required_columns = list(expected.get("requiredColumns", []))
        if required_columns:
            check(
                "required_columns",
                all(column in query_columns for column in required_columns),
                query_columns,
            )
        exact_columns = expected.get("exactColumns")
        if exact_columns is not None:
            check(
                "exact_columns",
                query_columns == list(exact_columns),
                query_columns,
            )
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
            table_status == 200 and table.get("contractVersion") == "catalyst.table.v1"
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
        source = table.get("source", {})
        if runtime_data_source is not None:
            check(
                "table_data_source",
                source.get("dataSource") == runtime_data_source,
                source.get("dataSource"),
            )
        if runtime_catalog_version is not None:
            check(
                "table_catalog_version",
                source.get("catalogVersion") == runtime_catalog_version,
                source.get("catalogVersion"),
            )
        if runtime_pipeline_run_id is not None:
            freshness = source.get("freshness", {})
            check(
                "table_pipeline_run",
                freshness.get("pipelineRunId") == runtime_pipeline_run_id,
                freshness.get("pipelineRunId"),
            )
        table_columns = [item.get("name") for item in table["table"]["columns"]]
        check(
            "table_columns_match_preview",
            table_columns == query_columns,
            {"preview": query_columns, "table": table_columns},
        )
        required_columns = list(expected.get("requiredColumns", []))
        if required_columns:
            check(
                "table_required_columns",
                all(column in table_columns for column in required_columns),
                table_columns,
            )
        exact_columns = expected.get("exactColumns")
        if exact_columns is not None:
            check(
                "table_exact_columns",
                table_columns == list(exact_columns),
                table_columns,
            )
        row_count = table.get("table", {}).get("rowCount", {})
        returned = int(row_count.get("returned", 0))
        if "expectedReturned" in expected:
            check(
                "expected_returned",
                returned == int(expected["expectedReturned"]),
                returned,
            )
        if "expectedTruncated" in expected:
            check(
                "expected_truncated",
                row_count.get("truncated") is bool(expected["expectedTruncated"]),
                row_count.get("truncated"),
            )
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
    append_jsonl(path, payload)


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
    project_root = Path(project_root).resolve()
    suite_sha256 = hashlib.sha256(suite_path.read_bytes()).hexdigest()
    target_provenance = _target_provenance(project_root)
    catalyst_provenance = next(
        item for item in target_provenance if item["target_id"] == "catalyst"
    )
    hub_provenance = next(
        item for item in target_provenance if item["target_id"] == "med-agent-hub"
    )
    catalyst_provenance.update(
        {
            "suite_id": suite.id,
            "suite_sha256": suite_sha256,
            "dataset_id": suite.dataset_id,
            "dataset_version": suite.dataset_version,
            "dataset_overview": None,
            "dataset_overview_sha256": None,
            "catalog": None,
            "catalog_sha256": None,
        }
    )
    hub_provenance.update(
        {
            "profile_id": suite.profile_id,
            "profile": None,
            "profile_discovery_sha256": None,
            "provider_expected": suite.provider_name,
            "provider_name": None,
        }
    )
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component="catalyst-query-validation",
        git_sha=read_harness_git_sha(project_root),
        dataset_id=suite.dataset_id,
        dataset_version=suite.dataset_version,
        schema_mapping_version=suite.catalog_version,
        gen_ai_provider_name="unresolved",
        gen_ai_operation_name="chat",
        decision_rationale=(
            "Measure governed text-to-SQL behavior through real Catalyst and "
            "Med-Agent Hub paths with deterministic result assertions."
        ),
        target_provenance=target_provenance,
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
            "provider_expected": suite.provider_name,
            "scenario_ids": [item.id for item in selected],
            "repetitions": repeat_count,
        },
    )

    try:
        profiles = client.profiles()
    except Exception as error:
        append_event(
            events_path,
            {
                "event_type": "profile_discovery_failed",
                "run_id": run_id,
                "profile_id": suite.profile_id,
                "error_type": type(error).__name__,
                "message": str(error),
            },
        )
        raise
    profile = next(
        (
            item
            for item in profiles.get("profiles", [])
            if item.get("id") == suite.profile_id
        ),
        None,
    )
    if profile is None or profile.get("available") is not True:
        message = (
            f"Catalyst profile {suite.profile_id!r} is not advertised as available"
        )
        append_event(
            events_path,
            {
                "event_type": "profile_discovery_failed",
                "run_id": run_id,
                "profile_id": suite.profile_id,
                "error_type": "ProfileUnavailable",
                "message": message,
            },
        )
        raise ValueError(message)
    try:
        provider_name = _profile_provider(profile, suite)
    except ValueError as error:
        append_event(
            events_path,
            {
                "event_type": "profile_discovery_failed",
                "run_id": run_id,
                "profile_id": suite.profile_id,
                "error_type": type(error).__name__,
                "message": str(error),
            },
        )
        raise
    hub_provenance["profile"] = profile
    hub_provenance["profile_discovery_sha256"] = _canonical_sha256(profile)
    hub_provenance["provider_name"] = provider_name
    write_manifest(run_dir / "run_manifest.json", manifest)

    try:
        dataset_overview = client.dataset_overview()
        catalog = client.catalog()
        runtime_identity = _runtime_identity(suite, dataset_overview, catalog)
    except Exception as error:
        append_event(
            events_path,
            {
                "event_type": "runtime_identity_failed",
                "run_id": run_id,
                "error_type": type(error).__name__,
                "message": str(error),
            },
        )
        raise

    catalyst_provenance.update(
        {
            "dataset_overview": runtime_identity["dataset_overview"],
            "dataset_overview_sha256": runtime_identity["dataset_overview_sha256"],
            "catalog": runtime_identity["catalog"],
            "catalog_sha256": runtime_identity["catalog_sha256"],
            "runtime_dataset_id": runtime_identity["runtime_dataset_id"],
            "data_source": runtime_identity["data_source"],
            "pipeline_run_id": runtime_identity["pipeline_run_id"],
            "catalog_version": runtime_identity["catalog_version"],
            "catalog_schema_version": runtime_identity["catalog_schema_version"],
            "catalog_dialect": runtime_identity["catalog_dialect"],
        }
    )
    manifest.gen_ai_provider_name = provider_name
    manifest.schema_mapping_version = runtime_identity["catalog_version"]
    write_manifest(run_dir / "run_manifest.json", manifest)
    append_event(
        events_path,
        {
            "event_type": "runtime_identity",
            "run_id": run_id,
            "provider_name": provider_name,
            "runtime_dataset_id": runtime_identity["runtime_dataset_id"],
            "data_source": runtime_identity["data_source"],
            "pipeline_run_id": runtime_identity["pipeline_run_id"],
            "catalog_version": runtime_identity["catalog_version"],
            "catalog_schema_version": runtime_identity["catalog_schema_version"],
            "catalog_dialect": runtime_identity["catalog_dialect"],
            "dataset_overview_sha256": runtime_identity["dataset_overview_sha256"],
            "catalog_sha256": runtime_identity["catalog_sha256"],
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
                runtime_data_source=runtime_identity["data_source"],
                runtime_catalog_version=runtime_identity["catalog_version"],
                runtime_pipeline_run_id=runtime_identity["pipeline_run_id"],
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
