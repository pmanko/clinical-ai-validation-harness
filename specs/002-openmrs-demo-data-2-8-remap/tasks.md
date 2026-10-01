# Tasks: Reviewed OpenMRS Corpus and OpenELIS Feasibility

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

This register retains data functionality, requirement/task identity and existing
implementation markers. Checked entries identify recorded implementations, not
current runtime isolation or deployed acceptance; verify changed interfaces before
claiming completion. Reusable migration/terminology utilities need an external
maintained owner, an open umbrella decision. Do not delete those utilities pending
that decision or replace removed workspace management with harness-owned configuration.

The caller prepares source/baseline/build databases and target services. Product
build/test orchestration, restoration, deployments, lifecycle and website delivery
are external. Spec 001 owns readiness/evidence semantics, not a registry/setup API.
Paths below identify current data implementations or intended validation work;
[quickstart](quickstart.md) distinguishes implemented entry points from CLI stubs.

## Reviewed data inputs

- [X] T000c Keep OCL credential resolution outside captured metadata; credentials
  are references/environment inputs, never evidence content.
- [X] T000d Retain versioned CIEL export acquisition with SHA-256/provenance;
  target bootstrap is caller-owned, not part of validation collection.
- [X] T000e Retain deterministic seeded-baseline SQL and provenance snapshots as
  reusable data artifacts; environment reset/restore is outside the runner.
- [X] T000g Retain source-dump import for a supplied disposable data-build database,
  without requiring a named container or harness-managed service.

## Dependencies and foundation

- [X] T001 Keep compatible data-tool dependencies in `pyproject.toml`/`uv.lock`;
  record actual versions rather than duplicate ranges in plans.
- [ ] T002 Document HL7 Validator setup/conformance for mapping review; not a
  general product-build prerequisite.
- [ ] T003 Keep validator version identity and ignored downloaded-tool outputs.
- [X] T004 Retain `harness/profile`, `conceptmap`, `ocl`, `transform`,
  `refapp_binding`, `sampler` and `openelis` data modules pending owner assignment.
- [X] T005 Retain data conformance/sampler/binding/analysis test surfaces.
- [ ] T006 Verify documented data prerequisites and actual module CLI entry points.
- [X] T007 Retain `RunManifest002Extensions` for corpus/mapping/snapshot identity,
  reviewer signoffs and materialized-content evidence.
- [ ] T008 Verify manifest emitters against shared semantics and 002 extensions,
  including nullable revisions/images and no pin/override requirements.
- [ ] T009 Retain immutable versioned OCL snapshot loaders and provenance checks.
- [ ] T010 Test accepted/missing-provenance snapshot inputs with small fixtures.
- [ ] T011 Complete selected data CLI verbs using supplied inputs/settings only;
  no target preparation, workspace initialization or Git lookup.
- [ ] T012 Test actual implemented CLI argument shapes and explicit stub failures.
- [X] T013 Retain FHIR ConceptMap parsing of equivalence, action policy and rationale.
- [X] T014 Retain ConceptMap parsing/profile cross-element tests.
- [ ] T015 Verify material-change records cite before/after records and rationale;
  use the maintained change-record template rather than another placeholder.
- [ ] T016 Resolve selected data/output locations through feature configuration.

## US2 — Profile and terminology inventory (M2-A)

- [ ] T017 Validate inventory artifact shape against `contracts/profile_inventory.schema.yaml`.
- [X] T018 Retain schema-diff contract and clinical-meaning classification tests.
- [ ] T019 Validate Liquibase cost-estimate artifact shape.
- [X] T020 Retain diverse ambiguous/missing terminology, locale, FK and module tests.
- [X] T021 Retain inventory enumeration in `harness/profile/inventory.py` against
  supplied databases; no service lifecycle orchestration.
- [X] T022 Retain reference-source and locale enumeration in `harness/profile/terminology.py`.
- [X] T023 Retain module classification against an explicitly supplied RefApp baseline.
- [X] T024 Retain real schema introspection/diff and record-level clinical classification.
- [ ] T024a Verify supplied CIEL baseline identity and import receipts; environment
  creation/bootstrap belongs to the caller/umbrella.
