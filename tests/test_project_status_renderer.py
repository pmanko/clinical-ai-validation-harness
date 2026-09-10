import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = ROOT / "specs/artifacts/project-status/render.py"
SPEC = importlib.util.spec_from_file_location("project_status_renderer", RENDERER_PATH)
assert SPEC and SPEC.loader
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    """Use actual committed files; untracked/ignored presence is not portability."""
    directory = tmp_path / "specs/artifacts/project-status"
    directory.mkdir(parents=True)
    files = [
        "README.md",
        "specs/catalyst-program-roadmap.md",
        "specs/artifacts/project-status/reports/snapshot.md",
        "specs/artifacts/project-status/evidence/check.json",
        "specs/artifacts/project-status/artifacts.md",
        "specs/artifacts/project-status/artifacts.json",
        "specs/artifacts/project-status/exports/artifacts.csv",
    ]
    for relative in files:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Example\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("/artifacts/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", ".gitignore", *files], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "Fixture",
        ],
        check=True,
    )
    monkeypatch.setattr(RENDERER, "REPOSITORY", tmp_path)
    monkeypatch.setattr(RENDERER, "DIRECTORY", directory)
    return tmp_path, directory


def test_repository_line_reference_uses_a_markdown_fragment(repository):
    assert RENDERER.link("specs/catalyst-program-roadmap.md:11", "roadmap") == (
        "[roadmap](<../../catalyst-program-roadmap.md#L11>)"
    )


@pytest.mark.parametrize("labeled", [False, True])
def test_ignored_evidence_stays_plain_when_present_or_absent(repository, labeled):
    root, _ = repository
    path = "artifacts/not-present/status.json"
    value = {"path": path, "label": "Evidence"} if labeled else path
    cold = RENDERER.cell(value, "path")
    target = root / path
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    assert RENDERER.cell(value, "path") == cold
    assert "](" not in cold
    assert path in cold
    if labeled:
        assert "Evidence" in cold


@pytest.mark.parametrize(
    "target, expected",
    [
        ("reports/snapshot.md", "reports/snapshot.md"),
        ("evidence/check.json:2", "evidence/check.json#L2"),
        ("./reports/snapshot.md", "reports/snapshot.md"),
        ("README.md", "../../../README.md"),
        ("README.md:9", "../../../README.md#L9"),
        ("artifacts.md", "artifacts.md"),
    ],
)
def test_string_and_labeled_targets_resolve_from_the_same_base(
    repository, target, expected
):
    assert f"(<{expected}>)" in RENDERER.cell(target, "source")
    assert (
        RENDERER.cell({"path": target, "label": "Evidence"})
        == f"[Evidence](<{expected}>)"
    )


def test_external_and_uncommitted_files_are_plain_references(repository, tmp_path):
    root, _ = repository
    (root / "new.md").write_text("not committed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "new.md"], check=True)
    for target in (
        "new.md",
        str(tmp_path.parent / "outside.md"),
        "file:///tmp/private.txt",
    ):
        rendered = RENDERER.cell({"path": target, "label": "Evidence"})
        assert "](" not in rendered
        assert "Evidence" in rendered


def test_explicit_web_links_preserve_the_url(repository):
    assert RENDERER.cell(
        {"url": "https://example.org/report#L2", "label": "Report"}
    ) == ("[Report](<https://example.org/report#L2>)")


def test_actual_rendered_inventory_passes_the_markdown_link_checker(repository):
    _, directory = repository
    rows = [
        {"id": "report", "title": "Report", "path": "reports/snapshot.md"},
        {
            "id": "source",
            "title": "Source",
            "path": "specs/catalyst-program-roadmap.md:11",
        },
        {"id": "runtime", "title": "Runtime", "path": "artifacts/absent.json"},
    ]
    output = directory / "artifacts.md"
    output.write_text(RENDERER.markdown("artifacts", {}, rows), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify-local-markdown-links.py"),
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
