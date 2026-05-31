"""Persistence behind one save/find interface (spec 006 FR-006.6).

Two storage styles, keyed by collection:
  - authored (scenarios, comparison_sets): one checked-in JSON file per id,
    read-only — these are inputs, not run outputs.
  - run (results, feedback): JSONL appended under the run directory.

The JSONL file implementation is the wired one; the Mongo implementation is a
documented stub with the same interface.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

_AUTHORED = ("scenarios", "comparison_sets")
_RUN = ("results", "feedback")
_COLLECTIONS = _AUTHORED + _RUN


def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    return all(doc.get(k) == v for k, v in query.items())


class Repository(ABC):
    @abstractmethod
    def save(self, collection: str, doc: dict[str, Any]) -> None: ...

    @abstractmethod
    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...


class JsonlRepository(Repository):
    def __init__(self, authored_root: Path | str, run_dir: Path | str) -> None:
        self.authored_root = Path(authored_root)
        self.run_dir = Path(run_dir)

    def save(self, collection: str, doc: dict[str, Any]) -> None:
        if collection not in _RUN:
            raise ValueError(
                f"save supports run collections {_RUN}; {collection!r} is authored/checked-in"
            )
        path = self.run_dir / f"{collection}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(doc, separators=(",", ":")) + "\n")

    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query = query or {}
        if collection in _AUTHORED:
            docs = self._read_authored(collection)
        elif collection in _RUN:
            docs = self._read_jsonl(self.run_dir / f"{collection}.jsonl")
        else:
            raise ValueError(f"unknown collection {collection!r}; expected one of {_COLLECTIONS}")
        return [d for d in docs if _matches(d, query)]

    def _read_authored(self, collection: str) -> list[dict[str, Any]]:
        directory = self.authored_root / collection
        if not directory.is_dir():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


class MongoRepository(Repository):
    """Documented stub (spec 006 FR-006.6). The JSONL file repository is the
    wired implementation; constructing this raises so the gap is explicit."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "MongoRepository is a documented stub for the 006 MVP; use JsonlRepository. "
            "See specs/006-validation-harness-mvp/spec.md SC-006.6."
        )

    def save(self, collection: str, doc: dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError
