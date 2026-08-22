"""No video in git, and no new large binaries either.

A recording re-cut after every UI change is a new blob, and git keeps every
one of them forever: the repository was carrying ~11 MB of MP4 in a 40 MB pack
before these moved to the demo host, with more queued in an open PR. The pages
link to https://catalyst.openelis-global.org/media/<name> instead, which the
deploy writes and Caddy serves.

This guard exists because the previous arrangement was also deliberate, and it
still drifted -- landing/media held symlinks specifically "to avoid committing
duplicate binaries", which kept the count down but not the bytes out.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv"}
# Small hand-made page assets are fine; renderer output and screen captures are
# what grow without bound. 400 KB clears every poster in landing/media today.
LARGE_BINARY_BYTES = 400 * 1024
BINARY_SUFFIXES = VIDEO_SUFFIXES | {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}


def tracked_files() -> list[tuple[str, int]]:
    """Every blob in the index, sized from git rather than from disk.

    Deliberately not `Path.stat()`: a file can be tracked and absent from the
    checkout, and an earlier version of this guard read the working tree, so it
    passed while four videos were still committed. What matters is what the
    repository carries, so ask git.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-s", "--", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    entries = []
    for line in listing:
        meta, _, path = line.partition("\t")
        mode, blob, _stage = meta.split()
        # 160000 is a submodule gitlink; 120000 a symlink. Neither is a blob
        # whose bytes live in this repository.
        if mode in {"160000", "120000"}:
            continue
        entries.append((path, blob))

    if not entries:
        return []
    sizes = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectsize)"],
        cwd=ROOT,
        input="\n".join(blob for _, blob in entries) + "\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [
        (path, int(size)) for (path, _), size in zip(entries, sizes)
    ]


def test_no_video_files_are_tracked():
    videos = [
        path
        for path, _ in tracked_files()
        if Path(path).suffix.lower() in VIDEO_SUFFIXES
    ]
    assert videos == [], (
        "Video belongs on the demo host, not in git — upload it to "
        "targets/catalyst/runtime/media/ and link to "
        "https://catalyst.openelis-global.org/media/<name>. Offending files: "
        f"{videos}"
    )


def test_no_oversized_binaries_are_tracked():
    oversized = [
        (path, size)
        for path, size in tracked_files()
        if Path(path).suffix.lower() in BINARY_SUFFIXES and size > LARGE_BINARY_BYTES
    ]
    assert oversized == [], (
        "Large binaries accumulate in history forever. Host it and link to it, "
        f"or shrink it below {LARGE_BINARY_BYTES // 1024} KB. Offending files: "
        f"{oversized}"
    )
