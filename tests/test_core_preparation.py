"""Run the real shell launcher against isolated command doubles, never Docker."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def launcher(tmp_path):
    root = tmp_path / "project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/chartsearchai-local.sh", scripts)
    (scripts / "artifact-provenance.py").write_text("raise SystemExit(0)\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "commands.jsonl"
    for name in ("git", "make", "docker", "curl"):
        stub = bin_dir / name
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "with open(os.environ['TEST_COMMAND_LOG'], 'a') as out:\n"
            "    out.write(json.dumps([Path(sys.argv[0]).name, *sys.argv[1:]])+'\\n')\n"
            "if Path(sys.argv[0]).name == 'git': print('tested-sha')\n"
            "if Path(sys.argv[0]).name == 'docker' and sys.argv[1] == 'inspect': print('healthy')\n"
        )
        stub.chmod(0o755)
    directory = root / "artifacts/chartsearchai-local"
    (directory / "module-provenance").mkdir(parents=True)
    for module in ("chartsearchai", "querystore"):
        (
            directory
            / "module-provenance"
            / f"{module}-1.0.0-SNAPSHOT.omod.provenance.json"
        ).write_text("{}")
        (directory / f"deployed-{module}-omod.json").write_text("{}")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "TEST_COMMAND_LOG": str(log),
        "CHARTSEARCH_LOCAL_BUILD": "never",
    }

    def run(*args):
        result = subprocess.run(
            ["bash", str(scripts / "chartsearchai-local.sh"), *args],
            env=env,
            capture_output=True,
            text=True,
        )
        calls = (
            [json.loads(line) for line in log.read_text().splitlines()]
            if log.exists()
            else []
        )
        return result, calls

    return run


def test_core_check_does_not_need_or_contact_a_model_server(launcher):
    result, calls = launcher("--prepare-core", "--check")
    assert result.returncode == 0, result.stderr
    assert "model/provider readiness not checked" in result.stdout
    assert not any(call[0] == "curl" for call in calls)
    assert not any(call[0] == "make" for call in calls)
    assert not any("up" in call or "restart" in call for call in calls)


def test_core_preparation_never_calls_provider_configuration_or_inference(launcher):
    result, calls = launcher("--prepare-core")
    assert result.returncode == 0, result.stderr
    assert "core prepared" in result.stdout
    assert "ChartSearchAI is ready" not in result.stdout
    assert any("up" in call for call in calls)
    assert not any("med-agent-hub" in call for call in calls)
    urls = [part for call in calls for part in call if part.startswith("http")]
    assert urls == ["http://127.0.0.1:8088/__proxy_health"]
    # A missing configuration/probe script would make this real shell run fail
    # if the preparation path fell through into settings or inference work.


def test_unknown_mode_fails_before_build_or_docker_mutation(launcher):
    result, calls = launcher("--wipe")
    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert all(call[0] == "git" for call in calls)
