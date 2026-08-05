# Specification Quality Checklist: Catalyst Query Workbench

**Purpose**: Validate specification completeness and quality before planning

**Created**: 2026-07-17; D1 groundedness revalidation reopened 2026-08-05

**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Implementation constraints appear only where they are normative for
  interoperability, reproducibility, or acceptance
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] Incidental implementation choices do not override observable product
  requirements or acceptance criteria

## Notes

- Four clarification decisions are integrated: validator findings never gate
  manual Run; SQL and typed parameters are directly editable; sessions persist
  across refresh; and sessions export as versioned validation-harness artifacts.
- G2.8 adds a linear follow-up turn, exact editor-snapshot lineage, bounded
  revision context, failure recovery, per-turn profiles, and explicit
  non-branching/non-chat scope with measurable acceptance scenarios.
- The 2026-08-05 alignment records the accepted workbench as the shared
  foundation, adds Dashboard MVP User Story 7 plus FR-071–FR-080 and
  SC-035–SC-041, and explicitly keeps G2.10, W2, W3/CVR, R4, and R5 as parallel
  independently gated pathways.
- FR-080/SC-041 make the supplied Ask shell and chronological builder design the
  target UX while requiring it to integrate every accepted query-notebook
  capability through Save Dataset; the specification introduces no replacement
  prompt-only flow, second SQL editor, example prompts, or automatic execution.
- The second D1 groundedness audit found stale branch ancestry, missing
  API/pointer/receipt contracts, ambiguous bounded-result and layout/source
  semantics, oversized tasks, and insufficient constitution evidence. D1a was
  reopened; Dashboard MVP now uses path-specific red→green tasks T137–T182 and
  retains T144/T149/T154/T157 only as checkpoint gates.

## D1a grounded-contract readiness

- [x] Catalyst and harness dashboard branches are based on current `main`
- [x] Exact builder API, current-pointer, and receipt contracts validate
- [x] Bundle identity and portable per-asset provenance are unambiguous
- [x] Reconciled populated-Ask reference state preserves the accepted workbench
- [x] Canonical execution compatibility, bounded stable-warning mapping, and
  current-only Dataset promotion are specified without dropping accepted table
  wire types
- [x] Dashboard membership locks `dataSourceId` plus `catalogVersion`; catalog
  refresh requires an explicit new Dashboard
- [x] Stable Superset UUID/slug/URL evidence and Save Dataset v1 before follow-up
  are explicit in requirements and live acceptance
- [x] Prior-Dashboard preservation is scoped to pointer/bundle/manifest/
  credential and other preflight failures plus transactionally rolled-back CLI
  failures; post-import verification failure disables Open/current-
  success and requires a validated per-Dashboard last-verified projection, full
  Superset-local metadata/home reset, and verified reimport without asset-
  selective/direct-ORM/REST mutation or an automatic rollback/retry claim
- [x] Runtime setup proves only driver/network and DB-enforced read-only access;
  the canonical native fixture owns the persisted analytics Database asset
- [x] Importer/state implementation is standalone Python-3.10-compatible code
  under `targets/catalyst/scripts/` with no Catalyst package import; tests remain
  in Catalyst Gateway CI, prove constrained canonical JSON against `rfc8785`,
  and include a pinned-Superset-container smoke. The dedicated
  `mvp-superset.sh` operator wrapper, not `mvp-up.sh`, owns dispatch
- [x] Catalyst owns `runtime/superset/`; `/runtime/superset/` is target-gitignored
  and publication must preserve the clean-target guard
- [x] Missing/corrupt last-verified projection stops before reset; recovering A
  leaves failed desired B current/import_failed and suppresses automatic
  bootstrap/retry until explicit retry or a new publication
- [x] D1 tasks are path-specific and test-first, with event/acceptance schema and
  emitter validation before the live run
- [x] Preimplementation PCCP and N64–N74 register cover validation, product
  rollback, scoped import failure, and explicit recovery
- [x] Post-edit SpecKit analysis has zero unresolved CRITICAL/HIGH findings
- [x] User explicitly accepts the D1a written plan after the final analysis and
  before T139 or any product-code change
