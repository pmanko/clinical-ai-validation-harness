"""Module classification — fills the ``modules[]`` slot of the profile
inventory artifact.

Each populated legacy table is classified by inferred owning module via
a prefix-based heuristic. The status against the modern (O3) RefApp
distro is derived by intersecting with the target schema's table set
(``bundled`` if the table exists on both sides; ``removed`` if only on
source; ``unknown`` for tables on neither prefix-known nor present in
target).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .db import DBConfig, query


# Prefix → owning module. Order matters: longest prefix wins.
MODULE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("openconceptlab_",  "openconceptlab"),
    ("htmlformentry_",   "htmlformentry"),
    ("formentry_",       "formentry"),
    ("dataintegrity_",   "dataintegrity"),
    ("metadatasharing_", "metadatasharing"),
    ("appointmentscheduling_", "appointmentscheduling"),
    ("addresshierarchy_", "addresshierarchy"),
    ("emrapi_",          "emrapi"),
    ("hl7_",             "hl7"),
    ("logic_",           "logic"),
    ("reporting_",       "reporting"),
    ("xforms_",          "xforms"),
    ("idgen_",           "idgen"),
)

# Tables that are part of Platform/Core but have no prefix.
PLATFORM_CORE_TABLES: frozenset[str] = frozenset({
    "concept", "concept_name", "concept_description", "concept_class",
    "concept_datatype", "concept_map_type", "concept_answer", "concept_set",
    "concept_reference_source", "concept_reference_term", "concept_reference_map",
    "concept_reference_term_map", "concept_numeric", "concept_complex",
    "concept_attribute", "concept_attribute_type", "concept_reference_range",
    "concept_word", "concept_stop_word", "concept_proposal",
    "concept_proposal_tag_map", "concept_name_tag", "concept_name_tag_map",
    "concept_set_derived", "concept_state_conversion",
    "patient", "person", "person_name", "person_address", "person_attribute",
    "person_attribute_type", "person_merge_log",
    "encounter", "encounter_provider", "encounter_diagnosis",
    "encounter_type", "encounter_role",
    "obs", "conditions", "diagnosis_attribute",
    "allergy", "allergy_reaction",
    "drug_order", "drug", "drug_ingredient", "drug_reference_map",
    "orders", "order_type", "order_frequency", "order_attribute",
    "order_attribute_type", "order_set", "order_set_attribute",
    "order_set_attribute_type", "order_set_member", "order_group",
    "order_group_attribute", "order_group_attribute_type", "test_order",
    "location", "location_attribute", "location_attribute_type", "location_tag",
    "location_tag_map",
    "provider", "provider_attribute", "provider_attribute_type",
    "program", "program_attribute_type", "program_workflow",
    "program_workflow_state", "patient_program", "patient_state",
    "patient_program_attribute", "patient_identifier", "patient_identifier_type",
    "visit", "visit_attribute", "visit_attribute_type", "visit_type",
    "form", "form_field", "field", "field_type", "field_answer",
    "form_resource",
    "users", "user_role", "user_property",
    "role", "role_role", "role_privilege", "privilege",
    "global_property", "scheduler_task_config",
    "scheduler_task_config_property", "serialized_object",
    "notification_alert", "notification_alert_recipient", "notification_template",
    "liquibasechangelog", "liquibasechangeloglock",
    "person_name_tag_map", "person_attribute_tag_map",
    "active_list", "active_list_type", "active_list_allergy",
    "active_list_problem",
    "care_setting", "fulfiller_status", "report_object", "report_schema_xml",
    "test_orders", "tribe",
    "relationship", "relationship_type",
    "cohort", "cohort_member",
})


@dataclass(frozen=True)
class ModuleClassification:
    module_id: str
    contributed_tables: list[str]
    status_in_2_8_refapp: str  # 'bundled' | 'optional' | 'removed' | 'unknown'

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "contributed_tables": list(self.contributed_tables),
            "status_in_2_8_refapp": self.status_in_2_8_refapp,
        }


def classify_table(name: str) -> str:
    """Return the owning module_id for ``name``.

    Pure function — no DB. Prefix-first; Platform/Core fallback for
    well-known core tables; ``unknown`` for everything else.
    """
    for prefix, module_id in MODULE_PREFIXES:
        if name.startswith(prefix):
            return module_id
    if name in PLATFORM_CORE_TABLES:
        return "Platform/Core"
    return "unknown"


def _list_tables(cfg: DBConfig) -> set[str]:
    rows = query(cfg, f"""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='{cfg.database}' AND table_type='BASE TABLE'
    """)
    return {r[0] for r in rows if r and r[0]}


def classify_modules(
    source_tables: Iterable[str], target_tables: Iterable[str]
) -> list[ModuleClassification]:
    """Group tables by inferred module and compute per-module
    ``status_in_2_8_refapp``.

    Pure function — no DB. Both ``source_tables`` and ``target_tables``
    are passed in directly so this function is unit-testable.
    """
    src = set(source_tables)
    tgt = set(target_tables)

    by_module: dict[str, list[str]] = {}
    for table in src | tgt:
        mod = classify_table(table)
        by_module.setdefault(mod, []).append(table)

    out: list[ModuleClassification] = []
    for module_id in sorted(by_module):
        tables = sorted(by_module[module_id])
        module_in_src = any(t in src for t in tables)
        module_in_tgt = any(t in tgt for t in tables)
        if module_in_src and module_in_tgt:
            status = "bundled"
        elif module_in_src and not module_in_tgt:
            status = "removed"
        elif module_in_tgt and not module_in_src:
            status = "optional"
        else:
            status = "unknown"
        out.append(ModuleClassification(
            module_id=module_id,
            contributed_tables=tables,
            status_in_2_8_refapp=status,
        ))
    return out


def enumerate_modules(
    source_cfg: DBConfig, target_cfg: DBConfig
) -> list[ModuleClassification]:
    return classify_modules(_list_tables(source_cfg), _list_tables(target_cfg))


def emit(source_cfg: DBConfig, target_cfg: DBConfig) -> dict[str, list[dict[str, Any]]]:
    return {
        "modules": [m.to_dict() for m in enumerate_modules(source_cfg, target_cfg)],
    }


__all__ = [
    "MODULE_PREFIXES", "PLATFORM_CORE_TABLES",
    "ModuleClassification",
    "classify_table", "classify_modules", "enumerate_modules", "emit",
]
