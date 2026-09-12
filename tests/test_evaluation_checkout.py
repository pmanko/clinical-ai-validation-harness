"""Source-update safety tested with real disposable Git repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness.evaluation_setup import SetupError, update_checkout


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def commit(root: Path, text: str) -> str:
    (root / "tracked.txt").write_text(text)
    git(root, "add", "tracked.txt")
    git(root, "commit", "-m", text)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repositories(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "empty-git-config"))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Setup test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "setup@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Setup test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "setup@example.invalid")
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    remote = tmp_path / "shared.git"
    remote.mkdir()
    git(remote, "init", "--bare", "--initial-branch=main")
    publisher = tmp_path / "publisher"
    git(tmp_path, "clone", str(remote), str(publisher))
    commit(publisher, "baseline")
    git(publisher, "push", "origin", "main")
    ross = tmp_path / "ross"
    git(tmp_path, "clone", str(remote), str(ross))
    return publisher, ross, remote


def test_fast_forward_and_repeated_update(repositories):
    publisher, ross, remote = repositories
    before = git(ross, "rev-parse", "HEAD")
    after = commit(publisher, "shared update")
    git(publisher, "push", "origin", "main")

    result = update_checkout(ross, expected_origin=str(remote))

    assert result["before"] == before
    assert result["after"] == after
    assert result["status"] == "updated"
    assert (ross / "tracked.txt").read_text() == "shared update"
    assert update_checkout(ross, expected_origin=str(remote))["status"] == "current"


@pytest.mark.parametrize("dirty", ["tracked", "untracked", "staged"])
def test_local_work_is_never_overwritten(repositories, dirty):
    publisher, ross, remote = repositories
    before = git(ross, "rev-parse", "HEAD")
    path = ross / ("notes.txt" if dirty == "untracked" else "tracked.txt")
    path.write_text("Ross's work")
    if dirty == "staged":
        git(ross, "add", "tracked.txt")
    commit(publisher, "shared update")
    git(publisher, "push", "origin", "main")

    with pytest.raises(SetupError, match="local changes"):
        update_checkout(ross, expected_origin=str(remote))

    assert path.read_text() == "Ross's work"
    assert git(ross, "rev-parse", "HEAD") == before


@pytest.mark.parametrize("shared_changed", [False, True])
def test_local_commits_do_not_get_reset_or_merged(repositories, shared_changed):
    publisher, ross, remote = repositories
    before = commit(ross, "local commit")
    if shared_changed:
        commit(publisher, "shared update")
        git(publisher, "push", "origin", "main")

    with pytest.raises(SetupError, match="local-only commits"):
        update_checkout(ross, expected_origin=str(remote))

    assert git(ross, "rev-parse", "HEAD") == before


def test_feature_branch_is_not_silently_switched(repositories):
    _, ross, remote = repositories
    git(ross, "switch", "-c", "my-work")
    with pytest.raises(SetupError, match="main"):
        update_checkout(ross, expected_origin=str(remote))
    assert git(ross, "branch", "--show-current") == "my-work"


def test_wrong_origin_is_rejected(repositories):
    _, ross, _ = repositories
    with pytest.raises(SetupError, match="origin"):
        update_checkout(ross)


def test_check_fetches_but_does_not_change_checkout(repositories):
    publisher, ross, remote = repositories
    before = git(ross, "rev-parse", "HEAD")
    after = commit(publisher, "shared update")
    git(publisher, "push", "origin", "main")

    result = update_checkout(ross, expected_origin=str(remote), check_only=True)

    assert result["target"] == after
    assert result["after"] == before
    assert result["status"] == "update_available"


def test_submodules_use_parent_pin_not_latest_branch(repositories, tmp_path):
    publisher, ross, remote = repositories
    child = tmp_path / "child"
    child.mkdir()
    git(child, "init", "--initial-branch=main")
    pinned = commit(child, "pinned version")
    git(publisher, "submodule", "add", str(child), "targets/component")
    git(publisher, "commit", "-am", "pin component")
    git(publisher, "push", "origin", "main")
    commit(child, "newer untested version")

    result = update_checkout(ross, expected_origin=str(remote))

    assert git(ross / "targets/component", "rev-parse", "HEAD") == pinned
    assert result["submodules"]["targets/component"] == pinned


def test_dirty_submodule_refuses_update(repositories, tmp_path):
    publisher, ross, remote = repositories
    child = tmp_path / "child"
    child.mkdir()
    git(child, "init", "--initial-branch=main")
    commit(child, "pinned version")
    git(publisher, "submodule", "add", str(child), "targets/component")
    git(publisher, "commit", "-am", "pin component")
    git(publisher, "push", "origin", "main")
    update_checkout(ross, expected_origin=str(remote))
    path = ross / "targets/component/tracked.txt"
    path.write_text("local module change")
    before = git(ross, "rev-parse", "HEAD")

    with pytest.raises(SetupError, match="local changes"):
        update_checkout(ross, expected_origin=str(remote))

    assert path.read_text() == "local module change"
    assert git(ross, "rev-parse", "HEAD") == before


def test_incoming_tracked_file_does_not_overwrite_ignored_local_config(repositories):
    publisher, ross, remote = repositories
    (publisher / ".gitignore").write_text("local.env\n")
    git(publisher, "add", ".gitignore")
    git(publisher, "commit", "-m", "ignore local configuration")
    git(publisher, "push", "origin", "main")
    update_checkout(ross, expected_origin=str(remote))
    config = ross / "local.env"
    config.write_text("Ross's private local configuration")
    (publisher / "local.env").write_text("incoming default")
    git(publisher, "add", "-f", "local.env")
    git(publisher, "commit", "-m", "incoming configuration")
    git(publisher, "push", "origin", "main")
    before = git(ross, "rev-parse", "HEAD")

    with pytest.raises(SetupError, match="overwrite local"):
        update_checkout(ross, expected_origin=str(remote))

    assert config.read_text() == "Ross's private local configuration"
    assert git(ross, "rev-parse", "HEAD") == before


def test_fetch_failure_never_changes_checkout(repositories):
    _, ross, remote = repositories
    before = git(ross, "rev-parse", "HEAD")
    unavailable = remote.parent / "missing.git"
    git(ross, "remote", "set-url", "origin", str(unavailable))
    with pytest.raises(SetupError, match="fetch failed"):
        update_checkout(ross, expected_origin=str(unavailable))
    assert git(ross, "rev-parse", "HEAD") == before


@pytest.mark.parametrize("collision", [True, False])
def test_submodule_ignored_configuration_is_preserved(
    repositories, tmp_path, collision
):
    publisher, local, remote = repositories
    child = tmp_path / "child"
    child.mkdir()
    git(child, "init", "--initial-branch=main")
    (child / ".gitignore").write_text("local.env\n")
    git(child, "add", ".gitignore")
    original = commit(child, "child baseline")
    git(publisher, "submodule", "add", str(child), "targets/component")
    git(publisher, "commit", "-am", "pin child")
    git(publisher, "push", "origin", "main")
    update_checkout(local, expected_origin=str(remote))
    private = local / "targets/component/local.env"
    private.write_text("private local settings")
    if collision:
        (child / "local.env").write_text("incoming defaults")
        git(child, "add", "-f", "local.env")
    updated = commit(child, "child update")
    git(publisher / "targets/component", "fetch", "origin")
    git(publisher / "targets/component", "checkout", updated)
    git(publisher, "commit", "-am", "update child pin")
    git(publisher, "push", "origin", "main")
    before = git(local, "rev-parse", "HEAD")

    if collision:
        with pytest.raises(SetupError, match="overwrite local"):
            update_checkout(local, expected_origin=str(remote))
        assert git(local, "rev-parse", "HEAD") == before
        assert git(local / "targets/component", "rev-parse", "HEAD") == original
    else:
        update_checkout(local, expected_origin=str(remote))
        assert git(local / "targets/component", "rev-parse", "HEAD") == updated
    assert private.read_text() == "private local settings"
