"""Unit + DB-backed integration tests for the terminology profile."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from harness.profile.db import DBConfig, DBError, query_scalar
from harness.profile.terminology import (
    DEFAULT_REFAPP_LOCALES,
    LocaleUsage,
    ReferenceSource,
    _parse_allowed_locale_list,
    enumerate_locales,
    enumerate_reference_sources,
)


# ---------- pure unit ----------


@pytest.mark.parametrize("raw,expected", [
    (None,                                set()),
    ("",                                  set()),
    ("en",                                {"en"}),
    ("en, es, fr",                        {"en", "es", "fr"}),
    ("en,es,fr,it,pt",                    {"en", "es", "fr", "it", "pt"}),
    (" en ,  es  ,fr ,  ",                {"en", "es", "fr"}),  # whitespace tolerance
])
def test_parse_allowed_locale_list(raw, expected):
    assert _parse_allowed_locale_list(raw) == expected


def test_reference_source_to_dict_drops_empty_description():
    rs = ReferenceSource(hl7_code="LN", name="LOINC", description=None,
                         retired=False, concept_reference_map_count=42)
    d = rs.to_dict()
    assert d["hl7_code"] == "LN"
    assert d["name"] == "LOINC"
    assert "description" not in d


def test_reference_source_to_dict_keeps_present_description():
    rs = ReferenceSource(hl7_code="LN", name="LOINC",
                         description="Logical Observation Identifiers",
                         retired=False, concept_reference_map_count=42)
    d = rs.to_dict()
    assert d["description"] == "Logical Observation Identifiers"


def test_locale_usage_marks_refapp_default_correctly():
    en = LocaleUsage("en", 100, expected_by_refapp=True).to_dict()
    bn = LocaleUsage("bn", 5, expected_by_refapp=False).to_dict()
    assert en["expected_by_refapp"] is True
    assert bn["expected_by_refapp"] is False


def test_default_refapp_locales_includes_english_and_spanish_french():
    assert "en" in DEFAULT_REFAPP_LOCALES
    assert "es" in DEFAULT_REFAPP_LOCALES
    assert "fr" in DEFAULT_REFAPP_LOCALES


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


legacy_only = pytest.mark.skipif(
    not _legacy_db_available(),
    reason="legacy_27_raw DB not reachable",
)


openmrs_only = pytest.mark.skipif(
    not _openmrs_db_available(),
    reason="openmrs DB (CIEL-loaded) not reachable",
)


@legacy_only
def test_legacy_corpus_reports_zero_reference_sources():
    """The legacy 2.7 dump ships with zero terminology cross-references —
    this is the M2-A finding that motivates §R-bridge-rule."""
    sources = enumerate_reference_sources(DBConfig.from_env(database="legacy_27_raw"))
    assert sources == []


@legacy_only
def test_legacy_corpus_locales_are_english_only():
    locales = enumerate_locales(DBConfig.from_env(database="legacy_27_raw"))
    assert any(l.locale == "en" for l in locales)
    # The dump's concept_name table is en-only per the inventory measurement.
    name_locales = {l.locale for l in locales if l.source_count >= 100}
    assert "en" in name_locales


@openmrs_only
def test_ciel_loaded_openmrs_has_many_reference_sources():
    """openmrs DB has CIEL loaded — should expose CIEL, LOINC, SNOMED, etc."""
    sources = enumerate_reference_sources(DBConfig.from_env(database="openmrs"))
    names = {s.name for s in sources}
    # At least a handful of major source systems.
    assert len(sources) >= 5, f"expected ≥5 reference sources from CIEL; got {len(sources)}"
    assert names & {"CIEL", "LOINC", "SNOMED CT", "SNOMED-CT"}, (
        f"expected CIEL/LOINC/SNOMED in reference sources; got {sorted(names)[:10]}"
    )


@openmrs_only
def test_ciel_loaded_openmrs_has_multilingual_locales():
    locales = enumerate_locales(DBConfig.from_env(database="openmrs"))
    locale_codes = {l.locale for l in locales}
    # CIEL ships en/es/fr at minimum.
    assert {"en", "es", "fr"}.issubset(locale_codes)
