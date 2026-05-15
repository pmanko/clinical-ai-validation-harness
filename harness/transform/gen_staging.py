"""Generate SQLMesh staging models for every populated legacy table.

Each staging model is a 1:1 copy from ``legacy_27_raw.<table>`` into the
``refapp_28_demo.staging`` schema, with concept-FK columns rebound via
``concept_translation``. The set of FK columns that route through the
bridge rule is small and well-known (concept_id, value_coded, value_drug,
etc.); other columns pass through unchanged.

The generated files live under ``datasets/transforms/sqlmesh/models/staging/``
and are deterministic given the same inputs.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from harness.profile.db import DBConfig, query


# Concept-FK columns that are rebound via the bridge rule.
CONCEPT_FK_COLUMNS = {
    "concept_id",
    "value_coded",
    "value_coded_name_id",
    "class_id",
    "datatype_id",
    "concept_class_id",
    "concept_datatype_id",
    "concept_map_type_id",
    "concept_source_id",
    "concept_reference_term_id",
    "answer_concept",
    "coded_allergen",
    "severity_concept_id",
    "condition_coded",
    "condition_coded_name_id",
}

# Skip these legacy tables entirely — they are terminology/dictionary tables
# that the target gets from CIEL, not from legacy.
TERMINOLOGY_TABLES = {
    "concept",
    "concept_name",
    "concept_description",
    "concept_class",
    "concept_datatype",
    "concept_map_type",
    "concept_answer",
    "concept_set",
    "concept_reference_source",
    "concept_reference_term",
    "concept_reference_map",
    "concept_reference_term_map",
    "concept_numeric",
    "concept_complex",
    "concept_attribute",
    "concept_attribute_type",
    "concept_reference_range",
    "concept_word",
    "concept_stop_word",
    "concept_proposal",
    "concept_proposal_tag_map",
    "concept_name_tag",
    "concept_name_tag_map",
    "concept_set_derived",
    "concept_state_conversion",
}

# Audit-only tables that have no clinical references; skip too.
AUDIT_ONLY_TABLES = {
    "audit_log",
    "log",
    "session_log",
    "scheduler_task_config",
    "scheduler_task_config_property",
    "global_property",
    "person_merge_log",
}


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    is_concept_fk: bool


@dataclass(frozen=True)
class TableInfo:
    name: str
    pk_columns: list[str]
    columns: list[ColumnInfo]


def list_populated_tables(cfg: DBConfig) -> list[str]:
    rows = query(cfg, f"""
        SELECT t.table_name
        FROM information_schema.tables t
        WHERE t.table_schema='{cfg.database}' AND t.table_type='BASE TABLE'
        ORDER BY t.table_name
    """)
    candidates = [r[0] for r in rows if r and r[0]]
    populated: list[str] = []
    for name in candidates:
        n = query(cfg, f"SELECT COUNT(*) FROM `{name}`")
        if n and int(n[0][0] or 0) > 0:
            populated.append(name)
    return populated


def describe_table(cfg: DBConfig, table: str) -> TableInfo:
    cols = query(cfg, f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
        ORDER BY ordinal_position
    """)
    pks = query(cfg, f"""
        SELECT column_name FROM information_schema.key_column_usage
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
          AND constraint_name='PRIMARY'
        ORDER BY ordinal_position
    """)
    return TableInfo(
        name=table,
        pk_columns=[r[0] for r in pks],
        columns=[ColumnInfo(name=r[0], is_concept_fk=r[0] in CONCEPT_FK_COLUMNS) for r in cols],
    )


def render_staging_model(table: TableInfo, source_schema: str) -> str:
    """Emit the SQL for one staging model.

    Concept-FK columns are wrapped in a left-join lookup against the
    concept_translation seed. Non-FK columns pass through.
    """
    select_lines: list[str] = []
    join_lines: list[str] = []
    join_idx = 0
    for col in table.columns:
        if col.is_concept_fk:
            alias = f"ct_{join_idx}"
            join_lines.append(
                f"  LEFT JOIN refapp_28_demo.seed__concept_translation {alias} "
                f"ON {alias}.source_concept_id = src.{col.name}"
            )
            select_lines.append(
                f"  COALESCE({alias}.target_concept_id, src.{col.name}) AS {col.name}"
            )
            join_idx += 1
        else:
            select_lines.append(f"  src.{col.name}")
    select_clause = ",\n".join(select_lines)
    join_clause = "\n".join(join_lines)

    pk_clause = ", ".join(table.pk_columns) if table.pk_columns else "1"
    # Audit only when the PK is a single column — SQLMesh's `unique_values`
    # audit treats each named column as independently unique (not as a
    # compound key), so multi-column PKs would falsely fail.
    audits_clause = (
        f"  audits (unique_values(columns := ({pk_clause})))"
        if len(table.pk_columns) == 1
        else "  audits ()"
    )

    model_name = f"refapp_28_demo.stg_{table.name}"

    return f"""MODEL (
  name {model_name},
  kind FULL,
  description 'Staging copy of {source_schema}.{table.name} with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain ({pk_clause}),
{audits_clause}
);

SELECT
{select_clause}
FROM {source_schema}.{table.name} src
{join_clause}
;
"""


def write_staging_model(model: str, table: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"stg__legacy_{table}.sql"
    path.write_text(model)
    return path


def generate_all(cfg: DBConfig, out_dir: Path, source_schema: str) -> list[Path]:
    populated = list_populated_tables(cfg)
    eligible = [
        t for t in populated
        if t not in TERMINOLOGY_TABLES and t not in AUDIT_ONLY_TABLES
    ]
    paths: list[Path] = []
    for table_name in eligible:
        info = describe_table(cfg, table_name)
        sql = render_staging_model(info, source_schema)
        paths.append(write_staging_model(sql, table_name, out_dir))
    return paths


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.transform.gen_staging")
    p.add_argument("--db", default="legacy_27_raw")
    p.add_argument("--out-dir", default="datasets/transforms/sqlmesh/models/staging")
    p.add_argument("--source-schema", default="legacy_27_raw")
    args = p.parse_args(argv)
    cfg = DBConfig.from_env(database=args.db)
    paths = generate_all(cfg, Path(args.out_dir), args.source_schema)
    print(f"Wrote {len(paths)} staging models to {args.out_dir}")
    for p in paths:
        print(f"  {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
