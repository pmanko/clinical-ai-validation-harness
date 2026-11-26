"""Tests for unified ContextStore, shared execute_cell_matrix, RunIndex, sharding, and SSE HTTP/1.1."""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from harness.validate.bundle import review_results
from harness.validate.context_store import (
    rehydrate_response_envelope,
    slim_response_envelope,
)
from harness.validate.dashboard_data import (
    build_dashboard_data,
    build_detail,
    build_status,
    write_dashboard_data,
)
from harness.validate.run_index import GLOBAL_RUN_INDEX, RunIndex
from harness.validate.runner import CellPlanItem, execute_cell_matrix


ROOT = Path(__file__).resolve().parents[1]


def _load_validate_dashboard():
    spec = importlib.util.spec_from_file_location(
        "validate_dashboard_test_mod", ROOT / "scripts" / "validate-dashboard.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _heavy_envelope(answer: str = "Patient takes Lisinopril [1].", *, uuid: str = "u-101") -> dict[str, Any]:
    mappings = [
        {
            "index": 1,
            "record_index": 1,
            "resourceType": "MedicationStatement",
            "resourceUuid": uuid,
            "display": "Lisinopril 10 MG",
            "date": "2026-01-15",
            "source_id": "Med-1",
        }
    ]
    return {
        "answer": answer,
        "condensed_text": "[1] (2026-01-15) MedicationStatement Lisinopril 10 MG\n" + ("x " * 1200),
        "mappings": mappings,
        "citation_map": {"1": {"uuid": uuid, "display": "Lisinopril 10 MG"}},
        "references": [
            {
                "index": 1,
                "record_index": 1,
                "resourceType": "MedicationStatement",
                "resourceUuid": uuid,
                "display": "Lisinopril 10 MG",
                "date": "2026-01-15",
            }
        ],
        "valid_uuids": [uuid],
        "retained_uuids": [uuid],
        "actual_tokens": 250,
        "latency_ms": 120.0,
        "x_ext": {
            "citation_map": {"1": {"uuid": uuid, "display": "Lisinopril 10 MG"}},
            "note": "keep-small-meta",
        },
    }


def test_context_store_dedupes_eagerly_writes_chart_and_rehydrates(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    env1 = _heavy_envelope("Arm A answer [1].")
    env2 = _heavy_envelope("Arm B answer [1].")

    slim1 = slim_response_envelope(run_dir, "scen_1", "pat_1", env1)
    slim2 = slim_response_envelope(run_dir, "scen_1", "pat_1", env2)
    assert slim1 is not None and slim2 is not None
    assert slim1["context_ref"] == slim2["context_ref"]
    assert "mappings" not in slim1
    assert "condensed_text" not in slim1
    assert "valid_uuids" not in slim1
    assert "retained_uuids" not in slim1
    assert "citation_map" not in slim1
    assert "citation_map" not in slim1["x_ext"]
    assert slim1["x_ext"]["note"] == "keep-small-meta"
    assert len(json.dumps(slim1)) < 4096

    ctx_files = list((run_dir / "inputs" / "contexts").glob("*.json"))
    assert len(ctx_files) == 1

    chart_path = run_dir / "inputs" / "charts" / "scen_1.json"
    assert chart_path.is_file()
    chart_obj = json.loads(chart_path.read_text(encoding="utf-8"))
    assert chart_obj["valid_uuids"] == ["u-101"]
    assert chart_obj["mappings"][0]["resourceUuid"] == "u-101"

    cache: dict[str, dict[str, Any]] = {}
    full1 = rehydrate_response_envelope(run_dir, slim1, cache=cache)
    assert full1 is not None
    assert full1["answer"] == "Arm A answer [1]."
    assert full1["mappings"][0]["resourceUuid"] == "u-101"
    assert full1["citation_map"]["1"]["uuid"] == "u-101"
    assert full1["x_ext"]["citation_map"]["1"]["uuid"] == "u-101"

    # Legacy `<ext>_citation_map` context artifact on disk rehydrates cleanly.
    legacy_ctx_id = "abcdef0123456789"
    (run_dir / "inputs" / "contexts" / f"{legacy_ctx_id}.json").write_text(
        json.dumps(
            {
                "schema": "openclinai.context.v1",
                "condensed_text": "[1] Legacy record",
                "mappings": [],
                "x_vendor_citation_map": {"1": {"uuid": "u-legacy"}},
            }
        ),
        encoding="utf-8",
    )
    legacy_rehydrated = rehydrate_response_envelope(
        run_dir,
        {"answer": "Legacy [1].", "context_ref": legacy_ctx_id, "x_vendor": {"meta": "ok"}},
    )
    assert legacy_rehydrated is not None
    assert legacy_rehydrated["x_vendor"]["citation_map"]["1"]["uuid"] == "u-legacy"

    # Legacy inline fat rows pass through unmodified.
    fat = _heavy_envelope("Legacy inline answer [1].")
    assert rehydrate_response_envelope(run_dir, fat, cache=cache) == fat


def test_execute_cell_matrix_isolates_failures_and_resumes_cleanly(tmp_path: Path) -> None:
    plan_items = [
        CellPlanItem(
            cell_key=("c_ok", "arm-a"),
            scenario_id="c_ok",
            backend_id="arm-a",
            turn=1,
            seed=None,
            payload="c_ok",
        ),
        CellPlanItem(
            cell_key=("c_fail", "arm-a"),
            scenario_id="c_fail",
            backend_id="arm-a",
            turn=1,
            seed=None,
            payload="c_fail",
        ),
    ]
    rdir1 = tmp_path / "runs" / "r1"
    rdir1.mkdir(parents=True)
    calls1: list[str] = []

    def _exec1(item: CellPlanItem) -> dict[str, Any]:
        calls1.append(str(item.payload))
        if item.payload == "c_fail":
            raise RuntimeError("service failed [503] for c_fail")
        slim = slim_response_envelope(rdir1, item.scenario_id, "pat_1", _heavy_envelope())
        return {
            "scenario_id": item.scenario_id,
            "backend_id": item.backend_id,
            "turn": 1,
            "response": slim,
            "metrics": {"http_status": 200, "latency_ms": 10},
        }

    execute_cell_matrix(
        plan_items,
        run_dir=rdir1,
        output_dir=tmp_path / "runs",
        execute_cell=_exec1,
        on_error_cell=lambda item, exc, code: {
            "scenario_id": item.scenario_id,
            "backend_id": item.backend_id,
            "turn": 1,
            "error": str(exc),
            "metrics": {"http_status": code or 500, "latency_ms": 0},
        },
        isolate_errors=True,
        events_path=rdir1 / "events.jsonl",
        run_id="r1",
    )
    reviewed = review_results(rdir1, strict=True)
    assert len(reviewed) == 2
    ok_row = next(r for r in reviewed if r["scenario_id"] == "c_ok")
    fail_row = next(r for r in reviewed if r["scenario_id"] == "c_fail")
    assert ok_row["response"]["mappings"][0]["resourceUuid"] == "u-101"
    assert fail_row["metrics"]["http_status"] == 503

    rdir2 = tmp_path / "runs" / "r2"
    rdir2.mkdir(parents=True)
    calls2: list[str] = []
    execute_cell_matrix(
        plan_items,
        run_dir=rdir2,
        output_dir=tmp_path / "runs",
        execute_cell=lambda item: (
            calls2.append(str(item.payload))
            or {
                "scenario_id": item.scenario_id,
                "backend_id": item.backend_id,
                "turn": 1,
                "response": slim_response_envelope(rdir2, item.scenario_id, "pat_1", _heavy_envelope()),
                "metrics": {"http_status": 200, "latency_ms": 12},
            }
        ),
        completed_rows={("c_ok", "arm-a"): ok_row},
        on_resume_cell=lambda _item, prior: {
            **prior,
            "response": slim_response_envelope(rdir2, prior["scenario_id"], "pat_1", prior["response"]),
        },
        events_path=rdir2 / "events.jsonl",
        run_id="r2",
    )
    assert calls2 == ["c_fail"]


def test_run_index_incremental_delta_partial_line_and_detail(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_idx"
    run_dir.mkdir()
    GLOBAL_RUN_INDEX.invalidate(run_dir)

    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "run",
                "run_id": "run_idx",
                "backend_ids": ["arm-a", "arm-b"],
                "scenario_ids": ["s1", "s2"],
                "cells": [
                    {"scenario_id": "s1", "backend_id": "arm-a", "turns": 1},
                    {"scenario_id": "s1", "backend_id": "arm-b", "turns": 1},
                    {"scenario_id": "s2", "backend_id": "arm-a", "turns": 1},
                    {"scenario_id": "s2", "backend_id": "arm-b", "turns": 1},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    res_path = run_dir / "results.jsonl"
    res_path.write_text("", encoding="utf-8")

    idx = GLOBAL_RUN_INDEX.get(run_dir)
    st0 = idx.get_status()
    assert st0["done"] == 0
    seq0 = st0["seq"]

    # Slim row written with eager inputs/charts/s1.json
    slim1 = slim_response_envelope(run_dir, "s1", "pat_1", _heavy_envelope("S1 Arm A [1]."))
    row1 = {
        "run_id": "run_idx",
        "scenario_id": "s1",
        "backend_id": "arm-a",
        "turn": 1,
        "request": {"patient": "pat_1", "question": "Q1?"},
        "response": slim1,
        "metrics": {"http_status": 200, "latency_ms": 100, "answer_chars": 15, "citation_count": 1},
    }
    with res_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row1) + "\n")

    st1 = idx.get_status(since_seq=seq0)
    assert st1["delta"] is True
    assert st1["unchanged"] is False
    assert len(st1["grid_updates"]) >= 1
    assert any(g["scenario"] == "s1" and g["backend"] == "arm-a" and g["state"] == "done" for g in st1["grid_updates"])

    st1_same = idx.get_status(since_seq=st1["seq"])
    assert st1_same["delta"] is True and st1_same["unchanged"] is True

    # Unterminated JSON fragment must be buffered cleanly until trailing newline arrives.
    row2 = {
        "run_id": "run_idx",
        "scenario_id": "s2",
        "backend_id": "arm-b",
        "turn": 1,
        "request": {"patient": "pat_1", "question": "Q2?"},
        "response": slim1,
        "metrics": {"http_status": 200, "latency_ms": 95, "answer_chars": 15, "citation_count": 1},
    }
    encoded_row2 = json.dumps(row2)
    half = len(encoded_row2) // 2
    with res_path.open("a", encoding="utf-8") as fh:
        fh.write(encoded_row2[:half])
    st_mid = idx.get_status(since_seq=st1["seq"])
    assert st_mid["done"] == 1

    with res_path.open("a", encoding="utf-8") as fh:
        fh.write(encoded_row2[half:] + "\n")
    st2 = idx.get_status(since_seq=st1["seq"])
    assert st2["done"] == 2
    assert any(g["scenario"] == "s2" and g["backend"] == "arm-b" for g in st2["grid_updates"])

    # O(1) detail lookup resolves [1] source card immediately from eager chart + rehydrated context.
    detail = idx.get_detail("s1", "arm-a")
    assert len(detail["turns"]) == 1
    assert detail["turns"][0]["sources"]["sources"][0]["record_index"] == 1


def test_write_dashboard_data_always_shards_even_for_single_cell(tmp_path: Path) -> None:
    run_dir = tmp_path / "shard_run"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "run",
                "run_id": "shard_run",
                "backend_ids": ["arm-a"],
                "scenario_ids": ["s1"],
                "cells": [{"scenario_id": "s1", "backend_id": "arm-a", "turns": 1}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    slim = slim_response_envelope(run_dir, "s1", "p", _heavy_envelope("ok [1]."))
    (run_dir / "results.jsonl").write_text(
        json.dumps(
            {
                "run_id": "shard_run",
                "scenario_id": "s1",
                "backend_id": "arm-a",
                "turn": 1,
                "request": {"patient": "p", "question": "Q?"},
                "response": slim,
                "metrics": {"http_status": 200, "latency_ms": 50, "answer_chars": 8, "citation_count": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out_sharded = write_dashboard_data(run_dir)
    sharded_payload = json.loads(out_sharded.read_text(encoding="utf-8"))
    assert sharded_payload["details"] == {}
    assert set(sharded_payload["detail_shards"].keys()) == {"arm-a"}
    shard_obj = json.loads((run_dir / sharded_payload["detail_shards"]["arm-a"]).read_text(encoding="utf-8"))
    assert set(shard_obj.keys()) == {"s1|arm-a"}

    # Custom payload handles pending backends (no shard) and undeclared detail backends cleanly.
    mixed_payload = {
        "schema": "openclinai.dashboard.v2",
        "schema_version": 2,
        "status": {"backends": ["arm-pending"]},
        "details": {"s1|arm-extra": {"turns": []}},
    }
    out_mixed = write_dashboard_data(run_dir, payload=mixed_payload)
    mixed_written = json.loads(out_mixed.read_text(encoding="utf-8"))
    assert mixed_written["details"] == {}
    assert set(mixed_written["detail_shards"]) == {"arm-extra"}

    # Empty details clears stale dashboard-details/ and emits empty detail_shards map.
    empty_payload = {
        "schema": "openclinai.dashboard.v2",
        "schema_version": 2,
        "status": {"backends": ["arm-a"]},
        "details": {},
    }
    out_empty = write_dashboard_data(run_dir, payload=empty_payload)
    empty_written = json.loads(out_empty.read_text(encoding="utf-8"))
    assert empty_written["details"] == {}
    assert empty_written["detail_shards"] == {}
    assert not (run_dir / "dashboard-details").exists()


def test_validate_dashboard_http11_runs_selector_and_sse_stream(tmp_path: Path) -> None:
    vd = _load_validate_dashboard()
    runs_root = tmp_path / "runs"
    run_a = runs_root / "run-alpha"
    run_b = runs_root / "run-beta"
    for rdir, rid in ((run_a, "run-alpha"), (run_b, "run-beta")):
        rdir.mkdir(parents=True)
        (rdir / "events.jsonl").write_text(
            json.dumps(
                {
                    "event_type": "run",
                    "run_id": rid,
                    "backend_ids": ["arm-1"],
                    "scenario_ids": ["s1"],
                    "cells": [{"scenario_id": "s1", "backend_id": "arm-1", "turns": 1}],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (rdir / "results.jsonl").write_text(
            json.dumps(
                {
                    "run_id": rid,
                    "scenario_id": "s1",
                    "backend_id": "arm-1",
                    "turn": 1,
                    "request": {"question": "Q?"},
                    "response": {"answer": f"Answer from {rid}"},
                    "metrics": {"http_status": 200, "latency_ms": 10, "answer_chars": 15, "citation_count": 0},
                }
            )
            + "\n",
            encoding="utf-8",
        )

    vd._WATCH_OUTPUT_DIRS.add(str(runs_root))
    srv = vd._Server(("127.0.0.1", 0), vd.H)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/runs")
        r1 = conn.getresponse()
        assert r1.status == 200
        runs_data = json.loads(r1.read().decode("utf-8"))
        ids = {r["run_id"] for r in runs_data["runs"]}
        assert {"run-alpha", "run-beta"} <= ids

        # Same keep-alive HTTP/1.1 connection can query specific ?run= and reject un-discovered paths
        conn.request("GET", "/api/detail?scenario=s1&backend=arm-1&run=run-alpha")
        r2 = conn.getresponse()
        assert r2.status == 200
        det = json.loads(r2.read().decode("utf-8"))
        assert det["turns"][0]["answer"] == "Answer from run-alpha"

        conn.request("GET", "/api/status?run=/etc/passwd")
        r3 = conn.getresponse()
        assert r3.status == 200
        assert json.loads(r3.read().decode("utf-8"))["run"] is None
        conn.close()

        # SSE /api/stream pushes event: status frame
        sse_conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        sse_conn.request("GET", "/api/stream?run=run-beta")
        sse_resp = sse_conn.getresponse()
        assert sse_resp.status == 200
        assert "text/event-stream" in sse_resp.getheader("Content-Type", "")
        chunk_lines: list[str] = []
        while True:
            line = sse_resp.fp.readline().decode("utf-8")
            chunk_lines.append(line)
            if line == "\n" or not line:
                break
        frame = "".join(chunk_lines)
        assert "event: status" in frame
        data_line = next(l for l in chunk_lines if l.startswith("data: "))
        sse_payload = json.loads(data_line[len("data: "):])
        assert sse_payload["run"] == "run-beta"
        assert sse_payload["done"] == 1
        sse_conn.close()
    finally:
        vd._WATCH_OUTPUT_DIRS.discard(str(runs_root))
        srv.shutdown()
        srv.server_close()


def test_run_index_resets_on_truncation_deletion_and_malformed_lines(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_edge"
    comp_dir = run_dir / "inputs" / "comparison_sets"
    comp_dir.mkdir(parents=True)
    (comp_dir / "bad.json").write_text("{not json", encoding="utf-8")
    (comp_dir / "good.json").write_text(json.dumps({"transport": "rest-v2"}), encoding="utf-8")
    (run_dir / "run_meta.json").write_text("{broken meta", encoding="utf-8")
    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "run",
                "run_id": "run_edge",
                "backend_ids": ["arm-a"],
                "scenario_ids": ["s1"],
                "cells": [{"scenario_id": "s1", "backend_id": "arm-a", "turns": 1}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    slim = slim_response_envelope(run_dir, "s1", "pat_99", _heavy_envelope("Ok [1]."))
    slim_in = slim_response_envelope(run_dir, "s1", "pat_99", _heavy_envelope("In [1]."))
    row = {
        "run_id": "run_edge",
        "scenario_id": "s1",
        "backend_id": "arm-a",
        "patient_id": "pat_99",
        "turn": 1,
        "request": {"question": "Q?"},
        "response": slim,
        "indepth": {"response": slim_in},
        "metrics": {"http_status": 200, "latency_ms": 12, "answer_chars": 7, "citation_count": 1},
    }
    res_path = run_dir / "results.jsonl"
    res_path.write_text(
        "\n{not-json}\n[]\n" + json.dumps(row) + "\n",
        encoding="utf-8",
    )

    # Empty scenario/backend short-circuits cleanly.
    idx = RunIndex(run_dir)
    assert idx.get_detail("", "arm-a") == {"turns": []}
    det = idx.get_detail("s1", "arm-a")
    assert det["turns"][0]["answer"] == "Ok [1]."
    assert det["turns"][0]["sources"]["sources"][0]["record_index"] == 1

    # review_results also populates patient_id, transport, and rehydrates indepth.response.
    (run_dir / "run_meta.json").write_text("{}", encoding="utf-8")
    rev = review_results(run_dir, strict=False)
    assert rev[0]["request"]["patient"] == "pat_99"
    assert rev[0]["request"]["transport"] == "rest-v2"
    assert rev[0]["indepth"]["response"]["answer"] == "In [1]."

    # Shrinking results.jsonl triggers clean index reset; removing it resets to 0.
    res_path.write_text("{bad\n", encoding="utf-8")
    assert idx.get_status()["done"] == 0
    res_path.unlink()
    assert idx.get_status()["done"] == 0


def test_context_store_edge_guards_and_dashboard_discovery_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "ctx_edge"
    assert slim_response_envelope(run_dir, "s1", None, None) is None
    assert rehydrate_response_envelope(run_dir, None) is None
    missing = {"answer": "x", "context_ref": "deadbeef01234567"}
    assert rehydrate_response_envelope(run_dir, missing)["context_ref"] == "deadbeef01234567"

    with pytest.raises(ValueError, match="context_ref"):
        rehydrate_response_envelope(run_dir, {"answer": "x", "context_ref": "../../etc/passwd"})
    with pytest.raises(ValueError, match="context_ref"):
        slim_response_envelope(run_dir, "s1", None, {"answer": "x", "context_ref": "../escape"})
    with pytest.raises(ValueError, match="scenario_id"):
        slim_response_envelope(run_dir, "../escape", "p", _heavy_envelope("ok [1]."))
    with pytest.raises(ValueError, match="scenario_id"):
        slim_response_envelope(run_dir, "..", "p", {"answer": "x", "context_ref": "deadbeef01234567"})

    # Symlink escape inside inputs/contexts must be rejected by resolve().is_relative_to().
    outside_secret = tmp_path / "outside_secret.json"
    outside_secret.write_text('{"condensed_text": "secret"}', encoding="utf-8")
    contexts_dir = run_dir / "inputs" / "contexts"
    contexts_dir.mkdir(parents=True, exist_ok=True)
    symlink_ctx = contexts_dir / "0123456789abcdef.json"
    symlink_ctx.symlink_to(outside_secret)
    with pytest.raises(ValueError, match="escapes"):
        rehydrate_response_envelope(run_dir, {"answer": "x", "context_ref": "0123456789abcdef"})

    vd = _load_validate_dashboard()
    runs_root = tmp_path / "dash_runs"
    cold_run = runs_root / "run-cold"
    cold_run.mkdir(parents=True)
    (cold_run / "run_manifest.json").write_text(
        json.dumps({"family": "clinical_qa", "total_cells": 3}), encoding="utf-8"
    )
    (cold_run / "summary.json").write_text("{corrupt", encoding="utf-8")
    empty_run = runs_root / "run-empty"
    empty_run.mkdir()

    monkeypatch.setattr(vd, "_RUN_OVERRIDE", str(cold_run))
    monkeypatch.setattr(vd, "_WATCH_OUTPUT_DIRS", {str(runs_root)})
    monkeypatch.setattr(vd, "_WATCH_ARTIFACTS_DIRS", set())
    monkeypatch.setattr(vd, "_WATCH_RUN_DIRS", set())

    GLOBAL_RUN_INDEX.invalidate(cold_run)
    assert vd.resolve_run("   ") == str(cold_run)
    discovered = {r["run_id"]: r for r in vd.discover_runs()}
    assert discovered["run-cold"]["expected"] == 3
    assert discovered["run-empty"]["completed"] == 0

    # Invalid since_seq and empty SSE stream shutdown are handled gracefully.
    srv = vd._Server(("127.0.0.1", 0), vd.H)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/status?since_seq=notanint")
        r = conn.getresponse()
        assert r.status == 200
        assert json.loads(r.read().decode("utf-8"))["run"] == "run-cold"
        conn.close()

        # When _discover_run_dirs finds nothing, /api/stream still emits initial empty status.
        monkeypatch.setattr(vd, "_RUN_OVERRIDE", None)
        monkeypatch.setattr(vd, "_discover_run_dirs", lambda: [])
        sse_conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        sse_conn.request("GET", "/api/stream")
        sse_resp = sse_conn.getresponse()
        assert sse_resp.status == 200
        line = sse_resp.fp.readline().decode("utf-8")
        assert line.startswith("id: 0")
        sse_conn.close()
    finally:
        srv.shutdown()
        srv.server_close()
