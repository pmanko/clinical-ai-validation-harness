"""Tests for evals.validate.dom_canon — attribute order + selective whitespace."""

from __future__ import annotations

from .dom_canon import canonicalize_html


def test_sorts_attributes_lexically() -> None:
    a = '<div class="x" id="a" data-z="1"></div>'
    b = '<div data-z="1" id="a" class="x"></div>'
    assert canonicalize_html(a) == canonicalize_html(b)
    assert 'class="x" data-z="1" id="a"' in canonicalize_html(a)


def test_normalizes_inter_tag_whitespace_only() -> None:
    a = "<div><span>hi</span></div>"
    b = "<div>\n  <span>hi</span>\n</div>"
    assert canonicalize_html(a) == canonicalize_html(b)


def test_preserves_script_text_exactly() -> None:
    raw = "<script>const x = 1;   // keep\n\tvar y = 2;</script>"
    out = canonicalize_html(f"<div>{raw}</div>")
    assert "const x = 1;   // keep\n\tvar y = 2;" in out


def test_preserves_style_text_exactly() -> None:
    raw = "<style>body {  color:  red; }\n</style>"
    out = canonicalize_html(raw)
    assert "body {  color:  red; }\n" in out


def test_preserves_pre_text_exactly() -> None:
    raw = "<pre>  line1\n\n  line2  </pre>"
    assert "  line1\n\n  line2  " in canonicalize_html(raw)


def test_preserves_answer_text_exactly() -> None:
    raw = '<div class="ans">  keep  spaces\nand newlines  </div>'
    out = canonicalize_html(raw)
    assert "  keep  spaces\nand newlines  " in out
