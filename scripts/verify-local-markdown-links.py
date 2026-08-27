#!/usr/bin/env python3
"""Report missing local file targets in current Markdown documents."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


LINK = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
REMOTE_SCHEMES = {"data", "http", "https", "mailto"}


def repository_markdown(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    files = [
        root / line
        for line in result.stdout.splitlines()
        if line and (root / line).is_file()
    ]
    catalyst = root / "targets" / "catalyst"
    if catalyst.is_dir():
        nested = subprocess.run(
            [
                "git",
                "-C",
                str(catalyst),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "*.md",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if nested.returncode == 0:
            files.extend(
                catalyst / line
                for line in nested.stdout.splitlines()
                if line and (catalyst / line).is_file()
            )
    return files


def gitlinks(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        metadata, separator, name = line.partition("\t")
        if separator and metadata.startswith("160000 "):
            paths.append((root / name).resolve())
    return paths


def belongs_to(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


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
    submodules = gitlinks(root)
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
                # A clean checkout may not initialize every git submodule. The
                # parent repository can verify the gitlink, but not files inside
                # an absent checkout.
                if any(belongs_to(target, submodule) for submodule in submodules):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{display_path(source, root)}:{line}: missing {relative}")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"markdown links: OK ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
