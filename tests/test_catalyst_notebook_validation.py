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
    HttpExchange,
    NotebookHttpClient,
    NotebookQuery,
    PostgresReadOnlyChecker,
    _binding_value,
    _driver_sql,
    _find_forbidden_keys,
    _json_safe_value,
    _parse_timestamp,
    _require_discovery,
    load_notebook_suite,
    query_digest,
    run_notebook_suite,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE_ID = "catalyst-query-gemma-4-12b"


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


def _evidence(turn_id: str, instruction: str) -> dict[str, Any]:
    invocations = []
    for index, (role, model_id) in enumerate(
        (("writer", "gemma-4-12b"), ("reviewer", "qwen2.5-14b")), start=1
    ):
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
        "totalInvocationDurationMs": 10,
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
        self.requests: list[tuple[str, str]] = []

    def session(self) -> dict[str, Any]:
        return {
            "contractVersion": "catalyst.workbench.session.v1",
            "sessionId": "session-1",
            "question": "Show patient identifiers.",
            "profileId": PROFILE_ID,
            "datasetId": "pipeline-1",
            "datasetVersion": "pipeline-1",
            "catalogVersion": "analytics-catalog-v1+schema.1234567890abcdef",
            "currentVersionId": self.current["versionId"],
            "browserState": {},
            "provenance": {},
            "status": "ready",
            "createdAt": "2026-07-20T12:00:00Z",
            "updatedAt": "2026-07-20T12:00:03Z",
            "versions": self.versions,
            "currentVersion": self.current,
            "validations": [],
            "latestValidation": None,
            "executions": self.executions,
        }

    def initial_turn(self) -> dict[str, Any]:
        return {
            "contractVersion": "catalyst.workbench.turn.v1",
            "sessionId": "session-1",
            "turnId": "turn-initial",
            "ordinal": 1,
            "kind": "initial",
            "status": "completed",
        }

    def timeline(self) -> dict[str, Any]:
        turns = [self.initial_turn()]
        if self.followup_turn is not None:
            turns.append(self.followup_turn)
        return {
            "contractVersion": "catalyst.workbench.turn.timeline.v1",
            "sessionId": "session-1",
            "currentTurnId": turns[-1]["turnId"],
            "currentVersion": {
                "versionId": self.current["versionId"],
                "queryDigest": self.current["queryDigest"],
            },
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
            if self.path == "/v1/catalyst/query-options":
                self._send(
                    200,
                    {
                        "profiles": [
                            {
                                "id": PROFILE_ID,
                                "available": True,
                                "revisionCapable": True,
                                "role_models": {
                                    "query_generate": "gemma-4-12b",
                                    "query_review": "qwen2.5-14b",
                                },
                            }
                        ]
                    },
                )
            elif self.path == "/v1/catalyst/dataset":
                self._send(
                    200,
                    {
                        "contractVersion": "catalyst.dataset-overview.v1",
                        "datasetId": "pipeline-1",
                        "pipelineRunId": "pipeline-1",
                    },
                )
            elif self.path == "/v1/catalyst/workbench/catalog":
                self._send(
                    200,
                    {
                        "contractVersion": "catalyst.workbench.editor-catalog.v1",
                        "catalogVersion": "analytics-catalog-v1+schema.1234567890abcdef",
                    },
                )
            elif self.path == "/v1/catalyst/workbench/sessions/session-1":
                self._send(200, state.session())
            elif self.path == "/v1/catalyst/workbench/sessions/session-1/turns":
                self._send(200, state.timeline())
            elif self.path.endswith("turn-initial/generation-evidence"):
                self._send(200, _evidence("turn-initial", "Show patient identifiers."))
            elif self.path.endswith("turn-followup/generation-evidence"):
                self._send(
                    200,
                    _evidence("turn-followup", "Return only distinct patients."),
                )
            else:
                self._send(404, {"error": {"code": "not_found"}})

        def do_POST(self) -> None:  # noqa: N802
            state.requests.append(("POST", self.path))
            body = self._body()
            if self.path == "/v1/catalyst/workbench/sessions":
                self._send(201, state.session())
            elif self.path == "/v1/catalyst/workbench/sessions/session-1/versions":
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
            elif self.path == "/v1/catalyst/workbench/sessions/session-1/turns":
                successor = _version(
                    "version-3",
                    "SELECT DISTINCT patient_id FROM analytics.lab_result_fact_v1",
                    parent=state.current["versionId"],
                )
                successor["authorType"] = "model_repair"
                state.versions.append(successor)
                state.current = successor
                state.followup_turn = {
                    "contractVersion": "catalyst.workbench.turn.v1",
                    "sessionId": "session-1",
                    "turnId": "turn-followup",
                    "ordinal": 2,
                    "kind": "followup",
                    "status": "completed",
                    "snapshotClassification": "reused",
                    "manualVersion": None,
                    "profileSnapshot": {"profileId": PROFILE_ID},
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
    results = json.loads((result.run_dir / "results.json").read_text())
    assert results["results"][0]["status"] == "failed_before_turn"
    assert results["results"][0]["sessionId"] is None


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

    assert checkpoints == [("unchanged", "session-1")]
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
    assert json.loads(capsys.readouterr().out) == {
        "run_id": "run-1",
        "run_dir": str(tmp_path / "run-1"),
        "passed": 2,
        "total": 2,
        "skipped": 1,
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

    assert exit_info.value.code == 1
    assert captured["postgres_checker"] is None
    capsys.readouterr()
