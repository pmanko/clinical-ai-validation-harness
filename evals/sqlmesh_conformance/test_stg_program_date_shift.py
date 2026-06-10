"""Behavior test: stg_program shifts its date columns via @shift_date.

The staging passthrough model `stg_program` carries two date/datetime source
columns — `date_created` and `date_changed`. Both must be wrapped with the
uniform date-transplant macro so they ride the same delta as every other model,
while keeping their original output names.

We load the real SQLMesh project and render the model's query, then assert on
the rendered SQL (not the source string): a bare `src.date_created` passthrough
is the unshifted/red state; the shifted state wraps it in the macro's
DATE_ADD(NULLIF(...)) form under an explicit AS alias that preserves the name.
Identifier quoting (backticks) is stripped so matches are dialect-quoting-agnostic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

DATE_COLUMNS = ("date_created", "date_changed")


def _strip_quotes(sql: str) -> str:
    """Drop identifier backticks/double-quotes so matches are quoting-agnostic."""
    return sql.replace("`", "").replace('"', "")


@pytest.fixture(scope="module")
def stg_program_sql() -> str:
    """Rendered (lowercased, quote-stripped) SQL for the stg_program model."""
    sqlmesh = pytest.importorskip("sqlmesh")
    ctx = sqlmesh.Context(paths=str(SQLMESH_DIR))
    model = ctx.get_model("refapp_28_demo.stg_program")
    assert model is not None, "stg_program model not found in project"
    return _strip_quotes(model.render_query_or_raise().sql(dialect="mysql").lower())


def test_date_columns_are_wrapped_in_shift_date(stg_program_sql: str):
    sql = stg_program_sql
    assert "date_add(nullif(" in sql, "no DATE_ADD(NULLIF(...)) shift present at all"
    for col in DATE_COLUMNS:
        # Shifted+aliased form: ... INTERVAL n DAY) AS <col>
        assert f"day) as {col}" in sql, (
            f"{col} is not shifted+aliased; expected a DATE_ADD(...) AS {col}, "
            f"rendered SQL:\n{sql}"
        )
