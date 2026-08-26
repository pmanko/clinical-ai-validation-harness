"""Real-path validation for the Catalyst iterative query notebook.

The older Catalyst runner exercises the governed-preview API.  This module is
deliberately separate: it follows the workbench session, immutable-version,
turn, validation, execution, and generation-evidence contracts used by the UI.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time as datetime_time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse
from uuid import UUID, uuid4

from urllib.parse import quote

import requests
import rfc8785

from ..common.jsonl import append_jsonl
from ..metadata import RunManifest, append_event
from ..submodules import read_harness_git_sha
from .events import NOTEBOOK_EVENT_SCHEMA_VERSION, notebook_result_events
from .run_config import publishable
from .validation import _response_payload, _target_provenance


@dataclass(frozen=True)
class NotebookQuery:
    sql: str
    parameters: tuple[dict[str, Any], ...] = ()
    expected_columns: tuple[dict[str, Any], ...] = ()

    def content(self) -> dict[str, Any]:
        return {
            "sql": self.sql,
            "parameters": [dict(item) for item in self.parameters],
            "expectedColumns": [dict(item) for item in self.expected_columns],
        }


_GOLD_CHECK_MODES = frozenset({"count", "row_set", "aggregate_by_key", "scalar"})
_PHASE1_COMPARISON_SUITE_PREFIX = "catalyst-phase1-comparison-"

# Reference SQL for a gold execution-match check runs directly against the
# analytics database outside the Gateway's write-blocking policy layer, so it
# gets its own defense-in-depth guard against write/DDL verbs.
_DISALLOWED_SQL_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "grant",
    "revoke",
    "create",
    "copy",
    "call",
    "merge",
)


def _guard_reference_sql(sql: str) -> None:
    lowered = sql.lower()
    for keyword in _DISALLOWED_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise ValueError(
                "gold check reference SQL must be read-only; found disallowed "
                f"keyword {keyword!r}"
            )


@dataclass(frozen=True)
class NotebookGoldCheck:
    """Proves a model's own SQL — executed directly and unbounded, bypassing
    the Gateway's UI row cap — matches a hand-authored reference query's
    intent, rather than merely matching its own (possibly truncated) page."""

    mode: str
    reference_sql: str
    reference_parameters: tuple[dict[str, Any], ...] = ()
    match_columns: tuple[str, ...] = ()
    normalizers: dict[str, str] = field(default_factory=dict)
    key_columns: tuple[str, ...] = ()
    value_columns: dict[str, dict[str, Any]] = field(default_factory=dict)
    value_column: str | None = None


def _load_gold_check(payload: dict[str, Any] | None) -> NotebookGoldCheck | None:
    if payload is None:
        return None
    mode = str(payload["mode"])
    if mode not in _GOLD_CHECK_MODES:
        raise ValueError(f"unknown gold check mode {mode!r}")
    reference_sql = str(payload["referenceSql"])
    _guard_reference_sql(reference_sql)
    match_columns = tuple(str(c) for c in payload.get("matchColumns", []))
    normalizers = {
        str(column): str(normalizer)
        for column, normalizer in payload.get("normalizers", {}).items()
    }
    key_columns = tuple(str(c) for c in payload.get("keyColumns", []))
    value_columns = {
        str(k): dict(v) for k, v in payload.get("valueColumns", {}).items()
    }
    value_column = payload.get("valueColumn")
    if mode == "row_set" and not match_columns:
        raise ValueError("row_set gold check requires matchColumns")
    if normalizers and mode != "row_set":
        raise ValueError("gold check normalizers are supported only for row_set")
    unknown_normalizer_columns = sorted(set(normalizers) - set(match_columns))
    if unknown_normalizer_columns:
        raise ValueError(
            "gold check normalizers name columns outside matchColumns: "
            f"{unknown_normalizer_columns}"
        )
    unsupported_normalizers = sorted(
        {
            normalizer
            for normalizer in normalizers.values()
            if normalizer != "unordered_csv"
        }
    )
    if unsupported_normalizers:
        raise ValueError(
            f"unsupported gold check normalizers: {unsupported_normalizers}"
        )
    if mode == "aggregate_by_key" and (not key_columns or not value_columns):
        raise ValueError(
            "aggregate_by_key gold check requires keyColumns and valueColumns"
        )
    if mode == "scalar" and not value_column:
        raise ValueError("scalar gold check requires valueColumn")
    return NotebookGoldCheck(
        mode=mode,
        reference_sql=reference_sql,
        reference_parameters=tuple(
            dict(p) for p in payload.get("referenceParameters", [])
        ),
        match_columns=match_columns,
        normalizers=normalizers,
        key_columns=key_columns,
        value_columns=value_columns,
        value_column=str(value_column) if value_column else None,
    )


WRITER_OUTCOMES = ("ready", "needs_clarification", "unsupported")
# A question and a refusal both end a generation with no SQL.
TERMINAL_WRITER_OUTCOMES = frozenset(WRITER_OUTCOMES[1:])
"""The writer's terminal choices. `rejected` is the Gateway's, not one of these."""


_SLOT_SUFFIX = re.compile(r"-(?:t\d+|base)$")

EVALUATION_ASSERTIONS = frozenset(
    {
        # How good the answer was. Every one of these can fail while the
        # product behaves exactly as designed -- a refusal, a question, a
        # rejected revision and a query killed by the statement timeout are
        # all allowed paths.
        "base_writer_outcome",
        "writer_outcome",
        "followup_terminal_status",
        "base_execution_succeeded",
        "successor_execution_succeeded",
        "base_gold_execution_match",
        "successor_gold_execution_match",
        "base_postgres_crosscheck",
        "successor_postgres_crosscheck",
        "exact_selected_output",
        "prior_results_stale_after_successor",
        "semantic_reviewer_correction",
    }
)
"""Judgments about the answer. These never mean the run misbehaved."""

CONFORMANCE_ASSERTIONS = frozenset(
    {
        # The product's and the harness's own contract: session protocol,
        # persisted state, evidence, configuration and safety. A failure
        # here is unexpected behaviour and invalidates the measurement.
        "session_created",
        "new_session_isolation",
        "initial_turn_recorded",
        "initial_evidence_available",
        "followup_http_created",
        "followup_evidence_available",
        "followup_profile",
        "base_version_available",
        "base_version_saved",
        "base_validation_recorded",
        "successor_validation_recorded",
        "successor_visible_under_three_minutes",
        "base_classification",
        "manual_version_classification",
        "failed_turn_preserved_base",
        "refresh_restored",
        "timeline_current_turn",
        "no_sql_after_non_ready_base",
        "no_sql_after_non_ready_outcome",
        "guidance_pinned",
        "token_evidence_recorded",
        "token_budget_respected",
        "writer_model",
        "reviewer_model",
        "effective_temperature_and_dry",
        "hub_request_evidence",
        "hub_request_digest_match",
        "hub_capacity_evidence",
        "retained_instruction_context",
        "invocation_digests",
        "invocation_duration_sum",
        "invocation_timestamp_reconciliation",
        "revision_context_exclusions",
    }
)
"""Contract checks. A failure here means the run, not the model, went wrong."""


def assertion_class(name: str, *, strict: bool = False) -> str | None:
    """Whether `name` judges the answer or checks the contract.

    Slot suffixes (`-base`, `-t2`) are the same check on another turn. An
    unclassified name is treated as a contract check so a new failure is
    loud rather than quietly filed as data; `strict=True` returns None
    instead, which is how the coverage test finds names nobody classified.
    """
    root = _SLOT_SUFFIX.sub("", name)
    if root in EVALUATION_ASSERTIONS:
        return "evaluation"
    if root in CONFORMANCE_ASSERTIONS:
        return "conformance"
    return None if strict else "conformance"


def writer_outcome(turn: dict[str, Any]) -> str:
    """Which terminal answer the writer gave for this turn.

    Catalyst does not publish a turn-level outcome yet: a clarification
    arrives as a failed turn whose failure code names the writer's choice.
    The published field wins as soon as it exists, so the runner reads the
    same vocabulary before and after that contract lands. Anything else that
    failed is the Gateway's `rejected`, which is not a writer answer.
    """
    published = turn.get("writerOutcome")
    if published in WRITER_OUTCOMES:
        return str(published)
    if turn.get("status") == "completed":
        return "ready"
    failure = turn.get("failure")
    code = failure.get("code") if isinstance(failure, dict) else None
    if code in WRITER_OUTCOMES:
        return str(code)
    return "rejected"


MODEL_TRANSPORT_STAGES = frozenset({"writer_transport", "reviewer_transport"})
COLLECTION_INTERRUPTION_STAGES = frozenset(
    {
        *MODEL_TRANSPORT_STAGES,
        "gateway_persistence",
        "orphan_recovery",
    }
)


def _persisted_service_interruption(turn: dict[str, Any]) -> dict[str, Any] | None:
    """Return a service interruption recorded inside a successful reply.

    Catalyst persists an upstream timeout or connection failure as a failed
    turn and still returns the workbench resource successfully.  The stage is
    the contract boundary: other failed turns are model answers or product
    behavior and remain part of the experiment.
    """
    failure = turn.get("failure")
    if (
        turn.get("status") == "failed"
        and isinstance(failure, dict)
        and failure.get("stage") in COLLECTION_INTERRUPTION_STAGES
    ):
        return failure
    return None


@dataclass(frozen=True)
class NotebookTurn:
    """One follow-up the operator sends after the session question.

    A scenario is the session question plus these, in order. Suites written
    before multi-turn scenarios describe exactly one, so the sequence is how
    every scenario is executed regardless of which form declared it.
    """

    instruction: str
    profile_id: str
    expected_turn_status: str = "completed"
    expected_outcome: str = "ready"
    gold_check: NotebookGoldCheck | None = None


@dataclass(frozen=True)
class NotebookScenario:
    id: str
    family: str
    initial_question: str
    initial_profile_id: str
    turns: tuple[NotebookTurn, ...]
    editor_query: NotebookQuery | None
    persist_editor_query: bool
    expected_base_classification: str
    validate_base: bool
    execute_base: bool
    validate_successor: bool
    execute_successor: bool
    repetitions: int | None
    manual_only: bool
    require_reviewer_correction: bool
    base_gold_check: NotebookGoldCheck | None = None
    successor_gold_check: NotebookGoldCheck | None = None
    expected_base_outcome: str = "ready"
    # Standing instructions pinned to the session after the opening answer,
    # before any follow-up -- exactly as a person would pin them.
    pin_guidance: tuple[str, ...] = ()

    @property
    def scored_on_the_opening_question_alone(self) -> bool:
        """The writer asked or refused, so nothing follows it."""

        return not self.turns

    @property
    def expected_turn_status(self) -> str:
        return self.turns[0].expected_turn_status if self.turns else "failed"

    @property
    def followup_instruction(self) -> str:
        return self.turns[0].instruction if self.turns else ""

    @property
    def followup_profile_id(self) -> str:
        # A scenario scored on its opening question alone was still run
        # by a profile: the one that answered it.
        return self.turns[0].profile_id if self.turns else self.initial_profile_id


@dataclass(frozen=True)
class NotebookSuite:
    id: str
    dataset_id: str
    dataset_version: str
    catalog_version: str
    provider_name: str
    repetitions: int
    extended_repetitions: int | None
    require_token_evidence: bool
    profiles: dict[str, dict[str, str | None]]
    scenarios: tuple[NotebookScenario, ...]
    # The teams this suite compares, in the order they are run. Empty means
    # the suite is not a comparison: each scenario uses the profile it names.
    comparison_profiles: tuple[str, ...] = ()
    # The gateway serves several sources and answers its default when not
    # told which; a suite bound to one names it so nothing else can answer.
    data_source_id: str | None = None


@dataclass(frozen=True)
class HttpExchange:
    method: str
    path: str
    status_code: int
    request_body: dict[str, Any] | None
    response_body: dict[str, Any]
    elapsed_ms: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": "harness.catalyst-notebook.http-exchange.v1",
            "request": {
                "method": self.method,
                "path": self.path,
                "body": self.request_body,
            },
            "response": {
                "httpStatus": self.status_code,
                "body": self.response_body,
            },
            "elapsedMs": self.elapsed_ms,
        }


class _CollectionInterrupted(RuntimeError):
    """A recorded dependency failure that stops the current collection."""

    def __init__(
        self,
        evidence_path: str,
        exchange: HttpExchange | None,
        *,
        recorded_failure: dict[str, Any] | None = None,
        interruption_kind: str | None = None,
        interruption_code: str | None = None,
    ) -> None:
        if recorded_failure is None and exchange is not None:
            message = f"{evidence_path} returned HTTP {exchange.status_code}"
        else:
            stage = (recorded_failure or {}).get("stage") or interruption_kind
            code = (recorded_failure or {}).get("code") or interruption_code
            label = ":".join(str(value) for value in (stage, code) if value)
            message = f"{evidence_path} recorded {label or 'a service interruption'}"
        super().__init__(message)
        self.evidence_path = evidence_path
        self.exchange = exchange
        self.recorded_failure = recorded_failure
        self.interruption_kind = interruption_kind
        self.interruption_code = interruption_code


def _carry_recorded_failure(
    interruption: _CollectionInterrupted,
    recorded_failure: dict[str, Any] | None,
) -> _CollectionInterrupted:
    """Keep an already persisted turn failure when a later evidence call fails."""
    if recorded_failure is None or interruption.recorded_failure is not None:
        return interruption
    return _CollectionInterrupted(
        interruption.evidence_path,
        interruption.exchange,
        recorded_failure=recorded_failure,
        interruption_kind=interruption.interruption_kind,
        interruption_code=interruption.interruption_code,
    )


@dataclass(frozen=True)
class NotebookRunResult:
    run_id: str
    run_dir: Path
    result_count: int
    passed_count: int
    skipped_count: int
    complete: bool
    measurement_valid: bool


class NotebookTransport(Protocol):
    def profiles(self) -> HttpExchange: ...

    def dataset_overview(self) -> HttpExchange: ...

    def catalog(self) -> HttpExchange: ...

    def create_session(self, question: str, profile_id: str) -> HttpExchange: ...

    def pin_guidance(self, session_id: str, text: str) -> HttpExchange: ...

    def get_session(self, session_id: str) -> HttpExchange: ...

    def get_turns(self, session_id: str) -> HttpExchange: ...

    def generation_evidence(self, session_id: str, turn_id: str) -> HttpExchange: ...

    def save_version(
        self,
        session_id: str,
        query: NotebookQuery,
        parent: dict[str, Any] | None,
    ) -> HttpExchange: ...

    def validate_version(self, version_id: str) -> HttpExchange: ...

    def execute_version(self, version: dict[str, Any]) -> HttpExchange: ...

    def create_turn(
        self,
        session_id: str,
        *,
        instruction: str,
        profile_id: str,
        observed_base: dict[str, str] | None,
        editor_snapshot: dict[str, Any] | None,
    ) -> HttpExchange: ...


class PostgresChecker(Protocol):
    def check(
        self,
        version: dict[str, Any],
        execution: object,
    ) -> dict[str, Any]: ...


class GoldChecker(Protocol):
    def check(
        self,
        version: dict[str, Any],
        gold_check: "NotebookGoldCheck",
    ) -> dict[str, Any]: ...


class NotebookHttpClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: int = 240,
        data_source_id: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.data_source_id = data_source_id
        self.session = requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> HttpExchange:
        started = time.monotonic()
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                json=body,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as error:
            # Preserve a transport failure as an exchange. The collection
            # runner records it, stops, and returns the evidence location so
            # the operator can resume explicitly.
            return HttpExchange(
                method=method,
                path=path,
                status_code=599,
                request_body=body,
                response_body={
                    "error": {
                        "code": "transport_failed",
                        # Some RequestException variants stringify to nothing;
                        # the class name keeps the evidence diagnosable.
                        "message": f"{type(error).__name__}: {error}",
                    }
                },
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return HttpExchange(
            method=method,
            path=path,
            status_code=response.status_code,
            request_body=body,
            response_body=_response_payload(response),
            elapsed_ms=elapsed_ms,
        )

    def profiles(self) -> HttpExchange:
        return self._request("GET", "/v1/catalyst/query-options")

    def bind_data_source(self, data_source_id: str) -> None:
        self.data_source_id = data_source_id

    def pin_guidance(self, session_id: str, text: str) -> HttpExchange:
        return self._request(
            "POST",
            f"/v1/catalyst/workbench/sessions/{session_id}/guidance",
            {
                "contractVersion": "catalyst.workbench.guidance.request.v1",
                "text": text,
            },
        )

    def _scoped(self, path: str) -> str:
        """Ask the suite's source, not whichever one the gateway defaults to."""
        if self.data_source_id is None:
            return path
        return f"{path}?dataSourceId={quote(self.data_source_id)}"

    def dataset_overview(self) -> HttpExchange:
        return self._request("GET", self._scoped("/v1/catalyst/dataset"))

    def catalog(self) -> HttpExchange:
        return self._request(
            "GET", self._scoped("/v1/catalyst/workbench/catalog")
        )

    def create_session(self, question: str, profile_id: str) -> HttpExchange:
        return self._request(
            "POST",
            "/v1/catalyst/workbench/sessions",
            {
                "contractVersion": "catalyst.workbench.session.request.v1",
                "deploymentMode": "demo",
                "question": question,
                "profileId": profile_id,
                **(
                    {"dataSourceId": self.data_source_id}
                    if self.data_source_id is not None
                    else {}
                ),
            },
        )

    def get_session(self, session_id: str) -> HttpExchange:
        return self._request("GET", f"/v1/catalyst/workbench/sessions/{session_id}")

    def get_turns(self, session_id: str) -> HttpExchange:
        return self._request(
            "GET", f"/v1/catalyst/workbench/sessions/{session_id}/turns"
        )

    def generation_evidence(self, session_id: str, turn_id: str) -> HttpExchange:
        return self._request(
            "GET",
            f"/v1/catalyst/workbench/sessions/{session_id}/turns/"
            f"{turn_id}/generation-evidence",
        )

    def save_version(
        self,
        session_id: str,
        query: NotebookQuery,
        parent: dict[str, Any] | None,
    ) -> HttpExchange:
        body: dict[str, Any] = {
            "contractVersion": "catalyst.workbench.version.request.v1",
            **query.content(),
        }
        if parent is not None:
            body.update(
                {
                    "parentVersionId": parent["versionId"],
                    "parentQueryDigest": parent["queryDigest"],
                }
            )
        return self._request(
            "POST",
            f"/v1/catalyst/workbench/sessions/{session_id}/versions",
            body,
        )

    def validate_version(self, version_id: str) -> HttpExchange:
        return self._request(
            "POST", f"/v1/catalyst/workbench/versions/{version_id}/validate"
        )

    def execute_version(self, version: dict[str, Any]) -> HttpExchange:
        version_id = str(version["versionId"])
        return self._request(
            "POST",
            f"/v1/catalyst/workbench/versions/{version_id}/execute",
            {
                "contractVersion": "catalyst.workbench.execute.request.v1",
                "versionId": version_id,
                "queryDigest": version["queryDigest"],
                "idempotencyKey": f"harness-notebook-{uuid4()}",
            },
        )

    def create_turn(
        self,
        session_id: str,
        *,
        instruction: str,
        profile_id: str,
        observed_base: dict[str, str] | None,
        editor_snapshot: dict[str, Any] | None,
    ) -> HttpExchange:
        return self._request(
            "POST",
            f"/v1/catalyst/workbench/sessions/{session_id}/turns",
            {
                "contractVersion": "catalyst.workbench.turn.request.v1",
                "instruction": instruction,
                "profileId": profile_id,
                **(
                    {"dataSourceId": self.data_source_id}
                    if self.data_source_id is not None
                    else {}
                ),
                "observedBase": observed_base,
                "editorSnapshot": editor_snapshot,
            },
        )


class PostgresReadOnlyChecker:
    """Execute the selected immutable version through a separate DB connection."""

    def __init__(
        self,
        dsn: str,
        *,
        statement_timeout_ms: int = 30_000,
        max_rows: int = 100,
    ) -> None:
        self.dsn = dsn
        self.statement_timeout_ms = statement_timeout_ms
        self.max_rows = max_rows

    def check(
        self,
        version: dict[str, Any],
        execution: object,
    ) -> dict[str, Any]:
        import psycopg

        parameters = list(version.get("parameters") or [])
        bindings = {
            str(parameter["name"]): _binding_value(parameter)
            for parameter in parameters
        }
        driver_sql = _driver_sql(str(version["sql"]), set(bindings))
        gateway_execution = execution if isinstance(execution, dict) else {}
        result = gateway_execution.get("result")
        gateway_columns = [
            item.get("name") for item in (result or {}).get("columns", [])
        ]
        gateway_rows = [
            [_gateway_cell_value(cell) for cell in row]
            for row in (result or {}).get("rows", [])
        ]
        row_count = (result or {}).get("rowCount", {})
        parsed = urlparse(self.dsn)
        with psycopg.connect(self.dsn, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (f"{self.statement_timeout_ms}ms",),
                )
                try:
                    cursor.execute(driver_sql, bindings)
                except psycopg.errors.QueryCanceled:
                    return {
                        "contractVersion": (
                            "harness.catalyst-notebook.postgres-crosscheck.v1"
                        ),
                        "readOnlyTransaction": True,
                        "database": parsed.path.lstrip("/") or None,
                        "versionId": version.get("versionId"),
                        "queryDigest": version.get("queryDigest"),
                        "gatewayExecutionId": gateway_execution.get("executionId"),
                        "maxRows": self.max_rows,
                        "statementTimeoutMs": self.statement_timeout_ms,
                        "timedOut": True,
                        "comparisons": {"queryCompleted": False},
                        "passed": False,
                        "disagreement": (
                            "the model's query exceeded the "
                            f"{self.statement_timeout_ms}ms statement timeout "
                            "when re-executed independently"
                        ),
                        "gateway": {
                            "columns": gateway_columns,
                            "returned": row_count.get("returned"),
                            "truncated": row_count.get("truncated"),
                            "recordDigests": _row_digests(gateway_rows),
                        },
                        "postgres": {"queryCompleted": False},
                    }
                direct_rows = list(cursor.fetchmany(self.max_rows + 1))
                direct_columns = [item.name for item in (cursor.description or ())]

        direct_truncated = len(direct_rows) > self.max_rows
        direct_rows = direct_rows[: self.max_rows]
        normalized_direct = [
            [_json_safe_value(value) for value in row] for row in direct_rows
        ]
        comparisons = {
            "columns": gateway_columns == direct_columns,
            "returnedRows": row_count.get("returned") == len(direct_rows),
            "truncated": row_count.get("truncated") is direct_truncated,
            "recordDigests": _row_digests(gateway_rows)
            == _row_digests(normalized_direct),
        }
        return {
            "contractVersion": "harness.catalyst-notebook.postgres-crosscheck.v1",
            "readOnlyTransaction": True,
            "database": parsed.path.lstrip("/") or None,
            "versionId": version.get("versionId"),
            "queryDigest": version.get("queryDigest"),
            "gatewayExecutionId": gateway_execution.get("executionId"),
            "maxRows": self.max_rows,
            "comparisons": comparisons,
            "passed": all(comparisons.values()),
            "gateway": {
                "columns": gateway_columns,
                "returned": row_count.get("returned"),
                "truncated": row_count.get("truncated"),
                "recordDigests": _row_digests(gateway_rows),
            },
            "postgres": {
                "columns": direct_columns,
                "returned": len(direct_rows),
                "truncated": direct_truncated,
                "recordDigests": _row_digests(normalized_direct),
            },
        }


def _escape_percents_outside_placeholders(sql: str) -> str:
    """Double every % that is not opening a %(name)s placeholder."""
    output: list[str] = []
    index = 0
    while index < len(sql):
        char = sql[index]
        if char == "%":
            if sql.startswith("%(", index):
                end = sql.find(")s", index)
                if end != -1:
                    output.append(sql[index : end + 2])
                    index = end + 2
                    continue
            output.append("%%")
            index += 1
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _fetch_all_rows(
    cursor: Any,
    sql: str,
    parameters: list[dict[str, Any]],
    *,
    max_rows: int,
) -> tuple[list[dict[str, Any]], bool]:
    bindings = {
        str(parameter["name"]): _binding_value(parameter) for parameter in parameters
    }
    driver_sql = _driver_sql(sql, set(bindings))
    cursor.execute(driver_sql, bindings)
    rows = list(cursor.fetchmany(max_rows + 1))
    exceeded = len(rows) > max_rows
    columns = [item.name for item in (cursor.description or ())]
    return (
        [
            {column: _json_safe_value(value) for column, value in zip(columns, row)}
            for row in rows[:max_rows]
        ],
        exceeded,
    )


