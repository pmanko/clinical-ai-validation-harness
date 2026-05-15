"""Read-side companion to ``harness.ocl.bootstrap``.

The bootstrap module fetches pinned OCL exports onto disk and runs the
offline import into OpenMRS. This module reads the resulting on-disk
snapshot: a directory under ``datasets/sources/ocl/<collection>/<version>/``
containing at minimum a ``provenance.json`` and the canonical export ZIP.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


REQUIRED_PROVENANCE_FIELDS = {"collection", "version", "sha256", "size_bytes", "local_path"}


class OclSnapshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class OclProvenance:
    collection: str           # "CIEL" | "LOINC" | "SNOMED-CT" etc.
    version: str              # e.g. "v2026-04-28"
    sha256: str               # of the export archive
    size_bytes: int
    local_path: str           # relative to repo root
    ocl_source: str | None = None
    ocl_export_endpoint: str | None = None
    retrieved_at: str | None = None


@dataclass(frozen=True)
class OclSnapshot:
    root: Path                # directory containing provenance.json + the archive
    provenance: OclProvenance

    @property
    def archive_path(self) -> Path:
        """The export archive, by basename of provenance.local_path, in ``root``."""
        return self.root / Path(self.provenance.local_path).name

    def verify_archive_checksum(self) -> bool:
        """Recompute the archive's SHA-256 and compare to provenance.

        Raises ``OclSnapshotError`` if the archive is missing.
        """
        if not self.archive_path.exists():
            raise OclSnapshotError(f"archive missing: {self.archive_path}")
        actual = hashlib.sha256(self.archive_path.read_bytes()).hexdigest()
        return actual == self.provenance.sha256


def load_snapshot(snapshot_dir: Path | str) -> OclSnapshot:
    """Load + validate the snapshot at ``snapshot_dir``.

    Refuses to load if ``provenance.json`` is missing or malformed, or
    if the file is missing any required field. Does NOT read the archive
    itself — use ``OclSnapshot.verify_archive_checksum()`` for that.
    """
    root = Path(snapshot_dir)
    prov_path = root / "provenance.json"
    if not root.is_dir():
        raise OclSnapshotError(f"snapshot dir does not exist: {root}")
    if not prov_path.is_file():
        raise OclSnapshotError(f"missing required provenance.json under {root}")
    try:
        data = json.loads(prov_path.read_text())
    except json.JSONDecodeError as exc:
        raise OclSnapshotError(f"provenance.json is not valid JSON: {exc}") from exc

    missing = REQUIRED_PROVENANCE_FIELDS - set(data.keys())
    if missing:
        raise OclSnapshotError(
            f"provenance.json missing required fields: {sorted(missing)}"
        )

    return OclSnapshot(
        root=root,
        provenance=OclProvenance(
            collection=data["collection"],
            version=data["version"],
            sha256=data["sha256"],
            size_bytes=int(data["size_bytes"]),
            local_path=data["local_path"],
            ocl_source=data.get("ocl_source"),
            ocl_export_endpoint=data.get("ocl_export_endpoint"),
            retrieved_at=data.get("retrieved_at"),
        ),
    )


__all__ = ["OclSnapshot", "OclProvenance", "OclSnapshotError", "load_snapshot"]
