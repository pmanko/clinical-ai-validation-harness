"""Exercise the OCL snapshot loader against both a real on-disk snapshot
and synthetic corrupt inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.ocl.snapshot import (
    OclSnapshotError,
    load_snapshot,
)


REAL_SNAPSHOT = (
    Path(__file__).resolve().parents[2]
    / "datasets" / "sources" / "ocl" / "CIEL" / "v2026-04-28"
)


# ---------- positive: the real pinned snapshot ----------


@pytest.mark.skipif(
    not REAL_SNAPSHOT.is_dir(),
    reason="pinned CIEL snapshot not present (run scripts/fetch-ciel-release.sh)",
)
def test_loads_pinned_ciel_v2026_04_28():
    snap = load_snapshot(REAL_SNAPSHOT)
    assert snap.provenance.collection == "CIEL"
    assert snap.provenance.version == "v2026-04-28"
    assert snap.provenance.size_bytes > 0
    assert len(snap.provenance.sha256) == 64


@pytest.mark.skipif(
    not (REAL_SNAPSHOT / "CIEL_v2026-04-28.zip").is_file(),
    reason="pinned CIEL archive not present",
)
def test_verify_archive_checksum_on_real_pinned_zip():
    snap = load_snapshot(REAL_SNAPSHOT)
    assert snap.archive_path.is_file()
    assert snap.verify_archive_checksum() is True


# ---------- negative: malformed inputs ----------


def test_rejects_when_snapshot_dir_missing(tmp_path: Path):
    with pytest.raises(OclSnapshotError, match="does not exist"):
        load_snapshot(tmp_path / "no-such-dir")


def test_rejects_when_provenance_missing(tmp_path: Path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    with pytest.raises(OclSnapshotError, match="provenance.json"):
        load_snapshot(snapshot_dir)


def test_rejects_when_provenance_not_json(tmp_path: Path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "provenance.json").write_text("not json at all {")
    with pytest.raises(OclSnapshotError, match="not valid JSON"):
        load_snapshot(snapshot_dir)


def test_rejects_when_required_fields_missing(tmp_path: Path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "provenance.json").write_text(
        json.dumps({"collection": "CIEL", "version": "v1"})
    )
    with pytest.raises(OclSnapshotError, match="missing required fields"):
        load_snapshot(snapshot_dir)


def test_verify_archive_checksum_detects_corruption(tmp_path: Path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    archive = snapshot_dir / "fake.zip"
    archive.write_bytes(b"original content")
    correct_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (snapshot_dir / "provenance.json").write_text(json.dumps({
        "collection": "TEST",
        "version": "v0",
        "sha256": correct_sha,
        "size_bytes": archive.stat().st_size,
        "local_path": "snapshot/fake.zip",
    }))
    snap = load_snapshot(snapshot_dir)
    assert snap.verify_archive_checksum() is True

    archive.write_bytes(b"different content")
    assert snap.verify_archive_checksum() is False


def test_archive_path_uses_basename_from_provenance(tmp_path: Path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "provenance.json").write_text(json.dumps({
        "collection": "TEST",
        "version": "v0",
        "sha256": "0" * 64,
        "size_bytes": 1,
        "local_path": "very/deep/path/to/myfile.zip",
    }))
    snap = load_snapshot(snapshot_dir)
    assert snap.archive_path == snapshot_dir / "myfile.zip"
