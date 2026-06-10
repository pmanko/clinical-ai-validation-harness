"""mod__formentry_archive (carry-forward orphan) must transplant date_created.

Loads the module model through the real SQLMesh project Context (the same loader
the CLI uses, so the date_transplant macro module is wired exactly as in
production), renders it at EVALUATING stage against a fake adapter, and asserts on
the *resolved projection expressions* — not a source string. The legacy
formentry_archive table has one datetime column (date_created); a bare `SELECT *`
or a bare `src.date_created` passthrough renders unshifted and fails. Only the
@shift_date wrapper produces the DATE_ADD/NULLIF form. The output alias must stay
date_created so the carry-forward output schema is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlglot import exp
from sqlmesh.core.context import Context
from sqlmesh.core.macros import RuntimeStage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"
MODEL_NAME = "refapp_28_demo.mod__formentry_archive"

# The single datetime column on legacy formentry_archive that must be shifted.
DATE_COLUMNS = ("date_created",)

# A representative delta returned by the fake adapter's DATEDIFF.
_DELTA = 7174


class _FakeAdapter:
    """Engine adapter returning a fixed DATEDIFF delta for @date_shift_days."""

    def fetchdf(self, sql: str) -> pd.DataFrame:
        return pd.DataFrame({"d": [_DELTA]})


def _rendered_projections() -> dict[str, exp.Expression]:
    """Render the model at EVALUATING stage; return {output_alias: inner_expr}."""
    context = Context(paths=str(SQLMESH_DIR))
    model = context.get_model(MODEL_NAME)
    query = model.render_query(
        runtime_stage=RuntimeStage.EVALUATING,
        engine_adapter=_FakeAdapter(),
        end_date="2026-06-01",
    )
    projections: dict[str, exp.Expression] = {}
    for select in query.selects:
        inner = select.this if isinstance(select, exp.Alias) else select
        projections[select.alias_or_name] = inner
    return projections


def test_date_created_is_shifted_and_keeps_its_name():
    """date_created renders as DATE_ADD(NULLIF(src.date_created, zero), INTERVAL n
    DAY) and is aliased back to its original output name."""
    projections = _rendered_projections()
    for col in DATE_COLUMNS:
        assert col in projections, f"output column {col} disappeared from the model"
        inner = projections[col]
        assert isinstance(inner, exp.DateAdd), (
            f"{col} is not shifted; rendered as {inner.sql(dialect='mysql')!r} "
            "(expected a DATE_ADD from @shift_date)"
        )
        nullif = inner.this
        assert isinstance(nullif, exp.Nullif), f"{col} not wrapped in NULLIF: {inner.sql()!r}"
        assert nullif.this.sql(dialect="mysql") == f"`src`.`{col}`"
        assert nullif.expression.sql(dialect="mysql") == "'0000-00-00 00:00:00'"
        assert int(inner.expression.name) == _DELTA, (
            f"{col} shifted by {inner.expression.name!r}, expected {_DELTA}"
        )


def test_non_date_columns_are_not_shifted():
    """FK / int / text passthroughs must NOT be wrapped — only dates move."""
    projections = _rendered_projections()
    for col in ("formentry_archive_id", "form_data", "creator"):
        assert col in projections, f"output column {col} disappeared from the model"
        assert not isinstance(projections[col], exp.DateAdd), (
            f"{col} was shifted but is not a date column"
        )
