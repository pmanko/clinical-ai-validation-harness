from __future__ import annotations

from harness.validate.runner import _row_is_good


def _row(answer: str, *, status: int = 200) -> dict:
    return {
        "metrics": {"http_status": status},
        "response": {"answer": answer},
    }


def test_row_is_good_rejects_empty_fallback_and_punctuation_only_answers():
    assert not _row_is_good(_row(""))
    assert not _row_is_good(_row("   "))
    assert not _row_is_good(_row("..."))
    assert not _row_is_good(_row("...!!"))
    assert not _row_is_good(_row("I could not produce a complete answer from the available data."))


def test_row_is_good_accepts_substantive_200_answers_only():
    assert _row_is_good(_row("No."))
    assert _row_is_good(_row("70 kg on 2026-01-26."))
    assert not _row_is_good(_row("70 kg on 2026-01-26.", status=500))
