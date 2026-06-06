"""Behavior tests for the uniform date-transplant macros.

`@shift_date` and `@date_shift_days` live in
`datasets/transforms/sqlmesh/macros/date_transplant.py`. SQLMesh auto-discovers
that folder; here we exercise the two macro callables directly against a real
`MacroEvaluator` (the same object SQLMesh hands them), so the assertions cover
actual rendered SQL and the runtime-stage gating — not source strings.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
from sqlglot import exp
from sqlmesh.core.macros import MacroEvaluator, RuntimeStage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MACRO_PATH = (
    PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh" / "macros" / "date_transplant.py"
)


def _load_macro_module():
    """Import the macro file by path (it lives under the SQLMesh project, not on
    sys.path)."""
    spec = importlib.util.spec_from_file_location("date_transplant", MACRO_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeAdapter:
    """Stand-in engine adapter returning a fixed MAX(encounter_datetime) delta."""

    def __init__(self, value):
        self.value = value
        self.queries: list[str] = []

    def fetchdf(self, sql: str) -> pd.DataFrame:
        self.queries.append(sql)
        return pd.DataFrame({"d": [self.value]})


def _evaluator(stage: RuntimeStage, *, adapter=None, end_date=None) -> MacroEvaluator:
    ev = MacroEvaluator(dialect="mysql", runtime_stage=stage)
    if end_date is not None:
        ev.locals["end_date"] = end_date
    if adapter is not None:
        # The engine_adapter property reads evaluator.locals["engine_adapter"];
        # inject the fake there (same slot SQLMesh uses at evaluation time).
        ev.locals["engine_adapter"] = adapter
    return ev


def test_shift_date_renders_null_and_zero_date_safe_dateadd():
    """shift_date wraps a column in DATE_ADD(NULLIF(col, zero), INTERVAL n DAY)."""
    mod = _load_macro_module()
    adapter = _FakeAdapter(7305)
    ev = _evaluator(RuntimeStage.EVALUATING, adapter=adapter, end_date="2026-06-01")

    rendered = mod.shift_date(ev, exp.column("encounter_datetime")).sql(dialect="mysql")
    assert rendered == (
        "DATE_ADD(NULLIF(encounter_datetime, '0000-00-00 00:00:00'), INTERVAL 7305 DAY)"
    )


def test_date_shift_days_is_loading_placeholder_without_db():
    """At LOADING stage the engine adapter is unavailable, so the delta must be
    a stable 0 literal — the model fingerprint must not depend on the DB."""
    mod = _load_macro_module()
    ev = _evaluator(RuntimeStage.LOADING)

    out = mod.date_shift_days(ev)
    assert isinstance(out, exp.Literal)
    assert out.sql(dialect="mysql") == "0"


def test_date_shift_days_queries_anchor_and_memoizes():
    """At EVALUATING stage the delta is DATEDIFF(@end_date, MAX(encounter_datetime))
    queried exactly once and reused for subsequent columns."""
    mod = _load_macro_module()
    adapter = _FakeAdapter(7305)
    ev = _evaluator(RuntimeStage.EVALUATING, adapter=adapter, end_date="2026-06-01")

    first = mod.date_shift_days(ev)
    second = mod.date_shift_days(ev)

    assert first.sql(dialect="mysql") == "7305"
    assert second.sql(dialect="mysql") == "7305"
    # Anchored on encounter, not obs; uses DATEDIFF against the bound end_date.
    assert len(adapter.queries) == 1, "delta must be computed once, then memoized"
    q = adapter.queries[0].lower()
    assert "max(encounter_datetime)" in q
    assert "from legacy_27_raw.encounter" in q
    assert "obs_datetime" not in q
    assert "datediff" in q


def test_compute_delta_handles_empty_table_as_no_shift():
    """NULL/NaN MAX (empty legacy.encounter) yields a 0 shift, not an error."""
    mod = _load_macro_module()
    adapter = _FakeAdapter(float("nan"))
    ev = _evaluator(RuntimeStage.EVALUATING, adapter=adapter, end_date="2026-06-01")

    assert mod.date_shift_days(ev).sql(dialect="mysql") == "0"


def test_compute_delta_falls_back_to_curdate_without_end_date():
    """With @end_date unset, the anchor delta is computed against CURDATE()."""
    mod = _load_macro_module()
    adapter = _FakeAdapter(42)
    ev = _evaluator(RuntimeStage.EVALUATING, adapter=adapter)  # no end_date

    mod.date_shift_days(ev)
    assert "curdate()" in adapter.queries[0].lower()
