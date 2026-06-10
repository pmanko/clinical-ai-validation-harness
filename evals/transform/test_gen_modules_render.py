"""Carry-forward SELECT rendering in gen_modules (no DB).

Pure rendering exercised with synthetic column metadata so it runs without
legacy_27_raw: a table with no date column stays a verbatim ``SELECT *``; once
any column is date-typed every column is enumerated and the date columns are
wrapped with ``@shift_date(...)`` under their original names. This is the
generator-side guarantee that re-running it preserves the uniform date-transplant
(the byte-identical integration test in test_gen_modules_date_shift.py is the
DB-backed end-to-end check).
"""

from harness.transform import gen_modules


def test_no_date_columns_stay_bare_select_star():
    cols = [("tribe_id", False), ("name", False)]
    sql = gen_modules._carry_forward_select("tribe", cols)
    assert sql == "SELECT * FROM legacy_27_raw.tribe;\n"


def test_date_columns_are_enumerated_and_shift_wrapped():
    cols = [
        ("formentry_queue_id", False),
        ("form_data", False),
        ("creator", False),
        ("date_created", True),
    ]
    sql = gen_modules._carry_forward_select("formentry_queue", cols)
    assert sql == (
        "SELECT\n"
        "  src.formentry_queue_id,\n"
        "  src.form_data,\n"
        "  src.creator,\n"
        "  @shift_date(src.date_created) AS date_created\n"
        "FROM legacy_27_raw.formentry_queue src;\n"
    )


def test_render_carry_forward_composes_header_and_shifted_select():
    cols = [("formentry_queue_id", False), ("date_created", True)]
    out = gen_modules.render_carry_forward(
        "formentry_queue", "legacy-only table; default carry-forward",
        "formentry_queue_id", cols,
    )
    # Header carries the model name, tag, grain, and rationale...
    assert "name refapp_28_demo.mod__formentry_queue," in out
    assert "tags (policy_bucket:orphan_carry_forward)," in out
    assert "grain (formentry_queue_id)" in out
    assert "legacy-only table; default carry-forward" in out
    # ...and the body is the enumerated, date-shifted SELECT.
    assert "@shift_date(src.date_created) AS date_created" in out
    assert out.rstrip().endswith("FROM legacy_27_raw.formentry_queue src;")
