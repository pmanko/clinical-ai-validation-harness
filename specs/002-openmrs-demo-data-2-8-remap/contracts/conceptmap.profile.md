# ConceptMap Profile (harness-local)

**Standard**: FHIR R4 ConceptMap (`http://hl7.org/fhir/ConceptMap`)
**Validated by**: HL7 FHIR Validator CLI (unmodified release)
**File**: `datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json`

## Scope and intent

This is a **profile** of FHIR R4 ConceptMap — i.e., it tightens the standard's optionality without modifying its semantics. Any artifact conformant to this profile is also conformant to the underlying FHIR R4 ConceptMap resource, so conformance attestation routes through the standard's own tool (FR-028, SC-011).

The ConceptMap describes the translation from the 2.7 source dump's concept dictionary to the 2.8 RefApp's seeded CIEL dictionary. CIEL via OCL is the terminology authority; LOINC/SNOMED/ICD-10/RxNorm are referenced terminologies; FHIR ConceptMap is the *grammar*.

## Required elements

### Resource level

| Element | Profile requirement |
|---|---|
| `ConceptMap.url` | MUST be `http://harness.local/openmrs-2.7-to-2.8` |
| `ConceptMap.version` | MUST be a semver string; bumped on any element-level change |
| `ConceptMap.status` | MUST be `draft` (advisory) or `active` (accepted/reviewed). Only `active` may be consumed by SQLMesh. |
| `ConceptMap.sourceUri` | MUST be `http://openmrs.org/concepts/2.7-demo` |
| `ConceptMap.targetUri` | MUST be `http://openmrs.org/concepts/2.8-seeded-ciel` |
| `ConceptMap.experimental` | RECOMMENDED `true` for advisory drafts; `false` for accepted artifacts |

### `ConceptMap.group[]`

The artifact MAY use multiple groups when the source or target concepts are partitioned by source system (e.g., a group per source `concept_reference_source`). One group is sufficient when all translations target the same seeded CIEL.

### `ConceptMap.group.element[]`

| Element | Profile requirement |
|---|---|
| `element.code` | Source concept_id or UUID from the 2.7 dump |
| `element.display` | Source concept display name (sanity for reviewers) |
| `element.target[]` | MUST have exactly one target per element under this profile (multi-target is reserved for future use) |

### `ConceptMap.group.element.target[]`

| Element | Profile requirement |
|---|---|
| `target.code` | Target seeded-CIEL concept_id or UUID |
| `target.display` | Target concept display name |
| `target.equivalence` | MUST be one of: `equivalent`, `equal`, `wider`, `narrower`, `inexact`, `unmatched`, `disjoint`. `relatedto` and `unmatched` MUST carry a non-empty `target.comment`. |
| `target.comment` | MUST be non-empty; carries reviewer rationale |
| `target.extension[]` | MUST include the two harness extensions below |

### Required harness extensions on `target.extension[]`

| URL | Value | Required |
|---|---|---|
| `http://harness.local/StructureDefinition/policy-bucket` | `code` in `[remap, seed-augment, drop]` | YES |
| `http://harness.local/StructureDefinition/source-record-examples` | Array of strings; up to 3 source record identifiers (e.g., `obs_id:12345`, `drug_order_id:678`) | YES (may be empty array if no clinical records reference this source concept yet) |
| `http://harness.local/StructureDefinition/seed-augment-class` | Required only when `policy-bucket = seed-augment`; one of `Test`, `LabSet`, `Drug`, `Diagnosis`, `Finding`, `Symptom` (per research.md §R6) | conditional |
| `http://harness.local/StructureDefinition/seed-augment-reference-term` | Required only when `policy-bucket = seed-augment`; published reference term `<system>:<code>` (e.g., `LOINC:1751-7`) | conditional |

### Cross-element constraints

- Every source concept_id referenced by ≥1 row in the corpus's clinical tables (obs, conditions, diagnosis, allergy, drug_order, encounter_diagnosis, concept_set) MUST appear as an `element` in this ConceptMap.
- `policy-bucket = drop` elements MUST also carry `target.equivalence = unmatched` and a `target.comment` explaining the clinical impact of dropping.
- `policy-bucket = seed-augment` elements MUST be limited to the concept classes enumerated in research.md §R6 (`Test`, `LabSet`, `Drug`, `Diagnosis`, `Finding`, `Symptom`).

## Companion review document

`datasets/mappings/openmrs-2.7-to-2.8.conceptmap.review.md` — required alongside the JSON. Captures:

- Per-policy-bucket counts
- Reviewer identity and signoff date
- Summary of `seed-augment` decisions (per concept class)
- Open follow-ups (concepts whose mapping is provisional pending external review)
- Cross-reference to the OCL CIEL snapshot version used during review

## Validation

```bash
# FHIR Validator (unmodified release)
java -jar org.hl7.fhir.validator.jar \
  datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json \
  -version 4.0
```

Plus harness-internal `harness/conceptmap/validate.py` enforces the profile-only fields (extensions, single-target, cross-element constraints). Profile-only validation FAILURES are reviewer-actionable; they do not invalidate FHIR conformance.
