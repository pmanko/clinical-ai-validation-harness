"""AST guard: shared JSONL/escape/trace helpers must not be reimplemented."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (ROOT / "harness", ROOT / "scripts", ROOT / "evals")


def _py_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _function_defs(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def test_exactly_one_jsonl_reader_implementation() -> None:
    locs = []
    for path in _py_files():
        names = set(_function_defs(path))
        if "read_jsonl" in names or "_read_jsonl" in names:
            locs.append(path.relative_to(ROOT).as_posix())
    assert locs == ["harness/common/jsonl.py"], locs


def test_esc_and_esc_inline_defined_only_in_text() -> None:
    esc_locs = []
    esc_inline_locs = []
    for path in _py_files():
        names = set(_function_defs(path))
        rel = path.relative_to(ROOT).as_posix()
        if "esc" in names:
            esc_locs.append(rel)
        if "esc_inline" in names:
            esc_inline_locs.append(rel)
    assert esc_locs == ["harness/common/text.py"], esc_locs
    assert esc_inline_locs == ["harness/common/text.py"], esc_inline_locs


def test_validate_dashboard_has_no_match_trace_def() -> None:
    path = ROOT / "scripts" / "validate-dashboard.py"
    assert path.exists()
    names = set(_function_defs(path))
    assert "_match_trace" not in names
