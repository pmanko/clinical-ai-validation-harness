# OpenELIS Mapping Skeleton Profile (harness-local)

**Status**: Analysis artifact only (Q1 clarification). No live OpenELIS load is executed under this feature.

The OpenELIS mapping is a **skeleton** — two paired artifacts that a future loader feature would consume:

1. **Terminology skeleton** (`datasets/mappings/openmrs-2.7-to-openelis.skeleton.conceptmap.json`) — FHIR R4 ConceptMap, OpenMRS source → LOINC primarily, SNOMED CT secondarily. Validated by HL7 FHIR Validator CLI. Conforms to `contracts/conceptmap.profile.md` with the following overrides:
   - `ConceptMap.url` = `http://harness.local/openmrs-2.7-to-openelis-skeleton`
   - `ConceptMap.targetUri` = `http://openelis-global.org/terminology/loinc`
   - `policy-bucket` extension is replaced by `http://harness.local/StructureDefinition/openelis-feasibility-bucket` with `code` in `[full, partial, synthesized, not-feasible]`.

2. **Structural skeleton** (`datasets/mappings/openmrs-2.7-to-openelis.skeleton.yaml`) — per-entity mapping from OpenMRS source tables/columns to proposed OpenELIS Global entity fields. Not executable; intended as the loader's starting input.

## Structural skeleton (`.yaml`) layout

```yaml
schema_version: 1
kind: OpenELISMappingSkeleton
target:
  product: OpenELIS Global
  version: <built-release-version>
  source: built-release
  catalyst_umbrella_submodule: targets/catalyst
generated_at: <iso-timestamp>
generated_from:
  openmrs_profile: artifacts/<run>/profile/inventory.json
  conceptmap: datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json
  ocl_ciel_snapshot: datasets/sources/ocl/CIEL/<version>/
  loinc_snapshot: datasets/sources/ocl/LOINC/<version>/

entities:
  - entity: patient
    feasibility: full | partial | synthesized | not-feasible
    source_columns:
      - patient.patient_id
      - person.gender
      - person_name.given_name
      - person_name.family_name
      - person_address.country
    target_fields:
      - patient_id
      - gender
      - first_name
      - last_name
      - country
    shared_identifier_proposal:
      openmrs_field: patient_identifier.identifier
      openelis_field: patient.external_id
      shared_scheme: "OpenMRS patient_identifier_type 'OpenMRS ID' is the matchable scheme"
    rationale: |
      ...
    gaps: []
  # ... provider, organization, location, test, analyte, order, result, observation, specimen, reference_terminology
```

## Required entities

Every skeleton MUST cover (each entry classified `full` / `partial` / `synthesized` / `not-feasible`):

- `patient`
- `provider`
- `organization`
- `location`
- `test` (lab test definition)
- `analyte` (the analyte/observable the test measures — primary LOINC bridge surface)
- `order` (lab order)
- `result` (observation result)
- `observation` (general lab observation row)
- `specimen`
- `reference_terminology` (per-source coverage for LOINC, SNOMED, ICD-10, RxNorm)

## LOINC bridge coverage

For `test`, `analyte`, `result`, `observation` entities, the structural skeleton entry MUST include `loinc_bridge_coverage_percent` — the percentage of source-side clinical concept references that have an existing LOINC mapping via the pinned CIEL snapshot. Concepts without LOINC are listed under `gaps[]` with the source record IDs that depend on them.

## Out of scope for this feature

- Live OpenELIS Global bringup
- Catalyst code execution
- Any data being loaded into OpenELIS

The Catalyst submodule (`targets/catalyst`, pinned by PR #4) is referenced as the documented umbrella entry point for a future loader feature, not invoked here.
