"""Uniform date transplant for the OpenMRS demo remap.

Every date/datetime column is shifted by ONE uniform delta so the whole record
set lands on a recent, realistic window while every ordering, interval,
age-at-encounter, and entry~event relationship is preserved exactly.

    delta_days = DATEDIFF(@end_date, anchor)
    anchor     = MAX(encounter_datetime) FROM <legacy>.encounter

Apply @shift_date EXACTLY ONCE along each column's lineage -- at the layer that
reads RAW legacy_27_raw (the staging models + the module carry-forward models).
Downstream models that read an already-shifted refapp_28_demo.* column (e.g.
clin__conditions / clin__orders / clin__allergy / terminology__concept_rebind
reading refapp_28_demo.stg_obs) MUST pass that column through unwrapped -- a
second @shift_date there would DOUBLE-shift it (2x delta -> a future date).

The anchor is taken from encounter (a clean 2006-02-01..2006-10-10 range,
verified against the live MariaDB 10.11.7), NOT from obs.obs_datetime: obs
carries 8 out-of-range typo rows (live MIN/MAX = 1899-12-30 .. 5006-03-17)
that would poison a MAX(). Those rows ride the same uniform delta and remain
out-of-range outliers (8/476973, negligible) -- by design.

Two macros are exposed:

  @date_shift_days   -- the delta, computed ONCE per run as an INTEGER literal
                        by querying the live engine at EVALUATING stage. Gated
                        on runtime_stage so model loading never touches the DB
                        and the data hash / plan diff stays stable.

  @shift_date(col)   -- wraps a column as DATE_ADD(col, INTERVAL <delta> DAY),
                        NULL-safe and invalid-date-safe (0000-00-00 -> NULL).
"""

from __future__ import annotations

from sqlglot import exp

from sqlmesh.core.macros import MacroEvaluator, RuntimeStage, macro

# Memoize the delta so MAX(encounter_datetime) is queried at most once per
# evaluator (i.e. once per `sqlmesh run`), not once per shifted column.
_DELTA_CACHE_KEY = "__date_transplant_delta_days__"

# Neutral placeholder used at LOADING stage, where the engine adapter is not
# available. 0 = no shift; keeps the rendered SQL parseable and the model
# fingerprint stable. The real delta is substituted at EVALUATING.
_LOAD_PLACEHOLDER = 0

# Zero-date sentinel: MySQL/MariaDB store invalid dates as this under the
# default non-strict ALLOW_INVALID_DATES path.
_ZERO_DATE = "0000-00-00 00:00:00"


@macro()
def date_shift_days(evaluator: MacroEvaluator) -> exp.Expression:
    """The uniform shift, as an INTEGER literal.

    At LOADING stage (plan diff / column resolution / data hash) the engine
    adapter is unavailable, so return a stable placeholder. At EVALUATING stage
    query the anchor once, memoize on the evaluator, and emit the delta as a
    literal so DATE_ADD receives a constant -- no per-row/per-column correlated
    subquery.

    The anchor is MAX(encounter_datetime) from the legacy encounter table (a
    clean 2006 range), NOT obs.obs_datetime which carries out-of-range typo
    rows. When end_date is unset, fall back to CURDATE() so the target is
    always a realistic <= now date even without an explicit end_date.
    NULL/NaN MAX (empty table) yields a 0 shift rather than an error.
    """
    if evaluator.runtime_stage == RuntimeStage.LOADING.value:
        return exp.Literal.number(_LOAD_PLACEHOLDER)
    cache = evaluator.locals
    if _DELTA_CACHE_KEY not in cache:
        legacy = str(evaluator.var("source_legacy_schema", "legacy_27_raw"))
        end_date = evaluator.var("end_date")
        # DATEDIFF is computed server-side so the calendar arithmetic matches
        # the exact MySQL/MariaDB semantics used by @shift_date's DATE_ADD.
        end_expr = f"DATE('{end_date}')" if end_date else "CURDATE()"
        sql = (
            f"SELECT DATEDIFF({end_expr}, MAX(encounter_datetime)) AS d "
            f"FROM {legacy}.encounter"
        )
        df = evaluator.engine_adapter.fetchdf(sql)
        value = df.iloc[0]["d"]
        if value is None or (isinstance(value, float) and value != value):
            cache[_DELTA_CACHE_KEY] = _LOAD_PLACEHOLDER
        else:
            cache[_DELTA_CACHE_KEY] = int(value)
    return exp.Literal.number(cache[_DELTA_CACHE_KEY])


@macro()
def shift_date(evaluator: MacroEvaluator, column: exp.Expression) -> exp.Expression:
    """Shift a single date/datetime column by the uniform delta.

    NULL-safe:    NULL input -> NULL output (DATE_ADD propagates NULL).
    Invalid-safe: '0000-00-00' / zero dates -> NULL, no error (the NULLIF makes
                  it explicit and engine-independent).
    Name-preserving: returns only the expression; the caller keeps the AS alias.

    Renders (mysql dialect) to:
        DATE_ADD(NULLIF(<column>, '0000-00-00 00:00:00'), INTERVAL <delta> DAY)
    """
    safe_col = exp.func("NULLIF", column, exp.Literal.string(_ZERO_DATE))
    delta = date_shift_days(evaluator)
    return exp.DateAdd(this=safe_col, expression=delta, unit=exp.var("DAY"))
