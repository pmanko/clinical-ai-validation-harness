"""Lossless notebook-event mapping onto the harness metadata envelope."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


NOTEBOOK_EVENT_SCHEMA_VERSION = "harness.catalyst-notebook.event.v1"


_REQUIRED_WORKBENCH_EVENT_FIELDS = {
    "contractVersion",
    "eventId",
    "sessionId",
    "sequence",
    "type",
    "timestamp",
    "actor",
    "entityRefs",
    "payload",
}


def workbench_event_envelope(
    run_id: str,
    event: Mapping[str, Any],
) -> dict[str, Any]:
    """Map one persisted Gateway event without interpreting its typed payload."""

    if not run_id:
        raise ValueError("run_id must not be empty")
    missing = sorted(_REQUIRED_WORKBENCH_EVENT_FIELDS.difference(event))
    if missing:
        raise ValueError(
            f"workbench event is missing required fields: {', '.join(missing)}"
        )
    return {
        "schema_version": event["contractVersion"],
        "event_id": event["eventId"],
        "event_type": event["type"],
        "timestamp": event["timestamp"],
        "run_id": run_id,
        "session_id": event["sessionId"],
        "sequence": event["sequence"],
        "actor": event["actor"],
        "entity_refs": deepcopy(event["entityRefs"]),
        "payload": deepcopy(event["payload"]),
    }


def _existing_evidence_paths(
    run_dir: Path,
    candidates: list[str],
) -> list[str]:
    """Return only safe, materialized evidence references for an event."""

    root = run_dir.resolve()
    paths: list[str] = []
    for relative in candidates:
        path = run_dir / relative
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("event evidence path must stay within the run directory")
        if path.is_file():
            paths.append(relative)
    return paths


def notebook_result_events(
    *,
    run_id: str,
    run_dir: Path,
    prefix: str,
    result: Mapping[str, Any],
    backend_id: str,
) -> list[dict[str, Any]]:
    """Project one completed notebook repetition into versioned event records.

    Events reference the immutable HTTP/database evidence already recorded by
    the runner. They contain identifiers and outcomes, never SQL result rows.
    """

    common = {
        "schema_version": NOTEBOOK_EVENT_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario_id": str(result["scenarioId"]),
        "repetition": int(result["repetition"]),
        "session_id": result.get("sessionId"),
        "backend_id": backend_id,
    }
    events: list[dict[str, Any]] = [
        {
            **common,
            "event_type": "scenario",
            "status": result.get("status"),
            "passed": bool(result.get("passed")),
            "evidence_paths": _existing_evidence_paths(
                run_dir,
                [
                    f"{prefix}/01-create-session.json",
                    f"{prefix}/08-create-followup.json",
                    f"{prefix}/09-refreshed-session.json",
                ],
            ),
        }
    ]

    for turn_role, turn_id, evidence in (
        (
            "initial",
            result.get("initialTurnId"),
            [
                f"{prefix}/02-initial-turns.json",
                f"{prefix}/03-initial-generation-evidence.json",
            ],
        ),
        (
            "followup",
            result.get("followupTurnId"),
            [
                f"{prefix}/08-create-followup.json",
                f"{prefix}/10-final-turns.json",
                f"{prefix}/11-followup-generation-evidence.json",
            ],
        ),
    ):
        if turn_id:
            events.append(
                {
                    **common,
                    "event_type": "turn",
                    "turn_role": turn_role,
                    "turn_id": turn_id,
                    "evidence_paths": _existing_evidence_paths(run_dir, evidence),
                }
            )

    for version_role, version_id, digest, turn_id, evidence in (
        (
            "base",
            result.get("baseVersionId"),
            result.get("baseQueryDigest"),
            result.get("initialTurnId"),
            [f"{prefix}/04-save-base-version.json"],
        ),
        (
            "successor",
            result.get("selectedVersionId"),
            result.get("selectedQueryDigest"),
            result.get("followupTurnId"),
            [
                f"{prefix}/09-refreshed-session.json",
                f"{prefix}/10-final-turns.json",
            ],
        ),
    ):
        if version_id:
            events.append(
                {
                    **common,
                    "event_type": "version",
                    "version_role": version_role,
                    "version_id": version_id,
                    "query_digest": digest,
                    "turn_id": turn_id,
                    "evidence_paths": _existing_evidence_paths(run_dir, evidence),
                }
            )

    for execution_role, execution_id, version_id, evidence in (
        (
            "base",
            result.get("baseExecutionId"),
            result.get("baseVersionId"),
            [
                f"{prefix}/06-execute-base.json",
                f"{prefix}/07-postgres-base.json",
                f"{prefix}/15-gold-execution-match-base.json",
            ],
        ),
        (
            "successor",
            result.get("successorExecutionId"),
            result.get("selectedVersionId"),
            [
                f"{prefix}/13-execute-successor.json",
                f"{prefix}/14-postgres-successor.json",
                f"{prefix}/16-gold-execution-match-successor.json",
            ],
        ),
    ):
        if execution_id:
            events.append(
                {
                    **common,
                    "event_type": "execution",
                    "execution_role": execution_role,
                    "execution_id": execution_id,
                    "version_id": version_id,
                    "evidence_paths": _existing_evidence_paths(run_dir, evidence),
                }
            )
    return events
