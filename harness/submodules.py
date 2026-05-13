from __future__ import annotations

import configparser
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class SubmoduleSyncPlan:
    """Planned git commands to initialize pinned submodules."""

    commands: tuple[list[str], ...]


def read_gitmodules_submodule_paths(project_root: Path) -> dict[str, str]:
    """Return mapping submodule name -> path from .gitmodules."""
    gm = project_root / ".gitmodules"
    if not gm.is_file():
        return {}
    cfg = configparser.ConfigParser()
    cfg.read(gm)
    out: dict[str, str] = {}
    for section in cfg.sections():
        if not section.startswith("submodule "):
            continue
        name = section[len("submodule ") :].strip().strip('"')
        if cfg.has_option(section, "path"):
            out[name] = cfg.get(section, "path").strip()
    return out


def plan_submodule_update(
    submodule_rel_paths: Sequence[str],
    *,
    depth: int | None = None,
) -> SubmoduleSyncPlan:
    cmds: list[list[str]] = []
    for rel in submodule_rel_paths:
        cmd = ["git", "submodule", "update", "--init", "--recursive"]
        if depth is not None:
            cmd.extend(["--depth", str(depth)])
        cmd.append(rel)
        cmds.append(cmd)
    return SubmoduleSyncPlan(commands=tuple(cmds))


def read_superproject_gitlink(project_root: Path, submodule_path: str) -> str | None:
    """Return gitlink SHA recorded in the superproject index for submodule path."""
    try:
        out = subprocess.run(
            ["git", "ls-tree", "HEAD", submodule_path],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    # format: <mode> <type> <object>\t<path>
    parts = out.stdout.strip().split(maxsplit=3)
    if len(parts) < 3:
        return None
    if parts[1] != "commit":
        return None
    return parts[2]


def read_submodule_head(project_root: Path, submodule_path: str) -> str | None:
    """Return current HEAD SHA inside submodule working tree, if present."""
    sub = project_root / submodule_path
    if not (sub / ".git").exists() and not (sub / ".git").is_file():
        # gitfile or .git dir
        pass
    if not sub.is_dir():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(sub), "rev-parse", "HEAD"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    sha = out.stdout.strip()
    return sha or None


def submodule_worktree_dirty(project_root: Path, submodule_path: str) -> bool:
    sub = project_root / submodule_path
    if not sub.is_dir():
        return False
    try:
        out = subprocess.run(
            ["git", "-C", str(sub), "status", "--porcelain"],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if out.returncode != 0:
        return False
    return bool(out.stdout.strip())


def read_override_path(env_name: str) -> Path | None:
    raw = os.environ.get(env_name)
    if not raw:
        return None
    return Path(raw).expanduser()


def read_harness_git_sha(project_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unknown"
    if out.returncode != 0:
        return "unknown"
    return out.stdout.strip() or "unknown"
