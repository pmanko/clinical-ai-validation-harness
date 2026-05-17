"""Unit + DB-backed tests for ``harness/load/snapshot_resolver.py``."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from harness.load.snapshot_resolver import (
    ResolvedSnapshot,
    _parse_view_definition,
    resolve_snapshots,
)
from harness.profile.db import DBConfig, DBError, query_scalar


# ---------- pure unit ----------


def test_parse_view_definition_extracts_backticked_snapshot():
    view = (
        "select `sqlmesh__refapp_28_demo`.`refapp_28_demo__clin__obs__3649557428`."
        "`obs_id` AS `obs_id` from `sqlmesh__refapp_28_demo`."
        "`refapp_28_demo__clin__obs__3649557428`"
    )
    assert _parse_view_definition(view) == (
        "sqlmesh__refapp_28_demo",
        "refapp_28_demo__clin__obs__3649557428",
    )


def test_parse_view_definition_returns_none_on_no_sqlmesh_reference():
    assert _parse_view_definition("SELECT 1") is None
    assert _parse_view_definition("SELECT * FROM other_schema.tbl") is None


# ---------- DB-backed ----------


def _refapp_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return query_scalar(
            DBConfig.from_env(database="refapp_28_demo"),
            "SELECT 1", timeout=5,
        ) == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.mark.skipif(not _refapp_db_available(),
                    reason="refapp_28_demo not reachable")
def test_resolve_snapshots_finds_clinical_marts():
    cfg = DBConfig.from_env(database="refapp_28_demo")
    m = resolve_snapshots(cfg)
    for view in ("clin__obs", "clin__drug_order", "clin__test_order",
                 "clin__conditions", "clin__allergy", "clin__orders",
                 "stg_patient", "stg_person"):
        assert view in m, f"missing resolved snapshot for {view!r}"
        snap = m[view]
        assert snap.physical_schema == "sqlmesh__refapp_28_demo"
        assert snap.physical_table.startswith("refapp_28_demo__")
