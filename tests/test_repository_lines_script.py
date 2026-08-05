from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-repository-lines.sh"
OPENMRS_REPOS = ("chartsearchai", "chartsearchai-esm", "querystore")
OTHER_REPOS = ("med-agent-hub", "catalyst", "openmrs_chatbot")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    marker = repo / "marker.txt"
    marker.write_text(message, encoding="utf-8")
    _git(repo, "add", "marker.txt")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "harness"
    (root / "scripts").mkdir(parents=True)
    (root / "targets").mkdir()
    shutil.copy2(SCRIPT, root / "scripts" / SCRIPT.name)
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.test")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "scripts")
    _git(root, "commit", "-m", "add repository check")

    for name in (*OPENMRS_REPOS, *OTHER_REPOS):
        repo = root / "targets" / name
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "test@example.test")
        _git(repo, "config", "user.name", "Test")
        head = _commit(repo, f"{name} source")
        remote_ref = (
            "refs/remotes/origin/harness-integration"
            if name in OPENMRS_REPOS
            else "refs/remotes/origin/main"
        )
        _git(repo, "update-ref", remote_ref, head)
        _git(
            root,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{head},targets/{name}",
        )
    _git(root, "commit", "-m", "pin source lines")
    _git(root, "update-ref", "refs/remotes/origin/main", _git(root, "rev-parse", "HEAD"))
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / "scripts" / SCRIPT.name), *args],
        env={**os.environ, "HARNESS_ROOT": str(root)},
        capture_output=True,
        text=True,
    )


def test_repository_check_accepts_owned_main_and_exact_openmrs_integration(tmp_path):
    root = _fixture(tmp_path)

    result = _run(root)

    assert result.returncode == 0, result.stderr
    assert "approved ownership policy" in result.stdout


def test_repository_check_allows_only_the_harness_pull_request_branch(tmp_path):
    root = _fixture(tmp_path)
    _commit(root, "pull request change")
    _git(
        root,
        "update-ref",
        "refs/remotes/origin/codex/test-followup",
        _git(root, "rev-parse", "HEAD"),
    )

    strict = _run(root)
    pull_request = _run(root, "--allow-harness-branch")

    assert strict.returncode != 0
    assert "validation harness HEAD has not been merged" in strict.stderr
    assert pull_request.returncode == 0, pull_request.stderr


def test_repository_check_rejects_unmerged_hub_and_stale_openmrs_head(tmp_path):
    root = _fixture(tmp_path)
    hub = root / "targets" / "med-agent-hub"
    unmerged_hub = _commit(hub, "unmerged hub change")
    _git(
        hub,
        "update-ref",
        "refs/remotes/origin/codex/test-followup",
        unmerged_hub,
    )
    _git(
        root,
        "update-index",
        "--cacheinfo",
        f"160000,{unmerged_hub},targets/med-agent-hub",
    )
    _git(root, "commit", "-m", "pin unmerged hub")
    _git(
        root,
        "update-ref",
        "refs/remotes/origin/codex/test-followup",
        _git(root, "rev-parse", "HEAD"),
    )

    result = _run(root, "--allow-harness-branch")
    assert result.returncode != 0
    assert "med-agent-hub HEAD has not been merged" in result.stderr

    _git(hub, "update-ref", "refs/remotes/origin/main", unmerged_hub)
    querystore = root / "targets" / "querystore"
    unpublished_querystore = _commit(querystore, "unpublished QueryStore change")
    _git(
        querystore,
        "update-ref",
        "refs/remotes/origin/feat/unpublished",
        unpublished_querystore,
    )
    _git(
        root,
        "update-index",
        "--cacheinfo",
        f"160000,{unpublished_querystore},targets/querystore",
    )
    _git(root, "commit", "-m", "pin unpublished QueryStore")
    _git(
        root,
        "update-ref",
        "refs/remotes/origin/codex/test-followup",
        _git(root, "rev-parse", "HEAD"),
    )
    result = _run(root, "--allow-harness-branch")
    assert result.returncode != 0
    assert "QueryStore does not match origin/harness-integration" in result.stderr


def test_publication_check_uses_paginated_exact_head_lookup_and_readiness():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "gh api" in script
    assert "--paginate" in script
    assert "--slurp" not in script
    assert "head=pmanko%3Aharness-integration" in script
    assert "--limit 100" not in script
    assert "isDraft,mergeable,statusCheckRollup" in script
    assert '"MERGEABLE"' in script
    assert "has no completed checks" in script


def test_harness_ci_uses_the_repository_node_action_major():
    workflow = (ROOT / ".github" / "workflows" / "harness-ci.yml").read_text(
        encoding="utf-8"
    )

    assert "actions/setup-node@v4" in workflow
    assert "actions/setup-node@v6" not in workflow


def test_publication_make_target_is_described_as_pull_request_safe():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "Network-backed PR-safe publication check" in makefile
