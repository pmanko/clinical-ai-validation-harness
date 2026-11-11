"""Packaged resources for `harness.validate` (rubrics and judge briefs)."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

_CHECKOUT_ROOT = Path(__file__).resolve().parents[3]
_CHECKOUT_SCORING_DIR = _CHECKOUT_ROOT / ".claude" / "skills" / "clinical-answer-scoring"


def _read_scoring_asset_bytes(checkout_name: str, packaged_name: str) -> bytes:
    checkout_file = _CHECKOUT_SCORING_DIR / checkout_name
    if checkout_file.is_file():
        return checkout_file.read_bytes()
    pkg = resources.files("harness.validate.resources.clinical_answer_scoring")
    return pkg.joinpath(packaged_name).read_bytes()


def read_judge_brief_bytes() -> bytes:
    """Return raw UTF-8 bytes of `clinical-answer-scoring/judge.md`."""
    return _read_scoring_asset_bytes("judge.md", "judge.txt")


def read_judge_brief_text() -> str:
    """Return UTF-8 text of `clinical-answer-scoring/judge.md`."""
    return read_judge_brief_bytes().decode("utf-8")


def read_rubric_bytes() -> bytes:
    """Return raw UTF-8 bytes of `clinical-answer-scoring/rubric.md`."""
    return _read_scoring_asset_bytes("rubric.md", "rubric.txt")


def read_rubric_text() -> str:
    """Return UTF-8 text of `clinical-answer-scoring/rubric.md`."""
    return read_rubric_bytes().decode("utf-8")
