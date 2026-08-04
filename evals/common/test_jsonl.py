from __future__ import annotations

from pathlib import Path

import pytest

from harness.common.jsonl import read_jsonl


def test_missing_file_returns_empty_list(tmp_path: Path) -> None:
    assert read_jsonl(tmp_path / "missing.jsonl") == []


def test_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text('{"a": 1}\n\n{"b": 2}\n', encoding="utf-8")
    assert read_jsonl(path) == [{"a": 1}, {"b": 2}]


def test_strict_raises_value_error_with_path_and_line(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"ok": true}\n{not-json}\n', encoding="utf-8")
    with pytest.raises(ValueError, match=rf"{path.name}.*line 2"):
        read_jsonl(path, strict=True)


def test_lenient_skips_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "mixed.jsonl"
    path.write_text('{"ok": true}\n{not-json}\n{"also": 1}\n', encoding="utf-8")
    assert read_jsonl(path, strict=False) == [{"ok": True}, {"also": 1}]
