from __future__ import annotations

import json

from harness.catalyst.events import workbench_event_envelope
from harness.metadata import append_event


def test_notebook_records_round_trip_through_events_jsonl_without_loss(
    tmp_path,
) -> None:
    turn = {
        "contractVersion": "catalyst.workbench.turn.v1",
        "sessionId": "c6f079fc-b9f4-49e5-b2ec-fd1760fd6497",
        "turnId": "d3880166-ef1c-4f94-8dd1-5218775e79fa",
        "kind": "followup",
        "status": "completed",
    }
    snapshot = {
        "contractVersion": "catalyst.workbench.editor-snapshot-record.v1",
        "snapshotId": "b395a80c-fbf7-42ea-bf29-3f36259e9cc9",
        "content": {
            "contractVersion": "catalyst.workbench.editor-snapshot.v1",
            "sql": "SELECT 1",
            "parameters": [],
            "expectedColumns": [],
            "editorDigest": (
                "82d9696f92e64acb0c4edba843633c97eb23fd3f22887d93755eb86971855105"
            ),
        },
    }
    evidence = {
        "contractVersion": "catalyst.workbench.generation-evidence.v1",
        "evidenceId": "662e923f-99dd-402f-ad5e-d3df14ab5626",
        "turnId": turn["turnId"],
        "instruction": "Return one row",
        "invocations": [
            {
                "role": "writer",
                "modelId": "gemma-4-12b",
                "durationMs": 17,
                "requestDigest": "a" * 64,
                "responseDigest": "b" * 64,
            }
        ],
    }
    source = {
        "contractVersion": "catalyst.workbench.event.v1",
        "eventId": "b878802f-22ac-4c92-8649-14258080c91c",
        "sessionId": turn["sessionId"],
        "sequence": 4,
        "type": "query_turn.completed",
        "timestamp": "2026-07-18T12:00:00Z",
        "actor": "med_agent_hub",
        "entityRefs": {
            "sessionId": turn["sessionId"],
            "turnId": turn["turnId"],
        },
        "payload": {
            "turn": turn,
            "editorSnapshot": snapshot,
            "generationEvidence": evidence,
        },
    }

    envelope = workbench_event_envelope("run-008", source)
    events_path = tmp_path / "events.jsonl"
    append_event(events_path, envelope)
    restored = json.loads(events_path.read_text(encoding="utf-8"))

    assert restored == envelope
    assert restored["schema_version"] == "catalyst.workbench.event.v1"
    assert restored["event_id"] == source["eventId"]
    assert restored["event_type"] == source["type"]
    assert restored["run_id"] == "run-008"
    assert restored["payload"]["turn"] == turn
    assert restored["payload"]["editorSnapshot"] == snapshot
    assert restored["payload"]["generationEvidence"] == evidence
