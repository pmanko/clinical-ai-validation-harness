"""UI release operations must not replace application or data dependencies."""

import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def configured_ui(tmp_path):
    target = tmp_path / "Catalyst checkout"
    target.mkdir()
    (target / ".env").write_text("CATALYST_UI_PORT=13000\n")
    override = tmp_path / "isolated override.yml"
    override.touch()
    output = tmp_path / "docker-call.json"
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['DOCKER_CALL']).write_text(json.dumps({"
        "'args': sys.argv[1:], 'port': os.environ['CATALYST_UI_PORT']}))\n"
        "sys.exit(int(os.environ.get('DOCKER_STATUS', '0')))\n"
    )
    docker.chmod(0o755)
    return target, override, output, {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CATALYST_DIR": str(target),
        "MVP_COMPOSE_OVERRIDE_FILE": str(override),
        "CATALYST_UI_PORT": "13001",
        "DOCKER_CALL": str(output),
    }


@pytest.mark.parametrize("status", [0, 37])
def test_update_targets_only_ui_and_propagates_build_failures(configured_ui, status):
    target, override, output, env = configured_ui
    env["DOCKER_STATUS"] = str(status)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/catalyst-ui-update.sh")],
        env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == status, result.stderr
    call = json.loads(output.read_text())
    assert call["args"] == [
        "compose", "--project-directory", str(target),
        "--env-file", str(target / ".env"),
        "-f", str(target / "docker-compose.mvp.yml"), "-f", str(override),
        "up", "--detach", "--build", "--no-deps", "catalyst-ui",
    ]
    assert call["port"] == "13001"


def test_unconfigured_checkout_does_not_start_docker(configured_ui):
    target, _, output, env = configured_ui
    (target / ".env").unlink()
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/catalyst-ui-update.sh")],
        env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert ".env missing" in result.stderr
    assert not output.exists()
