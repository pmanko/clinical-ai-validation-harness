"""Generate the accepted ConceptMap and assert it loads back cleanly."""

from __future__ import annotations

from pathlib import Path

from harness.conceptmap.load import load_conceptmap
from harness.conceptmap.write import build_conceptmap, write_conceptmap


def test_build_emits_one_bridge_and_four_promotions():
    doc = build_conceptmap()
    elements = doc["group"][0]["element"]
    assert len(elements) == 5
    # Element 0 is the bridge rule.
    bridge_target = elements[0]["target"][0]
    bridge_ext_urls = {e["url"] for e in bridge_target["extension"]}
    assert "http://harness.local/StructureDefinition/bridge-template" in bridge_ext_urls
    # Elements 1-4 are promotions with target tables.
    target_tables = []
    for element in elements[1:]:
        ext = element["target"][0]["extension"]
        for e in ext:
            if e["url"] == "http://harness.local/StructureDefinition/target-table":
                target_tables.append(e["valueString"])
    assert sorted(target_tables) == ["allergy", "conditions", "drug_order", "test_order"]


def test_written_file_is_deterministic(tmp_path: Path):
    p1 = write_conceptmap(tmp_path / "a.conceptmap.json")
    p2 = write_conceptmap(tmp_path / "b.conceptmap.json")
    assert p1.read_bytes() == p2.read_bytes()


def test_written_file_loads_back_via_loader(tmp_path: Path):
    out = write_conceptmap(tmp_path / "round_trip.conceptmap.json")
    cm = load_conceptmap(out)
    assert cm.url == "http://harness.local/openmrs-2.7-to-2.8"
    assert cm.version == "0.1.0"
    assert cm.status == "active"
    assert cm.bridge_rule.ext.bridge_template == "RPAD(CAST(source.code AS CHAR), 36, 'A')"
    promos = cm.promotion_rules
    assert len(promos) == 4
    by_table = {p.ext.target_table: p for p in promos}
    assert by_table["drug_order"].ext.row_count_expected == 43412
    assert by_table["conditions"].ext.row_count_expected == 3642
    assert by_table["allergy"].ext.row_count_expected == 7
    assert by_table["test_order"].ext.row_count_expected == 1120


def test_field_mapping_is_round_trippable_json(tmp_path: Path):
    out = write_conceptmap(tmp_path / "rt.conceptmap.json")
    cm = load_conceptmap(out)
    p1 = next(p for p in cm.promotion_rules if p.ext.target_table == "drug_order")
    assert p1.ext.field_mapping is not None
    assert p1.ext.field_mapping["patient_id"] == "obs.person_id"
    assert "encounter_id" in p1.ext.field_mapping


def test_no_extension_url_typos_in_generated_doc():
    doc = build_conceptmap()
    seen_urls = set()
    for element in doc["group"][0]["element"]:
        for e in element["target"][0]["extension"]:
            seen_urls.add(e["url"])
    # Every extension URL must be one of the harness URLs we declared.
    from harness.conceptmap.load import (
        EXT_BRIDGE_TEMPLATE,
        EXT_FIELD_MAPPING,
        EXT_POLICY_BUCKET,
        EXT_ROW_COUNT_EXPECTED,
        EXT_SELECTOR_SQL,
        EXT_SOURCE_RECORD_EXAMPLES,
        EXT_TARGET_TABLE,
    )
    allowed = {
        EXT_POLICY_BUCKET, EXT_SOURCE_RECORD_EXAMPLES,
        EXT_SELECTOR_SQL, EXT_TARGET_TABLE, EXT_FIELD_MAPPING,
        EXT_ROW_COUNT_EXPECTED, EXT_BRIDGE_TEMPLATE,
    }
    unknown = seen_urls - allowed
    assert not unknown, f"unknown extension URLs emitted: {unknown}"
