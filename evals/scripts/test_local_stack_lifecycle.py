"""Behavioral coverage for the shared and fast-resume stack lifecycle scripts."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_NAMES = (
    "local-stack-up.sh",
    "local-stack-down.sh",
    "stack-up.sh",
    "stack-down.sh",
)


def _write_executable(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    root = tmp_path / "harness"
    scripts = root / "scripts"
    fake_bin = tmp_path / "bin"
    scripts.mkdir(parents=True)
    fake_bin.mkdir()
    (root / "compose").mkdir()
    (root / "targets" / "med-agent-hub").mkdir(parents=True)
    (root / "compose" / "openmrs-2.8-refapp.yml").write_text(
        "services: {}\n", encoding="utf-8"
    )
    for name in (*SCRIPT_NAMES, "llama-router-up.sh", "llama-router.ini"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)

    docker_log = tmp_path / "docker.log"
    router_ready = tmp_path / "router.ready"
    router_invocation = tmp_path / "router-invocation.log"
    _write_executable(
        fake_bin / "docker",
        """#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_DOCKER_LOG}"
case "${1:-}" in
  info) exit "${FAKE_DOCKER_INFO_STATUS:-0}" ;;
  desktop) exit 1 ;;
  compose)
    case "$*" in
      *" config --quiet"*) exit "${FAKE_DOCKER_CONFIG_STATUS:-0}" ;;
      *" up "*) exit "${FAKE_DOCKER_UP_STATUS:-0}" ;;
      *" down"*) exit "${FAKE_DOCKER_DOWN_STATUS:-0}" ;;
      *) exit 0 ;;
    esac
    ;;
  *) exit 0 ;;
esac
""",
    )
    _write_executable(
        fake_bin / "git",
        """#!/usr/bin/env bash
