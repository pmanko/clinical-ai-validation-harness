from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunManifest:
    run_id: str
    project: str
    component: str
    git_sha: str
    dataset_id: str
    dataset_version: str
    schema_mapping_version: str
    gen_ai_provider_name: str
    generated_at: str = field(default_factory=utc_now_iso)
    evidence_status: str = "development"
    decision_rationale: str | None = None
    target_provenance: list[dict[str, Any]] = field(default_factory=list)
    otel_semconv_status: str = "development"
    otel_semconv_stability_opt_in: str = "gen_ai_latest_experimental"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "project": self.project,
            "component": self.component,
            "git_sha": self.git_sha,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "schema_mapping_version": self.schema_mapping_version,
            "generated_at": self.generated_at,
            "evidence_status": self.evidence_status,
            "target_provenance": list(self.target_provenance),
            "otel": {
                "semconv_status": self.otel_semconv_status,
                "semconv_stability_opt_in": self.otel_semconv_stability_opt_in,
                "gen_ai.provider.name": self.gen_ai_provider_name,
            },
        }
        if self.decision_rationale is not None:
            payload["decision_rationale"] = self.decision_rationale
        return payload


def write_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("timestamp", utc_now_iso())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, separators=(",", ":")) + "\n")


# ---------------------------------------------------------------------------
# Feature 002 extensions (T007)
#
# The base RunManifest above is M0's primitive. Feature 002 adds top-level
# keys per `specs/002-openmrs-demo-data-2-8-remap/contracts/run_manifest_002_extensions.schema.yaml`.
# Producers stamp the extension dataclass into the manifest payload via
# `RunManifest.to_dict() | RunManifest002Extensions(...).to_dict()`.
# ---------------------------------------------------------------------------


@dataclass
class OclCollectionVersion:
    collection: str        # 'CIEL' | 'LOINC' | 'SNOMED-CT'
    version: str           # e.g. 'v2026-04-28'
    snapshot_path: str     # 'datasets/sources/ocl/CIEL/v2026-04-28/'
    checksum: str          # SHA-256 of the snapshot tar / SQL


@dataclass
class ReviewerSignoff:
    document_path: str
    document_checksum: str
    signer: str            # email or GitHub handle
    signed_at: str         # ISO 8601


@dataclass
class RunManifest002Extensions:
    """002 top-level extensions appended to RunManifest.to_dict()."""

    conceptmap_path: str
    conceptmap_checksum: str
    sqlmesh_project_path: str
    sqlmesh_project_checksum: str
    concept_translation_seed_checksum: str
    module_table_policy_seed_checksum: str
    ocl_collection_versions: list[OclCollectionVersion]
    openmrs_refapp_image_digest: str
    mariadb_image_digest: str
    fhir_validator_version: str
    sqlmesh_version: str
    python_version: str
    equivalence_labels: list[str] = field(default_factory=list)
    policy_buckets: list[str] = field(default_factory=list)
    reviewer_signoffs: list[ReviewerSignoff] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conceptmap_path": self.conceptmap_path,
            "conceptmap_checksum": self.conceptmap_checksum,
            "sqlmesh_project_path": self.sqlmesh_project_path,
            "sqlmesh_project_checksum": self.sqlmesh_project_checksum,
            "concept_translation_seed_checksum": self.concept_translation_seed_checksum,
            "module_table_policy_seed_checksum": self.module_table_policy_seed_checksum,
            "ocl_collection_versions": [
                {
                    "collection": v.collection,
                    "version": v.version,
                    "snapshot_path": v.snapshot_path,
                    "checksum": v.checksum,
                }
                for v in self.ocl_collection_versions
            ],
            "openmrs_refapp_image_digest": self.openmrs_refapp_image_digest,
            "mariadb_image_digest": self.mariadb_image_digest,
            "fhir_validator_version": self.fhir_validator_version,
            "sqlmesh_version": self.sqlmesh_version,
            "python_version": self.python_version,
            "equivalence_labels": list(self.equivalence_labels),
            "policy_buckets": list(self.policy_buckets),
            "reviewer_signoffs": [
                {
                    "document_path": s.document_path,
                    "document_checksum": s.document_checksum,
                    "signer": s.signer,
                    "signed_at": s.signed_at,
                }
                for s in self.reviewer_signoffs
            ],
        }


def merge_002_extensions(
    manifest: RunManifest, extensions: RunManifest002Extensions
) -> dict[str, Any]:
    """Compose the full 002 run-manifest dict: M0 base ∪ 002 extensions.

    Schema invariant per contracts/run_manifest_002_extensions.schema.yaml:
    a 002 manifest validates against BOTH the M0 base schema AND the 002
    extensions schema. Top-level keys don't overlap.
    """
    return {**manifest.to_dict(), **extensions.to_dict()}
