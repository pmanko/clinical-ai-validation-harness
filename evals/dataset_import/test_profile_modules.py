"""Tests for module classification."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from harness.profile.db import DBConfig, DBError, query_scalar
from harness.profile.modules import (
    MODULE_PREFIXES,
    PLATFORM_CORE_TABLES,
    ModuleClassification,
    classify_modules,
    classify_table,
)


# ---------- classify_table ----------


@pytest.mark.parametrize("table,expected", [
    # Prefix-based module attribution.
    ("htmlformentry_html_form",         "htmlformentry"),
    ("formentry_archive",               "formentry"),
    ("formentry_queue",                 "formentry"),
    ("hl7_source",                      "hl7"),
    ("dataintegrity_integrity_checks",  "dataintegrity"),
    ("openconceptlab_import",           "openconceptlab"),
    ("openconceptlab_subscription",     "openconceptlab"),
    ("logic_rule_definition",           "logic"),
    # Well-known Platform/Core tables.
    ("obs",                             "Platform/Core"),
    ("patient",                         "Platform/Core"),
    ("encounter",                       "Platform/Core"),
    ("concept",                         "Platform/Core"),
    ("liquibasechangelog",              "Platform/Core"),
    # Unknown tables.
    ("some_random_table_3000",          "unknown"),
])
def test_classify_table(table, expected):
    assert classify_table(table) == expected


def test_classify_table_longer_prefix_wins():
    """If a table name starts with a known prefix, the prefix-match takes
    precedence over the bare-table fallback."""
    # Make sure prefixes are checked before the Platform/Core set even
    # when the suffix portion happens to be in core.
    assert classify_table("openconceptlab_import").startswith("openconceptlab") or (
        classify_table("openconceptlab_import") == "openconceptlab"
    )


# ---------- classify_modules ----------


def test_empty_inputs_yield_empty_output():
    assert classify_modules([], []) == []


def test_status_bundled_when_module_tables_in_both_schemas():
    src = ["obs", "patient", "concept"]
    tgt = ["obs", "patient", "concept"]
    out = classify_modules(src, tgt)
    assert len(out) == 1
    assert out[0].module_id == "Platform/Core"
    assert out[0].status_in_2_8_refapp == "bundled"
    assert out[0].contributed_tables == ["concept", "obs", "patient"]


def test_status_removed_when_module_tables_only_in_source():
    src = ["formentry_archive", "formentry_queue"]
    tgt: list[str] = []
    out = classify_modules(src, tgt)
    assert len(out) == 1
    assert out[0].module_id == "formentry"
    assert out[0].status_in_2_8_refapp == "removed"


def test_status_optional_when_module_tables_only_in_target():
    """A module added in the target (e.g., addresshierarchy bundled by O3)
    but absent from source is ``optional`` from the source's perspective."""
    src: list[str] = []
    tgt = ["addresshierarchy_address_hierarchy_entry"]
    out = classify_modules(src, tgt)
    assert len(out) == 1
    assert out[0].module_id == "addresshierarchy"
    assert out[0].status_in_2_8_refapp == "optional"


def test_mixed_modules_each_get_their_own_classification():
    src = ["obs", "formentry_archive", "openconceptlab_import"]
    tgt = ["obs", "openconceptlab_import", "addresshierarchy_address"]
    out = {m.module_id: m for m in classify_modules(src, tgt)}
    assert out["Platform/Core"].status_in_2_8_refapp == "bundled"
    assert out["formentry"].status_in_2_8_refapp == "removed"
    assert out["openconceptlab"].status_in_2_8_refapp == "bundled"
    assert out["addresshierarchy"].status_in_2_8_refapp == "optional"


def test_classification_is_deterministic_and_sorted_by_module_id():
    out = classify_modules(["obs", "hl7_source", "formentry_archive"],
                           ["obs", "hl7_source"])
    module_ids = [m.module_id for m in out]
    assert module_ids == sorted(module_ids)


def test_to_dict_shape_matches_inventory_contract():
    """The output of ``ModuleClassification.to_dict()`` must satisfy the
    inventory schema's ``modules[]`` shape."""
    src = ["obs", "formentry_archive"]
    tgt = ["obs"]
    for m in classify_modules(src, tgt):
        d = m.to_dict()
        assert set(d.keys()) >= {"module_id", "contributed_tables", "status_in_2_8_refapp"}
        assert isinstance(d["contributed_tables"], list)
        assert d["status_in_2_8_refapp"] in {"bundled", "optional", "removed", "unknown"}


def test_module_prefixes_constant_is_nonempty_and_ordered():
    assert len(MODULE_PREFIXES) >= 5
    # Each entry is (prefix, module_id) and prefix ends in '_'.
    for prefix, module_id in MODULE_PREFIXES:
        assert prefix.endswith("_"), f"prefix {prefix!r} must end with '_'"
        assert module_id, f"module_id for {prefix!r} is empty"


def test_platform_core_tables_constant_has_clinical_set():
    """The §R5 clinical-reference tables should all be in PLATFORM_CORE."""
    from harness.schema_diff import CLINICAL_TABLES
    missing = CLINICAL_TABLES - PLATFORM_CORE_TABLES
    assert not missing, f"clinical tables missing from PLATFORM_CORE_TABLES: {missing}"


# ---------- DB-backed integration ----------


def _legacy_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return query_scalar(DBConfig.from_env(database="legacy_27_raw"),
                            "SELECT 1", timeout=5) == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _openmrs_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return query_scalar(DBConfig.from_env(database="openmrs"),
                            "SELECT 1", timeout=5) == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.mark.skipif(
    not (_legacy_db_available() and _openmrs_db_available()),
    reason="legacy_27_raw or openmrs DB not reachable",
)
def test_real_classification_finds_known_legacy_only_modules():
    """formentry / htmlformentry / dataintegrity / logic tables exist on
    legacy but not on the modern RefApp."""
    from harness.profile.modules import enumerate_modules
    result = enumerate_modules(
        DBConfig.from_env(database="legacy_27_raw"),
        DBConfig.from_env(database="openmrs"),
    )
    by_id = {m.module_id: m for m in result}
    for legacy_module in ("formentry", "htmlformentry", "dataintegrity", "logic"):
        if legacy_module in by_id:
            assert by_id[legacy_module].status_in_2_8_refapp == "removed", (
                f"{legacy_module} expected to be removed in modern RefApp; "
                f"got {by_id[legacy_module].status_in_2_8_refapp!r}"
            )
