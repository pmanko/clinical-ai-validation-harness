from __future__ import annotations

from pathlib import Path

from harness.report_shell.assets import THEME_TOGGLE_BUTTON_HTML


def test_dashboard_imports_shell_theme_assets() -> None:
    src = (
        Path(__file__).resolve().parents[2] / "scripts" / "validate-dashboard.py"
    ).read_text(encoding="utf-8")
    assert "from harness.report_shell.assets import" in src
    assert "THEME_TOGGLE_BUTTON_HTML" in src
    assert "THEME_TOGGLE_CSS" in src
    assert "theme-toggle" in THEME_TOGGLE_BUTTON_HTML
