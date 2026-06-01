# Demo-Data Regen — Deviation Ledger

How the 2.7→2.8 regen maps every source row to modern OpenMRS. **No `legacy_27_raw`
row is dropped.** Baseline = OpenMRS Reference Application 3.6.0 + CIEL. Verified:
`openmrs_test` has **0 orphan FKs** and full source preservation.

## Preservation proof (verified against the loaded `openmrs_test`)

- `person` 5286, `patient` 5284, `person_address` 5283, `person_attribute` 5287,
  `patient_program` 3935, `patient_state` **8499**, `encounter` 14316,
  `program_workflow_state` 82 — all preserved exactly.
- **obs conservation (0 difference):** legacy obs 476,973 = target `obs` 428,013 +
  `drug_order` 43,412 + `conditions` 4,451 + `test_order` 1,095 + `allergy` 2.
  Every observation is either retained as `obs` or promoted to a modern typed table.

## ① Defects fixed (data recovery / referential validity)

| item | grounded signal | fix |
|---|---|---|
| Dropped demographics: `person_address` (5283), `person_attribute` (5287, +`_type`) | real rows for every demo person, absent from `LOAD_RESOURCES` (models existed, never wired) | added to `LOAD_RESOURCES` |
| Dropped enrollments detail: `patient_state` (8499) | audit-invisible; child of loaded `patient_program` | added to `LOAD_RESOURCES`, fully preserved |
| Program-concept gap: HIV/TB/MDR-TB + all workflow/state concepts | omitted by the bridge rule (false "not clinically referenced") | `MANUAL_CONCEPT_OVERRIDES` (seed_emit.py) maps the clean clinical ones to CIEL |
| 67 local AMPATH concepts with no CIEL equivalent (cohort GROUP labels, clinical state variants) | referenced by program/workflow/state, absent from CIEL, **0 id-collision** | **carried forward** into the dictionary (`stg_concept_carryforward` + `_name`) so all rows resolve — nothing dropped |
| `program*` merge collisions | baseline programs 1–4 vs legacy 3,4,5 | `program`/`program_workflow`/`program_workflow_state` → `replace` (full legacy refresh) |
| Account scaffolding orphans: `provider`/`users` person 3,4,5 | RefApp clerk/nurse/tech; legacy owns the person-space | deterministic repair in the load (`repair_scaffolding_accounts`) — RefApp stock, not source data |
| FR-013 not enforced | optional, `--allow-orphans` | `orphan-fk-check` is the blocking gate; load self-repairs first |

## ② Modern representation (faithful, not loss)

- **`drug_order`** (43,412) / **`conditions`** (4,451) / **`test_order`** (1,095) /
  **`allergy`** (2) — promoted from coded obs (`seed_augment`). Legacy recorded meds
  and diagnoses as observations; the modern OpenMRS shape is typed clinical tables.
  The obs are *moved*, not lost (see conservation proof). `drug_order` dosing is NULL
  because the source carries none (verified: 0 of 43,412 med-obs have dose) — never
  fabricated.
- **Program/enrollment** — modeled as program → workflow → state. Clinical states map
  to CIEL `State` concepts; local AMPATH cohort labels are carried forward as local
  concepts (OpenMRS implementations add local concepts routinely). All workflows
  (incl. the cohort TREATMENT GROUP workflow) and all 8,499 enrollment-states retained.
- **Triomune (3TC+NVP+d4T)** — 3 component orders + 137 FDC orders; faithful 2006-era
  passthrough.

## ③ RefApp 3.6.0 stock removed (NOT our source data — verified `legacy_27_raw` = 0)

- Stock-patient leakage: `encounter_diagnosis`, `obs_reference_range`, `visit`,
  `patient_appointment` (+ `_audit`/`_provider` children) — the appointment module
  doesn't exist in 2.7; these are the RefApp's stock ~50 demo patients. Cleared in
  `loadtest-up`.
- RefApp service accounts (clerk/nurse/technician) — legacy has only `admin`+`daemon`.

## ④ Source tables not row-copied, with reason

- `concept_*` — remapped into CIEL via the bridge rule + carry-forward (not row-copied).
- `liquibasechangelog*`, `privilege`, `global_property`, `logic_token_registration`,
  `scheduler_task_config`, `hl7_source` — system/config; target owns its own.
- `tribe` — deprecated table, removed from modern OpenMRS.
