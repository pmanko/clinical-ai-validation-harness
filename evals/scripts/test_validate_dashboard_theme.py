from __future__ import annotations

from pathlib import Path


def test_dashboard_uses_structured_dashboard_data_and_external_shell() -> None:
    src = (
        Path(__file__).resolve().parents[2] / "scripts" / "validate-dashboard.py"
    ).read_text(encoding="utf-8")
    assert "from harness.validate.dashboard_data import" in src
    assert "dashboard-shell.css" in src
    assert "dashboard-shell.js" in src
    assert "--freeze" not in src
