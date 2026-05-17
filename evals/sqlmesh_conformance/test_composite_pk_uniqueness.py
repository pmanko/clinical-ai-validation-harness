"""Composite-PK uniqueness assertion for staging models.

SQLMesh's built-in ``unique_values((a, b))`` audit treats columns
independently — it asserts that each of ``a`` and ``b`` is individually
unique, not that the row ``(a, b)`` is unique. For tables with
multi-column PKs the model declares ``audits ()`` (empty) per
``contracts/sqlmesh_project.profile.md`` and the composite uniqueness
is asserted here instead.

When SQLMesh ships ``unique_rows((a, b))`` (or equivalent), move this
back inline as a model audit and delete this file.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from harness.profile.db import DBConfig, DBError, query, query_scalar


# (table, [pk_columns]) — must match the seed/legacy schema's PRIMARY KEY.
COMPOSITE_PK_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stg_liquibasechangelog", ("ID", "AUTHOR", "FILENAME")),
    ("stg_role_privilege",     ("role", "privilege")),
    ("stg_user_property",      ("user_id", "property")),
    ("stg_user_role",          ("user_id", "role")),
)


def _openmrs_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return query_scalar(
            DBConfig.from_env(database="refapp_28_demo"),
            "SELECT 1",
            timeout=5,
        ) == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


db_only = pytest.mark.skipif(
    not _openmrs_db_available(),
    reason="refapp_28_demo not reachable (run sqlmesh plan first)",
)


@db_only
@pytest.mark.parametrize("table,pk_cols", COMPOSITE_PK_TABLES)
def test_composite_pk_is_unique(table: str, pk_cols: tuple[str, ...]):
    """Assert no duplicate ``(pk_cols)`` rows in the materialized
    staging table."""
    cfg = DBConfig.from_env(database="refapp_28_demo")
    col_list = ", ".join(f"`{c}`" for c in pk_cols)
    sql = f"""
        SELECT {col_list}, COUNT(*) AS dup_count
        FROM `refapp_28_demo`.`{table}`
        GROUP BY {col_list}
        HAVING COUNT(*) > 1
    """
    rows = query(cfg, sql, timeout=30)
    assert not rows, (
        f"Composite PK violation in {table}({pk_cols}): "
        f"{len(rows)} duplicate row groups. First offender: {rows[0]}"
    )
