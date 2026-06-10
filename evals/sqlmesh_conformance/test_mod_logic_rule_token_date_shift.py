"""mod__logic_rule_token (carry-forward orphan) must transplant its datetimes.

Loads the module model through the real SQLMesh project Context (the same loader
the CLI uses, so the date_transplant macro module is wired exactly as in
production), renders it at EVALUATING stage against a fake adapter, and asserts on
the *resolved projection expressions* — not a source string. The legacy
logic_rule_token table has two datetime columns (date_created, date_changed); a
bare `SELECT *` or a bare `src.<col>` passthrough renders unshifted and fails.
Only the @shift_date wrapper produces the DATE_ADD/NULLIF form. The output
aliases must stay date_created / date_changed so the carry-forward output schema
is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlglot import exp
from sqlmesh.core.context import Context
from sqlmesh.core.macros import RuntimeStage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"
MODEL_NAME = "refapp_28_demo.mod__logic_rule_token"

# The two datetime columns on legacy logic_rule_token that must be shifted.
DATE_COLUMNS = ("date_created", "date_changed")

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


def test_datetimes_are_shifted_and_keep_their_names():
    """date_created/date_changed each render as DATE_ADD(NULLIF(src.<col>, zero),
    INTERVAL n DAY) and are aliased back to their original output names."""
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
