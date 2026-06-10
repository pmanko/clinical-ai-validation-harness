"""gen_modules must regenerate the carry-forward models byte-identically.

This is the generator's idempotency / source-of-truth contract (SC-004):
re-running it against the real legacy_27_raw schema must reproduce the reviewed
model files exactly, so the generator stays the single source of truth and a
re-run never silently reverts the date-transplant @shift_date edits. Exercises
the real generator against the live DB — real information_schema, real column
types and ordering, no mocks.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from harness.profile.db import DBConfig, DBError, query_scalar
from harness.transform import gen_modules

MODELS_DIR = Path("datasets/transforms/sqlmesh/models/modules")


def _legacy_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return (
            query_scalar(
                DBConfig.from_env(database="legacy_27_raw"), "SELECT 1", timeout=5
            )
            == "1"
        )
    except (DBError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


db_only = pytest.mark.skipif(
    not _legacy_available(), reason="legacy_27_raw not reachable"
)


@db_only
def test_generator_reproduces_committed_models_byte_identically(tmp_path):
    """Regenerate into a temp dir; every file must match its committed twin."""
    written, _skipped = gen_modules.generate(out_dir=tmp_path)
    assert written, "generator wrote no models"

    drifted = []
    for path in written:
        committed = MODELS_DIR / path.name
        assert committed.exists(), f"generated {path.name} has no committed counterpart"
        if path.read_text() != committed.read_text():
            drifted.append(path.name)

    assert not drifted, (
        "generator output drifted from the committed reviewed models "
        f"({len(drifted)}): " + ", ".join(sorted(drifted))
    )
