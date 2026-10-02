"""Default execution must not discover workspaces or control model processes."""

import builtins
import json
import os
import subprocess
from pathlib import Path

import pytest

from harness.cli import main
from harness.validate.client import ChatResult
from harness.validate.runner import run_comparison


class Client:
    def new_session(self, patient):
        return "session"

    def chat(self, patient, session, question, *, profile=None):
        return ChatResult(
            status=200, latency_ms=1,
            envelope={"answer": "Captured answer", "model": "observed-model"},
        )


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")

    def forbidden(*args, **kwargs):
        pytest.fail("runtime attempted a workspace or process-management operation")

    for name in ("run", "Popen", "check_output", "check_call"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"harness.targets", "harness.submodules", "harness.compose",
                    "harness.validate.router_policy"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    data = tmp_path / "data"
    (data / "comparison_sets").mkdir(parents=True)
    (data / "scenarios").mkdir()
    (data / "comparison_sets" / "mini.json").write_text(json.dumps({
        "id": "mini", "scenario_ids": ["s"], "backend_ids": ["arm"],
    }))
    (data / "scenarios" / "s.json").write_text(json.dumps({
        "id": "s", "patient_ref": "patient", "turns": [{"n": 1, "question": "q"}],
    }))
    (data / "backends.json").write_text(json.dumps({
        "arm": {"label": "Configured label", "kind": "product_profile", "modelName": "configured-profile",
                "endpointUrl": "http://service/v1/chat/completions"},
    }))
    return data


@pytest.mark.parametrize("supplied", [False, True])
def test_clinical_default_path_without_git_registry_or_process_control(isolated, tmp_path, supplied):
    identity = [{"target_id": "clinical-service", "target_source": "supplied",
                 "target_actual_sha": "claimed-target-revision"}] if supplied else None
    metadata = {"arm": {"title": "Supplied model title",
                        "models": [{"id": "writer", "quant": "Q8_0"}]}} if supplied else None
    original_identity = json.loads(json.dumps(identity))
    out = run_comparison(
        comparison_set_id="mini", client=Client(), data_root=isolated,
        output_dir=tmp_path / "runs",
        **({"git_sha": "claimed-runner-revision", "target_provenance": identity,
            "arm_metadata": metadata} if supplied else {}),
    )
    manifest = json.loads(out.manifest_path.read_text())
    assert manifest["git_sha"] == ("claimed-runner-revision" if supplied else None)
    assert manifest["target_provenance"] == (identity or [])
    assert identity == original_identity
    rows = [json.loads(line) for line in out.results_path.read_text().splitlines()]
    assert rows[0]["request"]["profile"] == "configured-profile"
    assert rows[0]["response"]["model"] == "observed-model"
    card = json.loads((out.run_dir / "run_meta.json").read_text())["arm_cards"]["arm"]
    assert card["title"] == ("Supplied model title" if supplied else "Configured label")
    assert card["models"] == (metadata["arm"]["models"] if supplied else [{"id": "configured-profile"}])
    events = [json.loads(line) for line in (out.run_dir / "events.jsonl").read_text().splitlines()]
    assert all(event["event_type"] != "llama_router_policy" for event in events)
    assert all("llamaRouterModelsMax" not in event for event in events)
    assert out.report_path.is_file()
    assert not (tmp_path / ".git").exists()
    assert not (tmp_path / "targets").exists()


@pytest.mark.parametrize("command", ["schema-diff", "import-smoke"])
def test_cli_metadata_commands_without_registry_or_git(isolated, tmp_path, command, monkeypatch):
    # Schema comparison needs a configured database; isolate CLI metadata dispatch here.
    monkeypatch.setattr("harness.cli.write_schema_diff", lambda output: (output / "diff.json", output / "summary.json"))
    output = tmp_path / command
    assert main([command, "--output-dir", str(output)]) == 0
    manifest = json.loads((output / "run_manifest.json").read_text())
    assert manifest["git_sha"] is None
    assert manifest["target_provenance"] == []
    assert main([command, "--output-dir", str(output), "--git-sha", "supplied-revision"]) == 0
    assert json.loads((output / "run_manifest.json").read_text())["git_sha"] == "supplied-revision"


def test_clinical_cli_run_and_report_without_workspace(isolated, tmp_path, monkeypatch):
    monkeypatch.setattr("harness.validate.client.ChartSearchAiClient", Client)
    output = tmp_path / "runs"
    provenance = tmp_path / "identity.json"
    provenance.write_text(json.dumps([{"target_id": "service", "target_source": "supplied",
                                      "target_actual_sha": None}]))
    metadata = tmp_path / "arm-metadata.json"
    metadata.write_text(json.dumps({"arm": {"title": "Frozen title"}}))
    receipt = tmp_path / "corpus.json"
    receipt.write_text(json.dumps({"dump_sha256": "supplied-dump-digest", "source": "reviewed-corpus"}))
    from harness.metadata import utc_now_iso
    trace = {"level_id": "observed-model", "ts": utc_now_iso(), "question": "q", "session": "session"}
    trace_file = tmp_path / "trace-export.jsonl"
    trace_file.write_text(json.dumps(trace) + "\n")
    assert main([
        "validate", "run", "mini", "--data-root", str(isolated),
        "--output-dir", str(output), "--git-sha", "supplied-revision",
        "--target-provenance", str(provenance), "--arm-metadata", str(metadata),
        "--corpus-provenance", str(receipt), "--trace-file", str(trace_file),
    ]) == 0
    run_dir = next(output.iterdir())
    assert json.loads((run_dir / "run_manifest.json").read_text())["git_sha"] == "supplied-revision"
    assert json.loads((run_dir / "run_meta.json").read_text())["arm_cards"]["arm"]["title"] == "Frozen title"
    dataset = json.loads((run_dir / "run_manifest.json").read_text())["dataset_provenance"]
    assert dataset["corpus_dump_sha256"] == "supplied-dump-digest"
    assert dataset["corpus"] == json.loads(receipt.read_text())
    assert [json.loads(line) for line in (run_dir / "trace.jsonl").read_text().splitlines()] == [trace]
    assert main(["validate", "report", "--run-dir", str(run_dir)]) == 0


def test_missing_frozen_arm_cards_do_not_trigger_live_lookup(tmp_path, monkeypatch):
    from harness.validate import model_registry, report

    def forbidden(*args, **kwargs):
        pytest.fail("offline report attempted live arm resolution")

    monkeypatch.setattr(model_registry, "arm_card", forbidden)
    assert report._arm_cards_for(tmp_path, ["absent"]) == {"absent": None}
    (tmp_path / "run_meta.json").write_text(json.dumps({"arm_cards": {"present": {"title": "Frozen"}}}))
    assert report._arm_cards_for(tmp_path, ["present", "absent"]) == {
        "present": {"title": "Frozen"}, "absent": None,
    }
