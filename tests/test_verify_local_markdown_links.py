"""In-process behavior of scripts/verify-local-markdown-links.py.

The docs guard runs the checker as a subprocess, which coverage cannot
trace; these tests import it and exercise the same contract directly.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "verify-local-markdown-links.py"
)
_SPEC = importlib.util.spec_from_file_location("verify_local_markdown_links", SCRIPT)
assert _SPEC and _SPEC.loader
links = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(links)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_link_targets_parse_like_markdown() -> None:
    assert links.target_path("docs/spec.md") == "docs/spec.md"
    assert links.target_path("spec.md#section") == "spec.md"
    assert links.target_path('spec.md "A title"') == "spec.md"
    assert links.target_path("<my file.md>") == "my file.md"
    assert links.target_path("a%20b.md") == "a b.md"
    # Remote, anchor-only, absolute, and templated targets are not local files.
    assert links.target_path("https://example.org/x.md") is None
    assert links.target_path("mailto:a@example.org") is None
    assert links.target_path("data:image/png;base64,xyz") is None
    assert links.target_path("#anchor") is None
    assert links.target_path("/absolute/path.md") is None
    assert links.target_path("{placeholder}/spec.md") is None


def test_good_links_pass_and_report_the_file_count(tmp_path, capsys, monkeypatch) -> None:
    target = tmp_path / "target.md"
    target.write_text("# t\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("see [t](target.md) and [ext](https://example.org)\n", encoding="utf-8")
    monkeypatch.setattr(links.sys, "argv", ["verify", str(source)])
    assert links.main() == 0
    assert "markdown links: OK (1 files)" in capsys.readouterr().out


def test_broken_local_link_names_file_and_line(tmp_path, capsys, monkeypatch) -> None:
    source = tmp_path / "doc.md"
    source.write_text("intro\n\nsee [gone](missing/file.md)\n", encoding="utf-8")
    monkeypatch.setattr(links.sys, "argv", ["verify", str(source)])
    assert links.main() == 1
    err = capsys.readouterr().err
    assert "doc.md:3: missing missing/file.md" in err


def test_missing_source_file_is_itself_a_failure(tmp_path, capsys, monkeypatch) -> None:
    ghost = tmp_path / "ghost.md"
    monkeypatch.setattr(links.sys, "argv", ["verify", str(ghost)])
    assert links.main() == 1
    assert "missing Markdown source" in capsys.readouterr().err


def test_targets_inside_absent_submodules_are_not_failures(tmp_path, capsys, monkeypatch) -> None:
    # A clean checkout may leave a gitlink uninitialized; a link into one is
    # not evidence of a broken document.
    root = SCRIPT.resolve().parents[1]
    submodules = links.gitlinks(root)
    assert submodules, "harness repo is expected to carry gitlinks"
    ghost_target = submodules[0] / "not-checked-out" / "ghost.md"
    assert not ghost_target.exists()
    relative = os.path.relpath(ghost_target, start=tmp_path)
    source = tmp_path / "doc.md"
    source.write_text(f"see [ghost]({relative})\n", encoding="utf-8")
    monkeypatch.setattr(links.sys, "argv", ["verify", str(source)])
    assert links.main() == 0
    assert "OK (1 files)" in capsys.readouterr().out


def test_repository_markdown_lists_tracked_untracked_and_nested_catalyst(tmp_path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "tracked.md").write_text("t\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.md")
    (tmp_path / "untracked.md").write_text("u\n", encoding="utf-8")
    nested = tmp_path / "targets" / "catalyst"
    nested.mkdir(parents=True)
    _git(nested, "init", "-q")
    (nested / "inner.md").write_text("i\n", encoding="utf-8")
    _git(nested, "add", "inner.md")

    found = {p.relative_to(tmp_path).as_posix() for p in links.repository_markdown(tmp_path)}
    assert {"tracked.md", "untracked.md", "targets/catalyst/inner.md"} <= found


def test_gitlinks_returns_only_gitlink_entries(tmp_path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "plain.md").write_text("p\n", encoding="utf-8")
    _git(tmp_path, "add", "plain.md")
    _git(
        tmp_path,
        "update-index",
        "--add",
        "--cacheinfo",
        "160000,1234567890123456789012345678901234567890,vendor",
    )
    found = links.gitlinks(tmp_path)
    assert (tmp_path / "vendor").resolve() in [p for p in found]
    assert all(p.name != "plain.md" for p in found)
