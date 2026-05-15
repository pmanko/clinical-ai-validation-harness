"""Unit tests for the schema-diff pure-logic surface (no DB).

Validates the §R5 classifier rules and the diff orchestration against
synthetic ``TableSchema`` inputs. DB-backed integration tests live in
``test_schema_diff_contract.py``.
"""

from __future__ import annotations

import pytest

from harness.schema_diff import (
    CLINICAL_TABLES,
    ColumnInfo,
    ForeignKey,
    IndexInfo,
    TableSchema,
    _is_clinically_loaded_column,
    classify_column_diff,
    classify_table_diff,
    diff_shared_table,
    diff_table_inventories,
)


# ---------- classifier: tables ----------


def test_clinical_table_populated_is_meaningful():
    cm, why = classify_table_diff(
        "obs", populated_in_source=True, in_target=False, in_source=True,
    )
    assert cm is True
    assert "populated" in why
    assert "obs" in why


def test_clinical_table_unpopulated_is_still_meaningful_for_target_side_changes():
    cm, why = classify_table_diff(
        "drug_order", populated_in_source=False, in_target=True, in_source=False,
    )
    assert cm is True
    assert "drug_order" in why


def test_non_clinical_table_is_cosmetic():
    cm, why = classify_table_diff(
        "session_log", populated_in_source=True, in_target=False, in_source=True,
    )
    assert cm is False
    assert why == ""


@pytest.mark.parametrize("table", sorted(CLINICAL_TABLES))
def test_every_clinical_table_classifies_as_meaningful(table):
    cm, _ = classify_table_diff(
        table, populated_in_source=True, in_target=True, in_source=True,
    )
    assert cm is True


# ---------- classifier: columns ----------


@pytest.mark.parametrize("col_name,col_key,expected", [
    ("person_id",       "PRI", True),   # PK
    ("encounter_id",    "MUL", True),   # FK
    ("uuid",            "UNI", True),   # unique
    ("value_coded",     "MUL", True),   # FK + coded suffix
    ("concept_id",      "MUL", True),   # FK + concept
    ("dx_concept_id",   "",    True),   # *_concept_id suffix
    ("severity_coded",  "",    True),   # *_coded suffix
    ("comments",        "",    False),  # cosmetic
    ("date_created",    "",    False),
    ("voided",          "",    False),
])
def test_clinically_loaded_column_detector(col_name, col_key, expected):
    assert _is_clinically_loaded_column(col_name, col_key) is expected


def test_column_on_clinical_populated_table_is_meaningful():
    col = ColumnInfo(name="comments", data_type="varchar", column_type="varchar(255)",
                     is_nullable=True, column_key="")
    cm, why = classify_column_diff("obs", col, populated_in_source=True)
    assert cm is True
    assert "obs" in why
    assert "populated" in why


def test_column_with_clinical_role_is_meaningful_anywhere():
    col = ColumnInfo(name="value_coded", data_type="int", column_type="int(11)",
                     is_nullable=True, column_key="MUL")
    cm, why = classify_column_diff("some_random_table", col, populated_in_source=False)
    assert cm is True
    assert "FK" in why or "concept" in why or "coded" in why


def test_pure_cosmetic_column_is_cosmetic():
    col = ColumnInfo(name="comments", data_type="varchar", column_type="varchar(255)",
                     is_nullable=True, column_key="")
    cm, why = classify_column_diff("session_log", col, populated_in_source=True)
    assert cm is False
    assert why == ""


# ---------- diff_table_inventories ----------


def test_only_in_source_yields_table_only_in_source_items():
    items = diff_table_inventories(
        source={"obs", "patient", "weird_legacy_table"},
        target={"obs", "patient"},
        source_populated={"obs", "patient", "weird_legacy_table"},
    )
    ids = {it["id"] for it in items}
    cats = {it["category"] for it in items}
    assert any("weird_legacy_table" in i for i in ids)
    assert "table_only_in_source" in cats


def test_only_in_target_yields_table_only_in_target_items():
    items = diff_table_inventories(
        source={"obs"}, target={"obs", "new_2_8_table"},
        source_populated={"obs"},
    )
    cats = [it["category"] for it in items]
    assert "table_only_in_target" in cats


def test_shared_tables_dont_appear_in_inventory_diff():
    items = diff_table_inventories(
        source={"obs", "patient"}, target={"obs", "patient"},
        source_populated={"obs"},
    )
    assert items == []


def test_inventory_diff_is_deterministic_on_set_inputs():
    a = diff_table_inventories({"a", "b"}, {"c"}, source_populated={"a"})
    b = diff_table_inventories({"a", "b"}, {"c"}, source_populated={"a"})
    assert a == b


# ---------- diff_shared_table ----------


def _col(name, key="", t="int(11)"):
    return ColumnInfo(name=name, data_type=t.split("(")[0],
                      column_type=t, is_nullable=True, column_key=key)


def test_added_column_in_target_is_column_added():
    src = TableSchema(name="obs", columns={"obs_id": _col("obs_id", "PRI")})
    tgt = TableSchema(name="obs", columns={
        "obs_id": _col("obs_id", "PRI"),
        "form_namespace_and_path": _col("form_namespace_and_path", t="varchar(255)"),
    })
    items = diff_shared_table("obs", src, tgt, populated_in_source=True)
    assert any(it["category"] == "column_added"
               and it["details"]["column"] == "form_namespace_and_path"
               for it in items)


