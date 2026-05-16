# Phase 0 — Research

**Feature**: 002-openmrs-demo-data-2-8-remap
**Date**: 2026-05-13

This phase resolves the plan-shaped open items from `/speckit-clarify` and records the technical decisions for `/speckit-plan`. Decisions reflect clarification-session updates from the user (FHIR is not a terminology authority; CIEL via OCL is; LOINC is the OpenMRS↔OpenELIS bridge) and the comparative ETL/transformation-tooling research summarized at the bottom of this file.

## Terminology stack (corrected baseline for all decisions below)

- **Terminology authority on the OpenMRS side**: **OCL (Open Concept Lab)** managing **CIEL**. The 2.7 source dictionary is a CIEL snapshot of some vintage; the O3 RefApp's seeded dictionary (running on Core 2.8.x) is also a CIEL subset (different vintage / curated subset).
- **Cross-terminology references**: LOINC (labs), SNOMED CT (findings/procedures), ICD-10 (diagnoses), RxNorm (drugs). Present in source corpus via `concept_reference_map` → `concept_reference_source` rows; present in CIEL similarly.
- **Mapping artifact grammar**: **FHIR R4 ConceptMap** — used purely as the equivalence-labeled grammar for source-concept ↔ target-concept relationships. FHIR is not a terminology standard; it provides resource types for representing terminology and mappings.
- **OpenMRS↔OpenELIS bridge**: **LOINC**. OpenMRS is CIEL-heavy; OpenELIS is LOINC-heavy; CIEL maps to LOINC in many places via `concept_reference_map`. The OpenELIS mapping skeleton resolves OpenMRS concept → its LOINC reference (via CIEL via OCL) → OpenELIS analyte that uses that LOINC.

## R1. Mapping artifact grammar

**Decision**: **FHIR ConceptMap (R4)** as the authoritative artifact format for source-→-target concept-to-concept mappings, including equivalence labels (`equivalent`, `equal`, `wider`, `narrower`, `inexact`, `unmatched`, `disjoint`).

**Rationale**:

- ConceptMap defines exactly the equivalence vocabulary FR-CD2 requires; reviewing the artifact is reviewing a published HL7 R4 resource, not a project-local schema.
- Validated by an unmodified open-source tool (HL7 FHIR Validator CLI; R3), satisfying FR-028 / SC-011 without harness-internal extensions to the standard.
- Python tooling exists (`fhir.resources` ≥ 7.0, MIT) for parse/serialize/validate against the R4 schema, so the harness reads/writes the artifact through a stable library.
- This decision does **not** claim FHIR as a terminology authority — see "Terminology stack" above. ConceptMap is the *grammar*; CIEL via OCL plus referenced terminologies (LOINC, SNOMED, ICD-10, RxNorm) are the *vocabularies* referenced by that grammar.

**Alternatives considered**: CTS2 (heavyweight, weak tool ecosystem, no clinical-equivalence alignment with OpenMRS), bespoke YAML (rejected by FR-025), SKOS (no clinical equivalence vocabulary).

## R2. Structural transform engine

**Decision**: **SQLMesh** as the standards-based, reproducibility-first transform engine, executed against MySQL 8 via SQLMesh's MySQL adapter.

**Rationale**:

- SC-004 (byte-identical re-runs under documented stable normalization) is a primary success criterion of this feature. SQLMesh is engineered around that property: content-fingerprint model versioning, time-filtered query wrappers that enforce per-batch reproducibility, virtual environments that let two runs sit side-by-side for diff inspection.
- 2026 published commentary on dbt (linked at bottom) identifies Jinja templating and dynamic macros as documented sources of non-determinism — a direct collision with our spec's reproducibility constraint.
- SQLMesh is open-source (Apache-2.0), Linux Foundation hosted, and **backwards-compatible with dbt projects**, so future-team familiarity is not foreclosed.
- Model files are reviewable SQL+YAML artifacts; `audits` (the SQLMesh analog of `dbt tests`) carry per-column rationale. The combination of model file, audit, and content-fingerprint version is exactly the "rationale-bearing reviewed artifact" the constitution wants.
- SQLMesh `seed_csv` models give us the deterministic ConceptMap → CSV bridge (R4) the same way dbt seeds would.
- License: Apache-2.0.

**Alternatives considered**:

- **dbt-core + dbt-mysql**: more mature ecosystem and bigger hiring pool. Loses on SC-004 because Jinja non-determinism is real and ongoing. Defensible alternative; not chosen because the spec puts reproducibility ahead of ecosystem familiarity.
- **Apache Hop**: visual / XML-files-on-disk; less natural for code-review of mapping logic. Apache-2.0.
- **Apache Camel**: wrong category — integration framework / EIP routes, not a batch-SQL transform engine. Adds JVM weight, gives us no native treatment of mapping as reviewable artifact.
- **Airbyte / Meltano / Singer**: ELT integration tools for moving data between systems; wrong shape for in-place dump transformation as the transform engine. Note: **dlt was initially rejected here on the same basis but is reintroduced in §R-load-pattern as the load layer on top of SQLMesh** — the validated SQLMesh+dlt handover pattern is purpose-built for this exact "transform with SQLMesh, load into a downstream OLTP target with dlt" architecture.
- **Plain SQL + Liquibase changesets**: closest to OpenMRS-native. Liquibase publishes a changeset format. Loses on lineage-aware testing, content-versioning, and reviewable audits out of the box. Stays in scope as a fallback if SQLMesh adoption proves friction-heavy mid-implementation.
- **FHIR StructureMap / FML** for the structural transform: strong fit for resource-shape transforms but our source/target are relational tables. The two extra format hops (SQL → FHIR → FML → FHIR → SQL) are operational cost without standards-fidelity benefit; rejected for structural transforms, retained for terminology as ConceptMap (R1).

