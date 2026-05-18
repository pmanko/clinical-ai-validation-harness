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
| `obs` | `replace` | `obs_id` | 428,013 rebound rows from `clin__obs` (the non-promoted obs). Promoted P1/P2/P3 facts are excluded so residual obs does not duplicate canonical typed-table facts. Wipe-and-reload. |
| `orders` | `replace` | `order_id` | 44,507 promoted parent rows for `drug_order` + `test_order`. `orders.uuid` is deterministic UUIDv5-style name-based synthetic identity. Wipe — legacy has no usable parent order rows for these promotions. |
| `drug_order` | `replace` | `order_id` | 43,412 promoted child rows from `clin__drug_order`; child table contains only OpenMRS `drug_order` columns. Medication catalog/display gaps are not fabricated; unresolved concepts are listed in `datasets/load/medication-mapping-triage.tsv`. |
| `conditions` | `replace` | `condition_id` (via uuid) | 4,451 promoted from `clin__conditions`. Wipe. |
| `allergy` | `replace` | `allergy_id` (via uuid) | 2 promoted from `clin__allergy`. Wipe. |
| `test_order` | `replace` | `order_id` | 1,095 promoted child rows from `clin__test_order` after the source-selector rule lets drug_order win for the 25 obs that match both Drug-class value_coded and Test-class concept_id. Parent fields live in `orders`. |
| `concept_*` tables | **SKIP** | n/a | CIEL has already populated these via openconceptlab in `make ciel-baseline`. Re-writing risks UUID-pattern conflicts per research.md §R-bridge-rule. The bridge rule's intent is met by the CIEL load itself; the dlt loader does not touch concept dictionary tables. |
| `location` / `encounter_type` / `encounter_role` / `role` / `privilege` / `visit_type` | `merge` (PK) | id | Stable lookups; legacy may add IDs that openmrs's stock doesn't have. Merge by PK preserves both. The FK reconciliation seed maps in `models/terminology/<entity>_map.sql` document which IDs come from where. |
| `provider` | `merge` (`provider_id`) | id | Same as location. |
| `users` / `user_property` / `user_role` | `merge` (PK) | id | Same as location; openmrs admin user(s) coexist with legacy users. |

## FK-reconciliation decisions

**Default strategy**: **legacy IDs verbatim** for clinical tables (person/patient/encounter/obs/drug_order/etc); openmrs stock is wiped (the `replace` disposition). For lookup tables (location/encounter_type/role/provider/users), legacy IDs coexist with openmrs's stock via `merge`. The FK reconciliation seed maps in `datasets/transforms/sqlmesh/models/terminology/<entity>_map.sql` document the mapping (default: identity).

**Rationale**: Legacy has the rich clinical history; openmrs's CIEL-baseline has minimal stock data. Keeping legacy IDs as canonical preserves clinical-record stability across iterations. If a specific ID collision surfaces during iteration (Phase 5F), the relevant `_map.sql` model is updated to renumber, and dlt's column projection consults the map.

## Phase 5C terminology maps — status (path B per Phase 5D.7)

The six terminology maps under `datasets/transforms/sqlmesh/models/terminology/` (`user_map`, `location_map`, `encounter_type_map`, `encounter_role_map`, `role_map`, `provider_map`) are **identity maps** — every `source_id` equals its `target_id`. They are **documentation-only** at this stage.

**Path B decision**: the dlt loader does NOT consult these maps. They exist to document the FK reconciliation contract ("legacy IDs are preserved verbatim into openmrs_test; openmrs stock is wiped at promote time for clinical tables, merged for lookup tables"). Path A — actively reading the maps to translate FK columns at load time — is deferred until a specific ID collision surfaces during iteration.

**Trigger to switch to Path A**: a concrete FK collision (e.g., legacy user_id=2 must be remapped to openmrs user_id=99 to avoid a conflict). When that surfaces, the relevant map's body is replaced with explicit translation, and the dlt loader is extended to JOIN the map during the promote step.

## Current mapping triage artifacts

- `datasets/load/medication-mapping-triage.tsv` lists every unresolved medication concept after the deterministic concept-FK fix. Current bucket summary: 43,412 `drug_order` rows are intentionally unresolved for catalog/display review; no `drug_inventory_id` or `drug_non_coded` values are fabricated without reviewer approval.
- Known patient `dd553355-1691-11df-97a5-7038c432aabf` now resolves medication order concepts to local CIEL target IDs, including `6689` Lopinavir / ritonavir, `6592` Didanosine, and `6531` Retrovir; no `Hip pain`/imaging concepts appear as medication names.
- Typed-table canonicalization is enforced: promoted P1/P2/P3 facts do not remain as duplicate residual obs. P4 is limited to the normal order/result distinction and requires explicit review if linked result obs are retained.

## Known follow-ups (discovered during Phase 5D first iteration)

- **FK orphans surfaced by `make orphan-fk-check`** (1,967 total across 13 FKs). All concentrate around stock-data residue that wasn't cleaned out before the load:
  - `encounter_diagnosis.encounter_id → encounter.encounter_id`: 562 orphans (stock encounter_diagnosis kept while encounter was wiped + reloaded with legacy)
  - `encounter_diagnosis.patient_id → patient.patient_id`: 530 orphans (same)
  - `obs_reference_range.obs_id → obs.obs_id`: 451 orphans
  - `visit.patient_id → patient.patient_id`: 174 orphans
  - `patient_appointment.patient_id → patient.patient_id`: 100 orphans
  - + 8 smaller FKs
  - **Fix path**: add the affected tables (encounter_diagnosis, obs_reference_range, visit, patient_appointment, etc.) to `LOAD_RESOURCES` so the dlt loader wipes + replaces them, OR add a post-clone TRUNCATE step in `loadtest-up.sh` that empties stock clinical-detail tables before dlt runs. Deferred to a follow-up iteration; current orphans don't block the demo for the marquee patient/obs/drug_order flow.
- **Lucene reindex 28 PersonAttribute orphans**: `PersonAttribute#1` references `Person#7` which doesn't exist. Stock-data residue. Same fix path as above.
- **Column-shape diffs surfaced by promote (`dropped_columns` per resource)**: 2.7→2.8 schema diffs handled automatically by the promote step's column-intersection. Notably `provider.provider_role_id` (added in 2.8). No data loss; the new column gets MySQL's DEFAULT.
- **drug_order vs test_order disambiguation**: 25 obs match both Drug-class value_coded AND Test-class concept_id. drug_order wins using source-ID-safe selectors (`stg_obs.source_value_coded` / `source_concept_id`). test_order final count: 1,095 (vs 1,120 unfiltered).

## Signoff

- Project owner: pending
- CIEL snapshot used during review: `datasets/sources/ocl/CIEL/v2026-04-28/`
- SQLMesh project checksum at review time: stamped per-run in `artifacts/<run>/transform/transform.report.json`
- dlt version at review time: 1.26.0
- First successful end-to-end load: 2026-05-16 (this commit chain)
- Date: pending reviewer signoff
