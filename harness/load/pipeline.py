"""Load manifest + entry point: SQLMesh snapshot tables → the OpenMRS build schema.

This module owns the *what to load* (the FK-ordered `LOAD_RESOURCES` manifest +
the excluded-with-reason list the completeness gate checks) and the run entry
point. The actual copy is done by ``harness/load/loader.py`` — a direct
``INSERT … SELECT`` from each resolved SQLMesh snapshot into the target schema.
There is no dlt and no staging schema: SQLMesh's snapshot tables are already
clean relational tables, so we read them directly.

  legacy_27_raw  →[SQLMesh]→  refapp_28_demo (snapshots)  →[direct loader]→  openmrs_test

Resource ordering follows FK dependency: parents before children (person before
patient before encounter before obs). Reference/lookup tables use ``merge`` so
legacy IDs coexist with CIEL-baseline stock; clinical fact tables use ``replace``
because the legacy corpus is the canonical clinical history. ``concept_*`` tables
are NOT loaded — CIEL already populated them in the build schema via
``scripts/loadtest-up.sh`` cloning the CIEL-loaded ``openmrs`` canvas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harness.load.loader import load_all, repair_scaffolding_accounts
from harness.load.snapshot_resolver import resolve_snapshots
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

    # ---- Clinical / fact tables (mostly replace — legacy is canonical; a few
    #      merge: *_type lookups + the carry-forward concept/concept_name rows) ----
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


# --------------------------------------------------------------------------
# Run entry point
# --------------------------------------------------------------------------


def run_load(target_schema: str = "openmrs_test") -> dict[str, Any]:
    """End-to-end: resolve SQLMesh snapshots → direct-load into the build schema.

    Reads each ``LOAD_RESOURCES`` table from its resolved snapshot in
    ``sqlmesh__refapp_28_demo`` and copies it into ``target_schema`` (default
    ``openmrs_test``) with the manifest's per-table write disposition, then runs
    the FR-013 scaffolding-account repair. The build schema is dumped by
    ``scripts/dump-loaded.sh`` into the portable demo-data artifact; instances are
    provisioned FROM that dump (``scripts/seed-local.sh`` / ``cloud-seed.sh``),
    never mutated in place.
    """
    cfg = DBConfig.from_env(database="refapp_28_demo")
    print(f"Resolving SQLMesh snapshots for {cfg.database} ...")
    snapshots = resolve_snapshots(cfg)
    print(f"  resolved {len(snapshots)} views")

    n_to_load = sum(1 for spec in LOAD_RESOURCES if spec.sqlmesh_view in snapshots)
    print(f"Loading {n_to_load} resources → {target_schema} ...")
    load_report = load_all(target_schema, LOAD_RESOURCES, snapshots)

    print("Repairing scaffolding accounts (FR-013 deterministic repair) ...")
    repair = repair_scaffolding_accounts(target_schema)

    return {
        "target_schema": target_schema,
        "resources_loaded": [spec.target_table for spec in LOAD_RESOURCES
                             if spec.sqlmesh_view in snapshots],
        "resources_skipped": [spec.sqlmesh_view for spec in LOAD_RESOURCES
                             if spec.sqlmesh_view not in snapshots],
        "load": load_report,
        "repair": repair,
    }


__all__ = [
    "LoadResource", "LOAD_RESOURCES", "EXCLUDED_PREFIXES", "EXCLUDED_WITH_REASON",
    "run_load",
]