def test_removed_column_in_target_is_column_removed():
    src = TableSchema(name="obs", columns={
        "obs_id": _col("obs_id", "PRI"),
        "ancient_field": _col("ancient_field", t="varchar(50)"),
    })
    tgt = TableSchema(name="obs", columns={"obs_id": _col("obs_id", "PRI")})
    items = diff_shared_table("obs", src, tgt, populated_in_source=True)
    assert any(it["category"] == "column_removed"
               and it["details"]["column"] == "ancient_field"
               for it in items)


def test_retyped_column_is_column_retyped():
    src = TableSchema(name="obs", columns={
        "obs_id": _col("obs_id", "PRI"),
        "value_complex": _col("value_complex", t="varchar(1000)"),
    })
    tgt = TableSchema(name="obs", columns={
        "obs_id": _col("obs_id", "PRI"),
        "value_complex": _col("value_complex", t="text"),
    })
    items = diff_shared_table("obs", src, tgt, populated_in_source=True)
    retypes = [it for it in items if it["category"] == "column_retyped"]
    assert len(retypes) == 1
    assert retypes[0]["details"]["source_type"] == "varchar(1000)"
    assert retypes[0]["details"]["target_type"] == "text"


def test_identical_columns_yield_no_diff():
    cols = {
        "obs_id": _col("obs_id", "PRI"),
        "value_numeric": _col("value_numeric", t="double"),
    }
    src = TableSchema(name="obs", columns=cols)
    tgt = TableSchema(name="obs", columns=cols)
    items = diff_shared_table("obs", src, tgt, populated_in_source=True)
    # No column_added/removed/retyped items.
    assert not any(it["category"].startswith("column_") for it in items)


def test_index_only_in_source_is_index_difference():
    src = TableSchema(name="obs", columns={"obs_id": _col("obs_id", "PRI")},
                      indexes={"PRIMARY": IndexInfo("PRIMARY", ("obs_id",), False),
                               "legacy_obs_creator_fk": IndexInfo("legacy_obs_creator_fk", ("creator",), True)})
    tgt = TableSchema(name="obs", columns={"obs_id": _col("obs_id", "PRI")},
                      indexes={"PRIMARY": IndexInfo("PRIMARY", ("obs_id",), False)})
    items = diff_shared_table("obs", src, tgt, populated_in_source=True)
    assert any(it["category"] == "index_difference"
               and "legacy_obs_creator_fk" in it["id"] for it in items)


def test_fk_only_in_target_is_constraint_difference_and_clinically_meaningful_on_clinical_table():
    src = TableSchema(name="obs", columns={"obs_id": _col("obs_id", "PRI")},
                      foreign_keys=[])
    tgt = TableSchema(name="obs", columns={"obs_id": _col("obs_id", "PRI")},
                      foreign_keys=[ForeignKey("obs_form_fk", "form_id",
                                               "form", "form_id")])
    items = diff_shared_table("obs", src, tgt, populated_in_source=True)
    cdiffs = [it for it in items if it["category"] == "constraint_difference"]
    assert len(cdiffs) == 1
    assert cdiffs[0]["clinical_meaningful"] is True


def test_fk_difference_on_non_clinical_table_is_cosmetic():
    src = TableSchema(name="session_log", columns={"id": _col("id", "PRI")},
                      foreign_keys=[])
    tgt = TableSchema(name="session_log", columns={"id": _col("id", "PRI")},
                      foreign_keys=[ForeignKey("sl_user_fk", "user_id",
                                               "users", "user_id")])
    items = diff_shared_table("session_log", src, tgt, populated_in_source=True)
    cdiffs = [it for it in items if it["category"] == "constraint_difference"]
    assert len(cdiffs) == 1
    assert cdiffs[0]["clinical_meaningful"] is False


# ---------- contract shape ----------


def test_every_table_diff_item_has_required_top_level_keys():
    items = diff_table_inventories(
        source={"obs", "weird"}, target={"new_table"},
        source_populated={"obs"},
    )
    for it in items:
        # Per contracts/schema_diff.schema.yaml.
        assert "id" in it
        assert "category" in it
        assert "clinical_meaningful" in it


def test_clinical_meaningful_items_carry_rationale():
    items = diff_table_inventories(
        source={"obs"}, target=set(),
        source_populated={"obs"},
    )
    for it in items:
        if it["clinical_meaningful"]:
            assert it.get("clinical_meaningful_rationale"), (
                f"item {it['id']} is clinically meaningful but has no rationale"
            )


def test_category_values_are_within_contract_enum():
    allowed = {
        "table_only_in_source", "table_only_in_target",
        "column_added", "column_removed", "column_retyped",
        "index_difference", "constraint_difference",
        "module_owned", "liquibase_changeset_delta",
    }
    src = TableSchema(name="obs", columns={
        "obs_id": _col("obs_id", "PRI"),
        "ancient": _col("ancient", t="int(11)"),
    }, indexes={"i": IndexInfo("i", ("obs_id",), True)},
       foreign_keys=[ForeignKey("fk", "obs_id", "obs", "obs_id")])
    tgt = TableSchema(name="obs", columns={
        "obs_id": _col("obs_id", "PRI"),
        "new_col": _col("new_col", t="varchar"),
    })
    inv = diff_table_inventories({"obs"}, {"obs"}, source_populated={"obs"})
    shared = diff_shared_table("obs", src, tgt, populated_in_source=True)
    for it in inv + shared:
        assert it["category"] in allowed, f"unknown category {it['category']!r}"
