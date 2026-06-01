"""Promote step: copy clean rows from dlt's staging schema to the OpenMRS target.

Per ``contracts/dlt_pipeline.profile.md`` §two-schema architecture, dlt
writes to ``<target>_dlt.<table>`` with mandatory ``_dlt_load_id`` and
``_dlt_id`` columns. The OpenMRS target schema (Hibernate-defined)
cannot tolerate these column additions, so we lift data from staging
to target using only the OpenMRS-defined column set.

For each resource in the load manifest:

  1. Read the destination's column list from ``information_schema.columns``.
  2. Filter out any ``_dlt_*`` columns (none should be in the target, but
     defense in depth).
  3. TRUNCATE the destination table (mirroring dlt's ``replace`` semantics).
  4. INSERT INTO target.<table> (cols) SELECT cols FROM staging.<table>.

Errors surface clearly per-resource (target column missing in staging,
type mismatch, etc.) so iteration can fix the SQLMesh model.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

import pymysql

if TYPE_CHECKING:
    from harness.load.pipeline import LoadResource
    from harness.load.snapshot_resolver import ResolvedSnapshot


import os


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


def _destination_columns(conn, schema: str, table: str) -> list[str]:
    """Column list of the OpenMRS-defined target table (NOT the dlt-staged copy)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            ORDER BY ordinal_position
        """, (schema, table))
        return [r[0] for r in cur.fetchall()]


def _staging_columns(conn, schema: str, table: str) -> set[str]:
    """Column set of the dlt-staged copy. Used to verify destination cols are present."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
        """, (schema, table))
        return {r[0] for r in cur.fetchall()}


@dataclass
class PromoteResult:
    target_table: str
    rows_promoted: int
    elapsed_seconds: float
    status: str                          # "ok" | "missing_in_staging" | "error"
    error: str | None = None
    dropped_columns: list[str] | None = None  # dest cols absent from staging (2.7→2.8 diff)


def promote_one(
    target_schema: str,
    staging_schema: str,
    target_table: str,
    write_disposition: str,
) -> PromoteResult:
    """Promote a single table from staging → target."""
    t0 = time.time()
    target_conn = _connect(target_schema)
    try:
        with target_conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema=%s AND table_name=%s
            """, (staging_schema, target_table))
            if cur.fetchone() is None:
                return PromoteResult(target_table, 0, time.time() - t0,
                                     "missing_in_staging",
                                     f"{staging_schema}.{target_table} does not exist")

        dest_cols = _destination_columns(target_conn, target_schema, target_table)
        dest_cols = [c for c in dest_cols if not c.startswith("_dlt_")]
        if not dest_cols:
            return PromoteResult(target_table, 0, time.time() - t0,
                                 "error",
                                 f"{target_schema}.{target_table} has no columns")

        # Intersect destination cols with staging cols. Columns added in 2.8
        # but absent in 2.7 staging (e.g. provider.provider_role_id) are
        # left to MySQL's default — surface them in the report.
        stg_cols = _staging_columns(target_conn, staging_schema, target_table)
        common_cols = [c for c in dest_cols if c in stg_cols]
        dropped = [c for c in dest_cols if c not in stg_cols]
        if not common_cols:
            return PromoteResult(target_table, 0, time.time() - t0,
                                 "error",
                                 f"no shared columns between {staging_schema}.{target_table} and {target_schema}.{target_table}",
                                 dropped_columns=dropped)

        col_list = ", ".join(f"`{c}`" for c in common_cols)

        with target_conn.cursor() as cur:
            if write_disposition == "replace":
                cur.execute(f"TRUNCATE TABLE `{target_schema}`.`{target_table}`")
                sql = (
                    f"INSERT INTO `{target_schema}`.`{target_table}` ({col_list}) "
                    f"SELECT {col_list} FROM `{staging_schema}`.`{target_table}`"
                )
            elif write_disposition == "merge":
                # Lookup tables coexist with CIEL-baseline stock. Preserve
                # target's pre-existing rows; add any new ones from staging.
                # INSERT IGNORE skips PK collisions — same semantics as the
                # "legacy verbatim, openmrs stock kept" decision in 5C.
                sql = (
                    f"INSERT IGNORE INTO `{target_schema}`.`{target_table}` ({col_list}) "
                    f"SELECT {col_list} FROM `{staging_schema}`.`{target_table}`"
                )
            elif write_disposition == "append":
                sql = (
                    f"INSERT INTO `{target_schema}`.`{target_table}` ({col_list}) "
                    f"SELECT {col_list} FROM `{staging_schema}`.`{target_table}`"
                )
            else:
                raise ValueError(f"unknown write_disposition {write_disposition!r}")
            cur.execute(sql)
            rows = cur.rowcount

        target_conn.commit()
        return PromoteResult(target_table, rows, time.time() - t0, "ok",
                             dropped_columns=dropped or None)
    except Exception as e:
        target_conn.rollback()
        return PromoteResult(target_table, 0, time.time() - t0, "error", str(e))
    finally:
        target_conn.close()


def promote_all(
    staging_schema: str,
    target_schema: str,
    resources: Iterable["LoadResource"],
    snapshots: dict[str, "ResolvedSnapshot"],
) -> dict[str, Any]:
    """Run promote for every resource in load order. Stop on first error.

    Returns a report stamped into the run manifest (per
    ``contracts/dlt_pipeline.profile.md``).
    """
    results: list[PromoteResult] = []
    failures: list[str] = []
    for spec in resources:
        if spec.sqlmesh_view not in snapshots:
            continue
        r = promote_one(target_schema, staging_schema, spec.target_table,
                        spec.write_disposition)
        results.append(r)
        if r.status not in {"ok", "missing_in_staging"}:
            failures.append(f"{r.target_table}: {r.status} — {r.error}")
            break
    return {
        "staging_schema": staging_schema,
        "target_schema": target_schema,
        "results": [
            {
                "target_table": r.target_table,
                "rows_promoted": r.rows_promoted,
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


__all__ = ["PromoteResult", "promote_one", "promote_all", "repair_scaffolding_accounts"]
