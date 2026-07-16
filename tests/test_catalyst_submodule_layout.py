"""Repository-layout guards for the harness-owned Catalyst MVP pin."""

from __future__ import annotations

import configparser
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_catalyst_and_hub_are_sibling_harness_submodules() -> None:
    config = configparser.ConfigParser()
    config.read(ROOT / ".gitmodules", encoding="utf-8")

    assert config["submodule \"targets/catalyst\""]["path"] == "targets/catalyst"
    assert config["submodule \"targets/med-agent-hub\""]["path"] == "targets/med-agent-hub"
    assert "160000 commit" in _git("ls-tree", "HEAD", "targets/catalyst")
    assert "160000 commit" in _git("ls-tree", "HEAD", "targets/med-agent-hub")


def test_pinned_catalyst_declares_no_nested_submodules() -> None:
    assert _git("-C", "targets/catalyst", "ls-tree", "HEAD", ".gitmodules") == ""
    assert "160000 commit" not in _git("-C", "targets/catalyst", "ls-tree", "HEAD")
