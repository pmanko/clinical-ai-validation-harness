"""Each staging/clinical model must shift its date/datetime columns.

The `@shift_date` macro is exercised in isolation by
`test_date_transplant_macro.py`; this module asserts the *wiring* — that a
model's SELECT actually wraps every date/datetime source column with
`@shift_date(...)` (rendering to `DATE_ADD(NULLIF(col, zero), INTERVAL n DAY)`)
while leaving FK / count / text / boolean columns as bare passthroughs and
preserving each column's output name.

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

PATIENT_PROGRAM = "refapp_28_demo.stg_patient_program"


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


def test_patient_program_date_enrolled_is_shifted(context):
    projs = _projections(context, PATIENT_PROGRAM)
    assert "date_enrolled" in projs, f"date_enrolled missing from {PATIENT_PROGRAM} output"
    assert _is_shifted(projs["date_enrolled"]), (
        "date_enrolled must be wrapped with @shift_date; rendered as "
        f"{projs['date_enrolled'].sql(dialect='mysql')}"
    )


def test_patient_program_date_completed_is_shifted(context):
    projs = _projections(context, PATIENT_PROGRAM)
    assert "date_completed" in projs, f"date_completed missing from {PATIENT_PROGRAM} output"
    assert _is_shifted(projs["date_completed"]), (
        "date_completed must be wrapped with @shift_date; rendered as "
        f"{projs['date_completed'].sql(dialect='mysql')}"
    )


def test_patient_program_date_created_is_shifted(context):
    projs = _projections(context, PATIENT_PROGRAM)
    assert "date_created" in projs, f"date_created missing from {PATIENT_PROGRAM} output"
    assert _is_shifted(projs["date_created"]), (
        "date_created must be wrapped with @shift_date; rendered as "
        f"{projs['date_created'].sql(dialect='mysql')}"
    )


def test_patient_program_date_changed_is_shifted(context):
    projs = _projections(context, PATIENT_PROGRAM)
    assert "date_changed" in projs, f"date_changed missing from {PATIENT_PROGRAM} output"
    assert _is_shifted(projs["date_changed"]), (
        "date_changed must be wrapped with @shift_date; rendered as "
        f"{projs['date_changed'].sql(dialect='mysql')}"
    )


def test_patient_program_date_voided_is_shifted(context):
    projs = _projections(context, PATIENT_PROGRAM)
    assert "date_voided" in projs, f"date_voided missing from {PATIENT_PROGRAM} output"
    assert _is_shifted(projs["date_voided"]), (
        "date_voided must be wrapped with @shift_date; rendered as "
        f"{projs['date_voided'].sql(dialect='mysql')}"
    )
