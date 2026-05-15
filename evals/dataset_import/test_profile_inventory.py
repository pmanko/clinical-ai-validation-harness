"""Tests for harness.profile.inventory (T020/T021).

Covers the inventory generator end-to-end against the live `legacy_27_raw`
database. Skips if the DB isn't reachable (CI without Docker, etc.) so the
suite still runs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from harness.profile import inventory
from harness.profile.db import DBConfig, DBError, query_scalar
from harness.profile.inventory import (
    PKRange,
    PopulatedColumn,
    _table_to_dict,
    foreign_keys_out,
    generate_inventory,
    list_columns,
    list_tables,
    populated_column_stats,
    primary_key_columns,
    row_count,
    sha256_file,
    summarize_table,
)


def _legacy_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        cfg = DBConfig.from_env()
        val = query_scalar(cfg, "SELECT 1", timeout=5)
        return val == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


pytestmark = pytest.mark.skipif(
    not _legacy_db_available(),
    reason="legacy_27_raw DB not reachable; run `make up && ./scripts/load-demo-data.sh` first",
)


@pytest.fixture(scope="module")
def cfg() -> DBConfig:
    return DBConfig.from_env()


# ---- identifier safety --------------------------------------------------


def test_ident_rejects_backtick():
    with pytest.raises(ValueError):
        inventory._ident("nasty`name")


def test_ident_rejects_nul():
    with pytest.raises(ValueError):
        inventory._ident("nasty\x00name")


def test_ident_wraps_plain():
    assert inventory._ident("patient") == "`patient`"


# ---- T020 scenarios: ground-truth signals from the live legacy_27_raw ---


def test_list_tables_returns_full_set(cfg):
    tables = list_tables(cfg)
    assert len(tables) == 143, "2.7 dump ships 143 base tables"
    assert "patient" in tables
    assert "obs" in tables
    assert "allergy" in tables  # empty, but its DDL is present


def test_known_row_counts(cfg):
    # These are the documented signals the user/agent has been steering by.
    assert row_count(cfg, "patient") == 5284
    assert row_count(cfg, "obs") == 476973
    # Clinical-promotion targets are all empty in the 2.7 dump.
    assert row_count(cfg, "allergy") == 0
    assert row_count(cfg, "conditions") == 0
    assert row_count(cfg, "orders") == 0
    assert row_count(cfg, "drug_order") == 0


def test_patient_pk_range_is_integer(cfg):
    pks = primary_key_columns(cfg, "patient")
    assert pks == ["patient_id"]
    rng = inventory.pk_range(cfg, "patient", pks)
    assert isinstance(rng, PKRange)
    assert rng.min >= 1 and rng.max >= rng.min


def test_patient_fks_include_person(cfg):
    fks = foreign_keys_out(cfg, "patient")
    refs = {fk.references for fk in fks}
    assert "person.person_id" in refs


def test_populated_columns_skips_all_null(cfg):
    """patient.voided_by is NULL for all rows where voided=false; should not appear in populated_columns."""
    cols = [c for c, _ in list_columns(cfg, "patient")]
    stats = populated_column_stats(cfg, "patient", cols)
    names = {s.name for s in stats}
    assert "patient_id" in names  # PK is always populated
    # `voided_by` is only populated for voided rows; in this dump it's all-null.
    voided_by = next((s for s in stats if s.name == "voided_by"), None)
    if voided_by is not None:
        # If present, it means some rows are voided — in that case non_null > 0.
        assert voided_by.non_null_count > 0


def test_summarize_empty_table(cfg):
    s = summarize_table(cfg, "allergy")
    assert s.row_count == 0
    assert s.populated_columns == []
    assert s.pk_range is None
    # FK metadata exists even for empty tables.
    assert any(fk.references == "patient.patient_id" for fk in s.foreign_keys_out)


# ---- end-to-end orchestration -------------------------------------------


def test_generate_inventory_full_shape(cfg, tmp_path):
    src = tmp_path / "fake-dump.sql"
    src.write_text("-- fake\n")
    inv = generate_inventory(cfg, source_dump_path=src)

    # Required top-level keys per contracts/profile_inventory.schema.yaml
    for key in (
        "schema_version", "kind", "source_dump_path", "source_dump_checksum",
        "generated_at", "tables", "reference_sources", "locales", "modules",
    ):
        assert key in inv, f"missing top-level key: {key}"

    assert inv["kind"] == "ProfileInventory"
    assert inv["source_dump_checksum"] == sha256_file(src)
    assert len(inv["tables"]) == 143

    # Every table entry has the contract-required fields.
    for t in inv["tables"]:
        assert "name" in t and "row_count" in t and "populated_columns" in t
        # foreign_keys_out is always emitted; pk_range is optional.

    # T022/T023 fillers are present as empty arrays.
    assert inv["reference_sources"] == []
    assert inv["locales"] == []
    assert inv["modules"] == []


def test_inventory_json_serializable(cfg, tmp_path):
    src = tmp_path / "fake.sql"
    src.write_text("x")
    inv = generate_inventory(cfg, source_dump_path=src)
    # If anything isn't JSON-safe (e.g. dataclass instance leaks), this raises.
    s = json.dumps(inv)
    assert len(s) > 0


# ---- pure unit (no DB) --------------------------------------------------


def test_table_to_dict_includes_pk_range_only_when_set():
    from harness.profile.inventory import TableSummary

    empty = TableSummary(name="x", row_count=0)
    d = _table_to_dict(empty)
    assert "pk_range" not in d
    assert d == {"name": "x", "row_count": 0, "populated_columns": [], "foreign_keys_out": []}

    with_pk = TableSummary(
        name="y", row_count=1,
        populated_columns=[PopulatedColumn(name="id", non_null_count=1, distinct_count=1)],
        pk_range=PKRange(min=1, max=1),
    )
    d2 = _table_to_dict(with_pk)
    assert d2["pk_range"] == {"min": 1, "max": 1}
