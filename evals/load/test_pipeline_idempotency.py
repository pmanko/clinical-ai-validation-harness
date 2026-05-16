"""Idempotency: re-running the loader without input changes produces stable
row counts (and ~stable content) in openmrs_test.

Per /speckit-analyze H3. Per research.md §R-load-pattern, the dlt
``write_disposition='replace'`` semantics guarantee that re-running on
identical staging input yields identical row counts. Content is also
identical except for ``UUID()`` calls in the SQLMesh promotion models
(research.md §R-typed-table-promotion Q2 specifies UUID v5; not yet
implemented), so we assert row counts but not content checksums.

Marked ``@pytest.mark.slow`` — full reset + replay takes 8-15 min.
Excluded from default ``pytest evals/``; included in CI via ``-m slow``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness.profile.db import DBConfig, DBError, query_scalar


REPO_ROOT = Path(__file__).resolve().parents[2]


CLINICAL_TABLES_MIN_ROWS: dict[str, int] = {
    "patient":    5_000,
    "person":     5_000,
    "obs":      400_000,
    "encounter": 13_000,
    "drug_order": 40_000,
    "orders":     40_000,
    "conditions":  4_000,
    "test_order":  1_000,
}


def _openmrs_test_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return query_scalar(
            DBConfig.from_env(database="openmrs_test"),
            "SELECT 1", timeout=5,
        ) == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _row_count(table: str) -> int:
    val = query_scalar(
        DBConfig.from_env(database="openmrs_test"),
        f"SELECT COUNT(*) FROM `openmrs_test`.`{table}`",
        timeout=60,
    )
    return int(val or 0)


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not _openmrs_test_available(),
                       reason="openmrs_test schema not present; "
                              "run `make loadtest-up && python -m harness.load run`"),
]


def test_loaded_row_counts_match_audit_floors():
    """After Phase 5D.3, every clinical table has at least its audit floor."""
    failures: list[str] = []
    for table, floor in CLINICAL_TABLES_MIN_ROWS.items():
        actual = _row_count(table)
        if actual < floor:
            failures.append(f"  {table}: actual={actual:,} floor={floor:,}")
    assert not failures, "Loaded clinical tables below floors:\n" + "\n".join(failures)


def test_rerun_loader_produces_stable_row_counts():
    """Run the dlt+promote pipeline twice; assert row counts identical."""
    pre_counts = {t: _row_count(t) for t in CLINICAL_TABLES_MIN_ROWS}

    # Re-run: dlt pipeline picks up its prior state; replace-disposition
    # tables get TRUNCATE+INSERT cycle, merge tables get INSERT IGNORE (no-op).
    proc = subprocess.run(
        [sys.executable, "-m", "harness.load", "run",
         "--target", "openmrs_test"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=900,
    )
    assert proc.returncode == 0, (
        f"loader rerun failed:\nSTDOUT:\n{proc.stdout[-2000:]}\n"
        f"STDERR:\n{proc.stderr[-2000:]}"
    )

    post_counts = {t: _row_count(t) for t in CLINICAL_TABLES_MIN_ROWS}

    diffs = {
        t: (pre_counts[t], post_counts[t])
        for t in CLINICAL_TABLES_MIN_ROWS
        if pre_counts[t] != post_counts[t]
    }
    assert not diffs, (
        "Row counts changed on re-run (loader is not idempotent):\n"
        + "\n".join(f"  {t}: {a:,} → {b:,}" for t, (a, b) in diffs.items())
    )
