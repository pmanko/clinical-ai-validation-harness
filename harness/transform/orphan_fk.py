"""Detect orphan foreign keys in the loaded OpenMRS schema (FR-013 / T057).

After the dlt loader populates ``openmrs_test`` (Phase 5D), the FK
checks were bypassed with ``FOREIGN_KEY_CHECKS=0``. This module
provides the post-load audit that surfaces any orphan rows so they
can either be repaired or surfaced as known data-quality issues.

Per FR-013: "The system MUST detect and report orphaned foreign keys
created by mapping/dropping decisions before any database is offered
as importable, and MUST either repair them deterministically or fail
the run."

For each declared FK in ``information_schema.referential_constraints``:

  1. Find child rows whose parent doesn't exist:
     ``SELECT child.<pk> FROM child LEFT JOIN parent ON ...
      WHERE parent.<pk> IS NULL AND child.<fk> IS NOT NULL``
  2. Count + sample 5 offending rows.
  3. Emit a per-FK entry in the report.

Output: ``artifacts/<run>/transform/orphan-fk-report.json`` per
``contracts/coverage_sample.schema.yaml``-compatible shape.

Default behavior: exit non-zero if any orphans exist (FR-013 fail-closed).
Pass ``--allow-orphans`` for iteration-mode runs where you want to see
the report without halting.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from harness.profile.db import DBConfig, query


@dataclass(frozen=True)
class ForeignKey:
    constraint_name: str
    child_table: str
    child_column: str
    parent_table: str
    parent_column: str


@dataclass
class OrphanReport:
    fk: ForeignKey
    orphan_count: int
    sample_offenders: list[Any]
    elapsed_seconds: float


def _list_fks(cfg: DBConfig) -> list[ForeignKey]:
    """Enumerate FK constraints in the target schema."""
    rows = query(cfg, f"""
        SELECT
            rc.constraint_name,
            kcu.table_name           AS child_table,
            kcu.column_name          AS child_column,
            kcu.referenced_table_name AS parent_table,
            kcu.referenced_column_name AS parent_column
        FROM information_schema.referential_constraints rc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_schema = rc.constraint_schema
         AND kcu.constraint_name   = rc.constraint_name
        WHERE rc.constraint_schema = '{cfg.database}'
        ORDER BY child_table, child_column
    """)
    return [
        ForeignKey(*r) for r in rows if r and r[3] is not None
    ]


def _check_one_fk(cfg: DBConfig, fk: ForeignKey, sample_n: int = 5) -> OrphanReport:
    """Find orphans for a single FK."""
    t0 = time.time()
    # Count orphans
    sql = f"""
        SELECT COUNT(*)
        FROM `{cfg.database}`.`{fk.child_table}` c
        LEFT JOIN `{cfg.database}`.`{fk.parent_table}` p
          ON p.`{fk.parent_column}` = c.`{fk.child_column}`
        WHERE c.`{fk.child_column}` IS NOT NULL
          AND p.`{fk.parent_column}` IS NULL
    """
    rows = query(cfg, sql, timeout=120)
    count = int(rows[0][0]) if rows and rows[0] else 0

    samples: list[Any] = []
    if count > 0:
        # Get sample offenders. Different from the count query — surface
        # the actual orphan child rows (PK columns) for evidence.
        # Best-effort: query the child PK if discoverable.
        sample_sql = f"""
            SELECT c.`{fk.child_column}` AS child_fk_value
            FROM `{cfg.database}`.`{fk.child_table}` c
            LEFT JOIN `{cfg.database}`.`{fk.parent_table}` p
              ON p.`{fk.parent_column}` = c.`{fk.child_column}`
            WHERE c.`{fk.child_column}` IS NOT NULL
              AND p.`{fk.parent_column}` IS NULL
            LIMIT {sample_n}
        """
        sample_rows = query(cfg, sample_sql, timeout=60)
        samples = [r[0] for r in sample_rows]

    return OrphanReport(
        fk=fk,
        orphan_count=count,
        sample_offenders=samples,
        elapsed_seconds=round(time.time() - t0, 2),
    )


def detect_orphans(
    target_schema: str = "openmrs_test",
    sample_n: int = 5,
    progress: bool = True,
) -> dict[str, Any]:
    """Run the full FK orphan check. Returns the report dict (matches the
    shape written to ``artifacts/<run>/transform/orphan-fk-report.json``).
    """
    cfg = DBConfig.from_env(database=target_schema)
    fks = _list_fks(cfg)
    if progress:
        print(f"Checking {len(fks)} FK constraints in {target_schema} ...")

    reports: list[OrphanReport] = []
    total_orphans = 0
    for i, fk in enumerate(fks, 1):
        r = _check_one_fk(cfg, fk, sample_n=sample_n)
        reports.append(r)
        total_orphans += r.orphan_count
        if progress and (r.orphan_count > 0 or i % 50 == 0):
            print(f"  [{i:3d}/{len(fks)}] {fk.child_table}.{fk.child_column} → "
                  f"{fk.parent_table}.{fk.parent_column}: orphans={r.orphan_count} ({r.elapsed_seconds}s)")

    orphan_reports = [r for r in reports if r.orphan_count > 0]

    return {
        "schema_version": 1,
        "kind": "OrphanFKReport",
        "target_schema": target_schema,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fks_checked": len(fks),
        "fks_with_orphans": len(orphan_reports),
        "total_orphan_rows": total_orphans,
        "orphans": [
            {
                "constraint_name": r.fk.constraint_name,
                "child_table": r.fk.child_table,
                "child_column": r.fk.child_column,
                "parent_table": r.fk.parent_table,
                "parent_column": r.fk.parent_column,
                "orphan_count": r.orphan_count,
                "sample_offenders": r.sample_offenders,
            }
            for r in orphan_reports
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.transform.orphan_fk")
    p.add_argument("--target", default="openmrs_test",
                   help="Schema to check (default: openmrs_test).")
    p.add_argument("--out", default=None,
                   help="Where to write the JSON report. Default: artifacts/dev-<ts>/transform/orphan-fk-report.json")
    p.add_argument("--sample-n", type=int, default=5,
                   help="Sample offender count per FK.")
    p.add_argument("--allow-orphans", action="store_true",
                   help="Exit 0 even if orphans exist (iteration mode).")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    report = detect_orphans(
        target_schema=args.target,
        sample_n=args.sample_n,
        progress=not args.quiet,
    )

    if args.out:
        out_path = Path(args.out)
    else:
        run_id = f"dev-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}"
        out_path = Path("artifacts") / run_id / "transform" / "orphan-fk-report.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nReport: {out_path}")
    print(f"FK constraints checked: {report['fks_checked']}")
    print(f"FKs with orphans:       {report['fks_with_orphans']}")
    print(f"Total orphan rows:      {report['total_orphan_rows']}")

    if report["total_orphan_rows"] > 0:
        print(f"\n⚠ Orphan FKs detected. Top offenders:")
        for o in sorted(report["orphans"], key=lambda x: -x["orphan_count"])[:5]:
            print(f"  {o['child_table']}.{o['child_column']} → {o['parent_table']}.{o['parent_column']}: "
                  f"{o['orphan_count']} orphans (samples: {o['sample_offenders']})")
        if not args.allow_orphans:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
