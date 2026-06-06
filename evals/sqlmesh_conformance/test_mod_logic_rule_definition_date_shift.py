"""mod__logic_rule_definition must transplant its date columns via @shift_date.

Loads the module model through the real SQLMesh project Context (the same loader
the CLI uses, so the date_transplant macro module is wired exactly as in
production), renders it at EVALUATING stage against a fake adapter, and asserts on
the *resolved projection expressions* — not a source string. A bare passthrough
(`SELECT *` / `src.date_created`) renders unshifted and fails; only the
@shift_date wrapper produces the DATE_ADD/NULLIF form. The output alias must stay
the original column name so the model's output schema is unchanged.

legacy_27_raw.logic_rule_definition has three date/datetime columns
(date_created, date_changed, date_retired); id (PK), creator/changed_by/
retired_by (FK), retired (tinyint flag) and the text columns must stay unshifted.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlglot import exp
from sqlmesh.core.context import Context
from sqlmesh.core.macros import RuntimeStage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"
MODEL_NAME = "refapp_28_demo.mod__logic_rule_definition"

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


def _assert_shifted(col: str) -> None:
    projections = _rendered_projections()
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


def test_date_created_is_shifted_and_keeps_its_name():
    """date_created renders as DATE_ADD(NULLIF(src.date_created, zero), INTERVAL n DAY)
    and is aliased back to its original output name."""
    _assert_shifted("date_created")


def test_date_changed_is_shifted_and_keeps_its_name():
    """date_changed renders as DATE_ADD(NULLIF(src.date_changed, zero), INTERVAL n DAY)
    and is aliased back to its original output name."""
    _assert_shifted("date_changed")


def test_date_retired_is_shifted_and_keeps_its_name():
    """date_retired renders as DATE_ADD(NULLIF(src.date_retired, zero), INTERVAL n DAY)
    and is aliased back to its original output name."""
    _assert_shifted("date_retired")


def test_non_date_columns_pass_through_unshifted():
    """PK / FK / flag / text columns must NOT be wrapped in a DATE_ADD shift and
    must keep their original output name."""
    non_date = (
        "id",
        "uuid",
        "name",
        "description",
        "rule_content",
        "language",
        "creator",
        "changed_by",
        "retired",
        "retired_by",
        "retire_reason",
    )
    projections = _rendered_projections()
    for col in non_date:
        assert col in projections, f"output column {col} disappeared from the model"
        assert not isinstance(projections[col], exp.DateAdd), (
            f"{col} must not be date-shifted; rendered as "
            f"{projections[col].sql(dialect='mysql')!r}"
        )
