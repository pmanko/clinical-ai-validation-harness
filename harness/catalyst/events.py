"""Lossless notebook-event mapping onto the harness metadata envelope."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


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
