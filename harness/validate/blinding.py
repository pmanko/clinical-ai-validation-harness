"""Blind judging: the judge scores lettered answers, one scenario per session.

``blind_cells`` turns the judge cells of one run into per-scenario bundles whose arms are
letters (A, B, C, shuffled per scenario with a seed from the run id), plus the map that
``judge-finalize`` uses to put the real ``backend_id`` back. The judge never reads the map,
so an arm's name or its neighbours' answers cannot steer a score. Everything else on a cell
stays as it is: the judge still needs to know whether a cell carries In-Depth material.
"""
from __future__ import annotations

import hashlib
import json
import random
import string
from pathlib import Path
from typing import Any

MAP_SCHEMA = "judge_blind.v1"
MAP_FILE = "judge-blind-map.json"
BUNDLES_DIR = "judge-bundles"


def blind_cells(cells: list[dict[str, Any]], run_id: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Per-scenario bundles with lettered arms, and the map from letters back to arms.

    The shuffle is seeded by the run id and the scenario id, so the same run blinds the same
    way every time it is prepared, and a bundle's letters say nothing about the arms' order
    in the run's configuration."""
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        by_scenario.setdefault(cell["scenario_id"], []).append(cell)
    bundles: dict[str, list[dict[str, Any]]] = {}
    scenarios: dict[str, dict[str, str]] = {}
    for scenario_id, rows in sorted(by_scenario.items()):
        arms = sorted({r["backend_id"] for r in rows})
        if len(arms) > len(string.ascii_uppercase):
            raise ValueError(f"{scenario_id}: more arms than letters")
        seed = int(hashlib.sha256(f"{run_id}:{scenario_id}".encode()).hexdigest()[:16], 16)
        letters = list(string.ascii_uppercase[:len(arms)])
        random.Random(seed).shuffle(letters)
        letter_of = dict(zip(arms, letters))
        scenarios[scenario_id] = {letter: arm for arm, letter in letter_of.items()}
        bundle = []
        for r in sorted(rows, key=lambda r: letter_of[r["backend_id"]]):
            bundle.append({**r, "backend_id": letter_of[r["backend_id"]], "blinded": True})
        bundles[scenario_id] = bundle
    return bundles, {"schema_version": MAP_SCHEMA, "run_id": run_id, "scenarios": scenarios}


def write_bundles(run_dir: Path | str, cells: list[dict[str, Any]], run_id: str) -> list[Path]:
    """Write ``judge-bundles/<scenario>.jsonl`` and ``judge-blind-map.json`` beside the cells."""
    run_dir = Path(run_dir)
    bundles, blind_map = blind_cells(cells, run_id)
    out_dir = run_dir / BUNDLES_DIR
    out_dir.mkdir(exist_ok=True)
    for stale in out_dir.glob("*.jsonl"):
        stale.unlink()
    paths = []
    for scenario_id, rows in bundles.items():
        path = out_dir / f"{scenario_id}.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        paths.append(path)
    (run_dir / MAP_FILE).write_text(json.dumps(blind_map, indent=2) + "\n", encoding="utf-8")
    return paths


def load_map(run_dir: Path | str) -> dict[str, dict[str, str]]:
    """The letter-to-arm map per scenario, or empty when the run was not blinded."""
    path = Path(run_dir) / MAP_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scenarios = data.get("scenarios") if isinstance(data, dict) else None
    return scenarios if isinstance(scenarios, dict) else {}


def unblind_rows(rows: list[dict[str, Any]], blind_map: dict[str, dict[str, str]]) -> tuple[list[dict[str, Any]], int]:
    """Rows with their letters replaced by the arms the map names; a row whose backend_id is
    already an arm, or whose scenario the map does not know, is returned as it is. Returns
    the rows and how many were mapped back."""
    out, mapped = [], 0
    for r in rows:
        letters = blind_map.get(str(r.get("scenario_id")), {}) if isinstance(r, dict) else {}
        arm = letters.get(str(r.get("backend_id"))) if isinstance(r, dict) else None
        if arm:
            r = {**r, "backend_id": arm}
            mapped += 1
        out.append(r)
    return out, mapped
