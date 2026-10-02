#!/usr/bin/env python3
"""Report missing local file targets in current Markdown documents."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


LINK = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
REMOTE_SCHEMES = {"data", "http", "https", "mailto"}


# Discover authored documentation from the filesystem, including source archives
# without Git metadata. Generated output and independently owned checkouts are
# not default source documents; explicitly supplied files are still checked.
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "build", "dist", "target", "tdd-guard",
}


def repository_markdown(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory, directories, filenames in os.walk(root):
        parent = Path(directory)
        directories[:] = sorted(
            name for name in directories
            if name not in SKIP_DIRS
            and not (parent == root and name in {"artifacts", "logs", "data", "targets"})
            and not (parent / name / ".git").exists()
        )
        files.extend(parent / name for name in filenames if name.endswith(".md"))
    # The share handoff is curated documentation, not generated run output.
    files.extend((root / "artifacts" / "share").glob("*.md"))
    return sorted(files)


def display_path(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def target_path(raw: str) -> str | None:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    else:
        value = value.split(maxsplit=1)[0]

    parsed = urlsplit(value)
    if parsed.scheme.lower() in REMOTE_SCHEMES or value.startswith(("#", "/")):
        return None
    if not parsed.path or "{" in parsed.path:
        return None
    return unquote(parsed.path)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    files = [Path(arg).resolve() for arg in sys.argv[1:]] or repository_markdown(root)
    failures: list[str] = []

    for source in files:
        if not source.is_file():
            failures.append(f"missing Markdown source: {source}")
            continue
        text = source.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            relative = target_path(match.group(1))
            if relative is None:
                continue
            target = (source.parent / relative).resolve()
            if not target.exists():
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{display_path(source, root)}:{line}: missing {relative}")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"markdown links: OK ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
