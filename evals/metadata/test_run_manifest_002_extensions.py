"""T008 — round-trip RunManifest002Extensions through to_dict() + assert it
composes with the M0 base manifest into a single 002 payload.

The full schema is `specs/002-openmrs-demo-data-2-8-remap/contracts/run_manifest_002_extensions.schema.yaml`.
"""

from __future__ import annotations

import json

from harness.metadata import (
    OclCollectionVersion,
    ReviewerSignoff,
    RunManifest,
    RunManifest002Extensions,
    merge_002_extensions,
)


def _sample_manifest() -> RunManifest:
    return RunManifest(
        run_id="run-20260514-abcd",
        project="clinical-ai-validation-harness",
        component="harness-cli",
        git_sha="0a18df7",
        dataset_id="openmrs-demo-2.7",
        dataset_version="large-demo-data-2-7-0",
        schema_mapping_version="openmrs-2.7-to-2.8",
        gen_ai_provider_name="none",
    )


def _sample_extensions() -> RunManifest002Extensions:
    return RunManifest002Extensions(
        conceptmap_path="datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json",
        conceptmap_checksum="a" * 64,
        sqlmesh_project_path="datasets/transforms/sqlmesh",
        sqlmesh_project_checksum="b" * 64,
        concept_translation_seed_checksum="c" * 64,
        module_table_policy_seed_checksum="d" * 64,
        ocl_collection_versions=[
            OclCollectionVersion(
                collection="CIEL",
                version="v2026-04-28",
                snapshot_path="datasets/sources/ocl/CIEL/v2026-04-28/",
                checksum="c4122d55f384bf853c55b7de196f9cdd6cc1760ae516272a754ea2ff7035d12a",
            ),
        ],
        openmrs_refapp_image_digest="sha256:abc123",
        mariadb_image_digest="sha256:def456",
        fhir_validator_version="6.x",
        sqlmesh_version="0.234.1",
        python_version="3.11.15",
        equivalence_labels=["equal", "inexact"],
        policy_buckets=["remap", "seed-augment"],
        reviewer_signoffs=[
            ReviewerSignoff(
                document_path="datasets/mappings/openmrs-2.7-to-2.8.review.md",
                document_checksum="e" * 64,
                signer="pmanko@uw.edu",
                signed_at="2026-05-15T01:00:00Z",
            )
        ],
    )


def test_extensions_to_dict_has_all_top_level_keys():
    ext = _sample_extensions()
    d = ext.to_dict()
    required = {
        "conceptmap_path",
        "conceptmap_checksum",
        "sqlmesh_project_path",
        "sqlmesh_project_checksum",
        "concept_translation_seed_checksum",
        "module_table_policy_seed_checksum",
        "ocl_collection_versions",
        "openmrs_refapp_image_digest",
        "mariadb_image_digest",
        "fhir_validator_version",
        "sqlmesh_version",
        "python_version",
        "equivalence_labels",
        "policy_buckets",
        "reviewer_signoffs",
    }
    assert required.issubset(d.keys())


def test_extensions_round_trip_through_json():
    ext = _sample_extensions()
    serialized = json.dumps(ext.to_dict(), sort_keys=True)
    parsed = json.loads(serialized)
    assert parsed["sqlmesh_version"] == "0.234.1"
    assert parsed["ocl_collection_versions"][0]["collection"] == "CIEL"
    assert parsed["reviewer_signoffs"][0]["signer"] == "pmanko@uw.edu"


def test_merge_002_extensions_top_level_keys_disjoint():
    base = _sample_manifest()
    ext = _sample_extensions()
    merged = merge_002_extensions(base, ext)
    base_keys = set(base.to_dict().keys())
    ext_keys = set(ext.to_dict().keys())
    # No overlap: the schema says 002 extensions are ADDITIONAL top-level keys.
    assert base_keys.isdisjoint(ext_keys), f"overlap: {base_keys & ext_keys}"
    # Merged contains both.
    assert base_keys.issubset(merged.keys())
    assert ext_keys.issubset(merged.keys())


def test_merge_002_extensions_preserves_m0_values():
    base = _sample_manifest()
    ext = _sample_extensions()
    merged = merge_002_extensions(base, ext)
    assert merged["run_id"] == "run-20260514-abcd"
    assert merged["dataset_version"] == "large-demo-data-2-7-0"
    assert merged["otel"]["gen_ai.provider.name"] == "none"


def test_extensions_empty_lists_default():
    ext = RunManifest002Extensions(
        conceptmap_path="x",
        conceptmap_checksum="0" * 64,
        sqlmesh_project_path="y",
        sqlmesh_project_checksum="0" * 64,
        concept_translation_seed_checksum="0" * 64,
        module_table_policy_seed_checksum="0" * 64,
        ocl_collection_versions=[],
        openmrs_refapp_image_digest="",
        mariadb_image_digest="",
        fhir_validator_version="",
        sqlmesh_version="",
        python_version="",
    )
    d = ext.to_dict()
    assert d["equivalence_labels"] == []
    assert d["policy_buckets"] == []
    assert d["reviewer_signoffs"] == []
    assert d["ocl_collection_versions"] == []
