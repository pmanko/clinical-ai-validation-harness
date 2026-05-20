# PCCP Change Record: Feature 002 Mapping Remediation

Date: 2026-05-18

## Change

Correct the Feature 002 SQLMesh + dlt mapping path at the source:

- Resolve `concept_translation.target_concept_id` from target `concept.uuid`, not from the legacy integer.
- Preserve source concept identity in `stg_obs.source_concept_id` and `stg_obs.source_value_coded` so promotion selectors remain source-ID-safe after FK rebinding.
- Rewrite `orders` + `drug_order` and `orders` + `test_order` as proper OpenMRS parent/child table shapes.
- Enforce typed-table canonicalization: promoted P1/P2/P3 facts do not remain as duplicate residual obs.
- Replace non-deterministic promoted-row `UUID()` with deterministic UUIDv5-style name-based identifiers for synthetic parent rows and typed rows requiring UUIDs.
- Augment the drug catalog deterministically so promoted `drug_order` rows have valid `drug_inventory_id` values, while preserving formulation/regimen review in `datasets/load/medication-mapping-triage.tsv`.

## Rationale

The prior transform wrote legacy concept integers into target FK columns. This could point to an existing but unrelated target concept (for example, legacy `794` became target concept `794` = Hip pain instead of local CIEL concept `6689` = Lopinavir / ritonavir). Existing audits only proved that a concept ID existed, not that it matched the intended CIEL UUID.

The prior `clin__drug_order` model also emitted parent-table fields that do not exist on OpenMRS `drug_order`. `promote.py` dropped those columns by column intersection, leaving medication child rows with no display/catalog data. Legacy `drug` rows also collided with stock RefApp drug IDs, so they were not usable as-is for promoted orders.

## Before / After Evidence

Known patient: `dd553355-1691-11df-97a5-7038c432aabf`.

Before remediation:

- Loaded medication parent rows used unrelated local concept IDs such as `794` (Hip pain).
- `drug_order.drug_inventory_id`, `drug_order.drug_non_coded`, and `drug_order.dose` were null for all checked rows.
- Source selectors depended on rebound IDs still matching legacy IDs.

After remediation in `openmrs_test`:

- Known patient drug order concepts resolve to local CIEL IDs: `6689` Lopinavir / ritonavir, `6592` Didanosine, `6531` Retrovir.
- No Hip pain / imaging concepts appear as medication names for the known patient.
- `seed__concept_translation` UUID/id agreement check returns 0 mismatches.
- Promoted clinical FK agreement check returns 0 mismatches.
- Duplicate promoted P1/P2/P3 facts in residual obs check returns 0 rows.
- `stg_drug` now emits 36 augmented catalog rows: 6 preserved legacy drug rows under non-colliding IDs and 30 generated concept-level drug rows for the promoted medication concepts.
- All 43,412 promoted `drug_order` rows in `openmrs_test` have non-null `drug_inventory_id`; catalog coverage check returns 0 misses.
- Medication formulation/regimen review items are explicitly listed in `datasets/load/medication-mapping-triage.tsv`.

## Reviewer Decisions Still Pending

- Medication concepts in `datasets/load/medication-mapping-triage.tsv` need case-by-case clinical review before replacing generated concept-level catalog rows with formulation-specific rows or rerouting immunization/regimen/nutrition concepts.
- P3 allergen concept choices remain reviewable and are documented in `datasets/mappings/openmrs-2.7-to-2.8.review.md`.
- P4 order/result pairing must remain explicitly reviewed before retaining linked result obs for any non-order fact.
