from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "analyze-citation-run.py"


def _load():
    spec = importlib.util.spec_from_file_location("analyze_citation_run", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_summarize_counts_nested_duplicates_and_mismatches(tmp_path, monkeypatch):
    mod = _load()
    data = tmp_path / "data"
    scen_dir = data / "scenarios"
    chart_dir = data / "charts"
    scen_dir.mkdir(parents=True)
    chart_dir.mkdir()
    (scen_dir / "s1.json").write_text(json.dumps({"id": "s1", "patient_ref": "p1"}), encoding="utf-8")
    (chart_dir / "p.json").write_text(json.dumps({
        "patient": {"uuid": "p1"},
        "valid_uuids": ["u1"],
        "chart_snapshot": "[1] (2026-01-26) Finding — Weight: 70 kg",
        "mappings": [{"index": 1, "resourceUuid": "u1", "resourceType": "obs"}],
    }), encoding="utf-8")
    monkeypatch.setattr(mod, "DATA", data)

    run = tmp_path / "run"
    run.mkdir()
    row = {
        "scenario_id": "s1",
        "backend_id": "b1",
        "response": {
            "answer": "See table.",
            "references": [],
            "blocks": [{
                "kind": "table",
                "title": "Weights",
                "columns": [{"key": "date", "label": "Date"}, {"key": "weight", "label": "Weight"}],
                "rows": [{"cells": {
                    "date": {"text": "2026-01-26", "refs": [1]},
                    "weight": {"text": "70 kg", "refs": [1]},
                }}],
            }],
        },
    }
    (run / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    summary = mod.summarize(run)
    assert summary["totals"]["nested_refs"] == 2
    assert summary["totals"]["unique_nested_ref_sum"] == 1
    assert summary["totals"]["cells_with_duplicated_nested_refs"] == 1
    assert summary["totals"]["cells_with_top_nested_mismatch"] == 1


def test_main_emits_text_and_json_audit(tmp_path, monkeypatch, capsys):
    mod = _load()
    data = tmp_path / "data"
    scen_dir = data / "scenarios"
    chart_dir = data / "charts"
    scen_dir.mkdir(parents=True)
    chart_dir.mkdir()
    (scen_dir / "s1.json").write_text(
        json.dumps({"id": "s1", "patient_ref": "p1"}), encoding="utf-8"
    )
    (chart_dir / "p.json").write_text(json.dumps({
        "patient": {"uuid": "p1"},
        "valid_uuids": ["u1"],
        "chart_snapshot": "[1] (2026-01-26) Finding — Weight: 70 kg",
        "mappings": [{"index": 1, "resourceUuid": "u1", "resourceType": "obs"}],
    }), encoding="utf-8")
    monkeypatch.setattr(mod, "DATA", data)

    run = tmp_path / "run"
    run.mkdir()
    row = {
        "scenario_id": "s1",
        "backend_id": "b1",
        "response": {
            "answer": "Malformed citation [abc].",
            "references": [{"index": 2}],
            "blocks": [{
                "kind": "table",
                "title": "Weights",
                "columns": [{"key": "date", "label": "Date"}],
                "rows": [{"cells": {"date": {"text": "2026-01-26", "refs": [1, 1]}}}],
            }],
        },
    }
    (run / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["analyze-citation-run.py", str(run)])
    mod.main()
    text = capsys.readouterr().out
    assert "citation/source audit" in text
    assert "dup_nested=[1]" in text
    assert "malformed=['[abc]']" in text

    monkeypatch.setattr(sys, "argv", ["analyze-citation-run.py", str(run), "--json"])
    mod.main()
    data = json.loads(capsys.readouterr().out)
    assert data["totals"]["cells"] == 1
    assert data["cells"][0]["top_only_refs"] == [2]
