"""Tests for scripts/validate-dashboard.py data builders — status() feed + detail().

The dashboard serves these two JSON payloads to its frontend; the bug-prone parts are the
two-call In-Depth fields. status()'s feed must surface indepth_status + indepth_chars
(including when the nested in-depth response is a JSON *string* that needs parsing), and
detail() must nest the In-Depth as its own {answer,status,latency_ms} block — or None when
the arm shipped no in-depth. The run is pinned via DASH_RUN to a tmp fixture containing
frozen inputs, metadata and traces. Loaded by path via importlib.
"""

from __future__ import annotations

import importlib.util
import json

from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "validate-dashboard.py"


def _load():
    assert _MOD_PATH.exists(), "scripts/validate-dashboard.py missing"
    spec = importlib.util.spec_from_file_location("validate_dashboard", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _setup_run(tmp_path: Path, vd, monkeypatch, *, results: list[dict],
               scenarios=("s1",), backends=("b1",), scen_turns=1):
    """Write a fixture run dir + scenario files; pin the dashboard to it via DASH_RUN."""
    run_dir = tmp_path / "artifacts" / "validate" / "run-x"
    run_dir.mkdir(parents=True)
    events = [{"event_type": "run", "comparison_set": "cs",
               "scenario_ids": list(scenarios), "backend_ids": list(backends)}]
    events += [{"event_type": "backend_selected", "backend_id": b, "label": f"Label {b}"}
               for b in backends]
    (run_dir / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")

    data_dir = run_dir / "inputs"
    (data_dir / "scenarios").mkdir(parents=True)
    (data_dir / "charts").mkdir()
    for s in scenarios:
        (data_dir / "scenarios" / f"{s}.json").write_text(
            json.dumps({"id": s, "patient_ref": "p",
                        "turns": [{"n": i + 1} for i in range(scen_turns)],
                        "expectations": {"should_abstain": False}}), encoding="utf-8")
    (data_dir / "charts" / "p.json").write_text(json.dumps({
        "patient": {"uuid": "p", "slug": "p"},
        "chart_snapshot": "Patient: 40F\n[1] Weight: 70 kg",
        "valid_uuids": ["u1"],
        "mappings": [{"index": 1, "resourceType": "obs", "resourceUuid": "u1"}],
    }), encoding="utf-8")
    (run_dir / "run_meta.json").write_text(json.dumps({
        "backends": {b: {"modelName": f"captured-{b}"} for b in backends},
        "arm_cards": {b: {"backend_id": b, "kind": "single", "config": {},
                          "models": [{"id": f"captured-{b}"}]} for b in backends},
    }), encoding="utf-8")
    (run_dir / "trace.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setenv("DASH_RUN", str(run_dir))
    return run_dir


def _answer_row(sid, bid, turn, *, status=200, chars=10, indepth=None):
    row = {"scenario_id": sid, "backend_id": bid, "turn": turn,
           "request": {"patient": "p", "question": f"q{turn}"},
           "response": {"answer": "A" * chars, "references": [], "blocks": []},
           "metrics": {"http_status": status, "answer_chars": chars, "latency_ms": 100,
                       "citation_count": 0},
           "started_at": "t0", "ended_at": "t1", "error": None}
    if indepth is not None:
        row["indepth"] = indepth
    return row


# --------------------------------------------------------------------------- #
# status().feed — In-Depth fields, incl. the string-JSON parse branch
# --------------------------------------------------------------------------- #
def test_status_feed_surfaces_indepth_status_and_chars(tmp_path, monkeypatch):
    vd = _load()
    indepth = {"http_status": 200,
               "response": {"answer": "In-depth elaboration text"}, "latency_ms": 4000}
    _setup_run(tmp_path, vd, monkeypatch,
               results=[_answer_row("s1", "b1", 1, indepth=indepth)])
    st = vd.status()
    feed = st["feed"]
    assert len(feed) == 1
    f = feed[0]
    assert f["indepth_status"] == 200
    assert f["indepth_chars"] == len("In-depth elaboration text")
    assert f["status"] == 200


def test_status_feed_parses_indepth_response_when_json_string(tmp_path, monkeypatch):
    vd = _load()
    # the nested in-depth response is a JSON STRING (not a dict) -> the builder must parse it
    indepth = {"http_status": 200,
               "response": json.dumps({"answer": "parsed from a json string"}),
               "latency_ms": 3000}
    _setup_run(tmp_path, vd, monkeypatch,
               results=[_answer_row("s1", "b1", 1, indepth=indepth)])
    f = vd.status()["feed"][0]
    assert f["indepth_chars"] == len("parsed from a json string")


def test_status_feed_no_indepth_keeps_fields_null(tmp_path, monkeypatch):
    vd = _load()
    _setup_run(tmp_path, vd, monkeypatch,
               results=[_answer_row("s1", "b1", 1)])  # no indepth artifact
    f = vd.status()["feed"][0]
    assert f["indepth_status"] is None
    assert f["indepth_chars"] == 0


def test_status_grid_marks_done_cell(tmp_path, monkeypatch):
    vd = _load()
    _setup_run(tmp_path, vd, monkeypatch,
               results=[_answer_row("s1", "b1", 1, status=200, chars=20)])
    st = vd.status()
    # a single-turn scenario with one good (200, >0 chars) row -> the cell is "done"
    cell = next(c for c in st["grid"] if c["scenario"] == "s1" and c["backend"] == "b1")
    assert cell["state"] == "done"
    assert st["done"] == 1
    assert st["total"] == 1


def test_status_no_run_returns_none(tmp_path, monkeypatch):
    vd = _load()
    # DASH_RUN points at an empty dir with no runs -> newest_run None
    empty = tmp_path / "artifacts" / "validate"
    empty.mkdir(parents=True)
    monkeypatch.setenv("DASH_RUN", str(tmp_path / "does-not-exist"))
    monkeypatch.setattr(vd, "ROOT", tmp_path)  # so the glob finds nothing
    assert vd.status() == {"run": None}


# --------------------------------------------------------------------------- #
# detail() — nested In-Depth block
# --------------------------------------------------------------------------- #
def test_detail_nests_indepth_block(tmp_path, monkeypatch):
    vd = _load()
    indepth = {"http_status": 200,
               "response": {"answer": "the in-depth answer"}, "latency_ms": 5500}
    _setup_run(tmp_path, vd, monkeypatch,
               results=[_answer_row("s1", "b1", 1, indepth=indepth)])
    d = vd.detail("s1", "b1")
    assert len(d["turns"]) == 1
    t = d["turns"][0]
    assert t["indepth"]["answer"] == "the in-depth answer"
    assert t["indepth"]["status"] == 200
    assert t["indepth"]["latency_ms"] == 5500
    assert t["answer"].startswith("A")  # the Answer is preserved alongside


def test_detail_uses_model_frozen_in_result_for_historical_trace(tmp_path, monkeypatch):
    vd = _load()
    row = _answer_row("s1", "historical-alias", 1)
    row["response"]["model"] = "frozen-product-profile"
    row["started_at"] = "2026-05-30T10:00:00"
    row["ended_at"] = "2026-05-30T10:00:30"
    run_dir = _setup_run(
        tmp_path,
        vd,
        monkeypatch,
        results=[row],
        backends=("historical-alias",),
    )
    # The response model outranks even the captured backend's configured model.
    traces = [{
        "level_id": model, "ts": "2026-05-30T10:00:15", "question": "q1",
        "answer_confidence": {"level": "green", "note": note},
    } for model, note in (
        ("frozen-product-profile", "observed model trace"),
        ("captured-historical-alias", "configured model trace"),
    )]
    (run_dir / "trace.jsonl").write_text(
        "".join(json.dumps(trace) + "\n" for trace in traces), encoding="utf-8")

    turn = vd.detail("s1", "historical-alias")["turns"][0]

    assert turn["trace"]["answer_confidence"]["note"] == "observed model trace"


def test_detail_indepth_is_none_when_arm_has_none(tmp_path, monkeypatch):
    vd = _load()
    _setup_run(tmp_path, vd, monkeypatch,
               results=[_answer_row("s1", "b1", 1)])  # no in-depth
    t = vd.detail("s1", "b1")["turns"][0]
    assert t["indepth"] is None


def test_detail_includes_canonical_sources_v1(tmp_path, monkeypatch):
    vd = _load()
    row = _answer_row("s1", "b1", 1)
    row["response"]["answer"] = "Weight is documented [1]."
    row["response"]["references"] = [{"index": 1, "resourceType": "obs", "resourceUuid": "u1"}]
    row["metrics"]["citation_count"] = 1
    _setup_run(tmp_path, vd, monkeypatch, results=[row])
    t = vd.detail("s1", "b1")["turns"][0]
    assert t["sources"]["schema_version"] == "sources.v1"
    assert t["sources"]["sources"][0]["record_index"] == 1
    assert t["sources"]["diagnostics"]["answer_inline_refs"] == [1]
    assert t["sources"]["sources"][0]["chart_record_index"] == 1


def test_detail_unknown_cell_is_empty(tmp_path, monkeypatch):
    vd = _load()
    _setup_run(tmp_path, vd, monkeypatch, results=[_answer_row("s1", "b1", 1)])
    # asking for a (scenario, backend) with no rows -> empty turns
    assert vd.detail("nope", "nobody")["turns"] == []
    # and a missing scenario/backend arg short-circuits
    assert vd.detail("", "b1") == {"turns": []}


def test_detail_parses_string_indepth_response(tmp_path, monkeypatch):
    vd = _load()
    # the nested in-depth response is a JSON STRING -> detail() must parse it for the answer
    indepth = {"http_status": 200,
               "response": json.dumps({"answer": "string-encoded in-depth"}),
               "latency_ms": 2200}
    _setup_run(tmp_path, vd, monkeypatch,
               results=[_answer_row("s1", "b1", 1, indepth=indepth)])
    t = vd.detail("s1", "b1")["turns"][0]
    assert t["indepth"]["answer"] == "string-encoded in-depth"


@pytest.mark.parametrize("metadata", [{}, {"backends": {"b1": {"modelName": "known-model"}}}, None])
def test_status_missing_frozen_arm_card_remains_unknown(tmp_path, monkeypatch, metadata):
    vd = _load()
    run_dir = _setup_run(tmp_path, vd, monkeypatch, results=[_answer_row("s1", "b1", 1)])
    # Missing capture stays explicit; do not invent a card from a current registry.
    if metadata is None:
        (run_dir / "run_meta.json").unlink()
    else:
        (run_dir / "run_meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    st = vd.status()
    assert st["arm_cards"] == {"b1": None}
    assert st["models"] == []
    assert st["feed"][0]["status"] == 200


def test_status_uses_frozen_cards_models_and_expected_turn_count(tmp_path, monkeypatch):
    vd = _load()
    run_dir = _setup_run(tmp_path, vd, monkeypatch,
                         results=[_answer_row("s1", "b1", 1)], scen_turns=2)
    st = vd.status()
    captured = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert st["arm_cards"] == captured["arm_cards"]
    assert st["models"] == ["captured-b1"]
    assert st["total"] == 2
    assert st["done"] == 1
    assert st["grid"][0]["state"] != "done"


def test_detail_uses_profile_frozen_in_run_meta_when_result_has_no_model(tmp_path, monkeypatch):
    vd = _load()
    row = _answer_row("s1", "historical-alias", 1)
    row["started_at"] = "2026-05-30T10:00:00"
    row["ended_at"] = "2026-05-30T10:00:30"
    run_dir = _setup_run(tmp_path, vd, monkeypatch, results=[row],
                         backends=("historical-alias",))
    trace = {"level_id": "captured-historical-alias", "ts": "2026-05-30T10:00:15",
             "question": "q1", "answer_confidence": {"level": "yellow", "note": "captured note"}}
    (run_dir / "trace.jsonl").write_text(json.dumps(trace) + "\n", encoding="utf-8")

    turn = vd.detail("s1", "historical-alias")["turns"][0]

    assert turn["trace"]["answer_confidence"] == trace["answer_confidence"]
    assert turn["answer_confidence_display"] is not None
