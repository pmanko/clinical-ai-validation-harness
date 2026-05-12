from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QueryStoreAdapter:
    repo_path: Path

    def command_plan(self) -> list[str]:
        return [
            "mvn -pl api install",
        ]
