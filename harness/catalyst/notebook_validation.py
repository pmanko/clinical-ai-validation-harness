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
    key_columns = tuple(str(c) for c in payload.get("keyColumns", []))
    value_columns = {
        str(k): dict(v) for k, v in payload.get("valueColumns", {}).items()
    }
    value_column = payload.get("valueColumn")
    if mode == "row_set" and not match_columns:
        raise ValueError("row_set gold check requires matchColumns")
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
        key_columns=key_columns,
        value_columns=value_columns,
        value_column=str(value_column) if value_column else None,
    )


WRITER_OUTCOMES = ("ready", "needs_clarification", "unsupported")
# A question and a refusal both end a generation with no SQL.
TERMINAL_WRITER_OUTCOMES = frozenset(WRITER_OUTCOMES[1:])
"""The writer's terminal choices. `rejected` is the Gateway's, not one of these."""


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
    infrastructure_replacements: int
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


@dataclass(frozen=True)
class NotebookRunResult:
    run_id: str
    run_dir: Path
    result_count: int
    passed_count: int
    skipped_count: int


class NotebookTransport(Protocol):
    def profiles(self) -> HttpExchange: ...

    def dataset_overview(self) -> HttpExchange: ...

    def catalog(self) -> HttpExchange: ...

    def create_session(self, question: str, profile_id: str) -> HttpExchange: ...

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
        execution: dict[str, Any],
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
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            json=body,
            timeout=self.timeout_seconds,
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
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        import psycopg

        parameters = list(version.get("parameters") or [])
        bindings = {
            str(parameter["name"]): _binding_value(parameter)
            for parameter in parameters
        }
        driver_sql = _driver_sql(str(version["sql"]), set(bindings))
        with psycopg.connect(self.dsn, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (f"{self.statement_timeout_ms}ms",),
                )
                cursor.execute(driver_sql, bindings)
                direct_rows = list(cursor.fetchmany(self.max_rows + 1))
                direct_columns = [item.name for item in (cursor.description or ())]

        direct_truncated = len(direct_rows) > self.max_rows
        direct_rows = direct_rows[: self.max_rows]
        normalized_direct = [
            [_json_safe_value(value) for value in row] for row in direct_rows
        ]
        result = execution.get("result") if isinstance(execution, dict) else None
        gateway_columns = [
            item.get("name") for item in (result or {}).get("columns", [])
        ]
        gateway_rows = [
            [_gateway_cell_value(cell) for cell in row]
            for row in (result or {}).get("rows", [])
        ]
        row_count = (result or {}).get("rowCount", {})
        comparisons = {
            "columns": gateway_columns == direct_columns,
            "returnedRows": row_count.get("returned") == len(direct_rows),
            "truncated": row_count.get("truncated") is direct_truncated,
            "recordDigests": _row_digests(gateway_rows)
            == _row_digests(normalized_direct),
        }
        parsed = urlparse(self.dsn)
        return {
            "contractVersion": "harness.catalyst-notebook.postgres-crosscheck.v1",
            "readOnlyTransaction": True,
            "database": parsed.path.lstrip("/") or None,
            "versionId": version.get("versionId"),
            "queryDigest": version.get("queryDigest"),
            "gatewayExecutionId": execution.get("executionId"),
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
            return result
        if gold_check.mode == "count":
            result["passed"] = len(model_rows) == len(reference_rows)
        elif gold_check.mode == "row_set":
            result.update(
                _compare_row_sets(model_rows, reference_rows, gold_check.match_columns)
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

    def _key(row: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(row.get(column) for column in match_columns)

    model_counter = Counter(_key(row) for row in model_rows)
    reference_counter = Counter(_key(row) for row in reference_rows)
    missing = list((reference_counter - model_counter).elements())
    extra = list((model_counter - reference_counter).elements())
    return {
        "matchColumns": list(match_columns),
        "missingFromModelCount": len(missing),
        "extraInModelCount": len(extra),
        "missingFromModelSample": [list(item) for item in missing[:20]],
        "extraInModelSample": [list(item) for item in extra[:20]],
        "passed": not missing and not extra,
    }


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

    model_by_key = {_key(row): row for row in model_rows}
    reference_by_key = {_key(row): row for row in reference_rows}
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
    return {
        "keyColumns": list(key_columns),
        "valueColumns": value_columns,
        "missingKeys": [list(key) for key in missing_keys],
        "extraKeys": [list(key) for key in extra_keys],
        "valueMismatches": mismatches,
        "valueColumnResolution": resolution,
        "passed": not missing_keys and not extra_keys and not mismatches,
    }


def _compare_scalars(
    model_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    value_column: str | None,
) -> dict[str, Any]:
    model_value = model_rows[0].get(value_column) if model_rows else None
    reference_value = reference_rows[0].get(value_column) if reference_rows else None
    return {
        "valueColumn": value_column,
        "modelValue": model_value,
        "referenceValue": reference_value,
        "passed": bool(model_rows)
        and bool(reference_rows)
        and model_value == reference_value,
    }


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
        return path

    def exchange(
        self,
        relative_path: str,
        exchange: HttpExchange,
        *,
        kind: str,
    ) -> dict[str, Any]:
        self.json(relative_path, exchange.as_dict(), kind=kind)
        return exchange.response_body

    def finish(self) -> None:
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
        index_path.write_bytes(encoded)
        (self.run_dir / "evidence-index.sha256").write_text(
            f"{hashlib.sha256(encoded).hexdigest()}  evidence-index.json\n",
            encoding="utf-8",
        )


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
            )
        )
    return tuple(turns)


def load_notebook_suite(path: Path | str) -> NotebookSuite:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    repetitions = int(payload["repetitions"])
    if repetitions < 1:
        raise ValueError("Notebook suite repetitions must be at least one")
    replacement_value = payload.get("infrastructureReplacements")
    replacement_budget = int(replacement_value) if replacement_value is not None else 0
    if replacement_budget < 0:
        raise ValueError("Notebook suite infrastructureReplacements must not be negative")
    extended_value = payload.get("extendedRepetitions")
    extended = int(extended_value) if extended_value is not None else None
    if extended is not None and extended < repetitions:
        raise ValueError(
            "Notebook suite extendedRepetitions must not be below repetitions"
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
            )
        )
    if not scenarios:
        raise ValueError("Notebook suite must contain scenarios")
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
        id=str(payload["id"]),
        dataset_id=str(payload["datasetId"]),
        dataset_version=str(payload["datasetVersion"]),
        catalog_version=str(payload["catalogVersion"]),
        provider_name=str(payload["providerName"]),
        repetitions=repetitions,
        extended_repetitions=extended,
        infrastructure_replacements=replacement_budget,
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
    for stem in _HTTP_STEP_STEMS:
        path = run_dir / prefix / f"{stem}.json"
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
    """Whether this repetition failed the host rather than the model.

    A team is judged on what its models did. A 5xx, or a repetition that never
    reached a turn, measured nothing and is replaced instead of scored. A 4xx
    is Catalyst refusing the request, which is the product's behaviour and
    belongs in the denominator like any other answer.
    """
    if result.get("status") == "failed_before_turn":
        return True
    status = result.get("httpStatus")
    return isinstance(status, int) and status >= 500


