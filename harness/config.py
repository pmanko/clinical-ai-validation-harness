from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .targets import HarnessTargetsDocument, default_targets_path


@dataclass(frozen=True)
class HarnessConfig:
    project_root: Path
    artifacts_dir: Path
    targets: HarnessTargetsDocument

    @staticmethod
    def from_defaults(project_root: Path) -> "HarnessConfig":
        project_root = project_root.resolve()
        targets = HarnessTargetsDocument.load(default_targets_path(project_root))
        return HarnessConfig(
            project_root=project_root,
            artifacts_dir=project_root / "artifacts",
            targets=targets,
        )
