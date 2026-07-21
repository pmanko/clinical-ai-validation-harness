from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
