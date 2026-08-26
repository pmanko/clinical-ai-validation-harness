from __future__ import annotations

import hashlib
import json
import runpy
import sys
import threading
from datetime import date, datetime, time, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from harness.catalyst.notebook_validation import (
    writer_outcome,
    repetition_pair_is_unstable,
    is_infrastructure_failure,
    token_evidence_checks,
    HttpExchange,
    NotebookHttpClient,
    NotebookQuery,
    PostgresGoldExecutionChecker,
    PostgresReadOnlyChecker,
    _binding_value,
    _driver_sql,
    _evidence_checks,
    _find_forbidden_keys,
    _json_safe_value,
    _parse_timestamp,
    _require_discovery,
    load_notebook_suite,
    query_digest,
    run_notebook_suite,
)
from harness.common.jsonl import read_jsonl


ROOT = Path(__file__).resolve().parents[1]
PROFILE_ID = "catalyst-query-gemma-4-12b-qwen2.5-14b-checked"
WRITER_ONLY_PROFILE_ID = "catalyst-query-gemma-4-12b"


def _version(version_id: str, sql: str, *, parent: str | None = None) -> dict[str, Any]:
    query = NotebookQuery(sql=sql)
    return {
        "contractVersion": "catalyst.workbench.query-version.v1",
        "versionId": version_id,
        "sessionId": "session-1",
        "ordinal": int(version_id.removeprefix("version-")),
        "parentVersionId": parent,
        "authorType": "model" if parent is None else "human",
        "sql": sql,
        "parameters": [],
        "expectedColumns": [],
        "queryDigest": query_digest(query),
        "provenance": {},
        "createdAt": "2026-07-20T12:00:00Z",
    }


def _evidence(
    turn_id: str,
    instruction: str,
    role_models: tuple[str, str | None] = ("gemma-4-12b", "qwen2.5-14b"),
) -> dict[str, Any]:
    invocations = []
    roles = [("writer", role_models[0])]
    if role_models[1] is not None:
        roles.append(("reviewer", role_models[1]))
    for index, (role, model_id) in enumerate(roles, start=1):
        invocations.append(
            {
                "invocationId": f"invocation-{turn_id}-{index}",
                "role": role,
                "stage": "followup_generation",
                "attempt": 1,
                "providerId": "llama.cpp",
                "modelId": model_id,
                "configuration": {
                    "temperature": 0,
                    "dryMultiplier": 0,
                    "maxTokens": 2048,
                    "responseFormat": "catalyst_query_candidate_v1",
                },
                "startedAt": f"2026-07-20T12:00:0{index}.000Z",
                "endedAt": f"2026-07-20T12:00:0{index}.005Z",
                "durationMs": 5,
                "requestDigest": str(index) * 64,
                "responseDigest": str(index + 2) * 64,
                "failureDigest": None,
                "outcome": "succeeded",
            }
        )
    return {
        "contractVersion": "catalyst.workbench.generation-evidence.v1",
        "evidenceId": f"evidence-{turn_id}",
        "evidenceDigest": "a" * 64,
        "sessionId": "session-1",
        "turnId": turn_id,
        "turnKind": "initial" if turn_id == "turn-initial" else "followup",
        "origin": "recorded",
        "status": "completed",
        "instruction": instruction,
        "instructionDigest": "b" * 64,
        "editorSnapshot": None,
        "observedBase": None,
        "effectiveBaseVersion": None,
        "manualVersion": None,
        "revisionContext": {"instructionHistory": []},
        "dataset": {},
        "catalog": {},
        "policy": {},
        "outputSchema": {},
        "profile": {},
        "correlation": {},
        "selectionPolicy": {},
        "history": {},
        "hubRequest": {},
        "hubResponse": {},
        "invocations": invocations,
        "totalInvocationDurationMs": 5 * len(invocations),
        "candidates": [],
        "finalSelection": {"status": "completed"},
        "omissions": [],
        "prohibitedClasses": [],
        "createdAt": "2026-07-20T12:00:00Z",
        "updatedAt": "2026-07-20T12:00:03Z",
    }


class _WorkbenchState:
    def __init__(self) -> None:
        self.versions = [
            _version("version-1", "SELECT patient_id FROM analytics.lab_result_fact_v1")
        ]
        self.current = self.versions[0]
        self.executions: list[dict[str, Any]] = []
        self.followup_turn: dict[str, Any] | None = None
        self.followup_turns: list[dict[str, Any]] = []
        self.turn_requests: list[dict[str, Any]] = []
        self.turn_status_sequence: list[str] | None = None
        self.followup_failure_stage: str | None = None
        self.followup_failure_code = "reviewer_transport_failed"
        self.session_id = "session-1"
        self.session_ids: list[str] = []
        self.profile_digest: str | None = None
        # "ready" produces the base query; a terminal answer produces
        # none, exactly as the Gateway does when the writer asks or
        # declines on the opening question.
        self.base_outcome = "ready"
        self.base_failure_stage: str | None = None
        self.base_failure_code = "writer_transport_failed"
        # Which profiles discovery advertises; a comparison suite needs
        # every team it names to be offered.
        self.profile_ids: list[str] = [PROFILE_ID]
        # Per-profile role models, so a comparison suite's teams are told
        # apart by what they actually offer.
        self.profile_models: dict[str, tuple[str, str | None]] = {}
        self.current_profile_id = PROFILE_ID
        # A terminal answer that nonetheless left SQL in the session:
        # the exact contradiction the runner has to catch.
        self.leaves_a_query_behind = False
        self.turn_http_sequence: list[int] | None = None
        self.turn_error_code = "unavailable"
        self.turn_attempts = 0
        self.session_http_sequence: list[int] | None = None
        self.session_error_code = "unavailable"
        self.session_attempts = 0
        self.generation_http_sequence: list[int] | None = None
        self.generation_error_code = "unavailable"
        self.generation_attempts = 0
        self.requests: list[tuple[str, str]] = []
        self.session_requests: list[dict[str, Any]] = []
        self.posts: list[tuple[str, str, dict[str, Any]]] = []
        self.guidance: list[dict[str, Any]] = []

    def reset(self) -> None:
        """A new session starts a repetition from the same clean state.

        Each repetition gets its own session id, which is what the runner's
        new_session_isolation assertion is there to catch.
        """
        self.session_id = f"session-{len(self.session_ids) + 1}"
        self.session_ids.append(self.session_id)
        self.versions = (
            []
            if (
                self.base_outcome != "ready" or self.base_failure_stage is not None
            )
            and not self.leaves_a_query_behind
            else [
                _version(
                    "version-1",
                    "SELECT patient_id FROM analytics.lab_result_fact_v1",
                )
            ]
        )
        self.current = self.versions[0] if self.versions else None
        self.executions = []
        self.followup_turn = None
        self.followup_turns = []

    def session(self) -> dict[str, Any]:
        return {
            "contractVersion": "catalyst.workbench.session.v1",
            "sessionId": self.session_id,
            "question": "Show patient identifiers.",
            "profileId": PROFILE_ID,
            "datasetId": "pipeline-1",
            "datasetVersion": "pipeline-1",
            "catalogVersion": "analytics-catalog-v1+schema.1234567890abcdef",
            "currentVersionId": (
                self.current["versionId"] if self.current else None
            ),
            "browserState": {},
            "provenance": {},
            "status": self.base_outcome,
            "createdAt": "2026-07-20T12:00:00Z",
            "updatedAt": "2026-07-20T12:00:03Z",
            "versions": self.versions,
            "currentVersion": self.current,
            "validations": [],
            "latestValidation": None,
            "executions": self.executions,
        }

    def initial_turn(self) -> dict[str, Any]:
        turn = {
            "contractVersion": "catalyst.workbench.turn.v1",
            "sessionId": self.session_id,
            "turnId": "turn-initial",
            "ordinal": 1,
            "kind": "initial",
            "status": "completed",
        }
        if self.base_outcome != "ready":
            turn["status"] = "failed"
            turn["writerOutcome"] = self.base_outcome
            turn["outputVersions"] = []
            turn["selectedVersionId"] = None
            turn["failure"] = {
                "code": self.base_outcome,
                "message": "The data records no home address.",
            }
        if self.base_failure_stage is not None:
            turn["status"] = "failed"
            turn.pop("writerOutcome", None)
            turn["outputVersions"] = []
            turn["selectedVersionId"] = None
            turn["failure"] = {
                "stage": self.base_failure_stage,
                "code": self.base_failure_code,
                "message": "The model service was unavailable.",
            }
        return turn

    def timeline(self) -> dict[str, Any]:
        turns = [self.initial_turn(), *self.followup_turns]
        return {
            "contractVersion": "catalyst.workbench.turn.timeline.v1",
            "sessionId": self.session_id,
            "currentTurnId": turns[-1]["turnId"],
            "currentVersion": (
                {
                    "versionId": self.current["versionId"],
                    "queryDigest": self.current["queryDigest"],
                }
                if self.current
                else None
            ),
            "turns": turns,
        }


def _handler(state: _WorkbenchState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(length)) if length else {}

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            state.requests.append(("GET", self.path))
            path = self.path.split("?")[0]
            if path == "/v1/catalyst/query-options":
                self._send(
                    200,
                    {
                        "profiles": [
                            {
                                "id": profile_id,
                                "available": True,
                                "revisionCapable": True,
                                "role_models": {
                                    "query_generate": state.profile_models.get(
                                        profile_id, ("gemma-4-12b", "qwen2.5-14b")
                                    )[0],
                                    "query_review": state.profile_models.get(
                                        profile_id, ("gemma-4-12b", "qwen2.5-14b")
                                    )[1],
                                },
                                "provenance": {
                                    "profileConfigurationDigest": state.profile_digest
                                },
                            }
                            for profile_id in state.profile_ids
                        ]
                    },
                )
            elif path == "/v1/catalyst/dataset":
                self._send(
                    200,
                    {
                        "contractVersion": "catalyst.dataset-overview.v1",
                        "datasetId": "pipeline-1",
                        "pipelineRunId": "pipeline-1",
                    },
                )
            elif path == "/v1/catalyst/workbench/catalog":
                self._send(
                    200,
                    {
                        "contractVersion": "catalyst.workbench.editor-catalog.v1",
                        "catalogVersion": "analytics-catalog-v1+schema.1234567890abcdef",
                    },
                )
            elif self.path == f"/v1/catalyst/workbench/sessions/{state.session_id}":
                self._send(200, state.session())
            elif self.path == f"/v1/catalyst/workbench/sessions/{state.session_id}/turns":
                self._send(200, state.timeline())
            elif "/generation-evidence" in self.path:
                turn_id = self.path.split("/turns/")[1].split("/")[0]
                if state.generation_http_sequence:
                    status = state.generation_http_sequence[
                        min(
                            state.generation_attempts,
                            len(state.generation_http_sequence) - 1,
                        )
                    ]
                    state.generation_attempts += 1
                    if status != 200:
                        self._send(
                            status,
                            {"error": {"code": state.generation_error_code}},
                        )
                        return
                self._send(
                    200,
                    _evidence(
                        turn_id,
                        (
                            "Show patient identifiers."
                            if turn_id == "turn-initial"
                            else "Return only distinct patients."
                        ),
                        state.profile_models.get(
                            state.current_profile_id,
                            ("gemma-4-12b", "qwen2.5-14b"),
                        ),
                    ),
                )
            else:
                self._send(404, {"error": {"code": "not_found"}})

        def do_POST(self) -> None:  # noqa: N802
            state.requests.append(("POST", self.path))
            body = self._body()
            state.posts.append(("POST", self.path, body))
            if self.path.endswith("/guidance"):
                state.guidance.append(
                    {"entryId": f"g-{len(state.guidance) + 1}",
                     "text": body.get("text"), "source": "human",
                     "active": True}
                )
                payload = state.session()
                payload["guidance"] = list(state.guidance)
                self._send(201, payload)
                return
            if self.path == "/v1/catalyst/workbench/sessions":
                state.current_profile_id = body.get("profileId", PROFILE_ID)
                if state.session_http_sequence:
                    status = state.session_http_sequence[
                        min(
                            state.session_attempts,
                            len(state.session_http_sequence) - 1,
                        )
                    ]
                    state.session_attempts += 1
                    if status != 201:
                        state.session_requests.append(body)
                        self._send(
                            status,
                            {"error": {"code": state.session_error_code}},
                        )
                        return
                state.reset()
                state.session_requests.append(body)
                self._send(201, state.session())
            elif self.path == f"/v1/catalyst/workbench/sessions/{state.session_id}/versions":
                version = _version(
                    "version-2", body["sql"], parent=state.current["versionId"]
                )
                version["parameters"] = body["parameters"]
                version["expectedColumns"] = body.get("expectedColumns", [])
                version["queryDigest"] = query_digest(version)
                state.versions.append(version)
                state.current = version
                self._send(201, state.session())
            elif self.path.endswith("/validate"):
                self._send(
                    201,
                    {
                        "contractVersion": "catalyst.workbench.validation.v1",
                        "status": "valid",
                        "findings": [],
                    },
                )
            elif self.path.endswith("/execute"):
                version_id = body["versionId"]
                execution = {
                    "contractVersion": "catalyst.workbench.execution.v1",
                    "executionId": f"execution-{version_id}",
                    "versionId": version_id,
                    "status": "succeeded",
                    "result": {
                        "columns": [
                            {
                                "name": "patient_id",
                                "logicalType": "string",
                                "nullable": False,
                            }
                        ],
                        "rows": [[{"type": "string", "value": "patient-1"}]],
                        "rowCount": {
                            "returned": 1,
                            "truncated": False,
                            "truncationReason": None,
                        },
                        "warnings": [],
                    },
                }
                state.executions.append(execution)
                self._send(200, execution)
            elif self.path == f"/v1/catalyst/workbench/sessions/{state.session_id}/turns":
                state.current_profile_id = body.get("profileId", PROFILE_ID)
                state.turn_requests.append(body)
                if state.turn_http_sequence:
                    status = state.turn_http_sequence[
                        min(state.turn_attempts, len(state.turn_http_sequence) - 1)
                    ]
                    state.turn_attempts += 1
                    if status != 201:
                        self._send(
                            status,
                            {"error": {"code": state.turn_error_code}},
                        )
                        return
                ordinal = len(state.followup_turns) + 1
                suffix = "" if ordinal == 1 else f"-{ordinal}"
                if state.followup_failure_stage is not None:
                    current_ref = (
                        {
                            "versionId": state.current["versionId"],
                            "queryDigest": state.current["queryDigest"],
                        }
                        if state.current is not None
                        else None
                    )
                    state.followup_turn = {
                        "contractVersion": "catalyst.workbench.turn.v1",
                        "sessionId": state.session_id,
                        "turnId": f"turn-followup{suffix}",
                        "ordinal": 1 + ordinal,
                        "kind": "followup",
                        "status": "failed",
                        "snapshotClassification": "reused",
                        "manualVersion": None,
                        "profileSnapshot": {"profileId": state.current_profile_id},
                        "outputVersions": [],
                        "selectedVersionId": None,
                        "resultingCurrentVersion": current_ref,
                        "failure": {
                            "stage": state.followup_failure_stage,
                            "code": state.followup_failure_code,
                            "message": "The reviewer service was unavailable.",
                        },
                    }
                    state.followup_turns.append(state.followup_turn)
                    self._send(201, state.followup_turn)
                    return
                successor = _version(
                    f"version-{2 + ordinal}",
                    "SELECT DISTINCT patient_id FROM analytics.lab_result_fact_v1"
                    + ("" if ordinal == 1 else f" LIMIT {ordinal}"),
                    # A turn answering a question produces the session's
                    # first version, so it has no parent.
                    parent=(
                        state.current["versionId"] if state.current else None
                    ),
                )
                successor["authorType"] = "model_repair"
                state.versions.append(successor)
                state.current = successor
                state.followup_turn = {
                    "contractVersion": "catalyst.workbench.turn.v1",
                    "sessionId": state.session_id,
                    "turnId": f"turn-followup{suffix}",
                    "ordinal": 1 + ordinal,
                    "kind": "followup",
                    "status": (
                        state.turn_status_sequence[
                            max(len(state.session_ids) - 1, 0)
                            % len(state.turn_status_sequence)
                        ]
                        if state.turn_status_sequence
                        else "completed"
                    ),
                    "snapshotClassification": "reused",
                    "manualVersion": None,
                    "profileSnapshot": {"profileId": state.current_profile_id},
                    "outputVersions": [
                        {
                            "versionId": successor["versionId"],
                            "queryDigest": successor["queryDigest"],
                            "role": "reviewer",
                            "selected": True,
                        }
                    ],
                    "selectedVersionId": successor["versionId"],
                    "resultingCurrentVersion": {
                        "versionId": successor["versionId"],
                        "queryDigest": successor["queryDigest"],
                    },
                    "failure": None,
                }
                state.followup_turns.append(state.followup_turn)
                self._send(201, state.followup_turn)
            else:
                self._send(404, {"error": {"code": "not_found"}})

    return Handler


class _PassingPostgresChecker:
    def __init__(self) -> None:
        self.version_ids: list[str] = []

    def check(
        self, version: dict[str, Any], execution: dict[str, Any]
    ) -> dict[str, Any]:
        self.version_ids.append(version["versionId"])
        return {
            "contractVersion": "harness.catalyst-notebook.postgres-crosscheck.v1",
            "versionId": version["versionId"],
            "gatewayExecutionId": execution["executionId"],
            "passed": True,
        }


class _UnavailablePostgresChecker:
    def check(
        self, version: dict[str, Any], execution: dict[str, Any]
    ) -> dict[str, Any]:
        raise ConnectionError("database host is unavailable")