class PostgresGoldExecutionChecker:
    """Prove a model's own SQL — executed directly and unbounded, bypassing the
    Gateway's UI row cap — matches a hand-authored reference query's intent,
    rather than merely matching its own (possibly truncated) visible page."""

    def __init__(
        self, dsn: str, *, statement_timeout_ms: int = 30_000, max_rows: int = 5_000
    ) -> None:
        self.dsn = dsn
        self.statement_timeout_ms = statement_timeout_ms
        self.max_rows = max_rows

    @staticmethod
    def _subquery(sql: str) -> str:
        return sql.strip().removesuffix(";").rstrip()

    @staticmethod
    def _identifier(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    def _database_row_set_check(
        self,
        cursor: Any,
        version: dict[str, Any],
        gold_check: "NotebookGoldCheck",
    ) -> dict[str, Any]:
        """Compare large plain row sets inside PostgreSQL.

        Only the counts and small disagreement samples cross the process
        boundary. This checks a complete large result without inventing a row
        cutoff for the evidence tool.
        """

        import psycopg

        model_parameters = list(version.get("parameters") or [])
        bindings = {
            str(parameter["name"]): _binding_value(parameter)
            for parameter in model_parameters
        }
        model_sql = self._subquery(
            _driver_sql(str(version["sql"]), set(bindings))
        )
        reference_sql = self._subquery(
            _driver_sql(gold_check.reference_sql, set())
        )
        result: dict[str, Any] = {
            "contractVersion": "harness.catalyst-notebook.gold-execution-match.v1",
            "mode": gold_check.mode,
            "versionId": version.get("versionId"),
            "queryDigest": version.get("queryDigest"),
            "matchColumns": list(gold_check.match_columns),
            "normalizers": {},
            "comparisonLocation": "postgresql",
        }

        try:
            cursor.execute(
                f"SELECT * FROM ({model_sql}) AS model_rows LIMIT 0",
                bindings,
            )
        except psycopg.errors.QueryCanceled:
            result.update(
                {
                    "passed": False,
                    "disagreement": (
                        "the model's query exceeded the "
                        f"{self.statement_timeout_ms}ms statement timeout "
                        "when re-executed independently"
                    ),
                }
            )
            return result
        except psycopg.Error as error:
            result.update(
                {
                    "passed": False,
                    "disagreement": (
                        "the model query could not be compared as a row set"
                    ),
                    "databaseDiagnostic": {"sqlstate": error.sqlstate},
                }
            )
            return result
        model_columns = [item.name for item in (cursor.description or ())]
        missing_model_columns = [
            column
            for column in gold_check.match_columns
            if column not in model_columns
        ]
        if missing_model_columns:
            result.update(
                {
                    "passed": False,
                    "disagreement": (
                        "the model result has no column named "
                        + ", ".join(repr(column) for column in missing_model_columns)
                        + f"; its columns are {sorted(model_columns)}"
                    ),
                }
            )
            return result

        try:
            cursor.execute(
                f"SELECT * FROM ({reference_sql}) AS reference_rows LIMIT 0",
                {},
            )
        except psycopg.Error as error:
            raise ValueError(
                "the independent reference query could not be compared"
            ) from error
        reference_columns = [item.name for item in (cursor.description or ())]
        missing_reference_columns = [
            column
            for column in gold_check.match_columns
            if column not in reference_columns
        ]
        if missing_reference_columns:
            raise ValueError(
                "the independent reference query is missing columns: "
                + ", ".join(missing_reference_columns)
            )

        projected = ", ".join(
            self._identifier(column) for column in gold_check.match_columns
        )
        common = (
            f"WITH model_rows AS ({model_sql}), "
            f"reference_rows AS ({reference_sql}), "
            f"model_values AS (SELECT {projected} FROM model_rows), "
            f"reference_values AS (SELECT {projected} FROM reference_rows) "
        )
        try:
            cursor.execute(
                common
                + "SELECT "
                + "(SELECT count(*) FROM model_values), "
                + "(SELECT count(*) FROM reference_values), "
                + "(SELECT count(*) FROM ("
                + "SELECT * FROM reference_values EXCEPT ALL "
                + "SELECT * FROM model_values) AS missing), "
                + "(SELECT count(*) FROM ("
                + "SELECT * FROM model_values EXCEPT ALL "
                + "SELECT * FROM reference_values) AS extra)",
                bindings,
            )
            summary_rows = list(cursor.fetchmany(1))
        except psycopg.Error as error:
            result.update(
                {
                    "passed": False,
                    "disagreement": (
                        "the requested model columns could not be compared with "
                        "the independent answer"
                    ),
                    "databaseDiagnostic": {"sqlstate": error.sqlstate},
                }
            )
            return result
        if len(summary_rows) != 1:
            raise ValueError("database row-set comparison returned no summary")
        model_count, reference_count, missing_count, extra_count = summary_rows[0]

        def sample(first: str, second: str) -> list[list[Any]]:
            cursor.execute(
                common
                + "SELECT * FROM ("
                + f"SELECT * FROM {first} EXCEPT ALL SELECT * FROM {second}"
                + ") AS difference LIMIT 20",
                bindings,
            )
            return [
                [_json_safe_value(value) for value in row]
                for row in cursor.fetchmany(20)
            ]

        missing_sample = (
            sample("reference_values", "model_values") if missing_count else []
        )
        extra_sample = (
            sample("model_values", "reference_values") if extra_count else []
        )
        passed = not missing_count and not extra_count
        result.update(
            {
                "modelRowCount": int(model_count),
                "referenceRowCount": int(reference_count),
                "missingFromModelCount": int(missing_count),
                "extraInModelCount": int(extra_count),
                "missingFromModelSample": missing_sample,
                "extraInModelSample": extra_sample,
                "passed": passed,
            }
        )
        if not passed:
            result["disagreement"] = (
                f"{missing_count} row{'s' if missing_count != 1 else ''} missing "
                f"from the answer and {extra_count} extra, compared on "
                f"{', '.join(gold_check.match_columns)}"
            )
        return result

    def check(
        self,
        version: dict[str, Any],
        gold_check: "NotebookGoldCheck",
    ) -> dict[str, Any]:
        import psycopg

        with psycopg.connect(self.dsn, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (f"{self.statement_timeout_ms}ms",),
                )
                if (
                    gold_check.mode == "row_set"
                    and not gold_check.normalizers
                    and not gold_check.reference_parameters
                ):
                    return self._database_row_set_check(
                        cursor, version, gold_check
                    )
                try:
                    model_rows, model_exceeded = _fetch_all_rows(
                        cursor,
                        str(version["sql"]),
                        list(version.get("parameters") or []),
                        max_rows=self.max_rows,
                    )
                except psycopg.errors.QueryCanceled:
                    # Too slow to answer within the product's own statement
                    # timeout is a wrong answer, not a broken harness.
                    return {
                        "contractVersion": (
                            "harness.catalyst-notebook.gold-execution-match.v1"
                        ),
                        "mode": gold_check.mode,
                        "versionId": version.get("versionId"),
                        "queryDigest": version.get("queryDigest"),
                        "passed": False,
                        "disagreement": (
                            "the model's query exceeded the "
                            f"{self.statement_timeout_ms}ms statement timeout "
                            "when re-executed independently"
                        ),
                    }
                reference_rows, reference_exceeded = _fetch_all_rows(
                    cursor,
                    gold_check.reference_sql,
                    list(gold_check.reference_parameters),
                    max_rows=self.max_rows,
                )
        # The reference is ours: oversized means the scenario is misauthored,
        # and scoring against a truncated reference would be a quiet lie.
        if reference_exceeded:
            raise ValueError(
                f"the reference query exceeded the {self.max_rows}-row safety "
                "cap; narrow the scenario or raise max_rows"
            )

        result: dict[str, Any] = {
            "contractVersion": "harness.catalyst-notebook.gold-execution-match.v1",
            "mode": gold_check.mode,
            "versionId": version.get("versionId"),
            "queryDigest": version.get("queryDigest"),
            "modelRowCount": len(model_rows),
            "referenceRowCount": len(reference_rows),
        }
        if model_exceeded:
            # An unfiltered model answer is a wrong answer, not a broken
            # harness: score the mismatch instead of erasing finished work.
            result["modelRowsExceededCap"] = True
            result["passed"] = False
            result["disagreement"] = (
                f"the answer returned over {len(model_rows)} rows; the "
                f"independent reference returns {len(reference_rows)}"
            )
            return result
        if gold_check.mode == "count":
            result["passed"] = len(model_rows) == len(reference_rows)
            if not result["passed"]:
                result["disagreement"] = (
                    f"the answer returned {len(model_rows)} rows; the "
                    f"independent reference returns {len(reference_rows)}"
                )
        elif gold_check.mode == "row_set":
            result.update(
                _compare_row_sets(
                    model_rows,
                    reference_rows,
                    gold_check.match_columns,
                    gold_check.normalizers,
                )
            )
        elif gold_check.mode == "aggregate_by_key":
            result.update(
                _compare_aggregates(
                    model_rows,
                    reference_rows,
                    gold_check.key_columns,
                    gold_check.value_columns,
                )
            )
        elif gold_check.mode == "scalar":
            result.update(
                _compare_scalars(model_rows, reference_rows, gold_check.value_column)
            )
        else:
            raise ValueError(f"unsupported gold check mode {gold_check.mode!r}")
        return result


def _compare_row_sets(
    model_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    match_columns: tuple[str, ...],
    normalizers: dict[str, str] | None = None,
) -> dict[str, Any]:
    # A match column the model never projected can only produce a wall of
    # None-vs-value diffs; the honest evidence is one sentence naming it.
    if model_rows:
        model_columns = sorted(model_rows[0])
        absent = [c for c in match_columns if c not in model_rows[0]]
        if absent:
            return {
                "matchColumns": list(match_columns),
                "passed": False,
                "disagreement": (
                    f"the model result has no column named "
                    f"{', '.join(repr(c) for c in absent)}; its columns are "
                    f"{model_columns}"
                ),
            }

    normalizers = normalizers or {}

    def _normalized_value(column: str, value: Any) -> Any:
        if normalizers.get(column) != "unordered_csv" or not isinstance(value, str):
            return value
        # Ordering and surrounding spaces are presentation details. Keeping
        # duplicates means a repeated or missing item still disagrees.
        return tuple(sorted(part.strip() for part in value.split(",") if part.strip()))

    def _key(row: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(
            _normalized_value(column, row.get(column)) for column in match_columns
        )

    model_counter = Counter(_key(row) for row in model_rows)
    reference_counter = Counter(_key(row) for row in reference_rows)
    missing = list((reference_counter - model_counter).elements())
    extra = list((model_counter - reference_counter).elements())
    passed = not missing and not extra
    verdict = {
        "matchColumns": list(match_columns),
        "normalizers": normalizers,
        "missingFromModelCount": len(missing),
        "extraInModelCount": len(extra),
        "missingFromModelSample": [list(item) for item in missing[:20]],
        "extraInModelSample": [list(item) for item in extra[:20]],
        "passed": passed,
    }
    if not passed:
        verdict["disagreement"] = (
            f"{len(missing)} row{'s' if len(missing) != 1 else ''} missing "
            f"from the answer and {len(extra)} extra, compared on "
            f"{', '.join(match_columns)}"
        )
    return verdict


def _values_match(model_value: Any, reference_value: Any, tolerance: float) -> bool:
    if model_value is None or reference_value is None:
        return model_value == reference_value
    try:
        return abs(float(model_value) - float(reference_value)) <= tolerance
    except (TypeError, ValueError):
        return model_value == reference_value


def _compare_aggregates(
    model_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    key_columns: tuple[str, ...],
    value_columns: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    def _key(row: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(row.get(column) for column in key_columns)

    model_keys = [_key(row) for row in model_rows]
    reference_keys = [_key(row) for row in reference_rows]

    def _duplicates(keys: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        return [
            {"key": list(key), "rowCount": count}
            for key, count in sorted(
                Counter(keys).items(), key=lambda item: str(item[0])
            )
            if count > 1
        ]

    duplicate_model_keys = _duplicates(model_keys)
    duplicate_reference_keys = _duplicates(reference_keys)
    if duplicate_model_keys or duplicate_reference_keys:
        parts: list[str] = []
        if duplicate_model_keys:
            first = duplicate_model_keys[0]
            parts.append(
                "the answer has duplicate aggregate keys "
                f"(first: {first['key']} appears {first['rowCount']} times)"
            )
        if duplicate_reference_keys:
            first = duplicate_reference_keys[0]
            parts.append(
                "the independent reference has duplicate aggregate keys "
                f"(first: {first['key']} appears {first['rowCount']} times)"
            )
        return {
            "keyColumns": list(key_columns),
            "valueColumns": value_columns,
            "duplicateModelKeys": duplicate_model_keys,
            "duplicateReferenceKeys": duplicate_reference_keys,
            "passed": False,
            "disagreement": "; ".join(parts),
        }

    # The criterion is "this aggregate by this key", not our spelling of the
    # aggregate: keys come from catalog values and match naturally, but the
    # value column is named by the model. When our name is absent and the row
    # has exactly one non-key column left, that column is the value. Two or
    # more is a real ambiguity, reported as a sentence rather than guessed.
    resolution: dict[str, str] = {}
    if model_rows:
        model_columns = list(model_rows[0])
        spare = [c for c in model_columns if c not in key_columns]
        for wanted in value_columns:
            if wanted in model_columns:
                continue
            others = [c for c in spare if c not in value_columns]
            if len(others) == 1:
                resolution[wanted] = others[0]
            else:
                return {
                    "keyColumns": list(key_columns),
                    "valueColumns": value_columns,
                    "passed": False,
                    "disagreement": (
                        f"the model result has no column named {wanted!r} and "
                        f"{'no' if not others else 'several'} unambiguous "
                        f"stand-in{'s' if len(others) != 1 else ''} "
                        f"({others}); its columns are {sorted(model_columns)}"
                    ),
                }

    # Duplicate keys were rejected above, so converting to keyed rows cannot
    # silently discard a disagreeing aggregate row.
    model_by_key = dict(zip(model_keys, model_rows))
    reference_by_key = dict(zip(reference_keys, reference_rows))
    missing_keys = sorted(set(reference_by_key) - set(model_by_key), key=str)
    extra_keys = sorted(set(model_by_key) - set(reference_by_key), key=str)
    mismatches: list[dict[str, Any]] = []
    for key in sorted(set(model_by_key) & set(reference_by_key), key=str):
        model_row, reference_row = model_by_key[key], reference_by_key[key]
        for column, spec in value_columns.items():
            model_value, reference_value = (
                model_row.get(resolution.get(column, column)),
                reference_row.get(column),
            )
            tolerance = float(spec.get("tolerance", 0))
            if not _values_match(model_value, reference_value, tolerance):
                mismatches.append(
                    {
                        "key": list(key),
                        "column": column,
                        "modelValue": model_value,
                        "referenceValue": reference_value,
                        "tolerance": tolerance,
                    }
                )
    passed = not missing_keys and not extra_keys and not mismatches
    verdict = {
        "keyColumns": list(key_columns),
        "valueColumns": value_columns,
        "missingKeys": [list(key) for key in missing_keys],
        "extraKeys": [list(key) for key in extra_keys],
        "valueMismatches": mismatches,
        "valueColumnResolution": resolution,
        "passed": passed,
    }
    if not passed:
        parts: list[str] = []
        if extra_keys:
            parts.append(
                f"the answer has {len(extra_keys)} group"
                f"{'s' if len(extra_keys) != 1 else ''} the reference does "
                "not have"
            )
        if missing_keys:
            parts.append(
                f"{len(missing_keys)} reference group"
                f"{'s' if len(missing_keys) != 1 else ''} missing"
            )
        if mismatches:
            # One entry per (group, value column); the sentence counts
            # groups, or two bad columns in one group would read as two
            # disagreeing groups.
            groups = len({tuple(item["key"]) for item in mismatches})
            first = mismatches[0]
            key_label = ", ".join(str(part) for part in first["key"])
            parts.append(
                f"counts disagree on {groups} group"
                f"{'s' if groups != 1 else ''} (first: "
                f"'{key_label}': {first['modelValue']} vs "
                f"{first['referenceValue']})"
            )
        verdict["disagreement"] = "; ".join(parts)
    return verdict


def _compare_scalars(
    model_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    value_column: str | None,
) -> dict[str, Any]:
    model_value = model_rows[0].get(value_column) if model_rows else None
    reference_value = reference_rows[0].get(value_column) if reference_rows else None
    verdict: dict[str, Any] = {
        "valueColumn": value_column,
        "modelValue": model_value,
        "referenceValue": reference_value,
        "passed": bool(model_rows)
        and bool(reference_rows)
        and model_value == reference_value,
    }
    if not verdict["passed"]:
        verdict["disagreement"] = (
            f"the answer's {value_column} is {model_value}; the independent "
            f"reference says {reference_value}"
        )
    return verdict


class _EvidenceRecorder:
    def __init__(self, run_dir: Path, run_id: str) -> None:
        self.run_dir = run_dir
        self.run_id = run_id
        self.entries: list[dict[str, Any]] = []

    def json(
        self,
        relative_path: str,
        payload: Any,
        *,
        kind: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        path = self.run_dir / relative_path
        if not path.resolve().is_relative_to(self.run_dir.resolve()):
            raise ValueError("Evidence path must stay within the run directory")
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        path.write_bytes(encoded)
        entry = {
            "path": relative_path,
            "kind": kind,
            "mediaType": "application/json",
            "bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
        if metadata:
            entry["metadata"] = metadata
        self.entries.append(entry)
        self._write_index()
        return path

    def exchange(
        self,
        relative_path: str,
        exchange: HttpExchange,
        *,
        kind: str,
    ) -> dict[str, Any]:
        self.json(relative_path, exchange.as_dict(), kind=kind)
        if exchange.status_code >= 500:
            raise _CollectionInterrupted(relative_path, exchange)
        return exchange.response_body

    def adopt(
        self,
        relative_path: str,
        source: Path,
        *,
        kind: str,
        metadata: dict[str, Any],
        expected_sha256: str,
    ) -> dict[str, Any]:
        """Copy one immutable evidence file and prove the bytes survived."""
        destination = self.run_dir / relative_path
        if not destination.resolve().is_relative_to(self.run_dir.resolve()):
            raise ValueError("Evidence path must stay within the run directory")
        if destination.exists():
            raise ValueError(f"recovery would overwrite {relative_path}")
        encoded = source.read_bytes()
        source_sha256 = hashlib.sha256(encoded).hexdigest()
        if source_sha256 != expected_sha256:
            raise ValueError(f"recovery evidence changed after preflight: {relative_path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encoded)
        destination_sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()
        if destination_sha256 != source_sha256:
            raise ValueError(f"recovery changed evidence bytes for {relative_path}")
        entry = {
            "path": relative_path,
            "kind": kind,
            "mediaType": "application/json",
            "bytes": len(encoded),
            "sha256": destination_sha256,
            "metadata": {**metadata, "sourceSha256": source_sha256},
        }
        self.entries.append(entry)
        self._write_index()
        return entry

    def file(
        self,
        relative_path: str,
        *,
        kind: str,
        media_type: str,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Bind an existing append-only run file into the evidence index."""
        path = self.run_dir / relative_path
        if not path.resolve().is_relative_to(self.run_dir.resolve()):
            raise ValueError("Evidence path must stay within the run directory")
        if not path.is_file():
            raise ValueError(f"Evidence file is missing: {relative_path}")
        prior = next(
            (item for item in self.entries if item.get("path") == relative_path),
            None,
        )
        if prior is not None and not replace:
            raise ValueError(f"Evidence path is already indexed: {relative_path}")
        encoded = path.read_bytes()
        entry = {
            "path": relative_path,
            "kind": kind,
            "mediaType": media_type,
            "bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
        if prior is not None:
            self.entries.remove(prior)
        self.entries.append(entry)
        self._write_index()
        return entry

    def _write_index(self) -> None:
        index = {
            "contractVersion": "harness.catalyst-notebook.evidence-index.v1",
            "runId": self.run_id,
            "hashAlgorithm": "sha256",
            "entries": sorted(self.entries, key=lambda item: item["path"]),
        }
        encoded = (
            json.dumps(index, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        index_path = self.run_dir / "evidence-index.json"
        index_temporary = self.run_dir / ".evidence-index.json.tmp"
        checksum_path = self.run_dir / "evidence-index.sha256"
        checksum_temporary = self.run_dir / ".evidence-index.sha256.tmp"
        index_temporary.write_bytes(encoded)
        checksum_temporary.write_text(
            f"{hashlib.sha256(encoded).hexdigest()}  evidence-index.json\n",
            encoding="utf-8",
        )
        index_temporary.replace(index_path)
        checksum_temporary.replace(checksum_path)

    def finish(self) -> None:
        self._write_index()


def _write_run_status(run_dir: Path, payload: dict[str, Any]) -> None:
    """Write the current lifecycle projection without changing older runs."""
    path = run_dir / "run-status.json"
    temporary = run_dir / ".run-status.json.tmp"
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _index_run_streams(recorder: _EvidenceRecorder) -> None:
    """Sign the append-only streams at their last complete record."""
    for relative_path, kind in (
        ("rows.jsonl", "measurement_rows"),
        ("interruptions.jsonl", "collection_interruptions"),
        ("results.jsonl", "result_stream"),
        ("events.jsonl", "event_stream"),
    ):
        if (recorder.run_dir / relative_path).is_file():
            recorder.file(
                relative_path,
                kind=kind,
                media_type="application/x-ndjson",
                replace=True,
            )


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(rfc8785.dumps(payload)).hexdigest()


def _exchange_body(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        body = payload["response"]["body"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"cannot read recovery identity from {path}") from error
    if not isinstance(body, dict):
        raise ValueError(f"recovery identity in {path} is not an object")
    return body


def _load_pin_guidance(
    scenario_id: str, item: dict[str, Any]
) -> tuple[str, ...]:
    """A list of instructions, never a bare string pinned per character."""
    declared = item.get("pinGuidance")
    if declared is None:
        return ()
    if isinstance(declared, str) or not isinstance(declared, (list, tuple)):
        raise ValueError(
            f"scenario {scenario_id!r}: pinGuidance must be a list of "
            "instructions"
        )
    return tuple(str(text) for text in declared)


def _load_turns(
    scenario_id: str, item: dict[str, Any], base_outcome: str
) -> tuple[NotebookTurn, ...]:
    """Read a scenario's follow-ups from whichever form declares them."""

    declared = item.get("turns")
    legacy = "followupInstruction" in item or "followupProfileId" in item
    if declared is not None and legacy:
        raise ValueError(
            f"scenario {scenario_id!r} declares both 'turns' and "
            "'followupInstruction'; use one form"
        )
    if declared is None:
        declared = [
            {
                "instruction": item["followupInstruction"],
                "profileId": item["followupProfileId"],
                "expectedTurnStatus": item.get("expectedTurnStatus", "completed"),
            }
        ]
    if not declared and base_outcome not in TERMINAL_WRITER_OUTCOMES:
        # A scenario scored on its opening question alone is fine when the
        # answer is a question or a refusal -- there is nothing to follow.
        # A query, though, has to be checked here or nothing is measured
        # beyond the session opening, which reads as a pass.
        if not (
            bool(item.get("validateBase", True))
            and bool(item.get("executeBase", True))
        ):
            raise ValueError(
                f"scenario {scenario_id!r} must declare at least one turn, "
                "or validate and execute the query its opening question asked for"
            )
    turns: list[NotebookTurn] = []
    for position, entry in enumerate(declared, start=1):
        status = str(entry.get("expectedTurnStatus", "completed"))
        if status not in {"completed", "failed"}:
            raise ValueError(
                f"scenario {scenario_id!r} turn {position} has invalid turn status"
            )
        outcome = str(entry.get("expectedOutcome", "ready"))
        if outcome not in WRITER_OUTCOMES:
            raise ValueError(
                f"scenario {scenario_id!r} turn {position} has invalid expected "
                f"outcome {outcome!r}"
            )
        turns.append(
            NotebookTurn(
                instruction=str(entry["instruction"]),
                profile_id=str(entry["profileId"]),
                expected_turn_status=status,
                expected_outcome=outcome,
                gold_check=_load_gold_check(entry.get("goldCheck")),
            )
        )
    return tuple(turns)


def load_notebook_suite(path: Path | str) -> NotebookSuite:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    suite_id = str(payload["id"])
    phase1_comparison = suite_id.startswith(_PHASE1_COMPARISON_SUITE_PREFIX)
    repetitions = int(payload["repetitions"])
    if repetitions < 1:
        raise ValueError("Notebook suite repetitions must be at least one")
    extended_value = payload.get("extendedRepetitions")
    extended = int(extended_value) if extended_value is not None else None
    if extended is not None and extended < repetitions:
        raise ValueError(
            "Notebook suite extendedRepetitions must not be below repetitions"
        )
    if phase1_comparison and (repetitions != 1 or extended is not None):
        raise ValueError(
            "Phase 1 repeated measures are separate full-suite runs; "
            "the suite must use one conversation per team/scenario cell"
        )
    scenarios: list[NotebookScenario] = []
    seen: set[str] = set()
    for item in payload["scenarios"]:
        scenario_id = str(item["id"])
        if scenario_id in seen:
            raise ValueError(f"duplicate notebook scenario id {scenario_id!r}")
        seen.add(scenario_id)
        editor_payload = item.get("editorQuery")
        editor_query = None
        if editor_payload is not None:
            editor_query = NotebookQuery(
                sql=str(editor_payload["sql"]),
                parameters=tuple(dict(value) for value in editor_payload["parameters"]),
                expected_columns=tuple(
                    dict(value) for value in editor_payload.get("expectedColumns", [])
                ),
            )
        scenario_repetitions = item.get("repetitions")
        if scenario_repetitions is not None and int(scenario_repetitions) < 1:
            raise ValueError(f"scenario {scenario_id!r} repetitions must be positive")
        if (
            phase1_comparison
            and scenario_repetitions is not None
            and int(scenario_repetitions) != 1
        ):
            raise ValueError(
                "Phase 1 repeated measures are separate full-suite runs; "
                f"scenario {scenario_id!r} cannot repeat within a run"
            )
        classification = str(item["expectedBaseClassification"])
        if classification not in {
            "not_applicable",
            "reused",
            "promoted_human",
            "unresolved",
        }:
            raise ValueError(f"scenario {scenario_id!r} has invalid classification")
        base_outcome = str(item.get("expectedBaseOutcome", "ready"))
        if base_outcome not in WRITER_OUTCOMES:
            raise ValueError(
                f"scenario {scenario_id!r} has invalid expected base "
                f"outcome {base_outcome!r}"
            )
        turns = _load_turns(scenario_id, item, base_outcome)
        scenarios.append(
            NotebookScenario(
                id=scenario_id,
                family=str(item["family"]),
                initial_question=str(item["initialQuestion"]),
                initial_profile_id=str(item["initialProfileId"]),
                turns=turns,
                editor_query=editor_query,
                persist_editor_query=bool(item.get("persistEditorQuery", False)),
                expected_base_classification=classification,
                validate_base=bool(item.get("validateBase", True)),
                execute_base=bool(item.get("executeBase", True)),
                validate_successor=bool(item.get("validateSuccessor", True)),
                execute_successor=bool(item.get("executeSuccessor", True)),
                repetitions=(
                    int(scenario_repetitions)
                    if scenario_repetitions is not None
                    else None
                ),
                manual_only=bool(item.get("manualOnly", False)),
                require_reviewer_correction=bool(
                    item.get("requireReviewerCorrection", False)
                ),
                base_gold_check=_load_gold_check(item.get("baseGoldCheck")),
                successor_gold_check=_load_gold_check(item.get("successorGoldCheck")),
                expected_base_outcome=base_outcome,
                pin_guidance=_load_pin_guidance(scenario_id, item),
            )
        )
    if not scenarios:
        raise ValueError("Notebook suite must contain scenarios")
    if payload.get("reportMode") == "reader-led":
        for scenario in scenarios:
            if scenario.pin_guidance:
                raise ValueError(
                    f"reader-led scenario {scenario.id!r} must express all "
                    "instructions in its conversation, not pinGuidance"
                )
            if (
                scenario.expected_base_outcome == "ready"
                and scenario.base_gold_check is None
            ):
                raise ValueError(
                    f"reader-led scenario {scenario.id!r} needs an independent "
                    "answer check for its opening turn"
                )
            for position, turn in enumerate(scenario.turns, start=1):
                if turn.expected_outcome == "ready" and turn.gold_check is None:
                    raise ValueError(
                        f"reader-led scenario {scenario.id!r} turn {position} "
                        "needs its own independent answer check"
                    )
    profiles = {}
    for profile_id, detail in payload["profiles"].items():
        reviewer_model_id = detail.get("reviewerModelId")
        frozen_digest = detail.get("profileConfigurationDigest")
        entry: dict[str, str | None] = {
            "writerModelId": str(detail["writerModelId"]),
            "reviewerModelId": (
                str(reviewer_model_id) if reviewer_model_id is not None else None
            ),
        }
        # Only suites that froze a digest carry the key, so a profile map keeps
        # exactly the shape every existing reader and suite already expects.
        if frozen_digest is not None:
            entry["profileConfigurationDigest"] = str(frozen_digest)
        profiles[str(profile_id)] = entry
    comparison_profiles = tuple(
        str(value) for value in payload.get("comparisonProfiles") or ()
    )
    for profile_id in comparison_profiles:
        if profile_id not in profiles:
            raise ValueError(
                f"suite compares unknown profile {profile_id!r}"
            )
    for scenario in scenarios:
        for profile_id in (
            scenario.initial_profile_id,
            *(turn.profile_id for turn in scenario.turns),
        ):
            if profile_id not in profiles:
                raise ValueError(
                    f"scenario {scenario.id!r} references unknown profile "
                    f"{profile_id!r}"
                )
    return NotebookSuite(
        id=suite_id,
        dataset_id=str(payload["datasetId"]),
        dataset_version=str(payload["datasetVersion"]),
        catalog_version=str(payload["catalogVersion"]),
        provider_name=str(payload["providerName"]),
        repetitions=repetitions,
        extended_repetitions=extended,
        require_token_evidence=bool(payload.get("requireTokenEvidence", False)),
        profiles=profiles,
        scenarios=tuple(scenarios),
        comparison_profiles=comparison_profiles,
        data_source_id=(
            str(payload["dataSourceId"])
            if payload.get("dataSourceId") is not None
            else None
        ),
    )


def query_digest(query: NotebookQuery | dict[str, Any]) -> str:
    if isinstance(query, NotebookQuery):
        content = query.content()
    else:
        content = {
            "sql": query["sql"],
            "parameters": list(query.get("parameters") or []),
            "expectedColumns": list(query.get("expectedColumns") or []),
        }
    return hashlib.sha256(rfc8785.dumps(content)).hexdigest()


# Numbered evidence-file stems that carry a real HTTP exchange (contract:
# _EvidenceRecorder.exchange writes HttpExchange.as_dict(), which nests the
# response under response.httpStatus). 07/14 (postgres) and 15/16 (gold) are
# recorder.json payloads with no httpStatus field, so they're excluded.
_HTTP_STEP_STEMS = (
    "01-create-session",
    "02-initial-turns",
    "03-initial-generation-evidence",
    "04-save-base-version",
    "05-validate-base",
    "06-execute-base",
    "08-create-followup",
    "09-refreshed-session",
    "10-final-turns",
    "11-followup-generation-evidence",
    "12-validate-successor",
    "13-execute-successor",
)


def _normalized_http_status(run_dir: Path, prefix: str) -> int:
    """200 iff every HTTP step in this repetition succeeded, else the first
    failing status code.

    Catalyst's own successes are 200/201, and a repetition can fail on
    semantic grounds (wrong turn status, wrong selection) with every
    underlying HTTP call at 2xx. Stamping raw codes either way would make
    the shared dashboard's non-`_good()` panels (which key on a plain
    ``status == 200``) misrender passing runs as all-errors. ``passed`` is
    the semantic authority; this is only for those legacy panels.
    """
    step_paths = [run_dir / prefix / f"{stem}.json" for stem in _HTTP_STEP_STEMS]
    # Guidance pins are numbered per entry; each one is a real HTTP step.
    step_paths.extend(sorted((run_dir / prefix).glob("04-pin-guidance-*.json")))
    for path in step_paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        status = (data.get("response") or {}).get("httpStatus")
        if isinstance(status, int) and not 200 <= status < 300:
            return status
    return 200


def _selected_answer_sql(run_dir: Path, prefix: str) -> str | None:
    """Re-read the successor SQL from the already-recorded session-restore
    evidence file, instead of extending ``_run_scenario``'s return value
    (which feeds ``results.json``, an indexed/hashed evidence entry)."""
    path = run_dir / prefix / "09-refreshed-session.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    body = (data.get("response") or {}).get("body") or {}
    current = body.get("currentVersion")
    return current.get("sql") if isinstance(current, dict) else None


def _result_preview(execution: dict[str, Any] | None) -> dict[str, Any] | None:
    """The first rows of what the query actually returned, for review.

    A reviewer judging a cell needs the SQL and the table it produced, not a
    filename. Values are unwrapped from their typed envelopes and clipped.
    """
    if not isinstance(execution, dict):
        return None
    result = execution.get("result")
    if not isinstance(result, dict):
        return None

    def plain(cell: Any) -> Any:
        return cell.get("value") if isinstance(cell, dict) else cell

    columns = [
        str(column.get("name"))
        for column in result.get("columns") or []
        if isinstance(column, dict)
    ]
    rows = [
        [plain(cell) for cell in row]
        for row in (result.get("rows") or [])[:10]
        if isinstance(row, list)
    ]
    row_count = result.get("rowCount") or {}
    return {
        "columns": columns,
        "rows": rows,
        "returned": row_count.get("returned"),
        "truncatedPreview": len(result.get("rows") or []) > 10,
    }


def _compact_evidence(evidence: Any) -> str:
    """One legible line per failed assertion, for the run dashboard.

    A gold check that produced a plain `disagreement` sentence surfaces it
    verbatim; anything else is compacted JSON, clipped so one wide diff
    cannot swallow the cell view.
    """
    if isinstance(evidence, dict) and isinstance(evidence.get("disagreement"), str):
        return evidence["disagreement"]
    text = json.dumps(evidence, sort_keys=True, default=str)
    return text if len(text) <= 400 else text[:397] + "..."


def _first_failed_assertion(assertions: list[dict[str, Any]]) -> str | None:
    for item in assertions:
        if not item.get("passed"):
            return f"{item['name']}: {item.get('evidence')!r}"
    return None


def token_evidence_checks(
    evidence: dict[str, Any],
) -> list[tuple[str, bool, Any]]:
    """Assertions over one turn's token accounting.

    A profile declares its window, its output reserve, and the exact
    tokenizer; the fully rendered messages are counted against them before the
    model is called. Evidence that names no tokenizer is a character-count
    substitute, which the roadmap forbids, so it does not count as recorded.
    """
    accounting = evidence.get("tokenAccounting")
    if not isinstance(accounting, dict):
        # An affirmatively empty invocation list is a deterministic answer --
        # the catalog-scope preflight asks or declines without any model call,
        # so nothing was rendered or sent and there is nothing to count. A
        # MISSING list stays strict: a turn cannot dodge the check by not
        # recording its calls.
        invocations = evidence.get("invocations")
        if isinstance(invocations, list) and not invocations:
            return [
                (
                    "token_evidence_recorded",
                    True,
                    {"recorded": False, "modelInvocations": 0},
                )
            ]
        return [("token_evidence_recorded", False, None)]

    window = accounting.get("contextWindow")
    reserve = accounting.get("outputReserve")
    prompt = accounting.get("promptTokens")
    tokenizer = accounting.get("tokenizer")
    recorded = (
        isinstance(tokenizer, str)
        and bool(tokenizer)
        and all(isinstance(value, int) for value in (window, reserve, prompt))
    )
    if not recorded:
        return [("token_evidence_recorded", False, accounting)]
    return [
        ("token_evidence_recorded", True, accounting),
        (
            "token_budget_respected",
            int(prompt) + int(reserve) <= int(window),
            {
                "promptTokens": prompt,
                "outputReserve": reserve,
                "contextWindow": window,
            },
        ),
    ]


def is_infrastructure_failure(result: dict[str, Any]) -> bool:
    """Whether an HTTP service or transport failure interrupted collection."""

    status = result.get("httpStatus")
    return result.get("status") == "infrastructure_failed" or (
        isinstance(status, int) and status >= 500
    ) or (
        result.get("failureStage") in COLLECTION_INTERRUPTION_STAGES
    )


def _profile_availability_drift(
    exchange: HttpExchange,
) -> bool:
    """Detect a profile disappearing after successful run discovery."""
    error = exchange.response_body.get("error")
    if (
        exchange.status_code == 422
        and isinstance(error, dict)
        and error.get("code") == "profile_unavailable"
    ):
        return True
    return False


def _database_service_interruption(error: Exception) -> bool:
    """Keep database availability failures separate from query judgments."""
    if isinstance(error, OSError):
        return True
    try:
        import psycopg
    except ImportError:
        return False
    if isinstance(error, psycopg.errors.QueryCanceled):
        return False
    return isinstance(error, psycopg.OperationalError)


def repetition_pair_is_unstable(runs: list[dict[str, Any]]) -> bool:
    """Legacy within-cell disagreement used by older notebook suites.

    Phase 1 comparison suites reject this collection shape. Their repeated
    measures are separate runs of the complete suite.
    """
    scored = [run for run in runs if run.get("status") != "skipped"]
    if len(scored) < 2:
        return False

    def answer_matches(run: dict[str, Any]) -> bool | None:
        for assertion in run.get("assertions") or []:
            if str(assertion.get("name", "")).endswith("gold_execution_match"):
                return bool(assertion.get("passed"))
        return None

    signatures = {
        (
            bool(run.get("passed")),
            tuple(
                str(turn.get("observedOutcome")) for turn in run.get("turns") or []
            ),
            answer_matches(run),
        )
        for run in scored
    }
    return len(signatures) > 1


def _measurement_evidence(
    *,
    run_dir: Path,
    prefix: str,
    scenario: NotebookScenario,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Record why each possible query-side action did or did not run."""

    def exists(name: str) -> bool:
        return (run_dir / prefix / name).is_file()

    def query_path(
        *,
        outcome: str,
        sql_present: bool,
        validation_requested: bool,
        validation_file: str,
        execution_requested: bool,
        execution_file: str,
        oracle_configured: bool,
        oracle_file: str,
    ) -> dict[str, Any]:
        ready = outcome == "ready"
        validation_recorded = exists(validation_file)
        execution_recorded = exists(execution_file)
        oracle_recorded = exists(oracle_file)
        execution_succeeded = False
        if execution_recorded:
            execution_payload = _exchange_body(run_dir / prefix / execution_file)
            execution_succeeded = execution_payload.get("status") == "succeeded"
        if not ready:
            validation_status = "not_run_non_query"
            execution_status = "not_run_non_query"
            oracle_status = "not_run_non_query"
            complete = (
                not sql_present
                and not validation_recorded
                and not execution_recorded
                and not oracle_recorded
            )
        else:
            validation_status = (
                "recorded"
                if validation_recorded
                else "not_requested"
                if not validation_requested
                else "missing"
            )
            execution_status = (
                "recorded"
                if execution_recorded
                else "not_requested"
                if not execution_requested
                else "missing"
            )
            oracle_status = (
                "recorded"
                if oracle_recorded
                else "not_configured"
                if not oracle_configured
                else "not_evaluable_without_successful_execution"
                if execution_recorded and not execution_succeeded
                else "missing"
            )
            complete = (
                sql_present
                and (validation_recorded or not validation_requested)
                and (execution_recorded or not execution_requested)
                and (
                    oracle_recorded
                    or not oracle_configured
                    or (execution_recorded and not execution_succeeded)
                )
            )
        return {
            "outcome": outcome,
            "sqlPresent": sql_present,
            "validationDecision": validation_status,
            "executionDecision": execution_status,
            "oracleResult": oracle_status,
            "complete": complete,
        }

    base = query_path(
        outcome=str(result.get("baseOutcome") or "rejected"),
        sql_present=bool(result.get("baseSql")),
        validation_requested=scenario.validate_base,
        validation_file="05-validate-base.json",
        execution_requested=scenario.execute_base,
        execution_file="06-execute-base.json",
        oracle_configured=scenario.base_gold_check is not None,
        oracle_file="15-gold-execution-match-base.json",
    )
    turns: list[dict[str, Any]] = []
    turn_summaries = list(result.get("turns") or [])
    turn_count_complete = (
        len(turn_summaries) == len(scenario.turns)
        or result.get("baseOutcomeEndedConversation") is True
    )
    for index, (turn_spec, summary) in enumerate(
        zip(scenario.turns, turn_summaries), start=1
    ):
        slot = "" if index == 1 else f"-t{index}"
        observed = str(summary.get("observedOutcome") or "rejected")
        # A non-query follow-up may retain the prior SQL in the editor. It
        # proves that it generated no new SQL through the absent selection.
        selected = bool(summary.get("selectedVersionId"))
        turn_gold_check = turn_spec.gold_check or scenario.successor_gold_check
        turns.append(
            {
                "turnIndex": index,
                **query_path(
                    outcome=observed,
                    sql_present=selected if observed == "ready" else False,
                    validation_requested=scenario.validate_successor,
                    validation_file=f"12-validate-successor{slot}.json",
                    execution_requested=scenario.execute_successor,
                    execution_file=f"13-execute-successor{slot}.json",
                    oracle_configured=turn_gold_check is not None,
                    oracle_file=f"16-gold-execution-match-successor{slot}.json",
                ),
            }
        )
    return {
        "contractVersion": "harness.catalyst-notebook.measurement-evidence.v1",
        "base": base,
        "turns": turns,
        "declaredTurnCount": len(scenario.turns),
        "recordedTurnCount": len(turn_summaries),
        "complete": (
            base["complete"]
            and turn_count_complete
            and all(item["complete"] for item in turns)
        ),
    }


def _row_is_measurement_valid(row: dict[str, Any]) -> bool:
    if row.get("status") in {
        "failed_before_turn",
        "infrastructure_failed",
        "skipped",
    }:
        return False
    assertions = row.get("assertions") or []
    if not assertions:
        return False
    conformance_assertions = [
        item for item in assertions if item.get("class") == "conformance"
    ]
    conformed = bool(conformance_assertions) and all(
        item.get("passed") is True for item in conformance_assertions
    )
    evidence = row.get("measurementEvidence") or {}
    return (
        conformed
        and evidence.get("complete") is True
        and isinstance(row.get("sessionId"), str)
        and bool(row.get("sessionId"))
    )


def _append_result_outputs(
    *,
    run_dir: Path,
    run_id: str,
    scenario: NotebookScenario,
    backend_id: str,
    result: dict[str, Any],
    results_path: Path,
    events_path: Path,
    reused: bool = False,
    started_at: str | None = None,
    ended_at: str | None = None,
) -> None:
    """Emit the same reader-facing row and events for live or reused evidence."""
    prefix = result.get("evidencePrefix")
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("a completed result must name its evidence directory")
    answer = (
        _selected_answer_sql(run_dir, prefix)
        or result.get("baseSql")
        or result.get("baseAnswerText")
        or str(result.get("status"))
    )
    question = " ⇒ ".join(
        [scenario.initial_question, *(turn.instruction for turn in scenario.turns)]
    )
    metrics = {
        "http_status": result.get("httpStatus"),
        "latency_ms": (result.get("timing") or {}).get(
            "unadjustedGenerationWallMs"
        ),
        "answer_chars": len(answer) if isinstance(answer, str) else 0,
        "passed": result.get("passed"),
        "first_turn": result.get("repetition") == 1,
    }
    if reused:
        metrics["reused"] = True
    stream_row: dict[str, Any] = {
        "run_id": run_id,
        "scenario_id": scenario.id,
        "backend_id": backend_id,
        "turn": result.get("repetition"),
        "request": {"question": question},
        "response": {
            "answer": answer,
            "question": scenario.initial_question,
            "baseOutcome": result.get("baseOutcome"),
            "baseAnswerText": result.get("baseAnswerText"),
            "baseSql": result.get("baseSql"),
            "expectedBaseOutcome": result.get("expectedBaseOutcome"),
            "turns": [
                {
                    "turnId": turn.get("turnId"),
                    "instruction": turn.get("instruction"),
                    "expectedOutcome": turn.get("expectedOutcome"),
                    "observedOutcome": turn.get("observedOutcome"),
                    "answerText": turn.get("answerText"),
                    "sql": turn.get("sql"),
                    "selectedVersionId": turn.get("selectedVersionId"),
                    "selectedQueryDigest": turn.get("selectedQueryDigest"),
                    "executionId": turn.get("executionId"),
                    "candidateDigests": turn.get("candidateDigests") or [],
                    "evidenceDigest": turn.get("evidenceDigest"),
                    "timing": turn.get("timing") or {},
                }
                for turn in result.get("turns") or []
            ],
            "resultPreview": result.get("resultPreview"),
            "failedAssertions": [
                {
                    "name": item["name"],
                    "class": item.get("class") or assertion_class(item["name"]),
                    "evidence": _compact_evidence(item.get("evidence")),
                }
                for item in result.get("assertions") or []
                if not item.get("passed")
            ][:8],
        },
        "metrics": metrics,
        "error": _first_failed_assertion(result.get("assertions") or []),
    }
    started_at = started_at or result.get("startedAt")
    ended_at = ended_at or result.get("endedAt")
    if isinstance(started_at, str) and started_at:
        stream_row["started_at"] = started_at
    if isinstance(ended_at, str) and ended_at:
        stream_row["ended_at"] = ended_at
    append_jsonl(results_path, stream_row)

    recorded_turns = [
        turn for turn in result.get("turns") or [] if isinstance(turn, dict)
    ]
    event_result = result
    if recorded_turns:
        # The shared event projector predates multi-turn scenarios and its
        # unsuffixed evidence paths identify the first follow-up. Give it that
        # turn's identities, then append every later suffixed turn below.
        first_turn = recorded_turns[0]
        event_result = {
            **result,
            "followupTurnId": first_turn.get("turnId"),
            "selectedVersionId": first_turn.get("selectedVersionId"),
            "selectedQueryDigest": first_turn.get("selectedQueryDigest"),
            "successorExecutionId": first_turn.get("executionId"),
        }
    for event in notebook_result_events(
        run_id=run_id,
        run_dir=run_dir,
        prefix=prefix,
        result=event_result,
        backend_id=backend_id,
    ):
        append_event(events_path, event)

    def materialized(paths: list[str]) -> list[str]:
        root = run_dir.resolve()
        existing: list[str] = []
        for relative in paths:
            path = run_dir / relative
            if not path.resolve().is_relative_to(root):
                raise ValueError(
                    "event evidence path must stay within the run directory"
                )
            if path.is_file():
                existing.append(relative)
        return existing

    event_common = {
        "schema_version": NOTEBOOK_EVENT_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario_id": str(result["scenarioId"]),
        "repetition": int(result["repetition"]),
        "session_id": result.get("sessionId"),
        "backend_id": backend_id,
    }
    for turn_index, turn in enumerate(recorded_turns[1:], start=2):
        slot = f"-t{turn_index}"
        turn_id = turn.get("turnId")
        if turn_id:
            append_event(
                events_path,
                {
                    **event_common,
                    "event_type": "turn",
                    "turn_role": "followup",
                    "turn_id": turn_id,
                    "evidence_paths": materialized(
                        [
                            f"{prefix}/08-create-followup{slot}.json",
                            f"{prefix}/10-final-turns{slot}.json",
                            f"{prefix}/11-followup-generation-evidence{slot}.json",
                        ]
                    ),
                },
            )
        version_id = turn.get("selectedVersionId")
        if version_id:
            append_event(
                events_path,
                {
                    **event_common,
                    "event_type": "version",
                    "version_role": "successor",
                    "version_id": version_id,
                    "query_digest": turn.get("selectedQueryDigest"),
                    "turn_id": turn_id,
                    "evidence_paths": materialized(
                        [
                            f"{prefix}/09-refreshed-session{slot}.json",
                            f"{prefix}/10-final-turns{slot}.json",
                        ]
                    ),
                },
            )
        execution_id = turn.get("executionId")
        if execution_id:
            append_event(
                events_path,
                {
                    **event_common,
                    "event_type": "execution",
                    "execution_role": "successor",
                    "execution_id": execution_id,
                    "version_id": version_id,
                    "evidence_paths": materialized(
                        [
                            f"{prefix}/13-execute-successor{slot}.json",
                            f"{prefix}/14-postgres-successor{slot}.json",
                            f"{prefix}/16-gold-execution-match-successor{slot}.json",
                        ]
                    ),
                },
            )
    append_event(
        events_path,
        {
            "schema_version": NOTEBOOK_EVENT_SCHEMA_VERSION,
            "event_type": "evaluation",
            "check": "notebook_scenario",
            "run_id": run_id,
            "scenario_id": scenario.id,
            "backend_id": backend_id,
            "turn": result.get("repetition"),
            "http_status": result.get("httpStatus"),
            "passed": result.get("passed"),
            **({"reused": True} if reused else {}),
        },
    )


def _adopt_reused_pair(
    *,
    recorder: _EvidenceRecorder,
    resume_from: Path | None,
    run_id: str,
    scenario: NotebookScenario,
    team: str | None,
    recorded: list[dict[str, Any]],
    results_path: Path,
    events_path: Path,
    imports: list[dict[str, Any]],
    preflight_digests: dict[str, str],
) -> None:
    """Bring a reused pair fully into the resumed run's directory.

    Everything downstream -- the live dashboard, the report's evidence
    links, the scorer -- reads one run directory, so a reused pair's rows,
    feed entries, and evidence tree travel with the resumed run instead of
    staying behind in the interrupted one.
    """
    # Match the live rows exactly: they group by the profile that answered
    # the follow-ups (which falls back to the opener when there are none).
    backend_id = team or scenario.followup_profile_id
    key = f"{backend_id}/{scenario.id}" if team is not None else scenario.id
    if resume_from is None:
        raise ValueError("recovery source is required when adopting evidence")
    for row in recorded:
        evidence_prefix = row.get("evidencePrefix")
        if not isinstance(evidence_prefix, str) or not evidence_prefix.startswith(
            f"scenarios/{key}/"
        ):
            raise ValueError(
                f"reusable {key} row does not identify its exact evidence directory"
            )
        source = resume_from / evidence_prefix
        if not source.is_dir():
            raise ValueError(f"recovery evidence is missing for {evidence_prefix}")
        copied: list[dict[str, Any]] = []
        for source_file in sorted(source.rglob("*.json")):
            relative = source_file.relative_to(resume_from).as_posix()
            expected_sha256 = preflight_digests.get(relative)
            if expected_sha256 is None:
                raise ValueError(
                    f"recovery evidence appeared after preflight: {relative}"
                )
            copied.append(
                recorder.adopt(
                    relative,
                    source_file,
                    kind="recovered_conversation_evidence",
                    metadata={
                        "sourceRunId": resume_from.name,
                        "scenarioId": scenario.id,
                        "profileId": backend_id,
                    },
                    expected_sha256=expected_sha256,
                )
            )
        if not copied:
            raise ValueError(f"recovery evidence is empty for {evidence_prefix}")
        row_sha256 = _canonical_sha256(row)
        imports.append(
            {
                "kind": "measurement_cell",
                "sourceRunId": resume_from.name,
                "profileId": backend_id,
                "scenarioId": scenario.id,
                "repetition": row.get("repetition"),
                "rowSha256": row_sha256,
                "evidence": [
                    {"path": item["path"], "sha256": item["sha256"]}
                    for item in copied
                ],
            }
        )
        append_jsonl(recorder.run_dir / "rows.jsonl", row)
        recorder.file(
            "rows.jsonl",
            kind="measurement_rows",
            media_type="application/x-ndjson",
            replace=True,
        )
        _append_result_outputs(
            run_dir=recorder.run_dir,
            run_id=run_id,
            scenario=scenario,
            backend_id=backend_id,
            result=row,
            results_path=results_path,
            events_path=events_path,
            reused=True,
        )


def _adopt_recovery_warmup(
    *,
    recorder: _EvidenceRecorder,
    source: Path,
    profile_id: str,
    imports: list[dict[str, Any]],
    preflight_digests: dict[str, str],
) -> None:
    """Carry the excluded warm-up that actually preceded reused cells."""
    source_prefix = source / "warmups" / profile_id
    copied: list[dict[str, Any]] = []
    for source_file in sorted(source_prefix.rglob("*.json")):
        source_relative = source_file.relative_to(source).as_posix()
        expected_sha256 = preflight_digests.get(source_relative)
        if expected_sha256 is None:
            raise ValueError(
                f"recovery warm-up appeared after preflight: {source_relative}"
            )
        tail = source_file.relative_to(source_prefix).as_posix()
        destination = f"warmups/{profile_id}/sources/{source.name}/{tail}"
        copied.append(
            recorder.adopt(
                destination,
                source_file,
                kind="recovered_excluded_warmup",
                metadata={
                    "sourceRunId": source.name,
                    "profileId": profile_id,
                    "sourcePath": source_relative,
                },
                expected_sha256=expected_sha256,
            )
        )
    if not copied:
        raise ValueError(f"recovery warm-up is missing for profile {profile_id!r}")
    imports.append(
        {
            "kind": "excluded_warmup",
            "sourceRunId": source.name,
            "profileId": profile_id,
            "evidence": [
                {"path": item["path"], "sha256": item["sha256"]}
                for item in copied
            ],
        }
    )


def _adopt_recovery_interruptions(
    *,
    recorder: _EvidenceRecorder,
    source: Path,
    failures: list[dict[str, Any]],
    evidence_index: dict[str, dict[str, Any]],
    imports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep inherited failure pointers truthful inside the recovery run."""
    adopted_failures: list[dict[str, Any]] = []
    for failure in failures:
        source_path = failure.get("evidencePath")
        origin_run_id = failure.get("runId")
        origin_path = failure.get("sourceEvidencePath", source_path)
        if (
            not isinstance(source_path, str)
            or not source_path
            or not isinstance(origin_run_id, str)
            or not origin_run_id
            or not isinstance(origin_path, str)
            or not origin_path
        ):
            raise ValueError(
                "recovery interruption is missing its run or evidence identity"
            )
        entry = evidence_index.get(source_path)
        if entry is None:
            raise ValueError(
                f"recovery interruption evidence is not indexed: {source_path}"
            )
        destination = (
            f"interruptions/sources/{origin_run_id}/{origin_path}"
        )
        copied = recorder.adopt(
            destination,
            source / source_path,
            kind="recovered_interruption_evidence",
            metadata={
                "sourceRunId": source.name,
                "originRunId": origin_run_id,
                "sourcePath": source_path,
                "originEvidencePath": origin_path,
            },
            expected_sha256=str(entry["sha256"]),
        )
        adopted_failures.append(
            {
                **failure,
                "evidencePath": destination,
                "sourceEvidencePath": origin_path,
                "recoveredFromRunId": source.name,
            }
        )
        imports.append(
            {
                "kind": "collection_interruption",
                "sourceRunId": source.name,
                "originRunId": origin_run_id,
                "sourcePath": source_path,
                "originEvidencePath": origin_path,
                "destinationPath": destination,
                "sha256": copied["sha256"],
            }
        )
    return adopted_failures


def _pair_is_complete(
    recorded: list[dict[str, Any]],
    suite: NotebookSuite,
    scenario: NotebookScenario,
    repetitions: int | None,
) -> bool:
    """Whether an interrupted run finished this pair by its suite's rules.

    Older suites may declare several within-cell repetitions. Phase 1
    comparison suites declare one cell and repeat only as complete new runs.
    """
    # Only scored repetitions count: interrupted infrastructure attempts and
    # skips are outside the model denominator, so they neither complete a
    # pair nor read as instability.
    scored = [
        row
        for row in recorded
        if row.get("status") not in {"skipped", "infrastructure_failed"}
    ]
    required = _effective_repetitions(suite, scenario, repetitions)
    if len(scored) < required:
        return False
    if (
        repetitions is None
        and suite.extended_repetitions is not None
        and required < suite.extended_repetitions
        and repetition_pair_is_unstable(scored)
    ):
        return len(scored) >= suite.extended_repetitions
    return True


def _finished_pairs(
    resume_from: Path | str | None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Completed (team, scenario) rows from an interrupted run, by pair.

    Only whole pairs are reused. A pair that was mid-flight when the run
    stopped is re-run from the start, because half a pair's repetitions is
    not a measurement of anything.
    """
    if resume_from is None:
        return {}
    # rows.jsonl is appended and re-signed as each repetition completes. Read
    # only that signed prefix: an abrupt stop may leave an unfinished next
    # line after it, but may not rewrite any completed row.
    rows: list[dict[str, Any]] = []
    source = Path(resume_from)
    incremental = source / "rows.jsonl"
    if not incremental.exists():
        return {}
    indexed = _validated_evidence_index(source)
    if "rows.jsonl" not in indexed:
        return {}
    rows = _signed_jsonl_records(source, indexed, "rows.jsonl")
    pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    seen_cells: set[tuple[str, str, int]] = set()
    for row in rows:
        profile_id = row.get("profileId")
        scenario_id = row.get("scenarioId")
        if not isinstance(profile_id, str) or not isinstance(scenario_id, str):
            continue
        if not _row_is_measurement_valid(row):
            continue
        repetition = row.get("repetition")
        if not isinstance(repetition, int):
            continue
        cell = (profile_id, scenario_id, repetition)
        if cell in seen_cells:
            raise ValueError(f"recovery source duplicates measurement cell {cell!r}")
        seen_cells.add(cell)
        pairs.setdefault((profile_id, scenario_id), []).append(row)
    return pairs


def _scenario_for_profile(
    scenario: NotebookScenario, profile_id: str
) -> NotebookScenario:
    """The same scenario, answered by one team.

    Every team is compared on identical wording and order; only who answers
    changes, so the scenario is rebuilt with its profile references replaced
    and nothing else touched.
    """
    return replace(
        scenario,
        initial_profile_id=profile_id,
        turns=tuple(replace(turn, profile_id=profile_id) for turn in scenario.turns),
    )


def _effective_repetitions(
    suite: NotebookSuite, scenario: NotebookScenario, repetitions: int | None
) -> int:
    return repetitions or scenario.repetitions or suite.repetitions


def _preflight_recovery_evidence(
    resume_from: Path,
    reusable_pairs: list[tuple[str, list[dict[str, Any]]]],
    warmup_profiles: set[str] | None = None,
) -> dict[str, str]:
    """Hash every file eligible for import before any model conversation."""
    digests: dict[str, str] = {}
    seen_prefixes: set[str] = set()
    indexed = {
        path: str(item["sha256"])
        for path, item in _validated_evidence_index(resume_from).items()
    }

    def add_tree(prefix: str) -> None:
        source = resume_from / prefix
        if not source.is_dir():
            raise ValueError(f"recovery evidence is missing for {prefix}")
        evidence_files = sorted(source.rglob("*.json"))
        if not evidence_files:
            raise ValueError(f"recovery evidence is empty for {prefix}")
        for source_file in evidence_files:
            relative = source_file.relative_to(resume_from).as_posix()
            if relative in digests:
                raise ValueError(f"recovery evidence path is duplicated: {relative}")
            digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
            if relative not in indexed:
                raise ValueError(f"recovery evidence is not indexed: {relative}")
            if indexed[relative] != digest:
                raise ValueError(
                    f"recovery evidence no longer matches its index: {relative}"
                )
            digests[relative] = digest

    for expected_prefix, rows in reusable_pairs:
        for row in rows:
            evidence_prefix = row.get("evidencePrefix")
            if (
                not isinstance(evidence_prefix, str)
                or not evidence_prefix.startswith(expected_prefix)
                or evidence_prefix in seen_prefixes
            ):
                raise ValueError(
                    "recovery row has a missing, misplaced, or duplicate evidence path"
                )
            seen_prefixes.add(evidence_prefix)
            add_tree(evidence_prefix)
    for profile_id in sorted(warmup_profiles or set()):
        add_tree(f"warmups/{profile_id}")
    return digests


def _run_tree_sha256(run_dir: Path) -> str:
    files = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        files.append(
            {
                "path": path.relative_to(run_dir).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return _canonical_sha256(files)


def _validated_evidence_index(
    run_dir: Path,
    *,
    expected_run_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Verify an interrupted run's signed inventory before trusting any row."""
    expected_run_id = expected_run_id or run_dir.name
    index_candidates = (
        run_dir / "evidence-index.json",
        run_dir / ".evidence-index.json.tmp",
    )
    checksum_candidates = (
        run_dir / "evidence-index.sha256",
        run_dir / ".evidence-index.sha256.tmp",
    )
    checksums: set[str] = set()
    for path in checksum_candidates:
        try:
            value = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match = re.fullmatch(
            r"([0-9a-f]{64})  evidence-index\.json\n?",
            value,
        )
        if match is not None:
            checksums.add(match.group(1))
    candidates: list[dict[str, Any]] = []
    for path in index_candidates:
        try:
            encoded = path.read_bytes()
        except OSError:
            continue
        if hashlib.sha256(encoded).hexdigest() not in checksums:
            continue
        try:
            candidate = json.loads(encoded)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            candidates.append(candidate)
    if not candidates:
        raise ValueError(
            "recovery evidence index is invalid or its checksum does not match"
        )

    def validate(
        index: dict[str, Any],
    ) -> tuple[tuple[int, int, int], dict[str, dict[str, Any]]]:
        if (
            index.get("contractVersion")
            != "harness.catalyst-notebook.evidence-index.v1"
            or index.get("runId") != expected_run_id
            or index.get("hashAlgorithm") != "sha256"
        ):
            raise ValueError("recovery evidence index identity is invalid")
        entries = index.get("entries")
        if not isinstance(entries, list):
            raise ValueError("recovery evidence index entries are invalid")
        validated: dict[str, dict[str, Any]] = {}
        total_bytes = 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("recovery evidence index entry is invalid")
            relative = entry.get("path")
            digest = entry.get("sha256")
            byte_count = entry.get("bytes")
            if (
                not isinstance(relative, str)
                or not relative
                or relative in validated
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or not isinstance(byte_count, int)
                or byte_count < 0
            ):
                raise ValueError("recovery evidence index entry is invalid")
            path = run_dir / relative
            if (
                not path.resolve().is_relative_to(run_dir.resolve())
                or not path.is_file()
            ):
                raise ValueError(
                    f"recovery evidence is missing or misplaced: {relative}"
                )
            file_bytes = path.read_bytes()
            # These streams are append-only. The signed prefix is
            # authoritative; any later bytes were not committed records.
            if relative in {"rows.jsonl", "interruptions.jsonl"}:
                if len(file_bytes) < byte_count:
                    raise ValueError(
                        f"recovery {relative} is shorter than its signed prefix"
                    )
                signed_bytes = file_bytes[:byte_count]
            else:
                if len(file_bytes) != byte_count:
                    raise ValueError(f"recovery evidence size changed: {relative}")
                signed_bytes = file_bytes
            if hashlib.sha256(signed_bytes).hexdigest() != digest:
                raise ValueError(
                    f"recovery evidence no longer matches its index: {relative}"
                )
            validated[relative] = dict(entry)
            total_bytes += byte_count
        core_paths = {"run_manifest.json", "run-config.json", "suite.json"}
        try:
            run_config = json.loads(
                (run_dir / "run-config.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("recovery run configuration cannot be read") from error
        rubric_digest = str(run_config.get("readerRubricSha256") or "")
        if rubric_digest:
            core_paths.add("reader-rubric.md")
            indexed_digest = str(
                (validated.get("reader-rubric.md") or {}).get("sha256") or ""
            )
            if indexed_digest and indexed_digest != rubric_digest:
                raise ValueError(
                    "recovery reader rubric differs from its frozen digest"
                )
        missing_core = sorted(core_paths.difference(validated))
        if missing_core:
            raise ValueError(
                "recovery identity files are not indexed: "
                + ", ".join(missing_core)
            )
        rows_bytes = int((validated.get("rows.jsonl") or {}).get("bytes") or 0)
        return (len(validated), rows_bytes, total_bytes), validated

    valid: list[tuple[tuple[int, int, int], dict[str, dict[str, Any]]]] = []
    errors: list[ValueError] = []
    for candidate in candidates:
        try:
            valid.append(validate(candidate))
        except ValueError as error:
            errors.append(error)
    if not valid:
        raise errors[0]
    # A crash can leave both the prior canonical checkpoint and the next fully
    # written temporary checkpoint. Prefer the one that safely binds more
    # evidence, especially a longer completed-row prefix.
    return max(valid, key=lambda item: item[0])[1]


def validate_notebook_evidence(
    run_dir: Path | str,
) -> dict[str, dict[str, Any]]:
    """Verify a run's signed evidence inventory before downstream use."""

    run_dir = Path(run_dir)
    try:
        manifest = json.loads(
            (run_dir / "run_manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("run manifest cannot be read") from error
    run_id = manifest.get("run_id") if isinstance(manifest, dict) else None
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run manifest has no run_id")
    return _validated_evidence_index(run_dir, expected_run_id=run_id)


def _signed_jsonl_records(
    run_dir: Path,
    evidence_index: dict[str, dict[str, Any]],
    relative_path: str,
) -> list[dict[str, Any]]:
    entry = evidence_index.get(relative_path)
    if entry is None:
        return []
    signed = (run_dir / relative_path).read_bytes()[: int(entry["bytes"])]
    if signed and not signed.endswith(b"\n"):
        raise ValueError(f"recovery {relative_path} has an incomplete signed record")
    records: list[dict[str, Any]] = []
    try:
        for line in signed.decode("utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"recovery {relative_path} record is not an object")
            records.append(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"recovery {relative_path} has an invalid signed record") from error
    return records


def _load_resume_header(resume_from: Path | None) -> dict[str, Any] | None:
    if resume_from is None:
        return None
    if not resume_from.is_dir():
        raise ValueError(f"recovery source does not exist: {resume_from}")
    try:
        status = json.loads(
            (resume_from / "run-status.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (resume_from / "run_manifest.json").read_text(encoding="utf-8")
        )
        frozen_config = json.loads(
            (resume_from / "run-config.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            "recovery requires the source manifest, frozen config, and run status"
        ) from error
    if not all(isinstance(item, dict) for item in (status, manifest, frozen_config)):
        raise ValueError(
            "recovery requires object-shaped manifest, frozen config, and run status"
        )
    if status.get("state") != "incomplete":
        raise ValueError("only an immutable incomplete run can be recovered")
    source_id = manifest.get("run_id")
    if not isinstance(source_id, str) or source_id != resume_from.name:
        raise ValueError("recovery source directory and manifest run ID disagree")
    evidence_index = _validated_evidence_index(resume_from)
    failures = status.get("infrastructureFailures")
    if (
        status.get("contractVersion")
        != "harness.catalyst-notebook.run-status.v1"
        or status.get("runId") != source_id
        or status.get("measurementValid") is not False
        or not isinstance(failures, list)
        or any(not isinstance(item, dict) for item in failures)
    ):
        raise ValueError("recovery run status is inconsistent with its source")
    signed_failures = _signed_jsonl_records(
        resume_from,
        evidence_index,
        "interruptions.jsonl",
    )
    if any(
        item.get("runId") != source_id
        or item.get("status") != "infrastructure_failed"
        or not isinstance(item.get("phase"), str)
        or not isinstance(item.get("evidencePath"), str)
        for item in signed_failures
    ):
        raise ValueError("recovery interruption history is invalid")
    merged_failures: list[dict[str, Any]] = []
    seen_failures: set[str] = set()
    for item in [*failures, *signed_failures]:
        digest = _canonical_sha256(item)
        if digest in seen_failures:
            continue
        seen_failures.add(digest)
        merged_failures.append(dict(item))
    prior_ancestry = list(manifest.get("resumeAncestry") or [])
    ancestry = prior_ancestry + [source_id]
    if not all(isinstance(item, str) and item for item in ancestry):
        raise ValueError("recovery ancestry contains an invalid run ID")
    if len(set(ancestry)) != len(ancestry):
        raise ValueError("recovery ancestry contains a cycle or duplicate run")
    direct_parent = manifest.get("resumedFrom")
    if (
        status.get("resumedFrom") != direct_parent
        or list(status.get("resumeAncestry") or []) != prior_ancestry
    ):
        raise ValueError("recovery run status and manifest ancestry disagree")
    if prior_ancestry:
        if direct_parent != prior_ancestry[-1]:
            raise ValueError("recovery manifest does not preserve its direct parent")
    elif direct_parent is not None:
        raise ValueError("recovery manifest names a parent outside its ancestry")
    for index, ancestor_id in enumerate(prior_ancestry):
        ancestor_path = resume_from.parent / str(ancestor_id) / "run_manifest.json"
        try:
            _validated_evidence_index(ancestor_path.parent)
            ancestor = json.loads(ancestor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                f"recovery ancestry manifest is missing for {ancestor_id!r}"
            ) from error
        expected_ancestry = prior_ancestry[:index]
        expected_parent = expected_ancestry[-1] if expected_ancestry else None
        if (
            ancestor.get("run_id") != ancestor_id
            or list(ancestor.get("resumeAncestry") or []) != expected_ancestry
            or ancestor.get("resumedFrom") != expected_parent
        ):
            raise ValueError(f"recovery ancestry is inconsistent at {ancestor_id!r}")
    return {
        "runId": source_id,
        "ancestry": ancestry,
        "manifest": manifest,
        "frozenConfig": frozen_config,
        "infrastructureFailures": merged_failures,
        "evidenceIndex": evidence_index,
        "treeSha256": _run_tree_sha256(resume_from),
    }


def _validate_recovery_identity(
    *,
    resume_from: Path,
    header: dict[str, Any],
    frozen_config: dict[str, Any],
    suite_sha256: str,
    manifest: RunManifest,
    profiles: dict[str, Any],
    dataset: dict[str, Any],
    catalog: dict[str, Any],
    allow_incomplete_source_discovery: bool = False,
) -> None:
    source_manifest = header["manifest"]
    comparisons = {
        "frozen configuration": (
            header["frozenConfig"],
            frozen_config,
        ),
        "suite bytes": (source_manifest.get("suite_sha256"), suite_sha256),
        "Harness revision": (source_manifest.get("git_sha"), manifest.git_sha),
        "component revisions": (
            source_manifest.get("target_provenance") or [],
            manifest.target_provenance,
        ),
        "dataset ID": (source_manifest.get("dataset_id"), manifest.dataset_id),
        "dataset version": (
            source_manifest.get("dataset_version"),
            manifest.dataset_version,
        ),
        "catalog identity": (
            source_manifest.get("schema_mapping_version"),
            manifest.schema_mapping_version,
        ),
    }
    discovery = (
        (
            "profile and model discovery",
            resume_from / "discovery/query-options.json",
            profiles,
        ),
        ("dataset discovery", resume_from / "discovery/dataset.json", dataset),
        ("catalog discovery", resume_from / "discovery/catalog.json", catalog),
    )
    source_discovery: dict[str, dict[str, Any]] = {}
    for name, path, _ in discovery:
        relative = path.relative_to(resume_from).as_posix()
        if path.is_file() and relative not in header["evidenceIndex"]:
            raise ValueError(f"recovery discovery evidence is not indexed: {relative}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            response = payload.get("response") or {}
            body = response.get("body")
            http_status = response.get("httpStatus")
        except (OSError, json.JSONDecodeError, AttributeError):
            body = None
            http_status = None
        if (
            isinstance(body, dict)
            and isinstance(http_status, int)
            and 200 <= http_status < 300
        ):
            source_discovery[name] = body
    if len(source_discovery) == len(discovery):
        comparisons.update(
            {
                name: (source_discovery[name], current)
                for name, _, current in discovery
            }
        )
    elif not allow_incomplete_source_discovery:
        raise ValueError("recovery source has incomplete discovery evidence")
    drifted = [
        name
        for name, (source, current) in comparisons.items()
        if _canonical_sha256(source) != _canonical_sha256(current)
    ]
    if drifted:
        raise ValueError(
            "recovery identity drifted before reuse or model calls: "
            + ", ".join(drifted)
        )


def _record_warmup(
    *,
    client: NotebookTransport,
    recorder: _EvidenceRecorder,
    profile_id: str,
    question: str,
) -> str:
    """Run one fresh, recorded conversation that never enters scoring."""
    prefix = f"warmups/{profile_id}"
    created = client.create_session(question, profile_id)
    session = recorder.exchange(
        f"{prefix}/01-create-session.json", created, kind="excluded_warmup"
    )
    if _profile_availability_drift(created):
        raise _CollectionInterrupted(
            f"{prefix}/01-create-session.json",
            created,
            interruption_kind="profile_availability",
            interruption_code="profile_unavailable",
        )
    session_id = session.get("sessionId")
    if created.status_code != 201 or not isinstance(session_id, str):
        raise ValueError(f"warm-up failed before a session for profile {profile_id!r}")
    timeline_exchange = client.get_turns(session_id)
    timeline = recorder.exchange(
        f"{prefix}/02-turns.json", timeline_exchange, kind="excluded_warmup"
    )
    initial = next(
        (
            item
            for item in timeline.get("turns") or []
            if item.get("kind") == "initial" and isinstance(item.get("turnId"), str)
        ),
        None,
    )
    if timeline_exchange.status_code != 200 or initial is None:
        raise ValueError(f"warm-up timeline is incomplete for profile {profile_id!r}")
    interruption = _persisted_service_interruption(initial)
    evidence_exchange = client.generation_evidence(session_id, initial["turnId"])
    try:
        recorder.exchange(
            f"{prefix}/03-generation-evidence.json",
            evidence_exchange,
            kind="excluded_warmup",
        )
    except _CollectionInterrupted as later:
        raise _carry_recorded_failure(later, interruption) from later
    if evidence_exchange.status_code != 200:
        raise ValueError(f"warm-up evidence is incomplete for profile {profile_id!r}")
    if interruption is not None:
        raise _CollectionInterrupted(
            f"{prefix}/02-turns.json",
            timeline_exchange,
            recorded_failure=interruption,
        )
    return session_id


def run_notebook_suite(
    *,
    suite_path: Path | str,
    client: NotebookTransport,
    output_dir: Path | str = "artifacts/catalyst-notebook-validation",
    project_root: Path | str = ".",
    scenario_ids: set[str] | None = None,
    repetitions: int | None = None,
    include_manual: bool = False,
    postgres_checker: PostgresChecker | None = None,
    gold_checker: GoldChecker | None = None,
    manual_checkpoint: Callable[[NotebookScenario, str], None] | None = None,
    provenance_loader: Callable[[Path], list[dict[str, Any]]] = _target_provenance,
    resume_from: Path | str | None = None,
    frozen_config: dict[str, Any] | None = None,
    warmup_question: str | None = None,
    reader_rubric_path: Path | str | None = None,
) -> NotebookRunResult:
    suite_path = Path(suite_path)
    suite = load_notebook_suite(suite_path)
    # A gateway serving several sources answers its default when it is not
    # told which, so a suite bound to one binds the client to it too.
    if suite.data_source_id is not None:
        bind = getattr(client, "bind_data_source", None)
        if bind is not None:
            bind(suite.data_source_id)
    selected = [
        scenario
        for scenario in suite.scenarios
        if scenario_ids is None or scenario.id in scenario_ids
    ]
    if not selected:
        raise ValueError("no notebook scenarios selected")
    if (
        suite.id.startswith(_PHASE1_COMPARISON_SUITE_PREFIX)
        and scenario_ids is not None
        and scenario_ids != {scenario.id for scenario in suite.scenarios}
    ):
        raise ValueError(
            "Phase 1 collection must run the complete frozen scenario set"
        )
    if repetitions is not None and repetitions < 1:
        raise ValueError("repetitions must be at least one")
    if (
        suite.id.startswith(_PHASE1_COMPARISON_SUITE_PREFIX)
        and repetitions not in {None, 1}
    ):
        raise ValueError(
            "Phase 1 repeated measures are separate full-suite runs; "
            "the repetition override must be one"
        )

    resume_path = Path(resume_from) if resume_from is not None else None
    resume_header = _load_resume_header(resume_path)
    recovery_chain = (
        tuple(
            resume_path.parent / str(source_id)
            for source_id in reversed(resume_header["ancestry"])
        )
        if resume_path is not None and resume_header is not None
        else ()
    )
    recovery_source_hashes = (
        {resume_path: resume_header["treeSha256"]}
        if resume_path is not None and resume_header is not None
        else {}
    )
    run_id = str(uuid4())
    run_dir = Path(output_dir) / run_id
    recorder = _EvidenceRecorder(run_dir, run_id)
    root = Path(project_root).resolve()
    target_provenance = provenance_loader(root)
    suite_sha256 = hashlib.sha256(suite_path.read_bytes()).hexdigest()
    public_config = publishable(frozen_config or {
        "contractVersion": "harness.catalyst-notebook.run-config.v1",
        "suiteSha256": suite_sha256,
        "scenarioIds": [scenario.id for scenario in selected],
        "repetitions": repetitions,
        "includeManual": include_manual,
        "warmupQuestion": warmup_question or "",
    })
    configured_warmup = str(public_config.get("warmupQuestion") or "")
    if warmup_question and configured_warmup and warmup_question != configured_warmup:
        raise ValueError("the requested warm-up differs from the frozen run config")
    warmup_question = configured_warmup or warmup_question
    manifest = RunManifest(
        run_id=run_id,
        project="clinical-ai-validation-harness",
        component="catalyst-iterative-query-notebook-validation",
        git_sha=read_harness_git_sha(root),
        dataset_id=suite.dataset_id,
        dataset_version=suite.dataset_version,
        schema_mapping_version=suite.catalog_version,
        gen_ai_provider_name=suite.provider_name,
        gen_ai_operation_name="chat",
        decision_rationale=(
            "Exercise the real Catalyst workbench session/turn/version path, retain "
            "typed model evidence, and compare selected executions through a separate "
            "read-only PostgreSQL connection."
        ),
        target_provenance=target_provenance,
        report_family="catalyst",
        suite_id=suite.id,
        suite_sha256=suite_sha256,
        resumed_from=(resume_header or {}).get("runId"),
        resume_ancestry=list((resume_header or {}).get("ancestry") or []),
    )
    recorder.json("run_manifest.json", manifest.to_dict(), kind="run_manifest")
    recorder.json(
        "suite.json",
        json.loads(suite_path.read_text(encoding="utf-8")),
        kind="suite_definition",
        metadata={"sourceSha256": suite_sha256},
    )
    recorder.json("run-config.json", public_config, kind="run_configuration")
    if reader_rubric_path is not None:
        rubric_source = Path(reader_rubric_path)
        rubric_bytes = rubric_source.read_bytes()
        rubric_digest = hashlib.sha256(rubric_bytes).hexdigest()
        expected_rubric_digest = str(
            public_config.get("readerRubricSha256") or ""
        )
        if expected_rubric_digest and rubric_digest != expected_rubric_digest:
            raise ValueError(
                "reader rubric bytes differ from the frozen run configuration"
            )
        rubric_path = run_dir / "reader-rubric.md"
        rubric_path.write_bytes(rubric_bytes)
        recorder.file(
            "reader-rubric.md",
            kind="reader_rubric",
            media_type="text/markdown",
        )
    recovery_imports: list[dict[str, Any]] = []
    source_failures: list[dict[str, Any]] = list(
        (resume_header or {}).get("infrastructureFailures") or []
    )
    infrastructure_failures = (
        _adopt_recovery_interruptions(
            recorder=recorder,
            source=resume_path,
            failures=source_failures,
            evidence_index=resume_header["evidenceIndex"],
            imports=recovery_imports,
        )
        if resume_path is not None and resume_header is not None
        else source_failures
    )
    status = {
        "contractVersion": "harness.catalyst-notebook.run-status.v1",
        "runId": run_id,
        "state": "incomplete",
        "measurementValid": False,
        "resumedFrom": (resume_header or {}).get("runId"),
        "resumeAncestry": list((resume_header or {}).get("ancestry") or []),
        "infrastructureFailures": infrastructure_failures,
    }
    _write_run_status(run_dir, status)
    results: list[dict[str, Any]] = []
    skipped = 0

    # Additive run-stream files use the same run/backend_selected/evaluation +
    # results-row contract as harness/validate/runner.py. They are signed at
    # the last complete record so a recovery never trusts mutable summaries.
    #
    # harness/catalyst/events.py::workbench_event_envelope is a separate,
    # tested bridge for typed Gateway *session* events (a different
    # granularity than this run/scenario spine) and stays unused here.
    events_path = run_dir / "events.jsonl"
    results_path = run_dir / "results.jsonl"
    # One matrix cell per (team, scenario): the comparison's tracking grid.
    cell_teams: tuple[str | None, ...] = suite.comparison_profiles or (None,)
    cells = [
        {
            "scenario_id": scenario.id,
            "backend_id": cell_team or scenario.followup_profile_id,
            "turns": _effective_repetitions(suite, scenario, repetitions),
        }
        for cell_team in cell_teams
        for scenario in selected
        if not (scenario.manual_only and not include_manual)
    ]
    append_event(
        events_path,
        {
            "schema_version": NOTEBOOK_EVENT_SCHEMA_VERSION,
            "event_type": "run",
            "run_id": run_id,
            "component": "catalyst-notebook-validation",
            "report_family": "catalyst",
            "suite_id": suite.id,
            "suite_sha256": suite_sha256,
            "scenario_ids": [cell["scenario_id"] for cell in cells],
            "backend_ids": sorted({cell["backend_id"] for cell in cells}),
            "cells": cells,
            "evidence_paths": ["run_manifest.json", "suite.json"],
        },
    )
    for profile_id, profile in suite.profiles.items():
        writer = profile.get("writerModelId", profile_id)
        reviewer = profile.get("reviewerModelId")
        label = (
            writer
            if reviewer is None or writer == reviewer
            else f"{writer} + {reviewer}"
        )
        append_event(
            events_path,
            {
                "schema_version": NOTEBOOK_EVENT_SCHEMA_VERSION,
                "event_type": "backend_selected",
                "run_id": run_id,
                "backend_id": profile_id,
                "label": label,
            },
        )

    def record_recovery_imports() -> None:
        if recovery_imports and not (run_dir / "recovery-import.json").exists():
            recorder.json(
                "recovery-import.json",
                {
                    "contractVersion": (
                        "harness.catalyst-notebook.recovery-import.v1"
                    ),
                    "resumedFrom": (resume_header or {}).get("runId"),
                    "resumeAncestry": list(
                        (resume_header or {}).get("ancestry") or []
                    ),
                    "imports": recovery_imports,
                },
                kind="recovery_import_ledger",
            )

    def require_unchanged_recovery_source() -> None:
        for source, expected_sha256 in recovery_source_hashes.items():
            if _run_tree_sha256(source) == expected_sha256:
                continue
            status.update(
                {
                    "state": "invalid",
                    "reason": "an interrupted source changed during recovery",
                }
            )
            _write_run_status(run_dir, status)
            raise ValueError("an interrupted source changed during recovery")

    def finish_incomplete(
        interruption: _CollectionInterrupted,
        *,
        phase: str,
        profile_id: str | None = None,
        scenario: NotebookScenario | None = None,
        repetition: int | None = None,
        attempt: str | None = None,
        evidence_prefix: str | None = None,
    ) -> NotebookRunResult:
        http_status = (
            interruption.exchange.status_code
            if interruption.exchange is not None
            else None
        )
        failure: dict[str, Any] = {
            "runId": run_id,
            "phase": phase,
            "status": "infrastructure_failed",
            "evidencePath": interruption.evidence_path,
        }
        if http_status is not None:
            failure["httpStatus"] = http_status
        recorded_failure = interruption.recorded_failure
        interruption_kind = interruption.interruption_kind
        interruption_code = interruption.interruption_code
        if recorded_failure is not None:
            stage = recorded_failure.get("stage")
            code = recorded_failure.get("code")
            if stage is not None:
                failure["failureStage"] = stage
            if code is not None:
                failure["failureCode"] = code
        if interruption_kind is not None:
            failure["interruptionKind"] = interruption_kind
        if interruption_code is not None:
            failure["interruptionCode"] = interruption_code
        for key, value in (
            ("profileId", profile_id),
            ("scenarioId", scenario.id if scenario is not None else None),
            ("repetition", repetition),
            ("attempt", attempt),
            ("evidencePrefix", evidence_prefix),
        ):
            if value is not None:
                failure[key] = value
        infrastructure_failures.append(failure)
        append_jsonl(run_dir / "interruptions.jsonl", failure)
        recorder.file(
            "interruptions.jsonl",
            kind="collection_interruptions",
            media_type="application/x-ndjson",
            replace=True,
        )

        if scenario is not None and repetition is not None and profile_id is not None:
            row = {
                "scenarioId": scenario.id,
                "family": scenario.family,
                "repetition": repetition,
                "status": "infrastructure_failed",
                "sessionId": None,
                "assertions": [],
                "passed": False,
                "profileId": profile_id,
                "httpStatus": http_status,
                "evidencePrefix": evidence_prefix,
                "interruptionEvidencePath": interruption.evidence_path,
                "measurementValid": False,
            }
            if recorded_failure is not None:
                stage = recorded_failure.get("stage")
                code = recorded_failure.get("code")
                if stage is not None:
                    row["failureStage"] = stage
                if code is not None:
                    row["failureCode"] = code
            if interruption_kind is not None:
                row["interruptionKind"] = interruption_kind
            if interruption_code is not None:
                row["interruptionCode"] = interruption_code
            append_jsonl(run_dir / "rows.jsonl", row)
            recorder.file(
                "rows.jsonl",
                kind="measurement_rows",
                media_type="application/x-ndjson",
                replace=True,
            )
            results.append(row)

        record_recovery_imports()
        require_unchanged_recovery_source()
        _index_run_streams(recorder)
        recorder.finish()
        passed_count = sum(
            item.get("passed") is True
            and item.get("status") not in {"skipped", "infrastructure_failed"}
            for item in results
        )
        result_count = sum(
            item.get("status") not in {"skipped", "infrastructure_failed"}
            for item in results
        )
        status.update(
            {
                "state": "incomplete",
                "measurementValid": False,
                "reason": "collection stopped after "
                + (
                    "recorded "
                    + ":".join(
                        str(value)
                        for value in (
                            recorded_failure.get("stage"),
                            recorded_failure.get("code"),
                        )
                        if value
                    )
                    if recorded_failure is not None
                    else (
                        ":".join(
                            str(value)
                            for value in (interruption_kind, interruption_code)
                            if value
                        )
                        if interruption_kind is not None
                        else f"HTTP {http_status}"
                    )
                )
                + f" during {phase}; resume explicitly when the environment is ready",
                "resultCount": result_count,
                "passedCount": passed_count,
                "infrastructureFailures": infrastructure_failures,
            }
        )
        _write_run_status(run_dir, status)
        return NotebookRunResult(
            run_id=run_id,
            run_dir=run_dir,
            result_count=result_count,
            passed_count=passed_count,
            skipped_count=skipped,
            complete=False,
            measurement_valid=False,
        )

    try:
        profiles_exchange = client.profiles()
        recorder.exchange(
            "discovery/query-options.json",
            profiles_exchange,
            kind="profile_discovery",
        )
        dataset_exchange = client.dataset_overview()
        dataset = recorder.exchange(
            "discovery/dataset.json", dataset_exchange, kind="dataset_discovery"
        )
        catalog_exchange = client.catalog()
        catalog = recorder.exchange(
            "discovery/catalog.json", catalog_exchange, kind="catalog_discovery"
        )
    except _CollectionInterrupted as interruption:
        return finish_incomplete(
            interruption,
            phase="discovery",
            evidence_prefix="discovery",
        )
    _require_discovery(suite, profiles_exchange, dataset_exchange, catalog_exchange)
    finished_sources = [
        (source, _finished_pairs(source)) for source in recovery_chain
    ]
    direct_finished = finished_sources[0][1] if finished_sources else {}
    if resume_path is not None and resume_header is not None:
        _validate_recovery_identity(
            resume_from=resume_path,
            header=resume_header,
            frozen_config=public_config,
            suite_sha256=suite_sha256,
            manifest=manifest,
            profiles=profiles_exchange.response_body,
            dataset=dataset_exchange.response_body,
            catalog=catalog_exchange.response_body,
            allow_incomplete_source_discovery=not bool(direct_finished),
        )

    # A comparison is hours of model time, so an interruption resumes rather
    # than restarts: every (team, scenario) already recorded is reused
    # verbatim and only the missing pairs are run again.
    teams: tuple[str | None, ...] = suite.comparison_profiles or (None,)
    reusable: dict[tuple[str, str], tuple[Path, list[dict[str, Any]]]] = {}
    reusable_evidence: dict[Path, list[tuple[str, list[dict[str, Any]]]]] = {}
    recovery_warmups: dict[Path, set[str]] = {}
    for team in teams:
        for declared_scenario in selected:
            scenario = (
                _scenario_for_profile(declared_scenario, team)
                if team is not None
                else declared_scenario
            )
            key = (team or scenario.followup_profile_id, scenario.id)
            for source, finished in finished_sources:
                recorded = finished.get(key)
                if recorded is None or not _pair_is_complete(
                    recorded, suite, scenario, repetitions
                ):
                    continue
                reusable[key] = (source, recorded)
                expected_prefix = (
                    f"scenarios/{scenario.id}/"
                    if team is None
                    else f"scenarios/{team}/{scenario.id}/"
                )
                reusable_evidence.setdefault(source, []).append(
                    (expected_prefix, recorded)
                )
                if warmup_question and team is not None:
                    recovery_warmups.setdefault(source, set()).add(team)
                break
    preflight_digests: dict[Path, dict[str, str]] = {}
    for source, evidence in reusable_evidence.items():
        if source != resume_path:
            source_header = _load_resume_header(source)
            assert source_header is not None
            _validate_recovery_identity(
                resume_from=source,
                header=source_header,
                frozen_config=public_config,
                suite_sha256=suite_sha256,
                manifest=manifest,
                profiles=profiles_exchange.response_body,
                dataset=dataset_exchange.response_body,
                catalog=catalog_exchange.response_body,
            )
            recovery_source_hashes[source] = source_header["treeSha256"]
        preflight_digests[source] = _preflight_recovery_evidence(
            source,
            evidence,
            recovery_warmups.get(source),
        )
    for source, profile_ids in recovery_warmups.items():
        for profile_id in sorted(profile_ids):
            _adopt_recovery_warmup(
                recorder=recorder,
                source=source,
                profile_id=profile_id,
                imports=recovery_imports,
                preflight_digests=preflight_digests[source],
            )
    seen_sessions: set[str] = set()
    # Teams are the outer loop: a local model stays resident while it answers
    # the whole suite, and every team meets the same frozen scenario order.
    for team in teams:
        # Only a comparison declares one profile as a team across the whole
        # selected matrix. Legacy suites may choose a different profile in
        # each scenario and therefore have no single team-level warm-up.
        team_has_live_cells = any(
            not (scenario.manual_only and not include_manual)
            and (team or scenario.followup_profile_id, scenario.id) not in reusable
            for scenario in selected
        )
        if warmup_question and team is not None and team_has_live_cells:
            try:
                warmup_session_id = _record_warmup(
                    client=client,
                    recorder=recorder,
                    profile_id=team,
                    question=warmup_question,
                )
            except _CollectionInterrupted as interruption:
                return finish_incomplete(
                    interruption,
                    phase="warmup",
                    profile_id=team,
                    evidence_prefix=f"warmups/{team}",
                )
            seen_sessions.add(warmup_session_id)
        for scenario in selected:
            if team is not None:
                scenario = _scenario_for_profile(scenario, team)
            profile_id = team or scenario.followup_profile_id
            recovered = reusable.get(
                (profile_id, scenario.id)
            )
            if recovered is not None:
                source, recorded = recovered
                results.extend(recorded)
                _adopt_reused_pair(
                    recorder=recorder,
                    resume_from=source,
                    run_id=run_id,
                    scenario=scenario,
                    team=team,
                    recorded=recorded,
                    results_path=results_path,
                    events_path=events_path,
                    imports=recovery_imports,
                    preflight_digests=preflight_digests[source],
                )
                continue
            if scenario.manual_only and not include_manual:
                skipped += 1
                results.append(
                    {
                        "scenarioId": scenario.id,
                        "family": scenario.family,
                        "profileId": team or scenario.followup_profile_id,
                        "status": "skipped",
                        "reason": "manual-only bounded failure scenario was not enabled",
                    }
                )
                continue
            repeat_count = _effective_repetitions(suite, scenario, repetitions)
            # Compatibility for older notebook suites that explicitly declare
            # an adaptive within-cell extension. Phase 1 comparison suites
            # reject that shape and repeat only as complete new runs.
            ceiling = (
                repeat_count
                if repetitions is not None or suite.extended_repetitions is None
                else max(repeat_count, suite.extended_repetitions)
            )
            scenario_runs: list[dict[str, Any]] = []
            repetition = 0
            while repetition < repeat_count:
                repetition += 1
                attempt_slot = f"repetition-{repetition:02d}"
                prefix = (
                    f"scenarios/{scenario.id}/{attempt_slot}"
                    if team is None
                    else f"scenarios/{team}/{scenario.id}/{attempt_slot}"
                )
                started_at = datetime.now(timezone.utc).isoformat()
                try:
                    result = _run_scenario(
                        suite=suite,
                        scenario=scenario,
                        repetition=repetition,
                        client=client,
                        recorder=recorder,
                        prefix=prefix,
                        postgres_checker=postgres_checker,
                        gold_checker=gold_checker,
                        manual_checkpoint=manual_checkpoint,
                    )
                except _CollectionInterrupted as interruption:
                    return finish_incomplete(
                        interruption,
                        phase="scenario",
                        profile_id=profile_id,
                        scenario=scenario,
                        repetition=repetition,
                        attempt=attempt_slot,
                        evidence_prefix=prefix,
                    )
                session_id = result.get("sessionId")
                isolated = isinstance(session_id, str) and session_id not in seen_sessions
                if isinstance(session_id, str):
                    seen_sessions.add(session_id)
                result["assertions"].append(
                    {
                        "name": "new_session_isolation",
                        "class": assertion_class("new_session_isolation"),
                        "passed": isolated,
                        "evidence": session_id,
                    }
                )
                result["passed"] = all(item["passed"] for item in result["assertions"])
                result["profileId"] = profile_id
                result["httpStatus"] = _normalized_http_status(run_dir, prefix)
                result["evidencePrefix"] = prefix
                result["measurementEvidence"] = _measurement_evidence(
                    run_dir=run_dir,
                    prefix=prefix,
                    scenario=scenario,
                    result=result,
                )
                result["measurementValid"] = _row_is_measurement_valid(result)
                ended_at = datetime.now(timezone.utc).isoformat()
                result["startedAt"] = started_at
                result["endedAt"] = ended_at
                # Appended only after its final classification: this is what a
                # recovery run may import if the process stops before summary.
                append_jsonl(run_dir / "rows.jsonl", result)
                recorder.file(
                    "rows.jsonl",
                    kind="measurement_rows",
                    media_type="application/x-ndjson",
                    replace=True,
                )
                results.append(result)
                scenario_runs.append(result)
                backend_id = scenario.followup_profile_id
                _append_result_outputs(
                    run_dir=run_dir,
                    run_id=run_id,
                    scenario=scenario,
                    backend_id=backend_id,
                    result=result,
                    results_path=results_path,
                    events_path=events_path,
                    started_at=started_at,
                    ended_at=ended_at,
                )
                if (
                    repetition == repeat_count
                    and repeat_count < ceiling
                    and repetition_pair_is_unstable(scenario_runs)
                ):
                    repeat_count = ceiling

    record_recovery_imports()
    require_unchanged_recovery_source()

    passed_count = sum(
        result.get("passed") is True
        and result.get("status") != "infrastructure_failed"
        for result in results
    )
    result_count = sum(
        result.get("status") not in {"skipped", "infrastructure_failed"}
        for result in results
    )
    measured = [
        result
        for result in results
        if result.get("status") not in {"skipped", "infrastructure_failed"}
    ]
    measurement_valid = bool(measured) and all(
        result.get("measurementValid") is True for result in measured
    )
    nondeterminism = _nondeterminism_summary(results)
    summary = {
        "contractVersion": "harness.catalyst-notebook.validation-run.v1",
        "runId": run_id,
        "suiteId": suite.id,
        "dataset": dataset,
        "catalogVersion": catalog.get("catalogVersion"),
        "resultCount": result_count,
        "passedCount": passed_count,
        "measurementValid": measurement_valid,
        "skippedCount": skipped,
        "infrastructureFailureCount": len(infrastructure_failures),
        "infrastructureFailures": infrastructure_failures,
        "nondeterminism": nondeterminism,
        "results": results,
    }
    recorder.json("results.json", summary, kind="validation_results")
    _index_run_streams(recorder)
    recorder.finish()
    status.update(
        {
            "state": "complete" if measurement_valid else "invalid",
            "measurementValid": measurement_valid,
            "resultCount": result_count,
            "passedCount": passed_count,
        }
    )
    if not measurement_valid:
        status["reason"] = "one or more conversations lacked complete contract evidence"
    _write_run_status(run_dir, status)
    return NotebookRunResult(
        run_id=run_id,
        run_dir=run_dir,
        result_count=result_count,
        passed_count=passed_count,
        skipped_count=skipped,
        complete=True,
        measurement_valid=measurement_valid,
    )


def _run_scenario(
    *,
    suite: NotebookSuite,
    scenario: NotebookScenario,
    repetition: int,
    client: NotebookTransport,
    recorder: _EvidenceRecorder,
    prefix: str,
    postgres_checker: PostgresChecker | None,
    gold_checker: GoldChecker | None,
    manual_checkpoint: Callable[[NotebookScenario, str], None] | None,
) -> dict[str, Any]:
    assertions: list[dict[str, Any]] = []

    def check(name: str, passed: bool, evidence: Any) -> None:
        assertions.append(
            {
                "name": name,
                "class": assertion_class(name),
                "passed": bool(passed),
                "evidence": evidence,
            }
        )

    def database_check(
        *,
        relative_path: str,
        operation: str,
        kind: str,
        call: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            result = call()
        except Exception as error:
            if not _database_service_interruption(error):
                raise
            recorder.json(
                relative_path,
                {
                    "contractVersion": (
                        "harness.catalyst-notebook.service-interruption.v1"
                    ),
                    "service": "postgresql",
                    "operation": operation,
                    "exceptionType": type(error).__name__,
                },
                kind="service_interruption",
            )
            raise _CollectionInterrupted(
                relative_path,
                None,
                interruption_kind="database_availability",
                interruption_code="postgres_unavailable",
            ) from error
        recorder.json(relative_path, result, kind=kind)
        return result

    create = client.create_session(
        scenario.initial_question, scenario.initial_profile_id
    )
    session = recorder.exchange(
        f"{prefix}/01-create-session.json", create, kind="session_create"
    )
    if _profile_availability_drift(create):
        raise _CollectionInterrupted(
            f"{prefix}/01-create-session.json",
            create,
            interruption_kind="profile_availability",
            interruption_code="profile_unavailable",
        )
    check("session_created", create.status_code == 201, create.status_code)
    if create.status_code != 201 or not isinstance(session.get("sessionId"), str):
        return {
            "scenarioId": scenario.id,
            "family": scenario.family,
            "repetition": repetition,
            "status": "failed_before_turn",
            "sessionId": session.get("sessionId"),
            "assertions": assertions,
            "passed": False,
        }
    session_id = str(session["sessionId"])
    current = session.get("currentVersion")

    initial_timeline_exchange = client.get_turns(session_id)
    initial_timeline = recorder.exchange(
        f"{prefix}/02-initial-turns.json",
        initial_timeline_exchange,
        kind="turn_timeline",
    )
    initial_turn = next(
        (
            item
            for item in initial_timeline.get("turns", [])
            if item.get("kind") == "initial"
        ),
        None,
    )
    check("initial_turn_recorded", isinstance(initial_turn, dict), initial_turn)
    initial_interruption = (
        _persisted_service_interruption(initial_turn)
        if isinstance(initial_turn, dict)
        else None
    )
    base_failure_message = (
        str((initial_turn.get("failure") or {}).get("message") or "")
        if isinstance(initial_turn, dict)
        else ""
    )
    initial_evidence: dict[str, Any] = {}
    if isinstance(initial_turn, dict):
        evidence_exchange = client.generation_evidence(
            session_id, str(initial_turn["turnId"])
        )
        try:
            initial_evidence = recorder.exchange(
                f"{prefix}/03-initial-generation-evidence.json",
                evidence_exchange,
                kind="generation_evidence",
            )
        except _CollectionInterrupted as later:
            raise _carry_recorded_failure(later, initial_interruption) from later
        check(
            "initial_evidence_available",
            evidence_exchange.status_code == 200,
            evidence_exchange.status_code,
        )
        for name, passed, detail in _evidence_checks(
            initial_evidence,
            expected_profile=suite.profiles[scenario.initial_profile_id],
        ):
            check(f"{name}-base", passed, detail)
        # The opening generation is a scored turn like any other -- for a
        # base-only scenario it is the only one -- so its token accounting is
        # asserted here, not just inside the follow-up loop.
        for name, passed, detail in token_evidence_checks(initial_evidence):
            if name == "token_evidence_recorded" and not passed:
                if suite.require_token_evidence:
                    check(f"{name}-base", False, detail)
                else:
                    assertions.append(
                        {
                            "name": f"{name}-base",
                            "class": assertion_class(name),
                            "passed": True,
                            "evidence": {"recorded": False, "required": False},
                        }
                    )
                continue
            check(f"{name}-base", passed, detail)

    if initial_interruption is not None:
        raise _CollectionInterrupted(
            f"{prefix}/02-initial-turns.json",
            initial_timeline_exchange,
            recorded_failure=initial_interruption,
        )

    # What the writer answered the opening question with, before anything is
    # done to the session: a query, a question, or a refusal.
    observed_base_outcome = (
        writer_outcome(initial_turn) if isinstance(initial_turn, dict) else "rejected"
    )
    check(
        "base_writer_outcome",
        observed_base_outcome == scenario.expected_base_outcome,
        {
            "observed": observed_base_outcome,
            "expected": scenario.expected_base_outcome,
        },
    )
    if observed_base_outcome in TERMINAL_WRITER_OUTCOMES:
        # A question or a refusal is one writer call and no SQL. There is
        # nothing to validate, execute or check an answer against, and the
        # session must be holding no query at all.
        #
        # Keyed on what the writer actually answered, not on what the
        # scenario hoped for: a writer that answers `ready` is supposed to
        # leave its query in the session, so asking this of it would fail a
        # contract check for a judgment the outcome check already made.
        check(
            "no_sql_after_non_ready_base",
            not session.get("versions") and session.get("currentVersionId") is None,
            {
                "versions": session.get("versions"),
                "currentVersionId": session.get("currentVersionId"),
            },
        )
    if scenario.expected_base_outcome in TERMINAL_WRITER_OUTCOMES:
        if scenario.validate_base or scenario.execute_base:
            raise ValueError(
                f"scenario {scenario.id!r} expects no query from its opening "
                "question, so it cannot validate or execute one"
            )

    if scenario.persist_editor_query:
        if scenario.editor_query is None:
            raise ValueError(
                f"scenario {scenario.id!r} persists an absent editor query"
            )
        saved_exchange = client.save_version(
            session_id,
            scenario.editor_query,
            current if isinstance(current, dict) else None,
        )
        session = recorder.exchange(
            f"{prefix}/04-save-base-version.json",
            saved_exchange,
            kind="query_version_create",
        )
        check(
            "base_version_saved",
            saved_exchange.status_code == 201,
            saved_exchange.status_code,
        )
        current = session.get("currentVersion")

    base_version = current if isinstance(current, dict) else None
    # The opening query, captured before any turn moves the session head:
    # `base_version` is reassigned as turns land, so reading it at the end
    # reported the final query where the first belongs.
    opening_sql = (base_version or {}).get("sql")
    opening_version_id = (base_version or {}).get("versionId")
    opening_query_digest = (base_version or {}).get("queryDigest")
    if base_version is None and scenario.expected_base_outcome not in (
        TERMINAL_WRITER_OUTCOMES
    ):
        # A writer may answer with a complete question or refusal where the
        # suite expected SQL. That is a wrong answer, not a broken collection:
        # record it and end this conversation without attempting refinements
        # that require a query to exist.
        if observed_base_outcome in TERMINAL_WRITER_OUTCOMES:
            return {
                "scenarioId": scenario.id,
                "family": scenario.family,
                "repetition": repetition,
                "status": initial_turn.get("status", "failed"),
                "baseOutcome": observed_base_outcome,
                "expectedBaseOutcome": scenario.expected_base_outcome,
                "baseAnswerText": base_failure_message or None,
                "baseSql": None,
                "sessionId": session_id,
                "initialTurnId": initial_turn.get("turnId"),
                "turns": [],
                "baseOutcomeEndedConversation": True,
                "assertions": assertions,
                "passed": False,
            }
        check("base_version_available", False, None)
        return {
            "scenarioId": scenario.id,
            "family": scenario.family,
            "repetition": repetition,
            "status": "failed_before_turn",
            "sessionId": session_id,
            "assertions": assertions,
            "passed": False,
        }
    if base_version is not None:
        check("base_version_available", True, base_version.get("versionId"))

    if scenario.validate_base:
        validated = client.validate_version(str(base_version["versionId"]))
        recorder.exchange(
            f"{prefix}/05-validate-base.json",
            validated,
            kind="query_validation",
        )
        check(
            "base_validation_recorded",
            validated.status_code == 201,
            validated.status_code,
        )

    base_execution: dict[str, Any] | None = None
    base_execution_wall_ms = 0
    if scenario.execute_base:
        executed = client.execute_version(base_version)
        base_execution_wall_ms = executed.elapsed_ms
        base_execution = recorder.exchange(
            f"{prefix}/06-execute-base.json", executed, kind="query_execution"
        )
        check(
            "base_execution_succeeded",
            executed.status_code == 200 and base_execution.get("status") == "succeeded",
            {
                "httpStatus": executed.status_code,
                "status": base_execution.get("status"),
            },
        )
        if (
            postgres_checker is not None
            and executed.status_code == 200
            and base_execution.get("status") == "succeeded"
        ):
            crosscheck = database_check(
                relative_path=f"{prefix}/07-postgres-base.json",
                operation="base_postgres_crosscheck",
                kind="postgres_crosscheck",
                call=lambda: postgres_checker.check(base_version, base_execution),
            )
            check("base_postgres_crosscheck", crosscheck["passed"], crosscheck)
        if (
            gold_checker is not None
            and scenario.base_gold_check is not None
            and executed.status_code == 200
            and base_execution.get("status") == "succeeded"
        ):
            gold_result = database_check(
                relative_path=f"{prefix}/15-gold-execution-match-base.json",
                operation="base_gold_execution_match",
                kind="gold_execution_match",
                call=lambda: gold_checker.check(
                    base_version, scenario.base_gold_check
                ),
            )
            check("base_gold_execution_match", gold_result["passed"], gold_result)

    for pin_index, guidance_text in enumerate(scenario.pin_guidance, start=1):
        pin_exchange = client.pin_guidance(session_id, guidance_text)
        pinned_session = recorder.exchange(
            f"{prefix}/04-pin-guidance-{pin_index:02d}.json",
            pin_exchange,
            kind="guidance_pin",
        )
        listed = [
            entry.get("text")
            for entry in pinned_session.get("guidance") or []
        ]
        check(
            "guidance_pinned",
            pin_exchange.status_code == 201 and guidance_text in listed,
            {"httpStatus": pin_exchange.status_code, "guidance": listed},
        )

    # Each declared turn runs against the query the previous turn left current.
    # Turn 1 keeps the original evidence filenames and assertion names so every
    # suite recorded before multi-turn scenarios replays byte-for-byte.
    turn_summaries: list[dict[str, Any]] = []
    # A scenario scored on its opening question alone never enters the
    # loop, so everything the summary reads from a turn is stated here
    # as the absence it actually is.
    turn: dict[str, Any] = {}
    followup: HttpExchange | None = None
    followup_evidence: dict[str, Any] = {}
    selected: dict[str, Any] | None = None
    successor_execution: dict[str, Any] | None = None
    successor_execution_wall_ms = 0
    scenario_check = check
    prior_execution = base_execution
    latest_execution = base_execution
    followup_candidate_digest_sequences: list[list[str]] = []
    followup_evidence_digests: list[str | None] = []
    followup_selected_query_digests: list[str | None] = []
    successor_execution_ids: list[str] = []
    turn_timing_summaries: list[dict[str, Any]] = []
    for turn_index, turn_spec in enumerate(scenario.turns, start=1):
        slot = "" if turn_index == 1 else f"-t{turn_index}"
        turn_gold_check = turn_spec.gold_check or scenario.successor_gold_check

        def check(name: str, passed: bool, evidence: Any, _slot: str = slot) -> None:
            assertions.append(
                {
                    "name": f"{name}{_slot}",
                    "class": assertion_class(name),
                    "passed": bool(passed),
                    "evidence": evidence,
                }
            )

        pinned = scenario.editor_query if turn_index == 1 else None
        # Answering the writer's question revises nothing: the session holds
        # no query, so the turn claims neither an editor nor a base.
        editor_query = pinned or (
            NotebookQuery(
                sql=str(base_version["sql"]),
                parameters=tuple(
                    dict(item) for item in base_version.get("parameters", [])
                ),
                expected_columns=tuple(
                    dict(item) for item in base_version.get("expectedColumns", [])
                ),
            )
            if base_version is not None
            else None
        )
        snapshot = (
            {
                "contractVersion": "catalyst.workbench.editor-snapshot.v1",
                **editor_query.content(),
                "editorDigest": query_digest(editor_query),
            }
            if editor_query is not None
            else None
        )
        observed_base = (
            {
                "versionId": str(base_version["versionId"]),
                "queryDigest": str(base_version["queryDigest"]),
            }
            if base_version is not None
            else None
        )
        if scenario.manual_only:
            if manual_checkpoint is None:
                raise ValueError(
                    f"scenario {scenario.id!r} requires an operator checkpoint"
                )
            manual_checkpoint(scenario, session_id)
        followup = client.create_turn(
            session_id,
            instruction=turn_spec.instruction,
            profile_id=turn_spec.profile_id,
            observed_base=observed_base,
            editor_snapshot=snapshot,
        )
        turn = recorder.exchange(
            f"{prefix}/08-create-followup{slot}.json", followup, kind="turn_create"
        )
        if _profile_availability_drift(followup):
            raise _CollectionInterrupted(
                f"{prefix}/08-create-followup{slot}.json",
                followup,
                interruption_kind="profile_availability",
                interruption_code="profile_unavailable",
            )
        followup_interruption = _persisted_service_interruption(turn)
        check("followup_http_created", followup.status_code == 201, followup.status_code)
        check(
            "followup_terminal_status",
            turn.get("status") == turn_spec.expected_turn_status,
            turn.get("status"),
        )
        observed_outcome = writer_outcome(turn)
        check(
            "writer_outcome",
            observed_outcome == turn_spec.expected_outcome,
            {"observed": observed_outcome, "expected": turn_spec.expected_outcome},
        )
        if observed_outcome in TERMINAL_WRITER_OUTCOMES:
            # A question or a refusal is one writer call and no SQL: the prior
            # selected query has to survive it untouched. Keyed on the answer
            # actually given, for the reason spelled out at the base check.
            check(
                "no_sql_after_non_ready_outcome",
                not turn.get("outputVersions") and turn.get("selectedVersionId") is None,
                {
                    "outputVersions": turn.get("outputVersions"),
                    "selectedVersionId": turn.get("selectedVersionId"),
                },
            )
        check(
            "base_classification",
            turn.get("snapshotClassification") == scenario.expected_base_classification,
            turn.get("snapshotClassification"),
        )
        manual_version = turn.get("manualVersion")
        check(
            "manual_version_classification",
            (manual_version is not None)
            is (scenario.expected_base_classification == "promoted_human"),
            manual_version,
        )
        check(
            "followup_profile",
            turn.get("profileSnapshot", {}).get("profileId")
            == turn_spec.profile_id,
            turn.get("profileSnapshot", {}).get("profileId"),
        )

        refreshed_exchange = client.get_session(session_id)
        try:
            refreshed = recorder.exchange(
                f"{prefix}/09-refreshed-session{slot}.json",
                refreshed_exchange,
                kind="session_restore",
            )
        except _CollectionInterrupted as later:
            raise _carry_recorded_failure(later, followup_interruption) from later
        timeline_exchange = client.get_turns(session_id)
        try:
            timeline = recorder.exchange(
                f"{prefix}/10-final-turns{slot}.json",
                timeline_exchange,
                kind="turn_timeline",
            )
        except _CollectionInterrupted as later:
            raise _carry_recorded_failure(later, followup_interruption) from later
        check(
            "refresh_restored",
            refreshed_exchange.status_code == 200,
            refreshed_exchange.status_code,
        )
        check(
            "timeline_current_turn",
            timeline.get("currentTurnId") == turn.get("turnId"),
            timeline.get("currentTurnId"),
        )

        followup_evidence: dict[str, Any] = {}
        if isinstance(turn.get("turnId"), str):
            evidence_exchange = client.generation_evidence(session_id, turn["turnId"])
            try:
                followup_evidence = recorder.exchange(
                    f"{prefix}/11-followup-generation-evidence{slot}.json",
                    evidence_exchange,
                    kind="generation_evidence",
                )
            except _CollectionInterrupted as later:
                raise _carry_recorded_failure(later, followup_interruption) from later
            check(
                "followup_evidence_available",
                evidence_exchange.status_code == 200,
                evidence_exchange.status_code,
            )
            evidence_checks = _evidence_checks(
                followup_evidence,
                expected_profile=suite.profiles[turn_spec.profile_id],
            )
            for name, passed, evidence in evidence_checks:
                check(name, passed, evidence)
            for name, passed, detail in token_evidence_checks(followup_evidence):
                # Recorded either way; only a suite that requires the
                # accounting fails the turn for its absence.
                if name == "token_evidence_recorded" and not passed:
                    if suite.require_token_evidence:
                        check(name, False, detail)
                    else:
                        assertions.append(
                            {
                                "name": f"{name}{slot}",
                                "class": assertion_class(name),
                                "passed": True,
                                "evidence": {"recorded": False, "required": False},
                            }
                        )
                    continue
                check(name, passed, detail)

        expected_manual_transport = (
            followup_interruption is not None
            and followup_interruption.get("stage") in MODEL_TRANSPORT_STAGES
            and scenario.manual_only
            and scenario.family == "hub-tool-failure"
            and turn_spec.expected_turn_status == "failed"
        )
        if followup_interruption is not None and not expected_manual_transport:
            raise _CollectionInterrupted(
                f"{prefix}/08-create-followup{slot}.json",
                followup,
                recorded_failure=followup_interruption,
            )

        selected = None
        if turn_spec.expected_turn_status == "completed":
            outputs = list(turn.get("outputVersions") or [])
            selected_outputs = [item for item in outputs if item.get("selected") is True]
            if len(selected_outputs) == 1:
                selected = refreshed.get("currentVersion")
            exact_selection = (
                len(selected_outputs) == 1
                and turn.get("selectedVersionId") == selected_outputs[0].get("versionId")
                and turn.get("resultingCurrentVersion", {}).get("versionId")
                == selected_outputs[0].get("versionId")
                and refreshed.get("currentVersionId")
                == selected_outputs[0].get("versionId")
            )
            check("exact_selected_output", exact_selection, selected_outputs)
            reviewer_corrected = bool(
                selected_outputs and selected_outputs[0].get("role") == "reviewer"
            )
            check(
                "semantic_reviewer_correction",
                reviewer_corrected or not scenario.require_reviewer_correction,
                {
                    "observed": reviewer_corrected,
                    "required": scenario.require_reviewer_correction,
                },
            )
            if prior_execution is not None:
                check(
                    "prior_results_stale_after_successor",
                    refreshed.get("currentVersionId") != base_version.get("versionId")
                    and any(
                        item.get("versionId") == base_version.get("versionId")
                        for item in refreshed.get("executions", [])
                    ),
                    {
                        "baseVersionId": base_version.get("versionId"),
                        "currentVersionId": refreshed.get("currentVersionId"),
                    },
                )
        else:
            check(
                "failed_turn_preserved_base",
                turn.get("selectedVersionId") is None
                and refreshed.get("currentVersionId")
                == turn.get("resultingCurrentVersion", {}).get("versionId"),
                {
                    "failure": turn.get("failure"),
                    "currentVersionId": refreshed.get("currentVersionId"),
                },
            )

        successor_execution: dict[str, Any] | None = None
        successor_execution_wall_ms = 0
        if isinstance(selected, dict) and scenario.validate_successor:
            validated = client.validate_version(str(selected["versionId"]))
            recorder.exchange(
                f"{prefix}/12-validate-successor{slot}.json",
                validated,
                kind="query_validation",
            )
            check(
                "successor_validation_recorded",
                validated.status_code == 201,
                validated.status_code,
            )
        if isinstance(selected, dict) and scenario.execute_successor:
            executed = client.execute_version(selected)
            successor_execution_wall_ms = executed.elapsed_ms
            successor_execution = recorder.exchange(
                f"{prefix}/13-execute-successor{slot}.json",
                executed,
                kind="query_execution",
            )
            check(
                "successor_execution_succeeded",
                executed.status_code == 200
                and successor_execution.get("status") == "succeeded",
                {
                    "httpStatus": executed.status_code,
                    "status": successor_execution.get("status"),
                    "diagnostic": successor_execution.get("databaseDiagnostic"),
                },
            )
            if (
                postgres_checker is not None
                and executed.status_code == 200
                and successor_execution.get("status") == "succeeded"
            ):
                crosscheck = database_check(
                    relative_path=f"{prefix}/14-postgres-successor{slot}.json",
                    operation="successor_postgres_crosscheck",
                    kind="postgres_crosscheck",
                    call=lambda: postgres_checker.check(
                        selected, successor_execution
                    ),
                )
                check("successor_postgres_crosscheck", crosscheck["passed"], crosscheck)
            if (
                gold_checker is not None
                and turn_gold_check is not None
                and executed.status_code == 200
                and successor_execution.get("status") == "succeeded"
            ):
                gold_result = database_check(
                    relative_path=(
                        f"{prefix}/16-gold-execution-match-successor{slot}.json"
                    ),
                    operation="successor_gold_execution_match",
                    kind="gold_execution_match",
                    call=lambda: gold_checker.check(selected, turn_gold_check),
                )
                check("successor_gold_execution_match", gold_result["passed"], gold_result)

        turn_candidate_digests = [
            str(item["candidateDigest"])
            for item in followup_evidence.get("candidates", [])
            if item.get("candidateDigest") is not None
        ]
        turn_evidence_digest = followup_evidence.get("evidenceDigest")
        turn_selected_query_digest = (
            selected.get("queryDigest") if isinstance(selected, dict) else None
        )
        turn_execution_id = (
            successor_execution.get("executionId")
            if isinstance(successor_execution, dict)
            else None
        )
        turn_invocation_ms = int(
            followup_evidence.get("totalInvocationDurationMs") or 0
        )
        turn_timing = {
            "turnIndex": turn_index,
            "generationWallMs": followup.elapsed_ms,
            "recordedInvocationDurationMs": turn_invocation_ms,
            "generationWallMinusRecordedInvocationsMs": (
                followup.elapsed_ms - turn_invocation_ms
            ),
            "executionWallMs": successor_execution_wall_ms,
        }
        followup_candidate_digest_sequences.append(turn_candidate_digests)
        followup_evidence_digests.append(
            str(turn_evidence_digest)
            if isinstance(turn_evidence_digest, str)
            else None
        )
        followup_selected_query_digests.append(
            str(turn_selected_query_digest)
            if isinstance(turn_selected_query_digest, str)
            else None
        )
        if isinstance(turn_execution_id, str):
            successor_execution_ids.append(turn_execution_id)
        turn_timing_summaries.append(turn_timing)

        turn_summaries.append(
            {
                "turnIndex": turn_index,
                "turnId": turn.get("turnId"),
                "instruction": turn_spec.instruction,
                "profileId": turn_spec.profile_id,
                "status": turn.get("status"),
                "expectedOutcome": turn_spec.expected_outcome,
                "observedOutcome": observed_outcome,
                # What the writer said this turn, in its own two currencies:
                # the words of a question or refusal, and the SQL the session
                # holds after the turn. A reader following the conversation
                # needs both, in place.
                "answerText": (
                    str((turn.get("failure") or {}).get("message") or "") or None
                ),
                "sql": (
                    str((refreshed.get("currentVersion") or {}).get("sql") or "")
                    or None
                )
                if turn.get("selectedVersionId")
                else None,
                "retainedSql": (
                    str((refreshed.get("currentVersion") or {}).get("sql") or "")
                    or None
                )
                if not turn.get("selectedVersionId")
                else None,
                "selectedVersionId": turn.get("selectedVersionId"),
                "selectedQueryDigest": turn_selected_query_digest,
                "executionId": turn_execution_id,
                "candidateDigests": turn_candidate_digests,
                "evidenceDigest": turn_evidence_digest,
                "timing": turn_timing,
            }
        )
        # The next turn starts from whatever this one left current, which is
        # the unchanged prior query when the writer asked or refused.
        current_version = refreshed.get("currentVersion")
        if isinstance(current_version, dict) and current_version.get("versionId"):
            base_version = current_version
        prior_execution = successor_execution or prior_execution
        latest_execution = successor_execution or latest_execution

    invocation_ms = int(initial_evidence.get("totalInvocationDurationMs") or 0) + sum(
        int(item["recordedInvocationDurationMs"])
        for item in turn_timing_summaries
    )
    followup_wall_ms = sum(
        int(item["generationWallMs"]) for item in turn_timing_summaries
    )
    successor_execution_wall_ms = sum(
        int(item["executionWallMs"]) for item in turn_timing_summaries
    )
    generation_wall_ms = create.elapsed_ms + followup_wall_ms
    timing = {
        "initialGenerationWallMs": create.elapsed_ms,
        "followupGenerationWallMs": followup_wall_ms,
        "unadjustedGenerationWallMs": generation_wall_ms,
        "recordedInvocationDurationMs": invocation_ms,
        "generationWallMinusRecordedInvocationsMs": generation_wall_ms - invocation_ms,
        "baseExecutionWallMs": base_execution_wall_ms,
        "successorExecutionWallMs": successor_execution_wall_ms,
        "followups": turn_timing_summaries,
    }
    scenario_check(
        "successor_visible_under_three_minutes",
        generation_wall_ms - invocation_ms < 180_000,
        timing,
    )

    return {
        "scenarioId": scenario.id,
        "family": scenario.family,
        "repetition": repetition,
        # With no turn to report on, the repetition's status is the
        # session's own: it ran to the end of what it declared.
        "status": turn.get("status") if scenario.turns else "completed",
        "baseOutcome": observed_base_outcome,
        "expectedBaseOutcome": scenario.expected_base_outcome,
        # For a question or a refusal these words ARE the answer under test.
        "baseAnswerText": base_failure_message or None,
        "baseSql": opening_sql,
        "resultPreview": _result_preview(latest_execution),
        "sessionId": session_id,
        "initialTurnId": initial_turn.get("turnId")
        if isinstance(initial_turn, dict)
        else None,
        "followupTurnId": turn.get("turnId"),
        "turns": turn_summaries,
        "baseVersionId": opening_version_id,
        "baseQueryDigest": opening_query_digest,
        "selectedVersionId": turn.get("selectedVersionId"),
        "baseExecutionId": (base_execution or {}).get("executionId"),
        "successorExecutionId": (successor_execution or {}).get("executionId"),
        "successorExecutionIds": successor_execution_ids,
        "initialCandidateDigests": [
            item.get("candidateDigest")
            for item in initial_evidence.get("candidates", [])
            if item.get("candidateDigest") is not None
        ],
        "followupCandidateDigests": [
            digest
            for sequence in followup_candidate_digest_sequences
            for digest in sequence
        ],
        "followupCandidateDigestSequences": followup_candidate_digest_sequences,
        "followupSelectedQueryDigests": followup_selected_query_digests,
        "selectedQueryDigest": (
            selected.get("queryDigest") if isinstance(selected, dict) else None
        ),
        "followupEvidenceDigest": (
            followup_evidence_digests[-1] if followup_evidence_digests else None
        ),
        "followupEvidenceDigests": followup_evidence_digests,
        "timing": timing,
        "assertions": assertions,
        "passed": all(item["passed"] for item in assertions),
    }


def _nondeterminism_summary(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenario_ids = sorted(
        {str(item["scenarioId"]) for item in results if item.get("status") != "skipped"}
    )
    summary: list[dict[str, Any]] = []
    for scenario_id in scenario_ids:
        repetitions = [
            item for item in results if item.get("scenarioId") == scenario_id
        ]
        candidate_sequences = [
            list(item.get("followupCandidateDigests") or []) for item in repetitions
        ]
        output_digests = sorted(
            {
                str(item["selectedQueryDigest"])
                for item in repetitions
                if item.get("selectedQueryDigest") is not None
            }
        )
        summary.append(
            {
                "scenarioId": scenario_id,
                "repetitions": len(repetitions),
                "candidateDigestSequences": candidate_sequences,
                "selectedQueryDigests": output_digests,
                "candidateDifferenceObserved": len(
                    {tuple(sequence) for sequence in candidate_sequences}
                )
                > 1,
                "selectedOutputDifferenceObserved": len(output_digests) > 1,
            }
        )
    return summary


def _require_discovery(
    suite: NotebookSuite,
    profiles_exchange: HttpExchange,
    dataset_exchange: HttpExchange,
    catalog_exchange: HttpExchange,
) -> None:
    for label, exchange in (
        ("profile", profiles_exchange),
        ("dataset", dataset_exchange),
        ("catalog", catalog_exchange),
    ):
        if exchange.status_code != 200:
            raise ValueError(f"{label} discovery returned HTTP {exchange.status_code}")
    advertised = {
        item.get("id"): item
        for item in profiles_exchange.response_body.get("profiles", [])
    }
    for profile_id, expected in suite.profiles.items():
        profile = advertised.get(profile_id)
        if not isinstance(profile, dict) or profile.get("available") is not True:
            raise ValueError(f"required profile {profile_id!r} is unavailable")
        if profile.get("revisionCapable") is not True:
            raise ValueError(f"required profile {profile_id!r} is not revision-capable")
        roles = profile.get("role_models") or profile.get("roleModels") or {}
        if roles.get("query_generate") != expected["writerModelId"]:
            raise ValueError(f"profile {profile_id!r} writer model drifted")
        if roles.get("query_review") != expected.get("reviewerModelId"):
            raise ValueError(f"profile {profile_id!r} reviewer model drifted")
        frozen_digest = expected.get("profileConfigurationDigest")
        if frozen_digest is not None:
            provenance = profile.get("provenance")
            advertised_digest = (
                provenance.get("profileConfigurationDigest")
                if isinstance(provenance, dict)
                else None
            )
            if not advertised_digest:
                raise ValueError(
                    f"profile {profile_id!r} does not advertise a profile digest "
                    "to compare with the frozen one"
                )
            if advertised_digest != frozen_digest:
                raise ValueError(f"profile {profile_id!r} profile digest drifted")
    dataset = dataset_exchange.response_body
    if dataset.get("contractVersion") != "catalyst.dataset-overview.v1":
        raise ValueError("runtime dataset overview contract is unsupported")
    runtime_dataset_id = dataset.get("datasetId")
    pipeline_run_id = dataset.get("pipelineRunId")
    if (
        not isinstance(runtime_dataset_id, str)
        or not runtime_dataset_id
        or runtime_dataset_id != pipeline_run_id
    ):
        raise ValueError("runtime dataset is not bound to its pipeline run")
    catalog_version = catalog_exchange.response_body.get("catalogVersion")
    if not isinstance(catalog_version, str) or not catalog_version.startswith(
        suite.catalog_version
    ):
        raise ValueError("runtime catalog does not derive from the notebook suite")


def _request_revision(invocation: dict[str, Any]) -> dict[str, Any] | None:
    exact = invocation.get("requestEvidence")
    request = exact.get("request") if isinstance(exact, dict) else None
    if not isinstance(request, dict):
        return None
    for message in request.get("messages") or []:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        try:
            payload = json.loads(content) if isinstance(content, str) else content
        except (TypeError, ValueError):
            continue
        revision = payload.get("revision") if isinstance(payload, dict) else None
        if isinstance(revision, dict):
            return revision
    return None


def _capacity_evidence_is_coherent(invocation: dict[str, Any]) -> bool:
    outcome = invocation.get("outcome")
    if outcome not in {"succeeded", "pre_dispatch_rejected"}:
        return True
    exact = invocation.get("requestEvidence")
    request = exact.get("request") if isinstance(exact, dict) else None
    tokens = exact.get("tokens") if isinstance(exact, dict) else None
    request_config = request.get("config") if isinstance(request, dict) else None
    invocation_config = invocation.get("configuration")
    if not all(
        isinstance(value, dict)
        for value in (tokens, request_config, invocation_config)
    ):
        return False

    context_window = tokens.get("contextWindow")
    output_reserve = tokens.get("outputReserve")
    prompt_tokens = tokens.get("promptTokens")
    required_tokens = tokens.get("requiredTokens")
    fits = tokens.get("fits")
    if not (
        isinstance(tokens.get("tokenizer"), str)
        and bool(tokens["tokenizer"])
        and tokens["tokenizer"] == invocation.get("modelId")
        and type(context_window) is int
        and context_window > 0
        and type(output_reserve) is int
        and output_reserve >= 0
        and type(prompt_tokens) is int
        and prompt_tokens >= 0
        and type(required_tokens) is int
        and required_tokens == prompt_tokens + output_reserve
        and type(fits) is bool
        and fits is (required_tokens <= context_window)
        and output_reserve == request_config.get("maxTokens")
        and output_reserve == invocation_config.get("maxTokens")
    ):
        return False

    if outcome == "succeeded":
        return fits and invocation.get("tokenAccounting") == {
            "tokenizer": tokens["tokenizer"],
            "contextWindow": context_window,
            "outputReserve": output_reserve,
            "promptTokens": prompt_tokens,
        }
    hub_error = invocation.get("hubError")
    return (
        not fits
        and isinstance(hub_error, dict)
        and hub_error.get("code") == "context_window_exceeded"
        and hub_error.get("httpStatus") == 422
    )


def _evidence_checks(
    evidence: dict[str, Any],
    *,
    expected_profile: dict[str, str | None],
) -> list[tuple[str, bool, Any]]:
    supplied_invocations = evidence.get("invocations")
    invocations = (
        list(supplied_invocations) if isinstance(supplied_invocations, list) else []
    )
    final_selection = evidence.get("finalSelection")
    terminal_failure = (
        final_selection.get("failure") if isinstance(final_selection, dict) else None
    )
    zero_invocation_answer = (
        isinstance(supplied_invocations, list)
        and not supplied_invocations
        and evidence.get("status") == "failed"
        and isinstance(terminal_failure, dict)
        and terminal_failure.get("code")
        in {"needs_clarification", "unsupported"}
    )
    duration_sum = sum(
        int(item.get("durationMs") or 0)
        for item in invocations
        if item.get("durationMs") is not None
    )
    terminal_digests = all(
        isinstance(item.get("requestDigest"), str)
        and len(item["requestDigest"]) == 64
        and (
            isinstance(item.get("responseDigest"), str)
            or isinstance(item.get("failureDigest"), str)
        )
        for item in invocations
        if item.get("outcome") != "in_progress"
    )
    timestamp_reconciliation: list[dict[str, Any]] = []
    for item in invocations:
        started = _parse_timestamp(item.get("startedAt"))
        ended = _parse_timestamp(item.get("endedAt"))
        duration = item.get("durationMs")
        if started is not None and ended is not None and duration is not None:
            wall_ms = round((ended - started).total_seconds() * 1000)
            timestamp_reconciliation.append(
                {
                    "invocationId": item.get("invocationId"),
                    "recordedDurationMs": duration,
                    "timestampDeltaMs": wall_ms,
                    "differenceMs": wall_ms - int(duration),
                }
            )
    role_models = {
        item.get("role"): item.get("modelId")
        for item in invocations
        if item.get("role") in {"writer", "reviewer"}
    }
    configurations = [item.get("configuration") or {} for item in invocations]
    config_ok = zero_invocation_answer or (
        bool(configurations)
        and all(
            item.get("temperature") == 0 and item.get("dryMultiplier") == 0
            for item in configurations
        )
    )
    forbidden = _find_forbidden_keys(evidence.get("revisionContext"))
    reviewer_model = role_models.get("reviewer")
    expected_reviewer_model = expected_profile.get("reviewerModelId")
    reviewer_not_reached_after_failure = (
        expected_reviewer_model is not None
        and evidence.get("status") == "failed"
        and reviewer_model is None
    )
    reviewer_matches_profile = (
        reviewer_model == expected_reviewer_model
        or reviewer_not_reached_after_failure
        or zero_invocation_answer
    )

    revision_context = evidence.get("revisionContext")
    followup_requires_context = evidence.get("turnKind") == "followup"
    revision_context_recorded = isinstance(revision_context, dict)
    request_evidence_detail = []
    digest_detail = []
    capacity_detail = []
    retained_context_detail = []
    for invocation in invocations:
        invocation_id = invocation.get("invocationId")
        role = invocation.get("role")
        exact = invocation.get("requestEvidence")
        request = exact.get("request") if isinstance(exact, dict) else None
        nested_digest = exact.get("requestDigest") if isinstance(exact, dict) else None
        recorded = (
            isinstance(exact, dict)
            and set(exact)
            == {"contractVersion", "request", "requestDigest", "prompt", "tokens"}
            and exact.get("contractVersion")
            == "med-agent-hub.catalyst-role-request-evidence.v1"
            and isinstance(request, dict)
            and isinstance(request.get("messages"), list)
            and len(request["messages"]) >= 2
            and isinstance(exact.get("prompt"), dict)
            and isinstance(exact.get("tokens"), dict)
        )
        request_evidence_detail.append(
            {"invocationId": invocation_id, "role": role, "recorded": recorded}
        )
        digest_match = (
            isinstance(nested_digest, str)
            and re.fullmatch(r"[a-f0-9]{64}", nested_digest) is not None
            and invocation.get("requestDigest") == nested_digest
        )
        digest_detail.append(
            {
                "invocationId": invocation_id,
                "invocationRequestDigest": invocation.get("requestDigest"),
                "requestEvidenceDigest": nested_digest,
                "matches": digest_match,
            }
        )
        capacity_coherent = _capacity_evidence_is_coherent(invocation)
        capacity_detail.append(
            {
                "invocationId": invocation_id,
                "outcome": invocation.get("outcome"),
                "coherent": capacity_coherent,
                "tokens": exact.get("tokens") if isinstance(exact, dict) else None,
            }
        )
        context_required = followup_requires_context or revision_context_recorded
        context_match = not context_required or (
            revision_context_recorded
            and _request_revision(invocation) == revision_context
        )
        retained_context_detail.append(
            {
                "invocationId": invocation_id,
                "required": context_required,
                "revisionContextRecorded": revision_context_recorded,
                "matches": context_match,
            }
        )

    request_evidence_ok = zero_invocation_answer or (
        bool(invocations)
        and len(request_evidence_detail) == len(invocations)
        and all(item["recorded"] for item in request_evidence_detail)
    )
    digest_matches = zero_invocation_answer or (
        bool(invocations)
        and len(digest_detail) == len(invocations)
        and all(item["matches"] for item in digest_detail)
    )
    capacity_coherent = zero_invocation_answer or (
        bool(invocations)
        and len(capacity_detail) == len(invocations)
        and all(item["coherent"] for item in capacity_detail)
    )
    retained_context = (
        not followup_requires_context or revision_context_recorded
    ) and (
        zero_invocation_answer
        or (
            bool(invocations)
            and len(retained_context_detail) == len(invocations)
            and all(item["matches"] for item in retained_context_detail)
        )
    )
    return [
        (
            "invocation_duration_sum",
            duration_sum == evidence.get("totalInvocationDurationMs"),
            {
                "computed": duration_sum,
                "recorded": evidence.get("totalInvocationDurationMs"),
            },
        ),
        ("invocation_digests", terminal_digests, invocations),
        (
            "invocation_timestamp_reconciliation",
            len(timestamp_reconciliation) == len(invocations),
            timestamp_reconciliation,
        ),
        (
            "writer_model",
            role_models.get("writer") == expected_profile["writerModelId"]
            or zero_invocation_answer,
            role_models,
        ),
        (
            "reviewer_model",
            reviewer_matches_profile,
            {
                "roleModels": role_models,
                "expectedReviewerModelId": expected_reviewer_model,
                "writerOnly": expected_reviewer_model is None,
                "notReachedAfterFailure": reviewer_not_reached_after_failure,
            },
        ),
        ("effective_temperature_and_dry", config_ok, configurations),
        ("hub_request_evidence", request_evidence_ok, request_evidence_detail),
        ("hub_request_digest_match", digest_matches, digest_detail),
        ("hub_capacity_evidence", capacity_coherent, capacity_detail),
        (
            "retained_instruction_context",
            retained_context,
            retained_context_detail,
        ),
        ("revision_context_exclusions", not forbidden, forbidden),
    ]


def _find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    forbidden_names = {
        "credentials",
        "dsn",
        "password",
        "previousresultrows",
        "resultrows",
        "reasoningtrace",
        "rawtrace",
    }
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).replace("_", "").lower() in forbidden_names:
                found.append(child)
            found.extend(_find_forbidden_keys(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_find_forbidden_keys(item, f"{path}[{index}]"))
    return found


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_digests(rows: list[list[Any]]) -> list[str]:
    return [hashlib.sha256(rfc8785.dumps(row)).hexdigest() for row in rows]


def _gateway_cell_value(cell: dict[str, Any]) -> Any:
    return None if cell.get("type") == "null" else cell.get("value")


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return repr(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return value.isoformat()
    if isinstance(value, (date, datetime_time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, dict):
        return {
            str(key): _json_safe_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _binding_value(parameter: dict[str, Any]) -> Any:
    value = parameter["value"]
    parameter_type = parameter["type"]
    if parameter_type == "date":
        return date.fromisoformat(value)
    if parameter_type == "date-time":
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parameter_type == "integer":
        if isinstance(value, bool):
            raise ValueError("Boolean values cannot be bound as integers.")
        return int(value)
    if parameter_type == "number":
        return Decimal(str(value))
    if parameter_type == "integer-list":
        if any(isinstance(item, bool) for item in value):
            raise ValueError("Boolean values cannot be bound as integers.")
        return [int(item) for item in value]
    if parameter_type == "string-list":
        return [str(item) for item in value]
    return value


def _driver_sql(sql: str, parameter_names: set[str]) -> str:
    """Convert named placeholders outside PostgreSQL strings/comments/casts.

    Every literal percent is doubled on the way through: psycopg treats %
    as a placeholder marker whenever a params argument is passed, and this
    data really does contain values like 'CD4%'.
    """

    output: list[str] = []
    index = 0
    quote: str | None = None
    dollar_quote: str | None = None
    line_comment = False
    block_comment = False
    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""
        if line_comment:
            output.append(char)
            index += 1
            if char == "\n":
                line_comment = False
            continue
        if block_comment:
            output.append(char)
            index += 1
            if char == "*" and following == "/":
                output.append(following)
                index += 1
                block_comment = False
            continue
        if quote:
            output.append(char)
            index += 1
            if char == quote:
                if following == quote:
                    output.append(following)
                    index += 1
                else:
                    quote = None
            continue
        if dollar_quote:
            if sql.startswith(dollar_quote, index):
                output.append(dollar_quote)
                index += len(dollar_quote)
                dollar_quote = None
            else:
                output.append(char)
                index += 1
            continue
        if char == "-" and following == "-":
            output.extend((char, following))
            index += 2
            line_comment = True
            continue
        if char == "/" and following == "*":
            output.extend((char, following))
            index += 2
            block_comment = True
            continue
        if char in {"'", '"'}:
            quote = char
            output.append(char)
            index += 1
            continue
        if char == "$":
            delimiter_end = sql.find("$", index + 1)
            if delimiter_end != -1:
                tag = sql[index + 1 : delimiter_end]
                if not tag or (
                    (tag[0].isalpha() or tag[0] == "_")
                    and all(part.isalnum() or part == "_" for part in tag)
                ):
                    dollar_quote = sql[index : delimiter_end + 1]
                    output.append(dollar_quote)
                    index = delimiter_end + 1
                    continue
        if (
            char == ":"
            and following != ":"
            and (following.isalpha() or following == "_")
        ):
            end = index + 2
            while end < len(sql) and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            name = sql[index + 1 : end]
            if name in parameter_names:
                output.append(f"%({name})s")
                index = end
                continue
        output.append(char)
        index += 1
    return _escape_percents_outside_placeholders("".join(output))
