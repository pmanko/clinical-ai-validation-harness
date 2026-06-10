"""Date-transplant wiring for stg_encounter_provider.

Renders the model through a real SQLMesh `Context` (the same load path SQLMesh
uses) and asserts that every audit date column is wrapped by `@shift_date`
(i.e. renders to a `DATE_ADD(NULLIF(...), INTERVAL ... DAY)` expression keeping
its original output name). At LOADING stage the delta is the stable 0
placeholder, but the DATE_ADD wrapper -- the thing under test here -- is still
emitted.
"""

from __future__ import annotations

from pathlib import Path

from sqlmesh.core.context import Context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

MODEL = "refapp_28_demo.stg_encounter_provider"
SHIFTED_DATE_COLUMNS = ("date_created", "date_changed", "date_voided")
BARE_NON_DATE_COLUMNS = (
    "encounter_provider_id",
    "encounter_id",
    "provider_id",
    "encounter_role_id",
    "creator",
    "changed_by",
    "voided",
    "voided_by",
    "void_reason",
    "uuid",
)


def _rendered_sql() -> str:
    ctx = Context(paths=[str(SQLMESH_DIR)])
    model = ctx.get_model(MODEL)
    return model.render_query_or_raise().sql(dialect="mysql")


def test_date_columns_are_shift_wrapped_with_preserved_names():
    sql = _rendered_sql()
    for col in SHIFTED_DATE_COLUMNS:
        # @shift_date emits DATE_ADD(NULLIF(<col>, '0000-00-00 00:00:00'), INTERVAL n DAY)
        assert f"DATE_ADD(NULLIF(`src`.`{col}`" in sql, (
            f"{col} is not wrapped by @shift_date:\n{sql}"
        )
        # Output name preserved via the caller-supplied alias.
        assert f"DAY) AS `{col}`" in sql, (
            f"{col} lost its output alias after shifting:\n{sql}"
        )


def test_non_date_columns_stay_bare():
    sql = _rendered_sql()
    for col in BARE_NON_DATE_COLUMNS:
        assert f"`src`.`{col}` AS `{col}`" in sql, (
            f"{col} should remain a bare passthrough:\n{sql}"
        )
        assert f"DATE_ADD(NULLIF(`src`.`{col}`" not in sql, (
            f"{col} is not a date column and must not be shifted:\n{sql}"
        )
