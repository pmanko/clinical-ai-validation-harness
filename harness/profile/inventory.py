"""T021: source-corpus profile inventory.

Enumerates every table in the legacy schema (default: `legacy_27_raw`) and
produces a JSON document matching `contracts/profile_inventory.schema.yaml`:

  - tables[]: name, row_count, populated_columns[non_null+distinct], pk_range,
              foreign_keys_out[]
  - source_dump_path / source_dump_checksum / generated_at

T022 (terminology — reference_sources, locales) and T023 (modules) are
separate modules that augment the same JSON; this file is responsible for
the `tables[]` core and the orchestrator entrypoint.

Performance note: `information_schema.tables.table_rows` is approximate on
InnoDB and can drift wildly. We use `COUNT(*)` per table for accurate row
counts. For populated tables, column non-null + distinct counts are bundled
into ONE aggregate query per table to avoid N*cols round-trips.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from harness.profile.db import DBConfig, query, query_scalar


# Identifier safety: MariaDB identifiers in information_schema are well-formed;
# we still backtick-wrap them as defense in depth. We refuse anything that
# contains a backtick or NUL.
def _ident(name: str) -> str:
    if "`" in name or "\x00" in name:
        raise ValueError(f"refusing to quote unsafe identifier: {name!r}")
    return f"`{name}`"


@dataclass
class PopulatedColumn:
    name: str
    non_null_count: int
    distinct_count: int


@dataclass
class PKRange:
    min: int
    max: int


@dataclass
class ForeignKey:
    column: str
    references: str  # "<table>.<column>"


@dataclass
class TableSummary:
    name: str
    row_count: int
    populated_columns: list[PopulatedColumn] = field(default_factory=list)
    pk_range: PKRange | None = None
    foreign_keys_out: list[ForeignKey] = field(default_factory=list)


def list_tables(cfg: DBConfig) -> list[str]:
    rows = query(cfg, f"""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='{cfg.database}' AND table_type='BASE TABLE'
        ORDER BY table_name
    """)
    return [r[0] for r in rows if r and r[0]]


def list_columns(cfg: DBConfig, table: str) -> list[tuple[str, str]]:
    """Return [(column_name, data_type), ...] in ordinal order."""
    rows = query(cfg, f"""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
        ORDER BY ordinal_position
    """)
    return [(r[0], r[1]) for r in rows]


def primary_key_columns(cfg: DBConfig, table: str) -> list[str]:
    rows = query(cfg, f"""
        SELECT column_name FROM information_schema.key_column_usage
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
          AND constraint_name='PRIMARY'
        ORDER BY ordinal_position
    """)
    return [r[0] for r in rows]


def foreign_keys_out(cfg: DBConfig, table: str) -> list[ForeignKey]:
    rows = query(cfg, f"""
        SELECT column_name, referenced_table_name, referenced_column_name
        FROM information_schema.key_column_usage
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
          AND referenced_table_name IS NOT NULL
        ORDER BY column_name
    """)
    return [
        ForeignKey(column=r[0], references=f"{r[1]}.{r[2]}")
        for r in rows
    ]


def row_count(cfg: DBConfig, table: str) -> int:
    val = query_scalar(cfg, f"SELECT COUNT(*) FROM {_ident(table)}")
    return int(val or 0)


def populated_column_stats(
    cfg: DBConfig, table: str, columns: list[str]
) -> list[PopulatedColumn]:
    """Single-query aggregate: COUNT(col), COUNT(DISTINCT col) for every column."""
    if not columns:
        return []
    # Build SELECT with one (non_null, distinct) pair per column.
    selects: list[str] = []
    for c in columns:
        ic = _ident(c)
        selects.append(f"COUNT({ic}) AS `nn_{c}`")
        selects.append(f"COUNT(DISTINCT {ic}) AS `dc_{c}`")
    sql = f"SELECT {', '.join(selects)} FROM {_ident(table)}"
    row = query(cfg, sql, timeout=300)
    if not row:
        return []
    vals = row[0]
    out: list[PopulatedColumn] = []
    for i, c in enumerate(columns):
        nn = int(vals[i * 2] or 0)
        dc = int(vals[i * 2 + 1] or 0)
        if nn > 0:
            out.append(PopulatedColumn(name=c, non_null_count=nn, distinct_count=dc))
    return out


def pk_range(cfg: DBConfig, table: str, pk_cols: list[str]) -> PKRange | None:
    # Only meaningful for single-column integer PKs.
    if len(pk_cols) != 1:
        return None
    col = pk_cols[0]
    # Probe the column's data type to confirm integer.
    rows = query(cfg, f"""
        SELECT data_type FROM information_schema.columns
        WHERE table_schema='{cfg.database}' AND table_name='{table}'
          AND column_name='{col}'
    """)
    if not rows or rows[0][0] not in {"int", "bigint", "smallint", "tinyint", "mediumint"}:
        return None
    row = query(cfg, f"SELECT MIN({_ident(col)}), MAX({_ident(col)}) FROM {_ident(table)}")
    if not row or row[0][0] is None:
        return None
    return PKRange(min=int(row[0][0]), max=int(row[0][1]))


def summarize_table(cfg: DBConfig, table: str) -> TableSummary:
    rc = row_count(cfg, table)
    summary = TableSummary(name=table, row_count=rc)
    summary.foreign_keys_out = foreign_keys_out(cfg, table)
    pk_cols = primary_key_columns(cfg, table)
    if rc > 0:
        cols = [c for c, _ in list_columns(cfg, table)]
        summary.populated_columns = populated_column_stats(cfg, table, cols)
        summary.pk_range = pk_range(cfg, table, pk_cols)
    return summary


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_inventory(
    cfg: DBConfig,
    *,
    source_dump_path: Path,
    progress: bool = False,
) -> dict[str, Any]:
    tables = list_tables(cfg)
    summaries: list[TableSummary] = []
    for i, t in enumerate(tables, 1):
        if progress:
            print(f"  [{i:3d}/{len(tables)}] {t}", flush=True)
        summaries.append(summarize_table(cfg, t))

    return {
        "schema_version": 1,
        "kind": "ProfileInventory",
        "source_dump_path": str(source_dump_path),
        "source_dump_checksum": sha256_file(source_dump_path),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tables": [_table_to_dict(s) for s in summaries],
        # T022/T023 fill these; emit empty arrays so the artifact validates
        # against the contract even before those modules land.
        "reference_sources": [],
        "locales": [],
        "modules": [],
    }


def _table_to_dict(s: TableSummary) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": s.name,
        "row_count": s.row_count,
        "populated_columns": [asdict(c) for c in s.populated_columns],
        "foreign_keys_out": [asdict(fk) for fk in s.foreign_keys_out],
    }
    if s.pk_range is not None:
        d["pk_range"] = asdict(s.pk_range)
    return d


def write_inventory(inventory: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inventory, indent=2) + "\n")
    return out_path
