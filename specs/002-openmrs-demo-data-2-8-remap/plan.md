# Plan: OpenMRS Demo Corpus Remap and OpenELIS Feasibility

**Spec**: [spec.md](spec.md)

## Scope and ownership

Retain reviewed corpus, terminology/structural mappings, fixtures, deterministic
reproduction, clinical-meaning checks and record-level evidence. Reusable migration
and terminology utilities still need an external maintained owner; this is an
[umbrella decision](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#7-outstanding-decisions),
not authorization to delete data functionality or move it wholesale.

The caller prepares a Core 2.8.x/O3 RefApp-compatible baseline, loads the source
corpus and supplies database/REST/FHIR settings and safe provenance. The umbrella
owns shared environment setup, product source selection/build/test orchestration,
restoration, deployment and release coordination. Spec 001 supplies readiness and
metadata semantics, not a registry, Git/submodule gate or service lifecycle API.
[ChartSearchAI](https://github.com/pmanko/openmrs-module-chartsearchai) owns its
product preparation and chat contracts. OpenELIS schema analysis accepts an explicit
schema artifact; no fixed sibling checkout is required by validation.

## Technical approach

- **Terminology**: CIEL via OCL is OpenMRS terminology authority; LOINC bridges
  lab concepts to OpenELIS. Reviewed FHIR R4 ConceptMap records equivalence,
  action policy and rationale. FHIR is the artifact grammar, not terminology authority.
- **Deterministic snapshots**: accepted CIEL/LOINC exports are versioned and
  checksum-recorded inputs; no live OCL calls during transform or sampler.
  A deliberate refresh carries clinical-impact review context.
- **Transform**: SQLMesh executes reviewed relational models, promotions,
  seed maps and audits. Use the compatible dependency range in `pyproject.toml`,
  not an independent package version requirement copied into this plan.
- **Load**: the direct loader reads physical SQLMesh snapshots, projects to
  OpenMRS-defined columns and copies into a caller-prepared disposable build schema.
  See [load profile](contracts/load.profile.md). It does not manage live services.
- **Artifact handoff**: a deterministic, module-clean portable dump is the data
  deliverable. The deploying owner restores it into a fresh target; OpenMRS owns
  Liquibase and module initialization. Do not mutate a running deployment in place.
- **Evidence**: sampler and binding checks read actual configured REST/FHIR
  interfaces and preserve records, translated concepts, values, units, dates,
  linkages, policy/equivalence labels and reviewer rationale.
- **OpenELIS**: feasibility classifications plus terminology and structural
  mapping skeleton only. No live OpenELIS load or Catalyst code execution occurs.

Python 3.11+, PyMySQL, SQLMesh, FHIR tooling and pytest support the current data
path. Java is needed only for the selected HL7 Validator operation; product build
requirements belong to product/umbrella tooling, not harness runtime prerequisites.
Clinical data stays in selected databases/dumps or bounded evidence; metadata
lives under the run output boundary. Secrets never enter configuration captures.

## Milestones and acceptance

| ID | Validation deliverable | Retained requirement coverage | Review |
| --- | --- | --- | --- |
| M2-A | Inventory, schema diff and Liquibase cost evidence | US2, FR-001–005 | Sources/locales/modules complete; clinical differences and cost assumptions explicit |
| M2-C | Accepted ConceptMap and companion rationale | US3, FR-CD1–4, FR-007, FR-025, FR-027–028, SC-011–012, SC-014 | Clinically informed review; HL7 conformance; referenced concepts fully labeled |
| M2-D | Reviewed SQLMesh models, seeds and audits | US1, FR-008–009, FR-012, FR-025–026 | Every meaningful diff has a decision; structural conformance and audits pass |
| M2-E | Reproducible transformed corpus | FR-009–011, FR-013, SC-001, SC-004 | Stable normalized content across clean replays; FK/completeness checks |
| M2-F | Import-smoke and RefApp binding evidence on prepared target | US1, FR-014, FR-CD5, SC-002, SC-013 | Real record-level REST/FHIR/UI readback; caller supplies startup/product-test evidence separately |
| M2-F.1 | Live ChartSearchAI answer over translated records | FR-014, FR-022, SC-015 | Configured real chat path; final citations resolve; persisted hydration where protocol requires |
| M2-G | Seeded translation-coverage sample | FR-015, FR-024, SC-002, SC-010 | Every declared nonempty policy bucket represented; specific failing records |
| M2-H | OpenELIS feasibility and mapping skeleton | US4, FR-017–020, SC-007–008 | Entity/source-column rationale; analysis only, no parity claim |
| M2-Z | Manifest, events and material-change review | FR-021–023, FR-PHI2, SC-006, SC-009 | Shared manifest meanings plus 002 extensions; actual exercised targets only |

Critical path: M2-A → M2-C → M2-D → M2-E → M2-F → M2-F.1 → M2-G.
M2-H can use reviewed inventory/mappings in parallel; provenance accrues throughout.
[Tasks](tasks.md) retains data implementation/evidence IDs. Dated measurements are
evidence, not a current deployed-state or completion register.

## Artifact contracts

- [Data model](data-model.md): inputs, clinical records, mappings and output identity.
- [ConceptMap](contracts/conceptmap.profile.md) and
  [SQLMesh](contracts/sqlmesh_project.profile.md): accepted transform semantics.
- [Load](contracts/load.profile.md): direct copy and portable data handoff.
- [002 manifest extensions](contracts/run_manifest_002_extensions.schema.yaml):
  mapping/snapshot/digest/reviewer and materialized-content evidence.
- [Quickstart](quickstart.md): current operator entry points and acceptance limits.

## Constitution review and verification

Use caller-prepared real interfaces for clinical claims, doubles only for mechanics.
No workspace registry, source revision lookup, pin gate or target lifecycle is part
of collection. Revisions/images are supplied or observed and nullable when absent.
Reviewed mappings are deterministic; proposals are advisory. Record-level evidence
and rationale are required; counts alone cannot establish clinical preservation.

Run focused corpus/mapping/transform/sampler tests and standards conformance, then
harness tests. Compare clean replays against SC-004, test ambiguous/missing concepts,
FK/locale/import failures, and verify final citations against translated records.
Capture the mapping/scenario/fixture inputs needed for portable offline reports.
Material changes include impact/residual-risk context. Deployment and product-test
acceptance remain external; this alignment does not certify an end-to-end run.
