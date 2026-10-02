"""Run metadata freezes supplied arm cards; reports never refresh them live."""

from __future__ import annotations

import json
import inspect
from pathlib import Path

from harness import cli
from harness.validate import report, runner


def _write_min_run(run_dir: Path, backend_id: str) -> None:
    """A minimal run dir the report blob can assemble: a manifest + one result row for
    the backend (so it appears in the blob's `backends`)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": run_dir.name, "component": "validate"}), encoding="utf-8")
    (run_dir / "results.jsonl").write_text(
        json.dumps({
            "run_id": run_dir.name, "scenario_id": "s1", "backend_id": backend_id,
            "turn": 1, "request": {"patient": "p1", "question": "q"},
            "response": {"answer": "a", "citations": [], "blocks": []},
            "metrics": {"http_status": 200, "latency_ms": 1, "citation_count": 0,
                        "first_turn": True, "json_valid": True},
            "error": None, "started_at": "2026-06-18T00:00:00Z",
            "ended_at": "2026-06-18T00:00:01Z", "reference_date": None,
        }) + "\n",
        encoding="utf-8",
    )


def test_runner_writes_run_meta_with_frozen_arm_cards(tmp_path):
    """The runner freezes each arm's FULL card — incl. the config block — into
    run_meta.json at run time."""
    run_dir = tmp_path / "run-A"
    run_dir.mkdir()
    backends = ["single-e4b-checked", "team-med-checked"]

    supplied = {bid: {"config": {"knobs": {}, "prompts": [], "retrieval": {}}}
                for bid in backends}
    runner.write_run_meta(
        run_dir, run_id="run-A", backend_ids=backends, reference_date="2026-01-01",
        arm_metadata=supplied)

    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["run_id"] == "run-A"
    assert meta["reference_date"] == "2026-01-01"
    assert meta.get("generated_at")  # an ISO8601 timestamp, non-empty
    cards = meta["arm_cards"]
    assert set(cards) == set(backends)
    for b in backends:
        # the FULL card is frozen, including the config block (knobs/prompts/retrieval)
        assert cards[b]["backend_id"] == b
        assert "config" in cards[b]
        cfg = cards[b]["config"]
        assert "knobs" in cfg and "prompts" in cfg and "retrieval" in cfg


def test_run_meta_reference_date_none_when_unset(tmp_path):
    run_dir = tmp_path / "run-N"
    run_dir.mkdir()
    runner.write_run_meta(
        run_dir, run_id="run-N", backend_ids=["single-e4b-checked"], reference_date=None)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["reference_date"] is None


def test_non_llm_run_omits_gen_ai_provider(tmp_path):
    assert (
        inspect.signature(runner.run_comparison)
        .parameters["gen_ai_provider_name"]
        .default
        is None
    )
    manifest_path, _ = cli._start_run(tmp_path, "validate")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "gen_ai.provider.name" not in manifest["otel"]


def test_comparison_provider_is_derived_from_all_arm_endpoints():
    class Backend:
        def __init__(self, endpoint_url):
            self.endpoint_url = endpoint_url

    assert runner._provider_name(
        [Backend("http://med-agent-hub:8080/v1/chat/completions")]
    ) == "med-agent-hub"
    assert runner._provider_name(
        [Backend("http://host.docker.internal:8077/v1/chat/completions")]
    ) == "llama.cpp"
    assert runner._provider_name(
        [
            Backend("http://med-agent-hub:8080/v1/chat/completions"),
            Backend("http://host.docker.internal:8077/v1/chat/completions"),
        ]
    ) == "mixed"


def test_blob_preserves_frozen_config_and_title(tmp_path):
    run_dir = tmp_path / "frozen"
    _write_min_run(run_dir, "12b-baseline")

    frozen = {
        "12b-baseline": {
            "backend_id": "12b-baseline",
            "title": "FROZEN TITLE",
            "config": {"knobs": {"frozen-marker": {"temp": "0.123"}},
                       "prompts": [], "retrieval": {"threshold": 0.99}},
        }
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps({"run_id": "frozen", "generated_at": "2026-06-18T00:00:00Z",
                    "reference_date": None, "arm_cards": frozen}),
        encoding="utf-8",
    )

    blob = report._run_blob(run_dir)
    card = blob["arm_cards"]["12b-baseline"]
    # config is FROZEN provenance — the run's actual knobs/retrieval survive verbatim
    assert card["config"]["retrieval"]["threshold"] == 0.99
    assert card["config"]["knobs"] == {"frozen-marker": {"temp": "0.123"}}
    assert card == frozen["12b-baseline"]


def test_blob_records_missing_arm_card_without_live_resolution(tmp_path):
    run_dir = tmp_path / "legacy"
    _write_min_run(run_dir, "12b-baseline")
    assert not (run_dir / "run_meta.json").exists()

    blob = report._run_blob(run_dir)
    assert blob["arm_cards"] == {"12b-baseline": None}
