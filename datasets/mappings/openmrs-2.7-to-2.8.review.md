# Review companion — `openmrs-2.7-to-2.8.conceptmap.json`

Required alongside the JSON per `specs/002-openmrs-demo-data-2-8-remap/contracts/sqlmesh_project.profile.md`. This file captures the reviewer rationale and the diff-items-to-models index that the transform's audits cross-check.

## Per-element review

| Element | Target | Rationale source | Sign-off |
|---|---|---|---|
| Identity bridge | every legacy concept_id | `data-model.md` §R-bridge-rule + `research.md` §R-bridge-rule; measured 100% coverage on the 457 obs-referenced concepts in the current corpus. | pending |
| P1 drug_order | `drug_order` | `data-model.md` §R-promotion-rules; `research.md` §R-typed-table-promotion (Q3 vaccines as drug_order). | pending |
| P2 conditions | `conditions` | `data-model.md` §R-promotion-rules; PROBLEM ADDED (concept 6042) is the semantic anchor. | pending |
| P3 allergy | `allergy` | `data-model.md` §R-promotion-rules; allergen-substance hand-pick required per question concept. | pending |
| P4 test_order | `test_order` | `data-model.md` §R-promotion-rules; the TEST concept (not the result) populates `test_order.concept_id`. | pending |

## Module-table policy summary

The default policy for the 22 legacy-only tables is `carry-forward`. The reviewer revisits this list during acceptance; tables that demonstrably affect RefApp behavior get escalated to `drop` / `install-module` / `remap` per `spec.md` FR-008(b).

| Table | Default policy | Reviewer decision |
|---|---|---|
| (see `datasets/transforms/sqlmesh/seeds/module_table_policy.csv`) | carry-forward | pending |

## Diff-items-to-models index

Filled in after Phase 6 schema diff runs. Each `clinical_meaningful: true` item from `schema_diff.json` lists the SQLMesh model that covers it (a clinical mart, a module-policy model, or an explicit drop).

| Diff item ID | Description | Covering model | Reviewer note |
|---|---|---|---|
| _(pending Phase 6)_ | | | |

## Outstanding decisions

- Allergen-substance hand-pick per P3 question concept (`6011 PENICILLIN`, `6012 SULFA`, `1083 OTHER MEDICINE`).
- Whether `CHILDS CURRENT HIV STATUS` (concept 5303) promotes to `conditions` alongside P2. Default: stays in obs.
- Whether vaccine drug-class answers should carry an attribute hint so the FHIR layer re-projects them as Immunization (Q3 in `research.md` §R-typed-table-promotion).

## Signoff

- Project owner: pending
- CIEL snapshot used during review: `datasets/sources/ocl/CIEL/v2026-04-28/`
- Date: pending
