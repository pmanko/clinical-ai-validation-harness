from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HarnessConfig:
    project_root: Path
    artifacts_dir: Path
    legacy_sql_path: Path
    chartsearchai_repo: Path
    querystore_repo: Path

    @staticmethod
    def from_defaults(project_root: Path) -> "HarnessConfig":
        project_root = project_root.resolve()
        return HarnessConfig(
            project_root=project_root,
            artifacts_dir=project_root / "artifacts",
            legacy_sql_path=Path(
                "/Users/pmanko/code/openmrs-module-chartsearchai/data/large-demo-data-2-7-0.sql"
            ),
            chartsearchai_repo=Path("/Users/pmanko/code/openmrs-module-chartsearchai"),
            querystore_repo=Path("/Users/pmanko/code/openmrs-module-querystore"),
        )
