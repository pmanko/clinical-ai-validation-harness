"""HTML5 document shell: skeleton, data island, theme variables + toggle."""

from __future__ import annotations

import json
from typing import Any

from harness.report_shell.assets import (
    SHARED_CSS,
    SHARED_JS,
    THEME_TOGGLE_BUTTON_HTML,
    theme_bootstrap_js,
    theme_toggle_js,
)


def embed_json(blob: dict[str, Any]) -> str:
    """Serialize ``blob`` for an inert ``<script type="application/json">`` island.

    Neutralises the three characters that could break out of the element;
    ``\\uXXXX`` escapes are JSON-valid, so ``JSON.parse`` reverses them.
    """
    s = json.dumps(blob, ensure_ascii=False)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_document(
    *,
    title: str,
    body_html: str,
    embedded_data: dict[str, Any],
    style: str | None = None,
    script: str | None = None,
    theme_storage_key: str = "oc-theme-report",
) -> str:
    """Return a self-contained HTML5 document.

    Owns the doctype/html skeleton, theme CSS variables (via default ``style``),
    early theme bootstrap, the ``#report-data`` JSON island, and theme-toggle JS
    (via default ``script``). Callers supply page body markup; a family report may
    pass fully composed ``style``/``script`` to preserve byte-identical output.
    """
    css = SHARED_CSS if style is None else style
    js = (
        SHARED_JS + theme_toggle_js(theme_storage_key)
        if script is None
        else script
    )
    # Shell owns #theme-toggle when the body does not already embed one
    # (some reports place a btn-ghost toggle in their topbar).
    if "id='theme-toggle'" not in body_html and 'id="theme-toggle"' not in body_html:
        body_html = THEME_TOGGLE_BUTTON_HTML + body_html
    return (
        "<!doctype html><html data-theme='light'><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{css}</style>"
        f"<script>{theme_bootstrap_js(theme_storage_key)}</script></head>"
        f"<body>{body_html}"
        f"<script type='application/json' id='report-data'>{embed_json(embedded_data)}</script>"
        f"<script>{js}</script>"
        "</body></html>"
    )
