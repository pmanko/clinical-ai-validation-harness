from __future__ import annotations

import json
from pathlib import Path

from harness.validate.dataset_provenance import build_dataset_provenance


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_build_dataset_provenance_hashes_selected_inputs_and_corpus(tmp_path: Path) -> None:
    data = tmp_path / "datasets/validation"
    _write_json(
        data / "comparison_sets/mini.json",
        {"id": "mini", "scenario_ids": ["s1"], "backend_ids": ["b1"]},
    )
    _write_json(
        data / "scenarios/s1.json",
        {"id": "s1", "patient_ref": "patient-1", "turns": [{"n": 1, "question": "q"}]},
    )
    _write_json(
        data / "charts/patient.json",
        {
            "patient": {"uuid": "patient-1"},
            "chart_snapshot": "[1] 2026-01-01 Observation: Weight 40 kg",
            "mappings": [{"index": 1, "resourceUuid": "obs-1"}],
        },
    )
    _write_json(
        tmp_path / "artifacts/chartsearchai-local/corpus-provenance.json",
        {"schema_version": "validation_corpus.v1", "dump_sha256": "abc123"},
    )

    result = build_dataset_provenance(data, "mini", project_root=tmp_path)

    assert result["schema_version"] == "validation_dataset.v1"
    assert result["comparison_set"]["id"] == "mini"
    assert [row["id"] for row in result["scenarios"]] == ["s1"]
    assert result["chart_fixtures"][0]["patient_ref"] == "patient-1"
    assert len(result["chart_fixtures"][0]["ledger_sha256"]) == 64
    assert result["missing_chart_fixtures"] == []
    assert result["corpus"]["dump_sha256"] == "abc123"
    assert len(result["combined_sha256"]) == 64


def test_missing_fixture_is_recorded_without_crashing(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _write_json(
        data / "comparison_sets/mini.json",
        {"id": "mini", "scenario_ids": ["s1"], "backend_ids": ["b1"]},
    )
    _write_json(
        data / "scenarios/s1.json",
        {"id": "s1", "patient_ref": "patient-1", "turns": [{"n": 1, "question": "q"}]},
    )

    result = build_dataset_provenance(data, "mini", project_root=tmp_path)

    assert result["chart_fixtures"] == []
    assert result["missing_chart_fixtures"] == ["patient-1"]
    assert result["corpus"] is None
