from __future__ import annotations

from pathlib import Path

from harness.catalyst.events import (
    NOTEBOOK_EVENT_SCHEMA_VERSION,
    notebook_result_events,
)


def test_notebook_result_events_are_versioned_and_reference_real_evidence(
    tmp_path: Path,
) -> None:
    prefix = "scenarios/s1/repetition-01"
    evidence = (
        "01-create-session.json",
        "02-initial-turns.json",
        "03-initial-generation-evidence.json",
        "04-save-base-version.json",
        "06-execute-base.json",
        "08-create-followup.json",
        "09-refreshed-session.json",
        "10-final-turns.json",
        "11-followup-generation-evidence.json",
        "13-execute-successor.json",
    )
    for name in evidence:
        path = tmp_path / prefix / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    events = notebook_result_events(
        run_id="run-1",
        run_dir=tmp_path,
        prefix=prefix,
        backend_id="profile-1",
        result={
            "scenarioId": "s1",
            "repetition": 1,
            "sessionId": "session-1",
            "status": "completed",
            "passed": True,
            "initialTurnId": "turn-0",
            "followupTurnId": "turn-1",
            "baseVersionId": "version-0",
            "baseQueryDigest": "a" * 64,
            "selectedVersionId": "version-1",
            "selectedQueryDigest": "b" * 64,
            "baseExecutionId": "execution-0",
            "successorExecutionId": "execution-1",
        },
    )

    assert [event["event_type"] for event in events] == [
        "scenario",
        "turn",
        "turn",
        "version",
        "version",
        "execution",
        "execution",
    ]
    assert all(
        event["schema_version"] == NOTEBOOK_EVENT_SCHEMA_VERSION for event in events
    )
    assert all("sql" not in event and "rows" not in event for event in events)
    for event in events:
        assert event["evidence_paths"]
        assert all((tmp_path / path).is_file() for path in event["evidence_paths"])


def test_notebook_result_events_reject_evidence_traversal(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    try:
        from harness.catalyst.events import _existing_evidence_paths

        try:
            _existing_evidence_paths(tmp_path, ["../outside.json"])
        except ValueError as exc:
            assert "within the run directory" in str(exc)
        else:
            raise AssertionError("path traversal was accepted")
    finally:
        outside.unlink()
