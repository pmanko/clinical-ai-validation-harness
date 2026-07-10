"""Direct loader: copy clean rows from a SQLMesh snapshot table into the OpenMRS
target schema, in FK-dependency order, with per-table write semantics.

The transform (SQLMesh) materializes ``refapp_28_demo.<view>`` over physical
snapshot tables in ``sqlmesh__refapp_28_demo``. This module reads each resolved
snapshot table directly and writes it into the build schema (``openmrs_test``)
using only the OpenMRS-defined column set. There is no dlt staging schema: the
snapshot tables are already clean relational tables, so we ``INSERT … SELECT``
straight across (cross-schema, same MariaDB instance).

For each resource in the load manifest:

  1. Read the destination's column list from ``information_schema.columns``.
  2. Read the source snapshot's column list (the 2.7 shape may lack 2.8-only
     destination columns; those are left to MySQL's default and reported).
  3. ``replace`` → TRUNCATE the destination + INSERT the intersection;
     ``merge`` → INSERT IGNORE (legacy IDs coexist with CIEL-baseline stock);
     ``append`` → plain INSERT.

Errors surface clearly per-resource (destination column missing in the source,
type mismatch, etc.) so iteration can fix the SQLMesh model.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

import pymysql

if TYPE_CHECKING:
    from harness.load.pipeline import LoadResource
    from harness.load.snapshot_resolver import ResolvedSnapshot


def _connect(schema: str):
    """Open a pymysql connection at session SQL mode permissive of MariaDB datetime quirks."""
    host = os.environ.get("MARIADB_HOST", "127.0.0.1")
    port = int(os.environ.get("MARIADB_PORT", "3307"))
    user = os.environ.get("MARIADB_USER", "openmrs")
    password = os.environ.get("MARIADB_PASSWORD", "openmrs")
    conn = pymysql.connect(
        host=host, port=port, user=user, password=password,
        database=schema, charset="utf8mb4",
        init_command=(
            "SET sql_mode='ALLOW_INVALID_DATES',"
            " time_zone='+00:00',"
            " FOREIGN_KEY_CHECKS=0;"
        ),
        autocommit=False,
    )
    return conn


def _table_columns(conn, schema: str, table: str) -> list[str]:
    """Ordered column list of a table in ``schema`` (ordinal position)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            ORDER BY ordinal_position
        """, (schema, table))
        return [r[0] for r in cur.fetchall()]


def _build_load_sql(
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    write_disposition: str,
    dest_cols: list[str],
    src_cols: list[str],
) -> tuple[list[str], list[str]]:
    """Pure: the SQL statements that copy ``source_schema.source_table`` →
    ``target_schema.target_table`` for one write disposition.

    Returns ``(statements, dropped_columns)``:

    - The column set is the intersection of the destination's columns (minus any
      ``_dlt_*`` defense-in-depth) and the source's columns. ``dropped_columns``
      are destination columns absent from the source (2.8-only; left to default).
    - ``replace`` → [TRUNCATE, INSERT …]; ``merge`` → [INSERT IGNORE …];
      ``append`` → [INSERT …]. The INSERT always reads ``FROM source_schema
      .source_table`` — the resolved SQLMesh snapshot, whose name differs from the
      OpenMRS target table name.
    - No shared columns → ``([], dest_cols)`` so the caller can surface the error.

    Raises ``ValueError`` on an unknown disposition.
    """
    dest = [c for c in dest_cols if not c.startswith("_dlt_")]
    src = set(src_cols)
    common = [c for c in dest if c in src]
    dropped = [c for c in dest if c not in src]

    if write_disposition not in {"replace", "merge", "append"}:
        raise ValueError(f"unknown write_disposition {write_disposition!r}")

    if not common:
        return [], dropped

    col_list = ", ".join(f"`{c}`" for c in common)
    select = (
        f"({col_list}) SELECT {col_list} "
        f"FROM `{source_schema}`.`{source_table}`"
    )
    statements: list[str] = []
    if write_disposition == "replace":
        statements.append(f"TRUNCATE TABLE `{target_schema}`.`{target_table}`")
        statements.append(f"INSERT INTO `{target_schema}`.`{target_table}` {select}")
    elif write_disposition == "merge":
        # Lookup tables coexist with CIEL-baseline stock. INSERT IGNORE preserves
        # target's pre-existing rows and skips PK collisions.
        statements.append(f"INSERT IGNORE INTO `{target_schema}`.`{target_table}` {select}")
    else:  # append
        statements.append(f"INSERT INTO `{target_schema}`.`{target_table}` {select}")
    return statements, dropped


@dataclass
class LoadResult:
    target_table: str
    rows_loaded: int
    elapsed_seconds: float
    status: str                          # "ok" | "missing_in_source" | "error"
    error: str | None = None
    dropped_columns: list[str] | None = None  # dest cols absent from source (2.7→2.8 diff)


def load_one(
    target_schema: str,
    source_schema: str,
    source_table: str,
    target_table: str,
    write_disposition: str,
) -> LoadResult:
    """Load a single table from a SQLMesh snapshot (``source_schema.source_table``)
    into ``target_schema.target_table``."""
    t0 = time.time()
    conn = _connect(target_schema)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema=%s AND table_name=%s
            """, (source_schema, source_table))
            if cur.fetchone() is None:
                return LoadResult(target_table, 0, time.time() - t0,
                                  "missing_in_source",
                                  f"{source_schema}.{source_table} does not exist")

        dest_cols = _table_columns(conn, target_schema, target_table)
        if not [c for c in dest_cols if not c.startswith("_dlt_")]:
            return LoadResult(target_table, 0, time.time() - t0,
                              "error",
                              f"{target_schema}.{target_table} has no columns")

        src_cols = _table_columns(conn, source_schema, source_table)
        statements, dropped = _build_load_sql(
            source_schema, source_table, target_schema, target_table,
            write_disposition, dest_cols, src_cols,
        )
        if not statements:
            return LoadResult(target_table, 0, time.time() - t0,
                              "error",
                              f"no shared columns between {source_schema}.{source_table} "
                              f"and {target_schema}.{target_table}",
                              dropped_columns=dropped)

        rows = 0
        with conn.cursor() as cur:
            for sql in statements:
                cur.execute(sql)
                if sql.lstrip().upper().startswith("INSERT"):
                    rows = cur.rowcount
        conn.commit()
        return LoadResult(target_table, rows, time.time() - t0, "ok",
                          dropped_columns=dropped or None)
    except Exception as e:
        conn.rollback()
        return LoadResult(target_table, 0, time.time() - t0, "error", str(e))
    finally:
        conn.close()


