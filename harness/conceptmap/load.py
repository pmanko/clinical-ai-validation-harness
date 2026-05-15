"""Parse the accepted FHIR R4 ConceptMap (T013).

Returns typed dataclasses that downstream code (seed_emit, transform
orchestrator, audits) can consume. The shape we expect is small — see
`specs/002-openmrs-demo-data-2-8-remap/contracts/conceptmap.profile.md`
§Expected shape:

  - 1 identity-bridge element (encodes the §R-bridge-rule UUID pattern)
  - N structural-promotion elements (P1-P4 for feature 002)

We use the `fhir.resources` library for FHIR R4 schema-level validation
of the resource shell; the harness-specific extensions are read out as
raw dicts since they're our own URLs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HARNESS_EXT_BASE = "http://harness.local/StructureDefinition"
EXT_POLICY_BUCKET = f"{HARNESS_EXT_BASE}/policy-bucket"
EXT_SOURCE_RECORD_EXAMPLES = f"{HARNESS_EXT_BASE}/source-record-examples"
EXT_SEED_AUGMENT_CLASS = f"{HARNESS_EXT_BASE}/seed-augment-class"
EXT_SEED_AUGMENT_REF_TERM = f"{HARNESS_EXT_BASE}/seed-augment-reference-term"
# M2-A additions for structural promotions:
EXT_SELECTOR_SQL = f"{HARNESS_EXT_BASE}/selector-sql"
EXT_TARGET_TABLE = f"{HARNESS_EXT_BASE}/target-table"
EXT_FIELD_MAPPING = f"{HARNESS_EXT_BASE}/field-mapping"
EXT_ROW_COUNT_EXPECTED = f"{HARNESS_EXT_BASE}/row-count-expected"
# Bridge-rule marker (only on element 0; opaque flag):
EXT_BRIDGE_TEMPLATE = f"{HARNESS_EXT_BASE}/bridge-template"


@dataclass
class HarnessExtensions:
    """Parsed harness-extension values from one `target.extension[]` block."""

    policy_bucket: str                          # 'remap' | 'seed-augment' | 'drop'
    source_record_examples: list[str] = field(default_factory=list)
    seed_augment_class: str | None = None       # only when policy-bucket=seed-augment
    seed_augment_reference_term: str | None = None
    # Structural-promotion fields (only on P1-P4 elements):
    selector_sql: str | None = None
    target_table: str | None = None
    field_mapping: dict[str, str] | None = None
    row_count_expected: int | None = None
    # Bridge-rule marker (only on element 0):
    bridge_template: str | None = None


@dataclass
class ConceptMapElement:
    """One `group.element` with its single `target`.

    Element 0 in feature 002 is the identity-bridge rule; elements 1+
    are structural promotions.
    """

    source_code: str
    source_display: str | None
    target_code: str
    target_display: str | None
    equivalence: str            # FHIR R4 equivalence label
    comment: str
    ext: HarnessExtensions

    @property
    def is_bridge_rule(self) -> bool:
        return self.ext.bridge_template is not None

    @property
    def is_structural_promotion(self) -> bool:
        return self.ext.target_table is not None and self.ext.selector_sql is not None


@dataclass
class AcceptedConceptMap:
    """The whole parsed ConceptMap, ready for downstream consumption."""

    url: str
    version: str
    status: str
    source_uri: str
    target_uri: str
    elements: list[ConceptMapElement]
    raw_path: Path
    raw_checksum: str           # SHA-256 of the file bytes

    @property
    def bridge_rule(self) -> ConceptMapElement:
        bridges = [e for e in self.elements if e.is_bridge_rule]
        if len(bridges) != 1:
            raise ValueError(
                f"expected exactly 1 bridge rule, found {len(bridges)} in {self.raw_path}"
            )
        return bridges[0]

    @property
    def promotion_rules(self) -> list[ConceptMapElement]:
        return [e for e in self.elements if e.is_structural_promotion]


def _read_ext(ext_array: list[dict[str, Any]] | None, url: str) -> Any:
    """Extract a single extension value by URL from a FHIR `extension[]` array."""
    if not ext_array:
        return None
    for e in ext_array:
        if e.get("url") == url:
            # FHIR extensions use one of valueX where X depends on type.
            for key, val in e.items():
                if key.startswith("value") and key != "valueX":
                    return val
            # Some are nested as `extension[]` for compound — handle inline.
            if "extension" in e:
                return e["extension"]
    return None


def _parse_extensions(target: dict[str, Any]) -> HarnessExtensions:
    exts = target.get("extension") or []
    examples = _read_ext(exts, EXT_SOURCE_RECORD_EXAMPLES) or []
    if not isinstance(examples, list):
        examples = []

    field_mapping_raw = _read_ext(exts, EXT_FIELD_MAPPING)
    if isinstance(field_mapping_raw, str):
        # JSON-encoded blob
        try:
            field_mapping_raw = json.loads(field_mapping_raw)
        except json.JSONDecodeError:
            field_mapping_raw = None
    if not isinstance(field_mapping_raw, dict):
        field_mapping_raw = None

    row_count_raw = _read_ext(exts, EXT_ROW_COUNT_EXPECTED)
    row_count = int(row_count_raw) if isinstance(row_count_raw, (int, str)) and str(row_count_raw).lstrip("-").isdigit() else None

    return HarnessExtensions(
        policy_bucket=_read_ext(exts, EXT_POLICY_BUCKET) or "",
        source_record_examples=list(examples),
        seed_augment_class=_read_ext(exts, EXT_SEED_AUGMENT_CLASS),
        seed_augment_reference_term=_read_ext(exts, EXT_SEED_AUGMENT_REF_TERM),
        selector_sql=_read_ext(exts, EXT_SELECTOR_SQL),
        target_table=_read_ext(exts, EXT_TARGET_TABLE),
        field_mapping=field_mapping_raw,
        row_count_expected=row_count,
        bridge_template=_read_ext(exts, EXT_BRIDGE_TEMPLATE),
    )


ALLOWED_POLICY_BUCKETS = {"remap", "seed-augment", "drop"}
ALLOWED_EQUIVALENCES = {
    "equivalent", "equal", "wider", "narrower",
    "inexact", "unmatched", "disjoint", "relatedto",
}


def _parse_element(raw: dict[str, Any]) -> ConceptMapElement:
    target_list = raw.get("target") or []
    if len(target_list) != 1:
        raise ValueError(
            f"profile requires exactly one target per element; got {len(target_list)} "
            f"for source code {raw.get('code')!r}"
        )
    t = target_list[0]
    src_code = raw.get("code") or ""
    equivalence = t.get("equivalence") or ""
    if equivalence not in ALLOWED_EQUIVALENCES:
        raise ValueError(
            f"target.equivalence={equivalence!r} for source {src_code!r} not in allowed set "
            f"{sorted(ALLOWED_EQUIVALENCES)}"
        )
    comment = t.get("comment") or ""
    if not comment.strip():
        raise ValueError(
            f"target.comment is required (non-empty) per the profile; source {src_code!r} is empty"
        )
    ext = _parse_extensions(t)
    if not ext.policy_bucket:
        raise ValueError(
            f"required harness extension {EXT_POLICY_BUCKET!r} is missing on source {src_code!r}"
        )
    if ext.policy_bucket not in ALLOWED_POLICY_BUCKETS:
        raise ValueError(
            f"policy-bucket={ext.policy_bucket!r} on source {src_code!r} not in allowed set "
            f"{sorted(ALLOWED_POLICY_BUCKETS)}"
        )
    return ConceptMapElement(
        source_code=src_code,
        source_display=raw.get("display"),
        target_code=t.get("code") or "",
        target_display=t.get("display"),
        equivalence=equivalence,
        comment=comment,
        ext=ext,
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_conceptmap(path: Path | str) -> AcceptedConceptMap:
    """Load + validate the accepted ConceptMap at `path`.

    Validates:
      - Resource shell parses as FHIR R4 (via fhir.resources)
      - Exactly one bridge rule + at least one promotion rule
      - Every element has exactly one target
      - Every target has the required harness extensions
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"ConceptMap not found at {p}")
    raw_bytes = p.read_bytes()
    obj = json.loads(raw_bytes)

    # FHIR R4 shell validation.
    from fhir.resources.R4B.conceptmap import ConceptMap as FhirConceptMap  # noqa: PLC0415
    FhirConceptMap(**obj)  # raises ValidationError on shape problems

    if obj.get("resourceType") != "ConceptMap":
        raise ValueError(f"resourceType must be 'ConceptMap'; got {obj.get('resourceType')!r}")

    groups = obj.get("group") or []
    if not groups:
        raise ValueError("ConceptMap has no groups; expected at least one")

    elements: list[ConceptMapElement] = []
    for g in groups:
        for raw_elem in g.get("element") or []:
            elements.append(_parse_element(raw_elem))

    cm = AcceptedConceptMap(
        url=obj.get("url") or "",
        version=obj.get("version") or "",
        status=obj.get("status") or "",
        source_uri=obj.get("sourceUri") or "",
        target_uri=obj.get("targetUri") or "",
        elements=elements,
        raw_path=p,
        raw_checksum=_sha256_file(p),
    )

    # Profile invariants — surface early so seed_emit / orchestrator don't have to.
    _ = cm.bridge_rule  # raises if 0 or >1 bridge rules present
    if not cm.promotion_rules:
        raise ValueError("expected at least one structural-promotion element; found none")
    return cm


__all__ = [
    "AcceptedConceptMap",
    "ConceptMapElement",
    "HarnessExtensions",
    "load_conceptmap",
    # Extension URL constants:
    "EXT_POLICY_BUCKET",
    "EXT_SOURCE_RECORD_EXAMPLES",
    "EXT_SEED_AUGMENT_CLASS",
    "EXT_SEED_AUGMENT_REF_TERM",
    "EXT_SELECTOR_SQL",
    "EXT_TARGET_TABLE",
    "EXT_FIELD_MAPPING",
    "EXT_ROW_COUNT_EXPECTED",
    "EXT_BRIDGE_TEMPLATE",
]
