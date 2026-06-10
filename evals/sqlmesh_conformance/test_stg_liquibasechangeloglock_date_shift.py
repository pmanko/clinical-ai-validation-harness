"""Behavior test: stg_liquibasechangeloglock shifts its one datetime column.

The Liquibase lock table carries a single date/datetime source column,
`LOCKGRANTED` (live MariaDB type: datetime). Its three siblings are non-date and
stay bare passthroughs: `ID` (int), `LOCKED` (tinyint(1) boolean flag), and
`LOCKEDBY` (varchar(255) text).

We render the real model query through a SQLMesh `Context` (no warehouse needed
— at LOADING stage the delta is a 0 placeholder) and inspect the projected
expressions, so the assertions cover actual rendered SQL, not source strings. A
bare `src.LOCKGRANTED` passthrough is the unshifted/red state; the shifted state
wraps it in the macro's DATE_ADD(NULLIF(..., zero), INTERVAL n DAY) form under an
explicit AS alias that preserves the LOCKGRANTED output name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlglot import exp
from sqlmesh.core.context import Context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

MODEL = "refapp_28_demo.stg_liquibasechangeloglock"
DATE_COLUMN = "LOCKGRANTED"


@pytest.fixture(scope="module")
def context() -> Context:
    return Context(paths=[str(SQLMESH_DIR)], gateway="harness")


def _projections(context: Context, model_name: str) -> dict[str, exp.Expression]:
    """Map output column name -> the projected expression for a model."""
    model = context.get_model(model_name)
    assert model is not None, f"{model_name} model not found in project"
    query = model.render_query_or_raise()
    out: dict[str, exp.Expression] = {}
    for proj in query.expressions:
        out[proj.alias_or_name] = proj.unalias()
    return out


def _is_shifted(projection: exp.Expression) -> bool:
    """True iff the projection is DATE_ADD(NULLIF(<col>, zero), INTERVAL n DAY)
    — the exact shape `@shift_date` renders."""
    if not isinstance(projection, exp.DateAdd):
        return False
    inner = projection.this
    if not isinstance(inner, exp.Nullif):
        return False
    zero = inner.expression
    return isinstance(zero, exp.Literal) and zero.this == "0000-00-00 00:00:00"


def test_lockgranted_is_shifted(context):
    projs = _projections(context, MODEL)
    assert DATE_COLUMN in projs, f"{DATE_COLUMN} missing from {MODEL} output"
    assert _is_shifted(projs[DATE_COLUMN]), (
        f"{DATE_COLUMN} must be wrapped with @shift_date; rendered as "
        f"{projs[DATE_COLUMN].sql(dialect='mysql')}"
    )
