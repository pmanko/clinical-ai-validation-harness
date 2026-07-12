import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "summarize-local-performance.py"
SPEC = importlib.util.spec_from_file_location("summarize_local_performance", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_proof = MODULE.build_proof


def _trace_line(timestamp, profile, timing):
    overhead = timing["answer_to_done_ms"] - timing["answer_stage_ms"]
    return json.dumps(
        {
            "ts": timestamp,
            "level_id": profile,
            "question": "When was the latest visit?",
            "context": {"sources": ["querystore"]},
            "steps": [
                {"role": "stage_timing", "stage": "context", "occurrence": 1, "duration_ms": overhead, "status": "completed"},
                {"role": "stage_timing", "stage": "answer", "occurrence": 1, "duration_ms": timing["answer_stage_ms"], "status": "completed"},
                {"role": "stage_timing", "stage": "resolve_refs", "occurrence": 1, "duration_ms": 0, "status": "completed"},
            ],
        }
    )


def test_build_proof_uses_relative_warm_measurements_without_absolute_threshold(tmp_path):
    trace = tmp_path / "trace.jsonl"
    rows = [
        _trace_line(
            "2026-07-10T00:00:00Z",
            "single-e4b-checked",
            {
                "answer_to_done_ms": 12000,
                "answer_stage_ms": 10000,
                "pipeline_overhead_ms": 2000,
                "pipeline_overhead_ratio": 0.1667,
            },
        ),
        _trace_line(
            "2026-07-10T00:01:00Z",
            "single-e4b-checked",
            {
                "answer_to_done_ms": 20000,
                "answer_stage_ms": 15000,
                "pipeline_overhead_ms": 5000,
                "pipeline_overhead_ratio": 0.25,
            },
        ),
    ]
    trace.write_text("\n".join(rows) + "\n", encoding="utf-8")

    proof = build_proof(trace, "single-e4b-checked", 10)

    assert proof["acceptance_model"] == "relative_observation"
    assert proof["fixed_latency_threshold"] is None
    assert proof["measurement_scope"] == "warm_answer_done"
    assert proof["cold_start_measured"] is False
    assert proof["summary"]["answer_to_done_ms"]["median"] == 16000
    assert proof["summary"]["pipeline_overhead_ratio"]["median"] == pytest.approx(
        0.20835
    )


def test_build_proof_can_filter_synthetic_inline_warmups(tmp_path):
    trace = tmp_path / "trace.jsonl"
    base_timing = {
        "answer_to_done_ms": 12000,
        "answer_stage_ms": 10000,
        "pipeline_overhead_ms": 2000,
        "pipeline_overhead_ratio": 0.1667,
    }
    querystore = json.loads(
        _trace_line("2026-07-10T00:00:00Z", "single-e4b-checked", base_timing)
    )
    inline = json.loads(
        _trace_line("2026-07-10T00:01:00Z", "single-e4b-checked", base_timing)
    )
    inline["context"]["sources"] = ["inline"]
    second_product = json.loads(
        _trace_line("2026-07-10T00:02:00Z", "single-e4b-checked", base_timing)
    )
    trace.write_text(
        "\n".join(json.dumps(row) for row in (querystore, inline, second_product)) + "\n",
        encoding="utf-8",
    )

    proof = build_proof(trace, "single-e4b-checked", 10, "querystore")

    assert len(proof["runs"]) == 2
    assert all(run["context_sources"] == ["querystore"] for run in proof["runs"])
    assert proof["runtime"]["context_source"] == "querystore"


def test_build_proof_requires_multiple_measurements(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        _trace_line(
            "2026-07-10T00:00:00Z",
            "single-e4b-checked",
            {
                "answer_to_done_ms": 12000,
                "answer_stage_ms": 10000,
                "pipeline_overhead_ms": 2000,
                "pipeline_overhead_ratio": 0.1667,
            },
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="at least two"):
        build_proof(trace, "single-e4b-checked", 10)


def test_build_proof_can_filter_a_repeatable_measurement_question(tmp_path):
    trace = tmp_path / "trace.jsonl"
    timing = {
        "answer_to_done_ms": 12000,
        "answer_stage_ms": 10000,
        "pipeline_overhead_ms": 2000,
        "pipeline_overhead_ratio": 0.1667,
    }
    rows = [
        json.loads(_trace_line("2026-07-10T00:00:00Z", "single-e4b-checked", timing)),
        json.loads(_trace_line("2026-07-10T00:01:00Z", "single-e4b-checked", timing)),
        json.loads(_trace_line("2026-07-10T00:02:00Z", "single-e4b-checked", timing)),
    ]
    rows[2]["question"] = "Different live E2E question"
    trace.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    proof = build_proof(
        trace,
        "single-e4b-checked",
        10,
        question="When was the latest visit?",
    )

    assert len(proof["runs"]) == 2
    assert proof["runtime"]["question_filter"] == "When was the latest visit?"


def test_build_proof_binds_measurements_to_trace_code_config_and_model(tmp_path):
    trace = tmp_path / "trace.jsonl"
    timing = {
        "answer_to_done_ms": 12000,
        "answer_stage_ms": 10000,
        "pipeline_overhead_ms": 2000,
        "pipeline_overhead_ratio": 0.1667,
    }
    trace.write_text(
        "\n".join(
            [
                _trace_line("2026-07-10T00:00:00Z", "single-e4b-checked", timing),
                _trace_line("2026-07-10T00:01:00Z", "single-e4b-checked", timing),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model artifact")
    root = Path(__file__).parents[1]

    proof = build_proof(
        trace,
        "single-e4b-checked",
        10,
        repo_root=root,
        model_path=model,
        router_version="version: test",
    )

    provenance = proof["provenance"]
    assert len(provenance["trace_snapshot_sha256"]) == 64
    assert len(provenance["selected_runs_sha256"]) == 64
    assert len(provenance["harness"]["commit"]) == 40
    assert len(provenance["med_agent_hub"]["commit"]) == 40
    assert len(provenance["profile_config_sha256"]) == 64
    assert len(provenance["router_config_sha256"]) == 64
    assert provenance["router_version"] == "version: test"
    assert provenance["model_artifact"]["size_bytes"] == len(b"model artifact")
    assert len(provenance["model_artifact"]["sha256"]) == 64


def test_build_proof_uses_identity_captured_by_collection_manifest(tmp_path):
    trace = tmp_path / "selected.jsonl"
    timing = {
        "answer_to_done_ms": 12000,
        "answer_stage_ms": 10000,
        "pipeline_overhead_ms": 2000,
        "pipeline_overhead_ratio": 0.1667,
    }
    trace.write_text(
        "\n".join(
            [
                _trace_line("2026-07-10T00:00:00Z", "single-e4b-checked", timing),
                _trace_line("2026-07-10T00:01:00Z", "single-e4b-checked", timing),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    import hashlib

    trace_hash = hashlib.sha256(trace.read_bytes()).hexdigest()
    manifest = tmp_path / "collection.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "local_performance_collection.v1",
                "runs": 2,
                "selected_trace_sha256": trace_hash,
                "warmup": {"last_event": "answer_done"},
                "runtime_identity": {
                    "med_agent_hub": {"commit": "a" * 40, "tree_clean": True}
                },
            }
        ),
        encoding="utf-8",
    )

    proof = build_proof(
        trace,
        "single-e4b-checked",
        10,
        collection_manifest=manifest,
    )

    assert proof["provenance"]["med_agent_hub"]["commit"] == "a" * 40
    assert proof["provenance"]["warmup"]["last_event"] == "answer_done"
    assert len(proof["provenance"]["collection_manifest_sha256"]) == 64
