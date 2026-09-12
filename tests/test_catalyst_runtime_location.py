"""Temporary review checkouts must not become persistent runtime owners."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "command", ["up", "boot", "restart", "seed", "warm", "superset-import"]
)
def test_temporary_runtime_rejected_before_target_or_docker_access(tmp_path, command):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "compose").mkdir()
    shutil.copy(ROOT / "scripts/catalyst-mvp.sh", tmp_path / "scripts/catalyst-mvp.sh")
    (tmp_path / "compose/catalyst-mvp-isolated.override.yml").touch()
    env = {**os.environ, "TMPDIR": str(tmp_path) + "/"}
    env.pop("MVP_COMPOSE_OVERRIDE_FILE", None)
    result = subprocess.run(
        ["bash", str(tmp_path / "scripts/catalyst-mvp.sh"), command],
        env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "start Catalyst from a persistent checkout" in result.stderr
    assert "is not initialized" not in result.stderr
