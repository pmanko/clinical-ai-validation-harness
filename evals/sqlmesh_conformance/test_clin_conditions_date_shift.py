"""The clinical conditions model must NOT re-shift already-shifted columns.

`clin__conditions` reads FROM `refapp_28_demo.stg_obs` — a staging model whose
`obs_datetime` is ALREADY shifted once by `@shift_date`. Its date columns
(`onset_date`, `date_created`) therefore project that already-shifted staging
column straight through (a bare `s.obs_datetime` reference); wrapping them in
`@shift_date` again would DOUBLE-shift (2× delta → a future date). The single
shift must happen exactly once per lineage, at the staging layer that reads RAW
legacy. The `CAST(NULL AS DATETIME)` literal (`date_voided`) stays a bare NULL.

We render the real model query through a SQLMesh `Context` (no warehouse
needed — at LOADING stage the delta is a 0 placeholder) and inspect the
projected expressions, so the assertions cover actual rendered SQL, not source
strings.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlglot import exp
from sqlmesh.core.context import Context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"

CONDITIONS = "refapp_28_demo.clin__conditions"


@pytest.fixture(scope="module")
def context() -> Context:
    return Context(paths=[str(SQLMESH_DIR)], gateway="harness")


def _projections(context: Context, model_name: str) -> dict[str, exp.Expression]:
    """Map output column name -> the projected expression for a model."""
    model = context.get_model(model_name)
    query = model.render_query_or_raise()
    out: dict[str, exp.Expression] = {}
    for proj in query.expressions:
        out[proj.alias_or_name] = proj.unalias()
    return out


def _is_shifted(projection: exp.Expression) -> bool:
    """True iff the projection is a DATE_ADD(NULLIF(<col>, zero), INTERVAL n DAY)
    — the exact shape `@shift_date` renders."""
    if not isinstance(projection, exp.DateAdd):
        return False
    inner = projection.this
    if not isinstance(inner, exp.Nullif):
        return False
    zero = inner.expression
    return isinstance(zero, exp.Literal) and zero.this == "0000-00-00 00:00:00"


@pytest.mark.parametrize("column", ["onset_date", "date_created"])
def test_conditions_obs_datetime_passthrough_not_reshifted(context, column):
    """The column passes the ALREADY-shifted staging obs_datetime straight
    through: a bare `obs_datetime` reference, NOT a second @shift_date wrap."""
    projs = _projections(context, CONDITIONS)
    assert column in projs, f"{column} missing from {CONDITIONS} output"
    proj = projs[column]
    assert not _is_shifted(proj), (
        f"{column} is DOUBLE-shifted: clin__conditions reads the already-shifted "
        f"stg_obs.obs_datetime, so it must pass through unwrapped. Rendered as "
        f"{proj.sql(dialect='mysql')}"
    )
    assert isinstance(proj, exp.Column) and proj.name == "obs_datetime", (
        f"{column} must project the staging obs_datetime column (already shifted), "
        f"got {proj.sql(dialect='mysql')}"
    )


def test_conditions_date_voided_stays_null(context):
    """The NULL-literal date column is not wrapped — NULL stays NULL."""
    projs = _projections(context, CONDITIONS)
    assert "date_voided" in projs, f"date_voided missing from {CONDITIONS} output"
    proj = projs["date_voided"]
    assert not _is_shifted(proj), (
        "date_voided is a CAST(NULL AS DATETIME) literal and must NOT be wrapped; "
        f"rendered as {proj.sql(dialect='mysql')}"
    )
