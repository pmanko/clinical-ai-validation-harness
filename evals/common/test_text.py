"""Parity vectors for harness.common.text escaping helpers."""

from __future__ import annotations

import html

import pytest

from harness.common.text import esc, esc_inline


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        ("", ""),
        ("plain", "plain"),
        ("a & b", "a &amp; b"),
        ("<script>", "&lt;script&gt;"),
        ('say "hi"', "say &quot;hi&quot;"),
        ("a'b", "a&#x27;b"),
        (42, "42"),
        ("line\nbreak", "line\nbreak"),
    ],
)
def test_esc_matches_report_semantics(value, expected: str) -> None:
    assert esc(value) == expected
    assert esc(value) == html.escape("" if value is None else str(value))


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        ("", ""),
        ("plain", "plain"),
        ("a & b", "a &amp; b"),
        ("<script>", "&lt;script&gt;"),
        ("line\nbreak", "line break"),
        ('say "hi"', 'say "hi"'),  # dashboard esc_inline does not escape quotes
        (42, "42"),
        ("a > b < c", "a &gt; b &lt; c"),
    ],
)
def test_esc_inline_matches_dashboard_semantics(value, expected: str) -> None:
    assert esc_inline(value) == expected
    s = None if value is None else str(value)
    assert esc_inline(value) == (
        (s or "").replace("\n", " ").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
