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


def _blind_label(index: int) -> str:
    """Base-26 uppercase label for 0-based ``index``: A..Z, AA..AZ, BA..ZZ, ..."""
    if index < 0:
        raise ValueError(f"negative arm index: {index}")
    chars: list[str] = []
    n = index
    while True:
        n, rem = divmod(n, len(string.ascii_uppercase))
        chars.append(string.ascii_uppercase[rem])
        if n == 0:
            break
        n -= 1
    return "".join(reversed(chars))


def _validate_scenario_id(scenario_id: Any) -> str:
    """Ensure ``scenario_id`` is a single safe path component."""
    text = str(scenario_id or "")
    if (
        not text
        or text in (".", "..")
        or "/" in text
        or "\\" in text
        or "\x00" in text
        or Path(text).name != text
    ):
        raise ValueError(f"invalid scenario_id for bundle filename: {scenario_id!r}")
    return text


def blind_cells(cells: list[dict[str, Any]], run_id: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Per-scenario bundles with lettered arms, and the map from letters back to arms.

    The shuffle is seeded by the run id and the scenario id, so the same run blinds the same
    way every time it is prepared, and a bundle's letters say nothing about the arms' order
    in the run's configuration."""
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        sid = _validate_scenario_id(cell.get("scenario_id"))
        by_scenario.setdefault(sid, []).append(cell)
    bundles: dict[str, list[dict[str, Any]]] = {}
    scenarios: dict[str, dict[str, str]] = {}
    for scenario_id, rows in sorted(by_scenario.items()):
        arms = sorted({r["backend_id"] for r in rows})
        seed = int(hashlib.sha256(f"{run_id}:{scenario_id}".encode()).hexdigest()[:16], 16)
        letters = [_blind_label(i) for i in range(len(arms))]
        random.Random(seed).shuffle(letters)
        letter_of = dict(zip(arms, letters))
        scenarios[scenario_id] = {letter: arm for arm, letter in letter_of.items()}
        bundle = []
        for r in sorted(rows, key=lambda r: (len(letter_of[r["backend_id"]]), letter_of[r["backend_id"]])):
            bundle.append({**r, "backend_id": letter_of[r["backend_id"]], "blinded": True})
        bundles[scenario_id] = bundle
    return bundles, {"schema_version": MAP_SCHEMA, "run_id": run_id, "scenarios": scenarios}


def write_bundles(run_dir: Path | str, cells: list[dict[str, Any]], run_id: str) -> list[Path]:
    """Write ``judge-bundles/<scenario>.jsonl`` and ``judge-blind-map.json`` beside the cells."""
    run_dir = Path(run_dir)
    bundles, blind_map = blind_cells(cells, run_id)
    out_dir = run_dir / BUNDLES_DIR
    out_dir.mkdir(exist_ok=True)
    out_dir_resolved = out_dir.resolve()
    for stale in out_dir.glob("*.jsonl"):
        stale.unlink()
    paths = []
    for scenario_id, rows in bundles.items():
        safe_id = _validate_scenario_id(scenario_id)
        path = out_dir / f"{safe_id}.jsonl"
        if path.resolve().parent != out_dir_resolved:
            raise ValueError(f"bundle path escapes {out_dir}: {scenario_id!r}")
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        paths.append(path)
    (run_dir / MAP_FILE).write_text(json.dumps(blind_map, indent=2) + "\n", encoding="utf-8")
    return paths


def _load_cells_file(cells_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = cells_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            return []
        if isinstance(item, dict) and item.get("scenario_id") and item.get("backend_id"):
            rows.append(item)
    return rows


def validate_blind_map(
    data: Any,
    *,
    cells: list[dict[str, Any]] | None = None,
    expected_run_id: str | None = None,
    bundles_dir: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Validate a parsed ``judge-blind-map.json`` payload against schema, run, and cells."""
    if not isinstance(data, dict):
        return {}
    if data.get("schema_version") != MAP_SCHEMA:
        return {}
    map_run_id = data.get("run_id")
    if not isinstance(map_run_id, str) or not map_run_id.strip():
        return {}
    if expected_run_id and map_run_id != expected_run_id:
        return {}
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        return {}
    cleaned: dict[str, dict[str, str]] = {}
    for sid, mapping in scenarios.items():
        try:
            _validate_scenario_id(sid)
        except ValueError:
            return {}
        if not isinstance(mapping, dict) or not mapping:
            return {}
        letters: list[str] = []
        arms: list[str] = []
        for letter, arm in mapping.items():
            if not isinstance(letter, str) or not letter or not isinstance(arm, str) or not arm:
                return {}
            letters.append(letter)
            arms.append(arm)
        if len(set(letters)) != len(letters) or len(set(arms)) != len(arms):
            return {}
        cleaned[str(sid)] = {str(k): str(v) for k, v in mapping.items()}
    if cells:
        try:
            expected_bundles, expected_map = blind_cells(cells, map_run_id)
        except ValueError:
            return {}
        if cleaned != expected_map.get("scenarios"):
            return {}
        if bundles_dir is not None and bundles_dir.is_dir():
            bundle_files = sorted(bundles_dir.glob("*.jsonl"))
            if bundle_files:
                if [p.stem for p in bundle_files] != sorted(expected_bundles):
                    return {}
                for bpath in bundle_files:
                    sid = bpath.stem
                    try:
                        disk_rows = [
                            json.loads(line)
                            for line in bpath.read_text(encoding="utf-8").splitlines()
                            if line.strip()
                        ]
                    except (OSError, json.JSONDecodeError):
                        return {}
                    exp_rows = expected_bundles.get(sid) or []
                    if len(disk_rows) != len(exp_rows):
                        return {}
                    for d_row, e_row in zip(disk_rows, exp_rows):
                        if not isinstance(d_row, dict):
                            return {}
                        if d_row.get("backend_id") != e_row.get("backend_id"):
                            return {}
                        if "answer_section" in e_row and d_row.get("answer_section") != e_row.get("answer_section"):
                            return {}
    return cleaned


def load_map(
    run_dir: Path | str,
    *,
    cells: list[dict[str, Any]] | None = None,
    expected_run_id: str | None = None,
) -> dict[str, dict[str, str]]:
    """The letter-to-arm map per scenario, or empty when the run was not blinded or the map is invalid."""
    target = Path(run_dir)
    path = target if target.is_file() else target / MAP_FILE
    base_dir = path.parent
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if expected_run_id is None and (base_dir / "run_meta.json").is_file():
        try:
            meta = json.loads((base_dir / "run_meta.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        if isinstance(meta, dict) and isinstance(meta.get("run_id"), str) and meta["run_id"].strip():
            expected_run_id = meta["run_id"].strip()
    if cells is None and (base_dir / "judge-cells.jsonl").is_file():
        cells = _load_cells_file(base_dir / "judge-cells.jsonl")
    return validate_blind_map(
        data,
        cells=cells,
        expected_run_id=expected_run_id,
        bundles_dir=base_dir / BUNDLES_DIR,
    )


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
