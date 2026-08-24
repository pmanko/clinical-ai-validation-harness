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


def tracked_files(root: Path = ROOT) -> list[tuple[str, int]]:
    """Every blob in the index, sized from git rather than from disk.

    Deliberately not `Path.stat()`: a file can be tracked and absent from the
    checkout, and an earlier version of this guard read the working tree, so it
    passed while four videos were still committed. What matters is what the
    repository carries, so ask git.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-s", "--", "."],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    entries = []
    for line in listing:
        meta, _, path = line.partition("\t")
        mode, blob, _stage = meta.split()
        # 160000 is a submodule gitlink: its "content" is a reference to
        # another repository's commit, not a blob whose bytes this repository
        # carries, so it is out of scope here. A symlink (120000) IS a blob in
        # this repository -- its target text -- and a tracked symlink is
        # exactly the arrangement this guard exists to catch (see module
        # docstring: "landing/media held symlinks specifically 'to avoid
        # committing duplicate binaries'"), so it stays in scope for the
        # suffix check below. Its blob size is the target string's length, not
        # the size of whatever it points to -- irrelevant here, since the
        # video check is a pure suffix match and never consults size.
        if mode == "160000":
            continue
        entries.append((path, blob))

    if not entries:
        return []
    sizes = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectsize)"],
        cwd=root,
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


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def test_guard_detects_a_tracked_video_a_video_symlink_and_an_oversized_binary(
    tmp_path,
):
    """Regression for the guard itself, in a disposable repository.

    A previous version of `tracked_files` excluded every symlink (mode
    120000) outright -- the exact arrangement the module docstring says this
    guard exists to catch, since landing/media once held symlinks "to avoid
    committing duplicate binaries". This proves all three offending shapes
    are caught by path, independent of the real repository's current state.
    """
    _git("init", "-q", cwd=tmp_path)

    (tmp_path / "clip.mp4").write_bytes(b"fake video bytes")

    media = tmp_path / "media"
    media.mkdir()
    (media / "alias.mp4").symlink_to("../clip.mp4")

    (tmp_path / "big.png").write_bytes(b"x" * (LARGE_BINARY_BYTES + 1))

    _git("add", "clip.mp4", "media/alias.mp4", "big.png", cwd=tmp_path)
    _git("commit", "-q", "-m", "fixture", cwd=tmp_path)

    files = tracked_files(tmp_path)

    videos = sorted(
        path for path, _ in files if Path(path).suffix.lower() in VIDEO_SUFFIXES
    )
    assert videos == ["clip.mp4", "media/alias.mp4"]

    oversized = [
        (path, size)
        for path, size in files
        if Path(path).suffix.lower() in BINARY_SUFFIXES and size > LARGE_BINARY_BYTES
    ]
    assert oversized == [("big.png", LARGE_BINARY_BYTES + 1)]
