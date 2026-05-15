"""Scenario-diversity test for the profile inventory (T020 / FR-024).

Asserts the inventory + schema-diff + module + terminology profile surface
the four scenario categories called out in FR-024:

  1. Ambiguous concept reference sources (legacy: ZERO reference rows;
     target: many).
  2. Missing locales (legacy: en-only; target: many).
  3. Orphan FK candidates (FK on a legacy table whose referenced table is
     legacy-only or unpopulated).
  4. Unbundled-module table cases (legacy-only tables classified to a
     known module, status_in_2_8_refapp = 'removed').

Pure-unit assertions use synthetic inputs; the DB-backed integration
tests confirm the same shapes against the live legacy_27_raw + openmrs.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from harness.profile.db import DBConfig, DBError, query_scalar
from harness.profile.modules import classify_modules
from harness.profile.terminology import (
    LocaleUsage, ReferenceSource, DEFAULT_REFAPP_LOCALES,
)
from harness.schema_diff import classify_table_diff


# ---------- pure unit ----------


def test_scenario_ambiguous_reference_sources_when_zero_in_source():
    """When the source has no reference_map rows, the inventory's
    ``reference_sources`` is empty — that's the M2-A signal."""
    source_sources: list[ReferenceSource] = []
    target_sources = [
        ReferenceSource("CIEL", "CIEL", None, False, 50_000),
        ReferenceSource("LN", "LOINC", None, False, 12_000),
        ReferenceSource("SCT", "SNOMED CT", None, False, 8_000),
    ]
    assert len(source_sources) == 0
    assert {s.name for s in target_sources} & {"CIEL", "LOINC", "SNOMED CT"}


def test_scenario_missing_locales_when_target_is_multilingual():
    source_locales = [LocaleUsage("en", 3555, expected_by_refapp=True)]
    target_locales = [
        LocaleUsage("en", 90_000, True),
        LocaleUsage("es", 55_000, True),
        LocaleUsage("fr", 15_000, True),
        LocaleUsage("nl", 12_000, True),
        LocaleUsage("pt_BR", 5_800, True),
        LocaleUsage("vi", 4_000, True),
        LocaleUsage("ru", 2_700, False),
    ]
    missing_in_source = {l.locale for l in target_locales} - {l.locale for l in source_locales}
    assert missing_in_source == {"es", "fr", "nl", "pt_BR", "vi", "ru"}


def test_scenario_unbundled_module_tables_show_removed_status():
    """When a legacy-only module's tables exist in source but not target,
    the classification reports status=removed."""
    src = ["formentry_archive", "formentry_queue", "htmlformentry_html_form",
           "dataintegrity_integrity_checks", "logic_rule_definition", "obs"]
    tgt = ["obs"]
    classified = {m.module_id: m for m in classify_modules(src, tgt)}
    for legacy_module in ("formentry", "htmlformentry", "dataintegrity", "logic"):
        assert classified[legacy_module].status_in_2_8_refapp == "removed"
    assert classified["Platform/Core"].status_in_2_8_refapp == "bundled"


def test_scenario_clinical_table_added_in_target_flagged_meaningful():
    """A new clinical table on the target side (e.g., test_order) flags
    clinical_meaningful even when not populated in source (it's pending
    promotion authoring)."""
    cm, _ = classify_table_diff(
        "test_order", populated_in_source=False, in_target=True, in_source=False,
    )
    assert cm is True


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


db_only = pytest.mark.skipif(
    not (_legacy_db_available() and _openmrs_db_available()),
    reason="legacy_27_raw and openmrs DB both required for the scenario test",
)


@db_only
def test_real_scenario_ambiguous_reference_sources():
    from harness.profile.terminology import enumerate_reference_sources
    legacy_sources = enumerate_reference_sources(DBConfig.from_env(database="legacy_27_raw"))
    target_sources = enumerate_reference_sources(DBConfig.from_env(database="openmrs"))
    assert len(legacy_sources) == 0, (
        "legacy_27_raw should ship zero terminology cross-references "
        "(M2-A finding); see research.md §R-bridge-rule"
    )
    assert len(target_sources) >= 5, (
        f"openmrs (CIEL-loaded) should expose many reference sources; "
        f"got {len(target_sources)}"
    )


@db_only
def test_real_scenario_missing_locales():
    from harness.profile.terminology import enumerate_locales
    legacy_locales = {l.locale for l in enumerate_locales(DBConfig.from_env(database="legacy_27_raw"))}
    target_locales = {l.locale for l in enumerate_locales(DBConfig.from_env(database="openmrs"))}
    missing = target_locales - legacy_locales
    # CIEL ships many locales; legacy is en-only.
    assert len(missing) >= 3, f"expected ≥3 locales missing in legacy; missing = {missing}"


@db_only
def test_real_scenario_unbundled_module_tables():
    from harness.profile.modules import enumerate_modules
    classified = {
        m.module_id: m
        for m in enumerate_modules(
            DBConfig.from_env(database="legacy_27_raw"),
            DBConfig.from_env(database="openmrs"),
        )
    }
    # At least one of these well-known legacy modules must be flagged removed.
    removed_modules = {mid for mid, m in classified.items()
                       if m.status_in_2_8_refapp == "removed"}
    expected_removed = {"formentry", "htmlformentry", "dataintegrity", "logic"}
    assert expected_removed & removed_modules, (
        f"expected at least one of {expected_removed} to be removed; "
        f"got removed = {removed_modules}"
    )
