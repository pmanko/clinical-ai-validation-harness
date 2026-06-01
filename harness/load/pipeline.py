"""dlt pipeline: SQLMesh snapshot tables → staging schema, then promoted to OpenMRS DB.

Per ``contracts/dlt_pipeline.profile.md`` + research.md §R-load-pattern,
this pipeline picks up after SQLMesh's transform completes. The
**two-schema architecture** is mandatory because dlt's ``_dlt_load_id``
and ``_dlt_id`` columns aren't suppressible — writing dlt directly
into the OpenMRS schema destructively mutates Hibernate-defined
tables. So:

  sqlmesh__refapp_28_demo.<snap>  ─[dlt]→  <target>_dlt.<table>  ─[promote]→  <target>.<table>
                                              (with _dlt_* cols)         (clean OpenMRS schema)

The promote step (``harness/load/promote.py``) reads from
``<target>_dlt.<table>`` and INSERTs into ``<target>.<table>`` using
only the OpenMRS-defined column set (filtering out _dlt_* columns).

For each iteration target:
  - ``openmrs_test_dlt`` ↔ ``openmrs_test``
  - ``openmrs_dlt``      ↔ ``openmrs``       (production promote)

Resource ordering follows FK dependency: parents before children
(person before patient before encounter before obs).

Reference tables (location, encounter_type, encounter_role, role,
provider, users) use `merge` so legacy IDs coexist with CIEL-baseline
stock. Clinical fact tables use `replace` because their inputs are
authoritative (legacy is the canonical clinical history).

``concept_*`` tables are NOT touched — CIEL has already populated
them in the destination schema via ``scripts/loadtest-up.sh`` cloning
the CIEL-loaded openmrs canvas.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import dlt
from dlt.sources.sql_database import sql_table
from sqlalchemy import create_engine

from harness.load.snapshot_resolver import ResolvedSnapshot, resolve_snapshots
from harness.profile.db import DBConfig


# --------------------------------------------------------------------------
# Resource manifest
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadResource:
    """One logical target table — what to load, how, with what PK."""
    sqlmesh_view: str               # name in refapp_28_demo (e.g. "stg_person")
    target_table: str               # name in openmrs[_test] (e.g. "person")
    primary_key: tuple[str, ...]
    write_disposition: str          # "replace" | "merge" | "append"


# FK-dependency ordered list. Parents first.
#
# Skip rationale: concept_* tables are pre-populated by CIEL in
# openmrs_test (via loadtest-up.sh). Rewriting them risks UUID-pattern
# conflicts per research.md §R-bridge-rule.
LOAD_RESOURCES: tuple[LoadResource, ...] = (
    # ---- Reference / lookup tables (merge — coexist with CIEL-baseline stock) ----
    LoadResource("stg_users",            "users",            ("user_id",),        "merge"),
    LoadResource("stg_role",             "role",             ("role",),           "merge"),
    LoadResource("stg_role_privilege",   "role_privilege",   ("role", "privilege"), "merge"),
    LoadResource("stg_user_role",        "user_role",        ("user_id", "role"), "merge"),
    LoadResource("stg_user_property",    "user_property",    ("user_id", "property"), "merge"),
    LoadResource("stg_location",         "location",         ("location_id",),    "merge"),
    LoadResource("stg_encounter_type",   "encounter_type",   ("encounter_type_id",), "merge"),
    LoadResource("stg_encounter_role",   "encounter_role",   ("encounter_role_id",), "merge"),
    LoadResource("stg_provider",         "provider",         ("provider_id",),    "merge"),

    # ---- Form / metadata tables (merge — small, infrequent collisions) ----
    LoadResource("stg_form",             "form",             ("form_id",),        "merge"),
    LoadResource("stg_field",            "field",            ("field_id",),       "merge"),
    LoadResource("stg_field_type",       "field_type",       ("field_type_id",),  "merge"),
    LoadResource("stg_form_field",       "form_field",       ("form_field_id",),  "merge"),
    LoadResource("stg_order_type",       "order_type",       ("order_type_id",),  "merge"),
    LoadResource("stg_drug",             "drug",             ("drug_id",),        "merge"),
    LoadResource("stg_care_setting",     "care_setting",     ("care_setting_id",), "merge"),

    # ---- Clinical / fact tables (replace — legacy is canonical) ----
    LoadResource("stg_person",           "person",           ("person_id",),      "replace"),
    LoadResource("stg_person_name",      "person_name",      ("person_name_id",), "replace"),
    LoadResource("stg_person_attribute_type", "person_attribute_type", ("person_attribute_type_id",), "merge"),
    LoadResource("stg_person_address",   "person_address",   ("person_address_id",), "replace"),
    LoadResource("stg_person_attribute", "person_attribute", ("person_attribute_id",), "replace"),
    LoadResource("stg_patient",          "patient",          ("patient_id",),     "replace"),
    LoadResource("stg_patient_identifier", "patient_identifier", ("patient_identifier_id",), "replace"),
    LoadResource("stg_patient_identifier_type", "patient_identifier_type", ("patient_identifier_type_id",), "merge"),
    LoadResource("stg_encounter",        "encounter",        ("encounter_id",),   "replace"),
    LoadResource("stg_encounter_provider", "encounter_provider", ("encounter_provider_id",), "replace"),
    LoadResource("stg_concept_carryforward", "concept", ("concept_id",), "merge"),
    LoadResource("stg_concept_name_carryforward", "concept_name", ("concept_name_id",), "merge"),
    LoadResource("stg_program",          "program",          ("program_id",),     "replace"),
    LoadResource("stg_program_workflow", "program_workflow", ("program_workflow_id",), "replace"),
    LoadResource("stg_program_workflow_state", "program_workflow_state", ("program_workflow_state_id",), "replace"),
    LoadResource("stg_patient_program",  "patient_program",  ("patient_program_id",), "replace"),
    LoadResource("stg_patient_state",    "patient_state",    ("patient_state_id",), "replace"),

    # ---- The 4 obs-promoted clinical marts + the residual obs ----
    # NB clin__orders is the PARENT of drug_order and test_order (Hibernate
    # joined-table inheritance). Must load BEFORE the two child tables.
    LoadResource("clin__obs",            "obs",              ("obs_id",),         "replace"),
    LoadResource("clin__orders",         "orders",           ("order_id",),       "replace"),
    LoadResource("clin__drug_order",     "drug_order",       ("order_id",),       "replace"),
    LoadResource("clin__conditions",     "conditions",       ("uuid",),           "replace"),
    LoadResource("clin__allergy",        "allergy",          ("uuid",),           "replace"),
    LoadResource("clin__test_order",     "test_order",       ("order_id",),       "replace"),
)


# Non-empty legacy_27_raw tables intentionally NOT row-copied, each with a reason.
# The completeness gate (harness.transform.completeness) fails the run if a
# non-empty source table is neither a LOAD_RESOURCES target nor listed here — the
# guard that would have caught the original person_address/patient_state silent
# drop. `concept_*` is matched by prefix (CIEL owns the dictionary).
EXCLUDED_PREFIXES: tuple[str, ...] = ("concept",)
EXCLUDED_WITH_REASON: dict[str, str] = {
    "liquibasechangelog": "schema migration bookkeeping; target owns its own",
    "liquibasechangeloglock": "schema migration bookkeeping; target owns its own",
    "global_property": "system config; RefApp 3.x owns its own",
    "privilege": "security metadata; RefApp 3.x owns its own",
    "tribe": "deprecated table, removed from modern OpenMRS",
    "logic_token_registration": "logic-module infra; RefApp owns its own",
    "scheduler_task_config": "scheduler infra; RefApp owns its own",
    "hl7_source": "HL7 infra; RefApp owns its own",
    "relationship_type": "relationship metadata; legacy.relationship has 0 rows (nothing references the legacy types); RefApp owns its own",
}


def staging_schema(target_schema: str) -> str:
    """Convert ``openmrs_test`` → ``openmrs_test_dlt``, ``openmrs`` → ``openmrs_dlt``.

    The two-schema architecture (per ``contracts/dlt_pipeline.profile.md``):
    dlt writes its ``_dlt_*``-decorated tables here; the promote step
    copies clean rows from here to the actual target schema.
    """
    return f"{target_schema}_dlt"


# --------------------------------------------------------------------------
# Pipeline construction
# --------------------------------------------------------------------------


def _source_engine_url() -> str:
    """SQLAlchemy URL for reading from sqlmesh__refapp_28_demo."""
    host = os.environ.get("MARIADB_HOST", "127.0.0.1")
    port = os.environ.get("MARIADB_PORT", "3307")
    user = os.environ.get("MARIADB_USER", "openmrs")
    password = os.environ.get("MARIADB_PASSWORD", "openmrs")
    # Source DSN is schema-less so we can switch schemas per resource.
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/sqlmesh__refapp_28_demo"


def _dest_credentials(staging_db: str) -> str:
    """SQLAlchemy URL for dlt's staging schema (NOT the final OpenMRS DB).

    dlt writes its _dlt_*-decorated tables to this staging schema; the
    promote step then copies to the actual OpenMRS target.
    """
    host = os.environ.get("MARIADB_HOST", "127.0.0.1")
    port = os.environ.get("MARIADB_PORT", "3307")
    user = os.environ.get("MARIADB_USER", "openmrs")
    password = os.environ.get("MARIADB_PASSWORD", "openmrs")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{staging_db}"


def build_resources(snapshots: dict[str, ResolvedSnapshot]) -> list[Any]:
    """Build the list of dlt resources, in FK-dependency order.

    Resources whose SQLMesh view doesn't resolve (e.g., the view doesn't
    exist because we haven't authored that staging model yet) are skipped
    with a printed warning so the operator sees the gap.
    """
    # dlt parallelizes resource extraction; ~32 resources means we need a
    # generous pool. pool_pre_ping handles stale connections after long pauses.
    engine = create_engine(
        _source_engine_url(),
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    resources: list[Any] = []
    for spec in LOAD_RESOURCES:
        snap = snapshots.get(spec.sqlmesh_view)
        if snap is None:
            print(f"  SKIP: {spec.sqlmesh_view} not in refapp_28_demo (no view to resolve)")
            continue
        # sql_table reads from the resolved physical snapshot table directly.
        res = sql_table(
            credentials=engine,
            table=snap.physical_table,
            schema=snap.physical_schema,
        )
        res.apply_hints(
            table_name=spec.target_table,
            primary_key=list(spec.primary_key),
            write_disposition=spec.write_disposition,
        )
        resources.append(res)
    return resources


def _build_dest_engine(staging_db: str):
    """Build the destination SQLAlchemy engine with MariaDB-friendly session config.

    Two MariaDB quirks the init_command works around:

    - dlt sends timezone-aware Python datetimes (Pendulum's UTC tzinfo).
      pymysql serializes those as strings with '+00:00' suffix, which
      MariaDB DATETIME columns reject under STRICT_TRANS_TABLES sql_mode.
      Empty sql_mode (or removing STRICT_TRANS_TABLES) makes MariaDB
      tolerant of the suffix.
    - Setting time_zone='+00:00' aligns session TZ with the datetimes
      so any column reads/writes stay consistent across runs.
    """
    return create_engine(
        _dest_credentials(staging_db),
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "init_command": (
                "SET sql_mode='ALLOW_INVALID_DATES',"
                " time_zone='+00:00',"
                " FOREIGN_KEY_CHECKS=0;"
            ),
        },
    )


def build_pipeline(target_schema: str = "openmrs_test") -> dlt.Pipeline:
    """Construct (but do not run) the dlt pipeline.

    dlt's `dataset_name` IS the destination schema where it writes its
    tables (with `_dlt_*` columns added). We use a parallel
    `<target>_dlt` staging schema; the promote step lifts data from
    there to the actual ``target_schema``.
    """
    staging = staging_schema(target_schema)
    return dlt.pipeline(
        pipeline_name=f"openmrs_loadback__{target_schema}",
        destination=dlt.destinations.sqlalchemy(
            credentials=_build_dest_engine(staging),
        ),
        dataset_name=staging,
        progress="log",
    )


def _state_hash(pipeline: dlt.Pipeline) -> str:
    """SHA-256 of the pipeline state json, the determinism witness."""
    state_path = Path(pipeline.working_dir) / "state.json"
    if not state_path.exists():
        return ""
    return hashlib.sha256(state_path.read_bytes()).hexdigest()


def run_pipeline(target_schema: str = "openmrs_test", promote: bool = True) -> dict[str, Any]:
    """End-to-end: resolve SQLMesh snapshots → dlt load to staging → promote.

    Args:
      target_schema: final OpenMRS destination (e.g. "openmrs_test"). dlt
        writes to ``<target_schema>_dlt`` (the staging schema); the promote
        step copies clean rows from there to ``<target_schema>``.
      promote: if False, only run the dlt load (skips the promote step).
        Used for unit-test-style verification of the dlt half.
    """
    cfg = DBConfig.from_env(database="refapp_28_demo")
    staging = staging_schema(target_schema)
    print(f"Resolving SQLMesh snapshots for {cfg.database} ...")
    snapshots = resolve_snapshots(cfg)
    print(f"  resolved {len(snapshots)} views")

    pipeline = build_pipeline(target_schema)
    resources = build_resources(snapshots)
    print(f"Loading {len(resources)} resources via dlt → {staging} ...")

    info = pipeline.run(resources)

    last_trace = pipeline.last_trace
    run_id = last_trace.transaction_id if last_trace else ""
    state_hash = _state_hash(pipeline)

    report: dict[str, Any] = {
        "pipeline_name": pipeline.pipeline_name,
        "staging_schema": staging,
        "target_schema": target_schema,
        "dlt_pipeline_run_id": run_id,
        "dlt_state_hash": state_hash,
        "dlt_version": dlt.__version__,
        "resources_loaded": [spec.target_table for spec in LOAD_RESOURCES if spec.sqlmesh_view in snapshots],
        "resources_skipped": [
            spec.sqlmesh_view for spec in LOAD_RESOURCES
            if spec.sqlmesh_view not in snapshots
        ],
        "load_info": str(info),
    }

    if promote:
        from harness.load.promote import promote_all, repair_scaffolding_accounts
        print(f"\nPromoting {staging} → {target_schema} ...")
        promote_report = promote_all(staging, target_schema, LOAD_RESOURCES, snapshots)
        report["promote"] = promote_report
        print("Repairing scaffolding accounts (FR-013 deterministic repair) ...")
        report["repair"] = repair_scaffolding_accounts(target_schema)

    return report


__all__ = [
    "LoadResource", "LOAD_RESOURCES",
    "build_resources", "build_pipeline", "run_pipeline",
]
