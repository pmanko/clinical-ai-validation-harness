# Phase 1 — Data Model

**Feature**: 002-openmrs-demo-data-2-8-remap
**Date**: 2026-05-13

This document enumerates the artifacts produced and consumed by the feature. It anchors on the M0 control-plane primitives (PR #2, merged to main via PR #3) plus the M0 follow-up (PR #4, in review) which pins `targets/catalyst` and aligns `compose/openmrs-2.8-refapp.yml` with the O3 RefApp stack.

## 0. Anchored on M0 / PR #4

The following primitives are **not redefined here** — they are consumed as-is:

| M0 primitive | Path | What 002 uses it for |
|---|---|---|
| Target registry | `harness/targets.yaml` | Reads `targets.chartsearchai.validation_surface.command` for M2-F cross-target validation; reads `shared_infrastructure.openmrs_refapp` for bringup. |
| Submodule pins | `.gitmodules`, `targets/<id>/` | `targets/chartsearchai`, `targets/querystore` (pinned by M0); `targets/catalyst` (pinned by PR #4) reference points. |
| Shared compose | `compose/openmrs-2.8-refapp.yml` (post-PR #4 = O3 stack on Core 2.8.x + MariaDB 10.11.7) | M2-F real-bringup; M2-A clean-baseline snapshot. |
| Run manifest | `harness.metadata.RunManifest` | Base manifest record. 002 adds top-level fields; see `contracts/run_manifest_002_extensions.schema.yaml`. |
| Events log | `harness.metadata.append_event` | All 002 events route through this writer. |
| Compose lifecycle | `harness.compose.compose_files_for_profile` | Plan compose ups/downs for M2-F. |
| Targets loader | `harness.targets.load_target_registry` | Load `harness/targets.yaml`; classify `evidence_status`. |

## 1. Source corpus

- **Path**: `data/large-demo-data-2-7-0.sql`
- **Format**: MySQL/MariaDB dump (CREATE TABLE + INSERT statements; 143 tables, 153 insert batches; MySQL 5.7 / utf8 origin; portable — no `USE` / `CREATE DATABASE` statements)
- **Provenance**: public, cleaned, anonymized OpenMRS demo dataset (FR-PHI1, FR-PHI2)
- **Pinned by**: `datasets/sources/large-demo-data-2-7-0.sql.checksum` (SHA-256 digest + origin URL + license + retrieval timestamp); measured sha256 `a7ca4bbe…`
- **Lifecycle**: read-only; loaded once per run into MariaDB schema `legacy_27_raw` via `scripts/load-demo-data.sh`

### 1.1 Measured corpus signals (from T021 inventory output)

Captured in `artifacts/legacy-27-raw-baseline/profile/inventory.json` against the pinned source dump:

| Metric | Value |
|---|---|
| Base tables in dump | 143 |
| Populated tables | 52 |
| Patients | 5,284 |
| Person | 5,286 |
| Encounters | 14,316 |
| Encounter providers | 14,316 |
| Obs | 476,973 |
| Distinct `obs.concept_id` values | 150 |
| Distinct `obs.value_coded` values | 318 |
| Distinct concept IDs referenced in `obs` (concept_id ∪ value_coded) | **457** |
| **Typed clinical tables**: `allergy` / `conditions` / `orders` / `drug_order` | **0 each** |
| `concept_reference_source` / `concept_reference_term` / `concept_reference_map` rows | **0 each** (legacy ships zero terminology cross-references) |
| Locales in `concept_name` | en only (3,555 names) |

The empty typed clinical tables + zero reference-map state IS the M2-A discovery that motivates §R-bridge-rule (identity rebind, not curated translation) and §R-promotion-rules (synthesize typed rows from obs).

## 2. Clean target baseline

- **Schema**: `openmrs` (MariaDB 10.11) — the live RefApp's DB, **after** CIEL has been loaded via the openconceptlab module (T024a/b). The CIEL-loaded `openmrs` schema IS the clean baseline; no separate empty-Liquibase-only DB is maintained.
- **Built by**: `make ciel-baseline` (calls `scripts/ciel-baseline-up.sh`), which boots the O3 backend against an empty MariaDB, lets Liquibase complete the Core 2.8.x changesets, then imports the pinned CIEL export via the openconceptlab module's offline-import path. The result is a Core 2.8.x schema populated with CIEL concepts but no clinical records.
- **Lifecycle**: rebuilt only when the CIEL pin or RefApp image digest changes (via `make ciel-baseline`); otherwise reused across runs. Schema export captured under `artifacts/<run>/schema-diff/openmrs.schema.json` (formerly `refapp_28_clean.schema.json`; renamed in M2-A close).

## 2.5 Materialized target — `refapp_28_demo`

- **Schema**: `refapp_28_demo` (MariaDB 10.11) — the materialized output of the SQLMesh transform (see §6 below).
- **Built by**: `harness-cli transform run` invokes the SQLMesh project under `datasets/transforms/sqlmesh/`. SQLMesh materializes the staging / terminology / clinical / modules / audit_views models against the harness gateway (the same MariaDB used by the live RefApp stack).
- **Loaded into the live stack**: `scripts/load-transformed.sh` dumps `refapp_28_demo` into `artifacts/<run>/transform/refapp_28_demo.sql` (deterministic mariadb-dump) and re-applies it on top of the CIEL-loaded `openmrs` DB so the live RefApp 3.6.0 stack serves REST / FHIR against the transformed corpus.
- **Lifecycle**: rebuilt on every `transform run`; the .sql artifact is the per-run deliverable for downstream consumers (chartsearchai M2-F, OpenELIS analysis M2-H).

## §R-bridge-rule. Identity bridge between legacy concept IDs and the seeded CIEL dictionary

> Discovered during M2-A profiling; see [`specs/artifacts/canvases/concept-mapping-discovery.canvas.tsx`](../artifacts/canvases/concept-mapping-discovery.canvas.tsx) for the visual derivation, and `research.md` §R-bridge-rule for the rationale.

The 2.7 demo dump uses AMPATH-style concept numbering. Empirically, **every legacy `concept_id N` that is referenced by ≥1 row in `obs` corresponds to the seeded CIEL concept whose UUID is `RPAD(CAST(N AS CHAR), 36, 'A')`** (the canonical CIEL UUID pattern: the integer ID left-padded by `A` to 36 chars). Reproduction:

```sql
-- Run after `make ciel-baseline` against the harness MariaDB.
WITH legacy_used AS (
  SELECT DISTINCT concept_id FROM legacy_27_raw.obs WHERE concept_id IS NOT NULL
  UNION
  SELECT DISTINCT value_coded FROM legacy_27_raw.obs WHERE value_coded IS NOT NULL
)
SELECT
  COUNT(DISTINCT lu.concept_id) AS legacy_distinct_in_obs,           -- 457
  COUNT(DISTINCT CASE WHEN ciel.concept_id IS NOT NULL
                      THEN lu.concept_id END) AS bridgeable_via_uuid  -- 457 (100%)
FROM legacy_used lu
LEFT JOIN openmrs.concept ciel ON ciel.uuid = RPAD(CAST(lu.concept_id AS CHAR), 36, 'A');
```

The bridge rule MUST materialize into `datasets/transforms/sqlmesh/seeds/concept_translation.csv` as one row per **distinct legacy `concept_id` present in `legacy_27_raw.concept`** (~2,528 rows), not just the obs-referenced subset. Including unreferenced concepts keeps the seed surface auditable against the source dump and protects against future references surfacing. The seed CSV columns are defined by `contracts/sqlmesh_project.profile.md` (`source_concept_id, source_uuid, target_concept_id, target_uuid, equivalence='equal', policy_bucket='remap', source_record_examples`).

If any legacy concept_id resolves to a row in `legacy_27_raw.concept` but NOT to a row in `openmrs.concept` via the UUID pattern, the `audit_concept_translation_coverage` SQLMesh audit emits that concept_id as a failing row and the transform halts (FR-008(a)). The acceptance gate is **zero failing rows** against the live corpus.

## §R-promotion-rules. Structural promotion (obs → typed clinical tables)

Documented per-rule below; encoded as one ConceptMap element each (FR-029–FR-032) and as one SQLMesh model each under `datasets/transforms/sqlmesh/models/clinical/`.

| Rule | Source selector | Target table | Expected rows (measured) | Field-mapping reference |
|---|---|---|---|---|
| P1 (FR-029) | `obs WHERE value_coded.concept.concept_class = 'Drug' AND voided = 0` | `drug_order` | 43,412 | clinical/drug_order.sql + ConceptMap element ext |
| P2 (FR-030) | `obs WHERE concept_id = 6042 ('PROBLEM ADDED') AND value_coded IS NOT NULL AND voided = 0` | `conditions` | 4,451 | clinical/conditions.sql |
| P3 (FR-031) | `obs WHERE concept_id IN (6011, 6012, 1083) AND value_coded = 1065 ('YES') AND voided = 0` | `allergy` | 2 | clinical/allergy.sql |
| P4 (FR-032) | `obs WHERE concept.concept_class = 'Test' AND concept.concept_datatype = 'Coded' AND voided = 0` | `test_order` | 1,120 | clinical/test_order.sql |
| (residual) | obs not matched by P1–P4 (after rebind) | `obs` (rebound) | ~428,013 | clinical/obs.sql |

Field mapping per rule is recorded canonically in the ConceptMap element's harness extensions (see `contracts/conceptmap.profile.md`). The SQLMesh model is the executable instantiation; `audits/audit_<mart>_row_count_min.sql` are the **single source of truth** for the minimum row-count floor — the audits fail the pipeline if a mart drops below its floor (catches silent-zero materialization failures, the C2-class incident from M2-A close). The "Expected rows (measured)" column above is illustrative; the audit SQL is canonical. Cross-cutting decisions (obs-preservation via `obs.order_id`, deterministic UUID v5, vaccine handling, orderer source, sampler strategy) are in `research.md` §R-typed-table-promotion.

## §R-load-stage. OLTP load layer (dlt; per research.md §R-load-pattern)

After SQLMesh materializes the transform into `refapp_28_demo` (virtual views over `sqlmesh__refapp_28_demo.*` snapshot tables), **dlt** moves the data into the live OpenMRS DB. This is the second half of the SQLMesh+dlt handover; see `contracts/dlt_pipeline.profile.md` for the load-layer contract.

- **Path**: `harness/load/` (package), `datasets/load/openmrs-loadback.review.md` (companion review doc)
- **Inputs**:
  - `sqlmesh__refapp_28_demo.*` — the physical snapshot tables SQLMesh writes (resolved via `harness/load/snapshot_resolver.py` mapping each `refapp_28_demo.<view>` to its underlying snapshot)
  - FK reconciliation seed maps under `datasets/transforms/sqlmesh/models/terminology/<entity>_map.sql` (legacy ↔ openmrs ID harmonization; default identity)
- **Outputs**: rows in `openmrs_test.*` (iteration target) or `openmrs.*` (promotion target).
- **Tool**: dlt `>=1.0` with the sqlalchemy destination, MySQL/MariaDB via PyMySQL.
- **Idempotency**: per-resource via `write_disposition='merge'` with declared `primary_key`. Re-runs produce no row deltas if SQLMesh inputs are unchanged.
- **Stamping**: each run writes `dlt_pipeline_run_id` + `dlt_state_hash` into the run manifest, plus per-table row counts into `materialized_outputs[]`.
- **Lifecycle**: replayed on every iteration of the validation loop (edit SQLMesh model → re-run plan + audit → re-run dlt → restart backend → smoke). Wall-time per incremental iteration < 10 min.

## 3. Pinned OCL snapshots

- **Path**: `datasets/sources/ocl/<collection>/<version>/`
- **Collections**: at minimum CIEL (terminology authority) and LOINC (OpenMRS↔OpenELIS bridge); SNOMED CT optional if the corpus requires it.
- **Provenance**: each snapshot directory carries a `provenance.json` recording OCL collection URL, version identifier, retrieval timestamp, checksum.
- **Lifecycle**: refreshed deliberately (out-of-band) as a PCCP-triggering action; read-only during transform.

## 4. Profile inventory

- **Path**: `artifacts/<run>/profile/inventory.json`
- **Contract**: [`contracts/profile_inventory.schema.yaml`](./contracts/profile_inventory.schema.yaml)
- **Fields**:
  - per-table: name, row count, populated columns, PK ranges, FK references in/out
  - concept reference sources (every row in `concept_reference_source` + the `concept_reference_map` row count per source)
  - locales (union of locales referenced by `concept_name`, `concept_description`, `global_property.allowed.locale.list`)
  - modules: every table classified by inferred owning module
- **FR coverage**: FR-001..FR-005

## 5. Schema/metadata diff + Liquibase cost estimate

- **Paths**:
  - `artifacts/<run>/schema-diff/diff.json` (contract: `contracts/schema_diff.schema.yaml`)
  - `artifacts/<run>/profile/liquibase-cost-estimate.json` (contract: `contracts/liquibase_cost.schema.yaml`)
- **Diff fields**: tables-only-in-source, tables-only-in-target, columns added/removed/retyped, index/constraint differences, module-owned classifications, Liquibase changeset deltas; each item carries `clinical_meaningful: boolean` (per research.md §R5).
- **Liquibase cost fields**: per-changeset (changeSetId, file, type, estimated cost class — `instant` / `seconds` / `minutes` / `hours`) based on corpus row counts and known OpenMRS-Talk-documented expensive-changeset patterns (research.md §R-Liquibase). Feeds M2-D's pre-stage decisions.
- **FR coverage**: FR-004, FR-005, FR-008 (covering-gate input)

## 6. Accepted terminology mapping (FHIR ConceptMap)

- **Path**: `datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json`
- **Format**: FHIR R4 ConceptMap (validated by HL7 FHIR Validator CLI)
- **Profile**: [`contracts/conceptmap.profile.md`](./contracts/conceptmap.profile.md)
- **Per-element-target required fields**:
  - `code` (target seeded-dictionary concept_id or UUID)
  - `equivalence` (`equivalent` / `equal` / `wider` / `narrower` / `inexact` / `unmatched` / `disjoint`)
  - `comment` (reviewer rationale; non-empty)
  - Extension `http://harness.local/StructureDefinition/policy-bucket`: `remap` / `seed-augment` / `drop`
  - Extension `http://harness.local/StructureDefinition/source-record-examples` (array of up to 3 source record IDs)
- **Companion review document**: `datasets/mappings/openmrs-2.7-to-2.8.review.md` (per `contracts/sqlmesh_project.profile.md`)
- **Element inventory**: 1 identity-bridge element (encodes §R-bridge-rule above; the seed CSV expands it to one row per legacy concept_id) plus 4 structural-promotion elements (one per §R-promotion-rules entry P1–P4). The file is small by construction — the heavy lifting is in the SQLMesh project (§7) and the seed CSV (§7 bullet "Seeds").
- **FR coverage**: US3 (P1), FR-CD1..CD4, FR-007, FR-027, FR-029, FR-030, FR-031, FR-032, SC-012, SC-014

## 7. Accepted structural mapping (SQLMesh project)

- **Path**: `datasets/transforms/sqlmesh/`
- **Profile**: [`contracts/sqlmesh_project.profile.md`](./contracts/sqlmesh_project.profile.md)
- **Per-model required `name:` / metadata fields** (in the model's `MODEL (...)` block or sidecar YAML):
  - `description` — reviewer-readable rationale
  - `tags` including a `policy_bucket:` entry (`remap` / `drop` / `install-module` / `orphan-carry-forward` / `passthrough`)
  - `audits:` — at least `unique_values()` on PK and `not_null()` on FK columns; custom audits where applicable
  - Cross-reference to `diff_items_covered[]` (from `schema_diff.json`) in the model's description
- **Seeds**:
  - `seeds/concept_translation.csv` — emitted by `harness.conceptmap.seed_emit` from the accepted ConceptMap; columns `(source_concept_id, source_uuid, target_concept_id, target_uuid, equivalence, policy_bucket, source_record_examples)`. Regenerable; checksum tracked in run manifest.
  - `seeds/module_table_policy.csv` — reviewed mapping of every module-owned table to `orphan-carry-forward` / `drop` / `install-module` / `remap-into-<table>` plus rationale.
- **FR coverage**: US1 (P1), FR-008..FR-013, FR-CD5, FR-025, FR-026

## 8. Transform output (candidate DB)

- **Paths**:
  - MariaDB schema `refapp_28_demo` (live)
  - Dump: `artifacts/<run>/transform/refapp_28_demo.sql`
  - Per-row audit: `artifacts/<run>/transform/row_audit.parquet` (or `.jsonl`) — one record per transformed row with `(source_table, source_pk, target_table, target_pk, policy_bucket, equivalence_label, reviewer_rationale_ref)`
  - Orphan-FK report: `artifacts/<run>/transform/orphan-fk-report.json`
- **FR coverage**: FR-009..FR-013

## 9. Import smoke + RefApp tests + binding report

- **Paths**:
  - `artifacts/<run>/import-smoke/report.json` — Liquibase startup, Compose health, REST/FHIR readback for canonical endpoints
  - `artifacts/<run>/refapp-binding/report.json` — bundled-form rendering, default order types, drug catalog resolution against translated concepts
  - `artifacts/<run>/chartsearchai-tests/results.xml` — surefire XML from invoking `harness/targets.yaml.targets.chartsearchai.validation_surface.command` (`mvn -pl api test`) inside `targets/chartsearchai/` with the translated demo DB connection
- **Per check captured**: check_id, target endpoint, inputs, pass/fail, evidence (response excerpt or test output), elapsed_ms
- **FR coverage**: FR-014, FR-CD5, SC-002 (binding), SC-013

## 10. Translation-coverage sampler output

- **Path**: `artifacts/<run>/coverage/sample-<seed>.json`
- **Contract**: [`contracts/coverage_sample.schema.yaml`](./contracts/coverage_sample.schema.yaml)
- **Fields**: sampler seed, ConceptMap version + checksum, per-policy-bucket samples (default N per bucket = 5, configurable), per-record evidence (`source_record_id`, `target_record_id`, `translated_concept_id`, `equivalence_label`, `value`, `units`, `date`, `encounter_id`, `provider_id`, REST/FHIR response excerpt, pass/fail).
- **FR coverage**: FR-015, FR-024, SC-002, SC-010

## 11. OpenELIS feasibility report + mapping skeleton

- **Paths**:
  - `artifacts/<run>/openelis/feasibility.md` — human-readable per-entity analysis
  - `artifacts/<run>/openelis/feasibility.json` — machine-readable counterpart ([`contracts/openelis_feasibility.schema.yaml`](./contracts/openelis_feasibility.schema.yaml))
  - `datasets/mappings/openmrs-2.7-to-openelis.skeleton.conceptmap.json` — terminology skeleton (FHIR ConceptMap, OpenMRS source → LOINC primarily, SNOMED secondarily)
  - `datasets/mappings/openmrs-2.7-to-openelis.skeleton.yaml` — structural skeleton ([`contracts/openelis_skeleton.profile.md`](./contracts/openelis_skeleton.profile.md))
- **Per OpenELIS entity** (patient, provider, organization/location, test/analyte, order, result/observation, specimen, reference terminology):
  - `feasibility`: `full` / `partial` / `synthesized` / `not-feasible`
  - `source_columns`: array of `<table>.<column>` strings
  - `rationale`: reviewer-written prose
  - `shared_identifier_proposal`: how OpenMRS patients would match OpenELIS patients
  - `terminology_translation_required`: boolean + notes
  - `loinc_bridge_coverage`: % of clinical references that have a LOINC mapping via CIEL (lab entities only)
- **Source for OE Global schema**: the sibling checkout at `/Users/pmanko/code/OpenELIS-Global-2/` (read-only; not a submodule of this harness)
- **No Catalyst code is executed**: the `targets/catalyst` submodule (PR #4) is referenced as the documented umbrella entry point for future loader work
- **FR coverage**: US4, FR-017..FR-020, SC-007, SC-008

## 12. Run manifest

- **Path**: `artifacts/<run>/run_manifest.json`
- **Authoring**: via `harness.metadata.RunManifest(...).to_dict()` (M0). 002 adds top-level fields as schema-compatible additions, enumerated in [`contracts/run_manifest_002_extensions.schema.yaml`](./contracts/run_manifest_002_extensions.schema.yaml). 002 does NOT define a new manifest schema.
- **M0-required fields populated by 002**:
  - `run_id`, `project=clinical-ai-validation-harness`, `component=002-openmrs-demo-data-2-8-remap`
  - `git_sha` (harness repo HEAD)
  - `dataset_id=openmrs-large-demo-2-7-0`, `dataset_version=<source_dump_sha256>`, `schema_mapping_version=<conceptmap_checksum>:<sqlmesh_project_checksum>`
  - `generated_at`, `evidence_status` (per stage; `development` or `scaffolding` for OpenELIS portion)
  - `decision_rationale` (when not `release`, required per M0 schema)
  - `target_provenance[]` for each consumed target (chartsearchai, querystore if used, catalyst as scaffolding-only): `target_id`, `target_source=reviewed_submodule`, `target_path`, `target_actual_sha` (from `git submodule status`), `target_reviewed_sha`, `target_override=false`, `evidence_status`
  - `otel.semconv_status=development`, `otel.semconv_stability_opt_in=gen_ai_latest_experimental`, `otel.gen_ai.provider.name` (N/A here — no LLM at runtime; the field is omitted with `decision_rationale` noting model_or_agent_involved == false)
- **002 extensions** (additional top-level fields):
  - `conceptmap_path`, `conceptmap_checksum`
  - `sqlmesh_project_path`, `sqlmesh_project_checksum`
  - `concept_translation_seed_checksum`, `module_table_policy_seed_checksum`
  - `ocl_collection_versions[]` (array of `{collection, version, snapshot_path, checksum}`)
  - `openmrs_refapp_image_digest` (the `openmrs-reference-application-3-backend:3.6.0` digest pulled at run time)
  - `mariadb_image_digest` (the `mariadb:10.11.7` digest)
  - `fhir_validator_version`, `sqlmesh_version`, `python_version`
  - `policy_buckets[]` (enumerated from the ConceptMap)
  - `reviewer_signoffs[]` (paths to ConceptMap review doc + SQLMesh project review doc + signer identity + signoff date + per-doc checksum)
- **FR coverage**: FR-021, SC-006, SC-009

## 13. Events log

- **Path**: `artifacts/<run>/events.jsonl`
- **Authoring**: via `harness.metadata.append_event` (M0)
- **002 event types** (one JSONL line each): `profile_start`, `profile_table`, `profile_complete`, `diff_start`, `diff_item`, `diff_complete`, `liquibase_cost_estimated`, `conceptmap_loaded`, `conceptmap_validated`, `sqlmesh_seed`, `sqlmesh_run_model`, `sqlmesh_audit`, `orphan_fk_detected`, `compose_up`, `compose_down`, `import_smoke_check`, `binding_check`, `chartsearchai_test_invoked`, `sample_drawn`, `openelis_classification`, `pccp_record_emitted`, `run_complete`
- **Fields per event**: `event_id`, `event_type`, `timestamp` (auto-set by `append_event`), `run_id`, type-specific payload, optional `decision_rationale` for events carrying a reviewer decision
- **FR coverage**: FR-021, SC-009

## 14. PCCP change records

- **Path**: `specs/002-openmrs-demo-data-2-8-remap/pccp/<YYYYMMDD>-<topic>.md`
- **Template**: existing `specs/artifacts/planning/pccp-change-record-template.md`
- **Triggered by**: material changes to ConceptMap, SQLMesh project, module_table_policy, target version pins (image digests), OCL pinned snapshot versions, OpenELIS feasibility classifications

---

## Lifecycle / state transitions

```mermaid
stateDiagram-v2
  [*] --> SourceLoaded: load legacy_27_raw
  SourceLoaded --> Profiled: harness profile (M2-A)
  Profiled --> DiffComputed: schema-diff vs openmrs (CIEL-loaded clean baseline)
  DiffComputed --> LiquibaseCostEstimated: per-changeset cost classifier
  LiquibaseCostEstimated --> ConceptMapReviewed: clinically informed reviewer (M2-C)
  ConceptMapReviewed --> ConceptMapValidated: HL7 FHIR Validator pass
  ConceptMapValidated --> SQLMeshProjectReviewed: SQLMesh project reviewed (M2-D)
  DiffComputed --> SQLMeshProjectReviewed
  LiquibaseCostEstimated --> SQLMeshProjectReviewed: pre-stage decisions absorbed
  SQLMeshProjectReviewed --> SeedEmitted: concept_translation.csv emitted
  SeedEmitted --> Transformed: sqlmesh seed/run/audit (M2-E)
  Transformed --> OrphanFKChecked: orphan-fk-report
  OrphanFKChecked --> Imported: O3 RefApp boots via harness.compose (M2-F)
  Imported --> RefAppTestsRun: chartsearchai mvn -pl api test
  RefAppTestsRun --> BindingChecked: forms/orders/drugs resolve
  BindingChecked --> Sampled: translation-coverage sampler (M2-G)
  Profiled --> OpenELISAnalyzed: feasibility + skeleton (M2-H, parallel)
  ConceptMapValidated --> OpenELISAnalyzed
  Sampled --> ManifestClosed: RunManifest finalized (M2-Z)
  OpenELISAnalyzed --> ManifestClosed
  ManifestClosed --> [*]
```

## Validation rules (cross-artifact)

- Every source concept_id referenced by ≥1 row in `obs`, `conditions`, `diagnosis`, `allergy`, `drug_order`, `encounter_diagnosis`, `concept_set` MUST appear in `concept_translation.csv` with a policy_bucket. Verified by `harness/conceptmap/validate.py` (cross-checks `profile/inventory.json` against the ConceptMap).
- Every diff item with `clinical_meaningful: true` MUST be referenced in at least one SQLMesh model's `description` / `diff_items_covered`. Verified by `harness/transform/run.py` pre-flight.
- Every PCCP change record MUST cite ≥1 before/after record example. Verified by `tests/test_pccp_records.py`.
- `run_manifest.json` MUST validate against `specs/001-harness-control-plane-foundation/contracts/run-manifest-control-plane.schema.yaml` (M0 base) AND `specs/002-openmrs-demo-data-2-8-remap/contracts/run_manifest_002_extensions.schema.yaml` (002 extensions). Verified at run-end and by CI.
- `harness/targets.yaml.targets.chartsearchai.validation_surface.command` MUST be the M2-F cross-target validation invocation; M2-F MUST NOT re-implement chartsearchai test logic.
