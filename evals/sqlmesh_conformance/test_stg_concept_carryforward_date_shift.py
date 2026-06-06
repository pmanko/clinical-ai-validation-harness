"""stg_concept_carryforward must transplant every date column via @shift_date.

Loads the model through the real SQLMesh project Context (the same loader the CLI
uses, so the date_transplant macro module is wired exactly as in production),
renders it at EVALUATING stage against a fake adapter, and asserts on the
*resolved projection expressions* — not a source string. A bare passthrough
(`src.date_created`) renders unshifted and fails; only the @shift_date wrapper
produces the DATE_ADD/NULLIF form. The output alias must stay the original column
name so the model's output schema is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlglot import exp
from sqlmesh.core.context import Context
from sqlmesh.core.macros import RuntimeStage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"
MODEL_NAME = "refapp_28_demo.stg_concept_carryforward"

# The three date/datetime audit columns on legacy concept that must be shifted.
DATE_COLUMNS = ("date_created", "date_changed", "date_retired")

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


def test_every_date_column_is_shifted_and_keeps_its_name():
    """Each date column renders as DATE_ADD(NULLIF(src.<col>, zero), INTERVAL n DAY)
    and is aliased back to its original output name."""
    projections = _rendered_projections()
    for col in DATE_COLUMNS:
        assert col in projections, f"output column {col} disappeared from the model"
        inner = projections[col]
        assert isinstance(inner, exp.DateAdd), (
            f"{col} is not shifted; rendered as {inner.sql(dialect='mysql')!r} "
            "(expected a DATE_ADD from @shift_date)"
        )
        # NULL/zero-date-safe inner column, and the uniform delta from the adapter.
        nullif = inner.this
        assert isinstance(nullif, exp.Nullif), f"{col} not wrapped in NULLIF: {inner.sql()!r}"
        assert nullif.this.sql(dialect="mysql") == f"`src`.`{col}`"
        assert nullif.expression.sql(dialect="mysql") == "'0000-00-00 00:00:00'"
        assert int(inner.expression.name) == _DELTA, (
            f"{col} shifted by {inner.expression.name!r}, expected {_DELTA}"
        )


def test_non_date_columns_are_not_shifted():
    """Booleans / FKs / text passthroughs must NOT be wrapped — only dates move."""
    projections = _rendered_projections()
    for col in ("concept_id", "retired", "creator", "changed_by", "retired_by", "uuid"):
        assert col in projections, f"output column {col} disappeared from the model"
        assert not isinstance(projections[col], exp.DateAdd), (
            f"{col} was shifted but is not a date column"
        )
