"""Generate the accepted ConceptMap for the 2.7 → 2.8 transform.

The output file lives at ``datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json``.
Shape: one identity-bridge element + one element per structural promotion
rule (P1 drug_order, P2 conditions, P3 allergy, P4 test_order). Profile:
``specs/.../contracts/conceptmap.profile.md``.

This module emits a deterministic JSON (sorted keys, stable formatting)
so re-running the generator on unchanged inputs produces byte-identical
output. The generated file is committed for review diff visibility.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .load import (
    EXT_BRIDGE_TEMPLATE,
    EXT_FIELD_MAPPING,
    EXT_POLICY_BUCKET,
    EXT_ROW_COUNT_EXPECTED,
    EXT_SELECTOR_SQL,
    EXT_SOURCE_RECORD_EXAMPLES,
    EXT_TARGET_TABLE,
)


CONCEPTMAP_URL = "http://harness.local/openmrs-2.7-to-2.8"
SOURCE_URI = "http://openmrs.org/concepts/2.7-demo"
TARGET_URI = "http://openmrs.org/concepts/2.8-seeded-ciel"


def _ext_code(url: str, code: str) -> dict[str, Any]:
    return {"url": url, "valueCode": code}


def _ext_string(url: str, value: str) -> dict[str, Any]:
    return {"url": url, "valueString": value}


def _ext_int(url: str, value: int) -> dict[str, Any]:
    return {"url": url, "valueInteger": value}


def _ext_examples(values: list[str]) -> dict[str, Any]:
    return {"url": EXT_SOURCE_RECORD_EXAMPLES, "valueString": json.dumps(values)}


# ---------- bridge rule ----------


def _bridge_element() -> dict[str, Any]:
    return {
        "code": "*",
        "display": "Identity bridge — every legacy concept_id N rebinds to the seeded CIEL concept with uuid RPAD(N, 36, 'A').",
        "target": [{
            "code": "{source.code}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "display": "Seeded CIEL concept resolved by UUID pattern.",
            "equivalence": "equal",
            "comment": (
                "The 2.7 demo dump uses AMPATH-style concept numbering; CIEL stores its "
                "concepts with UUIDs in the pattern <canonical_id>AAAA...A (32 A's). "
                "Measured 100% coverage on the 457 concepts referenced by obs in the "
                "current corpus. Identity rebind; reviewer rationale: AMPATH FSN strings "
                "match CIEL FSN strings modulo case. See data-model.md §R-bridge-rule."
            ),
            "extension": [
                _ext_code(EXT_POLICY_BUCKET, "remap"),
                _ext_examples([]),
                _ext_string(EXT_BRIDGE_TEMPLATE, "RPAD(CAST(source.code AS CHAR), 36, 'A')"),
            ],
        }],
    }


# ---------- structural promotions (P1-P4) ----------


def _promotion(*, source_code: str, source_display: str, target_table: str,
               target_display: str, comment: str, selector_sql: str,
               field_mapping: dict[str, str], row_count_expected: int,
               source_record_examples: list[str]) -> dict[str, Any]:
    return {
        "code": source_code,
        "display": source_display,
        "target": [{
            "code": f"$table:{target_table}",
            "display": target_display,
            "equivalence": "inexact",
            "comment": comment,
            "extension": [
                _ext_code(EXT_POLICY_BUCKET, "seed-augment"),
                _ext_examples(source_record_examples),
                _ext_string(EXT_SELECTOR_SQL, selector_sql),
                _ext_string(EXT_TARGET_TABLE, target_table),
                _ext_string(EXT_FIELD_MAPPING, json.dumps(field_mapping)),
                _ext_int(EXT_ROW_COUNT_EXPECTED, row_count_expected),
            ],
        }],
    }


def _promotion_p1_drug_order() -> dict[str, Any]:
    return _promotion(
        source_code="$selector:value_coded.concept_class=Drug",
        source_display="P1 — obs whose value_coded is a Drug-class concept.",
        target_table="drug_order",
        target_display="drug_order rows synthesized from obs.",
        comment=(
            "Coded drug answers on obs are promoted to drug_order. Top answers in the "
            "current corpus: LAMIVUDINE, STAVUDINE, NEVIRAPINE, TRIMETHOPRIM+SULFA, "
            "ISONIAZID, EFAVIRENZ, plus vaccines (DTP, polio, HepB, Hib, measles). "
            "See data-model.md §R-promotion-rules and research.md §R-typed-table-promotion "
            "for cross-cutting decisions (Q1 obs preservation via obs.order_id, Q2 UUID v5, "
            "Q3 vaccines emit as drug_order, Q4 orderer from encounter_provider)."
        ),
        selector_sql=(
            "SELECT o.obs_id, o.person_id, o.encounter_id, o.value_coded AS drug_concept_id, o.obs_datetime "
            "FROM legacy_27_raw.obs o "
            "JOIN legacy_27_raw.concept c ON c.concept_id = o.value_coded "
            "JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id "
            "WHERE cc.name = 'Drug' AND o.voided = 0"
        ),
        field_mapping={
            "patient_id":        "obs.person_id",
            "encounter_id":      "obs.encounter_id",
            "concept_id":        "lookup(obs.value_coded → CIEL via concept_translation)",
            "start_date":        "obs.obs_datetime",
            "orderer":           "encounter_provider.provider_id; fallback obs.creator",
            "urgency":           "'ROUTINE'",
            "uuid":              "UUIDv5(obs.uuid, 'drug_order')",
        },
        row_count_expected=43412,
        source_record_examples=["obs_id:1088001", "obs_id:1088002", "obs_id:625001"],
    )


def _promotion_p2_conditions() -> dict[str, Any]:
    return _promotion(
        source_code="$selector:concept_id=6042",
        source_display="P2 — obs whose question concept is 6042 (PROBLEM ADDED).",
        target_table="conditions",
        target_display="conditions rows synthesized from obs.",
        comment=(
            "PROBLEM ADDED is the semantic anchor for 'clinician recorded a new diagnosis "
            "this visit'. value_coded is the diagnosis concept (rebound via the bridge "
            "rule). 114 distinct diagnoses in the current corpus. See data-model.md "
            "§R-promotion-rules."
        ),
        selector_sql=(
            "SELECT o.obs_id, o.person_id, o.encounter_id, o.value_coded AS dx_concept_id, o.obs_datetime "
            "FROM legacy_27_raw.obs o "
            "WHERE o.concept_id = 6042 AND o.value_coded IS NOT NULL AND o.voided = 0"
        ),
        field_mapping={
            "patient_id":         "obs.person_id",
            "encounter_id":       "obs.encounter_id",
            "condition_coded":    "lookup(obs.value_coded → CIEL via concept_translation)",
            "clinical_status":    "'ACTIVE'",
            "onset_date":         "obs.obs_datetime",
            "date_created":       "obs.date_created",
            "creator":            "obs.creator",
            "uuid":               "UUIDv5(obs.uuid, 'conditions')",
        },
        row_count_expected=3642,
        source_record_examples=["obs_id:6042001", "obs_id:6042002"],
    )


def _promotion_p3_allergy() -> dict[str, Any]:
    return _promotion(
        source_code="$selector:concept_id_in_{6011,6012,1083}_and_value=1065",
        source_display="P3 — drug-allergy boolean questions answered YES.",
        target_table="allergy",
        target_display="allergy rows synthesized from obs.",
        comment=(
            "Three explicit drug-allergy questions: 6011 PENICILLIN, 6012 SULFA, "
            "1083 OTHER MEDICINE. Promotion only on value_coded=1065 ('YES'); NO "
            "answers do NOT promote (absence of allergy is not an allergy row). "
            "Extremely sparse in the current corpus (7 obs total). Allergen substance "
            "concept is hand-picked per question concept at acceptance time. "
            "See data-model.md §R-promotion-rules."
        ),
        selector_sql=(
            "SELECT o.obs_id, o.person_id, o.encounter_id, o.concept_id AS allergen_question, o.obs_datetime "
            "FROM legacy_27_raw.obs o "
            "WHERE o.concept_id IN (6011, 6012, 1083) AND o.value_coded = 1065 AND o.voided = 0"
        ),
        field_mapping={
            "patient_id":           "obs.person_id",
            "coded_allergen":       "allergen-substance pick per question concept (hand-curated)",
            "allergen_type":        "'DRUG'",
            "severity_concept_id":  "NULL (not recorded in legacy boolean form)",
            "encounter_id":         "obs.encounter_id",
            "date_created":         "obs.date_created",
            "creator":              "obs.creator",
            "uuid":                 "UUIDv5(obs.uuid, 'allergy')",
        },
        row_count_expected=7,
        source_record_examples=["obs_id:6011001"],
    )


def _promotion_p4_test_order() -> dict[str, Any]:
    return _promotion(
        source_code="$selector:concept.class=Test_and_datatype=Coded",
        source_display="P4 — obs whose question concept is Test-class with Coded datatype.",
        target_table="test_order",
        target_display="test_order rows synthesized from obs.",
        comment=(
            "Test-class concepts with Coded datatype are lab/imaging orders. Top "
            "questions in the current corpus: IMMUNIZATIONS ORDERED (891), X-RAY "
            "CHEST (172), VDRL (33), HIV DNA PCR (15), HIV ENZYME IMMUNOASSAY (9). "
            "test_order.concept_id is the TEST concept (obs.concept_id, not value_coded). "
            "The source obs is preserved as the result row, linked via obs.order_id. "
            "See data-model.md §R-promotion-rules."
        ),
        selector_sql=(
            "SELECT o.obs_id, o.person_id, o.encounter_id, o.concept_id AS test_concept, o.value_coded AS result_coded, o.obs_datetime "
            "FROM legacy_27_raw.obs o "
            "JOIN legacy_27_raw.concept c ON c.concept_id = o.concept_id "
            "JOIN legacy_27_raw.concept_class cc ON cc.concept_class_id = c.class_id "
            "JOIN legacy_27_raw.concept_datatype cd ON cd.concept_datatype_id = c.datatype_id "
            "WHERE cc.name = 'Test' AND cd.name = 'Coded' AND o.voided = 0"
        ),
        field_mapping={
            "patient_id":     "obs.person_id",
            "concept_id":     "lookup(obs.concept_id → CIEL via concept_translation)",
            "encounter_id":   "obs.encounter_id",
            "date_activated": "obs.obs_datetime",
            "urgency":        "'ROUTINE'",
            "order_action":   "'NEW'",
            "uuid":           "UUIDv5(obs.uuid, 'test_order')",
        },
        row_count_expected=1120,
        source_record_examples=["obs_id:984001", "obs_id:12001"],
    )


# ---------- top-level resource ----------


def build_conceptmap(version: str = "0.1.0") -> dict[str, Any]:
    return {
        "resourceType": "ConceptMap",
        "url": CONCEPTMAP_URL,
        "version": version,
        "status": "active",
        "experimental": False,
        "name": "OpenMRS27To28SeededCiel",
        "title": "OpenMRS 2.7 demo → 2.8 RefApp seeded-CIEL",
        "sourceUri": SOURCE_URI,
        "targetUri": TARGET_URI,
        "group": [{
            "source": SOURCE_URI,
            "target": TARGET_URI,
            "element": [
                _bridge_element(),
                _promotion_p1_drug_order(),
                _promotion_p2_conditions(),
                _promotion_p3_allergy(),
                _promotion_p4_test_order(),
            ],
        }],
    }


def write_conceptmap(path: Path | str, version: str = "0.1.0") -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_conceptmap(version=version)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m harness.conceptmap.write")
    p.add_argument(
        "--out", default="datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json",
        help="Output path; default datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json",
    )
    p.add_argument("--version", default="0.1.0", help="ConceptMap.version (semver)")
    args = p.parse_args(argv)
    written = write_conceptmap(args.out, version=args.version)
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
