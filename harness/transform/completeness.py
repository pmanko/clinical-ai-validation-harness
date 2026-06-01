"""Completeness gate: every non-empty legacy source table must be either loaded
(a ``LOAD_RESOURCES`` target) or explicitly excluded-with-reason.

This guards the failure mode that shipped the original broken dataset: a source
table silently absent from the load manifest (``person_address`` 5283 rows,
``person_attribute`` 5287, ``patient_state`` 8499 — all dropped, none of which
the orphan-FK audit could see because a dropped table orphans nothing).

Exit 0 if every non-empty source table is accounted for; exit 1 (and print the
offenders) otherwise.
"""
from __future__ import annotations

import argparse
import sys

from harness.profile.db import DBConfig, query
from harness.load.pipeline import (
    LOAD_RESOURCES,
    EXCLUDED_WITH_REASON,
    EXCLUDED_PREFIXES,
)


def find_uncovered(legacy_db: str = "legacy_27_raw") -> list[tuple[str, int]]:
    """Return [(table, row_count), ...] for non-empty source tables that are
    neither loaded nor excluded-with-reason."""
    cfg = DBConfig.from_env(database=legacy_db)
    targets = {r.target_table for r in LOAD_RESOURCES}
    tables = [row[0] for row in query(cfg, "SHOW TABLES") if row and row[0]]
    uncovered: list[tuple[str, int]] = []
    for t in tables:
        if t in targets or t in EXCLUDED_WITH_REASON or t.startswith(EXCLUDED_PREFIXES):
            continue
        # Constant-time non-empty probe (avoids a COUNT(*) full scan per table).
        # The COUNT only runs for the rare flagged table, to enrich the message.
        if query(cfg, f"SELECT 1 FROM `{t}` LIMIT 1"):
            cnt = query(cfg, f"SELECT COUNT(*) FROM `{t}`")
            n = int(cnt[0][0]) if cnt and cnt[0][0] is not None else 0
            uncovered.append((t, n))
    return uncovered


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.transform.completeness")
    p.add_argument("--legacy-db", default="legacy_27_raw")
    args = p.parse_args(argv)

    uncovered = find_uncovered(args.legacy_db)
    if uncovered:
        print("✗ Completeness FAIL — non-empty source tables neither loaded "
              "nor excluded-with-reason:")
        for t, n in sorted(uncovered, key=lambda x: -x[1]):
            print(f"    {t}: {n} rows")
        print("\n  Resolve each: add it to LOAD_RESOURCES (load the data) or to "
              "EXCLUDED_WITH_REASON in harness/load/pipeline.py (justify the exclusion).")
        return 1
    print("✓ Completeness OK — every non-empty source table is loaded or "
          "excluded-with-reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
