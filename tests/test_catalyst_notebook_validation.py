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
    assert "events.jsonl" not in indexed_paths
    assert "results.jsonl" not in indexed_paths


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
    from harness.catalyst.report import _headline_section

    html = _headline_section(
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


class _CrashingClient(_StubClient):
    """Raises on the Nth call to create_session, simulating a hard crash
    (e.g. a dropped connection) partway through a multi-scenario run."""

    def __init__(self, *, crash_on_call: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._create_session_calls = 0
        self._crash_on_call = crash_on_call

    def create_session(self, question: str, profile_id: str) -> HttpExchange:
        self._create_session_calls += 1
        if self._create_session_calls == self._crash_on_call:
            raise RuntimeError("simulated transport failure")
        return super().create_session(question, profile_id)


def test_results_jsonl_streams_incrementally_and_survives_a_mid_run_crash(
    tmp_path: Path,
) -> None:
    """The whole point of streaming: a crash mid-run must not erase evidence
    for scenarios that already completed. results.json/evidence-index.json
    are written once at the very end (recorder.finish()), so a crash means
    neither exists — but the streamed .jsonl rows for the first scenario
    must already be on disk."""
    suite_path = _write_suite(
        tmp_path,
        _suite_payload(
            scenarios=[
                {**_suite_payload()["scenarios"][0], "id": "first"},
                {**_suite_payload()["scenarios"][0], "id": "second"},
            ]
        ),
    )
    client = _CrashingClient(crash_on_call=2, session_status=503, session_body={})

    with pytest.raises(RuntimeError, match="simulated transport failure"):
        run_notebook_suite(
            suite_path=suite_path,
            client=client,
            output_dir=tmp_path / "artifacts",
            project_root=ROOT,
            provenance_loader=lambda _: [],
        )

    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    assert not (run_dir / "results.json").exists()
    assert not (run_dir / "evidence-index.json").exists()

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
    assert row["metrics"]["passed"] is False
    assert row["metrics"]["http_status"] == 503
    assert row["metrics"]["latency_ms"] is None
    assert row["error"] is not None


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
    assert isinstance(captured["gold_checker"], PostgresGoldExecutionChecker)
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
    assert captured["gold_checker"] is None
    capsys.readouterr()
