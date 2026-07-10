#!/usr/bin/env python3
"""Measure required-source recall through the real hub context preparation path.

This acceptance check intentionally uses llama.cpp's model-specific ``/tokenize``
endpoint. It does not offer an approximate-counter mode because such an artifact
would not prove the roadmap's exact-budget requirement.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "targets" / "med-agent-hub"
HUB_PROOF_INPUTS = (
    HUB / "server" / "context_sources.py",
    HUB / "server" / "engine.py",
    HUB / "server" / "levels_loader.py",
    HUB / "server" / "levels.yaml",
    HUB / "server" / "team.py",
    HUB / "server" / "temporal.py",
)
if importlib.util.find_spec("httpx") is None and not os.environ.get(
    "CONTEXT_QUALITY_BOOTSTRAPPED"
):
    for python in (HUB / ".venv-test" / "bin" / "python", HUB / ".venv" / "bin" / "python"):
        if python.exists():
            os.environ["CONTEXT_QUALITY_BOOTSTRAPPED"] = "1"
            os.execv(str(python), [str(python), *sys.argv])
sys.path.insert(0, str(HUB))

from server.context_sources import RouterTokenCounter  # noqa: E402
from server.engine import ExecutionRequest, _State, _prepare_context  # noqa: E402
from server.levels_loader import get_profile  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _combined_sha256(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _source_indices(value: Any) -> set[int]:
    found: set[int] = set()
    if isinstance(value, dict):
        index = value.get("index")
        if isinstance(index, int):
            found.add(index)
        indices = value.get("indices")
        if isinstance(indices, list):
            found.update(item for item in indices if isinstance(item, int))
        for nested in value.values():
            found.update(_source_indices(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_source_indices(nested))
    return found


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _chart_by_patient() -> dict[str, tuple[Path, dict[str, Any]]]:
    charts: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted((ROOT / "datasets/validation/charts").glob("*.json")):
        body = _load_json(path)
        patient = body.get("patient") or {}
        patient_uuid = patient.get("uuid")
        if patient_uuid:
            charts[str(patient_uuid)] = (path, body)
    return charts


def _iter_cases(comparison_set: dict[str, Any]) -> Iterable[tuple[str, str, list[int]]]:
    labels = (comparison_set.get("context_quality") or {}).get(
        "required_source_indices"
    ) or {}
    for scenario_id in comparison_set.get("scenario_ids") or []:
        required = labels.get(scenario_id)
        if not isinstance(required, list) or not required:
            raise ValueError(f"Missing required-source labels for {scenario_id!r}")
        yield scenario_id, f"datasets/validation/scenarios/{scenario_id}.json", [
            int(item) for item in required
        ]


async def _evaluate(args: argparse.Namespace) -> dict[str, Any]:
    comparison_path = ROOT / args.comparison_set
    comparison_set = _load_json(comparison_path)
    backends_path = ROOT / "datasets/validation/backends.json"
    backends = _load_json(backends_path)
    charts = _chart_by_patient()
    counter = RouterTokenCounter(args.router_url, timeout=args.timeout)
    results: list[dict[str, Any]] = []

    for backend_id in comparison_set.get("backend_ids") or []:
        backend = backends.get(backend_id) or {}
        profile_id = backend.get("modelName")
        if not profile_id:
            raise ValueError(f"Backend {backend_id!r} has no modelName")
        profile = get_profile(str(profile_id))
        if not profile.exact_tokenizer:
            raise ValueError(f"Profile {profile.id!r} does not require exact tokenization")

        for scenario_id, scenario_relpath, required in _iter_cases(comparison_set):
            scenario_path = ROOT / scenario_relpath
            scenario = _load_json(scenario_path)
            patient_ref = str(scenario["patient_ref"])
            chart_entry = charts.get(patient_ref)
            if chart_entry is None:
                raise ValueError(f"No chart fixture for patient {patient_ref!r}")
            chart_path, chart = chart_entry
            turns = scenario.get("turns") or []
            if len(turns) != 1:
                raise ValueError(f"Context quality case {scenario_id!r} must be single-turn")
            question = str(turns[0]["question"])
            messages = [
                {"role": "user", "content": str(chart["chart_snapshot"])},
                {"role": "user", "content": question},
            ]
            state = _State(messages=[dict(message) for message in messages])
            request = ExecutionRequest(
                profile=profile,
                messages=messages,
                token_counter=counter,
            )
            await _prepare_context(request, state)
            selected = set(state.view.record_indices if state.view else ())
            temporal = _source_indices(state.temporal_facts or {})
            available = selected | temporal
            missing = sorted(set(required) - available)
            results.append(
                {
                    "backend_id": backend_id,
                    "profile_id": profile.id,
                    "model": profile.models["answer"],
                    "scenario_id": scenario_id,
                    "scenario_sha256": _sha256(scenario_path),
                    "chart_fixture": str(chart_path.relative_to(ROOT)),
                    "chart_sha256": _sha256(chart_path),
                    "selection_mode": state.view.mode if state.view else "none",
                    "ledger_records": len(state.ledger.records),
                    "selected_records": len(selected),
                    "temporal_source_indices": len(temporal),
                    "input_tokens": state.view.input_tokens if state.view else None,
                    "input_limit": state.view.input_limit if state.view else None,
                    "required_source_indices": required,
                    "missing_source_indices": missing,
                    "recall": (len(required) - len(missing)) / len(required),
                }
            )

    total_required = sum(len(row["required_source_indices"]) for row in results)
    total_missing = sum(len(row["missing_source_indices"]) for row in results)
    return {
        "schema_version": "context_quality_gate.v1",
        "roadmap_id": "MAH-CONSOLIDATION-2026-07-09-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "actual hub _prepare_context path with llama.cpp /tokenize; recall is measured over selected chart records plus complete-ledger temporal_facts.v1.1 indices",
        "router_url": args.router_url,
        "comparison_set": str(comparison_path.relative_to(ROOT)),
        "comparison_set_sha256": _sha256(comparison_path),
        "backends_sha256": _sha256(backends_path),
        "hub_code_sha256": _combined_sha256(HUB_PROOF_INPUTS),
        "router_config_sha256": _sha256(ROOT / "scripts/llama-router.ini"),
        "cases": len(results),
        "required_sources": total_required,
        "missing_sources": total_missing,
        "required_source_recall": (
            (total_required - total_missing) / total_required if total_required else 0.0
        ),
        "status": "pass" if total_required and not total_missing else "fail",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--comparison-set",
        default="datasets/validation/comparison_sets/context-supply-dev.json",
    )
    parser.add_argument("--router-url", default="http://localhost:8077")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--output",
        default="artifacts/roadmap/gates/G09-context-quality.json",
    )
    args = parser.parse_args()
    result = asyncio.run(_evaluate(args))
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"{result['status'].upper()}: {result['required_source_recall']:.1%} "
        f"required-source recall across {result['cases']} cells -> {output}"
    )
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
