from __future__ import annotations

import json
import re

from harness.report_shell.assets import THEME_TOGGLE_BUTTON_HTML
from harness.report_shell.document import render_document


def test_render_document_has_theme_and_data_island() -> None:
    html = render_document(
        title="Fixture report",
        body_html=f"<header>{THEME_TOGGLE_BUTTON_HTML}</header><p>hello</p>",
        embedded_data={"ok": True, "n": 1},
    )
    assert "id=\"theme-toggle\"" in html or "id='theme-toggle'" in html
    assert "data-theme='light'" in html
    assert "oc-theme-report" in html
    m = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>",
        html,
        flags=re.DOTALL,
    )
    assert m is not None
    assert json.loads(m.group(1)) == {"ok": True, "n": 1}
