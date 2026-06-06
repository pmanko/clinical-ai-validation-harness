"""stg_person_address must shift every date/datetime column by the uniform delta.

The date-transplant design wraps every date/datetime source column with
`@shift_date(...)` while preserving the column's output name via an explicit
alias. This test renders the actual SQLMesh model (DB-free, at LOADING stage
where the delta is the stable 0 placeholder) and asserts each of the five
date/datetime columns renders as
    DATE_ADD(NULLIF(src.<col>, '0000-00-00 00:00:00'), INTERVAL <n> DAY) AS <col>
(structurally a DATE_ADD, not a bare passthrough) while keeping its output name.
"""

from __future__ import annotations

from pathlib import Path

from sqlglot import exp
from sqlmesh.core.context import Context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

DATE_COLUMNS = ("date_created", "date_voided", "date_changed", "start_date", "end_date")
# Sampled non-date passthrough columns that must NOT be wrapped.
NON_DATE_COLUMNS = ("person_id", "creator", "voided", "city_village", "postal_code")


def _select_aliases(model_name: str) -> dict[str, exp.Expression]:
    """Render the model query and return {output_name: projection_expression}."""
    ctx = Context(paths=str(SQLMESH_DIR), gateway="harness")
    model = ctx.get_model(model_name)
    query = model.render_query()
    aliases: dict[str, exp.Expression] = {}
    for proj in query.expressions:
        name = proj.alias_or_name
        inner = proj.this if isinstance(proj, exp.Alias) else proj
        aliases[name] = inner
    return aliases


def test_date_columns_wrapped_in_dateadd_and_keep_output_name():
    aliases = _select_aliases("refapp_28_demo.stg_person_address")
    for col in DATE_COLUMNS:
        assert col in aliases, f"output column {col} missing from rendered SELECT"
        inner = aliases[col]
        assert isinstance(inner, exp.DateAdd), (
            f"{col} is not wrapped in DATE_ADD; got: {inner.sql(dialect='mysql')}"
        )
        # NULL/zero-date safety: the shifted operand is NULLIF(src.<col>, zero).
        nullif = inner.this
        assert isinstance(nullif, exp.Func) and nullif.sql(dialect="mysql").upper().startswith(
            "NULLIF("
        ), f"{col} DATE_ADD operand is not NULLIF-guarded: {inner.sql(dialect='mysql')}"
        assert "0000-00-00" in nullif.sql(dialect="mysql"), (
            f"{col} NULLIF does not guard the zero-date sentinel"
        )
        col_ref = nullif.this
        assert isinstance(col_ref, exp.Column) and col_ref.name == col, (
            f"{col} does not shift its own source column"
        )


def test_non_date_columns_remain_bare_passthroughs():
    aliases = _select_aliases("refapp_28_demo.stg_person_address")
    for col in NON_DATE_COLUMNS:
        assert col in aliases, f"output column {col} missing from rendered SELECT"
        inner = aliases[col]
        assert not isinstance(inner, exp.DateAdd), (
            f"non-date column {col} was wrapped in DATE_ADD but must stay a passthrough"
        )
        assert isinstance(inner, exp.Column) and inner.name == col, (
            f"non-date column {col} is not a bare src.{col} passthrough: "
            f"{inner.sql(dialect='mysql')}"
        )