## R3. Conformance / validation tooling

**Decision**:

- **HL7 FHIR Validator CLI** (`org.hl7.fhir.validator` JAR, Apache-2.0) for ConceptMap conformance (FR-028, SC-011).
- **`sqlmesh plan` + `sqlmesh run --dry-run` + `sqlmesh audit`** as the unmodified open-source release that proves the SQLMesh project conforms to SQLMesh's stated semantics (FR-028, SC-011).

**Rationale**: FR-028 / SC-011 require conformance to be defined by the standard's *own* tool, not by harness-internal checks. The FHIR Validator is the HL7-published reference implementation for FHIR R4; SQLMesh's CLI is the project's own published conformance/audit surface.

**Alternatives considered**: HAPI FHIR validator library (same lineage; CLI form simpler to invoke from CI). `fhir.resources` schema check alone (insufficient — does not exercise full FHIR conformance such as terminology binding).

## R4. Bridging ConceptMap → SQLMesh deterministically

**Decision**: One-way emit. `harness/conceptmap/seed_emit.py` reads the accepted ConceptMap (`datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json`) and produces `datasets/transforms/sqlmesh/seeds/concept_translation.csv` containing one row per ConceptMap `element.target`, columns `(source_concept_id, source_uuid, target_concept_id, target_uuid, equivalence, policy_bucket, source_record_examples)`. SQLMesh consumes the CSV via a `seed_kind: csv` model. The seed file is committed for review-diff visibility but is regenerable; ConceptMap checksum and seed-emit step hash are recorded in `run_manifest.json` so any drift is detectable.

**Rationale**: Keeps ConceptMap the single source of truth for terminology decisions (no hand-edits to the seed CSV); SQLMesh's seed mechanism is standard, deterministic, and content-fingerprinted; reviewers diff seed CSV alongside ConceptMap diff. Avoids inventing a bespoke executor.

