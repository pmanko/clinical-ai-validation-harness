from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.common.jsonl import append_jsonl


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def copy_target_provenance(
    provenance: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Freeze caller claims without treating them as verified target identity."""
    if provenance is None:
        return []
    if not isinstance(provenance, list):
        raise ValueError("target_provenance must be a list of objects")
    required = {"target_id", "target_source", "target_actual_sha"}
    field_types = {
        "target_id": (str,), "target_source": (str,),
        "target_actual_sha": (str, type(None)), "target_url": (str, type(None)),
        "evidence_status": (str,), "decision_rationale": (str,),
    }
    for item in provenance:
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError("target_provenance objects require target_id, target_source and target_actual_sha")
        for name, types in field_types.items():
            if name in item and not isinstance(item[name], types):
                raise ValueError(f"target_provenance {name} has an invalid type")
        if not item["target_id"].strip():
            raise ValueError("target_provenance target_id must not be blank")
        if item["target_source"] not in ("supplied", "observed_api", "unavailable"):
            raise ValueError("target_provenance target_source must be supplied, observed_api or unavailable")
    try:
        return json.loads(json.dumps(provenance, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValueError("target_provenance must contain finite JSON values") from error


@dataclass
class RunManifest:
    run_id: str
    project: str
    component: str
    git_sha: str | None
    dataset_id: str
    dataset_version: str
    schema_mapping_version: str
    gen_ai_provider_name: str | None
    gen_ai_operation_name: str | None = None
    generated_at: str = field(default_factory=utc_now_iso)
    evidence_status: str = "development"
    decision_rationale: str | None = None
    target_provenance: list[dict[str, Any]] = field(default_factory=list)
    otel_semconv_status: str = "development"
    otel_semconv_stability_opt_in: str = "gen_ai_latest_experimental"
    patients: dict[str, Any] = field(default_factory=dict)
    dataset_provenance: dict[str, Any] = field(default_factory=dict)
    report_family: str | None = None
    suite_id: str | None = None
    suite_sha256: str | None = None
    resumed_from: str | None = None
    resume_ancestry: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        otel: dict[str, Any] = {
            "semconv_status": self.otel_semconv_status,
            "semconv_stability_opt_in": self.otel_semconv_stability_opt_in,
        }
        if self.gen_ai_provider_name is not None:
            otel["gen_ai.provider.name"] = self.gen_ai_provider_name
        if self.gen_ai_operation_name is not None:
            otel["gen_ai.operation.name"] = self.gen_ai_operation_name

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
            "otel": otel,
        }
        if self.decision_rationale is not None:
            payload["decision_rationale"] = self.decision_rationale
        if self.patients:
            payload["patients"] = self.patients
        if self.dataset_provenance:
            payload["dataset_provenance"] = self.dataset_provenance
        if self.report_family is not None:
            payload["report_family"] = self.report_family
        if self.suite_id is not None:
            payload["suite_id"] = self.suite_id
        if self.suite_sha256 is not None:
            payload["suite_sha256"] = self.suite_sha256
        if self.resumed_from is not None:
            payload["resumedFrom"] = self.resumed_from
        if self.resume_ancestry:
            payload["resumeAncestry"] = list(self.resume_ancestry)
        return payload


def write_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")


def append_event(path: Path, event: dict[str, Any]) -> None:
    event.setdefault("timestamp", utc_now_iso())
    append_jsonl(path, event)


@dataclass
class OclCollectionVersion:
    collection: str
    version: str
    snapshot_path: str
    checksum: str


@dataclass
class ReviewerSignoff:
    document_path: str
    document_checksum: str
    signer: str
    signed_at: str


@dataclass
class MaterializedOutput:
    """One materialized target table — row count + content checksum.

    Stamped after the transform completes so two runs that should be
    byte-identical can be compared per-table without diffing the full
    dump. ``checksum_method`` documents how ``content_checksum`` was
    computed:

      - ``sha256_of_canonical_dump`` (default): SHA-256 over a
        column-ordered, PK-ordered row representation. Works on views.
      - ``mariadb_checksum_table``: MariaDB's built-in ``CHECKSUM
        TABLE`` integer, rendered as a string. Only works on base
        tables (returns NULL on views).
    """

    table_name: str
    row_count: int
    content_checksum: str
    checksum_method: str = "sha256_of_canonical_dump"


@dataclass
class RunManifest002Extensions:
    """Additional top-level keys appended to ``RunManifest.to_dict()``."""

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
    materialized_outputs: list[MaterializedOutput] = field(default_factory=list)

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
            "materialized_outputs": [
                {
                    "table_name": o.table_name,
                    "row_count": o.row_count,
                    "content_checksum": o.content_checksum,
                    "checksum_method": o.checksum_method,
                }
                for o in self.materialized_outputs
            ],
        }


def merge_002_extensions(
    manifest: RunManifest, extensions: RunManifest002Extensions
) -> dict[str, Any]:
    """Compose the base manifest dict with the 002 extension keys.

    Top-level keys are required to be disjoint between the two.
    """
    return {**manifest.to_dict(), **extensions.to_dict()}