def test_real_http_client_runs_notebook_path_and_hashes_evidence(
    tmp_path: Path,
) -> None:
    suite = {
        "id": "notebook-test-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "unchanged",
                "family": "narrowing",
                "initialQuestion": "Show patient identifiers.",
                "initialProfileId": PROFILE_ID,
                "followupInstruction": "Return only distinct patients.",
                "followupProfileId": PROFILE_ID,
                "editorQuery": {
                    "sql": "SELECT patient_id FROM analytics.lab_result_fact_v1",
                    "parameters": [],
                    "expectedColumns": [],
                },
                "persistEditorQuery": True,
                "expectedBaseClassification": "reused",
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checker = _PassingPostgresChecker()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            postgres_checker=checker,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result.result_count == result.passed_count == 1
    assert result.skipped_count == 0
    assert checker.version_ids == ["version-2", "version-3"]
    assert ("POST", "/v1/catalyst/workbench/sessions/session-1/turns") in state.requests
    assert any(path.endswith("generation-evidence") for _, path in state.requests)

    # Streamed run/results files (harness/validate-shaped) let the shared
    # dashboard track a Catalyst run live; see run_notebook_suite's comment.
    events = read_jsonl(result.run_dir / "events.jsonl")
    result_rows = read_jsonl(result.run_dir / "results.jsonl")
    assert [e["event_type"] for e in events] == [
        "run",
        "backend_selected",
        "scenario",
        "turn",
        "turn",
        "version",
        "version",
        "execution",
        "execution",
        "evaluation",
    ]
    assert all(
        e["schema_version"] == "harness.catalyst-notebook.event.v1"
        for e in events
    )
    assert events[0]["cells"] == [
        {"scenario_id": "unchanged", "backend_id": PROFILE_ID, "turns": 1}
    ]
    assert events[0]["backend_ids"] == [PROFILE_ID]
    assert events[1]["backend_id"] == PROFILE_ID
    assert events[1]["label"] == "gemma-4-12b + qwen2.5-14b"
    assert len(result_rows) == 1
    row = result_rows[0]
    assert row["scenario_id"] == "unchanged"
    assert row["backend_id"] == PROFILE_ID
    assert row["turn"] == 1
    assert row["response"]["answer"] == (
        "SELECT DISTINCT patient_id FROM analytics.lab_result_fact_v1"
    )
    assert row["metrics"]["passed"] is True
    assert row["metrics"]["http_status"] == 200
    assert row["metrics"]["answer_chars"] == len(row["response"]["answer"])
    assert row["metrics"]["first_turn"] is True
    assert row["error"] is None

    index = json.loads((result.run_dir / "evidence-index.json").read_text())
    indexed_paths = {entry["path"] for entry in index["entries"]}
    assert {"rows.jsonl", "events.jsonl", "results.jsonl"} <= indexed_paths


class _PassingGoldChecker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def check(self, version: dict[str, Any], gold_check: Any) -> dict[str, Any]:
        self.calls.append((version["versionId"], gold_check.mode))
        return {
            "contractVersion": "harness.catalyst-notebook.gold-execution-match.v1",
            "mode": gold_check.mode,
            "versionId": version["versionId"],
            "passed": True,
        }


def test_gold_check_wiring_adds_assertion_and_evidence_when_configured(
    tmp_path: Path,
) -> None:
    scenario = dict(_suite_payload()["scenarios"][0])
    scenario["persistEditorQuery"] = True
    scenario["editorQuery"] = {
        "sql": "SELECT patient_id FROM analytics.lab_result_fact_v1",
        "parameters": [],
        "expectedColumns": [],
    }
    scenario["successorGoldCheck"] = {
        "mode": "count",
        "referenceSql": "SELECT patient_id FROM analytics.lab_result_fact_v1",
        "referenceParameters": [],
    }
    suite_path = _write_suite(tmp_path, _suite_payload(scenarios=[scenario]))
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    gold_checker = _PassingGoldChecker()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            gold_checker=gold_checker,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result.passed_count == result.result_count == 1
    assert gold_checker.calls == [("version-3", "count")]
    evidence_path = (
        result.run_dir
        / "scenarios/unchanged/repetition-01/16-gold-execution-match-successor.json"
    )
    assert evidence_path.exists()
    evidence = json.loads(evidence_path.read_text())
    assert evidence["passed"] is True
    results = json.loads((result.run_dir / "results.json").read_text())
    names = {item["name"] for item in results["results"][0]["assertions"]}
    assert "successor_gold_execution_match" in names


def test_base_gold_check_wiring_adds_assertion_and_evidence_when_configured(
    tmp_path: Path,
) -> None:
    scenario = dict(_suite_payload()["scenarios"][0])
    scenario["persistEditorQuery"] = True
    scenario["editorQuery"] = {
        "sql": "SELECT patient_id FROM analytics.lab_result_fact_v1",
        "parameters": [],
        "expectedColumns": [],
    }
    scenario["baseGoldCheck"] = {
        "mode": "count",
        "referenceSql": "SELECT patient_id FROM analytics.lab_result_fact_v1",
    }
    suite_path = _write_suite(tmp_path, _suite_payload(scenarios=[scenario]))
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    gold_checker = _PassingGoldChecker()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            gold_checker=gold_checker,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert ("version-2", "count") in gold_checker.calls
    evidence_path = (
        result.run_dir
        / "scenarios/unchanged/repetition-01/15-gold-execution-match-base.json"
    )
    assert evidence_path.exists()
    results = json.loads((result.run_dir / "results.json").read_text())
    names = {item["name"] for item in results["results"][0]["assertions"]}
    assert "base_gold_execution_match" in names


def test_gold_check_absent_by_default_when_not_configured(tmp_path: Path) -> None:
    suite_path = _write_suite(tmp_path, _suite_payload())
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    gold_checker = _PassingGoldChecker()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            gold_checker=gold_checker,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert gold_checker.calls == []
    results = json.loads((result.run_dir / "results.json").read_text())
    names = {item["name"] for item in results["results"][0]["assertions"]}
    assert "successor_gold_execution_match" not in names
    assert "base_gold_execution_match" not in names

    index_path = result.run_dir / "evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in index["entries"]:
        content = (result.run_dir / entry["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
    index_digest = hashlib.sha256(index_path.read_bytes()).hexdigest()
    assert (
        (result.run_dir / "evidence-index.sha256").read_text().startswith(index_digest)
    )


def test_query_digest_matches_the_shared_rfc8785_golden_vector() -> None:
    assert query_digest(NotebookQuery(sql="SELECT 1")) == (
        "82d9696f92e64acb0c4edba843633c97eb23fd3f22887d93755eb86971855105"
    )


def test_postgres_crosscheck_uses_read_only_transaction_and_record_digests(
    monkeypatch,
) -> None:
    import psycopg

    statements: list[tuple[str, object]] = []

    class Column:
        name = "patient_id"

    class Cursor:
        description = [Column()]

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, statement: str, parameters: object = None) -> None:
            statements.append((statement, parameters))

        def fetchmany(self, count: int) -> list[tuple[str]]:
            assert count == 101
            return [("patient-1",)]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def cursor(self) -> Cursor:
            return Cursor()

    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: Connection())
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_id FROM analytics.lab_result_fact_v1 "
        "WHERE test_name = :test_name",
        "parameters": [
            {
                "name": "test_name",
                "type": "string",
                "source": "human",
                "value": "Viral Load",
            }
        ],
    }
    execution = {
        "executionId": "execution-1",
        "result": {
            "columns": [{"name": "patient_id"}],
            "rows": [[{"type": "string", "value": "patient-1"}]],
            "rowCount": {"returned": 1, "truncated": False},
        },
    }

    result = PostgresReadOnlyChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, execution)

    assert result["passed"] is True
    assert result["readOnlyTransaction"] is True
    assert result["database"] == "catalyst_analytics"
    assert "secret" not in json.dumps(result)
    assert statements[0] == ("SET TRANSACTION READ ONLY", None)
    assert "%(test_name)s" in statements[2][0]
    assert statements[2][1] == {"test_name": "Viral Load"}


class _GoldCheckCursor:
    """Stub cursor returning canned rows keyed by a marker substring in the
    executed SQL, so a single instance can serve the model + reference
    queries a gold-execution-match check issues in sequence."""

    def __init__(
        self, rows_by_marker: dict[str, tuple[list[str], list[tuple]]]
    ) -> None:
        self.rows_by_marker = rows_by_marker
        self.statements: list[tuple[str, object]] = []
        self._columns: list[str] = []
        self._rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, statement: str, parameters: object = None) -> None:
        self.statements.append((statement, parameters))
        for marker, (columns, rows) in self.rows_by_marker.items():
            if marker in statement:
                self._columns, self._rows = columns, rows
                return

    @property
    def description(self):
        class Column:
            def __init__(self, name: str) -> None:
                self.name = name

        return [Column(name) for name in self._columns]

    def fetchmany(self, count: int) -> list[tuple]:
        return self._rows


def _gold_check_connection(
    monkeypatch, rows_by_marker: dict[str, tuple[list[str], list[tuple]]]
):
    import psycopg

    cursor = _GoldCheckCursor(rows_by_marker)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def cursor(self):
            return cursor

    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: Connection())
    return cursor


def test_gold_execution_checker_count_mode_compares_row_counts(monkeypatch) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    cursor = _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["patient_id"], [("p1",), ("p2",), ("p3",)]),
            "reference_table": (["patient_id"], [("p1",), ("p2",), ("p3",)]),
        },
    )
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_id FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="count", reference_sql="SELECT patient_id FROM reference_table"
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is True
    assert result["mode"] == "count"
    assert result["modelRowCount"] == 3
    assert result["referenceRowCount"] == 3
    assert "secret" not in json.dumps(result)
    assert cursor.statements[0] == ("SET TRANSACTION READ ONLY", None)


def test_gold_execution_checker_count_mode_detects_mismatch(monkeypatch) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["patient_id"], [("p1",), ("p2",)]),
            "reference_table": (["patient_id"], [("p1",), ("p2",), ("p3",)]),
        },
    )
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_id FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="count", reference_sql="SELECT patient_id FROM reference_table"
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is False
    assert result["modelRowCount"] == 2
    assert result["referenceRowCount"] == 3


def test_gold_execution_checker_row_set_mode_detects_wrong_predicate(
    monkeypatch,
) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    # The model's rows agree in COUNT with the reference (3 each) but include a
    # row the reference predicate excludes — a wrong-predicate bug a count-only
    # check would miss entirely.
    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["observation_id"], [("o1",), ("o2",), ("o4",)]),
            "reference_table": (["observation_id"], [("o1",), ("o2",), ("o3",)]),
        },
    )
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT observation_id FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="row_set",
        reference_sql="SELECT observation_id FROM reference_table",
        match_columns=("observation_id",),
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is False
    assert result["missingFromModelSample"] == [["o3"]]
    assert result["extraInModelSample"] == [["o4"]]


def test_gold_execution_checker_row_set_mode_passes_on_exact_match(monkeypatch) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["observation_id"], [("o2",), ("o1",)]),
            "reference_table": (["observation_id"], [("o1",), ("o2",)]),
        },
    )
    version = {
        "versionId": "v",
        "queryDigest": "a" * 64,
        "sql": "SELECT observation_id FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="row_set",
        reference_sql="SELECT observation_id FROM reference_table",
        match_columns=("observation_id",),
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is True


def test_gold_execution_checker_aggregate_by_key_mode_detects_value_mismatch(
    monkeypatch,
) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (
                ["observed_month", "result_count", "median_result_value"],
                [("2026-01", 10, 5.0), ("2026-02", 20, 6.0)],
            ),
            "reference_table": (
                ["observed_month", "result_count", "median_result_value"],
                [("2026-01", 10, 5.0), ("2026-02", 21, 6.005)],
            ),
        },
    )
    version = {
        "versionId": "v",
        "queryDigest": "a" * 64,
        "sql": "SELECT observed_month, result_count, median_result_value FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="aggregate_by_key",
        reference_sql=(
            "SELECT observed_month, result_count, median_result_value FROM reference_table"
        ),
        key_columns=("observed_month",),
        value_columns={
            "result_count": {"tolerance": 0},
            "median_result_value": {"tolerance": 0.01},
        },
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    # median_result_value is within tolerance (0.005 <= 0.01) so only the
    # exact-tolerance result_count column should be flagged.
    assert result["passed"] is False
    assert len(result["valueMismatches"]) == 1
    assert result["valueMismatches"][0]["column"] == "result_count"
    assert result["valueMismatches"][0]["key"] == ["2026-02"]


def test_gold_execution_checker_aggregate_by_key_mode_detects_missing_key(
    monkeypatch,
) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["observed_month", "result_count"], [("2026-01", 10)]),
            "reference_table": (
                ["observed_month", "result_count"],
                [("2026-01", 10), ("2026-02", 20)],
            ),
        },
    )
    version = {
        "versionId": "v",
        "queryDigest": "a" * 64,
        "sql": "SELECT observed_month, result_count FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="aggregate_by_key",
        reference_sql="SELECT observed_month, result_count FROM reference_table",
        key_columns=("observed_month",),
        value_columns={"result_count": {"tolerance": 0}},
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is False
    assert result["missingKeys"] == [["2026-02"]]
    assert result["extraKeys"] == []


def test_gold_execution_checker_scalar_mode_compares_single_value(monkeypatch) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["patient_count"], [(96,)]),
            "reference_table": (["patient_count"], [(96,)]),
        },
    )
    version = {
        "versionId": "v",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_count FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="scalar",
        reference_sql="SELECT patient_count FROM reference_table",
        value_column="patient_count",
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is True
    assert result["modelValue"] == 96
    assert result["referenceValue"] == 96


def test_gold_execution_checker_scalar_mode_detects_wrong_value(monkeypatch) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["patient_count"], [(90,)]),
            "reference_table": (["patient_count"], [(96,)]),
        },
    )
    version = {
        "versionId": "v",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_count FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="scalar",
        reference_sql="SELECT patient_count FROM reference_table",
        value_column="patient_count",
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is False
    assert result["modelValue"] == 90
    assert result["referenceValue"] == 96


def test_values_match_handles_none_and_non_numeric_fallback() -> None:
    from harness.catalyst.notebook_validation import _values_match

    assert _values_match(None, None, 0) is True
    assert _values_match(None, 1, 0) is False
    assert _values_match(1, None, 0) is False
    assert _values_match("a", "a", 0) is True
    assert _values_match("a", "b", 0) is False
    assert _values_match(1.0, 1.0000001, 0.001) is True


def test_gold_execution_checker_rejects_unsupported_mode(monkeypatch) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["x"], [(1,)]),
            "reference_table": (["x"], [(1,)]),
        },
    )
    version = {
        "versionId": "v",
        "queryDigest": "a" * 64,
        "sql": "SELECT x FROM model_table",
        "parameters": [],
    }
    # Constructed directly (bypassing the loader's mode validation) to exercise
    # the checker's own defense-in-depth guard against an unsupported mode.
    gold_check = NotebookGoldCheck(
        mode="unsupported", reference_sql="SELECT x FROM reference_table"
    )

    with pytest.raises(ValueError, match="unsupported gold check mode"):
        PostgresGoldExecutionChecker(
            "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
        ).check(version, gold_check)


def test_gold_execution_checker_enforces_max_rows_safety_cap(monkeypatch) -> None:
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {"model_table": (["x"], [(i,) for i in range(5)])},
    )
    version = {
        "versionId": "v",
        "queryDigest": "a" * 64,
        "sql": "SELECT x FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="count", reference_sql="SELECT x FROM model_table"
    )

    with pytest.raises(ValueError, match="safety cap"):
        PostgresGoldExecutionChecker(
            "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics",
            max_rows=2,
        ).check(version, gold_check)


def test_manual_failure_family_is_explicitly_skipped_by_default(tmp_path: Path) -> None:
    suite = {
        "id": "notebook-manual-test-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "bounded-failure",
                "family": "hub-tool-failure",
                "initialQuestion": "Show results.",
                "initialProfileId": PROFILE_ID,
                "followupInstruction": "Narrow results.",
                "followupProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
                "expectedTurnStatus": "failed",
                "manualOnly": True,
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result.result_count == result.passed_count == 0
    assert result.skipped_count == 1
    assert all("/sessions" not in path for _, path in state.requests)


def _suite_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "notebook-test-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "unchanged",
                "family": "narrowing",
                "initialQuestion": "Show patient identifiers.",
                "initialProfileId": PROFILE_ID,
                "followupInstruction": "Return only distinct patients.",
                "followupProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
            }
        ],
    }
    payload.update(overrides)
    return payload


