"""WS1 per-run capture layer: a run freezes each arm's resolved config into
`run_meta.json` so a report renders the config the run ACTUALLY used (provenance),
not whatever the static files (llama-router.ini / levels.yaml / backends.json) say
at render time.

Two contracts pinned here:
  - the runner writes run_meta.json carrying arm_cards keyed by backend_id, each with
    a `config` block (knobs/prompts/retrieval) frozen at run time;
  - the report blob PREFERS run_meta.json's frozen arm_cards when the file exists, and
    falls back to live model_registry.arm_card resolution byte-for-byte when it doesn't
    (so every existing run + the e2e suite are unaffected).
"""

from __future__ import annotations

import json
from pathlib import Path

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
    backends = ["12b-baseline", "med-agent-team-med-liquid"]

    runner.write_run_meta(
        run_dir, run_id="run-A", backend_ids=backends, reference_date="2026-01-01")

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
        run_dir, run_id="run-N", backend_ids=["12b-baseline"], reference_date=None)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["reference_date"] is None


def test_blob_prefers_frozen_arm_cards_when_run_meta_present(tmp_path):
    """When run_meta.json exists, the report blob USES its frozen arm_cards rather than
    re-resolving from the current static files."""
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
    assert blob["arm_cards"]["12b-baseline"]["title"] == "FROZEN TITLE"
    assert blob["arm_cards"]["12b-baseline"]["config"]["retrieval"]["threshold"] == 0.99


def test_blob_falls_back_to_live_resolution_without_run_meta(tmp_path):
    """No run_meta.json (every existing run) -> the blob resolves arm_cards live via
    model_registry.arm_card, byte-for-byte the prior behavior."""
    run_dir = tmp_path / "legacy"
    _write_min_run(run_dir, "12b-baseline")
    assert not (run_dir / "run_meta.json").exists()

    from harness.validate.model_registry import arm_card

    blob = report._run_blob(run_dir)
    assert blob["arm_cards"] == {"12b-baseline": arm_card("12b-baseline")}
