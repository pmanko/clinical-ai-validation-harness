from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_jsonl(path: Path | str, row: dict[str, Any]) -> None:
    """Append one compact JSON line to a JSONL file, creating parent dirs.

    The single writer for every run-stream file across validation families
    (harness/validate + harness/catalyst) — one plumbing, not one per family.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def read_jsonl(path: Path | str, *, strict: bool = True) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of objects.

    Missing files return ``[]``. Blank lines are skipped. With ``strict=True``
    (default), malformed JSON raises ``ValueError`` naming the path and 1-based
    line number. With ``strict=False``, malformed lines are skipped (dashboard
    live-tailer only).
    """
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except json.JSONDecodeError as exc:
            if strict:
                raise ValueError(f"{p}: line {lineno}: {exc.msg}") from exc
    return rows
