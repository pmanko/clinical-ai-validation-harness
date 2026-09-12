"""Safe source updates for the local ChartSearchAI evaluation workflow."""

from __future__ import annotations

import subprocess
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from harness.validate.dump_provenance import verify_dump


SHARED_ORIGIN = "https://github.com/pmanko/clinical-ai-validation-harness.git"


class SetupError(RuntimeError):
    """An incomplete setup step requiring an explicit correction, not a reset."""


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise SetupError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _origin_identity(value: str) -> str:
    # Accept the SSH and HTTPS spellings of the same shared repository.
    return (
        value.removesuffix("/")
        .removesuffix(".git")
        .replace("git@github.com:", "https://github.com/")
    )


def _require_clean(root: Path) -> None:
    status = _git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    if status:
        raise SetupError(
            "This checkout has local changes (including untracked files or changed "
            "submodule pins). Preserve and review them before updating; nothing "
            "was stashed, reset, or deleted.\n" + status
        )


def _submodule_heads(root: Path) -> dict[str, str]:
    heads = {}
    for line in _git(root, "submodule", "status", "--recursive").splitlines():
        # Keep the first status character: '+' is a changed pin, '-' uninitialized.
        # _git strips the initial space for the first successfully initialized row.
        fields = line.split()
        if not fields:
            continue
        sha = fields[0]
        if sha.startswith(("+", "-", "U")):
            raise SetupError("Submodule pins are incomplete or mismatched: " + line)
        heads[fields[1]] = sha
    return heads


