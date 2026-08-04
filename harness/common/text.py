from __future__ import annotations

import html
from typing import Any


def esc(value: Any) -> str:
    """HTML-escape for report document content (preserves newlines)."""
    return html.escape("" if value is None else str(value))


def esc_inline(value: Any) -> str:
    """HTML-escape for single-line dashboard text nodes (newlines collapse)."""
    s = "" if value is None else str(value)
    return (
        s.replace("\n", " ")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
