from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "script_name",
    [
        "check-querystore-drift.py",
        "verify-portable-dump.py",
        "verify-validation-corpus.py",
    ],
)
def test_cli_bootstraps_repo_imports_without_pythonpath(tmp_path: Path, script_name: str) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        ["python3", str(ROOT / "scripts" / script_name), "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
