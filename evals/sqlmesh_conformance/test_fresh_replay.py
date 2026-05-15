"""Fresh-replay integration test — proves the SQLMesh transform rebuilds
from a destructively-reset state and produces the expected row counts.

Motivation: the existing deterministic-rerun design (T043) compares two
runs from the same state. It does NOT catch the failure mode that bit
us in the M2-A incident — orphaned snapshot tables decoupled from the
SQLMesh metadata schema, leaving views in ``refapp_28_demo.*`` that
point at empty snapshots. The only way to detect that is to drop the
state and re-materialize from scratch, then assert row counts.

This test is ``@pytest.mark.slow`` because a full plan + run takes
~8-10 minutes (stg_obs alone is ~8 minutes). Excluded from the default
``pytest evals/`` run; included in the CI matrix only.

Skip conditions:

  - ``sqlmesh`` CLI not available in the venv bin
  - MariaDB unreachable via ``harness.profile.db``
  - ``scripts/reset-transform.sh`` not present (the destructive recovery
    isn't codified yet)
  - Required upstream data not loaded (``legacy_27_raw`` empty,
    ``openmrs`` empty)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness.profile.db import DBConfig, DBError, query_scalar


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"
RESET_SCRIPT = PROJECT_ROOT / "scripts" / "reset-transform.sh"


# Expected min row counts (must match audits/audit_<mart>_row_count_min.sql).
EXPECTED_MIN_ROWS: dict[str, int] = {
    "clin__obs":         400_000,
    "clin__drug_order":   40_000,
    "clin__conditions":    4_000,
    "clin__allergy":           1,
    "clin__test_order":    1_000,
}


def _sqlmesh_bin_available() -> bool:
    return (Path(sys.executable).parent / "sqlmesh").is_file()


def _legacy_db_populated() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        val = query_scalar(
            DBConfig.from_env(database="legacy_27_raw"),
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='legacy_27_raw'",
            timeout=5,
        )
        return int(val or 0) > 100  # 143 tables expected; 100 is a safe floor
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _ciel_baseline_loaded() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        val = query_scalar(
            DBConfig.from_env(database="openmrs"),
            "SELECT COUNT(*) FROM openmrs.concept",
            timeout=5,
        )
        return int(val or 0) > 50_000  # CIEL has ~59k after import
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not _sqlmesh_bin_available(),
                       reason="sqlmesh CLI not in venv bin"),
    pytest.mark.skipif(not RESET_SCRIPT.is_file(),
                       reason="scripts/reset-transform.sh not present"),
    pytest.mark.skipif(not _legacy_db_populated(),
                       reason="legacy_27_raw not loaded (run scripts/load-demo-data.sh)"),
    pytest.mark.skipif(not _ciel_baseline_loaded(),
                       reason="openmrs CIEL baseline not loaded (run make ciel-baseline)"),
]


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess with the harness's MariaDB env baked in."""
    env = {
        **os.environ,
        "MARIADB_HOST": "127.0.0.1",
        "MARIADB_PORT": "3307",
        "MARIADB_USER": "openmrs",
        "MARIADB_PASSWORD": "openmrs",
    }
    return subprocess.run(cmd, env=env, capture_output=True, text=True,
                          check=False, **kwargs)


def _row_count(table: str) -> int:
    val = query_scalar(
        DBConfig.from_env(database="refapp_28_demo"),
        f"SELECT COUNT(*) FROM `refapp_28_demo`.`{table}`",
        timeout=30,
    )
    return int(val or 0)


def test_fresh_replay_produces_expected_row_counts():
    """Drop everything, re-plan from scratch, assert all clinical marts
    have at least the audit-floor row counts."""

    # Step 1: destructive reset (--force skips the interactive prompt).
    reset = _run([str(RESET_SCRIPT), "--force"])
    assert reset.returncode == 0, (
        f"reset-transform failed (exit {reset.returncode}):\n"
        f"STDOUT:\n{reset.stdout}\nSTDERR:\n{reset.stderr}"
    )

    # Step 2: re-plan from scratch. ~8-10 min wall-time.
    sqlmesh_bin = Path(sys.executable).parent / "sqlmesh"
    plan = _run(
        [str(sqlmesh_bin), "-p", str(SQLMESH_DIR), "plan", "prod",
         "--no-prompts", "--auto-apply"],
        timeout=900,  # 15 min ceiling
    )
    assert plan.returncode == 0, (
        f"sqlmesh plan failed (exit {plan.returncode}):\n"
        f"STDOUT (last 2KB):\n{plan.stdout[-2000:]}\n"
        f"STDERR (last 2KB):\n{plan.stderr[-2000:]}"
    )

    # Step 3: every clinical mart meets its audit floor.
    failures: list[str] = []
    for table, min_rows in EXPECTED_MIN_ROWS.items():
        actual = _row_count(table)
        if actual < min_rows:
            failures.append(
                f"  {table}: actual={actual:,}  required_min={min_rows:,}"
            )
    assert not failures, (
        "Fresh-replay produced clinical marts below their audit-floor row counts:\n"
        + "\n".join(failures)
    )
