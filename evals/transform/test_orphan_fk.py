"""Pure-unit + DB-backed tests for ``harness/transform/orphan_fk.py`` (FR-013 / T057)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from harness.transform.orphan_fk import ForeignKey, _list_fks, detect_orphans
from harness.profile.db import DBConfig, DBError, query_scalar


# ---------- pure unit ----------


def test_foreign_key_dataclass_is_frozen():
    fk = ForeignKey("c1", "child", "child_col", "parent", "parent_col")
    assert fk.child_table == "child"
    with pytest.raises(Exception):
        fk.child_table = "other"  # frozen


# ---------- DB-backed ----------


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


db_only = pytest.mark.skipif(not _openmrs_test_available(),
                              reason="openmrs_test not reachable")


@db_only
def test_list_fks_returns_many_constraints():
    """openmrs_test should declare hundreds of FK constraints (OpenMRS schema)."""
    cfg = DBConfig.from_env(database="openmrs_test")
    fks = _list_fks(cfg)
    assert len(fks) > 100
    # Spot-check: patient.changed_by → users.user_id exists
    matches = [
        fk for fk in fks
        if fk.child_table == "patient" and fk.child_column == "changed_by"
        and fk.parent_table == "users" and fk.parent_column == "user_id"
    ]
    assert matches, "patient.changed_by FK to users not found"


@db_only
def test_detect_orphans_returns_report_shape():
    """Run a sample-only check; verify the report structure even if orphans exist."""
    report = detect_orphans(target_schema="openmrs_test", sample_n=2, progress=False)
    assert report["kind"] == "OrphanFKReport"
    assert report["target_schema"] == "openmrs_test"
    assert "fks_checked" in report
    assert "fks_with_orphans" in report
    assert "total_orphan_rows" in report
    assert isinstance(report["orphans"], list)
    for o in report["orphans"]:
        assert {"constraint_name", "child_table", "child_column",
                "parent_table", "parent_column", "orphan_count",
                "sample_offenders"}.issubset(o.keys())
        assert o["orphan_count"] > 0
