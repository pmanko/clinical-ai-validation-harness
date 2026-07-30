#!/usr/bin/env python3
"""Write or verify source-bound provenance for a staged local build artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_identity(path: Path) -> dict[str, object]:
    if path.is_file():
        return {
            "kind": "file",
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
    if not path.is_dir():
        raise FileNotFoundError(path)
    files = [
        {
            "path": str(item.relative_to(path)),
            "sha256": _sha256(item),
            "size_bytes": item.stat().st_size,
        }
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "kind": "directory",
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": sum(int(item["size_bytes"]) for item in files),
        "files": files,
    }


def build_provenance(repo: Path, artifact: Path) -> dict[str, object]:
    repo = repo.resolve()
    artifact = artifact.resolve()
    identity = artifact_identity(artifact)
    return {
        "schema_version": "artifact_build_provenance.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": str(repo.relative_to(ROOT)),
        "source_commit": _git(repo, "rev-parse", "HEAD"),
        "source_tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "source_tree_clean": not bool(
            _git(repo, "status", "--porcelain", "--untracked-files=all")
        ),
        "artifact": str(artifact.relative_to(ROOT)),
        "artifact_kind": identity["kind"],
        "artifact_sha256": identity["sha256"],
        "artifact_size_bytes": identity["size_bytes"],
        **({"artifact_files": identity["files"]} if identity["kind"] == "directory" else {}),
    }


def verify_provenance(repo: Path, artifact: Path, manifest: Path) -> bool:
    if not artifact.exists() or not manifest.is_file():
        return False
    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    current = build_provenance(repo, artifact)
    return (
        recorded.get("schema_version") == "artifact_build_provenance.v1"
        and recorded.get("source_tree_clean") is True
        and current["source_tree_clean"] is True
        and recorded.get("source_commit") == current["source_commit"]
        and recorded.get("source_tree") == current["source_tree"]
        and recorded.get("artifact_kind") == current["artifact_kind"]
        and recorded.get("artifact_sha256") == current["artifact_sha256"]
        and recorded.get("artifact_size_bytes") == current["artifact_size_bytes"]
        and recorded.get("artifact_files") == current.get("artifact_files")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "verify"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    repo = (ROOT / args.repo).resolve() if not args.repo.is_absolute() else args.repo
    artifact = (
        (ROOT / args.artifact).resolve()
        if not args.artifact.is_absolute()
        else args.artifact
    )
    manifest = (
        (ROOT / args.manifest).resolve()
        if not args.manifest.is_absolute()
        else args.manifest
    )
    if args.mode == "verify":
        return 0 if verify_provenance(repo, artifact, manifest) else 1

    result = build_provenance(repo, artifact)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
