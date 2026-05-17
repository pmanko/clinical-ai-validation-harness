"""Load the test ConceptMap fixture and assert profile invariants.

The fixture contains one identity-bridge element plus four structural-
promotion elements; the real ``datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json``
follows the same shape. The tests exercise the positive parse + the
negative validation surface so the loader functions as the gate that
catches malformed accepted ConceptMaps before they reach the transform.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from harness.conceptmap.load import (
    EXT_BRIDGE_TEMPLATE,
    EXT_POLICY_BUCKET,
    EXT_ROW_COUNT_EXPECTED,
    EXT_SELECTOR_SQL,
    EXT_TARGET_TABLE,
    AcceptedConceptMap,
    load_conceptmap,
)


FIXTURE = Path(__file__).parent / "fixtures" / "minimal.conceptmap.json"


# ---------- positive shape ---------------------------------------------------


@pytest.fixture(scope="module")
def cm() -> AcceptedConceptMap:
    return load_conceptmap(FIXTURE)


def test_top_level_metadata(cm: AcceptedConceptMap):
    assert cm.url == "http://harness.local/test-fixture"
    assert cm.version == "0.0.1"
    assert cm.status == "draft"
    assert cm.source_uri == "http://openmrs.org/concepts/2.7-demo"
    assert cm.target_uri == "http://openmrs.org/concepts/2.8-seeded-ciel"


def test_checksum_matches_file_bytes(cm: AcceptedConceptMap):
    expected = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert cm.raw_checksum == expected


def test_one_bridge_rule_recognized(cm: AcceptedConceptMap):
    bridge = cm.bridge_rule
    assert bridge.is_bridge_rule
    assert not bridge.is_structural_promotion
    assert bridge.equivalence == "equal"
    assert bridge.ext.policy_bucket == "remap"
    assert bridge.ext.bridge_template == "RPAD(source.code, 36, 'A')"


def test_four_promotion_rules_present(cm: AcceptedConceptMap):
    promos = cm.promotion_rules
    assert len(promos) == 4, f"expected 4 promotion rules (P1-P4); got {len(promos)}"
    target_tables = {p.ext.target_table for p in promos}
    assert target_tables == {"drug_order", "conditions", "allergy", "test_order"}


def test_promotion_p1_drug_order_shape(cm: AcceptedConceptMap):
    p1 = next(p for p in cm.promotion_rules if p.ext.target_table == "drug_order")
    assert p1.is_structural_promotion
    assert p1.equivalence == "inexact"
    assert p1.ext.policy_bucket == "seed-augment"
    assert p1.ext.row_count_expected == 43412
    assert "cc.name='Drug'" in (p1.ext.selector_sql or "")


def test_promotion_p2_conditions_shape(cm: AcceptedConceptMap):
    p2 = next(p for p in cm.promotion_rules if p.ext.target_table == "conditions")
    assert p2.ext.row_count_expected == 3642
    assert "concept_id=6042" in (p2.ext.selector_sql or "")


def test_promotion_p3_allergy_shape(cm: AcceptedConceptMap):
    p3 = next(p for p in cm.promotion_rules if p.ext.target_table == "allergy")
    assert p3.ext.row_count_expected == 7
    assert "value_coded=1065" in (p3.ext.selector_sql or "")


def test_promotion_p4_test_order_shape(cm: AcceptedConceptMap):
    p4 = next(p for p in cm.promotion_rules if p.ext.target_table == "test_order")
    assert p4.ext.row_count_expected == 1120
    assert "Test" in (p4.ext.selector_sql or "")
    assert "Coded" in (p4.ext.selector_sql or "")


# ---------- negative validation surface -------------------------------------


def _load_doc() -> dict:
    return json.loads(FIXTURE.read_text())


def _write_tmp(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "mutated.conceptmap.json"
    p.write_text(json.dumps(doc) + "\n")
    return p


def test_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_conceptmap(tmp_path / "does-not-exist.conceptmap.json")


def test_rejects_wrong_resource_type(tmp_path: Path):
    bad = tmp_path / "bundle.json"
    bad.write_text('{"resourceType": "Bundle", "type": "collection"}\n')
    with pytest.raises(Exception) as exc_info:
        load_conceptmap(bad)
    # Could be FHIR pydantic ValidationError or our own ValueError — either is fine.
    msg = str(exc_info.value)
    assert "ConceptMap" in msg or "resourceType" in msg or "type_error" in msg.lower() or "literal" in msg.lower()


def test_rejects_element_with_multiple_targets(tmp_path: Path):
    doc = _load_doc()
    # Duplicate the target so the element has 2 — the profile bans this.
    doc["group"][0]["element"][1]["target"].append(
        copy.deepcopy(doc["group"][0]["element"][1]["target"][0])
    )
    p = _write_tmp(tmp_path, doc)
    with pytest.raises(ValueError, match="exactly one target"):
        load_conceptmap(p)


def test_rejects_target_with_missing_policy_bucket(tmp_path: Path):
    doc = _load_doc()
    # Strip policy-bucket extension from P1's target.
    exts = doc["group"][0]["element"][1]["target"][0]["extension"]
    doc["group"][0]["element"][1]["target"][0]["extension"] = [
        e for e in exts if e.get("url") != EXT_POLICY_BUCKET
    ]
    p = _write_tmp(tmp_path, doc)
    with pytest.raises(ValueError, match="policy-bucket"):
        load_conceptmap(p)


def test_rejects_target_with_unknown_policy_bucket(tmp_path: Path):
    doc = _load_doc()
    # Change P1's policy-bucket to something not in the allowed set.
    for e in doc["group"][0]["element"][1]["target"][0]["extension"]:
        if e.get("url") == EXT_POLICY_BUCKET:
            e["valueCode"] = "wishful-thinking"
    p = _write_tmp(tmp_path, doc)
    with pytest.raises(ValueError, match="policy-bucket"):
        load_conceptmap(p)


def test_rejects_target_with_unknown_equivalence(tmp_path: Path):
    doc = _load_doc()
    doc["group"][0]["element"][1]["target"][0]["equivalence"] = "almost-the-same"
    p = _write_tmp(tmp_path, doc)
    # FHIR pydantic may reject this before our validator runs; either way it raises.
    with pytest.raises(Exception):
        load_conceptmap(p)


def test_rejects_target_with_empty_comment(tmp_path: Path):
    doc = _load_doc()
    doc["group"][0]["element"][1]["target"][0]["comment"] = ""
    p = _write_tmp(tmp_path, doc)
    with pytest.raises(ValueError, match="comment"):
        load_conceptmap(p)


def test_rejects_when_no_bridge_rule_present(tmp_path: Path):
    doc = _load_doc()
    bridge_elem = doc["group"][0]["element"][0]
    bridge_elem["target"][0]["extension"] = [
        e for e in bridge_elem["target"][0]["extension"] if e.get("url") != EXT_BRIDGE_TEMPLATE
    ]
    p = _write_tmp(tmp_path, doc)
    with pytest.raises(ValueError, match="bridge"):
        load_conceptmap(p)


def test_rejects_when_no_promotion_rules_present(tmp_path: Path):
    doc = _load_doc()
    doc["group"][0]["element"] = doc["group"][0]["element"][:1]
    p = _write_tmp(tmp_path, doc)
    with pytest.raises(ValueError, match="promotion"):
        load_conceptmap(p)
