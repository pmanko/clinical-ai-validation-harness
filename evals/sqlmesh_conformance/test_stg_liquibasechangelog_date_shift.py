"""Behavior test: stg_liquibasechangelog shifts its date column via @shift_date.

The staging passthrough model `stg_liquibasechangelog` carries a single
datetime source column — `DATEEXECUTED` (all other columns are varchar/int).
It must be wrapped with the uniform date-transplant macro so it rides the same
delta as every other model, while keeping its original output name.

We load the real SQLMesh project and render the model's query, then assert on
the rendered SQL (not the source string): a bare `src.dateexecuted` passthrough
is the unshifted/red state; the shifted state wraps it in the macro's
DATE_ADD(NULLIF(...)) form under an explicit AS alias that preserves the name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

DATE_COLUMNS = ("dateexecuted",)


@pytest.fixture(scope="module")
def stg_liquibasechangelog_sql() -> str:
    """Rendered SQL for the stg_liquibasechangelog model, via a real SQLMesh context."""
    sqlmesh = pytest.importorskip("sqlmesh")
    Context = sqlmesh.Context
    ctx = Context(paths=str(SQLMESH_DIR))
    model = ctx.get_model("refapp_28_demo.stg_liquibasechangelog")
    assert model is not None, "stg_liquibasechangelog model not found in project"
    # Strip identifier backticks: sqlglot may or may not quote the column name
    # depending on normalization/cache state, but the shift invariant is the same.
    return model.render_query_or_raise().sql(dialect="mysql").lower().replace("`", "")


def test_date_columns_are_wrapped_in_shift_date(stg_liquibasechangelog_sql: str):
    sql = stg_liquibasechangelog_sql
    assert "date_add(nullif(" in sql, "no DATE_ADD(NULLIF(...)) shift present at all"
    for col in DATE_COLUMNS:
        # Shifted+aliased form: ... INTERVAL n DAY) AS <col>
        assert f"day) as {col}" in sql, (
            f"{col} is not shifted+aliased; expected a DATE_ADD(...) AS {col}, "
            f"rendered SQL:\n{sql}"
        )
