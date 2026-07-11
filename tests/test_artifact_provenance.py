from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "artifact_provenance", ROOT / "scripts" / "artifact-provenance.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_provenance_binds_artifact_to_a_clean_source_commit(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "source.txt").write_text("source\n", encoding="utf-8")
    _git(repo, "add", "source.txt")
    _git(repo, "commit", "-qm", "initial")
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"built output")
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)

    provenance = MODULE.build_provenance(repo, artifact)
    manifest = tmp_path / "artifact.provenance.json"
    manifest.write_text(json.dumps(provenance), encoding="utf-8")

    assert MODULE.verify_provenance(repo, artifact, manifest)

    artifact.write_bytes(b"different output")
    assert not MODULE.verify_provenance(repo, artifact, manifest)


def test_provenance_rejects_a_dirty_source_tree(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "source.txt").write_text("source\n", encoding="utf-8")
    _git(repo, "add", "source.txt")
    _git(repo, "commit", "-qm", "initial")
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"built output")
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    provenance = MODULE.build_provenance(repo, artifact)
    manifest = tmp_path / "artifact.provenance.json"
    manifest.write_text(json.dumps(provenance), encoding="utf-8")

    (repo / "source.txt").write_text("dirty\n", encoding="utf-8")

    assert not MODULE.verify_provenance(repo, artifact, manifest)


def test_directory_provenance_binds_every_staged_asset(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "source.txt").write_text("source\n", encoding="utf-8")
    _git(repo, "add", "source.txt")
    _git(repo, "commit", "-qm", "initial")
    artifact = tmp_path / "bundle"
    artifact.mkdir()
    (artifact / "main.js").write_text("main", encoding="utf-8")
    (artifact / "chunk.js").write_text("chunk", encoding="utf-8")
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)

    provenance = MODULE.build_provenance(repo, artifact)
    manifest = tmp_path / "bundle.provenance.json"
    manifest.write_text(json.dumps(provenance), encoding="utf-8")

    assert provenance["artifact_kind"] == "directory"
    assert [item["path"] for item in provenance["artifact_files"]] == [
        "chunk.js",
        "main.js",
    ]
    assert MODULE.verify_provenance(repo, artifact, manifest)

    (artifact / "chunk.js").write_text("changed", encoding="utf-8")
    assert not MODULE.verify_provenance(repo, artifact, manifest)
