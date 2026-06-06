"""stg_drug must shift every legacy date/datetime passthrough column.

The uniform date-transplant rule says: in each model's SELECT, every
date/datetime *source* column is wrapped with `@shift_date(...)` while keeping
its original output name. For `stg_drug` the legacy passthrough date columns are
`date_created`, `date_retired`, `date_changed` (first UNION arm, from
`legacy_27_raw.drug src`).

The assertion renders the *actual* model through the real SQLMesh project
Context (the same loader SQLMesh uses), so it covers the rendered SQL — not a
source-string grep. At LOADING stage the anchor delta is the stable `0`
placeholder (no DB needed); the structural DATE_ADD(NULLIF(...)) wrapping is
what proves the columns are shifted.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlmesh.core.context import Context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLMESH_DIR = PROJECT_ROOT / "datasets" / "transforms" / "sqlmesh"


@lru_cache(maxsize=1)
def _rendered_stg_drug() -> str:
    ctx = Context(paths=[str(SQLMESH_DIR)])
    return ctx.render("refapp_28_demo.stg_drug").sql(dialect="mysql")


def test_legacy_passthrough_date_columns_are_shifted():
    """date_created / date_retired / date_changed from `drug src` render as a
    NULL-safe DATE_ADD shift, not a bare passthrough."""
    txt = _rendered_stg_drug()
    for col in ("date_created", "date_retired", "date_changed"):
        shifted = (
            f"DATE_ADD(NULLIF(`src`.`{col}`, '0000-00-00 00:00:00'), "
            f"INTERVAL '0' DAY) AS `{col}`"
        )
        assert shifted in txt, f"{col} not shifted; expected {shifted!r} in:\n{txt}"
        assert f"`src`.`{col}` AS `{col}`" not in txt, (
            f"{col} still emitted as a bare passthrough"
        )


def test_null_literal_date_columns_stay_null():
    """The generated-concept arm's CAST(NULL AS DATETIME) date columns must NOT
    be wrapped — NULL stays NULL."""
    txt = _rendered_stg_drug()
    assert "CAST(NULL AS DATETIME) AS `date_retired`" in txt
    assert "CAST(NULL AS DATETIME) AS `date_changed`" in txt
    assert "NULLIF(CAST(NULL" not in txt, "a NULL literal was wrongly shifted"


def test_aggregate_first_date_created_is_not_double_shifted():
    """MIN(meds.first_date_created) AS date_created is fed by already-shifted
    stg_obs.date_created; it must not be shifted a second time here."""
    txt = _rendered_stg_drug()
    assert "MIN(`meds`.`first_date_created`) AS `date_created`" in txt
    assert "DATE_ADD(NULLIF(`meds`.`first_date_created`" not in txt
    assert "DATE_ADD(NULLIF(MIN(`meds`.`first_date_created`)" not in txt
