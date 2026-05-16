# Review companion — `openmrs_loadback` dlt pipeline

Required alongside `harness/load/pipeline.py` per `specs/002-openmrs-demo-data-2-8-remap/contracts/dlt_pipeline.profile.md`. This file captures the reviewer rationale per resource + FK-reconciliation decisions; complements `datasets/mappings/openmrs-2.7-to-2.8.review.md` (which covers the transform side).

## Per-resource write-disposition rationale

| Resource | Disposition | PK | Rationale |
|---|---|---|---|
| `person` | `replace` | `person_id` | Legacy has 5,286 persons; openmrs CIEL-baseline has 56 stock + admin records. Wipe-and-reload — we want the legacy person identities as the canonical set in the demo. |
| `patient` | `replace` | `patient_id` | Same reasoning as person. 5,284 legacy patients. |
| `person_name` / `person_address` / `person_attribute` | `replace` | composite | Tied 1:1 to person; wipe-and-reload with person. |
| `encounter` | `replace` | `encounter_id` | 14,316 legacy encounters; stock has 1,478. Wipe. |
| `encounter_provider` / `encounter_diagnosis` | `replace` | composite | Child of encounter. |
| `obs` | `replace` | `obs_id` | 428,013 rebound rows from `clin__obs` (the non-promoted obs). Wipe-and-reload. |
| `drug_order` | `replace` | `order_id` (via uuid) | 43,412 promoted rows from `clin__drug_order`. Wipe — legacy has zero drug_orders, so all rows come from the promotion. |
| `conditions` | `replace` | `condition_id` (via uuid) | 4,451 promoted from `clin__conditions`. Wipe. |
| `allergy` | `replace` | `allergy_id` (via uuid) | 2 promoted from `clin__allergy`. Wipe. |
| `test_order` | `replace` | `order_id` (via uuid) | 1,120 promoted from `clin__test_order`. Wipe. |
| `concept_*` tables | **SKIP** | n/a | CIEL has already populated these via openconceptlab in `make ciel-baseline`. Re-writing risks UUID-pattern conflicts per research.md §R-bridge-rule. The bridge rule's intent is met by the CIEL load itself; the dlt loader does not touch concept dictionary tables. |
| `location` / `encounter_type` / `encounter_role` / `role` / `privilege` / `visit_type` | `merge` (PK) | id | Stable lookups; legacy may add IDs that openmrs's stock doesn't have. Merge by PK preserves both. The FK reconciliation seed maps in `models/terminology/<entity>_map.sql` document which IDs come from where. |
| `provider` | `merge` (`provider_id`) | id | Same as location. |
| `users` / `user_property` / `user_role` | `merge` (PK) | id | Same as location; openmrs admin user(s) coexist with legacy users. |

## FK-reconciliation decisions

**Default strategy**: **legacy IDs verbatim** for clinical tables (person/patient/encounter/obs/drug_order/etc); openmrs stock is wiped (the `replace` disposition). For lookup tables (location/encounter_type/role/provider/users), legacy IDs coexist with openmrs's stock via `merge`. The FK reconciliation seed maps in `datasets/transforms/sqlmesh/models/terminology/<entity>_map.sql` document the mapping (default: identity).

**Rationale**: Legacy has the rich clinical history; openmrs's CIEL-baseline has minimal stock data. Keeping legacy IDs as canonical preserves clinical-record stability across iterations. If a specific ID collision surfaces during iteration (Phase 5F), the relevant `_map.sql` model is updated to renumber, and dlt's column projection consults the map.

## Known follow-ups (filled during Phase 5F iteration)

_(populated during the iteration cycle — empty at spec-alignment time)_

- _Expected entries_:
  - First FK-orphan surface (which table, which column, fix applied)
  - First column-shape mismatch (which table, which column, fix applied)
  - First concept-binding gap (which concept, which surface, fix applied)
  - Liquibase upgrade-in-place behavior (any changesets that needed pre-staging)

## Signoff

- Project owner: pending
- CIEL snapshot used during review: `datasets/sources/ocl/CIEL/v2026-04-28/`
- SQLMesh project checksum at review time: pending (stamped by `make load-test` into the run manifest)
- dlt version at review time: pending
- Date: pending
