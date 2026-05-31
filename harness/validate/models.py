"""Authored inputs for a validation run: scenarios, comparison sets, and the
backend registry. All are checked-in JSON; these dataclasses load + validate
them against the documented shapes (spec 006 data model).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _require(data: dict[str, Any], keys: tuple[str, ...], what: str) -> None:
    missing = [k for k in keys if k not in data or data[k] in (None, "")]
    if missing:
        raise ValueError(f"{what}: missing required field(s): {', '.join(missing)}")


@dataclass(frozen=True)
class Turn:
    n: int
    question: str


@dataclass(frozen=True)
class Scenario:
    id: str
    patient_ref: str
    turns: list[Turn]
    tags: list[str] = field(default_factory=list)
    expectations: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        _require(data, ("id", "patient_ref", "turns"), "scenario")
        turns_raw = data["turns"]
        if not isinstance(turns_raw, list) or not turns_raw:
            raise ValueError(f"scenario {data.get('id')!r}: 'turns' must be a non-empty list")
        turns = [Turn(n=int(t["n"]), question=str(t["question"])) for t in turns_raw]
        return cls(
            id=str(data["id"]),
            patient_ref=str(data["patient_ref"]),
            turns=turns,
            tags=list(data.get("tags", [])),
            expectations=dict(data.get("expectations", {})),
        )


@dataclass(frozen=True)
class ComparisonSet:
    id: str
    scenario_ids: list[str]
    backend_ids: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComparisonSet":
        _require(data, ("id", "scenario_ids", "backend_ids"), "comparison_set")
        for key in ("scenario_ids", "backend_ids"):
            if not isinstance(data[key], list) or not data[key]:
                raise ValueError(f"comparison_set {data.get('id')!r}: '{key}' must be a non-empty list")
        return cls(
            id=str(data["id"]),
            scenario_ids=[str(s) for s in data["scenario_ids"]],
            backend_ids=[str(b) for b in data["backend_ids"]],
        )


@dataclass(frozen=True)
class Backend:
    """A concrete backend the runner can select: the {endpointUrl, modelName}
    pair POST /endpoint writes, resolved from an abstract backend_id."""

    id: str
    label: str
    endpoint_url: str
    model_name: str

    @classmethod
    def from_dict(cls, backend_id: str, data: dict[str, Any]) -> "Backend":
        _require(data, ("endpointUrl", "modelName"), f"backend {backend_id!r}")
        return cls(
            id=backend_id,
            label=str(data.get("label", backend_id)),
            endpoint_url=str(data["endpointUrl"]),
            model_name=str(data["modelName"]),
        )


def load_scenario(path: Path | str) -> Scenario:
    return Scenario.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def load_comparison_set(path: Path | str) -> ComparisonSet:
    return ComparisonSet.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def load_backends(path: Path | str) -> dict[str, Backend]:
    """The backend registry: a JSON object of backend_id -> {label?, endpointUrl, modelName}."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"backend registry {path} must be a JSON object of id -> config")
    return {bid: Backend.from_dict(bid, cfg) for bid, cfg in raw.items()}