**Alternatives considered**: SQLMesh `python_model` that reads the JSON ConceptMap directly at compile time (more complex; ties SQLMesh to a Python runtime per query; less reviewable diff surface). Embedding concept_id mappings inline in models (opaque; violates FR-CD2's single-source-of-truth requirement).

## R5. "Clinically meaningful difference" threshold for FR-008

**Decision**: A diff item is classified `clinical_meaningful: true` if **any** of the following hold; otherwise `cosmetic`.

- The diff touches a table that is referenced by ≥1 row in: `patient`, `person`, `person_name`, `person_address`, `person_attribute`, `encounter`, `encounter_provider`, `encounter_diagnosis`, `obs`, `conditions`, `diagnosis_attribute`, `allergy`, `allergy_reaction`, `drug_order`, `drug`, `drug_ingredient`, `concept`, `concept_name`, `concept_reference_map`, `concept_reference_source`, `concept_reference_term`, `location`, `provider`, `provider_attribute`, `orders`, `order_type`, `order_frequency`, `program`, `patient_program`, `patient_state`, `visit`, `visit_attribute`, `form`, `form_field`, `field`.
- The diff alters a column that participates in a foreign key, a unique constraint, a `concept_id` reference, or a coded-value column.
- The diff removes or retypes any column that the OpenMRS REST or FHIR module exposes (per the O3 RefApp module set on Core 2.8.x).

Items not matching are recorded as `cosmetic` (e.g., audit-only attribute_type tables that the demo doesn't populate, log-style tables with no clinical references).

**Rationale**: Precise, mechanically checkable from profile output, data-driven so it adapts to the corpus.

**Alternatives considered**: "Any schema diff is meaningful" (noisy; would block on attribute-type renames no clinical row references); "anything reviewer flags" (punts the question); hand-curated allow-list (brittle).

> **Status**: This is a working default. Confirm with user before implementation; small edits expected once Profile output is examined.

## R6. Seed-augmentation policy buckets

**Decision**: The `seed-augment` policy bucket (FR-CD3 option b) is permitted for source concepts whose semantic class is **lab analyte** (`concept_class = Test` or `LabSet`), **drug** (`concept_class = Drug`), or **finding/diagnosis** (`concept_class = Diagnosis`, `Finding`, or `Symptom`) — the three classes most likely to carry legitimate clinical specifics the 2.8 seeded dictionary doesn't ship (e.g., regional drugs, less common labs). Augmentation requires a published reference term in at least one of LOINC, SNOMED CT, ICD-10, or RxNorm; concepts without such a reference may not be augmented and must `remap` (with a non-`equivalent` label) or `drop`.

Other concept classes (concept-set, convertor, misc, etc.) may **not** be seed-augmented — they must remap or drop. This bounds the augmentation surface and keeps the seeded dictionary auditable against OCL.

**Rationale**: Lab/drug/diagnosis are the high-fidelity slices where AI/UI validation cares most about precise terminology. Bounding augmentation here keeps the seeded dictionary auditable against current CIEL via OCL and interoperable with downstream tooling.

**Alternatives considered**: Allow augmentation for any class (lower friction; expanded unreviewed surface); forbid augmentation entirely (cleaner; loses too many clinically-specific source records, hurting downstream eval fidelity).

> **Status**: Working default. Confirm with user once Profile output enumerates which source concept classes actually need augmentation.

## R-Terminology-Stack. OpenMRS concept-dictionary architecture, OCL/CIEL state, RefApp seeding (corrected, 2026-05-14)

Captured from reading the OpenMRS Concept Dictionary Basics wiki, the OCL docs, the `openmrs/openmrs-distro-referenceapplication` repo's actual distro configuration, and the `openmrs/openmrs-module-openconceptlab` README. Replaces earlier assumptions about "the seeded dictionary the RefApp ships with" — what the RefApp actually ships is the *mechanism to load CIEL*, not the dictionary itself.

### OpenMRS's concept-dictionary tables

A clinical OpenMRS installation's concept dictionary lives across these tables (all present in our 2.7 source dump's schema):

| Table | Role |
|---|---|
| `concept` | The concept rows themselves; one row per concept, with `concept_class_id` + `concept_datatype_id` + `is_set` + UUID. |
| `concept_name` | Localized names per concept (many rows per `concept_id`); each name has `locale`, `concept_name_type` (`FULLY_SPECIFIED`/`SHORT`/`INDEX_TERM`), and `locale_preferred`. |
| `concept_description` | Per-concept human descriptions, per locale. |
| `concept_class` | The 19 classes: `Test`, `Diagnosis`, `Drug`, `Question`, `Procedure`, `Finding`, `Symptom`, `LabSet`, etc. Drives semantic typing. |
| `concept_datatype` | Datatypes: `Numeric`, `Coded`, `Text`, `Date`, `Boolean`, `N/A`, `Document`, `Rule`, `Structured Numeric`, `Complex`. Drives which `value_*` column of `obs` is populated. |
| `concept_answer` | Concept-to-concept links: question-concept's allowable coded answers. (E.g., "Antiretroviral plan" question → list of answer concepts.) |
| `concept_set` | Concept-to-concept links: a "set" concept groups its member concepts (used for forms, lab panels). |
| `concept_reference_source` | External terminology authorities the deployment knows about: LOINC, SNOMED CT, ICD-10-WHO, RxNorm, CIEL, etc. |
| `concept_reference_term` | A specific code in one external source (e.g., LOINC `8302-2` = "Body height"). |
| `concept_reference_map` | The wire: links an OpenMRS `concept` to a `concept_reference_term` via a `concept_map_type` (`SAME-AS` / `NARROWER-THAN` / `BROADER-THAN` / etc.). This is what allows an OpenMRS concept to declare "I am LOINC 8302-2". |

### What ships with Platform/Core vs what a deployment loads

- **OpenMRS Platform/Core** ships an essentially **empty concept dictionary**. There are a handful of system-required concepts (Liquibase changesets populate things like the "Yes"/"No" boolean answer concepts and similar bookkeeping rows), but nothing clinical. A bare-bones Platform install can't represent a patient's vital signs because the concepts don't exist yet.
- **Distros (including the O3 RefApp)** are responsible for loading the clinical dictionary on top of Platform.

### The O3 Reference Application — what it actually ships

Verified directly from `openmrs/openmrs-distro-referenceapplication@main`:

- `distro/distro.properties` declares `omod.openconceptlab=${openconceptlab.version}` (currently `3.0.0`). The **`openmrs-module-openconceptlab` module is bundled as a default module** in every O3 RefApp install.
- `frontend/spa-assemble-config.json` bundles `@openmrs/esm-openconceptlab-app` — the O3 microfrontend UI for managing the OpenConceptLab module.
- **No concept seed CSVs / JSON dumps are committed in the RefApp distro.** The RefApp doesn't pre-populate the dictionary; it only ships the *loader*.

So when you `docker compose up` the O3 RefApp 3.6.0 against an empty MariaDB:
1. Liquibase creates the schema and populates only the system-required concepts.
2. The `openconceptlab` module starts; its admin UI is reachable; no concepts are pre-loaded.
3. To actually have a clinical dictionary, the deployer must either (a) configure an OCL subscription URL+token and run a sync, or (b) import an offline OCL export file.

Implication for this feature: when the harness brings up "the clean Core 2.8.x baseline" (M2-A), the concept dictionary it sees is **just the system-required stub**, not CIEL. Our spec's earlier framing — "the O3 RefApp's seeded CIEL dictionary" as the translation target — is precise only if we ALSO explicitly load CIEL into that baseline before treating it as authoritative.

### Two complementary loading mechanisms

- **`openmrs-module-openconceptlab`** — pulls concepts from OCL. Two modes:
  - **Subscription**: configure a subscription URL + OCL API token; the module syncs from OCL's API on a schedule. Not deterministic from a feature-002 perspective (subscription content can drift between runs).
  - **Offline**: import an OCL collection export file (zip). Deterministic if the file is pinned. This is the path that satisfies SC-004.
- **`openmrs-module-initializer`** — declarative configuration framework. Reads CSV / JSON / XML from `<openmrs-data>/configuration/`, applies metadata at startup. Includes a `concepts/` domain that loads concepts from CSVs. Independent of OCL — Initializer doesn't pull from OCL, it loads whatever files are in the configuration directory. Not currently bundled in the O3 RefApp distro by default but widely used in production distros (e.g., Bahmni).

The two modules can coexist: openconceptlab handles broad terminology imports (CIEL), Initializer handles distro-specific metadata that isn't in CIEL.

### CIEL and OCL — state as of 2026-05-14

- **CIEL** (Columbia International eHealth Laboratory dictionary) is the de-facto open clinical concept dictionary for OpenMRS deployments. ~50,000+ concepts; >20K with LOINC mappings; also SNOMED CT, ICD-10-WHO, RxNorm cross-references. Maintained by Andrew Kanter (Columbia U) and team. **Hosted on OCL** under `orgs/CIEL/sources/CIEL/`.
- **OCL (Open Concept Lab)** is a terminology service. Hosts CIEL plus many other dictionaries.
  - **REST API**: `https://api.openconceptlab.org`. **Anonymous read access is now gated** (verified 2026-05-14: returns `{"detail":"Authentication required. Anonymous API access is disabled.","upgrade_url":"https://app.openconceptlab.org/pricing"}` on `/orgs/CIEL/sources/CIEL/`). Requires an OCL user account; tokens are issued from the user profile page. The user (Piotr) confirms they have access.
  - **FHIR endpoint**: the standalone `openconceptlab/oclfhir` repo was **archived as deprecated 2026-04-07**; the FHIR endpoint is being integrated/replaced. Status of an anonymous FHIR read for CIEL is currently uncertain from public docs — needs verification with auth credentials.
  - **OpenMRS integration**: `openmrs-module-openconceptlab` (the bundled module in the RefApp) consumes OCL via subscription URL + token, or via an offline export file. **Public CIEL is downloadable as an OCL export** that the offline import path accepts.

### Implications for feature 002

This corrected understanding reshapes the spec's "remap to the seeded dictionary" framing in two ways:

1. **There is no "seeded dictionary" pre-loaded in a stock O3 RefApp install.** The target dictionary we map TO is whatever we explicitly load into the baseline before snapshotting it. Three deterministic paths:
   - **(a)** Configure `openmrs-module-openconceptlab` offline-import with a pinned CIEL export file (provenance-tracked under `datasets/sources/ocl/CIEL/<version>/`).
   - **(b)** Use `openmrs-module-initializer` with a curated subset of CIEL concepts loaded from CSV.
   - **(c)** Direct SQL load of a CIEL snapshot into the `concept`/`concept_name`/etc. tables before importing the demo.

   Path (a) is most idiomatic to OpenMRS and uses the already-bundled module. Path (b) is most controllable but requires the harness to author/maintain CSVs. Path (c) is operationally cheapest but bypasses the modules entirely.

2. **The R7 "OCL candidate-mining" path is correct in principle but needs authenticated OCL access for the mining queries**. Anonymous fetch is no longer an option. The user has OCL credentials; the harness must accept them (env var, runtime properties) and never log them.

### Open follow-ups (not blocking this section's commit)

- Decide which loading path (a/b/c above) the harness uses to populate the baseline CIEL. Path (a) is the working default unless overridden.
- Identify the canonical published CIEL export file (URL + checksum) — there are mirrored CIEL exports published by Bahmni and others; the most current canonical export needs confirmation.
- Verify whether OCL's FHIR endpoint (post-oclfhir-deprecation) supports anonymous reads for public CIEL or requires the same auth as the REST API.

## R7. Deterministic OCL / CIEL integration

**Decision** (corrected after R-Terminology-Stack): OCL data is pinned by collection version and used offline during the transform; the target "seeded" dictionary is explicitly *loaded into* the clean baseline via the bundled `openmrs-module-openconceptlab` offline-import path before it is treated as authoritative — the O3 RefApp does not ship CIEL pre-loaded.

- The harness fetches a **CIEL OCL export** (published collection version) **once per accepted-mapping cycle**, into `datasets/sources/ocl/CIEL/<version>/`. The export is checksum-recorded in `run_manifest.json` and read-only during the transform.
- Authenticated OCL access is required (user has credentials). The fetch happens out-of-band; the transform never makes live OCL calls.
- Refreshing the pin is a deliberate, out-of-band step that produces a new run-manifest version and triggers a PCCP-style change record (FR-023) because it is a material mapping-input change.
- The **target seeded dictionary** is produced by: boot the O3 RefApp's `db`+`backend` against empty MariaDB, install the bundled `openmrs-module-openconceptlab`, run an **offline import** of the pinned CIEL export, then snapshot the resulting `concept`/`concept_name`/`concept_reference_map`/`concept_reference_term`/`concept_reference_source` rows into `artifacts/<run>/profile/refapp_28_seeded_dictionary.snapshot.json`. This is the per-run deterministic target authority and the M2-A clean-target-baseline deliverable.
- The mapping job for each source 2.7 concept becomes a tiered lookup: (1) semantically equivalent concept in the loaded baseline CIEL → cheap remap; (2) not in baseline CIEL but in current CIEL via OCL (a later/wider CIEL version) → `seed-augment`; (3) not in current CIEL → remap with non-`equivalent` label or drop.

**Three concrete review tasks OCL assists with (offline, against the pinned snapshot)**:

1. **Auto-propose candidates**: for each source-2.7 concept, query the pinned CIEL snapshot for concepts sharing the same external reference term (LOINC code, SNOMED code, etc.); first-tier `equivalent`/`equal` candidates the reviewer can confirm.
2. **Validate targets**: reject any ConceptMap `target.code` whose concept_id/UUID is not present in *both* the pinned CIEL snapshot and the per-run RefApp seeded snapshot — catches typos and stale targets.
3. **Mine existing mappings**: where CIEL already declares a concept-to-concept mapping internally, surface that as a starting datapoint for the reviewer.

**LOINC as the OpenMRS↔OpenELIS bridge**: for the OpenELIS skeleton (M2-H), every OpenMRS lab-relevant concept used by the corpus is looked up against the pinned CIEL snapshot to extract its LOINC reference; that LOINC code becomes the OpenELIS-side analyte identity. Concepts without a LOINC reference are explicit feasibility gaps in the OpenELIS report (classified `partial` or `not-feasible`).

**Rationale**: Determinism is preserved because no live OCL API calls happen during `sqlmesh run`, `sqlmesh audit`, transform, smoke, or sampler stages — every OCL-derived datum is from the pinned snapshot whose checksum is in the manifest. OCL assistance is real: candidate proposals, target validation, and existing-mapping mining all run during the mapping-review loop (M2-C) against pinned data.

**Alternatives considered**:

- Live OCL API at transform time: rejected; would break SC-004.
- Tighter "subset of CIEL the O3 RefApp seeds" pinning: more compact but conflates "what we ship as default" with "what we have authority to consult." User's framing — "we need the default ciel, and then whatever we need to properly map the test data concepts" — favors pinning the full current CIEL collection so the reviewer has the full authority surface available during mapping.

## R8. Run-id, manifest schema alignment

**Decision**: Extend the run-manifest schema baseline in `specs/artifacts/planning/metadata-schema.md` with feature-specific fields: `source_dataset_checksum`, `conceptmap_version`, `conceptmap_checksum`, `sqlmesh_project_version`, `sqlmesh_project_checksum`, `concept_translation_seed_checksum`, `module_table_policy_seed_checksum`, `ocl_collection_versions` (array of `{collection, version, checksum}`), `refapp_28_seeded_dictionary_snapshot_checksum`, `openmrs_refapp_image_digest`, `mysql_image_digest`, `fhir_validator_version`, `sqlmesh_version`, `python_version`, `policy_buckets[]`, `reviewer_signoffs[]`, `openelis_target_version` (null in this feature; reserved for future use).

OpenTelemetry GenAI alignment is N/A for this feature — no model invocations at runtime; any advisory LLM proposals are an out-of-band operator action (not a milestone in this plan; FR-006 permits but does not require them, and the OCL candidate-mining described in §R7 covers the same function deterministically).

**Rationale**: The harness already plans a metadata schema; piggy-backing keeps fields consistent across milestones.

## R-Source-Provenance. Source corpus facts (from the OpenMRS Demo Data wiki)

Confirmed by reading the OpenMRS Demo Data wiki content directly (https://openmrs.atlassian.net/wiki/spaces/docs/pages/26273323/Demo+Data, content as of 2026-05-13):

- **What it is**: `large-demo-data-2-7-0.sql.zip` — ZIP archive containing the SQL dump for OpenMRS **Platform 2.7.0**. Uploaded 2025-01-10 by Daniel Kayiwa.
- **Scale**: 5,000 patients and ~500,000 observations (per wiki's "anonymized data set" header).
- **Install pattern (origin form, Platform target)**: `mysql> use <db>; mysql> source demo-1.10.0.sql` against an empty MySQL/MariaDB. This is the canonical schema-and-data load path. Confirms our M2-F approach: load the transformed dump into the MariaDB underlying the O3 RefApp 3.x backend the same way.
- **Default credentials**: `admin` / `Admin123`. Public, well-known, not a secret. FR-PHI3's stance (credential hygiene is the deployer's responsibility, not the transform's) is consistent with the wiki's own note ("You should change the password after installing the demo data").
- **License framing**: published as part of OpenMRS's demo-data resources on the openmrs.org wiki; treated as MPL 2.0 (OpenMRS's project license).

**Load-bearing caveat from the wiki, verbatim**:

> "demo data for OpenMRS Platform releases ... will not work for OpenMRS Reference Application releases"

For the RefApp, the wiki points to the `referencedemodata.createDemoPatientsOnNextStartup` global property — which generates fresh synthetic patients without the published corpus's clinical history.

**Implication for this feature**: feature 002 IS the bridge between the wiki's "Platform demo data" path and the modern (O3) RefApp. The transformation work (concept remap onto seeded CIEL, module-policy for unbundled module tables, terminology drift handling) is exactly what closes the wiki-documented incompatibility. Success is defined by: the transformed dump loads into the MariaDB underlying the O3 RefApp 3.x backend, Liquibase upgrade-in-place succeeds, and the rich clinical history (5,000 patients / ~500K observations) is preserved by the translation policy. The wiki's "createDemoPatientsOnNextStartup" path remains a valid alternative for users who do not need the published corpus's clinical depth.

## R-Liquibase. Liquibase upgrade-in-place cost (used by M2-A enumeration and M2-D pre-stage decisions)

**Observation**: OpenMRS Talk thread "Challenges with large data during platform upgrade" documents per-changeset Liquibase costs reaching multiple hours on `obs`-heavy datasets across Platform versions — one practitioner reported ~8h on a 1.11→2.1 jump for three `obs` alterations (specifically: `add status column`, `add interpretation column`, and a `value_complex` column resize). The change-type pattern that drives these costs is **schema modifications on the `obs` table requiring full-table copies** (MySQL/MariaDB's `ALGORITHM=COPY` path), especially `modifyDataType` against `value_complex` and `addColumn` with default backfill.

**Implication for our 2.7→2.8 hop**: SC-001's <60 min wall-time budget is at risk if any 2.7→2.8 Liquibase changeset triggers a full-table copy on `obs` for this corpus's row count. The mitigation is to **pre-stage** in SQLMesh: produce the post-changeset shape directly so Liquibase finds no work to do at import time.

**M2-A enumeration**: For every Liquibase changeset in the Core 2.7→2.8 path, classify the changeset type, the affected table, and the cost class given the corpus's row counts. Output: `artifacts/<run>/profile/liquibase-cost-estimate.json` (contract: `specs/002-openmrs-demo-data-2-8-remap/contracts/liquibase_cost.schema.yaml`). Cost classes: `instant` (DDL only) / `seconds` (small tables) / `minutes` / `hours` (`obs` full-table copy or similar).

**M2-D pre-stage decision rule**: any changeset estimated at `minutes` or `hours` is recommended for pre-staging unless a reviewer overrides with rationale. Pre-staging means the SQLMesh project's `clinical/` or `modules/` model directly produces the post-changeset table shape, and the changeset's `liquibasechangelog` row is inserted as already-executed.

**Sources**: OpenMRS Talk "Challenges with large data during platform upgrade" thread; mitigation pattern documented there uses Percona Toolkit's `pt-online-schema-change` but pre-staging in SQLMesh achieves the same outcome with less operational complexity.

## R-Import-Error-Tolerance. Acceptable error rate for the openconceptlab CIEL import (added 2026-05-14 from /speckit-analyze U3)

The openconceptlab module imports CIEL items (concepts, names, descriptions, mappings, reference terms, etc.) one at a time. A small percentage routinely fail — typical causes include foreign-key references to retired concepts, locale mismatches against the deployment's allowed-locales list, custom-validation-schema violations (CIEL uses `custom_validation_schema: "OpenMRS"`, so most errors are minor metadata issues), or concept-class definitions that already differ from what the deployment has.

**Final measurement (2026-05-14, T024c output `artifacts/dev-20260514-212318/profile/ciel-import-errors.json`)**: full import of CIEL `v2026-04-28` against the harness O3 RefApp baseline reported **133 errors out of 358,026 items (0.0371%)**.

- **23 distinct CIEL canonical IDs implicated** (root causes; 109 of 133 errors are cascading mapping failures whose `error_message` references the same 23 unimported concepts).
- **All 23 root failures are duplicate-name-in-locale validations** (e.g. `exantema súbito` es, `Quinine sulfate` en, `Phosphate de chloroquine` fr — CIEL FSN collisions the OpenMRS Hibernate validator rejects).
- **Top blockers**: `160034` (10×), `71917` (9×), `78200` (7×), `118492` (7×), `115427` (7×) — concentrated cascade.
- **Overlap with the 457 obs-referenced concepts in legacy_27_raw**: **0**. The 23 failed CIEL IDs are entirely in CIEL's long tail; non-blocking for this dataset.

(Earlier observation in this document noted ~73 errors / 207k items at 98% progress; the final measurement above replaces it.)

**Decision**: For M2-A, acceptable error rate is **≤ 0.1% of total CIEL items**. Above that threshold, M2-A's gate refuses to advance to M2-C until the errors are enumerated and either (a) accepted with rationale or (b) repaired by adjusting the openconceptlab subscription / validation settings / locale config.

Per Constitution Principle III (record-level evidence), every error MUST be captured at record level — concept identity (uuid + display name if available), error message, item type. Aggregate count alone is insufficient.

**Operator path** (T024c):
1. Hit `GET /openmrs/ws/rest/v1/openconceptlab/import/<uuid>/item?state=ERROR&limit=...` (paginated) to enumerate failed items.
2. Emit `artifacts/<run>/profile/ciel-import-errors.json` with per-record evidence.
3. Compute error rate; gate M2-A on the ≤ 0.1% threshold.
4. Below threshold: log as known acceptable, continue.
5. Above threshold: surface for reviewer + halt M2-A.

**Rationale**: 0.1% is empirically slack-enough to absorb the routine FK-to-retired-concept noise that CIEL imports always produce, while tight enough that a structural CIEL problem (e.g., schema-version drift, locale config mismatch) shows up as a gate failure.

**Alternatives considered**:
- Zero-tolerance (any error fails M2-A): too brittle; ~0.03% is normal.
- 1% tolerance: too loose; would mask real terminology-drift issues at scale.
- Per-class thresholds (e.g., 0% errors in Drug class, 0.5% in Misc): more nuanced but premature optimization; revisit if 0.1% global proves wrong.

## R9. Determinism caveats

**Decision**: Re-run determinism (SC-004) is asserted **byte-identically** for:

- `concept_translation.csv` (regenerated from the same ConceptMap)
- All transform model outputs *after* normalizing autogenerated audit timestamps to the `creator`/`date_created` values from the source rows (carry-forward, not regenerate)
- `events.jsonl` and `run_manifest.json` after normalizing the `run_id` (a content-addressed hash of inputs) and any wall-clock fields to a recorded canonical seed

Stable normalizations are documented in `contracts/run_manifest.schema.json` and `contracts/events.schema.json`.

**Rationale**: Byte-identical is achievable for transform outputs; manifests inherently carry wall-clock fields and so are matched under documented normalization, not byte-exact.

---

## Tooling-research summary (May 2026, referenced in R2)

- **Apache Camel**: integration framework; ETL examples exist but are file/message-flow oriented. Wrong category for batch SQL-to-SQL dump transformation. (Sources: Apache Camel ETL Example page; Camel Transformation category page.)
- **dbt-core**: mature, ecosystem-deep; 2026 commentary cites Jinja templating and dynamic macros as documented non-determinism sources. (Sources: SYNQ blog, Harness blog, ai2sql.io.)
- **SQLMesh**: Linux Foundation, Apache-2.0; designed around determinism (content-fingerprint versioning, time-filtered query wrappers, virtual environments). dbt-project-compatible. (Sources: SQLMesh GitHub, Medium / Andymadson, SYNQ comparison.)
- **Apache Hop**: modern Pentaho successor; GUI-centric; XML on-disk artifacts diff awkwardly. (Source: Apache Hop manual.)
- **Airbyte / Meltano / Singer**: ELT for moving data *between* systems. Wrong shape for in-place dump transformation. (Sources: Airbyte, Integrate.io, dataexpert.io 2026 comparisons.)
- **OpenELIS↔OpenMRS demo (OpenHIE)**: production pattern is FHIR APIs + LOINC, not any heavyweight ETL framework — confirms that "structural-transform tool choice" is a harness-internal concern, not an OpenMRS community convention to match. (Source: OpenHIE discourse thread.)

**All NEEDS CLARIFICATION items resolved. Proceed to Phase 1.**

---

## R-bridge-rule. Legacy concept-id ↔ seeded CIEL identity bridge (M2-A discovery, 2026-05-14)

**Decision**: The accepted ConceptMap's identity-rebind for legacy→seeded-CIEL terminology is **one rule, not a per-concept curated table**:

```
target_concept_id = (SELECT concept_id FROM openmrs.concept
                     WHERE uuid = RPAD(CAST(legacy.concept_id AS CHAR), 36, 'A'))
```

i.e., the seeded-CIEL concept whose UUID is the legacy `concept_id` left-padded by `A` to 36 chars. This rule is materialized into the SQLMesh seed `concept_translation.csv` as one row per distinct legacy `concept_id` present in `legacy_27_raw.concept` (~2,528 rows); the SQLMesh `audit_concept_translation_coverage` audit gates the M2-A acceptance bar at 100% coverage of obs-referenced concepts.

**How the discovery was made**:
1. T021 (`harness/profile/inventory.py`) produced `artifacts/legacy-27-raw-baseline/profile/inventory.json` — 5,284 patients / 476,973 obs / 52 populated tables / 0 reference_map rows / **0 rows in the four typed clinical tables**.
2. Manual probing during the M2-A canvas authoring showed that the legacy concept dictionary uses AMPATH-style numbering: `concept_id=5088` = "TEMPERATURE (C)", `concept_id=5089` = "WEIGHT (KG)", etc. — the same canonical IDs CIEL uses.
3. CIEL concepts in `openmrs.concept` carry UUIDs in the pattern `<canonical_id>AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA` (32 As after the integer). Reproduction in `data-model.md` §R-bridge-rule shows the JOIN and the 100% coverage result.
4. FSN strings match across the two dictionaries modulo case: legacy is uppercase AMPATH-style ("TEMPERATURE (C)"); CIEL is title-case ("Temperature (c)"). Same semantic concept.

**Rationale**:
- Removes the largest authoring burden the original spec/plan implied ("hundreds-to-thousands of curated mappings reviewed one at a time"). The actual remaining authoring surface for terminology is **zero per-concept rows** — every concept is identity-rebound. Per-row authoring is reserved for structural promotions (§R-typed-table-promotion).
- Preserves SC-004 (byte-identical re-runs): the bridge is a pure SQL function of `legacy.concept_id`, deterministic by construction.
- Preserves FR-007 reviewer rationale requirement: the ConceptMap carries one identity-bridge element with reviewer rationale citing this section; the per-row seed CSV is regenerable from that one element.
- Does not weaken FR-008: the SQLMesh `audit_concept_translation_coverage` audit emits any unmapped concept as a failing row and halts the pipeline. The 100% measurement above is on the current corpus's obs-referenced set; an unmatched concept on any future input would surface immediately.

**Alternatives considered**:
- Per-concept curated rows (the original framing): defensible but unnecessary given the measured 100% identity coverage; would inflate the ConceptMap artifact and add review friction without changing the deterministic output.
- Reference-term-based bridging (LOINC / SNOMED CT codes): not viable for legacy_27_raw — `concept_reference_map` is empty (0 rows) per T021. Reserved for §R-typed-table-promotion edge cases and for the OpenELIS skeleton (M2-H).
- Name-based fuzzy matching: rejected — non-deterministic; would violate SC-004.

> **Status**: confirmed against measured corpus + CIEL `v2026-04-28`. Sole risk: a future input concept whose UUID doesn't match the canonical CIEL pattern. The `audit_concept_translation_coverage` audit catches this at transform time.

## R-typed-table-promotion. obs → typed clinical tables (M2-A canvas, 2026-05-14)

**Decision**: The four target typed clinical tables (`allergy`, `conditions`, `orders`/`test_order`, `drug_order`) are empty in the source dump (measured: 0 rows each); the transform synthesizes typed rows from `obs` via four selector rules. The rules are encoded as one ConceptMap element each (FR-029–FR-032) and as one SQLMesh model each (`datasets/transforms/sqlmesh/models/clinical/{drug_order,conditions,allergy,test_order}.sql`).

The five cross-cutting decisions below are the project's defaults; documented here so reviewers don't re-derive them at each model.

| | Question | Decision (default) | Rationale |
|---|---|---|---|
| **Q1** | When obs → typed row, do we DELETE the obs or KEEP it with `obs.order_id` linkback? | **KEEP both.** `obs.order_id` already exists in the 2.7 schema (carries over to 2.8). | chartsearchai indexes obs; refapp UI reads typed tables. Both win. Preserves provenance. |
| **Q2** | UUID strategy on promoted rows? | **UUID v5 with namespace `harness-002-promotion`** derived from `(obs.uuid, target_table)`. | Reproducibility across re-runs (SC-004); fresh v4 would break determinism. |
| **Q3** | Vaccines (~3,045 of the 43,412 Drug-class answers) as `drug_order` or Immunization shape? | **Emit all as `drug_order`** with an attribute hint distinguishing vaccines. | OpenMRS 2.8 has no immunization table by default. FHIR read-side projects vaccines to FHIR Immunization at read time; record-side stays on `drug_order`. |
| **Q4** | Orderer field source on promoted orders? | **`encounter_provider` for the matching encounter**; fallback `obs.creator`. | Source `obs` has no provider FK. `encounter_provider` is the best-available proxy in this corpus (one provider per encounter). |
| **Q5** | `coverage_sample` sampling strategy per rule (FR-015)? | **5 records per (concept_class × datatype × value_class) cohort** × 5 buckets (rebound obs + 4 typed targets); deterministic `sampler_seed` recorded in `run_manifest.json`. | Per-class spread keeps the sample diverse; deterministic seed satisfies SC-004 across runs. |

**Per-rule field mapping** (target column ← source expression) is recorded canonically in the ConceptMap element's harness extensions (see `contracts/conceptmap.profile.md`). Each rule's SQLMesh model under `models/clinical/` instantiates it.

**Rationale**: The 4 rules are the only structural per-row authoring the M2-A reviewer signs off on; all other terminology decisions ride on §R-bridge-rule. This bounds the human-review surface to a tractable handful of rules with measured row counts, and concentrates the policy debate into the five Q1–Q5 cells.

**Alternatives considered**:
- Promote any obs whose `value_coded.class` matches a target-bucket class (without the question-concept filters in P2/P3/P4): too noisy; would emit "diagnosis observed on review" obs as new conditions, "yes I do have allergies" boolean answers as allergy rows, etc.
- Per-form mapping (route forms to specific target tables): more granular but the demo corpus's form metadata is sparse; class-based routing is more robust.

> **Status**: open questions tracked per-rule in `specs/artifacts/canvases/concept-mapping-discovery.canvas.tsx` (the B5 deep-dive panels). Defaults above are the M2-A acceptance baseline. **Demo-data validation posture**: deviations are reviewed iteratively with the project owner (consensus-guided), not gated through a heavyweight PCCP record. PCCP remains available for changes that materially affect downstream consumers; for per-rule tuning during M2-A iteration, recording the decision in the ConceptMap element's `comment` field is sufficient.

## R-load-pattern. OLTP load layer (SQLMesh + dlt handover, M2-F entry)

**Decision**: SQLMesh terminates at the **transform spec** (legacy_27_raw → refapp_28_demo). The **load** into the live OLTP target (`openmrs` / `openmrs_test`) is handled by [**dlt**](https://dlthub.com/) with the SQLAlchemy destination. Two complementary tools, each operating at its design intent.

**Rationale** — why this split rather than one tool end-to-end:

- SQLMesh's storage layer is **virtual-by-design**: the user-facing `refapp_28_demo` schema is views over versioned snapshot tables in `sqlmesh__refapp_28_demo`. That virtualization is the whole point of SQLMesh's atomic env-swap + time-travel + content-fingerprint guarantees for analytical workflows. It is **not designed to produce a portable, loadable SQL artifact for a separate OLTP application** — confirmed empirically (a `mariadb-dump refapp_28_demo` produces 165KB of CREATE VIEW statements, no data) and via the [SQLMesh Multi-Engine guide](https://sqlmesh.readthedocs.io/en/stable/guides/multi_engine/) which states models materialize in their assigned gateway only.
- dlt is purpose-built for the missing piece: SQL-source → SQL-destination ETL with primary-key idempotency, schema evolution, and pipeline state tracking. [Tobiko (the SQLMesh company) explicitly endorses the dlt handover pattern](https://dlthub.com/blog/sqlmesh-dlt-handover).
- The transform itself is non-trivial (1:N obs→typed-table promotions, FK reconciliation across user/location/encounter_type, ~2,528 concept rebinds with policy-bucket metadata) and benefits from SQLMesh's lineage + audit machinery. Throwing SQLMesh out to use plain SQL or a single ETL tool would re-encode in less-audited form what SQLMesh already gets right.

**What each tool owns**:

| Tool | Owns | Outputs |
|---|---|---|
| **SQLMesh** | Transform spec: bridge rule (concept rebind), 4 obs→typed-table promotions, FK reconciliation seed maps (`models/terminology/*.sql`), audit gates (row-count, concept-translation-coverage, FK-closure, policy-bucket-coverage), content-fingerprint determinism. | Physical snapshot tables in `sqlmesh__refapp_28_demo.*`; user-facing views in `refapp_28_demo.*`. |
| **dlt** | OLTP load: read from SQLMesh's physical snapshots → write to `openmrs_test.*` (iteration target) or `openmrs.*` (promotion target). PK-based idempotency via `write_disposition='merge'`; schema evolution; per-pipeline state. | Rows in the live RefApp's DB. Pipeline state under `.dlt/openmrs_loadback/state.json`. |

**Hermetic iteration**: dlt writes to `openmrs_test` (a separate schema in the same MariaDB), not the live `openmrs`. The iteration loop (edit SQLMesh model → re-run plan + audit → re-run dlt → restart backend pointed at openmrs_test → smoke) keeps the main CIEL-loaded baseline untouched. Promotion to `openmrs` is a single env-var change.

**Run-manifest extensions**: `RunManifest002Extensions` gains two fields per `contracts/run_manifest_002_extensions.schema.yaml`:

- `dlt_pipeline_run_id` — dlt's run UUID for the load step
- `dlt_state_hash` — SHA-256 of dlt's pipeline state JSON; a determinism witness (same SQLMesh inputs + same dlt config → same state hash)

Each loaded table's row count continues to stamp into `materialized_outputs[]` (already implemented in B2 of the prior remediation; extends naturally from "post-transform" to "post-load").

**Conformance signals**:
- SQLMesh side: `sqlmesh audit` exits 0 (existing).
- dlt side: `dlt pipeline info openmrs_loadback --schema` runs cleanly; per-table row counts post-load match the SQLMesh-side audit floors (`audit_<mart>_row_count_min.sql`).
- Integrated: a fresh-replay run (`scripts/reset-transform.sh && sqlmesh plan && harness-cli load-test`) produces byte-identical content checksums in `materialized_outputs[]` and the same `dlt_state_hash` for the same inputs.

**Companion artifacts**:
- `contracts/dlt_pipeline.profile.md` — the load-layer contract (write_dispositions per table, PK conventions, required dlt config).
- `datasets/load/openmrs-loadback.review.md` — reviewer rationale per resource + FK-reconciliation decisions; analogous to `datasets/mappings/openmrs-2.7-to-2.8.review.md` for the transform spec.

**Alternatives considered** (and rejected):

- **Plain SQL + mysqldump**: would force re-encoding the 1:N promotion fan-out and FK reconciliation in ad-hoc SQL, losing SQLMesh's audit gates and lineage tracking. Defensible only if SQLMesh's transform were trivial; ours isn't.
- **Liquibase custom changesets** (`loadData` / `loadUpdateData` from CSV): idiomatic to OpenMRS, but requires a separate module to host the changesets and adds XML ceremony. Held in reserve for the eventual production-grade artifact handoff if we ever ship the demo dataset upstream.
- **dlt for the entire transform**: dlt has SQL transformations via ibis, but the audit + content-fingerprint + reviewable-model-file machinery in SQLMesh is the load-bearing part of the spec's reproducibility commitment (SC-004). Replacing SQLMesh wholesale would be a larger architectural shift than the load-layer addition justifies.

**License**: dlt is Apache-2.0 (compatible with SQLMesh's Apache-2.0 and our existing OSS licensing).

