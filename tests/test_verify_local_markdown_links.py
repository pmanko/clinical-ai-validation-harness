"""Filesystem-only behavior of scripts/verify-local-markdown-links.py."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "verify-local-markdown-links.py"
)
_SPEC = importlib.util.spec_from_file_location("verify_local_markdown_links", SCRIPT)
assert _SPEC and _SPEC.loader
links = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(links)


@pytest.fixture(autouse=True)
def forbid_process_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("link validation must not invoke Git or other processes")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


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


def test_missing_product_link_is_not_exempted_by_git_metadata(tmp_path, capsys, monkeypatch) -> None:
    (tmp_path / ".gitmodules").write_text(
        '[submodule "catalyst"]\n\tpath = targets/catalyst\n', encoding="utf-8"
    )
    source = tmp_path / "README.md"
    source.write_text("[product](targets/catalyst/docs/specification.md)\n", encoding="utf-8")
    monkeypatch.setattr(links.sys, "argv", ["verify", str(source)])
    assert links.main() == 1
    assert "missing targets/catalyst/docs/specification.md" in capsys.readouterr().err


def test_existing_relative_link_outside_harness_resolves(tmp_path, capsys, monkeypatch) -> None:
    product = tmp_path / "product"
    product.mkdir()
    (product / "contract.md").write_text("# Contract\n", encoding="utf-8")
    harness = tmp_path / "harness"
    harness.mkdir()
    source = harness / "README.md"
    source.write_text("[contract](../product/contract.md#api)\n", encoding="utf-8")
    monkeypatch.setattr(links.sys, "argv", ["verify", str(source)])
    assert links.main() == 0


def test_repository_markdown_discovers_sources_without_git_and_skips_outputs(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# Harness\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n", encoding="utf-8")
    for relative in (".venv", "node_modules", "artifacts/run", "logs", "targets/catalyst"):
        generated = tmp_path / relative
        generated.mkdir(parents=True)
        (generated / "ignored.md").write_text("[broken](absent.md)\n", encoding="utf-8")
    independent = tmp_path / "other-product"
    independent.mkdir()
    (independent / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    (independent / "README.md").write_text("# Product\n", encoding="utf-8")

    metadata = tmp_path / "specs" / "artifacts" / "planning"
    metadata.mkdir(parents=True)
    (metadata / "metadata.md").write_text("# Metadata\n", encoding="utf-8")
    curated = tmp_path / "artifacts" / "share"
    curated.mkdir()
    (curated / "README.md").write_text("# Curated handoff\n", encoding="utf-8")

    found = [p.relative_to(tmp_path).as_posix() for p in links.repository_markdown(tmp_path)]
    assert found == [
        "README.md", "artifacts/share/README.md", "docs/guide.md",
        "specs/artifacts/planning/metadata.md",
    ]


def test_default_discovery_checks_an_archive_without_git(tmp_path, capsys, monkeypatch) -> None:
    script = tmp_path / "scripts" / SCRIPT.name
    monkeypatch.setattr(links, "__file__", str(script))
    monkeypatch.setattr(links.sys, "argv", ["verify"])
    (tmp_path / "README.md").write_text("[guide](guide.md)\n", encoding="utf-8")
    (tmp_path / "guide.md").write_text("# Guide\n", encoding="utf-8")
    assert not (tmp_path / ".git").exists()
    assert links.main() == 0
    assert "OK (2 files)" in capsys.readouterr().out

    (tmp_path / "guide.md").unlink()
    assert links.main() == 1
    assert "README.md:1: missing guide.md" in capsys.readouterr().err
