"""Exercise the ConceptMap → SQLMesh seed CSV emitter.

Unit-level tests (no DB) cover the bridge-rule template expansion,
the module-table-policy row shape, and the UUID-resolved FK logic.
Database-backed integration tests are guarded by DB availability checks.
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
    CT_OMISSIONS_COLUMNS,
    MTP_COLUMNS,
    _ciel_uuid,
    discover_legacy_only_tables,
    emit_concept_translation_rows,
    emit_module_table_policy_rows,
    fetch_clinically_referenced_concept_ids,
    fetch_legacy_concepts,
    fetch_target_uuid_to_id,
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


def _synthetic_target_map() -> dict[str, int]:
    """Target UUID → local concept_id map for synthetic test inputs."""
    return {
        "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": 1001,
        "5088AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": 5088001,
        "1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": 1107001,
    }


def test_emit_concept_translation_rows_shape():
    cm = load_conceptmap(FIXTURE)
    sample = [(1, "u-1"), (5088, "u-5088"), (1107, "u-1107")]
    rows, omissions = emit_concept_translation_rows(cm, sample, _synthetic_target_map())
    assert len(rows) == 3
    assert omissions == []
    # target_concept_id must be the UUID-resolved local FK, not the source integer
    assert rows[0] == ("1", "u-1", "1001", "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "equal", "remap", "")
    assert rows[1] == ("5088", "u-5088", "5088001", "5088AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "equal", "remap", "")


def test_emit_rows_omits_unreferenced_unresolvable():
    """An unreferenced concept with no target UUID is omitted into the omissions list."""
    cm = load_conceptmap(FIXTURE)
    sample = [(1, "u-1"), (999, "u-999")]  # 999 has no entry in target_map
    target_map = {"1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": 1001}
    clinically_referenced = {1}  # 999 is not referenced

    rows, omissions = emit_concept_translation_rows(cm, sample, target_map, clinically_referenced)
    assert len(rows) == 1
    assert rows[0][0] == "1"
    assert len(omissions) == 1
    assert omissions[0][0] == "999"
    assert "not found" in omissions[0][3].lower() or "not clinically referenced" in omissions[0][3].lower()


def test_emit_rows_raises_for_referenced_unresolvable():
    """A clinically-referenced concept with no target UUID raises ValueError."""
    cm = load_conceptmap(FIXTURE)
    sample = [(999, "u-999")]
    target_map: dict[str, int] = {}
    clinically_referenced = {999}

    with pytest.raises(ValueError, match="999"):
        emit_concept_translation_rows(cm, sample, target_map, clinically_referenced)


def test_emit_rows_strict_mode_raises_for_any_unresolvable():
    """With clinically_referenced=None (strict mode) any unresolvable concept raises."""
    cm = load_conceptmap(FIXTURE)
    sample = [(999, "u-999")]
    target_map: dict[str, int] = {}

    with pytest.raises(ValueError, match="999"):
        emit_concept_translation_rows(cm, sample, target_map, clinically_referenced=None)


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
    target_map = _synthetic_target_map()
    out = write_concept_translation_csv(cm, sample, target_map, None, tmp_path / "ct.csv")
    with out.open() as f:
        reader = csv.reader(f)
        header = next(reader)
        data = list(reader)
    assert tuple(header) == CT_COLUMNS
    assert len(data) == 2
    assert data[0][0] == "1"
    assert data[0][2] == "1001"                              # UUID-resolved local ID
    assert data[0][3] == "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def test_write_concept_translation_csv_writes_omissions(tmp_path: Path):
    cm = load_conceptmap(FIXTURE)
    sample = [(1, "u-1"), (999, "u-999")]
    target_map = {"1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": 1001}
    clinically_referenced = {1}  # 999 is not referenced
    out = write_concept_translation_csv(
        cm, sample, target_map, clinically_referenced,
        tmp_path / "ct.csv",
        omissions_out=tmp_path / "omissions.csv",
    )
    omissions = tmp_path / "omissions.csv"
    assert omissions.exists()
    with omissions.open() as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    assert tuple(header) == CT_OMISSIONS_COLUMNS
    assert len(rows) == 1
    assert rows[0][0] == "999"


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
    target_map = _synthetic_target_map()
    a = write_concept_translation_csv(cm, sample, target_map, None, tmp_path / "a.csv")
    b = write_concept_translation_csv(cm, sample, target_map, None, tmp_path / "b.csv")
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


def _target_db_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        val = query_scalar(DBConfig.from_env(database="openmrs"), "SELECT 1", timeout=5)
        return val == "1"
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


DB_AVAILABLE = _legacy_db_available()
BOTH_DBS_AVAILABLE = DB_AVAILABLE and _target_db_available()

db_only = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason="legacy_27_raw DB not reachable; run make up + scripts/load-demo-data.sh first",
)
both_dbs = pytest.mark.skipif(
    not BOTH_DBS_AVAILABLE,
    reason="legacy_27_raw or openmrs DB not reachable",
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
    assert len(legacy_only) == 22
    assert "formentry_archive" in legacy_only
    assert "htmlformentry_html_form" in legacy_only
    assert "concept_word" in legacy_only


@both_dbs
def test_target_uuid_to_id_resolves_known_concept():
    """CIEL UUID 794AAAA... must resolve to local concept 6689 (Lopinavir/ritonavir)."""
    cfg = DBConfig.from_env(database="openmrs")
    mapping = fetch_target_uuid_to_id(cfg)
    ciel_794 = _ciel_uuid(794)
    assert ciel_794 in mapping, f"UUID {ciel_794!r} not found in target concept table"
    assert mapping[ciel_794] == 6689, (
        f"Expected local concept_id 6689 for CIEL UUID {ciel_794!r}, "
        f"got {mapping[ciel_794]}"
    )


@both_dbs
def test_all_clinically_referenced_concepts_resolve():
    """Every obs-referenced concept_id must have a matching CIEL UUID in the target."""
    legacy_cfg = DBConfig.from_env(database="legacy_27_raw")
    target_cfg = DBConfig.from_env(database="openmrs")
    referenced = fetch_clinically_referenced_concept_ids(legacy_cfg)
    target_map = fetch_target_uuid_to_id(target_cfg)

    unresolvable = [
        cid for cid in referenced
        if _ciel_uuid(cid) not in target_map
    ]
    assert unresolvable == [], (
        f"{len(unresolvable)} clinically-referenced concepts cannot resolve by CIEL UUID: "
        f"{unresolvable[:10]}..."
    )


@both_dbs
def test_committed_concept_translation_csv_matches_fresh_emit(tmp_path: Path):
    """The committed seed must equal a fresh emit against the live DB."""
    cm = load_conceptmap(CONCEPTMAP)
    legacy_cfg = DBConfig.from_env(database="legacy_27_raw")
    target_cfg = DBConfig.from_env(database="openmrs")
    legacy_concepts = fetch_legacy_concepts(legacy_cfg)
    target_uuid_to_id = fetch_target_uuid_to_id(target_cfg)
    clinically_referenced = fetch_clinically_referenced_concept_ids(legacy_cfg)

    fresh = write_concept_translation_csv(
        cm,
        legacy_concepts,
        target_uuid_to_id,
        clinically_referenced,
        tmp_path / "ct.csv",
        omissions_out=tmp_path / "omissions.csv",
    )
    committed = (
        Path(__file__).resolve().parents[2]
        / "datasets" / "transforms" / "sqlmesh" / "seeds" / "concept_translation.csv"
    )
    assert committed.is_file()
    assert committed.read_bytes() == fresh.read_bytes(), (
        "Committed concept_translation.csv does not match a fresh emit. "
        "Re-run: python -m harness.conceptmap.seed_emit"
    )


@both_dbs
def test_seed_target_concept_ids_match_uuid_resolution():
    """Every row in the committed seed must have target_concept_id == concept.concept_id WHERE uuid = target_uuid."""
    target_cfg = DBConfig.from_env(database="openmrs")
    target_map = fetch_target_uuid_to_id(target_cfg)
    committed = (
        Path(__file__).resolve().parents[2]
        / "datasets" / "transforms" / "sqlmesh" / "seeds" / "concept_translation.csv"
    )
    assert committed.is_file()
    mismatches: list[tuple[str, str, str]] = []
    with committed.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            target_uuid = row["target_uuid"]
            seed_id = row["target_concept_id"]
            expected_id = target_map.get(target_uuid)
            if expected_id is None or str(expected_id) != seed_id:
                mismatches.append((row["source_concept_id"], target_uuid, seed_id))
                if len(mismatches) >= 10:
                    break
    assert mismatches == [], (
        f"target_concept_id does not match UUID-resolved concept_id for "
        f"{len(mismatches)} rows (showing up to 10): {mismatches}"
    )
