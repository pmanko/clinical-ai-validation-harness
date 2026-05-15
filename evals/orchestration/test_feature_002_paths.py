"""Canonical paths for the 2.7→2.8 transform flow."""

from __future__ import annotations

from pathlib import Path

from harness.config import Feature002Paths, get_feature_002_paths


def test_paths_anchored_at_project_root(tmp_path: Path):
    root = (tmp_path / "myproj").resolve()
    root.mkdir()
    paths = Feature002Paths.for_project(root)
    assert paths.project_root == root
    assert paths.conceptmap_path == root / "datasets" / "mappings" / "openmrs-2.7-to-2.8.conceptmap.json"
    assert paths.review_companion_path == root / "datasets" / "mappings" / "openmrs-2.7-to-2.8.review.md"
    assert paths.sqlmesh_project_dir == root / "datasets" / "transforms" / "sqlmesh"
    assert paths.sqlmesh_seeds_dir == root / "datasets" / "transforms" / "sqlmesh" / "seeds"
    assert paths.concept_translation_seed == paths.sqlmesh_seeds_dir / "concept_translation.csv"
    assert paths.module_table_policy_seed == paths.sqlmesh_seeds_dir / "module_table_policy.csv"
    assert paths.ocl_collections_dir == root / "datasets" / "sources" / "ocl"


def test_artifacts_dir_per_run(tmp_path: Path):
    root = (tmp_path / "myproj").resolve()
    root.mkdir()
    paths = Feature002Paths.for_project(root)
    assert paths.artifacts_dir("dev-abc") == root / "artifacts" / "dev-abc"
    assert paths.transform_artifact_dir("dev-abc") == root / "artifacts" / "dev-abc" / "transform"
    assert paths.profile_artifact_dir("dev-abc") == root / "artifacts" / "dev-abc" / "profile"


def test_default_helper_resolves_cwd():
    paths = get_feature_002_paths()
    assert paths.conceptmap_path.name == "openmrs-2.7-to-2.8.conceptmap.json"
    assert paths.sqlmesh_seeds_dir.name == "seeds"