def _check_update_collisions(root: Path, target: str) -> None:
    """Inspect incoming files at every initialized repo boundary before checkout.

    Fetching a pinned object is safe here; checking it out is not. Git's default
    submodule checkout can replace ignored files that normal status omits.
    """
    added = _git(
        root,
        "diff",
        "--no-renames",
        "--name-only",
        "--diff-filter=A",
        "-z",
        "HEAD",
        target,
    )
    for relative in filter(None, added.split("\0")):
        path = root / relative
        if path.exists() or path.is_symlink():
            raise SetupError(
                f"The shared update would overwrite local content at {path}. "
                "Preserve it explicitly before updating; ignored files also count."
            )
    for row in filter(None, _git(root, "ls-tree", "-rz", target).split("\0")):
        metadata, _, relative = row.partition("\t")
        mode, _, sha = metadata.split()
        if mode != "160000":
            continue
        child = root / relative
        if not (child / ".git").exists():
            # Refuse before the parent advances, rather than discovering this
            # collision later when submodule initialization tries to clone here.
            if child.exists() and any(child.iterdir()):
                raise SetupError(
                    f"Uninitialized submodule contains local content: {child}"
                )
            continue
        _require_clean(child)
        if _git(child, "rev-parse", "HEAD") == sha:
            continue
        available = subprocess.run(
            ["git", "-C", str(child), "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True,
            check=False,
        )
        if available.returncode:
            _git(child, "fetch", "--no-recurse-submodules", "origin", sha)
        _check_update_collisions(child, sha)


def update_checkout(
    root: Path,
    *,
    expected_origin: str = SHARED_ORIGIN,
    check_only: bool = False,
) -> dict[str, Any]:
    """Fast-forward a clean shared main, then use only its recorded target pins.

    This deliberately does not switch branches, merge local work, modify data,
    build components, or claim that the running application has been updated.
    """
    root = root.resolve()
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise SetupError("Run the update from the shared project's repository root.")
    if _origin_identity(_git(root, "remote", "get-url", "origin")) != _origin_identity(
        expected_origin
    ):
        raise SetupError(
            "origin is not the expected shared project; no update performed."
        )
    if _git(root, "branch", "--show-current") != "main":
        raise SetupError(
            "The evaluation updater requires a main checkout. Keep feature work in "
            "its own checkout; no branch was switched."
        )
    _require_clean(root)
    before = _git(root, "rev-parse", "HEAD")
    _git(
        root,
        "fetch",
        "--no-recurse-submodules",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
    )
    target = _git(root, "rev-parse", "refs/remotes/origin/main")
    local_count = int(_git(root, "rev-list", "--count", f"{target}..HEAD"))
    if local_count:
        raise SetupError(
            f"main has {local_count} local-only commits. Review them before updating; "
            "no reset, rebase, or merge was attempted."
        )
    # Recheck after the network operation in case someone edited during fetch.
    _require_clean(root)
    _check_update_collisions(root, target)
    if check_only:
        return {
            "status": "update_available" if before != target else "current",
            "before": before,
            "after": before,
            "target": target,
            "applied": False,
        }
    _git(root, "-c", "submodule.recurse=false", "merge", "--ff-only", target)
    try:
        _git(root, "submodule", "sync", "--recursive")
        _git(root, "submodule", "update", "--init", "--recursive")
        heads = _submodule_heads(root)
        _require_clean(root)
    except SetupError as error:
        raise SetupError(
            f"The parent checkout is now {target}, but target initialization is "
            "incomplete. Do not start the environment. Inspect git status and "
            "submodule status, preserve any local work, then finish "
            "'git submodule update --init --recursive' without --force and rerun "
            f"the updater. Details: {error}"
        ) from error
    return {
        "status": "updated" if before != target else "current",
        "before": before,
        "after": _git(root, "rev-parse", "HEAD"),
        "target": target,
        "submodules": heads,
        "applied": True,
    }


def verify_baseline(baseline: Path) -> dict[str, Any]:
    try:
        source, issues = verify_dump(
            baseline, Path(f"{baseline}.provenance.json"), require_portable=True
        )
    except (ValueError, OSError, TypeError, AttributeError) as error:
        raise SetupError(f"Cannot verify evaluation baseline: {error}") from error
    if issues:
        raise SetupError("Cannot restore evaluation baseline: " + "; ".join(issues))
    return source


def prepare_data(
    root: Path,
    *,
    reset: bool = False,
    baseline: Path | None = None,
    database: str = "openmrs",
    run: Callable[[list[str]], Any],
) -> dict[str, Any]:
    """Preserve by default; an explicit reset uses existing dump/seed/index scripts.

    The caller must establish ownership/readiness of the local stack before this
    function. This function never starts another deployment or deletes volumes.
    """
    if not reset:
        return {"action": "preserve"}
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", database):
        raise SetupError("Invalid local database name.")
    baseline = (
        baseline or root / "artifacts/demo-data/refapp_28_demo.sql.gz"
    ).resolve()
    source = verify_baseline(baseline)

    directory = root / "artifacts/evaluation-setup/backups"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = directory / f"{stamp}-{uuid4().hex[:8]}.sql.gz"
    run(["docker", "stop", "harness-openmrs-backend"])
    try:
        mask = os.umask(0o077)
        try:
            run(
                [
                    "bash",
                    "scripts/dump-loaded.sh",
                    "--source",
                    database,
                    "--include-module-state",
                    "--out",
                    str(backup),
                ]
            )
        finally:
            os.umask(mask)
        provenance, issues = verify_dump(
            backup, Path(f"{backup}.provenance.json"), require_full_backup=True
        )
        if issues:
            raise SetupError(
                "Full backup verification failed; the database was not reset."
            )
    except Exception:
        run(["docker", "start", "harness-openmrs-backend"])
        raise

    receipt = {
        "action": "reset_to_baseline",
        "status": "in_progress",
        "database": database,
        "backup": str(backup),
        "backup_sha256": provenance["output_sha256"],
        "baseline": str(baseline),
        "baseline_sha256": source["output_sha256"],
    }
    receipt_path = directory.parent / "data-reset.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    try:
        run(
            [
                "bash",
                "scripts/seed-local.sh",
                "--dump",
                str(baseline),
                "--target",
                database,
            ]
        )
        run(["bash", "scripts/querystore-configure.sh"])
        run(["make", "querystore-recreate-index", "ALLOW_QUERYSTORE_INDEX_RESET=1"])
    except Exception as error:
        receipt.update(
            status="failed",
            error="Restore or index rebuild failed; inspect the setup log.",
        )
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        raise SetupError(
            f"{error}. Do not retry blindly. Full backup retained at {backup}"
        ) from error
    receipt["status"] = "restored"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