def load_all(
    target_schema: str,
    resources: Iterable["LoadResource"],
    snapshots: dict[str, "ResolvedSnapshot"],
) -> dict[str, Any]:
    """Load every resource in FK-dependency order, reading each from its resolved
    SQLMesh snapshot table. Stop on first error.

    Returns a report stamped into the run manifest.
    """
    results: list[LoadResult] = []
    failures: list[str] = []
    for spec in resources:
        snap = snapshots.get(spec.sqlmesh_view)
        if snap is None:
            continue
        r = load_one(target_schema, snap.physical_schema, snap.physical_table,
                     spec.target_table, spec.write_disposition)
        results.append(r)
        if r.status not in {"ok", "missing_in_source"}:
            failures.append(f"{r.target_table}: {r.status} — {r.error}")
            break
    return {
        "source": "refapp_28_demo (SQLMesh snapshots)",
        "target_schema": target_schema,
        "results": [
            {
                "target_table": r.target_table,
                "rows_loaded": r.rows_loaded,
                "elapsed_seconds": round(r.elapsed_seconds, 3),
                "status": r.status,
                "error": r.error,
                "dropped_columns": r.dropped_columns,
            } for r in results
        ],
        "failures": failures,
        "ok": not failures,
    }


def repair_scaffolding_accounts(target_schema: str) -> dict[str, Any]:
    """FR-013 deterministic repair: drop RefApp scaffolding accounts whose
    backing person was replaced by the legacy corpus.

    The load replaces ``person`` with the legacy corpus (which carries its own
    ``admin``/``daemon``), so the RefApp's stock service accounts
    (clerk/nurse/technician) are left referencing persons that no longer exist.
    These are RefApp stock metadata, not source demo data, so the deterministic
    repair is to remove them and their account-layer children. Idempotent.
    """
    statements = [
        ("user_role",
         "DELETE ur FROM user_role ur JOIN users u ON u.user_id=ur.user_id "
         "LEFT JOIN person p ON p.person_id=u.person_id "
         "WHERE u.person_id IS NOT NULL AND p.person_id IS NULL"),
        ("user_property",
         "DELETE up FROM user_property up JOIN users u ON u.user_id=up.user_id "
         "LEFT JOIN person p ON p.person_id=u.person_id "
         "WHERE u.person_id IS NOT NULL AND p.person_id IS NULL"),
        ("users",
         "DELETE u FROM users u LEFT JOIN person p ON p.person_id=u.person_id "
         "WHERE u.person_id IS NOT NULL AND p.person_id IS NULL"),
        ("provider_attribute",
         "DELETE pa FROM provider_attribute pa JOIN provider pr ON pr.provider_id=pa.provider_id "
         "LEFT JOIN person p ON p.person_id=pr.person_id "
         "WHERE pr.person_id IS NOT NULL AND p.person_id IS NULL"),
        ("provider",
         "DELETE pr FROM provider pr LEFT JOIN person p ON p.person_id=pr.person_id "
         "WHERE pr.person_id IS NOT NULL AND p.person_id IS NULL"),
    ]
    conn = _connect(target_schema)
    deleted: dict[str, int] = {}
    try:
        with conn.cursor() as cur:
            for name, sql in statements:
                cur.execute(sql)
                deleted[name] = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return {"deleted": deleted, "total": sum(deleted.values())}


__all__ = ["LoadResult", "_build_load_sql", "load_one", "load_all",
           "repair_scaffolding_accounts"]
