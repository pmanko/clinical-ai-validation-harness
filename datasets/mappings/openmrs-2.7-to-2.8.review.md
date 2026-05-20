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

## Corrected promotion invariants

- No duplicate canonical facts: when P1/P2/P3 obs rows are promoted to typed clinical tables, those source obs rows are excluded from residual `obs`.
- P4 is the only exception shape: an `orders` + `test_order` pair may have a linked result obs via `obs.order_id` only when the obs is genuinely the test result, not a duplicate order fact.
- Promotion selectors are source-ID-safe: classification uses `stg_obs.source_concept_id` and `stg_obs.source_value_coded`, while output FK columns use UUID-resolved local target IDs from `seed__concept_translation`.
- Synthetic promoted UUIDs are deterministic UUIDv5-style name-based identifiers from Feature 002 namespace `2f56d7b8-8f8f-5d3a-9f52-002002800001`.
- Mapping gaps are explicit review artifacts. Medication catalog/display gaps are listed in `datasets/load/medication-mapping-triage.tsv`; no `drug_inventory_id` or `drug_non_coded` value is fabricated without reviewer approval.

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
- Medication catalog/display review for the concepts in `datasets/load/medication-mapping-triage.tsv`.
- Whether `CHILDS CURRENT HIV STATUS` (concept 5303) promotes to `conditions` alongside P2. Default: stays in obs.
- Whether vaccine drug-class answers should carry an attribute hint so the FHIR layer re-projects them as Immunization (Q3 in `research.md` §R-typed-table-promotion).

## Carry-forward orphan tables — deferred from materialization

The following legacy-only module tables ARE flagged `carry-forward` in `seeds/module_table_policy.csv` but are NOT materialized as `models/modules/<table>__carry-forward.sql` because their target identifiers would exceed MariaDB's 64-char limit when prefixed by SQLMesh's snapshot template (`refapp_28_demo__mod__<table>__<10-digit-hash>`). The `gen_modules.py` script (`harness/transform/gen_modules.py`) skips them with a clear log line:

| Table | Length | Status |
|---|---|---|
| `metadatasharing_imported_package_item` | 37 | deferred (over limit) |
| `metadatasharing_exported_package` | 32 | deferred (over limit) |
| `metadatasharing_imported_package` | 32 | deferred (over limit) |
| `xforms_person_repeat_attribute` | 30 | deferred (over limit) |
| `dataintegrity_integrity_checks` | 30 | deferred (over limit) |
| `metadatasharing_imported_item` | 29 | deferred (over limit) |

These tables are all empty in the 2.7 demo dump (0 rows each per the inventory). Carrying forward zero rows of an over-long-named table is symbolic; the deferral has no behavioral impact on the produced demo. If a future corpus populates one of these, options are: (a) rename in the target with documentation, (b) install the owning module in the 2.8 RefApp distro, or (c) drop with explicit reviewer rationale.

## Signoff

- Project owner: pending
- CIEL snapshot used during review: `datasets/sources/ocl/CIEL/v2026-04-28/`
- Date: pending
