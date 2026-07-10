"""Tests for scripts/judge-finalize.py — merges judge-agent semantic scores with the
deterministic citation_resolution from judge-cells.jsonl into judge.jsonl.

Pinned behaviors (each had a real correctness edge): the dict-wrapper unwrap
({result:[...]}), skipping error/empty rows (a rate-limited agent returns a row with no
`accuracy`), the temporal-axis conditional (only when has_temporal_claim), and the
team-only background block (kept only for is_team cells that shipped a background dict).
Loaded by path via importlib (hyphenated filename).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "judge-finalize.py"


def _load():
    assert _MOD_PATH.exists(), "scripts/judge-finalize.py missing"
    spec = importlib.util.spec_from_file_location("judge_finalize", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _run_with(tmp_path: Path, jf, monkeypatch, *, cells: list[dict],
              rows, capsys=None) -> list[dict]:
    """Write judge-cells.jsonl + a workflow_rows.json, run main(), return judge.jsonl rows."""
    rd = tmp_path / "run"
    rd.mkdir(exist_ok=True)
    (rd / "judge-cells.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in cells), encoding="utf-8")
    rows_path = tmp_path / "rows.json"
    rows_path.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["judge-finalize.py", str(rd), str(rows_path)])
    jf.main()
    jpath = rd / "judge.jsonl"
    return [json.loads(ln) for ln in jpath.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _cell(sid, bid, *, is_team=False, resolution=None):
    return {"scenario_id": sid, "backend_id": bid, "is_team": is_team,
            "citation_resolution": resolution or {"n_refs": 1, "n_resolved": 1,
                                                  "n_unresolved": 0, "unresolved": [], "rate": 1.0}}


def _score(sid, bid, **over):
    base = {"scenario_id": sid, "backend_id": bid, "accuracy": 8, "completeness": 7,
            "relevance": 9, "abstention_outcome": "n-a", "citation_groundedness": "supported",
            "harm": False, "note": ""}
    base.update(over)
    return base


def test_merges_citation_resolution_from_cells(tmp_path, monkeypatch):
    jf = _load()
    cells = [_cell("s1", "b1", resolution={"n_refs": 3, "n_resolved": 2, "n_unresolved": 1,
                                           "unresolved": [9], "rate": 0.667})]
    out = _run_with(tmp_path, jf, monkeypatch, cells=cells, rows=[_score("s1", "b1")])
    assert len(out) == 1
    row = out[0]
    # the deterministic citation_resolution is merged back from the cell, not the judge
    assert row["citation_resolution"]["n_unresolved"] == 1
    assert row["citation_resolution"]["rate"] == 0.667
    assert row["accuracy"] == 8 and row["harm"] is False


def test_unwraps_dict_result_wrapper(tmp_path, monkeypatch):
    jf = _load()
    cells = [_cell("s1", "b1")]
    # the workflow sometimes returns {"result": [...]} instead of a bare list
    out = _run_with(tmp_path, jf, monkeypatch, cells=cells,
                    rows={"result": [_score("s1", "b1")]})
    assert len(out) == 1
    assert out[0]["scenario_id"] == "s1"


def test_skips_error_and_empty_rows(tmp_path, monkeypatch):
    jf = _load()
    cells = [_cell("s1", "b1"), _cell("s2", "b1"), _cell("s3", "b1")]
    rows = [
        _score("s1", "b1"),                                  # good
        {"scenario_id": "s2", "backend_id": "b1", "_error": "rate limited"},  # error row
        {"scenario_id": "s3", "backend_id": "b1"},           # empty (no accuracy) -> re-judge
    ]
    out = _run_with(tmp_path, jf, monkeypatch, cells=cells, rows=rows)
    # only the one fully-scored row is written; the error + empty rows are skipped
    assert [(r["scenario_id"], r["backend_id"]) for r in out] == [("s1", "b1")]


def test_temporal_axes_only_when_claim_made(tmp_path, monkeypatch):
    jf = _load()
    cells = [_cell("s1", "b1"), _cell("s2", "b1")]
    rows = [
        _score("s1", "b1", has_temporal_claim=True, temporal_date_accuracy="minor",
               temporal_window="ok", temporal_trend="ok"),
        _score("s2", "b1"),  # no temporal claim
    ]
    out = {(_r["scenario_id"]): _r for _r in
           _run_with(tmp_path, jf, monkeypatch, cells=cells, rows=rows)}
    # the temporal cell carries the temporal_* axes...
    assert out["s1"]["temporal_date_accuracy"] == "minor"
    assert "temporal_window" in out["s1"]
    # ...the non-temporal cell omits them entirely (so reconcile won't penalize phantom claims)
    assert "temporal_date_accuracy" not in out["s2"]
    assert "temporal_trend" not in out["s2"]


def test_background_kept_only_for_team_cells(tmp_path, monkeypatch):
    jf = _load()
    cells = [_cell("s1", "team", is_team=True), _cell("s2", "single", is_team=False)]
    bg = {"support": 8, "added_value": 7, "no_new_harm": "ok", "conciseness": "ok",
          "n_background": 1}
    rows = [
        _score("s1", "team", background=bg),
        _score("s2", "single", background=bg),  # background present but cell is NOT a team
    ]
    out = {r["backend_id"]: r for r in
           _run_with(tmp_path, jf, monkeypatch, cells=cells, rows=rows)}
    # team cell keeps the background block...
    assert out["team"]["background"] == bg
    # ...the single (non-team) cell drops it even though the judge supplied one
    assert "background" not in out["single"]


def test_missing_cell_gets_default_citation_resolution(tmp_path, monkeypatch):
    jf = _load()
    # a scored row with NO matching judge-cells entry -> default zero resolution, still written
    out = _run_with(tmp_path, jf, monkeypatch, cells=[], rows=[_score("s9", "bX")])
    assert len(out) == 1
    assert out[0]["citation_resolution"] == {
        "n_refs": 0, "n_resolved": 0, "n_unresolved": 0, "unresolved": [], "rate": None}


def test_run_dir_resolves_id_and_exits_on_missing(tmp_path, monkeypatch):
    jf = _load()
    art = tmp_path / "artifacts" / "validate" / "rid"
    art.mkdir(parents=True)
    monkeypatch.setattr(jf, "ROOT", tmp_path)
    assert jf.run_dir("rid") == art
    assert jf.run_dir(str(art)) == art
    with pytest.raises(SystemExit):
        jf.run_dir("ghost-run")


def test_main_usage_guard_exits_without_two_args(tmp_path, monkeypatch):
    jf = _load()
    monkeypatch.setattr("sys.argv", ["judge-finalize.py", "only-one-arg"])
    with pytest.raises(SystemExit):
        jf.main()


def test_output_is_sorted_by_scenario_then_backend(tmp_path, monkeypatch):
    jf = _load()
    cells = [_cell("s2", "b1"), _cell("s1", "b2"), _cell("s1", "b1")]
    rows = [_score("s2", "b1"), _score("s1", "b2"), _score("s1", "b1")]
    out = _run_with(tmp_path, jf, monkeypatch, cells=cells, rows=rows)
    keys = [(r["scenario_id"], r["backend_id"]) for r in out]
    assert keys == [("s1", "b1"), ("s1", "b2"), ("s2", "b1")]
