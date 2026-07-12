"""Freeze the authored fixtures and restored corpus identity used by a run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .corpus_alignment import canonical_ledger, ledger_sha256


def _file_entry(path: Path, root: Path, **extra: Any) -> dict[str, Any]:
    return {
        **extra,
        "path": str(path.relative_to(root)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def build_dataset_provenance(
    data_root: Path,
    comparison_set_id: str,
    *,
    project_root: Path,
) -> dict[str, Any]:
    comparison_path = data_root / "comparison_sets" / f"{comparison_set_id}.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    scenario_entries: list[dict[str, Any]] = []
    patient_ids: set[str] = set()
    for scenario_id in comparison["scenario_ids"]:
        path = data_root / "scenarios" / f"{scenario_id}.json"
        scenario = json.loads(path.read_text(encoding="utf-8"))
        patient_ids.add(str(scenario["patient_ref"]))
        scenario_entries.append(_file_entry(path, data_root, id=scenario_id))

    fixture_entries: list[dict[str, Any]] = []
    found_patients: set[str] = set()
    for path in sorted((data_root / "charts").glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        patient_ref = str((fixture.get("patient") or {}).get("uuid") or "")
        if patient_ref not in patient_ids:
            continue
        found_patients.add(patient_ref)
        ledger = canonical_ledger(
            str(fixture.get("chart_snapshot") or ""),
            list(fixture.get("mappings") or []),
        )
        fixture_entries.append(
            _file_entry(
                path,
                data_root,
                patient_ref=patient_ref,
                ledger_sha256=ledger_sha256(ledger),
            )
        )

    receipt_path = project_root / "artifacts/chartsearchai-local/corpus-provenance.json"
    corpus: dict[str, Any] | None = None
    if receipt_path.is_file():
        corpus = json.loads(receipt_path.read_text(encoding="utf-8"))
        corpus = {
            **corpus,
            "receipt_path": str(receipt_path.relative_to(project_root)),
            "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        }

    comparison_entry = _file_entry(
        comparison_path, data_root, id=comparison_set_id
    )
    identity = {
        "comparison_set": comparison_entry,
        "scenarios": scenario_entries,
        "chart_fixtures": fixture_entries,
        "missing_chart_fixtures": sorted(patient_ids - found_patients),
        "corpus_dump_sha256": (corpus or {}).get("dump_sha256"),
    }
    combined = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "validation_dataset.v1",
        **identity,
        "corpus": corpus,
        "combined_sha256": combined,
    }
