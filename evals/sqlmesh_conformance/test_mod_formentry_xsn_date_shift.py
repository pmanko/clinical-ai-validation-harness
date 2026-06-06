"""Behavior test: mod__formentry_xsn shifts its date columns via @shift_date.

The carry-forward module model `mod__formentry_xsn` carries two datetime source
columns — `date_created` and `date_archived`. Both must be wrapped with the
uniform date-transplant macro so they ride the same delta as every other model,
while keeping their original output names.

We load the real SQLMesh project and render the model's query, then assert on
the rendered SQL (not the source string): a bare `src.date_created` passthrough
(or a `SELECT *`) is the unshifted/red state; the shifted state wraps it in the
macro's DATE_ADD(NULLIF(...)) form under an explicit AS alias that preserves the
name. Identifier quoting (backticks) is stripped so matches are
dialect-quoting-agnostic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

DATE_COLUMNS = ("date_created", "date_archived")


def _strip_quotes(sql: str) -> str:
    """Drop identifier backticks/double-quotes so matches are quoting-agnostic."""
    return sql.replace("`", "").replace('"', "")


@pytest.fixture(scope="module")
def mod_formentry_xsn_sql() -> str:
    """Rendered (lowercased, quote-stripped) SQL for the mod__formentry_xsn model."""
    sqlmesh = pytest.importorskip("sqlmesh")
    ctx = sqlmesh.Context(paths=str(SQLMESH_DIR))
    model = ctx.get_model("refapp_28_demo.mod__formentry_xsn")
    assert model is not None, "mod__formentry_xsn model not found in project"
    return _strip_quotes(model.render_query_or_raise().sql(dialect="mysql").lower())


def test_date_columns_are_wrapped_in_shift_date(mod_formentry_xsn_sql: str):
    sql = mod_formentry_xsn_sql
    assert "date_add(nullif(" in sql, "no DATE_ADD(NULLIF(...)) shift present at all"
    for col in DATE_COLUMNS:
        # Shifted+aliased form: ... INTERVAL n DAY) AS <col>
        assert f"day) as {col}" in sql, (
            f"{col} is not shifted+aliased; expected a DATE_ADD(...) AS {col}, "
            f"rendered SQL:\n{sql}"
        )


def test_archived_int_flag_is_not_shifted(mod_formentry_xsn_sql: str):
    """`archived` is an INT flag, not a date — it must stay a bare passthrough."""
    sql = mod_formentry_xsn_sql
    assert "day) as archived" not in sql, (
        "`archived` is an INT flag and must NOT be date-shifted; rendered SQL:\n"
        f"{sql}"
    )
