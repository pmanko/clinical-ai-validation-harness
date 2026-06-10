"""Behavior test: stg_form_field applies the uniform date-transplant to its date columns.

Renders the actual `stg_form_field.sql` model in-process through the real SQLMesh
`Context` (`get_model().render_query_or_raise()` — macro auto-discovery +
python_env construction + macro expansion) and asserts the rendered SQL, not
source strings. This is the same render path the sibling stg_* conformance tests
use, so it needs no warehouse connection. Date columns must come out wrapped in
`DATE_ADD(NULLIF(col, <zero>), INTERVAL <delta> DAY)` under their original output
names; FK/count columns must stay bare.

At render time (no warehouse) the delta is the stable `0` placeholder by design;
the real delta is substituted at EVALUATING. We assert the wrapping shape, which
is what distinguishes a shifted column from a bare passthrough.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlmesh.core.context import Context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

MODEL = "refapp_28_demo.stg_form_field"
DATE_COLUMNS = ("date_created", "date_changed")


def _rendered_sql() -> str:
    ctx = Context(paths=[str(SQLMESH_DIR)])
    return ctx.get_model(MODEL).render_query_or_raise().sql(dialect="mysql")


def test_date_columns_are_shifted_under_original_names():
    rendered = _rendered_sql()
    for col in DATE_COLUMNS:
        pattern = (
            r"DATE_ADD\(NULLIF\(`src`\.`" + col + r"`, '0000-00-00 00:00:00'\), "
            r"INTERVAL '?\d+'? DAY\) AS `" + col + r"`"
        )
        assert re.search(pattern, rendered), (
            f"{col} not transplanted under its original name; rendered:\n{rendered}"
        )
