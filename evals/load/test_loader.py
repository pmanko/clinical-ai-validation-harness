"""Direct loader (post-dlt): the SQL it generates to copy a SQLMesh snapshot
table into the OpenMRS target schema.

The load is all DB side-effects, so the testable seam is the *pure* SQL builder
``_build_load_sql`` — it owns the two things that actually change when dlt is
removed: (1) the INSERT reads ``FROM source_schema.source_table`` (the resolved
SQLMesh snapshot), NOT the destination table name dlt used to rename staging to;
(2) the 2.7→2.8 column intersection (destination cols present in the source).
These assertions are red-when-broken: rewire the FROM back to the target name, or
break the intersection, and they fail.
"""

from __future__ import annotations

import pytest

from harness.load.loader import _build_load_sql, load_one, load_all  # noqa: F401


# A SQLMesh snapshot table name differs from the OpenMRS target table name — that
# divergence is exactly what the dlt removal has to handle (dlt used to rename the
# staging table to the target name; now we read the snapshot directly).
SRC_SCHEMA = "sqlmesh__refapp_28_demo"
SRC_TABLE = "refapp_28_demo__clin__obs__3649557428"
TGT_SCHEMA = "openmrs_test"
TGT_TABLE = "obs"


def test_replace_truncates_target_then_inserts_from_source_snapshot():
    # dest has a 2.8-only column (provider_role_id) absent from the 2.7 source;
    # source has a _dlt_ artifact + a source-only column — both must be ignored.
    dest_cols = ["obs_id", "value_numeric", "provider_role_id"]
    src_cols = ["obs_id", "value_numeric", "_dlt_id", "legacy_only"]
    statements, dropped = _build_load_sql(
        SRC_SCHEMA, SRC_TABLE, TGT_SCHEMA, TGT_TABLE, "replace", dest_cols, src_cols
    )
    assert statements == [
        "TRUNCATE TABLE `openmrs_test`.`obs`",
        "INSERT INTO `openmrs_test`.`obs` (`obs_id`, `value_numeric`) "
        "SELECT `obs_id`, `value_numeric` "
        "FROM `sqlmesh__refapp_28_demo`.`refapp_28_demo__clin__obs__3649557428`",
    ]
    # the 2.8-only destination column is reported dropped (left to MySQL default);
    # the source-only + _dlt_ columns never appear.
    assert dropped == ["provider_role_id"]


def test_merge_is_insert_ignore_no_truncate():
    dest_cols = ["user_id", "username"]
    src_cols = ["user_id", "username"]
    statements, dropped = _build_load_sql(
        SRC_SCHEMA, "snap__users", TGT_SCHEMA, "users", "merge", dest_cols, src_cols
    )
    assert statements == [
        "INSERT IGNORE INTO `openmrs_test`.`users` (`user_id`, `username`) "
        "SELECT `user_id`, `username` FROM `sqlmesh__refapp_28_demo`.`snap__users`"
    ]
    assert dropped == []


def test_append_is_plain_insert():
    statements, _ = _build_load_sql(
        SRC_SCHEMA, "snap__x", TGT_SCHEMA, "x", "append", ["id"], ["id"]
    )
    assert statements == [
        "INSERT INTO `openmrs_test`.`x` (`id`) "
        "SELECT `id` FROM `sqlmesh__refapp_28_demo`.`snap__x`"
    ]


def test_unknown_disposition_raises():
    with pytest.raises(ValueError):
        _build_load_sql(SRC_SCHEMA, "s", TGT_SCHEMA, "t", "upsert", ["id"], ["id"])


def test_no_shared_columns_yields_no_insert():
    # if nothing intersects, the builder returns no INSERT (caller surfaces the error)
    statements, dropped = _build_load_sql(
        SRC_SCHEMA, "s", TGT_SCHEMA, "t", "replace", ["a", "b"], ["x", "y"]
    )
    assert statements == []
    assert dropped == ["a", "b"]
