"""Behavioral tests for scripts/local-stack-up.sh and scripts/local-stack-down.sh.

Two things worth pinning with a real subprocess, not just ShellCheck:
  - local-stack-up.sh must fail fast (non-zero exit, clear stderr) when
    .env.chartsearch is missing, instead of limping into a `docker compose up`
    that would fail confusingly deep inside stack-up.sh.
  - local-stack-down.sh must never kill a PID that isn't actually a
    llama-server process — the whole point of moving off a broad `pkill -f`.
    Proven against a real running process, not a mock.

Neither test needs Docker: `docker` is stubbed to a no-op success on PATH so
stack-down.sh's delegated `docker compose ... down` is a no-op, and
local-stack-up.sh's failure happens before it ever touches Docker.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_UP = _REPO_ROOT / "scripts" / "local-stack-up.sh"
_LOCAL_DOWN = _REPO_ROOT / "scripts" / "local-stack-down.sh"
_STACK_DOWN = _REPO_ROOT / "scripts" / "stack-down.sh"


def _fake_repo(tmp_path: Path) -> Path:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    for src in (_LOCAL_UP, _LOCAL_DOWN, _STACK_DOWN):
        dest = scripts_dir / src.name
        shutil.copy(src, dest)
        dest.chmod(0o755)
    return tmp_path


def _fake_docker_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    docker.chmod(0o755)
    return bin_dir


def _provision_env_and_hub_submodule(repo: Path) -> None:
    """Satisfy both scripts' required-config prelude: .env.chartsearch present,
    and targets/med-agent-hub a real (tiny) git repo so `git rev-parse HEAD`
    for HUB_BUILD_REVISION succeeds."""
    (repo / ".env.chartsearch").write_text("", encoding="utf-8")
    hub_dir = repo / "targets" / "med-agent-hub"
    hub_dir.mkdir(parents=True)
    run = lambda *args: subprocess.run(  # noqa: E731
        args, cwd=hub_dir, check=True, capture_output=True, text=True
    )
    run("git", "init", "--quiet")
    run("git", "config", "user.email", "test@example.com")
    run("git", "config", "user.name", "test")
    (hub_dir / "README.md").write_text("test\n", encoding="utf-8")
    run("git", "add", "README.md")
    run("git", "commit", "--quiet", "-m", "init")


def test_local_stack_up_fails_fast_without_env_chartsearch(tmp_path):
    repo = _fake_repo(tmp_path)

    result = subprocess.run(
        [str(repo / "scripts" / "local-stack-up.sh")],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode != 0
    assert ".env.chartsearch" in result.stderr


def test_local_stack_down_never_kills_a_non_llama_server_pid(tmp_path):
    repo = _fake_repo(tmp_path)
    bin_dir = _fake_docker_bin(tmp_path)
    _provision_env_and_hub_submodule(repo)
    router_dir = repo / "artifacts" / "llama-router"
    router_dir.mkdir(parents=True)

    # A real, currently-running process that is deliberately NOT llama-server.
    sentinel = subprocess.Popen(["sleep", "30"])  # noqa: S603,S607
    try:
        (router_dir / "router.pid").write_text(str(sentinel.pid), encoding="utf-8")
        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}:{env['PATH']}"

        result = subprocess.run(
            [str(repo / "scripts" / "local-stack-down.sh")],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert sentinel.poll() is None, "local-stack-down.sh killed a process it did not start"
        assert "WARNING" in result.stdout
    finally:
        sentinel.terminate()
        sentinel.wait(timeout=5)