def _write_suite(tmp_path: Path, payload: dict[str, Any]) -> Path:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(payload), encoding="utf-8")
    return suite_path


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"repetitions": 0}, "repetitions must be at least one"),
        ({"scenarios": []}, "must contain scenarios"),
    ],
)
def test_suite_loader_rejects_invalid_suite_level_fields(
    tmp_path: Path, overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        load_notebook_suite(_write_suite(tmp_path, _suite_payload(**overrides)))


@pytest.mark.parametrize(
    "payload",
    [
        _suite_payload(id="catalyst-phase1-comparison-v2", repetitions=2),
        _suite_payload(
            id="catalyst-phase1-comparison-v2",
            extendedRepetitions=5,
        ),
        _suite_payload(
            id="catalyst-phase1-comparison-v2",
            scenarios=[
                {**_suite_payload()["scenarios"][0], "repetitions": 2}
            ],
        ),
    ],
)
def test_phase1_repeated_measures_cannot_repeat_selected_cells(
    tmp_path: Path,
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="separate full-suite runs"):
        load_notebook_suite(_write_suite(tmp_path, payload))


def test_phase1_repetition_override_cannot_repeat_selected_cells(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _suite_payload(id="catalyst-phase1-comparison-v2")
    suite_path = _write_suite(tmp_path, suite)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError, match="repetition override must be one"):
            run_notebook_suite(
                suite_path=suite_path,
                client=NotebookHttpClient(
                    f"http://127.0.0.1:{server.server_port}"
                ),
                output_dir=tmp_path / "artifacts",
                project_root=ROOT,
                repetitions=2,
                provenance_loader=lambda _: [],
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert state.requests == []


def test_phase1_run_cannot_select_only_part_of_the_frozen_suite(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    base = _suite_payload()["scenarios"][0]
    suite = _suite_payload(
        id="catalyst-phase1-comparison-v2",
        scenarios=[{**base, "id": "first"}, {**base, "id": "second"}],
    )

    with pytest.raises(ValueError, match="complete frozen scenario set"):
        _run_against_fake(
            tmp_path,
            suite,
            state,
            scenario_ids={"first"},
        )

    assert state.requests == []


def test_suite_loader_allows_omitted_or_null_writer_only_reviewer(
    tmp_path: Path,
) -> None:
    base = _suite_payload()["scenarios"][0]
    null_reviewer_profile_id = "writer-only-with-explicit-null"
    suite = load_notebook_suite(
        _write_suite(
            tmp_path,
            _suite_payload(
                profiles={
                    WRITER_ONLY_PROFILE_ID: {"writerModelId": "gemma-4-12b"},
                    null_reviewer_profile_id: {
                        "writerModelId": "gemma-4-12b",
                        "reviewerModelId": None,
                    },
                },
                scenarios=[
                    {
                        **base,
                        "initialProfileId": WRITER_ONLY_PROFILE_ID,
                        "followupProfileId": null_reviewer_profile_id,
                    }
                ],
            ),
        )
    )

    assert suite.profiles[WRITER_ONLY_PROFILE_ID]["reviewerModelId"] is None
    assert suite.profiles[null_reviewer_profile_id]["reviewerModelId"] is None


def test_committed_t094_suite_uses_current_profiles_and_switches_per_turn() -> None:
    suite = load_notebook_suite(
        ROOT
        / "datasets/validation/catalyst/catalyst-notebook-t094-v1.json"
    )

    assert suite.profiles == {
        WRITER_ONLY_PROFILE_ID: {
            "writerModelId": "gemma-4-12b",
            "reviewerModelId": None,
        },
        PROFILE_ID: {
            "writerModelId": "gemma-4-12b",
            "reviewerModelId": "qwen2.5-14b",
        },
    }
    aggregation = next(
        scenario
        for scenario in suite.scenarios
        if scenario.id == "aggregation-dirty-base-profile-switch"
    )
    assert aggregation.initial_profile_id == WRITER_ONLY_PROFILE_ID
    assert aggregation.followup_profile_id == PROFILE_ID


def test_report_labels_writer_only_profile_without_inventing_a_reviewer() -> None:
    from harness.catalyst.report import _methods_section

    html = _methods_section(
        {
            "profiles": {
                WRITER_ONLY_PROFILE_ID: {"writerModelId": "gemma-4-12b"},
                PROFILE_ID: {
                    "writerModelId": "gemma-4-12b",
                    "reviewerModelId": "qwen2.5-14b",
                },
            }
        },
        {
            "passedCount": 1,
            "resultCount": 1,
            "skippedCount": 0,
            "results": [],
        },
        [],
    )

    assert "— (writer only)" in html
    assert "reviewed profiles also invoke their configured reviewer" in html
    assert ">None<" not in html


def test_suite_loader_rejects_invalid_scenario_fields(tmp_path: Path) -> None:
    base = _suite_payload()["scenarios"][0]
    duplicated = _suite_payload(scenarios=[dict(base), dict(base)])
    with pytest.raises(ValueError, match="duplicate notebook scenario id"):
        load_notebook_suite(_write_suite(tmp_path, duplicated))

    bad_classification = _suite_payload(
        scenarios=[{**base, "expectedBaseClassification": "guessed"}]
    )
    with pytest.raises(ValueError, match="invalid classification"):
        load_notebook_suite(_write_suite(tmp_path, bad_classification))

    bad_status = _suite_payload(scenarios=[{**base, "expectedTurnStatus": "poked"}])
    with pytest.raises(ValueError, match="invalid turn status"):
        load_notebook_suite(_write_suite(tmp_path, bad_status))

    bad_repetitions = _suite_payload(scenarios=[{**base, "repetitions": 0}])
    with pytest.raises(ValueError, match="repetitions must be positive"):
        load_notebook_suite(_write_suite(tmp_path, bad_repetitions))

    unknown_profile = _suite_payload(
        scenarios=[{**base, "followupProfileId": "missing-profile"}]
    )
    with pytest.raises(ValueError, match="unknown profile"):
        load_notebook_suite(_write_suite(tmp_path, unknown_profile))


def _gold_check_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": "count",
        "referenceSql": "SELECT patient_id FROM analytics.lab_result_fact_v1",
        "referenceParameters": [],
    }
    payload.update(overrides)
    return payload


def test_suite_loader_parses_gold_checks_by_mode(tmp_path: Path) -> None:
    base = _suite_payload()["scenarios"][0]

    count_scenario = {**base, "successorGoldCheck": _gold_check_payload()}
    suite = load_notebook_suite(
        _write_suite(tmp_path, _suite_payload(scenarios=[count_scenario]))
    )
    check = suite.scenarios[0].successor_gold_check
    assert check is not None
    assert check.mode == "count"
    assert check.reference_sql == "SELECT patient_id FROM analytics.lab_result_fact_v1"
    assert suite.scenarios[0].base_gold_check is None

    row_set_scenario = {
        **base,
        "baseGoldCheck": _gold_check_payload(
            mode="row_set", matchColumns=["observation_id"]
        ),
    }
    suite = load_notebook_suite(
        _write_suite(tmp_path, _suite_payload(scenarios=[row_set_scenario]))
    )
    check = suite.scenarios[0].base_gold_check
    assert check.mode == "row_set"
    assert check.match_columns == ("observation_id",)

    aggregate_scenario = {
        **base,
        "successorGoldCheck": _gold_check_payload(
            mode="aggregate_by_key",
            keyColumns=["observed_month"],
            valueColumns={"result_count": {"tolerance": 0}},
        ),
    }
    suite = load_notebook_suite(
        _write_suite(tmp_path, _suite_payload(scenarios=[aggregate_scenario]))
    )
    check = suite.scenarios[0].successor_gold_check
    assert check.mode == "aggregate_by_key"
    assert check.key_columns == ("observed_month",)
    assert check.value_columns == {"result_count": {"tolerance": 0}}

    scalar_scenario = {
        **base,
        "successorGoldCheck": _gold_check_payload(
            mode="scalar", valueColumn="patient_count"
        ),
    }
    suite = load_notebook_suite(
        _write_suite(tmp_path, _suite_payload(scenarios=[scalar_scenario]))
    )
    check = suite.scenarios[0].successor_gold_check
    assert check.mode == "scalar"
    assert check.value_column == "patient_count"


def test_suite_loader_rejects_invalid_gold_checks(tmp_path: Path) -> None:
    base = _suite_payload()["scenarios"][0]

    bad_mode = {**base, "successorGoldCheck": _gold_check_payload(mode="guessed")}
    with pytest.raises(ValueError, match="unknown gold check mode"):
        load_notebook_suite(
            _write_suite(tmp_path, _suite_payload(scenarios=[bad_mode]))
        )

    row_set_missing_columns = {
        **base,
        "successorGoldCheck": _gold_check_payload(mode="row_set"),
    }
    with pytest.raises(ValueError, match="row_set gold check requires matchColumns"):
        load_notebook_suite(
            _write_suite(tmp_path, _suite_payload(scenarios=[row_set_missing_columns]))
        )

    aggregate_missing_keys = {
        **base,
        "successorGoldCheck": _gold_check_payload(mode="aggregate_by_key"),
    }
    with pytest.raises(
        ValueError, match="aggregate_by_key gold check requires keyColumns"
    ):
        load_notebook_suite(
            _write_suite(tmp_path, _suite_payload(scenarios=[aggregate_missing_keys]))
        )

    scalar_missing_column = {
        **base,
        "successorGoldCheck": _gold_check_payload(mode="scalar"),
    }
    with pytest.raises(ValueError, match="scalar gold check requires valueColumn"):
        load_notebook_suite(
            _write_suite(tmp_path, _suite_payload(scenarios=[scalar_missing_column]))
        )

    write_verb_reference = {
        **base,
        "successorGoldCheck": _gold_check_payload(
            referenceSql="DELETE FROM analytics.lab_result_fact_v1"
        ),
    }
    with pytest.raises(ValueError, match="must be read-only"):
        load_notebook_suite(
            _write_suite(tmp_path, _suite_payload(scenarios=[write_verb_reference]))
        )


def test_run_suite_rejects_empty_selection_and_bad_repetitions(
    tmp_path: Path,
) -> None:
    suite_path = _write_suite(tmp_path, _suite_payload())
    with pytest.raises(ValueError, match="no notebook scenarios selected"):
        run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient("http://127.0.0.1:1"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            scenario_ids={"absent"},
            provenance_loader=lambda _: [],
        )
    with pytest.raises(ValueError, match="repetitions must be at least one"):
        run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient("http://127.0.0.1:1"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            repetitions=0,
            provenance_loader=lambda _: [],
        )


class _StubClient:
    """Minimal transport for exercising runner failure paths without HTTP."""

    def __init__(
        self,
        *,
        session_status: int = 201,
        session_body: dict[str, Any] | None = None,
    ) -> None:
        self.session_status = session_status
        self.session_body = (
            session_body
            if session_body is not None
            else {"sessionId": "session-1", "currentVersion": None}
        )

    def _ok(self, body: dict[str, Any], status: int = 200) -> HttpExchange:
        return HttpExchange(
            method="GET",
            path="/",
            status_code=status,
            request_body=None,
            response_body=body,
            elapsed_ms=1,
        )

    def profiles(self) -> HttpExchange:
        return self._ok({"profiles": [_discovery_profile()]})

    def dataset_overview(self) -> HttpExchange:
        return self._ok(
            {
                "contractVersion": "catalyst.dataset-overview.v1",
                "datasetId": "pipeline-1",
                "pipelineRunId": "pipeline-1",
            }
        )

    def catalog(self) -> HttpExchange:
        return self._ok({"catalogVersion": "analytics-catalog-v1+schema.abc"})

    def create_session(self, question: str, profile_id: str) -> HttpExchange:
        return self._ok(self.session_body, status=self.session_status)

    def get_session(self, session_id: str) -> HttpExchange:
        return self._ok({})

    def get_turns(self, session_id: str) -> HttpExchange:
        return self._ok({"turns": []})

    def generation_evidence(self, session_id: str, turn_id: str) -> HttpExchange:
        return self._ok({})

    def save_version(self, session_id: str, query: Any, parent: Any) -> HttpExchange:
        return self._ok({}, status=500)

    def validate_version(self, version_id: str) -> HttpExchange:
        return self._ok({}, status=500)

    def execute_version(self, version: dict[str, Any]) -> HttpExchange:
        return self._ok({}, status=500)

    def create_turn(self, session_id: str, **kwargs: Any) -> HttpExchange:
        return self._ok({}, status=500)


def test_failed_session_creation_short_circuits_the_scenario(tmp_path: Path) -> None:
    suite_path = _write_suite(tmp_path, _suite_payload())
    result = run_notebook_suite(
        suite_path=suite_path,
        client=_StubClient(session_status=503, session_body={}),
        output_dir=tmp_path / "artifacts",
        project_root=ROOT,
        provenance_loader=lambda _: [],
    )
    assert result.passed_count == 0
    assert result.complete is False
    assert not (result.run_dir / "results.json").exists()
    row = json.loads((result.run_dir / "rows.jsonl").read_text())
    assert row["status"] == "infrastructure_failed"
    assert row["httpStatus"] == 503


def test_missing_base_version_short_circuits_the_scenario(tmp_path: Path) -> None:
    suite_path = _write_suite(tmp_path, _suite_payload())
    result = run_notebook_suite(
        suite_path=suite_path,
        client=_StubClient(),
        output_dir=tmp_path / "artifacts",
        project_root=ROOT,
        provenance_loader=lambda _: [],
    )
    assert result.passed_count == 0
    results = json.loads((result.run_dir / "results.json").read_text())
    assertions = {
        item["name"]: item["passed"] for item in results["results"][0]["assertions"]
    }
    assert assertions["base_version_available"] is False


class _CrashingClient:
    """Raises on the Nth session call, simulating an unexpected code crash."""

    def __init__(self, delegate: NotebookHttpClient, *, crash_on_call: int) -> None:
        self.delegate = delegate
        self._create_session_calls = 0
        self._crash_on_call = crash_on_call

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    def create_session(self, question: str, profile_id: str) -> HttpExchange:
        self._create_session_calls += 1
        if self._create_session_calls == self._crash_on_call:
            raise RuntimeError("simulated transport failure")
        return self.delegate.create_session(question, profile_id)


def test_results_jsonl_streams_incrementally_and_survives_a_mid_run_crash(
    tmp_path: Path,
) -> None:
    """An unexpected code crash must not erase already streamed evidence.

    Recognized HTTP and transport interruptions finalize an evidence index;
    this raw exception exercises the fallback for an unclassified process
    failure before normal finalization.
    """
    suite_path = _write_suite(
        tmp_path,
        _suite_payload(
            scenarios=[
                {**_suite_payload()["scenarios"][0], "id": "first"},
                {**_suite_payload()["scenarios"][0], "id": "second"},
            ]
        ),
    )
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = _CrashingClient(
        NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
        crash_on_call=2,
    )
    try:
        with pytest.raises(RuntimeError, match="simulated transport failure"):
            run_notebook_suite(
                suite_path=suite_path,
                client=client,
                output_dir=tmp_path / "artifacts",
                project_root=ROOT,
                provenance_loader=lambda _: [],
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    assert not (run_dir / "results.json").exists()
    index_bytes = (run_dir / "evidence-index.json").read_bytes()
    assert (run_dir / "evidence-index.sha256").read_text().startswith(
        hashlib.sha256(index_bytes).hexdigest()
    )
    index = json.loads(index_bytes)
    rows_entry = next(
        item for item in index["entries"] if item["path"] == "rows.jsonl"
    )
    assert rows_entry["sha256"] == hashlib.sha256(
        (run_dir / "rows.jsonl").read_bytes()
    ).hexdigest()

    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["report_family"] == "catalyst"
    assert manifest["suite_id"] == "notebook-test-v1"
    assert len(manifest["suite_sha256"]) == 64

    events = read_jsonl(run_dir / "events.jsonl")
    result_rows = read_jsonl(run_dir / "results.jsonl")

    assert events[0]["event_type"] == "run"
    assert events[0]["schema_version"] == "harness.catalyst-notebook.event.v1"
    assert events[0]["report_family"] == "catalyst"
    assert events[0]["suite_id"] == "notebook-test-v1"
    assert "comparison_set" not in events[0]
    assert events[0]["cells"] == [
        {"scenario_id": "first", "backend_id": PROFILE_ID, "turns": 1},
        {"scenario_id": "second", "backend_id": PROFILE_ID, "turns": 1},
    ]
    evaluation_events = [e for e in events if e["event_type"] == "evaluation"]
    assert [e["scenario_id"] for e in evaluation_events] == ["first"]
    assert {e["event_type"] for e in events} >= {"run", "scenario", "evaluation"}
    for event in events:
        for path in event.get("evidence_paths", []):
            assert (run_dir / path).is_file(), path

    assert [row["scenario_id"] for row in result_rows] == ["first"]
    row = result_rows[0]
    assert row["backend_id"] == PROFILE_ID
    assert row["turn"] == 1
    assert row["metrics"]["passed"] is True
    assert row["metrics"]["http_status"] == 200
    assert row["metrics"]["latency_ms"] is not None
    assert row["error"] is None


def test_persisting_an_absent_editor_query_is_a_configuration_error(
    tmp_path: Path,
) -> None:
    scenario = dict(_suite_payload()["scenarios"][0])
    scenario["persistEditorQuery"] = True
    suite_path = _write_suite(tmp_path, _suite_payload(scenarios=[scenario]))
    with pytest.raises(ValueError, match="persists an absent editor query"):
        run_notebook_suite(
            suite_path=suite_path,
            client=_StubClient(
                session_body={"sessionId": "session-1", "currentVersion": None}
            ),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )


def test_manual_scenario_requires_an_operator_checkpoint(tmp_path: Path) -> None:
    scenario = dict(_suite_payload()["scenarios"][0])
    scenario.update({"manualOnly": True, "expectedTurnStatus": "failed"})
    suite_path = _write_suite(tmp_path, _suite_payload(scenarios=[scenario]))
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = NotebookHttpClient(f"http://127.0.0.1:{server.server_port}")
        with pytest.raises(ValueError, match="requires an operator checkpoint"):
            run_notebook_suite(
                suite_path=suite_path,
                client=client,
                output_dir=tmp_path / "artifacts-no-checkpoint",
                project_root=ROOT,
                include_manual=True,
                provenance_loader=lambda _: [],
            )

        checkpoints: list[tuple[str, str]] = []
        result = run_notebook_suite(
            suite_path=suite_path,
            client=client,
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            include_manual=True,
            manual_checkpoint=lambda s, sid: checkpoints.append((s.id, sid)),
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    # The second run opens its own session, so assert the pairing rather than
    # a fixed id: the checkpoint sees the scenario and the live session.
    assert checkpoints == [("unchanged", state.session_ids[-1])]
    # The mock completes the turn, so the expected-failed scenario records the
    # failed-turn preservation check and does not pass.
    results = json.loads((result.run_dir / "results.json").read_text())
    names = {item["name"] for item in results["results"][0]["assertions"]}
    assert "failed_turn_preserved_base" in names
    assert result.passed_count == 0


def _exchange(body: dict[str, Any], *, status: int = 200) -> HttpExchange:
    return HttpExchange(
        method="GET",
        path="/",
        status_code=status,
        request_body=None,
        response_body=body,
        elapsed_ms=1,
    )


def _discovery_profile(**overrides: Any) -> dict[str, Any]:
    profile = {
        "id": PROFILE_ID,
        "available": True,
        "revisionCapable": True,
        "role_models": {
            "query_generate": "gemma-4-12b",
            "query_review": "qwen2.5-14b",
        },
    }
    profile.update(overrides)
    return profile


def test_discovery_gate_requires_writer_only_profile_to_have_no_reviewer(
    tmp_path: Path,
) -> None:
    base = _suite_payload()["scenarios"][0]
    suite = load_notebook_suite(
        _write_suite(
            tmp_path,
            _suite_payload(
                profiles={
                    WRITER_ONLY_PROFILE_ID: {"writerModelId": "gemma-4-12b"}
                },
                scenarios=[
                    {
                        **base,
                        "initialProfileId": WRITER_ONLY_PROFILE_ID,
                        "followupProfileId": WRITER_ONLY_PROFILE_ID,
                    }
                ],
            ),
        )
    )
    dataset = _exchange(
        {
            "contractVersion": "catalyst.dataset-overview.v1",
            "datasetId": "pipeline-1",
            "pipelineRunId": "pipeline-1",
        }
    )
    catalog = _exchange({"catalogVersion": "analytics-catalog-v1+schema.abc"})
    writer_only = _discovery_profile(
        id=WRITER_ONLY_PROFILE_ID,
        role_models={"query_generate": "gemma-4-12b"},
    )

    _require_discovery(
        suite,
        _exchange({"profiles": [writer_only]}),
        dataset,
        catalog,
    )

    writer_only["role_models"]["query_review"] = "qwen2.5-14b"
    with pytest.raises(ValueError, match="reviewer model drifted"):
        _require_discovery(
            suite,
            _exchange({"profiles": [writer_only]}),
            dataset,
            catalog,
        )


def test_evidence_reviewer_invocation_exactly_matches_profile() -> None:
    reviewed_evidence = _evidence("turn-followup", "Refine the current query.")
    writer_only_evidence = json.loads(json.dumps(reviewed_evidence))
    writer_only_evidence["invocations"] = [
        item
        for item in writer_only_evidence["invocations"]
        if item["role"] != "reviewer"
    ]
    writer_only_evidence["totalInvocationDurationMs"] = 5
    failed_before_review_evidence = json.loads(json.dumps(writer_only_evidence))
    failed_before_review_evidence["status"] = "failed"

    writer_only_checks = {
        name: passed
        for name, passed, _ in _evidence_checks(
            writer_only_evidence,
            expected_profile={
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": None,
            },
        )
    }
    unexpected_reviewer_checks = {
        name: passed
        for name, passed, _ in _evidence_checks(
            reviewed_evidence,
            expected_profile={
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": None,
            },
        )
    }
    reviewed_checks = {
        name: passed
        for name, passed, _ in _evidence_checks(
            reviewed_evidence,
            expected_profile={
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            },
        )
    }
    missing_reviewer_checks = {
        name: passed
        for name, passed, _ in _evidence_checks(
            writer_only_evidence,
            expected_profile={
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            },
        )
    }
    failed_before_review_checks = {
        name: passed
        for name, passed, _ in _evidence_checks(
            failed_before_review_evidence,
            expected_profile={
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            },
        )
    }

    assert writer_only_checks["reviewer_model"] is True
    assert unexpected_reviewer_checks["reviewer_model"] is False
    assert reviewed_checks["reviewer_model"] is True
    assert missing_reviewer_checks["reviewer_model"] is False
    assert failed_before_review_checks["reviewer_model"] is True


def test_discovery_gate_rejects_runtime_drift(tmp_path: Path) -> None:
    suite = load_notebook_suite(_write_suite(tmp_path, _suite_payload()))
    profiles = _exchange({"profiles": [_discovery_profile()]})
    dataset = _exchange(
        {
            "contractVersion": "catalyst.dataset-overview.v1",
            "datasetId": "pipeline-1",
            "pipelineRunId": "pipeline-1",
        }
    )
    catalog = _exchange({"catalogVersion": "analytics-catalog-v1+schema.abc"})

    _require_discovery(suite, profiles, dataset, catalog)

    with pytest.raises(ValueError, match="discovery returned HTTP 503"):
        _require_discovery(suite, _exchange({}, status=503), dataset, catalog)
    with pytest.raises(ValueError, match="is unavailable"):
        _require_discovery(
            suite,
            _exchange({"profiles": [_discovery_profile(available=False)]}),
            dataset,
            catalog,
        )
    with pytest.raises(ValueError, match="not revision-capable"):
        _require_discovery(
            suite,
            _exchange({"profiles": [_discovery_profile(revisionCapable=False)]}),
            dataset,
            catalog,
        )
    with pytest.raises(ValueError, match="writer model drifted"):
        _require_discovery(
            suite,
            _exchange(
                {
                    "profiles": [
                        _discovery_profile(
                            role_models={
                                "query_generate": "other",
                                "query_review": "qwen2.5-14b",
                            }
                        )
                    ]
                }
            ),
            dataset,
            catalog,
        )
    with pytest.raises(ValueError, match="reviewer model drifted"):
        _require_discovery(
            suite,
            _exchange(
                {
                    "profiles": [
                        _discovery_profile(
                            role_models={
                                "query_generate": "gemma-4-12b",
                                "query_review": "other",
                            }
                        )
                    ]
                }
            ),
            dataset,
            catalog,
        )
    with pytest.raises(ValueError, match="contract is unsupported"):
        _require_discovery(suite, profiles, _exchange({}), catalog)
    with pytest.raises(ValueError, match="not bound to its pipeline run"):
        _require_discovery(
            suite,
            profiles,
            _exchange(
                {
                    "contractVersion": "catalyst.dataset-overview.v1",
                    "datasetId": "pipeline-1",
                    "pipelineRunId": "pipeline-2",
                }
            ),
            catalog,
        )
    with pytest.raises(ValueError, match="does not derive"):
        _require_discovery(
            suite, profiles, dataset, _exchange({"catalogVersion": "other-catalog"})
        )


def test_json_safe_value_normalizes_database_types() -> None:
    aware = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
    assert _json_safe_value(None) is None
    assert _json_safe_value("x") == "x"
    assert _json_safe_value(Decimal("1.50")) == "1.50"
    assert _json_safe_value(float("nan")) == "NaN"
    assert _json_safe_value(float("inf")) == "Infinity"
    assert _json_safe_value(float("-inf")) == "-Infinity"
    assert _json_safe_value(0.5) == "0.5"
    assert _json_safe_value(aware) == "2026-07-20T12:00:00Z"
    assert _json_safe_value(datetime(2026, 7, 20, 12, 0)) == "2026-07-20T12:00:00"
    assert _json_safe_value(date(2026, 7, 20)) == "2026-07-20"
    assert _json_safe_value(time(12, 30)) == "12:30:00"
    uuid_value = UUID("12345678-1234-5678-1234-567812345678")
    assert _json_safe_value(uuid_value) == str(uuid_value)
    assert _json_safe_value(b"\x00\x01") == "AAE="
    assert _json_safe_value({"b": 1, "a": memoryview(b"\x02")}) == {
        "a": "Ag==",
        "b": 1,
    }
    assert _json_safe_value((1, [2])) == [1, [2]]
    assert _json_safe_value(object).startswith("<class")


def test_binding_value_converts_typed_parameters() -> None:
    assert _binding_value({"name": "d", "type": "date", "value": "2026-07-20"}) == date(
        2026, 7, 20
    )
    assert _binding_value(
        {"name": "t", "type": "date-time", "value": "2026-07-20T12:00:00Z"}
    ) == datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    assert _binding_value({"name": "i", "type": "integer", "value": "7"}) == 7
    assert _binding_value({"name": "n", "type": "number", "value": 1.5}) == Decimal(
        "1.5"
    )
    assert _binding_value(
        {"name": "il", "type": "integer-list", "value": ["1", 2]}
    ) == [1, 2]
    assert _binding_value({"name": "sl", "type": "string-list", "value": [1, "a"]}) == [
        "1",
        "a",
    ]
    assert _binding_value({"name": "s", "type": "string", "value": "x"}) == "x"
    with pytest.raises(ValueError, match="Boolean"):
        _binding_value({"name": "i", "type": "integer", "value": True})
    with pytest.raises(ValueError, match="Boolean"):
        _binding_value({"name": "il", "type": "integer-list", "value": [True]})


def test_driver_sql_rewrites_placeholders_outside_literals() -> None:
    sql = (
        "-- :skip in line comment\n"
        "/* :skip in block */\n"
        "SELECT ':skip', \":skip\", $$:skip$$, $tag$:skip$tag$,\n"
        "  value::text, :bound, :unbound\n"
        "FROM t WHERE name = 'O''Brien'"
    )
    rewritten = _driver_sql(sql, {"bound"})
    assert "%(bound)s" in rewritten
    assert ":unbound" in rewritten
    assert rewritten.count(":skip") == 6
    assert "value::text" in rewritten
    assert "'O''Brien'" in rewritten


def test_forbidden_key_scan_and_timestamp_parse() -> None:
    found = _find_forbidden_keys(
        {
            "instructionHistory": [{"previous_result_rows": []}],
            "dsn": "postgres://",
            "nested": {"reasoningTrace": "x"},
        }
    )
    assert sorted(found) == [
        "$.dsn",
        "$.instructionHistory[0].previous_result_rows",
        "$.nested.reasoningTrace",
    ]
    assert _parse_timestamp("2026-07-20T12:00:00Z") == datetime(
        2026, 7, 20, 12, 0, tzinfo=timezone.utc
    )
    assert _parse_timestamp("not-a-timestamp") is None
    assert _parse_timestamp(None) is None


def test_evidence_recorder_rejects_paths_outside_run_directory(
    tmp_path: Path,
) -> None:
    from harness.catalyst.notebook_validation import _EvidenceRecorder

    recorder = _EvidenceRecorder(tmp_path / "run", "run-1")
    with pytest.raises(ValueError, match="must stay within the run directory"):
        recorder.json("../escape.json", {}, kind="evidence")


def test_recovered_evidence_cannot_escape_overwrite_or_change_after_preflight(
    tmp_path: Path,
) -> None:
    from harness.catalyst.notebook_validation import _EvidenceRecorder

    recorder = _EvidenceRecorder(tmp_path / "run", "run-1")
    source = tmp_path / "source.json"
    source.write_text("{}\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="must stay within the run directory"):
        recorder.adopt(
            "../escape.json",
            source,
            kind="recovered",
            metadata={},
            expected_sha256=digest,
        )
    recorder.run_dir.mkdir()
    (recorder.run_dir / "exists.json").write_text("already here")
    with pytest.raises(ValueError, match="would overwrite"):
        recorder.adopt(
            "exists.json",
            source,
            kind="recovered",
            metadata={},
            expected_sha256=digest,
        )
    with pytest.raises(ValueError, match="changed after preflight"):
        recorder.adopt(
            "changed.json",
            source,
            kind="recovered",
            metadata={},
            expected_sha256="0" * 64,
        )


def test_recovery_identity_exchange_must_exist_and_contain_an_object(
    tmp_path: Path,
) -> None:
    from harness.catalyst.notebook_validation import _exchange_body

    path = tmp_path / "exchange.json"
    with pytest.raises(ValueError, match="cannot read recovery identity"):
        _exchange_body(path)
    path.write_text(json.dumps({"response": {"body": []}}))
    with pytest.raises(ValueError, match="is not an object"):
        _exchange_body(path)


def test_a_malformed_recovery_evidence_index_is_refused(tmp_path: Path) -> None:
    from harness.catalyst.notebook_validation import _preflight_recovery_evidence

    (tmp_path / "evidence-index.json").write_text("{not-json")
    with pytest.raises(ValueError, match="evidence index is invalid"):
        _preflight_recovery_evidence(tmp_path, [])


def test_recovery_refuses_a_row_without_structural_conformance_checks() -> None:
    from harness.catalyst.notebook_validation import _row_is_measurement_valid

    assert not _row_is_measurement_valid(
        {
            "status": "completed",
            "sessionId": "session-1",
            "measurementEvidence": {"complete": True},
            "assertions": [
                {"name": "answer_match", "class": "model_quality", "passed": True}
            ],
        }
    )


def test_notebook_cli_wires_arguments_into_the_runner(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    captured: dict[str, Any] = {}

    def fake_run_notebook_suite(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            run_id="run-1",
            run_dir=tmp_path / "run-1",
            passed_count=2,
            result_count=2,
            skipped_count=1,
            complete=True,
            measurement_valid=True,
        )

    monkeypatch.setattr(
        notebook_validation, "run_notebook_suite", fake_run_notebook_suite
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-catalyst-notebook-validation.py",
            "--suite",
            "suite.json",
            "--gateway-url",
            "http://gateway.example",
            "--output-dir",
            str(tmp_path),
            "--scenario",
            "unchanged",
            "--repetitions",
            "2",
            "--postgres-dsn",
            "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics",
        ],
    )

    script_path = ROOT / "scripts" / "run-catalyst-notebook-validation.py"
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(script_path), run_name="__main__")

    assert exit_info.value.code == 0
    assert captured["suite_path"] == Path("suite.json")
    assert captured["scenario_ids"] == {"unchanged"}
    assert captured["repetitions"] == 2
    assert captured["include_manual"] is False
    assert captured["manual_checkpoint"] is None
    assert isinstance(captured["postgres_checker"], PostgresReadOnlyChecker)
    assert isinstance(captured["gold_checker"], PostgresGoldExecutionChecker)
    assert json.loads(capsys.readouterr().out) == {
        "run_id": "run-1",
        "run_dir": str(tmp_path / "run-1"),
        "passed": 2,
        "total": 2,
        "skipped": 1,
        "complete": True,
        "measurement_valid": True,
    }


def test_notebook_cli_can_skip_the_postgres_cross_check(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    captured: dict[str, Any] = {}

    def fake_run_notebook_suite(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            run_id="run-1",
            run_dir=tmp_path / "run-1",
            passed_count=0,
            result_count=1,
            skipped_count=0,
            complete=True,
            measurement_valid=True,
        )

    monkeypatch.setattr(
        notebook_validation, "run_notebook_suite", fake_run_notebook_suite
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-catalyst-notebook-validation.py",
            "--output-dir",
            str(tmp_path),
            "--no-postgres-cross-check",
        ],
    )

    script_path = ROOT / "scripts" / "run-catalyst-notebook-validation.py"
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(script_path), run_name="__main__")

    # A wrong answer is still a successfully completed measurement.
    assert exit_info.value.code == 0
    assert captured["postgres_checker"] is None
    assert captured["gold_checker"] is None
    capsys.readouterr()


def test_notebook_cli_fails_an_invalid_measurement_even_if_the_command_finished(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    monkeypatch.setattr(
        notebook_validation,
        "run_notebook_suite",
        lambda **_: SimpleNamespace(
            run_id="run-invalid",
            run_dir=tmp_path / "run-invalid",
            passed_count=1,
            result_count=1,
            skipped_count=0,
            complete=True,
            measurement_valid=False,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-catalyst-notebook-validation.py",
            "--output-dir",
            str(tmp_path),
            "--no-postgres-cross-check",
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(
            str(ROOT / "scripts" / "run-catalyst-notebook-validation.py"),
            run_name="__main__",
        )

    assert exit_info.value.code == 1


def test_notebook_cli_prints_the_exact_incomplete_run_for_explicit_resume(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import harness.catalyst.notebook_validation as notebook_validation

    run_dir = tmp_path / "run-incomplete"
    monkeypatch.setattr(
        notebook_validation,
        "run_notebook_suite",
        lambda **_: SimpleNamespace(
            run_id="run-incomplete",
            run_dir=run_dir,
            passed_count=1,
            result_count=1,
            skipped_count=0,
            complete=False,
            measurement_valid=False,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-catalyst-notebook-validation.py",
            "--output-dir",
            str(tmp_path),
            "--no-postgres-cross-check",
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(
            str(ROOT / "scripts" / "run-catalyst-notebook-validation.py"),
            run_name="__main__",
        )

    assert exit_info.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["run_id"] == "run-incomplete"
    assert output["run_dir"] == str(run_dir)
    assert output["complete"] is False


def test_notebook_cli_resolves_one_frozen_seed_for_the_whole_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from harness.catalyst import notebook_validation

    captured: dict[str, Any] = {}

    def fake_run_notebook_suite(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            run_id="run-configured",
            run_dir=tmp_path / "out" / "run-configured",
            passed_count=0,
            result_count=1,
            skipped_count=0,
            complete=True,
            measurement_valid=True,
        )

    monkeypatch.setattr(
        notebook_validation, "run_notebook_suite", fake_run_notebook_suite
    )
    monkeypatch.delenv("INTENTIONALLY_MISSING_DB_PASSWORD", raising=False)
    config_path = tmp_path / "seed.json"
    config_path.write_text(
        json.dumps(
            {
                "suite": "frozen-suite.json",
                "gatewayUrl": "http://127.0.0.1:18000",
                "outputDir": str(tmp_path / "out").removeprefix("/"),
                "warmupQuestion": "Warm the selected team once.",
                "postgres": {
                    "passwordEnv": "INTENTIONALLY_MISSING_DB_PASSWORD"
                },
                "gates": {"overall": 0.9, "perScenario": 0.8},
                "invocation": {
                    "scenarios": ["unchanged"],
                    "repetitions": 2,
                    "includeManual": False,
                    "postgresCrossCheck": False,
                    "timeoutSeconds": 321,
                },
                "publish": {"slug": "frozen"},
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-catalyst-notebook-validation.py",
            "--run-config",
            str(config_path),
            "--scenario",
            "unchanged",
            "--scenario",
            "unchanged",
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(
            str(ROOT / "scripts" / "run-catalyst-notebook-validation.py"),
            run_name="__main__",
        )

    assert exit_info.value.code == 0
    assert captured["suite_path"] == Path("frozen-suite.json")
    assert captured["client"].base_url == "http://127.0.0.1:18000"
    assert captured["scenario_ids"] == {"unchanged"}
    assert captured["repetitions"] == 2
    assert captured["postgres_checker"] is None
    assert captured["gold_checker"] is None
    assert captured["client"].timeout_seconds == 321
    assert captured["warmup_question"] == "Warm the selected team once."
    assert "source" not in captured["frozen_config"]
    assert captured["frozen_config"]["invocation"] == {
        "scenarios": ["unchanged"],
        "repetitions": 2,
        "includeManual": False,
        "postgresCrossCheck": False,
        "timeoutSeconds": 321,
    }


def test_scenario_turns_default_to_the_single_recorded_followup(
    tmp_path: Path,
) -> None:
    """Every suite in the repository predates multi-turn scenarios.

    Those suites describe one follow-up through `followupInstruction`. They
    keep loading, and they present as a one-turn sequence so the runner has a
    single shape to execute.
    """
    suite = load_notebook_suite(_write_suite(tmp_path, _suite_payload()))
    scenario = suite.scenarios[0]

    assert len(scenario.turns) == 1
    turn = scenario.turns[0]
    assert turn.instruction == "Return only distinct patients."
    assert turn.profile_id == PROFILE_ID
    assert turn.expected_turn_status == "completed"
    # The pre-turn accessors keep answering for the first follow-up.
    assert scenario.followup_instruction == turn.instruction
    assert scenario.followup_profile_id == turn.profile_id


def test_scenario_accepts_an_ordered_turn_sequence(tmp_path: Path) -> None:
    """The locked suite needs three user turns (M1, M2, M3), not two.

    Turns are executed in the order given, each naming its own profile and
    expected terminal status, so a scenario can drive refinement then a
    question without a second runner.
    """
    base = _suite_payload()["scenarios"][0]
    suite = load_notebook_suite(
        _write_suite(
            tmp_path,
            _suite_payload(
                scenarios=[
                    {
                        **{
                            key: value
                            for key, value in base.items()
                            if key
                            not in {"followupInstruction", "followupProfileId"}
                        },
                        "turns": [
                            {
                                "instruction": "Collapse to one row per patient.",
                                "profileId": PROFILE_ID,
                            },
                            {
                                "instruction": "Add the patient last name.",
                                "profileId": PROFILE_ID,
                                "expectedTurnStatus": "failed",
                            },
                        ],
                    }
                ]
            ),
        )
    )
    scenario = suite.scenarios[0]

    assert [turn.instruction for turn in scenario.turns] == [
        "Collapse to one row per patient.",
        "Add the patient last name.",
    ]
    assert [turn.expected_turn_status for turn in scenario.turns] == [
        "completed",
        "failed",
    ]
    # The first turn is what the pre-turn accessors describe.
    assert scenario.followup_instruction == "Collapse to one row per patient."


def test_scenario_rejects_declaring_both_turn_forms(tmp_path: Path) -> None:
    """One scenario, one description of its turns."""
    base = _suite_payload()["scenarios"][0]
    with pytest.raises(ValueError, match="both 'turns' and 'followupInstruction'"):
        load_notebook_suite(
            _write_suite(
                tmp_path,
                _suite_payload(
                    scenarios=[
                        {**base, "turns": [{"instruction": "x", "profileId": PROFILE_ID}]}
                    ]
                ),
            )
        )


def test_scenario_turn_profiles_must_exist_in_the_suite(tmp_path: Path) -> None:
    """Checked for every turn, not just the one that happens to be first."""
    base = _suite_payload()["scenarios"][0]
    with pytest.raises(ValueError, match="unknown profile"):
        load_notebook_suite(
            _write_suite(
                tmp_path,
                _suite_payload(
                    scenarios=[
                        {
                            **{
                                key: value
                                for key, value in base.items()
                                if key
                                not in {"followupInstruction", "followupProfileId"}
                            },
                            "turns": [
                                {"instruction": "first", "profileId": PROFILE_ID},
                                {"instruction": "x", "profileId": "not-a-profile"},
                            ],
                        }
                    ]
                ),
            )
        )


# --- writer outcomes -------------------------------------------------------
#
# The writer may end a turn three ways: ready, needs_clarification, or
# unsupported. `rejected` is the Gateway's, for policy/contract/reviewer or
# orchestration failure, and is never a writer choice. Catalyst does not
# publish a turn-level outcome yet — today a clarification arrives as a failed
# turn carrying failure.code — so the reader accepts the field when it appears
# and derives the outcome from the recorded shape until then.


def test_writer_outcome_prefers_the_published_field() -> None:
    turn = {"status": "failed", "writerOutcome": "unsupported"}
    assert writer_outcome(turn) == "unsupported"


@pytest.mark.parametrize("code", ["needs_clarification", "unsupported"])
def test_writer_outcome_derives_the_writer_choice_from_todays_shape(
    code: str,
) -> None:
    turn = {"status": "failed", "failure": {"code": code, "message": "…"}}
    assert writer_outcome(turn) == code


def test_writer_outcome_reads_a_completed_turn_as_ready() -> None:
    turn = {"status": "completed", "selectedVersionId": "v1"}
    assert writer_outcome(turn) == "ready"


def test_writer_outcome_keeps_gateway_failures_out_of_the_writer_vocabulary() -> None:
    """A contract or transport failure is the Gateway's, not a writer answer."""
    turn = {"status": "failed", "failure": {"code": "writer_output_contract_failed"}}
    assert writer_outcome(turn) == "rejected"


def test_turn_declares_its_expected_writer_outcome(tmp_path: Path) -> None:
    base = _suite_payload()["scenarios"][0]
    suite = load_notebook_suite(
        _write_suite(
            tmp_path,
            _suite_payload(
                scenarios=[
                    {
                        **{
                            key: value
                            for key, value in base.items()
                            if key
                            not in {"followupInstruction", "followupProfileId"}
                        },
                        "turns": [
                            {
                                "instruction": "Show recent HIV results.",
                                "profileId": PROFILE_ID,
                                "expectedOutcome": "needs_clarification",
                            },
                            {
                                "instruction": "Last 90 days, CD4 count.",
                                "profileId": PROFILE_ID,
                            },
                        ],
                    }
                ]
            ),
        )
    )
    turns = suite.scenarios[0].turns

    assert [turn.expected_outcome for turn in turns] == ["needs_clarification", "ready"]


def test_turn_rejects_gateway_rejection_as_an_expected_writer_outcome(
    tmp_path: Path,
) -> None:
    base = _suite_payload()["scenarios"][0]
    with pytest.raises(ValueError, match="invalid expected outcome"):
        load_notebook_suite(
            _write_suite(
                tmp_path,
                _suite_payload(
                    scenarios=[
                        {
                            **{
                                key: value
                                for key, value in base.items()
                                if key
                                not in {"followupInstruction", "followupProfileId"}
                            },
                            "turns": [
                                {
                                    "instruction": "x",
                                    "profileId": PROFILE_ID,
                                    "expectedOutcome": "rejected",
                                }
                            ],
                        }
                    ]
                ),
            )
        )


def test_three_turn_scenario_runs_every_turn_against_the_current_query(
    tmp_path: Path,
) -> None:
    """M1/M2/M3 drive three user turns; each one starts from the last result.

    Turn 1 keeps the original evidence filenames and assertion names, so suites
    recorded before multi-turn scenarios replay unchanged; later turns are
    suffixed and their own evidence is fetched and checked.
    """
    suite = {
        "id": "notebook-multi-turn-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "refine-twice",
                "family": "narrowing",
                "initialQuestion": "Show patient identifiers.",
                "initialProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
                "turns": [
                    {
                        "instruction": "Return only distinct patients.",
                        "profileId": PROFILE_ID,
                    },
                    {
                        "instruction": "Keep just the first row.",
                        "profileId": PROFILE_ID,
                    },
                ],
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    turn_posts = [
        path
        for method, path in state.requests
        if method == "POST" and path.endswith("/sessions/session-1/turns")
    ]
    assert len(turn_posts) == 2

    # Turn 2 must be based on what turn 1 left current, not on the original
    # base version — that chaining is what makes a refinement sequence real.
    assert state.turn_requests[0]["observedBase"]["versionId"] == "version-1"
    assert state.turn_requests[1]["observedBase"]["versionId"] == "version-3"
    assert (
        state.turn_requests[1]["editorSnapshot"]["sql"]
        == "SELECT DISTINCT patient_id FROM analytics.lab_result_fact_v1"
    )

    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    assert [turn["turnIndex"] for turn in row["turns"]] == [1, 2]
    assert [turn["turnId"] for turn in row["turns"]] == [
        "turn-followup",
        "turn-followup-2",
    ]
    assert [turn["instruction"] for turn in row["turns"]] == [
        "Return only distinct patients.",
        "Keep just the first row.",
    ]
    assert all(turn["observedOutcome"] == "ready" for turn in row["turns"])

    # Turn 1's evidence keeps its original name; turn 2 is slotted beside it.
    names = {item["name"] for item in row["assertions"]}
    assert "followup_terminal_status" in names
    assert "followup_terminal_status-t2" in names
    repetition_dir = next((result.run_dir / "scenarios").glob("*/*"))
    written = {path.name for path in repetition_dir.iterdir()}
    assert "08-create-followup.json" in written
    assert "08-create-followup-t2.json" in written


# --- adaptive repetitions --------------------------------------------------
#
# Every profile/scenario pair starts at three repetitions and extends to five
# when those three disagree: mixed verdicts, mixed writer outcomes, or a
# database answer that matched on one run and not another. A pair whose three
# runs agree is already settled and is not re-run.


def _rep(passed: bool, outcomes: list[str], *, answer: bool | None = None) -> dict:
    row: dict[str, Any] = {
        "status": "completed",
        "passed": passed,
        "turns": [{"observedOutcome": outcome} for outcome in outcomes],
        "assertions": [],
    }
    if answer is not None:
        row["assertions"] = [
            {"name": "successor_gold_execution_match", "passed": answer, "evidence": {}}
        ]
    return row


def test_agreeing_repetitions_are_settled() -> None:
    runs = [_rep(True, ["ready"], answer=True) for _ in range(3)]
    assert repetition_pair_is_unstable(runs) is False


def test_mixed_verdicts_extend_the_pair() -> None:
    runs = [
        _rep(True, ["ready"]),
        _rep(False, ["ready"]),
        _rep(True, ["ready"]),
    ]
    assert repetition_pair_is_unstable(runs) is True


def test_mixed_writer_outcomes_extend_the_pair() -> None:
    """Same verdict, different answer kind — the pair has not settled."""
    runs = [
        _rep(True, ["ready"]),
        _rep(True, ["needs_clarification"]),
        _rep(True, ["ready"]),
    ]
    assert repetition_pair_is_unstable(runs) is True


def test_a_database_answer_that_only_sometimes_matches_extends_the_pair() -> None:
    runs = [
        _rep(True, ["ready"], answer=True),
        _rep(True, ["ready"], answer=False),
        _rep(True, ["ready"], answer=True),
    ]
    assert repetition_pair_is_unstable(runs) is True


def test_a_single_repetition_cannot_disagree_with_itself() -> None:
    assert repetition_pair_is_unstable([_rep(True, ["ready"])]) is False


def test_skipped_repetitions_are_not_evidence_of_instability() -> None:
    runs = [
        _rep(True, ["ready"]),
        {"status": "skipped", "reason": "manual-only"},
        _rep(True, ["ready"]),
    ]
    assert repetition_pair_is_unstable(runs) is False


def _adaptive_suite(**scenario_overrides: Any) -> dict[str, Any]:
    return {
        "id": "notebook-adaptive-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 3,
        "extendedRepetitions": 5,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "adaptive",
                "family": "narrowing",
                "initialQuestion": "Show patient identifiers.",
                "initialProfileId": PROFILE_ID,
                "followupInstruction": "Return only distinct patients.",
                "followupProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
                **scenario_overrides,
            }
        ],
    }


def _run_against_fake(
    tmp_path: Path,
    suite: dict[str, Any],
    state,
    *,
    resume_from: Path | None = None,
    frozen_config: dict[str, Any] | None = None,
    warmup_question: str | None = None,
    postgres_checker: Any | None = None,
    scenario_ids: set[str] | None = None,
) -> Any:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
            resume_from=resume_from,
            frozen_config=frozen_config,
            warmup_question=warmup_question,
            postgres_checker=postgres_checker,
            scenario_ids=scenario_ids,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _mark_interrupted(run_dir: Path) -> None:
    """Checkpoint a completed test fixture as an interrupted run."""
    (run_dir / "results.json").unlink(missing_ok=True)
    index_path = run_dir / "evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    refreshed_entries = []
    for entry in index["entries"]:
        path = run_dir / entry["path"]
        if not path.is_file():
            continue
        if entry["path"] == "rows.jsonl":
            encoded = path.read_bytes()
            entry = {
                **entry,
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        refreshed_entries.append(entry)
    index["entries"] = refreshed_entries
    encoded_index = (
        json.dumps(index, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")
    index_path.write_bytes(encoded_index)
    (run_dir / "evidence-index.sha256").write_text(
        f"{hashlib.sha256(encoded_index).hexdigest()}  evidence-index.json\n",
        encoding="utf-8",
    )
    status_path = run_dir / "run-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update({"state": "incomplete", "measurementValid": False})
    status.pop("reason", None)
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


def test_a_settled_pair_stops_at_three_repetitions(tmp_path: Path) -> None:
    state = _WorkbenchState()
    result = _run_against_fake(tmp_path, _adaptive_suite(), state)

    assert result.result_count == 3


def test_an_unstable_pair_is_extended_to_five_repetitions(tmp_path: Path) -> None:
    """Repetition 2 disagrees with 1 and 3, so the pair has not settled."""
    state = _WorkbenchState()
    state.turn_status_sequence = ["completed", "failed", "completed"]
    result = _run_against_fake(tmp_path, _adaptive_suite(), state)

    assert result.result_count == 5


# --- frozen profile digests ------------------------------------------------
#
# The comparison freezes each team's resolved aliases and profile digest
# before the run. A profile that has been reconfigured since the freeze is a
# different team, so the run stops before spending a single model call on it.


def _digest_suite(**profile_extra: Any) -> dict[str, Any]:
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    suite["profiles"][PROFILE_ID] = {
        "writerModelId": "gemma-4-12b",
        "reviewerModelId": "qwen2.5-14b",
        **profile_extra,
    }
    return suite


def test_a_frozen_profile_digest_that_still_matches_runs(tmp_path: Path) -> None:
    state = _WorkbenchState()
    state.profile_digest = "d" * 64
    result = _run_against_fake(
        tmp_path, _digest_suite(profileConfigurationDigest="d" * 64), state
    )

    assert result.result_count == 1


def test_a_drifted_profile_digest_stops_before_any_model_call(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.profile_digest = "e" * 64
    with pytest.raises(ValueError, match="profile digest drifted"):
        _run_against_fake(
            tmp_path, _digest_suite(profileConfigurationDigest="d" * 64), state
        )

    assert not [
        path for method, path in state.requests if method == "POST"
    ], "no session or turn may be created once drift is known"


def test_a_frozen_digest_the_gateway_does_not_advertise_is_unverifiable(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.profile_digest = None
    with pytest.raises(ValueError, match="does not advertise a profile digest"):
        _run_against_fake(
            tmp_path, _digest_suite(profileConfigurationDigest="d" * 64), state
        )


# --- infrastructure vs model failures --------------------------------------
#
# A team is judged on what its models did. A Gateway 5xx or transport failure
# says nothing about the model, so collection stops and the operator decides
# when to resume it. Product and model failures remain experimental evidence.


def test_a_server_error_is_an_infrastructure_failure() -> None:
    assert is_infrastructure_failure({"status": "completed", "httpStatus": 503}) is True


def test_a_malformed_success_response_is_not_an_infrastructure_failure() -> None:
    assert (
        is_infrastructure_failure({"status": "failed_before_turn", "httpStatus": 200})
        is False
    )
    assert (
        is_infrastructure_failure({"status": "failed_before_turn", "httpStatus": 422})
        is False
    )


def test_a_model_that_answered_badly_is_not_an_infrastructure_failure() -> None:
    """A wrong answer is the measurement, not a broken run."""
    assert (
        is_infrastructure_failure(
            {"status": "completed", "httpStatus": 200, "passed": False}
        )
        is False
    )


@pytest.mark.parametrize(
    "stage",
    [
        "writer_transport",
        "reviewer_transport",
        "gateway_persistence",
        "orphan_recovery",
    ],
)
def test_a_persisted_service_interruption_is_infrastructure(stage: str) -> None:
    assert (
        is_infrastructure_failure(
            {
                "status": "infrastructure_failed",
                "httpStatus": 201,
                "failureStage": stage,
            }
        )
        is True
    )


@pytest.mark.parametrize(
    "stage",
    [
        "writer_output_contract",
        "writer_findings",
        "writer_decision",
        "reviewer_output_contract",
    ],
)
def test_a_persisted_model_failure_is_not_infrastructure(stage: str) -> None:
    assert (
        is_infrastructure_failure(
            {"status": "failed", "httpStatus": 201, "failureStage": stage}
        )
        is False
    )


def test_a_client_error_is_the_products_problem_not_the_hosts() -> None:
    """422 is Catalyst rejecting the request — that belongs in the denominator."""
    assert (
        is_infrastructure_failure({"status": "completed", "httpStatus": 422}) is False
    )


def test_a_profile_that_disappears_after_discovery_is_resumable(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.session_http_sequence = [422]
    state.session_error_code = "profile_unavailable"
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is False
    assert state.session_attempts == 1
    status = json.loads((result.run_dir / "run-status.json").read_text())
    failure = status["infrastructureFailures"][0]
    assert failure["httpStatus"] == 422
    assert failure["interruptionKind"] == "profile_availability"
    assert failure["interruptionCode"] == "profile_unavailable"
    assert "failureStage" not in failure


def test_an_unrelated_422_remains_a_product_result(tmp_path: Path) -> None:
    state = _WorkbenchState()
    state.session_http_sequence = [422]
    state.session_error_code = "invalid_request"
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is True
    assert result.measurement_valid is False
    status = json.loads((result.run_dir / "run-status.json").read_text())
    assert status["state"] == "invalid"
    assert status["infrastructureFailures"] == []


def test_a_followup_profile_that_disappears_is_resumable(tmp_path: Path) -> None:
    state = _WorkbenchState()
    state.turn_http_sequence = [422]
    state.turn_error_code = "profile_unavailable"
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is False
    assert state.turn_attempts == 1
    status = json.loads((result.run_dir / "run-status.json").read_text())
    failure = status["infrastructureFailures"][0]
    assert failure["interruptionKind"] == "profile_availability"
    assert failure["evidencePath"].endswith("/08-create-followup.json")


@pytest.mark.parametrize("legacy_budget", [None, 0, 2])
def test_the_first_infrastructure_failure_stops_collection_without_retry(
    tmp_path: Path, legacy_budget: int | None
) -> None:
    state = _WorkbenchState()
    # A successful response is available, but only an explicit resume may use it.
    state.turn_http_sequence = [503, 201, 201, 201]
    suite = _adaptive_suite()
    suite["repetitions"] = 3
    suite.pop("extendedRepetitions", None)
    if legacy_budget is not None:
        suite["infrastructureReplacements"] = legacy_budget
    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is False
    assert result.measurement_valid is False
    assert result.result_count == 0
    assert state.turn_attempts == 1
    assert not (result.run_dir / "results.json").exists()
    assert (result.run_dir / "evidence-index.json").is_file()
    rows = [
        json.loads(line)
        for line in (result.run_dir / "rows.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["status"] == "infrastructure_failed"
    assert "replacement" not in rows[0]["evidencePrefix"]
    status = json.loads((result.run_dir / "run-status.json").read_text())
    assert status["state"] == "incomplete"
    assert status["measurementValid"] is False
    assert len(status["infrastructureFailures"]) == 1
    failure = status["infrastructureFailures"][0]
    assert failure["runId"] == result.run_id
    assert failure["evidencePrefix"] == rows[0]["evidencePrefix"]
    index = json.loads((result.run_dir / "evidence-index.json").read_text())
    assert failure["evidencePath"] in {entry["path"] for entry in index["entries"]}


@pytest.mark.parametrize(
    ("stage", "code"),
    [
        ("writer_transport", "writer_transport_failed"),
        ("gateway_persistence", "initial_generation_failed"),
        ("orphan_recovery", "generation_interrupted"),
    ],
)
def test_a_persisted_initial_service_failure_stops_after_its_evidence(
    tmp_path: Path, stage: str, code: str,
) -> None:
    state = _WorkbenchState()
    state.base_failure_stage = stage
    state.base_failure_code = code
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is False
    assert result.result_count == 0
    assert state.turn_requests == []
    status = json.loads((result.run_dir / "run-status.json").read_text())
    failure = status["infrastructureFailures"][0]
    assert failure["httpStatus"] == 200
    assert failure["failureStage"] == stage
    assert failure["failureCode"] == code
    assert failure["evidencePath"].endswith("/02-initial-turns.json")
    indexed = {
        item["path"]
        for item in json.loads(
            (result.run_dir / "evidence-index.json").read_text()
        )["entries"]
    }
    assert failure["evidencePath"] in indexed
    assert any(path.endswith("/03-initial-generation-evidence.json") for path in indexed)


def test_a_later_evidence_503_keeps_the_persisted_initial_failure(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.base_failure_stage = "writer_transport"
    state.base_failure_code = "writer_transport_failed"
    state.generation_http_sequence = [503]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    failure = json.loads((result.run_dir / "run-status.json").read_text())[
        "infrastructureFailures"
    ][0]
    assert failure["httpStatus"] == 503
    assert failure["failureStage"] == "writer_transport"
    assert failure["failureCode"] == "writer_transport_failed"
    assert failure["evidencePath"].endswith("/03-initial-generation-evidence.json")


def test_a_persisted_output_contract_failure_is_not_called_an_interruption(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.base_failure_stage = "writer_output_contract"
    state.base_failure_code = "writer_output_contract_failed"
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is True
    assert result.measurement_valid is False
    status = json.loads((result.run_dir / "run-status.json").read_text())
    assert status["state"] == "invalid"
    assert status["infrastructureFailures"] == []


def test_a_persisted_followup_transport_failure_stops_before_another_turn(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.followup_failure_stage = "reviewer_transport"
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    scenario = suite["scenarios"][0]
    scenario.pop("followupInstruction")
    scenario.pop("followupProfileId")
    scenario["turns"] = [
        {"instruction": "First refinement.", "profileId": PROFILE_ID},
        {"instruction": "Second refinement.", "profileId": PROFILE_ID},
    ]

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is False
    assert [item["instruction"] for item in state.turn_requests] == [
        "First refinement."
    ]
    assert [item["versionId"] for item in state.executions] == ["version-1"]
    status = json.loads((result.run_dir / "run-status.json").read_text())
    failure = status["infrastructureFailures"][0]
    assert failure["httpStatus"] == 201
    assert failure["failureStage"] == "reviewer_transport"
    assert failure["failureCode"] == "reviewer_transport_failed"
    assert failure["evidencePath"].endswith("/08-create-followup.json")
    indexed = {
        item["path"]
        for item in json.loads(
            (result.run_dir / "evidence-index.json").read_text()
        )["entries"]
    }
    assert any(path.endswith("/11-followup-generation-evidence.json") for path in indexed)


def test_a_later_evidence_503_keeps_the_persisted_followup_failure(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.followup_failure_stage = "reviewer_transport"
    state.generation_http_sequence = [200, 503]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    failure = json.loads((result.run_dir / "run-status.json").read_text())[
        "infrastructureFailures"
    ][0]
    assert failure["httpStatus"] == 503
    assert failure["failureStage"] == "reviewer_transport"
    assert failure["failureCode"] == "reviewer_transport_failed"
    assert failure["evidencePath"].endswith(
        "/11-followup-generation-evidence.json"
    )


def test_the_operator_controlled_transport_scenario_remains_a_measurement(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.followup_failure_stage = "writer_transport"
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    suite["scenarios"][0].update(
        {
            "family": "hub-tool-failure",
            "expectedTurnStatus": "failed",
            "manualOnly": True,
        }
    )
    checkpoints: list[tuple[str, str]] = []

    suite_path = _write_suite(tmp_path, suite)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            include_manual=True,
            manual_checkpoint=lambda scenario, session_id: checkpoints.append(
                (scenario.id, session_id)
            ),
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result.complete is True
    assert result.measurement_valid is True
    assert len(checkpoints) == 1
    summary = json.loads((result.run_dir / "results.json").read_text())
    assert summary["infrastructureFailures"] == []
    row = summary["results"][0]
    assert row["status"] == "failed"
    assert row["measurementValid"] is True
    assert row["passed"] is False


def test_a_first_turn_service_failure_prevents_later_model_turns(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.turn_http_sequence = [503, 201]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    scenario = suite["scenarios"][0]
    scenario.pop("followupInstruction")
    scenario.pop("followupProfileId")
    scenario["turns"] = [
        {"instruction": "First refinement.", "profileId": PROFILE_ID},
        {"instruction": "Second refinement.", "profileId": PROFILE_ID},
    ]

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is False
    assert state.turn_attempts == 1
    assert [request["instruction"] for request in state.turn_requests] == [
        "First refinement."
    ]


def test_an_initial_evidence_service_failure_prevents_a_followup_model_call(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.generation_http_sequence = [503]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is False
    assert state.generation_attempts == 1
    assert state.turn_requests == []
    status = json.loads((result.run_dir / "run-status.json").read_text())
    assert status["infrastructureFailures"][0]["evidencePath"].endswith(
        "/03-initial-generation-evidence.json"
    )


def test_a_database_outage_returns_a_resumable_run_with_safe_evidence(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite(executeBase=True)
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(
        tmp_path,
        suite,
        state,
        postgres_checker=_UnavailablePostgresChecker(),
    )

    assert result.complete is False
    assert not (result.run_dir / "results.json").exists()
    status = json.loads((result.run_dir / "run-status.json").read_text())
    failure = status["infrastructureFailures"][0]
    assert failure["interruptionKind"] == "database_availability"
    assert failure["interruptionCode"] == "postgres_unavailable"
    assert "failureStage" not in failure
    evidence = json.loads((result.run_dir / failure["evidencePath"]).read_text())
    assert evidence == {
        "contractVersion": "harness.catalyst-notebook.service-interruption.v1",
        "service": "postgresql",
        "operation": "base_postgres_crosscheck",
        "exceptionType": "ConnectionError",
    }
    assert "database host" not in (result.run_dir / failure["evidencePath"]).read_text()


def test_a_database_statement_timeout_is_a_completed_wrong_answer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import psycopg

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, statement: str, parameters: object = None) -> None:
            if statement == "SET TRANSACTION READ ONLY" or "set_config" in statement:
                return
            raise psycopg.errors.QueryCanceled(
                "canceling statement due to statement timeout"
            )

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def cursor(self) -> Cursor:
            return Cursor()

    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: Connection())
    state = _WorkbenchState()
    suite = _adaptive_suite(executeBase=True, executeSuccessor=False)
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(
        tmp_path,
        suite,
        state,
        postgres_checker=PostgresReadOnlyChecker(
            "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics",
            statement_timeout_ms=25,
        ),
    )

    assert result.complete is True
    assert result.measurement_valid is True
    status = json.loads((result.run_dir / "run-status.json").read_text())
    assert status["state"] == "complete"
    assert status["infrastructureFailures"] == []
    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    timeout_assertion = next(
        item for item in row["assertions"] if item["name"] == "base_postgres_crosscheck"
    )
    assert timeout_assertion["class"] == "evaluation"
    assert timeout_assertion["passed"] is False
    evidence = json.loads(
        (
            result.run_dir
            / "scenarios/adaptive/repetition-01/07-postgres-base.json"
        ).read_text()
    )
    assert evidence["timedOut"] is True
    assert evidence["statementTimeoutMs"] == 25
    assert "statement timeout" in evidence["disagreement"]


def test_a_warmup_service_failure_stops_before_a_measured_session(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.profile_ids = ["team-a"]
    state.profile_models = {"team-a": ("gemma-4-12b", None)}
    state.session_http_sequence = [503, 201]
    suite = _comparison_suite(comparisonProfiles=["team-a"])
    suite["profiles"] = {
        "team-a": {"writerModelId": "gemma-4-12b", "reviewerModelId": None}
    }
    question = "Warm the selected team once."

    result = _run_against_fake(
        tmp_path,
        suite,
        state,
        frozen_config={"warmupQuestion": question},
        warmup_question=question,
    )

    assert result.complete is False
    assert state.session_attempts == 1
    assert len(state.session_requests) == 1
    assert state.session_requests[0]["question"] == question
    assert state.turn_requests == []
    status = json.loads((result.run_dir / "run-status.json").read_text())
    assert status["infrastructureFailures"][0]["phase"] == "warmup"


def test_a_warmup_evidence_503_keeps_the_persisted_model_service_failure(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.profile_ids = ["team-a"]
    state.profile_models = {"team-a": ("gemma-4-12b", None)}
    state.base_failure_stage = "writer_transport"
    state.generation_http_sequence = [503]
    suite = _comparison_suite(comparisonProfiles=["team-a"])
    suite["profiles"] = {
        "team-a": {"writerModelId": "gemma-4-12b", "reviewerModelId": None}
    }
    question = "Warm the selected team once."

    result = _run_against_fake(
        tmp_path,
        suite,
        state,
        frozen_config={"warmupQuestion": question},
        warmup_question=question,
    )

    failure = json.loads((result.run_dir / "run-status.json").read_text())[
        "infrastructureFailures"
    ][0]
    assert failure["phase"] == "warmup"
    assert failure["httpStatus"] == 503
    assert failure["failureStage"] == "writer_transport"
    assert failure["failureCode"] == "writer_transport_failed"


def test_discovery_stops_at_the_first_service_failure(tmp_path: Path) -> None:
    class DiscoveryFailureClient(_StubClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[str] = []

        def profiles(self) -> HttpExchange:
            self.calls.append("profiles")
            return self._ok({"error": {"code": "unavailable"}}, status=503)

        def dataset_overview(self) -> HttpExchange:
            self.calls.append("dataset")
            return super().dataset_overview()

        def catalog(self) -> HttpExchange:
            self.calls.append("catalog")
            return super().catalog()

        def create_session(self, question: str, profile_id: str) -> HttpExchange:
            self.calls.append("session")
            return super().create_session(question, profile_id)

    client = DiscoveryFailureClient()
    result = run_notebook_suite(
        suite_path=_write_suite(tmp_path, _suite_payload()),
        client=client,
        output_dir=tmp_path / "artifacts",
        project_root=ROOT,
        provenance_loader=lambda _: [],
    )

    assert result.complete is False
    assert client.calls == ["profiles"]
    status = json.loads((result.run_dir / "run-status.json").read_text())
    failure = status["infrastructureFailures"][0]
    assert failure["phase"] == "discovery"
    assert failure["evidencePath"] == "discovery/query-options.json"

    resumed = _run_against_fake(
        tmp_path,
        _suite_payload(),
        _WorkbenchState(),
        resume_from=result.run_dir,
    )
    assert resumed.complete is True
    assert resumed.measurement_valid is True


# --- token evidence --------------------------------------------------------
#
# Every writer, reviewer, or repair call counts its fully rendered messages
# against the profile's declared window before the model is invoked. The
# runner records that accounting and refuses a run whose numbers do not add
# up; a suite that requires the accounting also refuses one that lacks it.


def _accounting(**overrides: Any) -> dict[str, Any]:
    return {
        "tokenAccounting": {
            "tokenizer": "gemma-4",
            "contextWindow": 8192,
            "outputReserve": 1024,
            "promptTokens": 4000,
            "includedItemIds": ["guidance-1"],
            "omittedItemIds": [],
            "omissions": [],
            **overrides,
        }
    }


def test_token_evidence_within_the_declared_window_passes() -> None:
    checks = dict(
        (name, passed) for name, passed, _ in token_evidence_checks(_accounting())
    )
    assert checks == {"token_evidence_recorded": True, "token_budget_respected": True}


def test_a_prompt_that_leaves_no_room_for_the_reply_fails() -> None:
    """promptTokens + outputReserve must fit the window, not just the prompt."""
    evidence = _accounting(promptTokens=7500)
    checks = dict((name, passed) for name, passed, _ in token_evidence_checks(evidence))
    assert checks["token_budget_respected"] is False


def test_a_character_count_substitute_is_not_token_evidence() -> None:
    evidence = _accounting()
    del evidence["tokenAccounting"]["tokenizer"]
    checks = dict((name, passed) for name, passed, _ in token_evidence_checks(evidence))
    assert checks["token_evidence_recorded"] is False


def test_absent_accounting_is_reported_but_not_required_by_default() -> None:
    checks = dict((name, passed) for name, passed, _ in token_evidence_checks({}))
    assert checks == {"token_evidence_recorded": False}


def test_a_suite_may_require_token_evidence(tmp_path: Path) -> None:
    """The locked suite turns this on; older suites keep running without it."""
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    suite["requireTokenEvidence"] = True
    result = _run_against_fake(tmp_path, suite, state)

    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    names = {item["name"]: item["passed"] for item in row["assertions"]}
    assert names["token_evidence_recorded"] is False
    assert row["passed"] is False


def _terminal_base_scenario(**overrides: Any) -> dict[str, Any]:
    base = _suite_payload()["scenarios"][0]
    scenario = {
        key: value
        for key, value in base.items()
        if key not in {"followupInstruction", "followupProfileId"}
    }
    scenario.update(
        {
            "initialQuestion": "Show each patient's home address.",
            "expectedBaseOutcome": "unsupported",
            "validateBase": False,
            "executeBase": False,
            "turns": [],
        }
    )
    scenario.update(overrides)
    return scenario


def test_a_scenario_may_declare_the_answer_its_opening_question_deserves(
    tmp_path: Path,
) -> None:
    """U1/U2 and B1-B3 are scored on the opening question, not a follow-up.

    The writer's answer to the question that opened the session is the thing
    under test; without saying which answer is expected, a refusal and a
    query both read as "the base".
    """
    suite = load_notebook_suite(
        _write_suite(tmp_path, _suite_payload(scenarios=[_terminal_base_scenario()]))
    )

    assert suite.scenarios[0].expected_base_outcome == "unsupported"
    assert suite.scenarios[0].turns == ()


def test_a_scenario_that_says_nothing_still_expects_a_query(tmp_path: Path) -> None:
    suite = load_notebook_suite(_write_suite(tmp_path, _suite_payload()))

    assert suite.scenarios[0].expected_base_outcome == "ready"


def test_a_base_cannot_be_expected_to_be_gateway_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid expected base outcome"):
        load_notebook_suite(
            _write_suite(
                tmp_path,
                _suite_payload(
                    scenarios=[_terminal_base_scenario(expectedBaseOutcome="rejected")]
                ),
            )
        )


def test_a_ready_base_with_no_turns_must_check_the_query_it_asked_for(
    tmp_path: Path,
) -> None:
    """A1-A4 are scored on their opening question, by running its query.

    Expecting a query, declaring no follow-up and then not validating or
    executing it would measure nothing past the session opening -- which
    reads as a pass.
    """
    with pytest.raises(ValueError, match="must declare at least one turn"):
        load_notebook_suite(
            _write_suite(
                tmp_path,
                _suite_payload(
                    scenarios=[
                        _terminal_base_scenario(
                            expectedBaseOutcome="ready",
                            validateBase=False,
                            executeBase=False,
                        )
                    ]
                ),
            )
        )

    checked = load_notebook_suite(
        _write_suite(
            tmp_path,
            _suite_payload(
                scenarios=[
                    _terminal_base_scenario(
                        expectedBaseOutcome="ready",
                        validateBase=True,
                        executeBase=True,
                    )
                ]
            ),
        )
    )
    assert checked.scenarios[0].turns == ()
    assert checked.scenarios[0].expected_base_outcome == "ready"


def test_a_refused_opening_question_is_a_pass_not_a_failed_repetition(
    tmp_path: Path,
) -> None:
    """U1/U2: the session opens, the writer declines, and that is the answer.

    With no version to validate the runner used to abandon the repetition as
    `failed_before_turn`, scoring the product's correct refusal as its own
    breakage. The scenario is scored on the opening question alone.
    """
    suite = {
        "id": "notebook-unsupported-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "no-address",
                "family": "unsupported",
                "initialQuestion": "Show each patient's home address.",
                "initialProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
                "expectedBaseOutcome": "unsupported",
                "validateBase": False,
                "executeBase": False,
                "turns": [],
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()
    state.base_outcome = "unsupported"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    assert row["status"] == "completed"
    assert row["passed"] is True, [
        item for item in row["assertions"] if not item["passed"]
    ]
    assert row["turns"] == []
    assert row["baseOutcome"] == "unsupported"

    names = {item["name"] for item in row["assertions"]}
    assert "base_writer_outcome" in names
    # Nothing was produced, so nothing may have been validated or executed.
    assert "base_version_available" not in names
    assert "base_validation_recorded" not in names
    assert "no_sql_after_non_ready_base" in names
    # And no turn was posted at all.
    assert not [
        path
        for method, path in state.requests
        if method == "POST" and path.endswith("/turns")
    ]


def test_a_wrong_terminal_opening_answer_remains_valid_evidence(
    tmp_path: Path,
) -> None:
    """A complete refusal is still a result when the suite expected SQL."""
    state = _WorkbenchState()
    state.base_outcome = "unsupported"
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is True
    assert result.measurement_valid is True
    assert result.passed_count == 0
    assert state.turn_requests == []
    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    assert row["status"] == "failed"
    assert row["baseOutcome"] == "unsupported"
    assert row["expectedBaseOutcome"] == "ready"
    assert row["baseAnswerText"] == "The data records no home address."
    assert row["baseOutcomeEndedConversation"] is True
    assert row["measurementValid"] is True
    assert row["measurementEvidence"]["complete"] is True
    assert row["turns"] == []
    failed = {item["name"] for item in row["assertions"] if not item["passed"]}
    assert failed == {"base_writer_outcome"}
    assert "base_version_available" not in {
        item["name"] for item in row["assertions"]
    }


def test_an_opening_question_answered_with_sql_when_a_refusal_was_due_fails(
    tmp_path: Path,
) -> None:
    """The guard has to be about the answer, not merely about the absence."""
    suite = {
        "id": "notebook-unsupported-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "no-address",
                "family": "unsupported",
                "initialQuestion": "Show each patient's home address.",
                "initialProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
                "expectedBaseOutcome": "unsupported",
                "validateBase": False,
                "executeBase": False,
                "turns": [],
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()  # answers with a query instead of declining
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    assert row["passed"] is False
    failed = {item["name"] for item in row["assertions"] if not item["passed"]}
    assert "base_writer_outcome" in failed
    # The writer answered `ready`, so the session is *supposed* to hold that
    # query: the no-SQL contract check does not apply and must not fire. It
    # is the judgment that failed here, not the product's behaviour.
    names = {item["name"] for item in row["assertions"]}
    assert "no_sql_after_non_ready_base" not in names
    assert all(
        item["class"] == "evaluation"
        for item in row["assertions"]
        if not item["passed"]
    )


def test_a_refusal_that_left_a_query_behind_is_caught(tmp_path: Path) -> None:
    """Declining and producing SQL anyway is worse than either alone.

    The writer's answer is right and would pass the outcome check on its own,
    so only a separate assertion about the session's contents can see that a
    refusal still put an executable query in front of the person.
    """
    suite = {
        "id": "notebook-unsupported-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "no-address",
                "family": "unsupported",
                "initialQuestion": "Show each patient's home address.",
                "initialProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
                "expectedBaseOutcome": "unsupported",
                "validateBase": False,
                "executeBase": False,
                "turns": [],
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()
    state.base_outcome = "unsupported"
    state.leaves_a_query_behind = True
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    assert row["baseOutcome"] == "unsupported"
    failed = {item["name"] for item in row["assertions"] if not item["passed"]}
    # The answer itself was correct; only the leftover query is wrong.
    assert "base_writer_outcome" not in failed
    assert "no_sql_after_non_ready_base" in failed
    assert row["passed"] is False


def test_explicit_resume_reuses_complete_cells_and_runs_only_the_missing_cell(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.turn_http_sequence = [201, 503]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite["infrastructureReplacements"] = 2
    suite.pop("extendedRepetitions", None)
    base = suite["scenarios"][0]
    suite["scenarios"] = [{**base, "id": "finished"}, {**base, "id": "missing"}]

    source = _run_against_fake(tmp_path, suite, state)
    assert source.complete is False
    source_rows = [
        json.loads(line)
        for line in (source.run_dir / "rows.jsonl").read_text().splitlines()
    ]
    finished_row = next(row for row in source_rows if row["scenarioId"] == "finished")
    source_bytes = {
        path.relative_to(source.run_dir).as_posix(): path.read_bytes()
        for path in source.run_dir.rglob("*")
        if path.is_file()
    }

    state.turn_http_sequence = [201]
    state.turn_attempts = 0
    state.turn_requests.clear()
    resumed = _run_against_fake(tmp_path, suite, state, resume_from=source.run_dir)

    assert resumed.complete is True
    assert resumed.measurement_valid is True
    assert len(state.turn_requests) == 1
    summary = json.loads((resumed.run_dir / "results.json").read_text())
    assert [row["scenarioId"] for row in summary["results"]] == ["finished", "missing"]
    assert summary["results"][0] == finished_row
    assert summary["infrastructureFailureCount"] == 1
    assert source_bytes == {
        path.relative_to(source.run_dir).as_posix(): path.read_bytes()
        for path in source.run_dir.rglob("*")
        if path.is_file()
    }

    from harness.catalyst.notebook_scoring import score_run

    assert score_run(resumed.run_dir)["totals"]["infrastructureFailed"] == 1


def test_recovery_reconstructs_an_interruption_missing_from_stale_status(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.turn_http_sequence = [503, 201]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    source = _run_against_fake(tmp_path, suite, state)
    interruptions = source.run_dir / "interruptions.jsonl"
    source_failure = read_jsonl(interruptions)[0]
    assert source_failure["httpStatus"] == 503
    source_evidence = (
        source.run_dir / source_failure["evidencePath"]
    ).read_bytes()
    indexed = json.loads((source.run_dir / "evidence-index.json").read_text())
    assert "interruptions.jsonl" in {item["path"] for item in indexed["entries"]}
    # Simulate a stop after the interruption stream was signed but before the
    # final lifecycle projection was replaced.
    status_path = source.run_dir / "run-status.json"
    status = json.loads(status_path.read_text())
    status["infrastructureFailures"] = []
    status_path.write_text(json.dumps(status, indent=2) + "\n")
    state.turn_requests.clear()

    resumed = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=source.run_dir,
    )

    summary = json.loads((resumed.run_dir / "results.json").read_text())
    assert summary["infrastructureFailureCount"] == 1
    carried = summary["infrastructureFailures"][0]
    assert carried["httpStatus"] == 503
    assert carried["runId"] == source.run_id
    assert carried["sourceEvidencePath"] == source_failure["evidencePath"]
    assert carried["recoveredFromRunId"] == source.run_id
    assert carried["evidencePath"].startswith(
        f"interruptions/sources/{source.run_id}/"
    )
    assert (resumed.run_dir / carried["evidencePath"]).read_bytes() == source_evidence
    retried = json.loads(
        (resumed.run_dir / source_failure["evidencePath"]).read_text()
    )
    assert retried["response"]["httpStatus"] == 201


def test_recovery_accepts_results_written_before_the_complete_status_flip(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    source = _run_against_fake(tmp_path, suite, state)
    source_summary = json.loads((source.run_dir / "results.json").read_text())
    # Simulate an abrupt stop after the signed summary was written but before
    # the lifecycle status was atomically changed from incomplete to complete.
    status_path = source.run_dir / "run-status.json"
    status = json.loads(status_path.read_text())
    status.update({"state": "incomplete", "measurementValid": False})
    status_path.write_text(json.dumps(status, indent=2) + "\n")
    state.turn_requests.clear()

    resumed = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=source.run_dir,
    )

    assert state.turn_requests == []
    assert resumed.complete is True
    assert json.loads((resumed.run_dir / "results.json").read_text())["results"] == (
        source_summary["results"]
    )


def test_recovery_keeps_completed_cells_across_an_early_failed_resume(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.turn_http_sequence = [201, 503]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    base = suite["scenarios"][0]
    suite["scenarios"] = [{**base, "id": "finished"}, {**base, "id": "missing"}]

    first = _run_against_fake(tmp_path, suite, state)
    assert first.complete is False
    first_rows = [
        json.loads(line)
        for line in (first.run_dir / "rows.jsonl").read_text().splitlines()
    ]
    finished_row = next(row for row in first_rows if row["scenarioId"] == "finished")

    class DiscoveryFailureClient(_StubClient):
        def profiles(self) -> HttpExchange:
            return self._ok({"error": {"code": "unavailable"}}, status=503)

    second = run_notebook_suite(
        suite_path=_write_suite(tmp_path, suite),
        client=DiscoveryFailureClient(),
        output_dir=tmp_path / "artifacts",
        project_root=ROOT,
        provenance_loader=lambda _: [],
        resume_from=first.run_dir,
    )
    assert second.complete is False

    resumed_state = _WorkbenchState()
    final = _run_against_fake(
        tmp_path,
        suite,
        resumed_state,
        resume_from=second.run_dir,
    )

    assert final.complete is True
    assert final.measurement_valid is True
    assert len(resumed_state.turn_requests) == 1
    summary = json.loads((final.run_dir / "results.json").read_text())
    assert [row["scenarioId"] for row in summary["results"]] == [
        "finished",
        "missing",
    ]
    assert summary["results"][0] == finished_row
    manifest = json.loads((final.run_dir / "run_manifest.json").read_text())
    assert manifest["resumedFrom"] == second.run_id
    assert manifest["resumeAncestry"] == [first.run_id, second.run_id]
    assert summary["infrastructureFailureCount"] == 2
    imports = json.loads((final.run_dir / "recovery-import.json").read_text())
    measurement_import = next(
        item for item in imports["imports"] if item["kind"] == "measurement_cell"
    )
    assert measurement_import["sourceRunId"] == first.run_id
    assert measurement_import["scenarioId"] == "finished"


def test_repeated_explicit_interruptions_never_invalidate_by_count(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite["infrastructureReplacements"] = 2
    suite.pop("extendedRepetitions", None)
    state.turn_http_sequence = [503]

    first = _run_against_fake(tmp_path, suite, state)
    assert first.complete is False
    state.turn_attempts = 0
    second = _run_against_fake(tmp_path, suite, state, resume_from=first.run_dir)
    assert second.complete is False
    second_status = json.loads((second.run_dir / "run-status.json").read_text())
    assert second_status["state"] == "incomplete"
    assert len(second_status["infrastructureFailures"]) == 2

    state.turn_http_sequence = [201]
    state.turn_attempts = 0
    final = _run_against_fake(tmp_path, suite, state, resume_from=second.run_dir)
    assert final.complete is True
    assert final.measurement_valid is True
    final_status = json.loads((final.run_dir / "run-status.json").read_text())
    assert final_status["state"] == "complete"
    assert len(final_status["infrastructureFailures"]) == 2


# --- one frozen comparison, run once, resumable ----------------------------


def _comparison_suite(**overrides: Any) -> dict[str, Any]:
    """One suite, three teams, the same twelve scenarios for each."""
    payload = _adaptive_suite()
    payload["repetitions"] = 1
    payload.pop("extendedRepetitions", None)
    payload["profiles"] = {
        "team-a": {"writerModelId": "gemma-4-12b", "reviewerModelId": None},
        "team-b": {"writerModelId": "gemma-4-12b", "reviewerModelId": "gemma-4-12b"},
        "team-c": {"writerModelId": "gemma-4-12b", "reviewerModelId": "qwen2.5-14b"},
    }
    payload["comparisonProfiles"] = ["team-a", "team-b", "team-c"]
    base = payload["scenarios"][0]
    base["initialProfileId"] = "team-a"
    base["followupProfileId"] = "team-a"
    payload.update(overrides)
    return payload


def test_a_suite_can_name_the_teams_it_compares(tmp_path: Path) -> None:
    suite = load_notebook_suite(_write_suite(tmp_path, _comparison_suite()))

    assert suite.comparison_profiles == ("team-a", "team-b", "team-c")


def test_the_frozen_seed_exists_before_the_first_live_call(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"

    class FreezeCheckingClient(_StubClient):
        saw_seed = False

        def profiles(self) -> HttpExchange:
            run_dirs = list(output_dir.iterdir())
            assert len(run_dirs) == 1
            frozen = run_dirs[0] / "run-config.json"
            assert frozen.is_file()
            assert json.loads(frozen.read_text())["identity"] == "frozen-first"
            self.saw_seed = True
            return super().profiles()

    client = FreezeCheckingClient(session_status=503, session_body={})
    result = run_notebook_suite(
        suite_path=_write_suite(tmp_path, _suite_payload()),
        client=client,
        output_dir=output_dir,
        project_root=ROOT,
        provenance_loader=lambda _: [],
        frozen_config={"identity": "frozen-first"},
    )

    assert client.saw_seed is True
    assert result.measurement_valid is False


def test_each_team_gets_one_recorded_unscored_warmup(tmp_path: Path) -> None:
    state = _WorkbenchState()
    state.profile_ids = ["team-a", "team-b", "team-c"]
    state.profile_models = {
        "team-a": ("gemma-4-12b", None),
        "team-b": ("gemma-4-12b", "gemma-4-12b"),
        "team-c": ("gemma-4-12b", "qwen2.5-14b"),
    }
    suite = _comparison_suite()
    suite["comparisonProfiles"] = ["team-a", "team-b"]
    question = "How many distinct patients are represented in the approved HIV data?"

    result = _run_against_fake(
        tmp_path,
        suite,
        state,
        frozen_config={"warmupQuestion": question},
        warmup_question=question,
    )

    assert [
        (item["profileId"], item["question"])
        for item in state.session_requests
    ] == [
        ("team-a", question),
        ("team-a", "Show patient identifiers."),
        ("team-b", question),
        ("team-b", "Show patient identifiers."),
    ]
    assert result.result_count == 2
    rows = [
        json.loads(line)
        for line in (result.run_dir / "rows.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 2
    for profile_id in ("team-a", "team-b"):
        assert (
            result.run_dir / "warmups" / profile_id / "01-create-session.json"
        ).is_file()
        assert not any(
            row.get("sessionId")
            == json.loads(
                (
                    result.run_dir
                    / "warmups"
                    / profile_id
                    / "01-create-session.json"
                ).read_text()
            )["response"]["body"]["sessionId"]
            for row in rows
        )


def test_a_suite_that_names_no_teams_runs_the_profile_each_scenario_declares(
    tmp_path: Path,
) -> None:
    suite = load_notebook_suite(_write_suite(tmp_path, _suite_payload()))

    assert suite.comparison_profiles == ()


def test_a_compared_team_must_be_a_declared_profile(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        load_notebook_suite(
            _write_suite(
                tmp_path, _comparison_suite(comparisonProfiles=["team-a", "team-z"])
            )
        )


def test_every_team_runs_every_scenario_in_one_invocation(tmp_path: Path) -> None:
    """The comparison is one run, not one run per team.

    Teams are the outer loop so a local model stays resident while it answers
    the whole suite, and every team sees the same frozen scenario order.
    """
    state = _WorkbenchState()
    state.profile_ids = ["team-a", "team-b", "team-c"]
    state.profile_models = {
        "team-a": ("gemma-4-12b", None),
        "team-b": ("gemma-4-12b", "gemma-4-12b"),
        "team-c": ("gemma-4-12b", "qwen2.5-14b"),
    }
    suite = _comparison_suite()
    base = suite["scenarios"][0]
    suite["scenarios"] = [{**base, "id": "s1"}, {**base, "id": "s2"}]

    result = _run_against_fake(tmp_path, suite, state)

    summary = json.loads((result.run_dir / "results.json").read_text())
    ran = [(row["profileId"], row["scenarioId"]) for row in summary["results"]]
    assert ran == [
        ("team-a", "s1"), ("team-a", "s2"),
        ("team-b", "s1"), ("team-b", "s2"),
        ("team-c", "s1"), ("team-c", "s2"),
    ]
    # Each team actually answered under its own profile, not team-a's.
    assert {
        request["profileId"] for request in state.turn_requests
    } == {"team-a", "team-b", "team-c"}


def test_a_resumed_run_keeps_finished_work_and_only_runs_what_is_left(
    tmp_path: Path,
) -> None:
    """A comparison is hours of model time; an interruption must not restart it.

    Resuming reuses every (team, scenario) already recorded in the run
    directory verbatim -- the same rows, in the same order -- and spends model
    time only on the pairs that never finished.
    """
    state = _WorkbenchState()
    state.profile_ids = ["team-a", "team-b", "team-c"]
    state.profile_models = {
        "team-a": ("gemma-4-12b", None),
        "team-b": ("gemma-4-12b", "gemma-4-12b"),
        "team-c": ("gemma-4-12b", "qwen2.5-14b"),
    }
    suite = _comparison_suite()
    suite["comparisonProfiles"] = ["team-a", "team-b"]
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    first = _run_against_fake(tmp_path, suite, state)
    done = json.loads((first.run_dir / "results.json").read_text())
    finished_turns = len(state.turn_requests)
    assert [row["profileId"] for row in done["results"]] == ["team-a", "team-b"]

    # An interruption leaves the incremental rows and no final summary:
    # keep team-a's rows in rows.jsonl and delete everything summarising.
    team_a_rows = [row for row in done["results"] if row["profileId"] == "team-a"]
    (first.run_dir / "rows.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in team_a_rows), encoding="utf-8"
    )
    (first.run_dir / "results.json").unlink()
    _mark_interrupted(first.run_dir)
    source_bytes = {
        path.relative_to(first.run_dir).as_posix(): path.read_bytes()
        for path in first.run_dir.rglob("*")
        if path.is_file()
    }

    state.turn_requests.clear()
    resumed = _run_against_fake(tmp_path, suite, state, resume_from=first.run_dir)

    rows = json.loads((resumed.run_dir / "results.json").read_text())["results"]
    assert [row["profileId"] for row in rows] == ["team-a", "team-b"]
    # team-a was reused, not re-run: only team-b cost model time.
    assert len(state.turn_requests) == finished_turns // 2
    assert rows[0] == team_a_rows[0]
    assert source_bytes == {
        path.relative_to(first.run_dir).as_posix(): path.read_bytes()
        for path in first.run_dir.rglob("*")
        if path.is_file()
    }
    manifest = json.loads((resumed.run_dir / "run_manifest.json").read_text())
    assert manifest["resumedFrom"] == first.run_id
    assert manifest["resumeAncestry"] == [first.run_id]
    recovery = json.loads((resumed.run_dir / "recovery-import.json").read_text())
    measurement_import = next(
        item for item in recovery["imports"] if item["kind"] == "measurement_cell"
    )
    assert measurement_import["sourceRunId"] == first.run_id
    assert measurement_import["evidence"]


def test_recovery_reuses_a_complete_wrong_answer_without_rerunning_it(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _comparison_suite()
    suite["comparisonProfiles"] = ["team-a"]
    state.profile_ids = ["team-a", "team-b", "team-c"]
    state.profile_models = {
        "team-a": ("gemma-4-12b", None),
        "team-b": ("gemma-4-12b", "gemma-4-12b"),
        "team-c": ("gemma-4-12b", "qwen2.5-14b"),
    }
    state.base_outcome = "needs_clarification"
    first = _run_against_fake(tmp_path, suite, state)
    row = json.loads((first.run_dir / "rows.jsonl").read_text().splitlines()[0])
    assert row["baseOutcome"] == "needs_clarification"
    assert row["passed"] is False
    assert row["measurementValid"] is True
    _mark_interrupted(first.run_dir)
    state.turn_requests.clear()

    recovery = _run_against_fake(
        tmp_path, suite, state, resume_from=first.run_dir
    )

    assert state.turn_requests == []
    assert recovery.measurement_valid is True
    assert recovery.passed_count == 0
    adopted = json.loads((recovery.run_dir / "results.json").read_text())
    assert adopted["results"][0]["passed"] is False


def test_recovery_refuses_a_tampered_completed_row_before_live_calls(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    source = _run_against_fake(tmp_path, suite, state)
    _mark_interrupted(source.run_dir)
    rows_path = source.run_dir / "rows.jsonl"
    original = rows_path.read_text(encoding="utf-8")
    assert '"passed":true' in original
    rows_path.write_text(
        original.replace('"passed":true', '"passed":false', 1),
        encoding="utf-8",
    )
    state.requests.clear()

    with pytest.raises(ValueError, match="no longer matches.*rows"):
        _run_against_fake(tmp_path, suite, state, resume_from=source.run_dir)

    assert state.requests == []


def test_recovery_refuses_a_cross_copied_run_status_before_live_calls(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    source = _run_against_fake(tmp_path, suite, state)
    _mark_interrupted(source.run_dir)
    status_path = source.run_dir / "run-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["runId"] = "another-run"
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    state.requests.clear()

    with pytest.raises(ValueError, match="status is inconsistent"):
        _run_against_fake(tmp_path, suite, state, resume_from=source.run_dir)

    assert state.requests == []


def test_recovery_refuses_unindexed_conversation_evidence_before_model_calls(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    source = _run_against_fake(tmp_path, suite, state)
    _mark_interrupted(source.run_dir)
    index_path = source.run_dir / "evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    removed = next(
        item
        for item in index["entries"]
        if item["path"].endswith("/01-create-session.json")
    )
    index["entries"].remove(removed)
    encoded = (
        json.dumps(index, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")
    index_path.write_bytes(encoded)
    (source.run_dir / "evidence-index.sha256").write_text(
        f"{hashlib.sha256(encoded).hexdigest()}  evidence-index.json\n",
        encoding="utf-8",
    )
    state.turn_requests.clear()

    with pytest.raises(ValueError, match="evidence is not indexed"):
        _run_against_fake(tmp_path, suite, state, resume_from=source.run_dir)

    assert state.turn_requests == []


def test_recovery_ignores_only_an_unsigned_trailing_row_fragment(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    source = _run_against_fake(tmp_path, suite, state)
    _mark_interrupted(source.run_dir)
    with (source.run_dir / "rows.jsonl").open("ab") as stream:
        stream.write(b'{"scenarioId":"unfinished"')
    state.turn_requests.clear()

    resumed = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=source.run_dir,
    )

    assert resumed.complete is True
    assert state.turn_requests == []
    rows = read_jsonl(resumed.run_dir / "rows.jsonl")
    assert [row["scenarioId"] for row in rows] == ["adaptive"]


def test_recovery_reruns_a_wholly_unsigned_first_row(tmp_path: Path) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    source = _run_against_fake(tmp_path, suite, state)
    _mark_interrupted(source.run_dir)
    index_path = source.run_dir / "evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"] = [
        item for item in index["entries"] if item["path"] != "rows.jsonl"
    ]
    encoded = (
        json.dumps(index, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")
    index_path.write_bytes(encoded)
    (source.run_dir / "evidence-index.sha256").write_text(
        f"{hashlib.sha256(encoded).hexdigest()}  evidence-index.json\n",
        encoding="utf-8",
    )
    state.turn_requests.clear()

    resumed = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=source.run_dir,
    )

    assert resumed.complete is True
    assert len(state.turn_requests) == 1
    assert len(read_jsonl(resumed.run_dir / "rows.jsonl")) == 1


def test_recovery_ignores_a_wholly_unsigned_interruption_stream(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.turn_http_sequence = [503, 201]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    source = _run_against_fake(tmp_path, suite, state)
    index_path = source.run_dir / "evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"] = [
        item
        for item in index["entries"]
        if item["path"] not in {"rows.jsonl", "interruptions.jsonl"}
    ]
    encoded = (
        json.dumps(index, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")
    index_path.write_bytes(encoded)
    (source.run_dir / "evidence-index.sha256").write_text(
        f"{hashlib.sha256(encoded).hexdigest()}  evidence-index.json\n",
        encoding="utf-8",
    )
    (source.run_dir / "rows.jsonl").unlink()
    status_path = source.run_dir / "run-status.json"
    status = json.loads(status_path.read_text())
    status["infrastructureFailures"] = []
    status_path.write_text(json.dumps(status, indent=2) + "\n")
    state.turn_requests.clear()

    resumed = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=source.run_dir,
    )

    assert resumed.complete is True
    assert len(state.turn_requests) == 1
    summary = json.loads((resumed.run_dir / "results.json").read_text())
    assert summary["infrastructureFailures"] == []


def test_recovery_names_a_truncated_signed_interruption_stream(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.turn_http_sequence = [503]
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    source = _run_against_fake(tmp_path, suite, state)
    (source.run_dir / "interruptions.jsonl").write_bytes(b"")
    state.requests.clear()

    with pytest.raises(
        ValueError,
        match=(
            r"recovery interruptions\.jsonl is shorter than its signed prefix"
        ),
    ):
        _run_against_fake(
            tmp_path,
            suite,
            state,
            resume_from=source.run_dir,
        )

    assert state.requests == []


def test_recovery_accepts_the_matching_checksum_left_between_index_renames(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    source = _run_against_fake(tmp_path, suite, state)
    _mark_interrupted(source.run_dir)
    index_digest = hashlib.sha256(
        (source.run_dir / "evidence-index.json").read_bytes()
    ).hexdigest()
    (source.run_dir / ".evidence-index.sha256.tmp").write_text(
        f"{index_digest}  evidence-index.json\n",
        encoding="utf-8",
    )
    (source.run_dir / "evidence-index.sha256").write_text(
        f"{'0' * 64}  evidence-index.json\n",
        encoding="utf-8",
    )
    state.turn_requests.clear()

    resumed = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=source.run_dir,
    )

    assert resumed.complete is True
    assert state.turn_requests == []


def test_recovery_prefers_a_complete_temporary_checkpoint_over_the_prior_one(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 2
    suite.pop("extendedRepetitions", None)
    source = _run_against_fake(tmp_path, suite, state)
    _mark_interrupted(source.run_dir)
    index_path = source.run_dir / "evidence-index.json"
    current_bytes = index_path.read_bytes()
    current = json.loads(current_bytes)
    prior = json.loads(current_bytes)
    first_row = (source.run_dir / "rows.jsonl").read_bytes().splitlines(keepends=True)[0]
    prior_row = next(
        item for item in prior["entries"] if item["path"] == "rows.jsonl"
    )
    prior_row["bytes"] = len(first_row)
    prior_row["sha256"] = hashlib.sha256(first_row).hexdigest()
    prior_bytes = (
        json.dumps(prior, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")
    index_path.write_bytes(prior_bytes)
    (source.run_dir / "evidence-index.sha256").write_text(
        f"{hashlib.sha256(prior_bytes).hexdigest()}  evidence-index.json\n",
        encoding="utf-8",
    )
    (source.run_dir / ".evidence-index.json.tmp").write_bytes(current_bytes)
    (source.run_dir / ".evidence-index.sha256.tmp").write_text(
        f"{hashlib.sha256(current_bytes).hexdigest()}  evidence-index.json\n",
        encoding="utf-8",
    )
    state.turn_requests.clear()

    resumed = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=source.run_dir,
    )

    assert resumed.complete is True
    assert state.turn_requests == []
    assert len(read_jsonl(resumed.run_dir / "rows.jsonl")) == 2


def test_recovery_carries_the_source_warmup_without_warming_again(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.profile_ids = ["team-a"]
    state.profile_models = {"team-a": ("gemma-4-12b", None)}
    suite = _comparison_suite(comparisonProfiles=["team-a"])
    suite["profiles"] = {
        "team-a": {"writerModelId": "gemma-4-12b", "reviewerModelId": None}
    }
    question = "Warm the selected team once."
    config = {"warmupQuestion": question}
    source = _run_against_fake(
        tmp_path,
        suite,
        state,
        frozen_config=config,
        warmup_question=question,
    )
    _mark_interrupted(source.run_dir)
    state.session_requests.clear()

    resumed = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=source.run_dir,
        frozen_config=config,
        warmup_question=question,
    )

    assert state.session_requests == []
    copied = (
        resumed.run_dir
        / "warmups"
        / "team-a"
        / "sources"
        / source.run_id
        / "01-create-session.json"
    )
    assert copied.is_file()
    imports = json.loads((resumed.run_dir / "recovery-import.json").read_text())
    assert any(item.get("kind") == "excluded_warmup" for item in imports["imports"])

    _mark_interrupted(resumed.run_dir)
    state.session_requests.clear()
    third = _run_against_fake(
        tmp_path,
        suite,
        state,
        resume_from=resumed.run_dir,
        frozen_config=config,
        warmup_question=question,
    )
    assert third.complete is True
    assert state.session_requests == []


def test_recovery_refuses_a_completed_source_before_any_live_call(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    source = _run_against_fake(tmp_path, _adaptive_suite(), state)
    state.requests.clear()

    with pytest.raises(ValueError, match="only an immutable incomplete run"):
        _run_against_fake(tmp_path, _adaptive_suite(), state, resume_from=source.run_dir)

    assert state.requests == []


def test_recovery_identity_drift_stops_before_any_model_conversation(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    source = _run_against_fake(tmp_path, suite, state)
    (source.run_dir / "results.json").unlink()
    _mark_interrupted(source.run_dir)
    changed = json.loads(json.dumps(suite))
    changed["scenarios"][0]["initialQuestion"] = "A changed question"
    state.turn_requests.clear()

    with pytest.raises(ValueError, match="recovery identity drifted"):
        _run_against_fake(tmp_path, changed, state, resume_from=source.run_dir)

    assert state.turn_requests == []


def test_all_reusable_evidence_is_preflighted_before_any_warmup(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    state.profile_ids = ["team-a", "team-b", "team-c"]
    state.profile_models = {
        "team-a": ("gemma-4-12b", None),
        "team-b": ("gemma-4-12b", "gemma-4-12b"),
        "team-c": ("gemma-4-12b", "qwen2.5-14b"),
    }
    suite = _comparison_suite()
    suite["comparisonProfiles"] = ["team-a", "team-b"]
    question = "How many distinct patients are represented in the approved HIV data?"
    config = {"warmupQuestion": question}
    source = _run_against_fake(
        tmp_path,
        suite,
        state,
        frozen_config=config,
        warmup_question=question,
    )
    (source.run_dir / "results.json").unlink()
    _mark_interrupted(source.run_dir)
    missing = source.run_dir / "scenarios" / "team-b"
    missing.rename(source.run_dir / "missing-team-b-evidence")
    state.session_requests.clear()

    with pytest.raises(ValueError, match="recovery evidence is missing"):
        _run_against_fake(
            tmp_path,
            suite,
            state,
            resume_from=source.run_dir,
            frozen_config=config,
            warmup_question=question,
        )

    assert state.session_requests == []


def test_repeated_recovery_retains_the_complete_ancestry_without_duplicates(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    suite = _adaptive_suite()
    first = _run_against_fake(tmp_path, suite, state)
    (first.run_dir / "results.json").unlink()
    _mark_interrupted(first.run_dir)
    second = _run_against_fake(tmp_path, suite, state, resume_from=first.run_dir)
    (second.run_dir / "results.json").unlink()
    _mark_interrupted(second.run_dir)
    state.turn_requests.clear()

    third = _run_against_fake(tmp_path, suite, state, resume_from=second.run_dir)

    manifest = json.loads((third.run_dir / "run_manifest.json").read_text())
    assert manifest["resumedFrom"] == second.run_id
    assert manifest["resumeAncestry"] == [first.run_id, second.run_id]
    rows = [
        json.loads(line)
        for line in (third.run_dir / "rows.jsonl").read_text().splitlines()
    ]
    assert [(row["profileId"], row["scenarioId"], row["repetition"]) for row in rows] == [
        (PROFILE_ID, "adaptive", 1),
        (PROFILE_ID, "adaptive", 2),
        (PROFILE_ID, "adaptive", 3),
    ]
    assert state.turn_requests == []


def test_a_suite_bound_to_one_source_asks_that_source_everything(
    tmp_path: Path,
) -> None:
    """The HIV comparison must not be silently answered by OpenELIS.

    A gateway serving several sources answers the default one when asked
    without a `dataSourceId`, so a suite that names a source has to carry it
    into discovery and into every session it opens -- otherwise the run looks
    healthy and measures the wrong data.
    """
    state = _WorkbenchState()
    suite = _suite_payload(dataSourceId="openmrs-hiv")
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    assert load_notebook_suite(suite_path).data_source_id == "openmrs-hiv"

    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        run_notebook_suite(
            suite_path=suite_path,
            # Built the way the CLI builds it: knowing nothing about the
            # source, so only the suite can bind it.
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    asked = [path for method, path in state.requests if method == "GET"]
    assert any(
        path.startswith("/v1/catalyst/dataset") and "dataSourceId=openmrs-hiv" in path
        for path in asked
    ), asked
    assert any(
        path.startswith("/v1/catalyst/workbench/catalog")
        and "dataSourceId=openmrs-hiv" in path
        for path in asked
    ), asked
    assert state.session_requests[0]["dataSourceId"] == "openmrs-hiv"
    assert state.turn_requests[0]["dataSourceId"] == "openmrs-hiv"


def test_a_suite_naming_no_source_still_asks_the_gateways_default(
    tmp_path: Path,
) -> None:
    state = _WorkbenchState()
    _run_against_fake(tmp_path, _suite_payload(), state)

    assert load_notebook_suite  # imported
    assert all("dataSourceId" not in path for _method, path in state.requests)
    assert "dataSourceId" not in state.session_requests[0]


def test_a_clarification_is_answered_with_no_query_to_revise(tmp_path: Path) -> None:
    """B1-B3: the opening question asked, so the answering turn revises nothing.

    The turn still has to be sent, and it cannot carry an editor snapshot
    because the session holds no query -- reading one off the absent base is
    how this used to end the run.
    """
    suite = {
        "id": "notebook-clarify-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "recent-results",
                "family": "clarification",
                "initialQuestion": "Show recent HIV results.",
                "initialProfileId": PROFILE_ID,
                "expectedBaseClassification": "not_applicable",
                "expectedBaseOutcome": "needs_clarification",
                "validateBase": False,
                "executeBase": False,
                "turns": [
                    {
                        "instruction": "The last 90 days, and only CD4 count.",
                        "profileId": PROFILE_ID,
                    }
                ],
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()
    state.base_outcome = "needs_clarification"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    assert row["baseOutcome"] == "needs_clarification"
    assert len(row["turns"]) == 1
    # The answering turn claimed nothing about a query it never received.
    request = state.turn_requests[0]
    assert request["editorSnapshot"] is None
    assert request["observedBase"] is None


def test_a_model_query_that_blows_the_row_cap_fails_the_check_not_the_run(
    monkeypatch,
) -> None:
    """An unfiltered model query is a wrong answer, not a broken harness.

    The cap exists so a runaway query cannot stall the comparison; hitting it
    proves the model's answer is far larger than the reference, which is a
    scored mismatch. Killing the whole run here would let one bad answer
    erase hours of finished work.
    """
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["patient_id"], [(f"p{i}",) for i in range(6)]),
            "reference_table": (["patient_id"], [("p1",), ("p2",)]),
        },
    )
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_id FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="row_set",
        reference_sql="SELECT patient_id FROM reference_table",
        match_columns=("patient_id",),
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics",
        max_rows=5,
    ).check(version, gold_check)

    assert result["passed"] is False
    assert result["modelRowsExceededCap"] is True
    assert result["modelRowCount"] == 5


def test_a_reference_that_blows_the_row_cap_is_a_suite_error(monkeypatch) -> None:
    """The reference is ours: if it is oversized the scenario is misauthored,
    and silently scoring against a truncated reference would be a lie."""
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["patient_id"], [("p1",)]),
            "reference_table": (["patient_id"], [(f"p{i}",) for i in range(6)]),
        },
    )
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_id FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="row_set",
        reference_sql="SELECT patient_id FROM reference_table",
        match_columns=("patient_id",),
    )

    with pytest.raises(ValueError, match="reference"):
        PostgresGoldExecutionChecker(
            "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics",
            max_rows=5,
        ).check(version, gold_check)


# --- acceptance criteria must not depend on the model's column names --------


def test_an_aggregate_value_matches_whatever_the_model_called_its_count(
    monkeypatch,
) -> None:
    """The criterion is 'count of visits by encounter type', not a spelling.

    The keys come from catalog values so they match naturally; the aggregate
    is a column the model names itself ('visit_count', 'total', ...). A
    criterion that demands our spelling scores a correct answer as wrong.
    When the row has exactly one non-key column, that is the value.
    """
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (
                ["encounter_type", "visit_count"],
                [("Adult Visit", 13369), ("Check In", 941)],
            ),
            "reference_table": (
                ["encounter_type", "visits"],
                [("Adult Visit", 13369), ("Check In", 941)],
            ),
        },
    )
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT encounter_type, count(*) AS visit_count FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="aggregate_by_key",
        reference_sql="SELECT encounter_type, visits FROM reference_table",
        key_columns=("encounter_type",),
        value_columns={"visits": {"tolerance": 0}},
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is True, result
    assert result["valueColumnResolution"] == {"visits": "visit_count"}


def test_an_ambiguous_aggregate_names_the_columns_it_could_not_choose_between(
    monkeypatch,
) -> None:
    """Two candidate value columns cannot be silently guessed between --
    and the evidence says exactly that, not a wall of row diffs."""
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (
                ["encounter_type", "n", "pct"],
                [("Adult Visit", 13369, 0.9)],
            ),
            "reference_table": (
                ["encounter_type", "visits"],
                [("Adult Visit", 13369)],
            ),
        },
    )
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT encounter_type, n, pct FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="aggregate_by_key",
        reference_sql="SELECT encounter_type, visits FROM reference_table",
        key_columns=("encounter_type",),
        value_columns={"visits": {"tolerance": 0}},
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is False
    assert "visits" in result["disagreement"]
    assert "n" in result["disagreement"] and "pct" in result["disagreement"]


def test_a_row_set_missing_its_match_column_says_so_in_one_sentence(
    monkeypatch,
) -> None:
    """A wrong criterion or projection reads as a sentence, not a row diff."""
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    _gold_check_connection(
        monkeypatch,
        {
            "model_table": (["patient_id", "value"], [("p1", 7)]),
            "reference_table": (["observation_id"], [("o1",)]),
        },
    )
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_id, value FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="row_set",
        reference_sql="SELECT observation_id FROM reference_table",
        match_columns=("observation_id",),
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is False
    assert "observation_id" in result["disagreement"]
    assert "patient_id" in result["disagreement"]


def test_a_model_query_that_times_out_fails_the_check_not_the_run(
    monkeypatch,
) -> None:
    """A query too slow to answer within the statement timeout is a wrong
    answer for this product, and the evidence says so in one sentence."""
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    cursor = _gold_check_connection(
        monkeypatch,
        {
            "reference_table": (["patient_id"], [("p1",)]),
        },
    )

    class _Timeout(Exception):
        pass

    import psycopg

    monkeypatch.setattr(psycopg.errors, "QueryCanceled", _Timeout, raising=False)
    original = cursor.execute

    def slow_execute(sql, *args, **kwargs):
        if "model_table" in sql:
            raise _Timeout("canceling statement due to statement timeout")
        return original(sql, *args, **kwargs)

    cursor.execute = slow_execute
    version = {
        "versionId": "version-1",
        "queryDigest": "a" * 64,
        "sql": "SELECT patient_id FROM model_table",
        "parameters": [],
    }
    gold_check = NotebookGoldCheck(
        mode="row_set",
        reference_sql="SELECT patient_id FROM reference_table",
        match_columns=("patient_id",),
    )

    result = PostgresGoldExecutionChecker(
        "postgresql://readonly:secret@127.0.0.1:15443/catalyst_analytics"
    ).check(version, gold_check)

    assert result["passed"] is False
    assert "statement timeout" in result["disagreement"]


def test_a_partially_repeated_pair_is_rerun_not_reused(tmp_path: Path) -> None:
    """One recorded repetition of three is not a finished pair.

    An interruption can land mid-pair; reusing what it left would score the
    pair on fewer repetitions than the suite demands, silently.
    """
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 3
    suite.pop("extendedRepetitions", None)
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    first = _run_against_fake(tmp_path, suite, state)
    rows = [
        json.loads(line)
        for line in (first.run_dir / "rows.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 3
    # The interruption left one repetition recorded and no summary.
    (first.run_dir / "rows.jsonl").write_text(
        json.dumps(rows[0]) + "\n", encoding="utf-8"
    )
    (first.run_dir / "results.json").unlink()
    _mark_interrupted(first.run_dir)
    turns_before = len(state.turn_requests)
    state.turn_requests.clear()

    resumed = _run_against_fake(tmp_path, suite, state, resume_from=first.run_dir)

    summary = json.loads((resumed.run_dir / "results.json").read_text())
    assert len(summary["results"]) == 3
    # The whole pair re-ran: partial work is measurement of nothing.
    assert len(state.turn_requests) == turns_before


def test_an_unstable_recorded_pair_is_only_reused_at_the_extended_count(
    tmp_path: Path,
) -> None:
    """Three disagreeing repetitions of a 3->5 suite are not settled evidence.

    The live scheduler would have extended them; reuse holds resumed runs to
    the same rule, and accepts the pair once the extension is recorded.
    """
    from harness.catalyst.notebook_validation import _pair_is_complete

    suite = load_notebook_suite(_write_suite(tmp_path, _adaptive_suite()))
    scenario = suite.scenarios[0]
    disagreeing = [
        _rep(True, ["ready"]),
        _rep(False, ["ready"]),
        _rep(True, ["ready"]),
    ]

    assert _pair_is_complete(disagreeing, suite, scenario, None) is False
    extended = disagreeing + [_rep(True, ["ready"]), _rep(True, ["ready"])]
    assert _pair_is_complete(extended, suite, scenario, None) is True
    # An explicit repetition override was asked for exactly that many.
    assert _pair_is_complete(disagreeing, suite, scenario, 3) is True


def test_interrupted_infrastructure_attempts_do_not_complete_a_pair(
    tmp_path: Path,
) -> None:
    """Two model runs plus one interrupted 503 are not three repetitions."""
    from harness.catalyst.notebook_validation import _pair_is_complete

    suite = load_notebook_suite(_write_suite(tmp_path, _adaptive_suite()))
    scenario = suite.scenarios[0]
    recorded = [
        _rep(True, ["ready"]),
        {"status": "infrastructure_failed", "passed": False,
         "turns": [], "assertions": []},
        _rep(True, ["ready"]),
    ]

    assert _pair_is_complete(recorded, suite, scenario, None) is False
    assert (
        _pair_is_complete(recorded + [_rep(True, ["ready"])], suite, scenario, None)
        is True
    )


def test_a_dropped_connection_is_an_infrastructure_failure_not_a_dead_run(
    tmp_path: Path,
) -> None:
    """A transport error is recorded and returned as an incomplete run."""
    state = _WorkbenchState()
    state.turn_http_sequence = [599, 201, 201, 201]
    suite = _adaptive_suite()
    suite["repetitions"] = 3
    suite["infrastructureReplacements"] = 2
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    assert result.complete is False
    assert state.turn_attempts == 1
    assert not (result.run_dir / "results.json").exists()
    status = json.loads((result.run_dir / "run-status.json").read_text())
    assert status["state"] == "incomplete"
    assert status["infrastructureFailures"][0]["httpStatus"] == 599


def test_the_client_translates_a_transport_error_into_an_exchange() -> None:
    import requests as _requests

    client = NotebookHttpClient("http://127.0.0.1:9")  # nothing listens here
    client.session = type(
        "S", (), {"request": lambda *a, **k: (_ for _ in ()).throw(
            _requests.ConnectionError("Remote end closed connection")
        )}
    )()

    exchange = client.create_session("q", "profile")

    assert exchange.status_code == 599
    message = exchange.response_body["error"]["message"]
    assert "ConnectionError" in message and "Remote end closed" in message


def test_a_resumed_run_directory_is_self_contained(tmp_path: Path) -> None:
    """Reused pairs travel with the resumed run: rows, feed, and evidence.

    Everything downstream -- the live dashboard, the report's evidence
    links, the scorer -- reads one run directory. A resume that left the
    reused pairs' rows and evidence in the old directory would show 0 done
    on the dashboard and break the report's links for exactly the work that
    was already paid for.
    """
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    first = _run_against_fake(tmp_path, suite, state)
    source_feed = read_jsonl(first.run_dir / "results.jsonl")
    # The old run recorded its pair fully; the summary vanished with the crash.
    (first.run_dir / "results.json").unlink()
    _mark_interrupted(first.run_dir)

    resumed = _run_against_fake(tmp_path, suite, state, resume_from=first.run_dir)

    rows = [
        json.loads(line)
        for line in (resumed.run_dir / "rows.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert [row["scenarioId"] for row in rows] == ["adaptive"]
    feed = [
        json.loads(line)
        for line in (resumed.run_dir / "results.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert [entry["scenario_id"] for entry in feed] == ["adaptive"]
    assert feed[0]["metrics"]["passed"] is True
    assert feed[0]["metrics"]["reused"] is True
    assert feed[0]["request"] == source_feed[0]["request"]
    assert feed[0]["response"] == source_feed[0]["response"]
    assert feed[0]["started_at"] == source_feed[0]["started_at"]
    assert feed[0]["ended_at"] == source_feed[0]["ended_at"]
    events = read_jsonl(resumed.run_dir / "events.jsonl")
    assert any(
        event["event_type"] == "scenario"
        and event["scenario_id"] == "adaptive"
        for event in events
    )
    assert any(
        event["event_type"] == "evaluation"
        and event["scenario_id"] == "adaptive"
        and event["reused"] is True
        for event in events
    )
    # The reused pair's evidence tree came along.
    assert (
        resumed.run_dir / "scenarios" / "adaptive" / "repetition-01"
        / "01-create-session.json"
    ).exists()


def test_a_literal_percent_survives_the_driver_conversion() -> None:
    """'CD4%' is data, not a placeholder.

    psycopg treats % as a placeholder marker whenever a params argument is
    passed, so every literal percent must be doubled by the conversion --
    with or without named parameters present. The second full comparison
    died on exactly this, executing a reference that filters on 'CD4%'.
    """
    from harness.catalyst.notebook_validation import _driver_sql

    plain = _driver_sql(
        "SELECT 1 FROM t WHERE name IN ('CD4 count', 'CD4%')", set()
    )
    assert "'CD4%%'" in plain

    mixed = _driver_sql(
        "SELECT 1 FROM t WHERE name LIKE '%viral%' AND day >= :since",
        {"since"},
    )
    assert "'%%viral%%'" in mixed
    assert "%(since)s" in mixed


def test_the_opening_generation_is_token_checked_like_any_other(
    tmp_path: Path,
) -> None:
    """A base-only scenario's only generation is the opening one.

    A1-A4 have no follow-ups, so asserting token evidence only inside the
    turn loop let them pass with the requirement never exercised -- a
    vacuous pass the roadmap's 'complete token evidence' gate exists to
    forbid.
    """
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite["requireTokenEvidence"] = True
    suite.pop("extendedRepetitions", None)
    suite["scenarios"][0].pop("followupInstruction", None)
    suite["scenarios"][0].pop("followupProfileId", None)
    suite["scenarios"][0]["turns"] = []
    suite["scenarios"][0]["expectedBaseOutcome"] = "ready"

    result = _run_against_fake(tmp_path, suite, state)

    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    names = {a["name"]: a["passed"] for a in row["assertions"]}
    assert "token_evidence_recorded-base" in names
    # The fake's evidence carries no accounting, so a requiring suite fails.
    assert names["token_evidence_recorded-base"] is False
    assert row["passed"] is False


def test_a_suite_not_requiring_tokens_records_the_base_absence_honestly(
    tmp_path: Path,
) -> None:
    """Absent accounting on the opening turn is recorded, not failed."""
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)

    result = _run_against_fake(tmp_path, suite, state)

    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    base = [a for a in row["assertions"] if a["name"] == "token_evidence_recorded-base"]
    assert base and base[0]["passed"] is True
    assert base[0]["evidence"] == {"recorded": False, "required": False}


def test_a_deterministic_answer_with_no_model_call_owes_no_token_evidence() -> None:
    """Zero invocations means nothing was rendered or sent.

    B1's opening question is answered by the catalog-scope preflight -- no
    model call -- and the run scored that honest absence as a failure. An
    affirmatively empty invocation list passes with the absence recorded;
    a missing list stays strict, so a turn cannot dodge the check by not
    recording its calls.
    """
    zero_calls = {"invocations": [], "tokenAccounting": None}
    checks = dict(
        (name, (passed, detail))
        for name, passed, detail in token_evidence_checks(zero_calls)
    )
    passed, detail = checks["token_evidence_recorded"]
    assert passed is True
    assert detail == {"recorded": False, "modelInvocations": 0}

    no_record = {"tokenAccounting": None}
    checks = dict(
        (name, passed) for name, passed, _ in token_evidence_checks(no_record)
    )
    assert checks["token_evidence_recorded"] is False

    called_but_uncounted = {
        "invocations": [{"role": "writer", "outcome": "succeeded"}],
        "tokenAccounting": None,
    }
    checks = dict(
        (name, passed)
        for name, passed, _ in token_evidence_checks(called_but_uncounted)
    )
    assert checks["token_evidence_recorded"] is False


def test_a_scenario_pins_its_guidance_after_the_opening_answer(
    tmp_path: Path,
) -> None:
    """M2's pin is part of the scenario, not something the turns restate.

    The suite declares what gets pinned; the runner pins it through the same
    HTTP surface a person uses, after the opening answer and before any
    follow-up, and records the exchange as evidence.
    """
    state = _WorkbenchState()
    suite = _adaptive_suite()
    suite["repetitions"] = 1
    suite.pop("extendedRepetitions", None)
    suite["scenarios"][0]["pinGuidance"] = ["Exclude do_not_perform requests."]

    result = _run_against_fake(tmp_path, suite, state)

    pins = [
        (method, path, body)
        for method, path, body in state.posts
        if path.endswith("/guidance")
    ]
    assert len(pins) == 1
    assert pins[0][2]["text"] == "Exclude do_not_perform requests."
    row = json.loads((result.run_dir / "results.json").read_text())["results"][0]
    names = {a["name"]: a["passed"] for a in row["assertions"]}
    assert names.get("guidance_pinned") is True
    repetition_dir = next((result.run_dir / "scenarios").glob("*/repetition-01"))
    assert (repetition_dir / "04-pin-guidance-01.json").exists()
    # The pin precedes the follow-up turn.
    order = [p for _m, p, _b in state.posts]
    assert order.index(pins[0][1]) < order.index(
        next(p for p in order if p.endswith("/turns"))
    )


def test_a_bare_string_pin_is_refused_not_pinned_per_character(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="pinGuidance must be a list"):
        load_notebook_suite(
            _write_suite(
                tmp_path,
                _suite_payload(
                    scenarios=[
                        {
                            **_suite_payload()["scenarios"][0],
                            "pinGuidance": "Exclude do_not_perform requests.",
                        }
                    ]
                ),
            )
        )


def test_a_failed_pin_surfaces_in_the_rows_http_status(tmp_path: Path) -> None:
    """A 5xx pin is host trouble like any other 5xx step."""
    from harness.catalyst.notebook_validation import _normalized_http_status

    prefix = "scenarios/s1/repetition-01"
    step = tmp_path / prefix
    step.mkdir(parents=True)
    (step / "04-pin-guidance-01.json").write_text(
        json.dumps({"response": {"httpStatus": 503}}), encoding="utf-8"
    )

    assert _normalized_http_status(tmp_path, prefix) == 503


def test_every_failing_gold_verdict_says_why_in_one_sentence(monkeypatch) -> None:
    """A reviewer clicking a red cell reads a sentence, not a JSON diff.

    Two of four live reds showed raw structures because only the shape
    failures carried a `disagreement`; the count, aggregate, and row-set
    mismatch paths now write theirs too.
    """
    from harness.catalyst.notebook_validation import (
        PostgresGoldExecutionChecker,
        NotebookGoldCheck,
    )

    def run(tables, sql, gold):
        _gold_check_connection(monkeypatch, tables)
        version = {"versionId": "v", "queryDigest": "a" * 64,
                   "sql": sql, "parameters": []}
        return PostgresGoldExecutionChecker(
            "postgresql://readonly:secret@127.0.0.1:15443/x"
        ).check(version, gold)

    counted = run(
        {"model_table": (["n"], [(1,), (2,), (3,)]),
         "reference_table": (["n"], [(1,), (2,)])},
        "SELECT n FROM model_table",
        NotebookGoldCheck(mode="count", reference_sql="SELECT n FROM reference_table"),
    )
    assert counted["passed"] is False
    assert counted["disagreement"] == (
        "the answer returned 3 rows; the independent reference returns 2"
    )

    grouped = run(
        {"model_table": (["k", "c"], [("a", 5), ("b", 9), ("c", 1)]),
         "reference_table": (["k", "c"], [("a", 5), ("b", 7)])},
        "SELECT k, c FROM model_table",
        NotebookGoldCheck(
            mode="aggregate_by_key",
            reference_sql="SELECT k, c FROM reference_table",
            key_columns=("k",),
            value_columns={"c": {"tolerance": 0}},
        ),
    )
    assert grouped["passed"] is False
    assert "1 group the reference does not have" in grouped["disagreement"]
    assert "'b': 9 vs 7" in grouped["disagreement"]

    rowset = run(
        {"model_table": (["id"], [("x",), ("y",)]),
         "reference_table": (["id"], [("x",), ("z",)])},
        "SELECT id FROM model_table",
        NotebookGoldCheck(
            mode="row_set",
            reference_sql="SELECT id FROM reference_table",
            match_columns=("id",),
        ),
    )
    assert rowset["passed"] is False
    assert "1 row missing from the answer and 1 extra" in rowset["disagreement"]


def test_every_failing_gold_mode_says_why_in_one_sentence() -> None:
    """The PR's contract, held for the paths review found silent or wrong:
    a capped answer, a scalar mismatch, and one group wrong in two value
    columns (one group, not 'two groups')."""
    from harness.catalyst.notebook_validation import (
        _compare_aggregates,
        _compare_scalars,
    )

    scalar = _compare_scalars(
        [{"patient_count": 11}], [{"patient_count": 6}], "patient_count"
    )
    assert scalar["passed"] is False
    assert scalar["disagreement"] == (
        "the answer's patient_count is 11; the independent reference says 6"
    )

    verdict = _compare_aggregates(
        [{"g": "a", "n": 1, "m": 9}],
        [{"g": "a", "n": 2, "m": 8}],
        key_columns=["g"],
        value_columns={"n": {}, "m": {}},
    )
    assert verdict["passed"] is False
    assert "counts disagree on 1 group " in verdict["disagreement"] + " "


def test_every_assertion_the_runner_can_emit_is_classified():
    """The conformance/evaluation split is a closed contract.

    A new check that nobody classified would silently decide whether a cell
    reads as unexpected behaviour, so the table must cover every name the
    module can emit. Extracted from the source itself, so adding an
    assertion without classifying it fails here.
    """
    import ast

    from harness.catalyst import notebook_validation as nv

    source = Path(nv.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    emitted: set[str] = set()
    for node in ast.walk(tree):
        # check("name", ...) and check(f"{name}-base", ...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "check"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            emitted.add(node.args[0].value)
        # {"name": "literal", "passed": ...} appended directly
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            if "name" in keys and "passed" in keys:
                value = node.values[keys.index("name")]
                if isinstance(value, ast.Constant):
                    emitted.add(value.value)
    # The helpers yield (name, passed, evidence) tuples.
    for helper in ("_evidence_checks", "token_evidence_checks"):
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == helper:
                for inner in ast.walk(node):
                    if (
                        isinstance(inner, ast.Tuple)
                        and inner.elts
                        and isinstance(inner.elts[0], ast.Constant)
                        and isinstance(inner.elts[0].value, str)
                    ):
                        emitted.add(inner.elts[0].value)

    assert len(emitted) > 30, "the extractor stopped finding assertions"
    unclassified = sorted(n for n in emitted if not nv.assertion_class(n, strict=True))
    assert unclassified == []


def test_the_split_puts_judgment_on_one_side_and_the_contract_on_the_other():
    """Judged quality never colours a cell; broken behaviour always does."""
    from harness.catalyst.notebook_validation import assertion_class

    for name in (
        "base_writer_outcome",
        "writer_outcome",
        "followup_terminal_status",
        "base_gold_execution_match",
        "successor_gold_execution_match",
        "successor_execution_succeeded",
        "exact_selected_output",
        "prior_results_stale_after_successor",
        "semantic_reviewer_correction",
    ):
        assert assertion_class(name) == "evaluation", name

    for name in (
        "no_sql_after_non_ready_base",
        "token_evidence_recorded",
        "writer_model",
        "effective_temperature_and_dry",
        "guidance_pinned",
        "session_created",
        "base_classification",
        "revision_context_exclusions",
        "new_session_isolation",
    ):
        assert assertion_class(name) == "conformance", name

    # Slot suffixes are the same check on a later turn.
    assert assertion_class("writer_outcome-t3") == "evaluation"
    assert assertion_class("token_evidence_recorded-base") == "conformance"
    # An unknown check fails loud rather than passing as mere data.
    assert assertion_class("brand_new_check") == "conformance"
    assert assertion_class("brand_new_check", strict=True) is None


def test_the_dashboard_feed_carries_the_words_of_the_conversation(
    tmp_path: Path,
) -> None:
    """A refusal or a clarifying question IS the model's answer.

    The feed row is what the live dashboard renders, so when the writer
    declines it has to carry the sentence the writer wrote -- otherwise the
    cell shows a status where a conversation happened.
    """
    suite = {
        "id": "notebook-unsupported-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "no-address",
                "family": "unsupported",
                "initialQuestion": "Show each patient's home address.",
                "initialProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
                "expectedBaseOutcome": "unsupported",
                "validateBase": False,
                "executeBase": False,
                "turns": [],
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()
    state.base_outcome = "unsupported"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    feed = [
        json.loads(line)
        for line in (result.run_dir / "results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    response = feed[0]["response"]
    assert response["baseAnswerText"] == "The data records no home address."
    assert response["baseOutcome"] == "unsupported"
    # Every failed check reaching the dashboard says which kind it is.
    assert all("class" in item for item in response["failedAssertions"])


def test_every_generated_query_is_visible_in_the_feed(tmp_path: Path) -> None:
    """A reader following a conversation needs each turn's SQL, in place.

    The feed used to carry only the final selected query, so a multi-turn
    cell showed one query where three were written. The base turn's SQL and
    every follow-up's SQL now travel with the row, separate from the words
    a refusal or a question uses.
    """
    suite = {
        "id": "notebook-sql-visibility-v1",
        "datasetId": "catalyst-cohort-v1",
        "datasetVersion": "1",
        "catalogVersion": "analytics-catalog-v1",
        "providerName": "llama.cpp",
        "repetitions": 1,
        "profiles": {
            PROFILE_ID: {
                "writerModelId": "gemma-4-12b",
                "reviewerModelId": "qwen2.5-14b",
            }
        },
        "scenarios": [
            {
                "id": "refine-once",
                "family": "multiturn",
                "initialQuestion": "Show lab patients.",
                "initialProfileId": PROFILE_ID,
                "expectedBaseClassification": "reused",
                "expectedBaseOutcome": "ready",
                "validateBase": False,
                "executeBase": False,
                "turns": [
                    {"instruction": "Distinct patients only.",
                     "profileId": PROFILE_ID}
                ],
            }
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    state = _WorkbenchState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_notebook_suite(
            suite_path=suite_path,
            client=NotebookHttpClient(f"http://127.0.0.1:{server.server_port}"),
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    feed = [
        json.loads(line)
        for line in (result.run_dir / "results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    response = feed[0]["response"]
    assert str(response["baseSql"]).startswith("SELECT")
    turn = response["turns"][0]
    assert str(turn["sql"]).startswith("SELECT")
    # The base is the OPENING query. The session head moves as turns land,
    # so recording the head at the end showed the final query where the
    # first belongs -- three judges independently flagged it.
    assert response["baseSql"] != turn["sql"]
    # The identifiers travel with the same opening version, not the head.
    row = json.loads(
        (result.run_dir / "results.json").read_text(encoding="utf-8")
    )["results"][0]
    assert row["baseVersionId"] != row["selectedVersionId"]
    assert row["baseQueryDigest"] != row["selectedQueryDigest"]
