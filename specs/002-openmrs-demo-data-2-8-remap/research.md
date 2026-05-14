# Phase 0 — Research

**Feature**: 002-openmrs-demo-data-2-8-remap
**Date**: 2026-05-13

This phase resolves the plan-shaped open items from `/speckit-clarify` and records the technical decisions for `/speckit-plan`. Decisions reflect clarification-session updates from the user (FHIR is not a terminology authority; CIEL via OCL is; LOINC is the OpenMRS↔OpenELIS bridge) and the comparative ETL/transformation-tooling research summarized at the bottom of this file.

## Terminology stack (corrected baseline for all decisions below)

- **Terminology authority on the OpenMRS side**: **OCL (Open Concept Lab)** managing **CIEL**. The 2.7 source dictionary is a CIEL snapshot of some vintage; the 2.8 RefApp's seeded dictionary is also a CIEL subset (different vintage / curated subset).
- **Cross-terminology references**: LOINC (labs), SNOMED CT (findings/procedures), ICD-10 (diagnoses), RxNorm (drugs). Present in source corpus via `concept_reference_map` → `concept_reference_source` rows; present in CIEL similarly.
- **Mapping artifact grammar**: **FHIR ConceptMap R4** — used purely as the equivalence-labeled grammar for source-concept ↔ target-concept relationships. FHIR is not a terminology standard; it provides resource types for representing terminology and mappings.
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
- **Airbyte / Meltano / Singer / dlt**: ELT integration tools for moving data between systems; wrong shape for in-place dump transformation.
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
- The diff removes or retypes any column that the OpenMRS REST or FHIR module exposes (per the 2.8.0 RefApp module set).

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

## R7. Deterministic OCL / CIEL integration

**Decision**: OCL data is pinned by collection version and used offline during the transform.

- The harness fetches the **current CIEL collection** (and any required reference-source snapshots — at minimum LOINC) from OCL **once per accepted-mapping cycle**, into `datasets/sources/ocl/<collection>/<version>/`. The snapshot is committed (or LFS-tracked if oversized), checksum-recorded in `run_manifest.json`, and read-only during the transform.
- Refreshing the pin is a deliberate, out-of-band step that produces a new run-manifest version and triggers a PCCP-style change record (FR-023) because it is a material mapping-input change.
- The **default target** is the seeded dictionary that the 2.8 RefApp distro ships (pinned by RefApp distro image digest). After the RefApp container has applied Liquibase, the harness snapshots the seeded `concept` / `concept_name` / `concept_reference_map` / `concept_reference_term` / `concept_reference_source` rows into `artifacts/<run>/profile/refapp_28_seeded_dictionary.snapshot.json`. That is the per-run deterministic target authority.
- The **authoritative target for mapping decisions** is **most-current CIEL via the pinned OCL snapshot**. The mapping job for each source 2.7 concept becomes a tiered lookup: (1) semantically equivalent concept in the seeded baseline → cheap remap; (2) not in seeded baseline but in current CIEL → `seed-augment`; (3) not in current CIEL → remap with non-`equivalent` label or drop.

**Three concrete review tasks OCL assists with (offline, against the pinned snapshot)**:

1. **Auto-propose candidates**: for each source-2.7 concept, query the pinned CIEL snapshot for concepts sharing the same external reference term (LOINC code, SNOMED code, etc.); first-tier `equivalent`/`equal` candidates the reviewer can confirm.
2. **Validate targets**: reject any ConceptMap `target.code` whose concept_id/UUID is not present in *both* the pinned CIEL snapshot and the per-run RefApp seeded snapshot — catches typos and stale targets.
3. **Mine existing mappings**: where CIEL already declares a concept-to-concept mapping internally, surface that as a starting datapoint for the reviewer.

**LOINC as the OpenMRS↔OpenELIS bridge**: for the OpenELIS skeleton (M2-H), every OpenMRS lab-relevant concept used by the corpus is looked up against the pinned CIEL snapshot to extract its LOINC reference; that LOINC code becomes the OpenELIS-side analyte identity. Concepts without a LOINC reference are explicit feasibility gaps in the OpenELIS report (classified `partial` or `not-feasible`).

**Rationale**: Determinism is preserved because no live OCL API calls happen during `sqlmesh run`, `sqlmesh audit`, transform, smoke, or sampler stages — every OCL-derived datum is from the pinned snapshot whose checksum is in the manifest. OCL assistance is real: candidate proposals, target validation, and existing-mapping mining all run during the mapping-review loop (M2-C) against pinned data.

**Alternatives considered**:

- Live OCL API at transform time: rejected; would break SC-004.
- Tighter "subset of CIEL the 2.8 RefApp seeds" pinning: more compact but conflates "what we ship as default" with "what we have authority to consult." User's framing — "we need the default ciel, and then whatever we need to properly map the test data concepts" — favors pinning the full current CIEL collection so the reviewer has the full authority surface available during mapping.

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