- [X] T024b Retain deterministic seeded-baseline snapshot/checksum evidence;
  capture required inputs, not instructions to restart a workspace.
- [X] T024c Retain record-level CIEL import error evidence and the ≤0.1% gate,
  including overlap with clinically referenced concepts.
- [ ] T025 Retain Liquibase cost analysis using supplied changelog/runtime metadata.
- [ ] T026 Wire profiling of prepared source/baseline databases; emit inventory,
  terminology, module, schema-diff and cost artifacts without starting services.
- [ ] T027 Emit per-stage events and clinical-difference rationale.
- [ ] T028 Test specific source/target records and rationale, not counts alone.

## US3 — Accepted terminology mapping (M2-C)

- [ ] T029 Test ConceptMap profile shape, single-target/equivalence/policy and source-record examples.
- [ ] T030 Test every clinically referenced source concept appears with an action policy.
- [ ] T031 Test seed augmentation is limited to reviewed concept classes and published reference terms.
- [ ] T032 Test unmodified HL7 Validator pass/fail for diverse invalid mappings.
- [ ] T033 Retain offline OCL candidate mining as advisory, not accepted mapping authority.
- [ ] T034 Retain HL7/profile validation with actionable record/mapping failures.
- [ ] T035 Wire actual candidate/validation CLI entry points without setup orchestration.
- [ ] T036 Author accepted ConceptMap covering all clinically referenced source concepts,
  with target, equivalence, action, source-record examples and rationale.
- [ ] T037 Author the companion clinically informed review with bucket counts,
  signoff, augmentation decisions, open follow-ups and snapshot identity.
- [ ] T038 Emit mapping load/validation events with reviewer/signoff/validator identity.
- [X] T039 Retain deterministic translation seed emission from the accepted ConceptMap.
- [ ] T040 Test emitted seeds match reviewed mapping input, not manual edits.

## US1 — Deterministic transform and clinical preservation (M2-D–G)

- [ ] T041 Validate portable dump schema/data and loadability into a supplied empty database.
- [ ] T042 Validate coverage sample artifact shape.
- [ ] T043 Compare clean replays under documented normalization for SC-004.
- [ ] T044 Inspect externally prepared startup/Liquibase receipts and live readback;
  service startup and restoration are not runner actions.
- [ ] T045 Test form/order/drug binding failures with specific record/concept IDs.
- [ ] T046 Test seeded sampler repeatability and declared-empty buckets.
- [X] T048 Retain supplied-database SQLMesh gateway/settings, without embedded credentials.
- [X] T049 Retain reviewed staging models and composite-key uniqueness checks.
- [X] T050 Retain concept rebinding from reviewed translation seeds.
- [ ] T051 Verify clinical models and translated concept references.
  - [X] T051a Retain drug-order promotion P1 and row-count audit.
  - [X] T051b Retain condition promotion P2 and row-count audit.
  - [X] T051c Retain allergy promotion P3 and row-count audit.
  - [X] T051d Retain test-order promotion P4 and row-count audit.
- [X] T052 Retain explicit reviewed module-data policy and carry-forward models.
- [X] T053 Retain per-record equivalence/action audit views.
- [X] T054 Retain concept coverage, FK, policy, uniqueness and row-floor audits.
- [X] T055 Retain structural reviewer rationale and diff-to-model coverage.
- [X] T056 Retain SQLMesh transform execution/logs and materialized-content evidence;
  the portable dump is built from physical snapshots, not logical view DDL.
- [X] T057 Retain FK-orphan evidence with sample offending records; unresolved
  clinical failures block acceptance, not merely generate a summary.
