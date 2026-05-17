"""Exercise the ConceptMap → SQLMesh seed CSV emitter.

The unit-level tests (no DB) cover the bridge-rule template expansion
and the module-table-policy row shape. Database-backed integration tests
are guarded by the legacy_27_raw availability check.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import pytest

from harness.conceptmap.load import load_conceptmap
from harness.conceptmap.seed_emit import (
    CT_COLUMNS,
    MTP_COLUMNS,
    _ciel_uuid,
    discover_legacy_only_tables,
    emit_concept_translation_rows,
    emit_module_table_policy_rows,
    fetch_legacy_concepts,
    write_concept_translation_csv,
    write_module_table_policy_csv,
)
from harness.profile.db import DBConfig, DBError, query_scalar


FIXTURE = Path(__file__).parent / "fixtures" / "minimal.conceptmap.json"
CONCEPTMAP = Path(__file__).resolve().parents[2] / "datasets" / "mappings" / "openmrs-2.7-to-2.8.conceptmap.json"


# ---------- unit: bridge UUID template ----------


@pytest.mark.parametrize("cid,expected", [
    (1,    "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
    (5088, "5088AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
    (1107, "1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
    (123456, "123456AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
])
def test_ciel_uuid_pattern(cid: int, expected: str):
    out = _ciel_uuid(cid)
    assert out == expected
    assert len(out) == 36


# ---------- unit: rows from synthetic inputs ----------


def test_emit_concept_translation_rows_shape():
    cm = load_conceptmap(FIXTURE)
    sample = [(1, "u-1"), (5088, "u-5088"), (1107, "u-1107")]
    rows = emit_concept_translation_rows(cm, sample)
    assert len(rows) == 3
    assert rows[0] == ("1", "u-1", "1", "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "equal", "remap", "")
    assert rows[1] == ("5088", "u-5088", "5088", "5088AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "equal", "remap", "")


def test_emit_module_table_policy_rows_sorted_alphabetically():
    rows = emit_module_table_policy_rows(["zeta_table", "alpha_table", "mu_table"])
    table_names = [r[0] for r in rows]
    assert table_names == ["alpha_table", "mu_table", "zeta_table"]
    for r in rows:
        assert r[1] == "carry-forward"


def test_emit_module_table_policy_rows_respects_default_policy_arg():
    rows = emit_module_table_policy_rows(["x"], default_policy="drop")
    assert rows[0][1] == "drop"


# ---------- unit: CSV writers ----------


def test_write_concept_translation_csv_round_trips(tmp_path: Path):
    cm = load_conceptmap(FIXTURE)
    sample = [(1, "u-1"), (5088, "u-5088")]
    out = write_concept_translation_csv(cm, sample, tmp_path / "ct.csv")
    with out.open() as f:
        reader = csv.reader(f)
        header = next(reader)
        data = list(reader)
    assert tuple(header) == CT_COLUMNS
    assert len(data) == 2
    assert data[0][0] == "1"
    assert data[0][3] == "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def test_write_module_table_policy_csv_round_trips(tmp_path: Path):
    out = write_module_table_policy_csv(["foo", "bar"], tmp_path / "mtp.csv")
    with out.open() as f:
        reader = csv.reader(f)
        header = next(reader)
        data = list(reader)
    assert tuple(header) == MTP_COLUMNS
    assert data[0][0] == "bar"
    assert data[1][0] == "foo"


def test_writer_emits_deterministic_bytes(tmp_path: Path):
    cm = load_conceptmap(FIXTURE)
    sample = [(1, "u-1"), (5088, "u-5088")]
    a = write_concept_translation_csv(cm, sample, tmp_path / "a.csv")
    b = write_concept_translation_csv(cm, sample, tmp_path / "b.csv")
    assert a.read_bytes() == b.read_bytes()


# ---------- DB-backed integration ----------


def _legacy_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        val = query_scalar(DBConfig.from_env(database="legacy_27_raw"), "SELECT 1", timeout=5)
        return val == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


DB_AVAILABLE = _legacy_db_available()
db_only = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason="legacy_27_raw DB not reachable; run make up + scripts/load-demo-data.sh first",
)


@db_only
def test_fetch_legacy_concepts_returns_sorted_unique_ids():
    cfg = DBConfig.from_env(database="legacy_27_raw")
    concepts = fetch_legacy_concepts(cfg)
    assert len(concepts) > 0
    ids = [c[0] for c in concepts]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


@db_only
def test_discover_legacy_only_tables_returns_22_against_openmrs():
    legacy = DBConfig.from_env(database="legacy_27_raw")
    target = DBConfig.from_env(database="openmrs")
    legacy_only = discover_legacy_only_tables(legacy, target)
    # Currently measured: 22 legacy-only tables in the 2.7 dump that the
    # RefApp 3.6 schema does not have.
    assert len(legacy_only) == 22
    # Some well-known module tables that should be in the list.
    assert "formentry_archive" in legacy_only
    assert "htmlformentry_html_form" in legacy_only
    assert "concept_word" in legacy_only


@db_only
def test_committed_concept_translation_csv_matches_fresh_emit(tmp_path: Path):
    """The committed seed must equal a fresh emit against the live DB."""
    cm = load_conceptmap(CONCEPTMAP)
    cfg = DBConfig.from_env(database="legacy_27_raw")
    legacy_concepts = fetch_legacy_concepts(cfg)
    fresh = write_concept_translation_csv(
        cm, legacy_concepts, tmp_path / "ct.csv"
    )
    committed = (
        Path(__file__).resolve().parents[2]
        / "datasets" / "transforms" / "sqlmesh" / "seeds" / "concept_translation.csv"
    )
    assert committed.is_file()
    assert committed.read_bytes() == fresh.read_bytes()
