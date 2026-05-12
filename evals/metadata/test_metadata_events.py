import json
from pathlib import Path

from harness.metadata import RunManifest, append_event, write_manifest


def test_manifest_and_events_are_written(tmp_path: Path) -> None:
    manifest_path = tmp_path / "run_manifest.json"
    events_path = tmp_path / "events.jsonl"
    manifest = RunManifest(
        run_id="run-1",
        project="harness",
        component="schema-diff",
        git_sha="abc123",
        dataset_id="large-demo-data-2-7-0",
        dataset_version="2.7.0",
        schema_mapping_version="v0",
        gen_ai_system="lmstudio",
    )
    write_manifest(manifest_path, manifest)
    append_event(events_path, {"event_type": "run"})

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["otel"]["gen_ai.system"] == "lmstudio"
    event_line = events_path.read_text(encoding="utf-8").strip()
    assert '"event_type":"run"' in event_line
