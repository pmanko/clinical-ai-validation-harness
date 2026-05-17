"""Validates the schema_diff JSON output against ``contracts/schema_diff.schema.yaml``.

The contract is YAML-described (not strict JSON Schema), so the test
walks the contract spec and asserts each rule. DB-backed integration
test at the bottom is guarded by ``legacy_27_raw`` availability.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from harness.profile.db import DBConfig, DBError, query_scalar
from harness.schema_diff import (
    ColumnInfo,
    ForeignKey,
    IndexInfo,
    TableSchema,
    diff_schemas,
    diff_shared_table,
    diff_table_inventories,
    write_schema_diff_real,
)


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs" / "002-openmrs-demo-data-2-8-remap" / "contracts" / "schema_diff.schema.yaml"
)


@pytest.fixture(scope="module")
def contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text())


# ---------- contract shape validation ----------


def _validate_diff_against_contract(diff: dict, contract: dict) -> None:
    """Assert ``diff`` matches every rule the contract states.

    Mechanical translation of ``contracts/schema_diff.schema.yaml`` —
    top_level_required, items[].required, items[].properties.allowed,
    required_when.
    """
    # 1. Top-level required keys.
    for key in contract["top_level_required"]:
        assert key in diff, f"top-level key {key!r} missing"

    # 2. items[] each have the required properties.
    item_spec = contract["fields"]["items"]["items"]
    required_item_fields = set(item_spec["required"])
    allowed_categories = set(item_spec["properties"]["category"]["allowed"])

    for item in diff["items"]:
        # required fields
        for f in required_item_fields:
            assert f in item, f"item {item.get('id', item)} missing required {f!r}"
        # category enum
        assert item["category"] in allowed_categories, (
            f"item {item['id']} has category {item['category']!r} not in contract enum"
        )
        # required_when: clinical_meaningful_rationale when clinical_meaningful==true
        if item["clinical_meaningful"]:
            rationale = item.get("clinical_meaningful_rationale")
            assert rationale, (
                f"item {item['id']} is clinically meaningful but has no rationale"
            )
            assert isinstance(rationale, str) and rationale.strip(), (
                f"item {item['id']} rationale is empty"
            )


def test_synthetic_diff_validates_against_contract(contract):
    """Build a diff from synthetic ``TableSchema`` inputs and validate it."""
    inv = diff_table_inventories(
        source={"obs", "ancient_legacy"},
        target={"obs", "new_2_8_thing"},
        source_populated={"obs", "ancient_legacy"},
    )
    cols = {
        "obs_id": ColumnInfo("obs_id", "int", "int(11)", False, "PRI"),
        "ancient": ColumnInfo("ancient", "varchar", "varchar(50)", True, ""),
    }
    src = TableSchema(name="obs", columns=cols,
                      indexes={"PRIMARY": IndexInfo("PRIMARY", ("obs_id",), False)},
                      foreign_keys=[ForeignKey("fk", "obs_id", "obs", "obs_id")])
    tgt = TableSchema(name="obs",
                      columns={"obs_id": cols["obs_id"],
                               "form_namespace_and_path": ColumnInfo(
                                   "form_namespace_and_path", "varchar",
                                   "varchar(255)", True, "")},
                      indexes={"PRIMARY": IndexInfo("PRIMARY", ("obs_id",), False)})
    shared = diff_shared_table("obs", src, tgt, populated_in_source=True)
    diff = {
        "schema_version": 1,
        "kind": "SchemaDiff",
        "source_schema_id": "legacy_27_raw",
        "target_schema_id": "openmrs",
        "generated_at": "2026-05-15T00:00:00Z",
        "items": inv + shared,
    }
    _validate_diff_against_contract(diff, contract)


def test_empty_items_diff_validates(contract):
    """A diff with zero items still satisfies the contract."""
    diff = {
        "schema_version": 1,
        "kind": "SchemaDiff",
        "source_schema_id": "legacy_27_raw",
        "target_schema_id": "openmrs",
        "generated_at": "2026-05-15T00:00:00Z",
        "items": [],
    }
    _validate_diff_against_contract(diff, contract)


# ---------- DB-backed integration ----------


def _legacy_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        cfg = DBConfig.from_env(database="legacy_27_raw")
        return query_scalar(cfg, "SELECT 1", timeout=5) == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _target_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        cfg = DBConfig.from_env(database="openmrs")
        return query_scalar(cfg, "SELECT 1", timeout=5) == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


db_only = pytest.mark.skipif(
    not (_legacy_db_available() and _target_db_available()),
    reason="legacy_27_raw or openmrs DB not reachable; bring stack up first",
)


@db_only
def test_real_diff_validates_against_contract(tmp_path: Path, contract):
    diff_path, summary_path = write_schema_diff_real(
        tmp_path,
        DBConfig.from_env(database="legacy_27_raw"),
        DBConfig.from_env(database="openmrs"),
    )
    diff = json.loads(diff_path.read_text())
    _validate_diff_against_contract(diff, contract)
    assert summary_path.is_file()
    # Sanity: nontrivial output against the live DBs.
    assert len(diff["items"]) > 0


@db_only
def test_real_diff_finds_known_legacy_only_tables():
    """Smoke against the measured 22 legacy-only tables."""
    diff = diff_schemas(
        DBConfig.from_env(database="legacy_27_raw"),
        DBConfig.from_env(database="openmrs"),
    )
    legacy_only = [
        it["details"]["table"] for it in diff["items"]
        if it["category"] == "table_only_in_source"
    ]
    # A handful of the well-known module tables.
    for known in ("concept_word", "formentry_archive", "htmlformentry_html_form"):
        assert known in legacy_only, f"expected {known!r} in legacy-only tables; got {legacy_only}"


@db_only
def test_real_diff_marks_clinical_tables_as_meaningful():
    """obs is in §R5 and populated — any obs-touching diff must be meaningful."""
    diff = diff_schemas(
        DBConfig.from_env(database="legacy_27_raw"),
        DBConfig.from_env(database="openmrs"),
    )
    obs_items = [it for it in diff["items"] if "obs:" in it["id"] or it.get("details", {}).get("table") == "obs"]
    if obs_items:
        # At least one of them must be flagged clinical_meaningful.
        assert any(it["clinical_meaningful"] for it in obs_items)