printf 'test-hub-revision\n'
""",
    )
    _write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
[[ "${FAKE_CURL_ALWAYS_FAIL:-0}" != "1" && -f "${FAKE_ROUTER_READY}" ]]
""",
    )
    _write_executable(
        fake_bin / "llama-server",
        """#!/usr/bin/env bash
printf 'models_max=%s args=%s\n' "${LLAMA_ROUTER_MODELS_MAX:-}" "$*" > "${FAKE_ROUTER_INVOCATION}"
touch "${FAKE_ROUTER_READY}"
trap 'exit 0' INT TERM
while true; do sleep 1; done
""",
    )
    _write_executable(
        fake_bin / "ps",
        """#!/usr/bin/env bash
printf '%s\n' "${FAKE_PS_COMMAND}"
""",
    )
    _write_executable(
        fake_bin / "uname",
        """#!/usr/bin/env bash
printf '%s\n' "${FAKE_UNAME:-Darwin}"
""",
    )

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (root / ".env.chartsearch").write_text(
        "\n".join(
            (
                f"LLAMA_MODEL_DIR={model_dir}",
                "LLAMA_ROUTER_MODELS_MAX=7",
                "HARNESS_PROXY_HTTP_PORT=9088",
                "QUERYSTORE_ES_PORT=9920",
                "",
            )
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        "FAKE_DOCKER_LOG": str(docker_log),
        "FAKE_ROUTER_READY": str(router_ready),
        "FAKE_ROUTER_INVOCATION": str(router_invocation),
        "FAKE_PS_COMMAND": (
            f"llama-server --models-preset {root / 'scripts' / 'llama-router.ini'} "
            "--port 8077"
        ),
        "LOCAL_STACK_DOCKER_TIMEOUT_SECONDS": "1",
        "LOCAL_STACK_ROUTER_TIMEOUT_SECONDS": "5",
        "STACK_WAIT_TIMEOUT_SECONDS": "9",
        "HUB_BUILD_REVISION": "test-hub-revision",
    }
    return root, docker_log, env


@pytest.mark.parametrize("name", SCRIPT_NAMES)
def test_local_lifecycle_scripts_are_executable_and_parse(name: str) -> None:
    script = ROOT / "scripts" / name

    assert script.stat().st_mode & stat.S_IXUSR
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_stack_up_passes_explicit_env_wait_and_no_build(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(
        fake_bin / "docker",
        """#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_DOCKER_LOG}"
""",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_DOCKER_LOG": str(docker_log),
        "COMPOSE_ENV_FILE": str(tmp_path / "local.env"),
    }

    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts" / "stack-up.sh"),
            "--wait-timeout",
            "17",
            "--no-build",
            "backend",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = docker_log.read_text(encoding="utf-8").splitlines()
    assert calls[0].endswith("up -d --no-build --wait --wait-timeout 17 backend")
    assert f"--env-file {tmp_path / 'local.env'}" in calls[0]
    assert calls[1].endswith("ps")


def test_stack_up_rejects_unknown_options(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "stack-up.sh"), "--surprise"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unknown option" in result.stderr


def test_local_stack_requires_its_operator_configuration(tmp_path: Path) -> None:
    root, _docker_log, env = _fixture(tmp_path)
    (root / ".env.chartsearch").unlink()

    result = subprocess.run(
        ["bash", str(root / "scripts" / "local-stack-up.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert ".env.chartsearch not found" in result.stderr


def test_local_stack_does_not_try_to_launch_docker_desktop_off_macos(
    tmp_path: Path,
) -> None:
    root, _docker_log, env = _fixture(tmp_path)
    env["FAKE_DOCKER_INFO_STATUS"] = "1"
    env["FAKE_UNAME"] = "Linux"

    result = subprocess.run(
        ["bash", str(root / "scripts" / "local-stack-up.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "start Docker and retry" in result.stderr


def test_local_stack_fails_and_cleans_up_when_router_never_becomes_ready(
    tmp_path: Path,
) -> None:
    root, _docker_log, env = _fixture(tmp_path)
    env["FAKE_CURL_ALWAYS_FAIL"] = "1"
    env["LOCAL_STACK_ROUTER_TIMEOUT_SECONDS"] = "1"
    pid_file = root / "artifacts" / "llama-router" / "router.pid"

    result = subprocess.run(
        ["bash", str(root / "scripts" / "local-stack-up.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "llama-router did not become ready" in result.stderr
    assert not pid_file.exists()


def test_local_stack_cleans_started_router_when_compose_start_fails(
    tmp_path: Path,
) -> None:
    root, _docker_log, env = _fixture(tmp_path)
    env["FAKE_DOCKER_UP_STATUS"] = "1"
    pid_file = root / "artifacts" / "llama-router" / "router.pid"

    result = subprocess.run(
        ["bash", str(root / "scripts" / "local-stack-up.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Compose startup failed" in result.stderr
    assert not pid_file.exists()


def test_local_stack_round_trip_uses_config_and_stops_managed_router(
    tmp_path: Path,
) -> None:
    root, docker_log, env = _fixture(tmp_path)
    pid_file = root / "artifacts" / "llama-router" / "router.pid"

    up = subprocess.run(
        ["bash", str(root / "scripts" / "local-stack-up.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert up.returncode == 0, up.stderr
    assert "OpenMRS SPA:   http://localhost:9088" in up.stdout
    assert "Elasticsearch: http://localhost:9920" in up.stdout
    assert pid_file.is_file()
    router_pid = int(pid_file.read_text(encoding="utf-8"))
    invocation = Path(env["FAKE_ROUTER_INVOCATION"]).read_text(encoding="utf-8")
    assert "models_max=7" in invocation

    down = subprocess.run(
        ["bash", str(root / "scripts" / "local-stack-down.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    try:
        assert down.returncode == 0, down.stderr
        assert f"stopped managed router PID {router_pid}" in down.stdout
        assert not pid_file.exists()
        with pytest.raises(ProcessLookupError):
            os.kill(router_pid, 0)
    finally:
        try:
            os.kill(router_pid, 9)
        except ProcessLookupError:
            pass

    calls = docker_log.read_text(encoding="utf-8").splitlines()
    assert any("config --quiet" in call for call in calls)
    assert any("up -d --no-build --wait --wait-timeout 9" in call for call in calls)
    assert any(call.endswith("down") for call in calls)


def test_local_stack_down_cleans_router_even_when_compose_teardown_fails(
    tmp_path: Path,
) -> None:
    root, _docker_log, env = _fixture(tmp_path)
    pid_file = root / "artifacts" / "llama-router" / "router.pid"

    up = subprocess.run(
        ["bash", str(root / "scripts" / "local-stack-up.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert up.returncode == 0, up.stderr
    router_pid = int(pid_file.read_text(encoding="utf-8"))
    env["FAKE_DOCKER_DOWN_STATUS"] = "1"

    down = subprocess.run(
        ["bash", str(root / "scripts" / "local-stack-down.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    try:
        assert down.returncode != 0
        assert "continuing with router cleanup" in down.stderr
        assert f"stopped managed router PID {router_pid}" in down.stdout
        assert not pid_file.exists()
        with pytest.raises(ProcessLookupError):
            os.kill(router_pid, 0)
    finally:
        try:
            os.kill(router_pid, 9)
        except ProcessLookupError:
            pass


@pytest.mark.parametrize(
    "observed_command",
    (
        "sleep 30",
        "llama-server --models-preset /other/checkout/scripts/llama-router.ini",
    ),
)
def test_local_stack_down_leaves_unmanaged_pid_running(
    tmp_path: Path, observed_command: str
) -> None:
    root, _docker_log, env = _fixture(tmp_path)
    pid_file = root / "artifacts" / "llama-router" / "router.pid"
    pid_file.parent.mkdir(parents=True)
    env["FAKE_PS_COMMAND"] = observed_command
    sleeper = subprocess.Popen(["sleep", "30"])
    pid_file.write_text(f"{sleeper.pid}\n", encoding="utf-8")

    try:
        result = subprocess.run(
            ["bash", str(root / "scripts" / "local-stack-down.sh")],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "is not this project's llama-router; leaving it running" in result.stderr
        assert sleeper.poll() is None
        assert not pid_file.exists()
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)


def test_makefile_exposes_named_local_stack_targets() -> None:
    result = subprocess.run(
        ["make", "--dry-run", "local-stack-up", "local-stack-down"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "./scripts/local-stack-up.sh" in result.stdout
    assert "./scripts/local-stack-down.sh" in result.stdout
