# Feature Specification: OpenMRS Demo Data Remap, Import, and OpenELIS Cross-Load Analysis

**Feature Branch**: `002-openmrs-demo-data-2-8-remap`

**Created**: 2026-05-13

**Status**: Draft

**Input**: User description: "we need a robust feature #2 (see the project spec roadmap and artifacts/canvases etc) spec that takes the dataset in ./data, profiles/analyzes it, determines what terminology etc the dataset uses, and maps it to a transformed version that works with 2.8.0 and the most recent ref app, so we can use it as demo data in our OpenMRS work. Also, I want it analyzed for if any parts could be transformed to load into OpenELIS to have same base set of data at some level"

## Clarifications

### Session 2026-05-13

- Q: OpenELIS deliverable depth for this feature → A: Analysis-and-mapping-skeleton only; no OpenELIS loader is executed in this milestone. Real OpenELIS bringup is deferred to a later milestone.
- Q: Format authority for mapping artifacts (OpenMRS 2.7→2.8 mapping and OpenELIS mapping skeleton) → A: Must use a **published, standards-based mapping language/grammar** (not a bespoke project-local schema) and must be **consumable by an existing open transformation/mapping tool or runtime**; the harness integrates with that tool rather than building a bespoke executor. The specific standard and tool are selected during `/speckit-plan`.
- Q: Concept dictionary collision strategy (source 2.7 dictionary vs. the O3 RefApp's seeded CIEL dictionary on Core 2.8.x) → A: **Remap source clinical records onto the O3 RefApp's seeded concept dictionary.** The seeded approach is the basis for a modern demo: AI components, default forms, drug catalog, order types, and UI surfaces are configured against the RefApp's bundled dictionary, so source observations/diagnoses/orders/allergies/conditions must resolve to that dictionary's concept identities. Source concepts that have no equivalent in the seeded dictionary are handled by an explicit accepted policy (remap to nearest semantically-equivalent seeded concept with reviewer rationale, or drop with record-level evidence of impact, or — for a small reviewed set — augment the seeded dictionary via deterministic seed inserts with rationale). Source-only `concept_*` rows are not carried verbatim.
- Q: Terminology as a deliverable → A: **Terminology translation is a first-class P1 deliverable**, not a side effect of the structural transform. A reviewed terminology mapping artifact in a published terminology-mapping standard (ConceptMap-style) is the central artifact; structural SQL transforms consume it unchanged.
- Q: PHI / re-anonymization policy → A: **Source is a public, cleaned, anonymized published dataset.** No PHI scrubbing, no person/narrative re-anonymization, and no credential/auth state reset is part of this feature. The dump is shipped as-is for transform purposes. Credential hygiene for any public-facing deployment of the demo is the deploying environment's responsibility, not this feature's.
- Q: Legacy / unbundled module data policy → A: **Carry legacy module-owned tables and rows forward in parallel as orphans**, mirroring how real OpenMRS distros upgrade (Liquibase migrates Platform/Core; retired-module tables sit orphaned in the DB without affecting the app when their owning modules aren't installed). The transform preserves these tables and their rows as-is. The workflow MUST verify the O3 RefApp boots cleanly with the orphan tables present and exhibits no behavioral effect from them (no failed startup checks, no FK enforcement reaching into orphan tables, no UI surfaces breaking). Only tables that *do* affect RefApp behavior when their module is absent are escalated to the explicit drop / install / remap policy with reviewer rationale and record-level evidence.
- Q: Canary record set authority and coverage → A: **No standalone canary record set.** Clinical-meaning preservation is defined by (a) terminology mapping conformance under the chosen standards-based tool (SC-011, SC-012), (b) deterministic transform output (SC-004), and (c) a **translation-coverage check** that samples records on demand from the produced demo, parameterized by the accepted mapping's translation policy buckets (`equivalent`, `wider`/`narrower`/`inexact`, `unmatched-and-dropped`, `seed-augmented`). The sampled records are not a frozen curated list; the sampler is deterministic given a seed but draws fresh from the produced demo each run. A reviewer who wants a curated exhibit can request one on demand from the same sampler. This removes pre-curated canary artifacts from the spec entirely.

## Critical context: Platform demo data ≠ RefApp demo data

Per the OpenMRS Demo Data wiki (https://openmrs.atlassian.net/wiki/spaces/docs/pages/26273323/Demo+Data) the published `large-demo-data-2-7-0.sql.zip` is for OpenMRS **Platform** releases and the wiki itself states the published demo dumps **"will not work for OpenMRS Reference Application releases."** For the RefApp, the documented path is to set the `referencedemodata.createDemoPatientsOnNextStartup` global property and let the app synthesize fresh demo patients on startup — which produces patients without the rich clinical history this 5,000-patient / ~500,000-observation corpus carries.

This feature exists to bridge that gap: **transform the Platform-only 2.7 corpus into a candidate database that boots cleanly under the modern (O3) Reference Application 3.x on Core 2.8.x**, with the rich clinical history preserved (subject to the terminology translation, module-policy, and review gates defined below). The wiki's "will not work" caveat is exactly what the feature solves.

## Background and Scope Anchor

This feature implements roadmap milestone **M1 – OpenMRS demo data remap and import** (`specs/roadmap.canvas.tsx`) plus an explicit extension: a parallel analytical pass that determines which slices of the same source corpus could be remapped for **OpenELIS Global** (the LIS), so that downstream validation work — including Catalyst (the AI sub-project that consumes OpenELIS Global's data) — can compare clinical AI behavior across an aligned baseline of demo data in both systems.

The single authoritative source corpus is `data/large-demo-data-2-7-0.sql` (OpenMRS Platform/Core 2.7.0 reference database; 143 `CREATE TABLE` statements and 153 `INSERT INTO` batches as observed at spec time). The OpenMRS target is **Platform/Core 2.8.0 with the most recent Reference Application release**. The OpenELIS target is the most recent **OpenELIS Global / Catalyst** schema reachable through the harness adapter contract established in M0.

This spec depends on M0 (harness control plane foundation) and unlocks M4 (OpenMRS retrieval evaluation) and downstream answer/safety lanes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproducible OpenMRS 2.8 demo database from the legacy corpus (Priority: P1)

A harness operator (engineer or evaluator) needs to stand up an OpenMRS Reference Application 3.x (O3) instance on Core 2.8.x loaded with the legacy demo corpus so that OpenMRS-side AI validation runs (chartsearchai, querystore, openmrs_chatbot) have a rich, clinically meaningful patient population to operate against. The operator invokes a deterministic remap-and-import workflow from a clean baseline and ends with an importable database that boots the O3 RefApp without manual repair.

**Why this priority**: Every downstream OpenMRS validation milestone (M4, M5, M6, M7) is blocked until the demo corpus can be imported into a current OpenMRS without altering clinical meaning. This is the critical path.

**Independent Test**: From a clean machine, run the harness remap workflow against `data/large-demo-data-2-7-0.sql`; the produced candidate database boots the O3 RefApp container, REST/FHIR endpoints respond, and a defined set of records drawn by the translation-coverage sampler (FR-015) is retrievable with clinical fields intact.

**Acceptance Scenarios**:

1. **Given** a clean checkout and only `data/large-demo-data-2-7-0.sql` plus reviewed mappings under `datasets/mappings/`, **When** the operator runs the documented remap workflow, **Then** a candidate 2.8.0-compatible database is produced under `artifacts/` with no manual edits and a recorded `run_manifest.json`.
2. **Given** the candidate database, **When** the operator starts the O3 RefApp against it and exercises the import smoke checks, **Then** the platform starts cleanly, Liquibase reports no failed changesets, and the smoke checks pass.
3. **Given** an imported database, **When** the operator runs the translation-coverage check (which samples records on demand from the produced demo, parameterized by the accepted mapping's translation policy buckets — `equivalent`, `wider`/`narrower`/`inexact`, `unmatched-and-dropped`, `seed-augmented`), **Then** each sampled record's clinical fields (translated concept identity, units, value, date, encounter linkage, provider linkage, equivalence label) are surfaced as record-level evidence and reachable via REST/FHIR.
4. **Given** a deliberately altered mapping that changes a clinically meaningful equivalence label or target, **When** the workflow runs, **Then** mapping conformance, deterministic transform diff, or translation-coverage record-level checks fail and the failing records and the specific mapping entries are surfaced (not just an aggregate metric).

---

### User Story 2 - Profiling and terminology inventory before any transform decision (Priority: P1)

Before mappings are reviewed and accepted, an analyst needs a deterministic profile of the source corpus: which OpenMRS tables and columns are populated, which concept dictionaries and reference terminologies are in use, which modules contributed metadata, and where the dataset diverges from a clean Core 2.8.x baseline as produced by booting the O3 RefApp backend against an empty MariaDB. This profile is the input the human reviewer uses to accept or reject LLM-proposed mappings.

**Why this priority**: The constitution forbids accepted behavior from depending on advisory LLM output without review. A reproducible profile and schema/terminology diff is the artifact reviewers actually sign off on; without it, the remap is unreviewable.

**Independent Test**: Run only the profiling stage; verify it emits a machine-readable inventory of tables, row counts, populated columns, distinct terminologies (reference sources), module-owned tables, and a schema/metadata diff against a clean 2.8.0 baseline — all under `artifacts/schema-diff/` with provenance metadata, regardless of whether any transform has run.

**Acceptance Scenarios**:

1. **Given** the source SQL dump, **When** profiling runs, **Then** the output enumerates every table populated, distinct concept reference sources in use (e.g., CIEL, SNOMED CT, LOINC, ICD-10, RxNorm, CPT, MedDRA, AMPATH, locally defined sources), counts of mapped vs. unmapped concepts, and the locale set covered by `concept_name`.
2. **Given** the profile output, **When** compared against a freshly built clean Core 2.8.x baseline (produced by the O3 RefApp backend), **Then** a diff identifies: tables present in source but not target, tables present in target but not source, columns added/removed/retyped, module-owned tables (with the contributing module), and Liquibase changeset deltas.
3. **Given** the diff, **When** an LLM produces a mapping proposal, **Then** the proposal is stored as advisory-only and is not consumable by the transform stage until it is promoted into `datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json` by a reviewer with a recorded rationale.
4. **Given** a tables-only inventory without terminology details, **When** the reviewer inspects it, **Then** the workflow flags terminology coverage as incomplete and refuses to advance to the transform stage.

---

### User Story 3 - Terminology translation as a first-class reviewed deliverable (Priority: P1)

In OpenMRS, terminology *is* the data model: the meaning of every observation, diagnosis, order, allergy, and condition is carried by its concept reference, and that reference is read by the RefApp UI, the bundled forms, the drug catalog, the order-type system, and every AI/retrieval component this demo exists to exercise (chartsearchai, querystore, openmrs_chatbot). A faithful, reviewed terminology translation from the 2.7 source dictionary onto the O3 RefApp's seeded CIEL dictionary (on Core 2.8.x) is therefore not a side effect of the transform — it is **the** central deliverable. A clinically informed reviewer must be able to inspect, approve, and audit the terminology mapping independently of structural SQL transforms.

**Why this priority**: Every downstream OpenMRS AI/UI surface reads concepts; a structurally clean import with a poor terminology mapping is a broken demo that silently misleads validation. The terminology artifact is also the only piece that has any chance of being reused for OpenELIS analysis. It is at minimum co-P1 with the structural import.

**Independent Test**: From the profile output, produce a standalone reviewed **terminology mapping artifact** in a published terminology-mapping standard (a FHIR R4 ConceptMap or equivalent) that, for every source concept referenced by a clinical record in the corpus, names: source concept identity (id + UUID + display + source reference terms), target seeded-dictionary concept identity, FHIR R4 ConceptMap equivalence label, reviewer rationale, and the policy bucket (`remap` / `seed-augment` / `drop`). The artifact validates under an unmodified open ConceptMap-aware tool and is consumed unchanged by the structural transform.

**Acceptance Scenarios**:

1. **Given** the profile from User Story 2 listing all source concept references used by clinical records, **When** the terminology mapping artifact is produced, **Then** every such source concept appears in the artifact with a target, an equivalence label, a rationale, and a policy bucket; zero unspecified entries remain.
2. **Given** the terminology mapping artifact, **When** validated by an unmodified open ConceptMap-aware tool (selected at plan time), **Then** it parses, every equivalence label is one of the standard's defined values, and structural validation passes — proving the artifact is conformant rather than harness-internal.
3. **Given** a source concept with no semantically equivalent seeded target, **When** the reviewer inspects the artifact, **Then** the entry shows a non-`equivalent` label (`wider` / `narrower` / `inexact` / `unmatched`), the chosen policy bucket, and the rationale for choosing that policy — never a silent default.
4. **Given** a candidate change to the terminology mapping that would alter the equivalence label or target of any concept already used by ≥1 clinical record in the demo, **When** the change is proposed, **Then** a PCCP-style change record is produced citing before/after concept identities, affected source records, and the reviewer's rationale before the change is accepted.
5. **Given** the accepted terminology mapping, **When** the structural transform runs, **Then** it consumes the mapping artifact unchanged (no inline overrides, no per-row exceptions hidden in SQL) — terminology authority lives in one place.

---

### User Story 4 - OpenELIS cross-load feasibility analysis from the same corpus (Priority: P2)

A validation lead wants the same source corpus analyzed for which clinical slices — patients, providers, locations, lab-relevant orders/results, encounters, specimens, and reference terminology — *could* be transformed into an OpenELIS Global-compatible load so that both OpenMRS and OpenELIS demos could later share a common baseline of identities and clinical events at some defined level of fidelity. This feature delivers the **analysis and machine-readable mapping skeleton only**; executing a real OpenELIS Global load is explicitly deferred to a later milestone. Catalyst (`targets/catalyst` submodule) is the documented umbrella AI sub-project entry point that a future loader feature would orchestrate from; no Catalyst code is invoked here.

**Why this priority**: Cross-system demo parity unlocks future cross-project AI validation comparisons (an explicit roadmap "expansion" goal). Doing the analysis now, while the OpenMRS profile is fresh, costs far less than reconstructing it later. But the OpenMRS path must work first, so this is P2.

**Independent Test**: Produce a written feasibility report plus a machine-readable mapping skeleton that, for each candidate OpenELIS entity (patient, provider, organization/location, test/analyte, order, result, specimen, reference term), states: source tables and columns in the OpenMRS corpus that could supply it, expected fidelity level (full / partial / synthesized / not feasible), terminology translation required, and the smallest viable demo slice that would produce a coherent OpenELIS dataset. No loader execution against a live OpenELIS target is required to pass this story.

**Acceptance Scenarios**:

1. **Given** the OpenMRS profile from User Story 2, **When** the OpenELIS analysis runs, **Then** the report names every candidate OpenELIS entity and classifies each as full / partial / synthesized / not-feasible with the source columns and a rationale linked to specific source records.
2. **Given** the analysis output, **When** a reviewer opens the mapping skeleton, **Then** it is machine-readable and structured so a future OpenELIS-loader feature can consume it directly without re-deriving classifications from raw SQL.
3. **Given** an OpenELIS entity classified as "not feasible," **When** the report is reviewed, **Then** the reason is recorded in rationale (missing source field, semantic mismatch, terminology unmappable) so future work can revisit it deliberately.
4. **Given** the OpenELIS analysis artifacts, **When** the harness emits its run manifest, **Then** the manifest captures dataset version, mapping-skeleton version, and the explicit label that no OpenELIS load was executed under this feature — preventing the analysis from being mistaken for release evidence of cross-system parity.

---

### Edge Cases

- **Concept references that point at terminology versions no longer carried by the O3 RefApp** (e.g., a CIEL version mismatch): the workflow must surface the affected concepts, decide deterministically whether to remap, retain, or stub them, and record why.
- **Module-owned tables present in 2.7.0 but unbundled in the modern (O3) RefApp distro** (e.g., legacy form entry, HL7 queues, htmlformentry): default policy is **carry forward as orphan** (mirroring real distro upgrade behavior). Tables that demonstrably affect RefApp behavior when their owning module is absent escalate to drop / install-module / remap with reviewer rationale and record-level evidence.
- **Liquibase changeset divergence**: changesets recorded in `liquibasechangelog` that do not exist in the Core 2.8.x baseline must be reconciled without leaving the database in a state where the platform refuses to start.
- **Patient identifier types and locations** that do not exist in the RefApp's seeded defaults: the workflow must extend or remap rather than silently drop, and the import smoke must verify every imported patient resolves through REST.
- **Foreign key fan-out**: dropping or remapping a row in `concept`, `person`, `encounter_type`, or `location` cascades widely; the workflow must detect orphans before import and either repair or fail loudly.
- **Provider, user, and role rows** referenced by clinical records but tied to outdated authentication schemas: must remap to RefApp roles without granting unsafe defaults.
- **Locale-tagged concept names** absent for locales the RefApp expects: workflow must either backfill via mapping or document the gap.
- **OpenELIS-side terminology gap**: an analyte concept exists in the OpenMRS corpus but has no LOINC mapping; the analysis must record the gap rather than synthesize an incorrect code.
- **Empty-answer / missing-evidence cases** during retrieval-readiness checks must be represented explicitly (per constitution V), not silently passed.
- **Advisory LLM output drift**: if the LLM mapping proposal changes between runs, the accepted YAML must remain stable; only reviewer-promoted changes affect transform behavior.

## Requirements *(mandatory)*

### Functional Requirements

#### Profiling and terminology inventory

- **FR-001**: The system MUST profile `data/large-demo-data-2-7-0.sql` into a machine-readable inventory of populated tables, row counts, populated columns, and per-table primary-key ranges, written under `artifacts/schema-diff/`.
- **FR-002**: The system MUST enumerate every concept reference source present in `concept_reference_source` and report the number of `concept_reference_map` rows per source, identifying at least: CIEL, SNOMED CT, LOINC, ICD-10, RxNorm, CPT, MedDRA, and any locally defined source observed.
- **FR-003**: The system MUST report the locale coverage of `concept_name` and the set of locales referenced by `global_property` and `allowed locale list`, and flag locales the O3 RefApp expects but the source lacks.
- **FR-004**: The system MUST produce a schema and metadata diff between the source corpus and a freshly built clean Core 2.8.x baseline (the schema produced by booting the O3 RefApp backend against an empty MariaDB), classifying every difference as: tables only-in-source, tables only-in-target, column added/removed/retyped, index/constraint difference, module-owned, or Liquibase changeset delta.
- **FR-005**: The system MUST identify module-contributed tables in the source (e.g., legacy form-entry, HL7, htmlformentry, dataintegrity) and label whether each is bundled, optional, or removed in the modern (O3) RefApp distro.

#### Mapping authority and review

- **FR-006**: The system MUST keep LLM-produced mapping proposals strictly advisory; they MUST be written to a clearly labelled advisory artifact path and MUST NOT be consumed by transform steps.
- **FR-007**: The system MUST require accepted mappings to live in reviewed configuration under `datasets/mappings/` (path canonical; file extension determined by the chosen standard). The accepted ConceptMap (`openmrs-2.7-to-2.8.conceptmap.json`) is a small file: **(a) one identity-bridge element** that maps the entire source concept-id space to the seeded-CIEL space via a single deterministic rule (see research.md §R-bridge-rule), plus **(b) one element per structural promotion rule** (one per typed clinical table the transform synthesizes from `obs` — see FR-029–FR-032). Each element MUST carry reviewer rationale and a source-record example. A companion `datasets/mappings/openmrs-2.7-to-2.8.review.md` records per-element rationale plus the schema-diff-items-to-models index required by `contracts/sqlmesh_project.profile.md`.
- **FR-008**: Coverage gates for the transform — split into one hard determinism gate and one iterative-review gate:
  - **(a) Identity-rebind coverage (hard, deterministic).** The transform MUST refuse to execute when any legacy concept_id referenced by ≥1 source record has no entry in `concept_translation.csv`. Coverage is measured 100% on the current corpus (457 / 457 distinct obs-referenced concepts via the §R-bridge-rule UUID pattern); any future drop in coverage is a determinism failure and halts the transform.
  - **(b) Structural-diff coverage (iterative).** The transform MUST list every schema/metadata-diff item flagged `clinical_meaningful: true` (per research.md §R5) that is not covered by an accepted ConceptMap element, a `policy:drop` row in `module_table_policy.csv`, or a `policy:carry-forward` row. Reviewer + project-owner decide iteratively whether to advance, drop, or extend coverage. This is demo-data — validation loops on iteration, not on pre-flight gate hardness.

#### Concept dictionary and terminology translation

- **FR-CD1**: The transform MUST treat **a CIEL concept dictionary explicitly loaded into the clean Core 2.8.x baseline** (via the bundled `openmrs-module-openconceptlab` offline-import path, per research.md §R-Terminology-Stack) as the authoritative dictionary in the produced demo database. Note: a stock O3 RefApp install does NOT ship CIEL pre-loaded — only the openconceptlab module itself; the harness explicitly performs the CIEL load as the M2-A clean-baseline-construction step before snapshotting. Source-only `concept`, `concept_name`, `concept_reference_map`, and `concept_reference_source` rows MUST NOT be carried verbatim; clinical records (observations, diagnoses, orders, allergies, conditions, drug orders) MUST reference the loaded-CIEL concept identities after transform.
- **FR-CD2**: Every source-concept-to-target-concept translation MUST carry a **published-standard equivalence label** (e.g., FHIR ConceptMap `equivalence`: `equivalent` / `equal` / `wider` / `narrower` / `inexact` / `unmatched`) and a reviewer-recorded rationale. Translations without an explicit equivalence label MUST NOT be accepted into the authoritative mapping.
- **FR-CD3**: Source concepts with no semantically equivalent target in the seeded dictionary MUST be resolved by exactly one of: (a) **remap** to the closest target with an honest non-`equivalent` equivalence label and rationale, (b) **deterministic seed augmentation** — extend the seeded dictionary with a small reviewed set of additional concepts (with reference mappings to standard terminologies where available) and rationale for why the seeded dictionary alone is insufficient, or (c) **drop** the affected source clinical records with record-level evidence of clinical impact. No source concept may be left in an undefined state.
- **FR-CD4**: The terminology mapping MUST be expressed in a published terminology-mapping standard (per FR-027) so equivalence labels are interoperable with downstream clinical tooling and with the OpenELIS analysis.
- **FR-CD5**: After transform, the demo database MUST be exercised against Ref App-bundled forms, default order types, and drug catalog to confirm AI/UI surfaces resolve the translated concepts; failures here surface specific concept_ids and the records that depend on them, not aggregate counts.

#### Deterministic transform and import

- **FR-009**: The system MUST execute transforms deterministically from a clean baseline with no hidden manual repair steps; rerunning the workflow against the same inputs MUST produce byte-identical (or explicitly documented stable) transform outputs.
- **FR-010**: The system MUST produce a candidate database artifact that boots under OpenMRS Core 2.8.x running the modern (O3) Reference Application 3.x without Liquibase failures and without manual SQL edits between produce-and-boot.
- **FR-011**: The system MUST capture, for every transform, the source-record example, the target-record outcome, and the rationale (which mapping rule applied), so reviewers can trace any transformed row back to its source.
- **FR-012**: The system MUST handle module-owned tables under a **carry-forward-as-orphan default**: module-owned tables and rows present in the source are preserved verbatim in the target database, matching real OpenMRS distro upgrade behavior. The workflow MUST verify the O3 RefApp boots cleanly with these orphan tables present and exhibits no behavioral effect from them (startup checks pass, FK enforcement does not reach into orphan tables, RefApp UI/REST/FHIR surfaces are unaffected). Tables that *do* affect RefApp behavior when their owning module is absent MUST be escalated to an explicit reviewed policy (drop with record-level impact evidence / install the owning module / remap data into a still-bundled equivalent) with reviewer rationale recorded against each escalation.
- **FR-013**: The system MUST detect and report orphaned foreign keys created by mapping/dropping decisions before any database is offered as importable, and MUST either repair them deterministically or fail the run.

#### Import smoke and clinical-meaning preservation

- **FR-014**: The system MUST exercise import smoke checks against the imported O3 RefApp that verify: platform startup, Liquibase health, REST `/ws/rest/v1/patient` and `/ws/rest/v1/encounter` readability, FHIR endpoints where applicable, search index population sufficient for retrieval-evaluation readiness, and reference-application UI navigability for records drawn by the translation-coverage sampler.
- **FR-015**: The system MUST provide a **translation-coverage check** that, given the accepted terminology mapping, deterministically samples records on demand from the produced demo across every translation policy bucket declared in the mapping (`equivalent`, `wider`/`narrower`/`inexact`, `unmatched-and-dropped`, `seed-augmented`) and verifies each sampled record's clinical fields — translated concept identity, units, value, date, encounter linkage, provider linkage, and equivalence label — survive round-trip via the RefApp's REST/FHIR surfaces. No pre-curated canary record list is required; the sampler is deterministic given a seed but draws fresh from the produced demo on each run.
- **FR-016**: The system MUST treat aggregate counts as supporting signals only; pass/fail decisions for clinical-meaning preservation MUST be backed by inspected record-level evidence with explicit rationale.

#### OpenELIS cross-load analysis (parallel pass)

- **FR-017**: The system MUST produce an OpenELIS cross-load feasibility report that, for each candidate OpenELIS entity (at minimum: patient, provider, organization/location, test/analyte concept, order, result/observation, specimen, reference terminology), classifies feasibility as full / partial / synthesized / not-feasible with source-column references and rationale.
- **FR-018**: The system MUST identify which source terminologies (LOINC especially) provide direct OpenELIS-side compatibility and which require translation or are unmappable; gaps MUST be recorded rather than papered over with synthesized codes.
- **FR-019**: The system MUST define a "smallest viable demo slice" for OpenELIS in writing (entities, identifier scheme, terminology translation required) and emit a **machine-readable mapping skeleton** consumable by a future OpenELIS-loader feature. Executing a load against a live OpenELIS target is explicitly out of scope for this feature.
- **FR-020**: The system MUST clearly label OpenELIS analysis artifacts as feasibility analysis only — not release evidence of cross-system parity — in all manifests and reports, and MUST NOT permit them to be promoted as parity evidence without a future loader feature that exercises a real OpenELIS path.

#### Provenance, metadata, and adapter contract

- **FR-021**: Every run MUST emit a `run_manifest.json` and `events.jsonl` capturing: source dataset path and checksum, source version, accepted mapping version, advisory LLM proposal version (if any) with explicit advisory label, OpenMRS target version, OpenELIS target version (if exercised), adapter invocation identity, git revision, and reviewer decisions referenced.
- **FR-022**: The system MUST invoke real OpenMRS and OpenELIS startup/setup paths through the M0 adapter contract for any release-evidence claim; any fixture-only path MUST be labelled as development scaffolding and excluded from release evidence. For this feature, the OpenMRS portion is real-path; OpenELIS analysis output is labelled `evidence_status: scaffolding` per FR-020 and is not promoted as release evidence.
- **FR-023**: The system MUST emit PCCP-style change records for material mapping, transform, or import changes that would alter clinical meaning of the imported corpus, including before/after record examples and reviewer rationale.

#### Data sensitivity and credential handling

- **FR-PHI1**: The source `data/large-demo-data-2-7-0.sql` is a **public, cleaned, anonymized published demo dataset**. This feature MUST NOT apply PHI scrubbing, person/narrative re-anonymization, identifier reshuffling, date-shifting, or credential/auth-state reset to the source contents. Person, provider, user, role, and narrative columns are carried through transforms by structural rules only.
- **FR-PHI2**: The harness MUST record the source dataset's provenance (origin URL or citation, license, version, checksum) in the run manifest so any party deploying the produced demo can verify what they are deploying.
- **FR-PHI3**: Credential hygiene for any deployment of the produced demo (e.g., changing default admin passwords before exposing the instance on a public network) is **out of scope** for this feature and belongs to the deploying environment's documentation, not the transform.

#### Scenario diversity and failure surfaces

- **FR-024**: The workflow MUST include scenario-diverse checks covering: ambiguous mappings, missing-evidence records, unsupported claims (e.g., source obs whose concept cannot be resolved in the target), terminology drift between source and target, and import failure surfaces (Liquibase, FK orphan, locale gap). Each scenario MUST surface specific record IDs, not only aggregate pass/fail.

#### Standards-based mapping format and tool integration

- **FR-025**: Mapping artifacts (both the OpenMRS 2.7→2.8 accepted mapping and the OpenELIS mapping skeleton) MUST be expressed in a **published, standards-based mapping language or grammar** suitable for the data shapes involved (relational-to-relational and/or clinical-record-to-clinical-record). Bespoke project-local schemas invented solely for this feature are not acceptable as the authoritative mapping format. The specific standard is selected during `/speckit-plan` after a documented comparison of candidate standards (e.g., FHIR StructureMap / FHIR Mapping Language, ConceptMap for terminology, ETL-DSLs such as Apache Camel routes / Pentaho Kettle, modern lightweight options such as JOLT/JSLT, dbt-style models, dlt pipelines, Singer/Meltano taps, or Airbyte connectors); the plan MUST justify the choice against criteria including: clinical-domain fit, reviewability, determinism, tool maturity, and licensing.
- **FR-026**: The chosen mapping format MUST be **executable by an existing open-source transformation/mapping tool or runtime**; the harness integrates with that tool through the M0 adapter contract rather than implementing a bespoke executor for the mapping grammar. The plan MUST identify the tool/runtime, its version pin, and the adapter invocation contract.
- **FR-027**: Terminology mappings (e.g., source concept ↔ target concept, source reference term ↔ target reference term) MUST be representable in a **published terminology-mapping standard** (such as a FHIR R4 ConceptMap resource or equivalent), regardless of which mapping language is chosen for structural transforms. This keeps terminology decisions interoperable with downstream clinical tooling and with the OpenELIS skeleton.
- **FR-028**: The harness MUST emit, alongside accepted mapping artifacts, a small set of **conformance tests** that the chosen standard's tool can run against the artifacts to verify they parse and execute under that tool's stated semantics, so that "valid mapping" is defined by the standard's tool rather than by harness-internal checking only.

### Structural promotion (obs → typed clinical tables)

- **FR-029** — The transform MUST synthesize typed clinical rows from `obs` per the rules in the table below (P1–P4). Each rule is encoded as one structural-promotion element in the accepted ConceptMap (FR-007) and as one SQLMesh model under `datasets/transforms/sqlmesh/models/clinical/`. Field mapping is canonical in `data-model.md` §R-promotion-rules; cross-cutting decisions (obs preservation, UUID strategy, vaccine handling, orderer source, sampler strategy) are in research.md §R-typed-table-promotion.

  | Rule | Selector (from `obs`, voided=0) | Target table | Measured rows |
  |---|---|---|---|
  | **P1** | `value_coded.concept_class = 'Drug'` | `drug_order` | 43,412 |
  | **P2** | `concept_id = 6042` ('PROBLEM ADDED') | `conditions` | 4,451 |
  | **P3** | `concept_id IN (6011, 6012, 1083) AND value_coded = 1065 ('YES')` | `allergy` | 2 |
  | **P4** | `concept.concept_class = 'Test' AND concept.concept_datatype = 'Coded'` | `test_order` | 1,120 |

  Source rows are preserved and back-linked via `obs.order_id`. Row counts above are measured directly from the first end-to-end transform run against the live stack; they are signals to report in `transform.report.json` for iterative review, not exact-match gates. Total promoted: 48,985 (10.3% of legacy obs); residual obs ~428,013 (89.7%).

### Key Entities

- **Source corpus**: `data/large-demo-data-2-7-0.sql` — OpenMRS 2.7.0 reference dump with patients, encounters, observations, drug orders, allergies, conditions, diagnoses, concept dictionary, terminology references, module-owned tables, Liquibase state.
- **Profile inventory**: machine-readable description of the source corpus (tables, rows, populated columns, terminologies, locales, modules).
- **Schema/metadata diff**: structured comparison between source corpus and a clean Core 2.8.x baseline produced by the O3 RefApp backend.
- **Advisory mapping proposal**: LLM-generated mapping suggestions, clearly labelled, not consumable by transforms.
- **Accepted mapping**: reviewed mapping artifact under `datasets/mappings/` expressed in a published standards-based mapping language (specific standard selected at plan time), with rationale per entry and executable by an existing open mapping tool.
- **Terminology mapping artifact**: source-↔-target concept and reference-term mappings represented in a published terminology-mapping standard (e.g., FHIR R4 ConceptMap), interoperable with downstream clinical tooling.
- **Transform output**: deterministic candidate database artifact ready for OpenMRS 2.8.0 import.
- **Translation-coverage sampler**: deterministic on-demand sampler that, given the accepted terminology mapping and a seed, draws records from the produced demo covering every translation policy bucket and reports record-level evidence (no pre-curated record list maintained).
- **Import smoke result**: per-check pass/fail with record-level evidence.
- **OpenELIS feasibility report**: per-entity classification (full/partial/synthesized/not-feasible) with rationale.
- **OpenELIS smallest-viable slice (analysis only)**: per-entity description (entities, identifier scheme, terminology translation required) that a future loader feature would consume to load into OpenELIS Global. Catalyst (`targets/catalyst` submodule) is the documented umbrella AI sub-project entry point, not a load target itself.
- **Run manifest**: provenance record per harness invocation.
- **Reviewer decision / PCCP change record**: durable record of mapping or transform acceptances/changes with rationale.

### Evidence, Provenance & Data Boundaries *(mandatory)*

- **Clinical evidence records**: source `patient`, `person`, `person_name`, `person_address`, `encounter`, `obs`, `conditions`, `diagnosis`, `allergy`, `drug_order`, `concept`, `concept_name`, `concept_reference_map`, `concept_reference_source`, plus their transformed counterparts in the candidate database and any OpenELIS loader output.
- **Decision rationale**: per accepted mapping entry, per dropped/remapped row class, per translation-coverage sampler finding, per OpenELIS feasibility classification — recorded in the accepted FHIR R4 ConceptMap JSON, SQLMesh model descriptions, transform logs, and feasibility report.
- **Operating metadata**: `run_manifest.json`, `events.jsonl`, profile inventory, schema/metadata diff, advisory proposal file, accepted ConceptMap JSON, accepted SQLMesh project, transform run logs, import smoke results, OpenELIS feasibility report, PCCP change records.
- **Accepted deterministic inputs**: reviewed FHIR R4 ConceptMap JSON under `datasets/mappings/`, reviewed SQLMesh project under `datasets/transforms/sqlmesh/`, pinned OCL snapshots under `datasets/sources/ocl/`, adapter configurations.
- **Advisory inputs**: LLM mapping proposals, research notes, analytical commentary on terminologies — all labelled and excluded from transform consumption.
- **PCCP/change record needs**: any material change to accepted mappings (structural or terminology), transform logic, target-version pinning, translation-coverage sampler policy, or OpenELIS feasibility classifications triggers a change record citing before/after record examples and reviewer rationale.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean baseline, an operator can produce a candidate database that boots under the O3 RefApp 3.x on Core 2.8.x, and pass import smoke checks in under 60 minutes of wall time on a developer machine, with zero manual SQL edits between transform and boot.
- **SC-002**: For every translation policy bucket declared in the accepted terminology mapping (`equivalent`, `wider`/`narrower`/`inexact`, `unmatched-and-dropped`, `seed-augmented`), the on-demand translation-coverage sampler can draw records from the produced demo whose clinical fields (translated concept identity, units, value, date, encounter/provider linkage, equivalence label) survive RefApp REST/FHIR round-trip, with record-level evidence per sampled record; zero buckets are sampler-empty unless the mapping itself declares the bucket empty.
- **SC-003**: 100% of differences flagged "clinically meaningful" in the schema/metadata diff are covered by either an accepted mapping entry, an explicit accepted drop with rationale, or an explicit accepted module-carry-forward — and zero such items are left unhandled when the transform stage runs.
- **SC-004**: Re-running the entire workflow on the same inputs produces transform outputs that match the prior run (byte-identical where possible; otherwise stable under a documented normalization), demonstrating determinism.
- **SC-005**: The profile inventory enumerates every concept reference source in use and reports per-source concept coverage; a reviewer can identify within 10 minutes which terminologies the demo data depends on.
- **SC-006**: Advisory LLM mapping output is never consumed by transforms; an audit of the run manifest can show, for every accepted mapping entry, the reviewer identity and the rationale recorded at acceptance time.
- **SC-007**: The OpenELIS feasibility report classifies every candidate entity (patient, provider, organization/location, test/analyte, order, result, specimen, reference terminology) with a source-column citation and rationale; reviewers reach agreement on classifications without re-deriving them from raw SQL.
- **SC-008**: A reviewer can hand the OpenELIS mapping skeleton to a follow-up loader feature and start implementing without re-deriving any per-entity feasibility classification from raw SQL; every entity carries source-column references, rationale, and a proposed shared-identifier scheme to OpenMRS patients.
- **SC-009**: Every release-evidence run emits a complete `run_manifest.json` and `events.jsonl` that link transform decisions, mapping versions, and adapter invocations back to specific source and target records.
- **SC-010**: Failure modes are observable at record level: when a smoke check fails, the failing patient/encounter/observation IDs (and the specific assertion violated) are surfaced; no failure is reported as an aggregate count alone.
- **SC-011**: All authoritative mapping artifacts produced by this feature parse and execute under the chosen open-source standards-based mapping tool's stated semantics; conformance tests pass against an unmodified release of that tool, demonstrating the harness has not silently extended the standard.
- **SC-012**: **Terminology coverage is total and labelled.** Every source concept referenced by ≥1 clinical record in the corpus appears in the accepted terminology mapping artifact with a target identity, a published-standard equivalence label, a policy bucket (`remap` / `seed-augment` / `drop`), and reviewer rationale. Zero source-record-referenced concepts are left unmapped or unlabeled.
- **SC-013**: After import, the demo passes a **RefApp terminology-binding check**: bundled forms render against translated concepts, default order types resolve, the drug catalog resolves drug concepts referenced by the corpus, and the translation-coverage sampler (parameterized to cover each major concept class — lab, vitals, problem, allergen, drug, diagnosis) draws ≥1 record per class that renders correctly in the O3 RefApp UI; failures surface specific record IDs and concept_ids.
- **SC-014**: A clinically informed reviewer can audit terminology decisions independently of the SQL transforms: opening only the terminology mapping artifact gives them every source→target decision, equivalence label, policy bucket, and rationale needed to approve or reject the translation without reading transform code.
- **SC-015**: **First real milestone — live chartsearchai chat against translated demo.** From a clean checkout, an operator can reach the chartsearchai chat UI showing a clinically grounded answer with at least one citation about a named patient drawn from the translated demo dataset, in ≤ 90 minutes wall-time on a developer machine. The path follows the published chartsearchai README (`targets/chartsearchai/README.md`): `docker compose up --build` against the chartsearchai docker-compose (image tag `nightly-chartsearch`), with the produced `refapp_28_demo.sql` substituted for the synthetic `referencedemodata.createDemoPatientsOnNextStartup` patients. Citations in the response MUST resolve to records present in the translated demo. This is the user-visible MVP of feature 002 and the satisfaction of Constitution Principle I (real chartsearchai production path against our translated data).

## Assumptions

- The single source corpus for this feature is `data/large-demo-data-2-7-0.sql`. No additional source dumps are introduced under this feature.
- The OpenMRS target is Core 2.8.x paired with the modern (O3) Reference Application 3.x — currently pinned to RefApp 3.6.0 in `compose/openmrs-2.8-refapp.yml`; the exact RefApp version is recorded in the run manifest.
- OpenELIS work in this feature is **analysis and a machine-readable mapping skeleton only**; no OpenELIS Global instance is brought up or loaded under this milestone. Catalyst (the AI sub-project, `targets/catalyst` submodule) is referenced as the documented umbrella entry point only. A future feature will execute a real OpenELIS Global load and is expected to consume the mapping skeleton produced here.
- M0 (harness control plane foundation) provides the adapter contract used to bring up the real OpenMRS RefApp 3.x stack (Core 2.8.x). OpenELIS Global bringup is deferred to a future feature; this feature consumes Catalyst's submodule pointer as documentation only.
- "Most recent RefApp" means the latest tagged release at the time of run, recorded in the manifest; if the released RefApp version changes, a new run produces a new manifest entry rather than silently rebasing.
- LLM-assisted analysis is allowed for profiling commentary, mapping proposals, and feasibility reasoning, but is strictly advisory per the project constitution; accepted behavior lives only in reviewed configuration and code.
- No pre-curated canary record list is maintained. Inspection coverage is produced on demand by a deterministic translation-coverage sampler parameterized off the accepted mapping's translation policy buckets; reviewers who want a curated exhibit obtain it from the sampler.
- "Same base set of data at some level" for OpenELIS is interpreted as: shared patient identities and, where feasible, shared analyte/order/result references; full clinical parity between OpenMRS and OpenELIS is explicitly out of scope.
- Modules whose schemas appear in the source but are not bundled with the modern (O3) RefApp distro (e.g., legacy form-entry, HL7 queues) are by default **carried forward as orphan tables** to match real distro upgrade behavior; only those tables that demonstrably affect RefApp behavior are escalated to an explicit reviewed decision (drop / install module / remap).
- The source SQL dump is a publicly-published, cleaned, anonymized OpenMRS demo corpus; no PHI risk attaches to it and no anonymization or credential-reset work is required as part of this feature.
- Reviewers (engineering plus, where clinical interpretation matters, a clinically informed reviewer) are available to sign off on accepted mappings and PCCP-style change records; their identity is recorded.
- Validation of the candidate database depends on real OpenMRS and OpenELIS startup paths being executable from the harness; if a real path cannot run in a given environment, the run is labelled development scaffolding and excluded from release evidence.
- **Demo-data posture**: this is demo data, not a production migration. Replication + determinism (SC-004) stay non-negotiable — two runs of the same inputs produce identical transform outputs. Validation is **iterative**: run the transform, inspect outputs, adjust the ConceptMap or a model, re-run. Acceptance is a consensus-guided review with the project owner; heavyweight PCCP records (FR-023) are reserved for changes that materially affect downstream consumers (chartsearchai, OpenELIS), not for per-rule tuning during M2-A iteration.

## Implementation Status

Live snapshot of progress against the milestones above. Detail is in `tasks.md`; measured signals are kept here because they shape FR-007/008/029.

| Milestone | Status | Evidence |
|---|---|---|
| Operator infra (T000a–g) | ✅ done | PRs #5, #6 |
| Public docs site (T000h–k) | ✅ done | PRs #6–9; live at `pmanko.github.io/clinical-ai-validation-harness/` |
| Profile inventory (T021) | ✅ done | `artifacts/legacy-27-raw-baseline/profile/inventory.json`, dump sha256 `a7ca4bbe…` |
| CIEL load + snapshot (T024a/b) | ✅ done | `datasets/sources/ocl/CIEL/v2026-04-28/` |
| CIEL import-error audit (T024c) | ✅ done | `artifacts/dev-20260514-212318/profile/ciel-import-errors.json` |
| Foundational (T001–T016) | ⏳ next | deps, manifest extensions, ConceptMap loader |
| Accepted ConceptMap + seeds | ⏳ pending | drives the SQLMesh transform |
| SQLMesh transform | ⏳ pending | produces `refapp_28_demo.sql` |
| Loadback + sampler | ⏳ pending | clinician opens O3, sees rebound + promoted rows |
| Schema diff + M2-A gate | ⏳ pending | closes FR-008(b) iteration |

### Measured signals driving FR-007/008/029

**Source corpus** (T021): 5,284 patients · 476,973 obs · 14,316 encounters · 0 rows in `allergy`/`conditions`/`orders`/`drug_order` · 0 reference_map rows · 457 distinct concept ids referenced in `obs`.

**Bridge rule coverage** (live join): **457 / 457 (100%)** of obs-referenced concepts resolve to a CIEL concept via `uuid = RPAD(CAST(legacy.concept_id AS CHAR), 36, 'A')`. Drives FR-008(a) — see `research.md` §R-bridge-rule.

**CIEL import** (T024c): 358,026 items, 133 errors (**0.0371%**, under 0.1% gate). 23 root concepts; **0 overlap** with the 457 legacy-referenced concepts → non-blocking. See `research.md` §R-Import-Error-Tolerance.
