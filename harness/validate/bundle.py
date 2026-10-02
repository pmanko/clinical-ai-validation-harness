"""Portable run inputs and frozen-only review access.

Execution may read explicitly configured experiment inputs and trace exports.
Review never reads outside the run directory, even when original sources exist.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from harness.common.jsonl import read_jsonl

from .hub_trace import match_trace, trace_model_for_result
from .sources import load_scenario_chart


def load_run_meta(run_dir: Path | str) -> dict[str, Any]:
    path = Path(run_dir) / "run_meta.json"
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: run metadata must be an object")
    return value


def frozen_arm_cards(run_dir: Path | str, backend_ids: list[str]) -> dict[str, Any]:
    frozen = load_run_meta(run_dir).get("arm_cards") or {}
    return {bid: frozen.get(bid) for bid in backend_ids}


def review_results(run_dir: Path | str, *, strict: bool = True) -> list[dict[str, Any]]:
    """Resolve routing identity only from the result or frozen connection metadata."""
    backends = load_run_meta(run_dir).get("backends") or {}
    rows = read_jsonl(Path(run_dir) / "results.jsonl", strict=strict)
    for row in rows:
        request = row.get("request") or {}
        row["request"] = request
        backend = backends.get(row.get("backend_id")) or {}
        if "profile" not in request and backend.get("provider") != "bundled":
            model = backend.get("modelName")
            if model:
                request["profile"] = model
    return rows


def run_chart(run_dir: Path | str, scenario_id: str) -> dict[str, Any] | None:
    inputs = Path(run_dir) / "inputs"
    return load_scenario_chart(scenario_id, inputs / "scenarios", inputs / "charts")


def freeze_inputs(data_root: Path, run_dir: Path, comparison_set_id: str) -> None:
    """Copy the selected authored inputs before execution; fail if capture fails."""
    comparison_path = data_root / "comparison_sets" / f"{comparison_set_id}.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    inputs = run_dir / "inputs"
    paths = [comparison_path, data_root / "backends.json"]
    patients = set()
    for sid in comparison["scenario_ids"]:
        path = data_root / "scenarios" / f"{sid}.json"
        patients.add(json.loads(path.read_text(encoding="utf-8"))["patient_ref"])
        paths.append(path)
    for path in sorted((data_root / "charts").glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        if (fixture.get("patient") or {}).get("uuid") in patients:
            paths.append(path)
    for path in paths:
        destination = inputs / path.relative_to(data_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)


def capture_traces(run_dir: Path, candidates: list[dict[str, Any]]) -> None:
    """Freeze only traces correlated to this run's answer and In-Depth requests."""
    captured = []
    for row in review_results(run_dir):
        requests = [row]
        indepth = row.get("indepth") or {}
        if indepth:
            requests.append({
                **row,
                "response": indepth.get("response"),
                "request": {
                    **(row.get("request") or {}),
                    "profile": indepth.get("model_name"),
                    "session": indepth.get("session"),
                    "question": "Now provide the in-depth clinical background for that answer.",
                    "request_id": indepth.get("request_id"),
                },
                "started_at": indepth.get("started_at"),
                "ended_at": indepth.get("ended_at"),
            })
        for result in requests:
            request = result.get("request") or {}
            trace = match_trace(
                candidates,
                trace_model_for_result(result, result.get("backend_id")),
                result.get("started_at"), result.get("ended_at"),
                question=request.get("question"), session=request.get("session"),
                request_id=request.get("request_id"),
            )
            if trace is not None and trace not in captured:
                captured.append(trace)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "trace.jsonl").write_text(
        "".join(json.dumps(trace) + "\n" for trace in captured), encoding="utf-8"
    )