def repetition_pair_is_unstable(runs: list[dict[str, Any]]) -> bool:
    """Whether a profile/scenario pair's repetitions disagree with each other.

    Three agreeing runs settle a pair. Three that disagree — on the verdict,
    on which answer the writer gave, or on whether the database check matched
    — have not measured anything yet, so the pair earns two more runs.
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


def _pair_is_complete(
    recorded: list[dict[str, Any]],
    suite: NotebookSuite,
    scenario: NotebookScenario,
    repetitions: int | None,
) -> bool:
    """Whether an interrupted run finished this pair by the live run's rules.

    One recorded repetition of three is not a finished pair, and three
    mutually disagreeing repetitions of a suite that extends to five are not
    either: reuse applies exactly the scheduler's own completion rule, so a
    resumed run and an uninterrupted one accept the same evidence.
    """
    # Only scored repetitions count: replaced infrastructure attempts and
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
    # rows.jsonl is appended as each repetition completes, so it is what an
    # interrupted run actually left behind; results.json only exists once a
    # run finished.
    rows: list[dict[str, Any]] = []
    incremental = Path(resume_from) / "rows.jsonl"
    if incremental.exists():
        for line in incremental.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    else:
        results_path = Path(resume_from) / "results.json"
        if not results_path.exists():
            return {}
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        rows = list(payload.get("results") or [])
    pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        profile_id = row.get("profileId")
        scenario_id = row.get("scenarioId")
        if not isinstance(profile_id, str) or not isinstance(scenario_id, str):
            continue
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
    if repetitions is not None and repetitions < 1:
        raise ValueError("repetitions must be at least one")

    run_id = str(uuid4())
    run_dir = Path(output_dir) / run_id
    recorder = _EvidenceRecorder(run_dir, run_id)
    root = Path(project_root).resolve()
    target_provenance = provenance_loader(root)
    suite_sha256 = hashlib.sha256(suite_path.read_bytes()).hexdigest()
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
    )
    recorder.json("run_manifest.json", manifest.to_dict(), kind="run_manifest")
    recorder.json(
        "suite.json",
        json.loads(suite_path.read_text(encoding="utf-8")),
        kind="suite_definition",
        metadata={"sourceSha256": suite_sha256},
    )

    # Additive run-stream files (events.jsonl / results.jsonl): NOT registered
    # in the evidence index, so evidence-index.json/.sha256 and results.json
    # stay byte-identical to today. This is the same run/backend_selected/
    # evaluation + results-row contract harness/validate/runner.py streams,
    # so scripts/validate-dashboard.py tracks a Catalyst run live instead of
    # only ChartSearchAI's "validate" family — one harness architecture, only
    # the scenarios and rubric differ.
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

    profiles_exchange = client.profiles()
    dataset_exchange = client.dataset_overview()
    catalog_exchange = client.catalog()
    recorder.exchange(
        "discovery/query-options.json", profiles_exchange, kind="profile_discovery"
    )
    dataset = recorder.exchange(
        "discovery/dataset.json", dataset_exchange, kind="dataset_discovery"
    )
    catalog = recorder.exchange(
        "discovery/catalog.json", catalog_exchange, kind="catalog_discovery"
    )
    _require_discovery(suite, profiles_exchange, dataset_exchange, catalog_exchange)

    # A comparison is hours of model time, so an interruption resumes rather
    # than restarts: every (team, scenario) already recorded is reused
    # verbatim and only the missing pairs are run again.
    finished = _finished_pairs(resume_from)
    results: list[dict[str, Any]] = []
    seen_sessions: set[str] = set()
    # The budget belongs to the run: it exists to stop a team being scored
    # on a host that keeps falling over, and a per-scenario counter would
    # let a twelve-scenario suite absorb twenty-four failures.
    replacements = 0
    infrastructure_failures: list[dict[str, Any]] = []
    skipped = 0
    # Teams are the outer loop: a local model stays resident while it answers
    # the whole suite, and every team meets the same frozen scenario order.
    teams: tuple[str | None, ...] = suite.comparison_profiles or (None,)
    for team in teams:
        # The budget invalidates *that team's* run, so each team gets its own.
        replacements = 0
        for scenario in selected:
            if team is not None:
                scenario = _scenario_for_profile(scenario, team)
            recorded = finished.get(
                (team or scenario.initial_profile_id, scenario.id)
            )
            if recorded is not None and _pair_is_complete(
                recorded, suite, scenario, repetitions
            ):
                results.extend(recorded)
                continue
            if scenario.manual_only and not include_manual:
                skipped += 1
                results.append(
                    {
                        "scenarioId": scenario.id,
                        "family": scenario.family,
                        "profileId": team or scenario.initial_profile_id,
                        "status": "skipped",
                        "reason": "manual-only bounded failure scenario was not enabled",
                    }
                )
                continue
            repeat_count = _effective_repetitions(suite, scenario, repetitions)
            # A pair that disagrees with itself has measured nothing, so it earns
            # the extension; one that agrees is settled and is not re-run.
            ceiling = (
                repeat_count
                if repetitions is not None or suite.extended_repetitions is None
                else max(repeat_count, suite.extended_repetitions)
            )
            scenario_runs: list[dict[str, Any]] = []
            repetition = 0
            while repetition < repeat_count:
                repetition += 1
                attempt_slot = (
                    f"repetition-{repetition:02d}"
                    if replacements == 0
                    else f"repetition-{repetition:02d}-replacement-{replacements:02d}"
                )
                prefix = (
                    f"scenarios/{scenario.id}/{attempt_slot}"
                    if team is None
                    else f"scenarios/{team}/{scenario.id}/{attempt_slot}"
                )
                started_at = datetime.now(timezone.utc).isoformat()
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
                session_id = result.get("sessionId")
                isolated = isinstance(session_id, str) and session_id not in seen_sessions
                if isinstance(session_id, str):
                    seen_sessions.add(session_id)
                result["assertions"].append(
                    {
                        "name": "new_session_isolation",
                        "passed": isolated,
                        "evidence": session_id,
                    }
                )
                result["passed"] = all(item["passed"] for item in result["assertions"])
                result["profileId"] = team or scenario.initial_profile_id
                # Appended now, not at the end: this row is what --resume
                # reuses when the run dies before the summary is written.
                append_jsonl(run_dir / "rows.jsonl", result)
                result["httpStatus"] = _normalized_http_status(run_dir, prefix)
                if suite.infrastructure_replacements and is_infrastructure_failure(result):
                    replacements += 1
                    if replacements > suite.infrastructure_replacements:
                        raise ValueError(
                            f"scenario {scenario.id!r} hit a third infrastructure "
                            "failure for this run; the run is invalid for that team"
                        )
                    infrastructure_failures.append(
                        {
                            "scenarioId": scenario.id,
                            "repetition": repetition,
                            "attempt": attempt_slot,
                            "httpStatus": result["httpStatus"],
                            "status": result.get("status"),
                            "sessionId": result.get("sessionId"),
                        }
                    )
                    result["status"] = "infrastructure_failed"
                    results.append(result)
                    # The host, not the model, failed: re-run this repetition
                    # rather than scoring it.
                    repetition -= 1
                    continue
                results.append(result)
                scenario_runs.append(result)
                ended_at = datetime.now(timezone.utc).isoformat()

                http_status = _normalized_http_status(run_dir, prefix)
                answer = (
                    _selected_answer_sql(run_dir, prefix)
                    or result.get("baseSql")
                    or result.get("baseAnswerText")
                    or str(result.get("status"))
                )
                backend_id = scenario.followup_profile_id
                append_jsonl(
                    results_path,
                    {
                        "run_id": run_id,
                        "scenario_id": scenario.id,
                        "backend_id": backend_id,
                        "turn": repetition,
                        "request": {
                            "question": (
                                f"{scenario.initial_question} ⇒ "
                                f"{scenario.followup_instruction}"
                                if scenario.turns
                                else scenario.initial_question
                            )
                        },
                        "response": {
                            "answer": answer,
                            "baseOutcome": result.get("baseOutcome"),
                            "expectedBaseOutcome": result.get(
                                "expectedBaseOutcome"
                            ),
                            "turns": [
                                {
                                    "instruction": t.get("instruction"),
                                    "expectedOutcome": t.get("expectedOutcome"),
                                    "observedOutcome": t.get("observedOutcome"),
                                }
                                for t in result.get("turns") or []
                            ],
                            "resultPreview": result.get("resultPreview"),
                            "failedAssertions": [
                                {
                                    "name": item["name"],
                                    "evidence": _compact_evidence(
                                        item.get("evidence")
                                    ),
                                }
                                for item in result.get("assertions") or []
                                if not item.get("passed")
                            ][:8],
                        },
                        "metrics": {
                            "http_status": http_status,
                            "latency_ms": (result.get("timing") or {}).get(
                                "unadjustedGenerationWallMs"
                            ),
                            "answer_chars": len(answer) if isinstance(answer, str) else 0,
                            "passed": result["passed"],
                            "first_turn": repetition == 1,
                        },
                        "error": _first_failed_assertion(result["assertions"]),
                        "started_at": started_at,
                        "ended_at": ended_at,
                    },
                )
                for event in notebook_result_events(
                    run_id=run_id,
                    run_dir=run_dir,
                    prefix=prefix,
                    result=result,
                    backend_id=backend_id,
                ):
                    append_event(events_path, event)
                append_event(
                    events_path,
                    {
                        "schema_version": NOTEBOOK_EVENT_SCHEMA_VERSION,
                        "event_type": "evaluation",
                        "check": "notebook_scenario",
                        "run_id": run_id,
                        "scenario_id": scenario.id,
                        "backend_id": backend_id,
                        "turn": repetition,
                        "http_status": http_status,
                        "passed": result["passed"],
                    },
                )
                if (
                    repetition == repeat_count
                    and repeat_count < ceiling
                    and repetition_pair_is_unstable(scenario_runs)
                ):
                    repeat_count = ceiling

    passed_count = sum(
        result.get("passed") is True
        and result.get("status") != "infrastructure_failed"
        for result in results
    )
    result_count = sum(
        result.get("status") not in {"skipped", "infrastructure_failed"}
        for result in results
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
        "skippedCount": skipped,
        "infrastructureFailureCount": len(infrastructure_failures),
        "infrastructureFailures": infrastructure_failures,
        "nondeterminism": nondeterminism,
        "results": results,
    }
    recorder.json("results.json", summary, kind="validation_results")
    recorder.finish()
    return NotebookRunResult(
        run_id=run_id,
        run_dir=run_dir,
        result_count=result_count,
        passed_count=passed_count,
        skipped_count=skipped,
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
        assertions.append({"name": name, "passed": bool(passed), "evidence": evidence})

    create = client.create_session(
        scenario.initial_question, scenario.initial_profile_id
    )
    session = recorder.exchange(
        f"{prefix}/01-create-session.json", create, kind="session_create"
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
        initial_evidence = recorder.exchange(
            f"{prefix}/03-initial-generation-evidence.json",
            evidence_exchange,
            kind="generation_evidence",
        )
        check(
            "initial_evidence_available",
            evidence_exchange.status_code == 200,
            evidence_exchange.status_code,
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
    if scenario.expected_base_outcome in TERMINAL_WRITER_OUTCOMES:
        # A question or a refusal is one writer call and no SQL. There is
        # nothing to validate, execute or check an answer against, and the
        # session must be holding no query at all.
        check(
            "no_sql_after_non_ready_base",
            not session.get("versions") and session.get("currentVersionId") is None,
            {
                "versions": session.get("versions"),
                "currentVersionId": session.get("currentVersionId"),
            },
        )
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
    if base_version is None and scenario.expected_base_outcome not in (
        TERMINAL_WRITER_OUTCOMES
    ):
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
            crosscheck = postgres_checker.check(base_version, base_execution)
            recorder.json(
                f"{prefix}/07-postgres-base.json",
                crosscheck,
                kind="postgres_crosscheck",
            )
            check("base_postgres_crosscheck", crosscheck["passed"], crosscheck)
        if (
            gold_checker is not None
            and scenario.base_gold_check is not None
            and executed.status_code == 200
            and base_execution.get("status") == "succeeded"
        ):
            gold_result = gold_checker.check(base_version, scenario.base_gold_check)
            recorder.json(
                f"{prefix}/15-gold-execution-match-base.json",
                gold_result,
                kind="gold_execution_match",
            )
            check("base_gold_execution_match", gold_result["passed"], gold_result)

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
    for turn_index, turn_spec in enumerate(scenario.turns, start=1):
        slot = "" if turn_index == 1 else f"-t{turn_index}"

        def check(name: str, passed: bool, evidence: Any, _slot: str = slot) -> None:
            assertions.append(
                {
                    "name": f"{name}{_slot}",
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
        if turn_spec.expected_outcome in {"needs_clarification", "unsupported"}:
            # A question or a refusal is one writer call and no SQL: the prior
            # selected query has to survive it untouched.
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
        refreshed = recorder.exchange(
            f"{prefix}/09-refreshed-session{slot}.json",
            refreshed_exchange,
            kind="session_restore",
        )
        timeline_exchange = client.get_turns(session_id)
        timeline = recorder.exchange(
            f"{prefix}/10-final-turns{slot}.json",
            timeline_exchange,
            kind="turn_timeline",
        )
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
            followup_evidence = recorder.exchange(
                f"{prefix}/11-followup-generation-evidence{slot}.json",
                evidence_exchange,
                kind="generation_evidence",
            )
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
                                "passed": True,
                                "evidence": {"recorded": False, "required": False},
                            }
                        )
                    continue
                check(name, passed, detail)

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
            if base_execution is not None:
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
                crosscheck = postgres_checker.check(selected, successor_execution)
                recorder.json(
                    f"{prefix}/14-postgres-successor{slot}.json",
                    crosscheck,
                    kind="postgres_crosscheck",
                )
                check("successor_postgres_crosscheck", crosscheck["passed"], crosscheck)
            if (
                gold_checker is not None
                and scenario.successor_gold_check is not None
                and executed.status_code == 200
                and successor_execution.get("status") == "succeeded"
            ):
                gold_result = gold_checker.check(selected, scenario.successor_gold_check)
                recorder.json(
                    f"{prefix}/16-gold-execution-match-successor{slot}.json",
                    gold_result,
                    kind="gold_execution_match",
                )
                check("successor_gold_execution_match", gold_result["passed"], gold_result)

        turn_summaries.append(
            {
                "turnIndex": turn_index,
                "turnId": turn.get("turnId"),
                "instruction": turn_spec.instruction,
                "profileId": turn_spec.profile_id,
                "status": turn.get("status"),
                "expectedOutcome": turn_spec.expected_outcome,
                "observedOutcome": observed_outcome,
                "selectedVersionId": turn.get("selectedVersionId"),
                "evidenceDigest": followup_evidence.get("evidenceDigest"),
            }
        )
        # The next turn starts from whatever this one left current, which is
        # the unchanged prior query when the writer asked or refused.
        current_version = refreshed.get("currentVersion")
        if isinstance(current_version, dict) and current_version.get("versionId"):
            base_version = current_version
        base_execution = successor_execution or base_execution
        base_execution_wall_ms = successor_execution_wall_ms or base_execution_wall_ms

    invocation_ms = int(initial_evidence.get("totalInvocationDurationMs") or 0) + int(
        followup_evidence.get("totalInvocationDurationMs") or 0
    )
    followup_wall_ms = followup.elapsed_ms if followup is not None else 0
    generation_wall_ms = create.elapsed_ms + followup_wall_ms
    timing = {
        "initialGenerationWallMs": create.elapsed_ms,
        "followupGenerationWallMs": followup_wall_ms,
        "unadjustedGenerationWallMs": generation_wall_ms,
        "recordedInvocationDurationMs": invocation_ms,
        "generationWallMinusRecordedInvocationsMs": generation_wall_ms - invocation_ms,
        "baseExecutionWallMs": base_execution_wall_ms,
        "successorExecutionWallMs": successor_execution_wall_ms,
    }
    check(
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
        "baseSql": (base_version or {}).get("sql"),
        "resultPreview": _result_preview(successor_execution or base_execution),
        "sessionId": session_id,
        "initialTurnId": initial_turn.get("turnId")
        if isinstance(initial_turn, dict)
        else None,
        "followupTurnId": turn.get("turnId"),
        "turns": turn_summaries,
        "baseVersionId": (base_version or {}).get("versionId"),
        "baseQueryDigest": (base_version or {}).get("queryDigest"),
        "selectedVersionId": turn.get("selectedVersionId"),
        "baseExecutionId": (base_execution or {}).get("executionId"),
        "successorExecutionId": (successor_execution or {}).get("executionId"),
        "initialCandidateDigests": [
            item.get("candidateDigest")
            for item in initial_evidence.get("candidates", [])
            if item.get("candidateDigest") is not None
        ],
        "followupCandidateDigests": [
            item.get("candidateDigest")
            for item in followup_evidence.get("candidates", [])
            if item.get("candidateDigest") is not None
        ],
        "selectedQueryDigest": (
            selected.get("queryDigest") if isinstance(selected, dict) else None
        ),
        "followupEvidenceDigest": followup_evidence.get("evidenceDigest"),
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


def _evidence_checks(
    evidence: dict[str, Any],
    *,
    expected_profile: dict[str, str | None],
) -> list[tuple[str, bool, Any]]:
    invocations = list(evidence.get("invocations") or [])
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
    config_ok = bool(configurations) and all(
        item.get("temperature") == 0 and item.get("dryMultiplier") == 0
        for item in configurations
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
            role_models.get("writer") == expected_profile["writerModelId"],
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
    """Convert named placeholders outside PostgreSQL strings/comments/casts."""

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
    return "".join(output)
