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
from harness.wahs.evaluator import (
    WahsEvalCase,
    WahsHubClient,
    run_wahs_suite,
    score_wahs_run,
)


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
        "x_wahs": {
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
    assert "citation_map" not in slim1["x_wahs"]
    assert slim1["x_wahs"]["note"] == "keep-small-meta"
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
    assert full1["x_wahs"]["citation_map"]["1"]["uuid"] == "u-101"

    # Legacy inline fat rows pass through unmodified.
    fat = _heavy_envelope("Legacy inline answer [1].")
    assert rehydrate_response_envelope(run_dir, fat, cache=cache) == fat


def test_wahs_profile_suite_isolates_failures_resumes_and_non_destructively_scores(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "case_id": "c_ok",
                        "patient_id": "pat_ok",
                        "use_case": "qa",
                        "prompt": "What medication is active?",
                        "target_token_budgets": [8192],
                        "expected_uuids": ["u-101"],
                        "expected_facts": ["Lisinopril"],
                    }
                ),
                json.dumps(
                    {
                        "case_id": "c_fail",
                        "patient_id": "pat_ok",
                        "use_case": "qa",
                        "prompt": "Second question?",
                        "target_token_budgets": [8192],
                        "expected_uuids": ["u-101"],
                        "expected_facts": ["Lisinopril"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    class MixedClient:
        def __init__(self, fail_second: bool) -> None:
            self.fail_second = fail_second
            self.calls: list[str] = []

        def evaluate_case(self, case: WahsEvalCase, **_kw: Any) -> dict[str, Any]:
            self.calls.append(case.case_id)
            if self.fail_second and case.case_id == "c_fail":
                raise RuntimeError("wahs-engine failed [500] for c_fail: transient error")
            return _heavy_envelope(f"Answer for {case.case_id} uses Lisinopril [1].")

    out_dir = tmp_path / "runs"
    res1 = run_wahs_suite(
        cases_path,
        client=MixedClient(fail_second=True),
        output_dir=out_dir,
        profiles=["wahs-engine-chart:ollama/gemma4:e4b@16k"],
    )
    rdir1 = Path(res1.run_dir)
    assert res1.total_cells == 2

    # Eager chart & scenario inputs exist before wahs report / score runs.
    assert (rdir1 / "inputs" / "charts" / "c_ok.json").is_file()
    assert (rdir1 / "inputs" / "scenarios" / "c_ok.json").is_file()
    assert (rdir1 / "inputs" / "contexts").is_dir()

    # events.jsonl records cells upfront.
    ev_rows = [
        json.loads(line)
        for line in (rdir1 / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    run_ev = next(e for e in ev_rows if e.get("event_type") == "run")
    assert len(run_ev["cells"]) == 2

    # results.jsonl stayed compact (slim context_ref) and recorded http_status=500 for c_fail.
    res_path = rdir1 / "results.jsonl"
    raw_lines = [line for line in res_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(raw_lines) == 2
    assert all(len(line.encode("utf-8")) < 4096 for line in raw_lines)
    rows = [json.loads(line) for line in raw_lines]
    fail_row = next(r for r in rows if r["case_id"] == "c_fail")
    assert fail_row["metrics"]["http_status"] == 500

    # review_results transparently rehydrates context_ref rows.
    reviewed = review_results(rdir1, strict=True)
    ok_rev = next(r for r in reviewed if r["case_id"] == "c_ok")
    assert ok_rev["response"]["mappings"][0]["resourceUuid"] == "u-101"

    # score_wahs_run must NOT rewrite results.jsonl inode or bytes.
    before_stat = os.stat(res_path)
    before_bytes = res_path.read_bytes()
    score_summary = score_wahs_run(rdir1)
    after_stat = os.stat(res_path)
    assert after_stat.st_ino == before_stat.st_ino
    assert res_path.read_bytes() == before_bytes
    assert score_summary["incomplete"] is True

    # Resume re-runs only c_fail and carries over c_ok.
    recovered = MixedClient(fail_second=False)
    res2 = run_wahs_suite(
        cases_path,
        client=recovered,
        output_dir=out_dir,
        profiles=["wahs-engine-chart:ollama/gemma4:e4b@16k"],
        resume_from=rdir1,
    )
    assert recovered.calls == ["c_fail"]
    assert res2.passed_cells == 2


def test_wahs_hub_client_retries_http_500(tmp_path: Path) -> None:
    (tmp_path / "p1.json").write_text(
        json.dumps({"resourceType": "Bundle", "type": "collection", "entry": []}),
        encoding="utf-8",
    )
    chat_calls = 0

    class _FakeResp:
        def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.text = json.dumps(self._payload)

        def json(self) -> dict[str, Any]:
            return self._payload

    class _FakeSession:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def post(self, url: str, json: dict[str, Any], timeout: float) -> _FakeResp:  # noqa: A002
            nonlocal chat_calls
            if url.endswith("/context/preview"):
                return _FakeResp(
                    200,
                    {"condensed_text": "[1] Lisinopril", "citation_map": {}, "condensation": {}},
                )
            chat_calls += 1
            if chat_calls == 1:
                return _FakeResp(500, {"detail": "transient gpu blip"})
            return _FakeResp(
                200,
                {
                    "choices": [{"message": {"content": "Lisinopril active [1]."}}],
                    "x_wahs": {"condensation": {"actual_tokens": 120}, "timings": {"llm_rounds": 1}},
                },
            )

        def get(self, url: str, timeout: float) -> _FakeResp:
            return _FakeResp(200, {})

    client = WahsHubClient(
        base_url="http://127.0.0.1:18088",
        session=_FakeSession(),
        max_retries=2,
        retry_backoff_s=0.0,
        bundle_dirs=[tmp_path],
    )
    case = WahsEvalCase(
        case_id="c1",
        patient_id="p1",
        use_case="qa",
        prompt="Question?",
        target_token_budgets=[8192],
    )
    env = client.evaluate_case(
        case,
        budget_tokens=8192,
        profile_id="wahs-engine-chart:ollama/gemma4:e4b@16k",
    )
    assert chat_calls == 2
    assert "Lisinopril" in env["answer"]


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


def test_write_dashboard_data_sharding_threshold_and_inline_roundtrip(tmp_path: Path) -> None:
    run_dir = tmp_path / "shard_run"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "run",
                "run_id": "shard_run",
                "backend_ids": ["arm-a", "arm-b"],
                "scenario_ids": ["s1", "s2"],
                "cells": [
                    {"scenario_id": s, "backend_id": b, "turns": 1}
                    for b in ("arm-a", "arm-b")
                    for s in ("s1", "s2")
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    slim = slim_response_envelope(run_dir, "s1", "p", _heavy_envelope("ok [1]."))
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for b in ("arm-a", "arm-b"):
            for s in ("s1", "s2"):
                fh.write(
                    json.dumps(
                        {
                            "run_id": "shard_run",
                            "scenario_id": s,
                            "backend_id": b,
                            "turn": 1,
                            "request": {"patient": "p", "question": "Q?"},
                            "response": slim,
                            "metrics": {"http_status": 200, "latency_ms": 50, "answer_chars": 8, "citation_count": 1},
                        }
                    )
                    + "\n"
                )

    out_sharded = write_dashboard_data(run_dir, shard_threshold=3)
    sharded_payload = json.loads(out_sharded.read_text(encoding="utf-8"))
    assert sharded_payload["details"] == {}
    assert set(sharded_payload["detail_shards"].keys()) == {"arm-a", "arm-b"}
    for b, rel in sharded_payload["detail_shards"].items():
        shard_obj = json.loads((run_dir / rel).read_text(encoding="utf-8"))
        assert set(shard_obj.keys()) == {f"s1|{b}", f"s2|{b}"}

    # Below threshold removes dashboard-details/ and restores inline details.
    out_inline = write_dashboard_data(run_dir, shard_threshold=100)
    inline_payload = json.loads(out_inline.read_text(encoding="utf-8"))
    assert "detail_shards" not in inline_payload
    assert len(inline_payload["details"]) == 4
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
    missing = {"answer": "x", "context_ref": "nonexistent_sha"}
    assert rehydrate_response_envelope(run_dir, missing)["context_ref"] == "nonexistent_sha"

    vd = _load_validate_dashboard()
    runs_root = tmp_path / "dash_runs"
    cold_run = runs_root / "run-cold"
    cold_run.mkdir(parents=True)
    (cold_run / "run_manifest.json").write_text(
        json.dumps({"family": "wahs", "total_cells": 3}), encoding="utf-8"
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
