"""Behavior test: stg_provider applies the uniform date-transplant to its date columns.

Renders the actual `stg_provider.sql` model through the real `sqlmesh render` CLI
(the production code path: macro auto-discovery + python_env construction + macro
expansion) and asserts the rendered SQL, not source strings. Date columns must
come out wrapped in `DATE_ADD(NULLIF(col, <zero>), INTERVAL <delta> DAY)` under
their original output names; FK/text/boolean columns must stay bare.

At render time (no warehouse) the delta is the stable `0` placeholder by design;
the real delta is substituted at EVALUATING. We assert the wrapping shape, which
is what distinguishes a shifted column from a bare passthrough.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

DATE_COLUMNS = ("date_created", "date_changed", "date_retired")


def _render_stg_provider() -> str:
    sqlmesh_bin = Path(sys.executable).parent / "sqlmesh"
    proc = subprocess.run(
        [str(sqlmesh_bin), "-p", str(SQLMESH_DIR), "render",
         "refapp_28_demo.stg_provider"],
        env={**os.environ}, capture_output=True, text=True, check=False,
    )
    out = proc.stdout + proc.stderr
    assert "SELECT" in out, f"sqlmesh render did not emit SQL:\n{out}"
    # `sqlmesh render` wraps output to the terminal width; join continuation
    # lines so a single projection isn't split across physical lines.
    return re.sub(r"\s+", " ", out)


@pytest.mark.skipif(
    not (Path(sys.executable).parent / "sqlmesh").is_file(),
    reason="sqlmesh CLI not in venv bin (install via `uv sync`)",
)
def test_date_columns_are_shifted_under_original_names():
    rendered = _render_stg_provider()
    for col in DATE_COLUMNS:
        pattern = (
            r"DATE_ADD\(NULLIF\(`src`\.`" + col + r"`, '0000-00-00 00:00:00'\), "
            r"INTERVAL '?\d+'? DAY\) AS `" + col + r"`"
        )
        assert re.search(pattern, rendered), (
            f"{col} not transplanted under its original name; rendered:\n{rendered}"
        )
