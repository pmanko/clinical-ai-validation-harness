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


@dataclass(frozen=True)
class Feature002Paths:
    """Canonical paths the 2.7→2.8 transform flow reads and writes."""

    project_root: Path
    mappings_dir: Path                # datasets/mappings/
    conceptmap_path: Path             # datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json
    review_companion_path: Path       # datasets/mappings/openmrs-2.7-to-2.8.review.md
    sqlmesh_project_dir: Path         # datasets/transforms/sqlmesh/
    sqlmesh_seeds_dir: Path           # datasets/transforms/sqlmesh/seeds/
    concept_translation_seed: Path
    module_table_policy_seed: Path
    ocl_collections_dir: Path         # datasets/sources/ocl/

    @staticmethod
    def for_project(project_root: Path | str) -> "Feature002Paths":
        root = Path(project_root).resolve()
        mappings = root / "datasets" / "mappings"
        sqlmesh = root / "datasets" / "transforms" / "sqlmesh"
        seeds = sqlmesh / "seeds"
        return Feature002Paths(
            project_root=root,
            mappings_dir=mappings,
            conceptmap_path=mappings / "openmrs-2.7-to-2.8.conceptmap.json",
            review_companion_path=mappings / "openmrs-2.7-to-2.8.review.md",
            sqlmesh_project_dir=sqlmesh,
            sqlmesh_seeds_dir=seeds,
            concept_translation_seed=seeds / "concept_translation.csv",
            module_table_policy_seed=seeds / "module_table_policy.csv",
            ocl_collections_dir=root / "datasets" / "sources" / "ocl",
        )

    def artifacts_dir(self, run_id: str) -> Path:
        return self.project_root / "artifacts" / run_id

    def transform_artifact_dir(self, run_id: str) -> Path:
        return self.artifacts_dir(run_id) / "transform"

    def profile_artifact_dir(self, run_id: str) -> Path:
        return self.artifacts_dir(run_id) / "profile"


def get_feature_002_paths(project_root: Path | str | None = None) -> Feature002Paths:
    """Default path bundle for the 2.7→2.8 transform flow."""
    return Feature002Paths.for_project(project_root or Path("."))