- [ ] T058 Verify CLI transform wiring and per-stage events against actual implementation.
- [X] T059 Retain direct snapshot-to-build-schema loading.
  - [ ] T059a Verify a supplied disposable schema/baseline for corpus build;
    no service setup or running-deployment promotion.
  - [X] T059b Retain reviewed FK reconciliation seed maps and collision rationale.
  - [X] T059c Retain `harness/load` direct SQL snapshot resolver/copy with column
    projection and per-table replace/merge semantics; no ETL state fields.
  - [X] T059d Retain real REST/FHIR patient readback capability; verify CLI wiring
    separately because the current top-level import-smoke command still uses a stub.
- [ ] T060 Verify forms bind to translated concepts through prepared endpoints.
- [ ] T061 Verify default order types resolve.
- [ ] T062 Verify drug catalog concepts resolve.
- [ ] T063a Verify vitals concepts and record rendering.
- [ ] T063b Verify allergen concepts and record rendering.
- [ ] T063c Verify problem-list concepts and record rendering.
- [ ] T063 Aggregate binding evidence for all six SC-013 concept classes.
- [ ] T064 Wire real import-smoke/binding collection using prepared interfaces;
  product-native test evidence is supplied externally, not built from local sources.
- [ ] T064c Exercise configured real ChartSearchAI chat against translated records;
  preserve Answer/validation/In-Depth/evidence and persisted hydration observations.
- [ ] T064d Resolve final citations against translated records and accepted concepts.
- [ ] T064e Optional browser evidence follows the
  [ChartSearchAI documentation](https://github.com/pmanko/openmrs-module-chartsearchai),
  using an already-prepared target, not a nested checkout.
- [ ] T064f Collect live chat/citation evidence and SC-015 timing without startup,
  indexing/warmup or Compose lifecycle operations.
- [ ] T065 Enumerate nonempty accepted action-policy buckets.
- [ ] T066 Sample with recorded seed/count and inspect REST/FHIR clinical fields.
- [ ] T067 Wire sampler collection/events and specific failure rationale.

## US4 — OpenELIS analysis only (M2-H)

- [ ] T068 Validate feasibility artifact contract.
- [ ] T069 Verify entity/source-column/rationale coverage.
- [ ] T070 Validate terminology and structural mapping skeleton contracts.
- [ ] T071 Independently verify LOINC bridge coverage and gap records.
- [ ] T072 Analyze an explicitly supplied versioned OpenELIS schema artifact with
  reviewed source profile/ConceptMap/terminology snapshots; no fixed source checkout.
- [ ] T073 Emit terminology/structural skeletons, not an executable loader.
- [ ] T074 Render human-readable feasibility from captured analysis artifacts.
- [ ] T075 Wire analysis/events with explicit scaffolding classification and no parity claim.

## Evidence, documentation and verification (M2-Z)

- [ ] T076 Finalize shared manifest/events plus 002 fields, recording only exercised
  targets with supplied/observed origin and nullable revisions; no reference-only Catalyst entry.
- [ ] T077 Record material downstream-impact changes with before/after examples,
  protocol, impact, reviewer rationale and residual risk.
- [ ] T078 Verify README/quickstart accurately distinguish working data interfaces from stubs.
- [ ] T079 Keep agent context aligned with caller-owned preparation and retained corpus scope.
- [ ] T080 Keep shared metadata consumers aligned with 002 extensions.
- [ ] T081 Reconcile external data-remap consumers with accepted mappings and current validation interfaces.
- [ ] T083 Audit diverse ambiguous/missing/unsupported and failure cases; avoid single-record tuning.
- [ ] T084 Verify corpus-build SC-001 budget separately from experiment timing,
  with performance evidence and explicit externally prepared baseline assumptions.
- [ ] T085 Verify actual quickstart entry points and captured evidence on prepared
  targets; do not treat doc checks or stub output as acceptance.

Order: accepted source/baseline → inventory/diff → reviewed ConceptMap → SQLMesh
models/audits → direct data build → external restoration → real readback/binding/
chat/citation sample. OpenELIS analysis can use reviewed inputs in parallel.
Metadata/rationale accompany each stage. Offline reports must use captured packet
inputs only; publishing outputs and product/release decisions remain external.
