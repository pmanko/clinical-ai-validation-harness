"""Confirm the SQLMesh project parses and surfaces the expected models."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"


def _run_sqlmesh(*args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "MARIADB_HOST": "127.0.0.1",
        "MARIADB_PORT": "3307",
        "MARIADB_USER": "openmrs",
        "MARIADB_PASSWORD": "openmrs",
    }
    return subprocess.run(
        [sys.executable.replace("python3", "sqlmesh"), "-p", str(SQLMESH_DIR), *args],
        env=env, capture_output=True, text=True, check=False,
    )


def _sqlmesh_bin() -> Path:
    candidate = Path(sys.executable).parent / "sqlmesh"
    return candidate


# `test_project_root_exists` (config.yaml) and `test_seeds_present` (the seed CSVs)
# were dropped: both are hard prerequisites for `sqlmesh info` to run at all. Without
# config.yaml the CLI cannot load the project, and a SEED model declares its CSV via an
# explicit `path` so a missing CSV is a load error that suppresses the "Models:" line —
# either way test_sqlmesh_info_runs_and_lists_models goes red. The name-specific model/
# audit checks below are NOT redundant: the parse test only asserts a loose count
# (>= 46 vs 71 actual), so a single missing model just drops the count and stays green,
# and audits are not counted by `sqlmesh info` at all. They pin required artifacts the
# count threshold misses.


def test_seed_models_present():
    models = SQLMESH_DIR / "models" / "seeds"
    assert (models / "concept_translation.sql").is_file()
    assert (models / "module_table_policy.sql").is_file()


def test_clinical_promotion_models_present():
    clinical = SQLMESH_DIR / "models" / "clinical"
    for name in ("obs", "drug_order", "conditions", "allergy", "test_order"):
        assert (clinical / f"{name}.sql").is_file(), f"missing clinical/{name}.sql"


def test_staging_models_cover_critical_legacy_tables():
    staging = SQLMESH_DIR / "models" / "staging"
    present = {p.stem for p in staging.glob("stg_*.sql")}
    for critical in ("stg_patient", "stg_person",
                     "stg_encounter", "stg_obs"):
        assert critical in present, f"missing critical staging model {critical}"


def test_audits_present():
    audits = SQLMESH_DIR / "audits"
    for name in (
        "audit_concept_translation_coverage",
        "audit_clinical_fk_integrity",
        "audit_policy_bucket_coverage",
    ):
        assert (audits / f"{name}.sql").is_file(), f"missing audit {name}"


@pytest.mark.skipif(
    not (Path(sys.executable).parent / "sqlmesh").is_file(),
    reason="sqlmesh CLI not in venv bin (install via `uv sync`)",
)
def test_sqlmesh_info_runs_and_lists_models():
    """`sqlmesh info` should at least PARSE the project even if the warehouse
    is unreachable. The model count must include our seeds + clinical + staging."""
    sqlmesh_bin = Path(sys.executable).parent / "sqlmesh"
    env = {
        **os.environ,
        "MARIADB_HOST": "127.0.0.1",
        "MARIADB_PORT": "3307",
        "MARIADB_USER": "openmrs",
        "MARIADB_PASSWORD": "openmrs",
    }
    proc = subprocess.run(
        [str(sqlmesh_bin), "-p", str(SQLMESH_DIR), "info"],
        env=env, capture_output=True, text=True, check=False,
    )
    # Parsing must succeed even if the warehouse connection fails — `info`
    # reports model/macro counts then attempts to ping. We assert the report
    # is present.
    combined = proc.stdout + proc.stderr
    assert "Models:" in combined, f"sqlmesh info did not list models:\n{combined}"
    # Extract the count.
    import re
    m = re.search(r"Models:\s*(\d+)", combined)
    assert m is not None
    n = int(m.group(1))
    # 2 seeds + 5 clinical + 39 staging = 46. Allow ≥ since we may add more.
    assert n >= 46, f"expected ≥46 SQLMesh models; got {n}"
