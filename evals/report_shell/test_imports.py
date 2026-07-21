from __future__ import annotations

from pathlib import Path

SHELL = Path(__file__).resolve().parents[2] / "harness" / "report_shell"


def test_report_shell_contains_exactly_four_modules() -> None:
    files = sorted(p.name for p in SHELL.iterdir() if p.suffix == ".py")
    assert files == ["__init__.py", "assets.py", "document.py", "stats.py"]


def test_report_shell_public_imports() -> None:
    from harness import report_shell
    from harness.report_shell import stats

    assert callable(report_shell.render_document)
    assert callable(stats.avg)
    assert callable(stats.box_stats)
