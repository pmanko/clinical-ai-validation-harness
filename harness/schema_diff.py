"""Schema diff between the source corpus and the target RefApp baseline.

Produces an artifact matching ``contracts/schema_diff.schema.yaml``. The
diff is structural — table inventory, column types, indexes, FK
constraints. Per-item ``clinical_meaningful`` classification follows
``research.md`` §R5.

Two entry points:

  - ``diff_schemas(source_cfg, target_cfg, *, populated_source_tables)``
    returns the dict matching the contract. Pure orchestration; the
    introspection helpers (``list_tables``, ``list_columns``,
    ``list_indexes``, ``list_foreign_keys``) are exposed for testing
    and reuse.
  - ``write_schema_diff(output_dir, ...)`` keeps a backward-compatible
    signature for the existing ``harness-cli schema-diff`` flow. When
    called without source/target configs it writes a stub-shaped JSON
    so existing callers don't break before a real run is possible.

Introspection talks to MariaDB via ``harness.profile.db.query`` (the
same subprocess shim ``harness.profile.inventory`` uses), so this module
works without a native Python DB driver.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .profile.db import DBConfig, query


# §R5 — tables whose presence/structure is clinically meaningful.
CLINICAL_TABLES: frozenset[str] = frozenset({
    "patient", "person", "person_name", "person_address", "person_attribute",
    "encounter", "encounter_provider", "encounter_diagnosis",
    "obs", "conditions", "diagnosis_attribute",
    "allergy", "allergy_reaction",
    "drug_order", "drug", "drug_ingredient", "test_order",
    "concept", "concept_name",
    "concept_reference_map", "concept_reference_source", "concept_reference_term",
    "location", "provider", "provider_attribute",
    "orders", "order_type", "order_frequency",
    "program", "patient_program", "patient_state",
    "visit", "visit_attribute",
    "form", "form_field", "field",
})

# §R5 — columns whose alteration is clinically meaningful regardless of
# which table they sit on.
CLINICALLY_LOADED_COLUMN_SUFFIXES: tuple[str, ...] = (
    "_concept_id", "concept_id",
    "_coded", "value_coded",
)


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str           # 'int', 'varchar', etc.
    column_type: str         # 'int(11)', 'varchar(255)' — full spec
    is_nullable: bool
    column_key: str          # '', 'PRI', 'UNI', 'MUL'


@dataclass(frozen=True)
class IndexInfo:
    name: str
    columns: tuple[str, ...]
    non_unique: bool


@dataclass(frozen=True)
class ForeignKey:
    constraint_name: str
    column: str
    referenced_table: str
    referenced_column: str


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: dict[str, ColumnInfo] = field(default_factory=dict)
    indexes: dict[str, IndexInfo] = field(default_factory=dict)
    foreign_keys: list[ForeignKey] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DB introspection helpers
# ---------------------------------------------------------------------------


def list_tables(cfg: DBConfig) -> set[str]:
    rows = query(cfg, f"""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='{cfg.database}' AND table_type='BASE TABLE'
    """)
    return {r[0] for r in rows if r and r[0]}


def list_columns(cfg: DBConfig, table: str) -> dict[str, ColumnInfo]:
    rows = query(cfg, f"""
        SELECT column_name, data_type, column_type, is_nullable, column_key
        FROM information_schema.columns
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
        ORDER BY ordinal_position
    """)
    out: dict[str, ColumnInfo] = {}
    for r in rows:
        out[r[0]] = ColumnInfo(
            name=r[0], data_type=r[1] or "", column_type=r[2] or "",
            is_nullable=(r[3] == "YES"), column_key=r[4] or "",
        )
    return out


def list_indexes(cfg: DBConfig, table: str) -> dict[str, IndexInfo]:
    rows = query(cfg, f"""
        SELECT index_name, column_name, non_unique
        FROM information_schema.statistics
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
        ORDER BY index_name, seq_in_index
    """)
    grouped: dict[str, list[tuple[str, bool]]] = {}
    for r in rows:
        idx_name, col_name, non_unique = r[0], r[1], r[2]
        grouped.setdefault(idx_name, []).append((col_name, bool(int(non_unique))))
    return {
        name: IndexInfo(name=name, columns=tuple(c for c, _ in cols), non_unique=cols[0][1])
        for name, cols in grouped.items()
    }


def list_foreign_keys(cfg: DBConfig, table: str) -> list[ForeignKey]:
    rows = query(cfg, f"""
        SELECT constraint_name, column_name, referenced_table_name, referenced_column_name
        FROM information_schema.key_column_usage
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
          AND referenced_table_name IS NOT NULL
        ORDER BY constraint_name, ordinal_position
    """)
    return [
        ForeignKey(constraint_name=r[0], column=r[1],
                   referenced_table=r[2], referenced_column=r[3])
        for r in rows
    ]


def introspect_table(cfg: DBConfig, table: str) -> TableSchema:
    return TableSchema(
        name=table,
        columns=list_columns(cfg, table),
        indexes=list_indexes(cfg, table),
        foreign_keys=list_foreign_keys(cfg, table),
    )


def populated_tables(cfg: DBConfig) -> set[str]:
    """Set of tables with ≥1 row. Used to classify clinical-meaningful per §R5."""
    rows = query(cfg, f"""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='{cfg.database}' AND table_type='BASE TABLE'
    """)
    candidates = [r[0] for r in rows if r and r[0]]
    out: set[str] = set()
    for name in candidates:
        n = query(cfg, f"SELECT COUNT(*) FROM `{name}` LIMIT 1")
        if n and int(n[0][0] or 0) > 0:
            out.add(name)
    return out


# ---------------------------------------------------------------------------
# Classification (pure — no DB)
# ---------------------------------------------------------------------------


def _is_clinically_loaded_column(column_name: str, column_key: str) -> bool:
    """A column participates in clinically-loaded surface per §R5 if it has a
    concept/coded/foreign-key/unique role."""
    if column_key in {"PRI", "UNI", "MUL"}:
        return True
    name = column_name.lower()
    return any(name.endswith(s) for s in CLINICALLY_LOADED_COLUMN_SUFFIXES)


def classify_table_diff(
    table: str, *, populated_in_source: bool, in_target: bool, in_source: bool
) -> tuple[bool, str]:
    """Return (clinical_meaningful, rationale) for a table-level diff item.

    §R5 rule:
      - If the table is in the §R5 clinical-table set AND is populated in
        source, it's clinically meaningful.
      - Otherwise cosmetic.
    """
    if table in CLINICAL_TABLES:
        if populated_in_source:
            return True, f"table {table!r} is in the §R5 clinical-reference set and is populated in the source corpus"
        return True, f"table {table!r} is in the §R5 clinical-reference set (target-side change matters even if source is empty)"
    return False, ""


def classify_column_diff(
    table: str, column: ColumnInfo, *, populated_in_source: bool
) -> tuple[bool, str]:
    if table in CLINICAL_TABLES and populated_in_source:
        return True, (
            f"column {table}.{column.name} sits on a §R5 clinical-reference table that is populated in source"
        )
    if _is_clinically_loaded_column(column.name, column.column_key):
        return True, (
            f"column {table}.{column.name} participates in an FK, unique constraint, or concept/coded role"
        )
    return False, ""


# ---------------------------------------------------------------------------
# Diff orchestration
# ---------------------------------------------------------------------------


def _column_diff_id(table: str, column: str, kind: str) -> str:
    return f"table:{table}:{column}:{kind}"


def _table_diff_id(table: str, kind: str) -> str:
    return f"table:{table}:{kind}"


def diff_table_inventories(
    source: set[str], target: set[str], *, source_populated: set[str]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for t in sorted(source - target):
        cm, why = classify_table_diff(
            t,
            populated_in_source=t in source_populated,
            in_target=False, in_source=True,
        )
        item = {
            "id": _table_diff_id(t, "only_in_source"),
            "category": "table_only_in_source",
            "clinical_meaningful": cm,
            "details": {"table": t, "populated_in_source": t in source_populated},
        }
        if cm:
            item["clinical_meaningful_rationale"] = why
        items.append(item)
    for t in sorted(target - source):
        cm, why = classify_table_diff(
            t, populated_in_source=False, in_target=True, in_source=False,
        )
        item = {
            "id": _table_diff_id(t, "only_in_target"),
            "category": "table_only_in_target",
            "clinical_meaningful": cm,
            "details": {"table": t},
        }
        if cm:
            item["clinical_meaningful_rationale"] = why
        items.append(item)
    return items


def diff_shared_table(
    table: str, src: TableSchema, tgt: TableSchema, *, populated_in_source: bool
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    src_cols = src.columns
    tgt_cols = tgt.columns
    for col in sorted(set(src_cols) - set(tgt_cols)):
        info = src_cols[col]
        cm, why = classify_column_diff(table, info, populated_in_source=populated_in_source)
        item = {
            "id": _column_diff_id(table, col, "removed"),
            "category": "column_removed",
            "clinical_meaningful": cm,
            "details": {
                "table": table, "column": col,
                "source_type": info.column_type, "column_key": info.column_key,
            },
        }
        if cm: item["clinical_meaningful_rationale"] = why
        items.append(item)
    for col in sorted(set(tgt_cols) - set(src_cols)):
        info = tgt_cols[col]
        cm, why = classify_column_diff(table, info, populated_in_source=populated_in_source)
        item = {
            "id": _column_diff_id(table, col, "added"),
            "category": "column_added",
            "clinical_meaningful": cm,
            "details": {
                "table": table, "column": col,
                "target_type": info.column_type, "column_key": info.column_key,
            },
        }
        if cm: item["clinical_meaningful_rationale"] = why
        items.append(item)
    for col in sorted(set(src_cols) & set(tgt_cols)):
        s = src_cols[col]
        t = tgt_cols[col]
        if s.column_type != t.column_type:
            cm, why = classify_column_diff(table, s, populated_in_source=populated_in_source)
            item = {
                "id": _column_diff_id(table, col, "retyped"),
                "category": "column_retyped",
                "clinical_meaningful": cm,
                "details": {
                    "table": table, "column": col,
                    "source_type": s.column_type, "target_type": t.column_type,
                },
            }
            if cm: item["clinical_meaningful_rationale"] = why
            items.append(item)

    # Indexes — coarse comparison by name.
    src_idx_names = set(src.indexes)
    tgt_idx_names = set(tgt.indexes)
    for name in sorted(src_idx_names ^ tgt_idx_names):
        side = "only_in_source" if name in src_idx_names else "only_in_target"
        idx = (src.indexes.get(name) or tgt.indexes.get(name))
        item = {
            "id": f"index:{table}:{name}:{side}",
            "category": "index_difference",
            "clinical_meaningful": table in CLINICAL_TABLES,
            "details": {"table": table, "index": name, "side": side,
                        "columns": list(idx.columns) if idx else []},
        }
        if table in CLINICAL_TABLES:
            item["clinical_meaningful_rationale"] = (
                f"index on §R5 clinical-reference table {table!r}"
            )
        items.append(item)

    # FK constraints — name-based shallow comparison.
    src_fks = {fk.constraint_name for fk in src.foreign_keys}
    tgt_fks = {fk.constraint_name for fk in tgt.foreign_keys}
    for name in sorted(src_fks ^ tgt_fks):
        side = "only_in_source" if name in src_fks else "only_in_target"
        items.append({
            "id": f"constraint:{table}:{name}:{side}",
            "category": "constraint_difference",
            "clinical_meaningful": table in CLINICAL_TABLES,
            "details": {"table": table, "constraint": name, "side": side},
            **({"clinical_meaningful_rationale":
                f"FK on §R5 clinical-reference table {table!r}"}
               if table in CLINICAL_TABLES else {}),
        })
    return items


def diff_schemas(
    source_cfg: DBConfig, target_cfg: DBConfig
) -> dict[str, Any]:
    src_tables = list_tables(source_cfg)
    tgt_tables = list_tables(target_cfg)
    src_pop = populated_tables(source_cfg)
    items: list[dict[str, Any]] = list(diff_table_inventories(
        src_tables, tgt_tables, source_populated=src_pop,
    ))
    for table in sorted(src_tables & tgt_tables):
        src_schema = introspect_table(source_cfg, table)
        tgt_schema = introspect_table(target_cfg, table)
        items.extend(diff_shared_table(
            table, src_schema, tgt_schema,
            populated_in_source=table in src_pop,
        ))
    return {
        "schema_version": 1,
        "kind": "SchemaDiff",
        "source_schema_id": source_cfg.database,
        "target_schema_id": target_cfg.database,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "items": items,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _render_summary(diff: dict[str, Any]) -> str:
    items: Iterable[dict[str, Any]] = diff.get("items", [])
    by_category: dict[str, int] = {}
    cm_count = 0
    for it in items:
        by_category[it["category"]] = by_category.get(it["category"], 0) + 1
        if it.get("clinical_meaningful"):
            cm_count += 1
    total = sum(by_category.values())
    lines = [
        "# Schema diff summary",
        "",
        f"- Source: `{diff['source_schema_id']}`",
        f"- Target: `{diff['target_schema_id']}`",
        f"- Generated: {diff['generated_at']}",
        f"- Total diff items: **{total}**",
        f"- Clinically meaningful (per research.md §R5): **{cm_count}**",
        "",
        "## By category",
        "",
    ]
    for cat in sorted(by_category):
        lines.append(f"- `{cat}`: {by_category[cat]}")
    return "\n".join(lines) + "\n"


def write_schema_diff_real(
    output_dir: Path, source_cfg: DBConfig, target_cfg: DBConfig
) -> tuple[Path, Path]:
    """Compute the real diff against two DBs and write the artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    diff = diff_schemas(source_cfg, target_cfg)
    diff_path = output_dir / "schema_diff.json"
    summary_path = output_dir / "summary.md"
    diff_path.write_text(json.dumps(diff, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(_render_summary(diff), encoding="utf-8")
    return diff_path, summary_path


def write_schema_diff(output_dir: Path) -> tuple[Path, Path]:
    """Backward-compatible entry used by ``harness-cli schema-diff``.

    Tries the real diff against ``legacy_27_raw`` and ``openmrs`` from the
    default env-driven config. Falls back to a placeholder shape if the
    introspection fails so the CLI doesn't crash when the stack is down.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        return write_schema_diff_real(
            output_dir,
            DBConfig.from_env(database="legacy_27_raw"),
            DBConfig.from_env(database="openmrs"),
        )
    except Exception as exc:
        placeholder = {
            "schema_version": 1,
            "kind": "SchemaDiff",
            "source_schema_id": "legacy_27_raw",
            "target_schema_id": "openmrs",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": [],
            "error": f"introspection failed: {exc.__class__.__name__}: {exc}",
        }
        diff_path = output_dir / "schema_diff.json"
        summary_path = output_dir / "summary.md"
        diff_path.write_text(json.dumps(placeholder, indent=2) + "\n", encoding="utf-8")
        summary_path.write_text(
            f"# Schema diff (not computed)\n\nIntrospection failed: {exc}\n",
            encoding="utf-8",
        )
        return diff_path, summary_path


__all__ = [
    "CLINICAL_TABLES", "CLINICALLY_LOADED_COLUMN_SUFFIXES",
    "ColumnInfo", "IndexInfo", "ForeignKey", "TableSchema",
    "list_tables", "list_columns", "list_indexes", "list_foreign_keys",
    "introspect_table", "populated_tables",
    "_is_clinically_loaded_column",
    "classify_table_diff", "classify_column_diff",
    "diff_table_inventories", "diff_shared_table", "diff_schemas",
    "write_schema_diff", "write_schema_diff_real",
]
