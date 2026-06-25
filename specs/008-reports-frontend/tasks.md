# Tasks: Validation Run Reporting Platform

**Input**: Design documents from `specs/008-reports-frontend/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: REQUIRED. Behavioral changes ship with red-first tests (Constitution V); the plan's priority
targets (ingest trace-correlation, judged-sibling lineage, unscored rendering, multi-reviewer
adjudication, calibration) are written to FAIL before implementation.

**Organization**: tasks are grouped by user story (P1–P5) so each can be implemented, tested, and
demoed independently. Paths follow the `reports-app/{api,web,shared}` structure from plan.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 (user-story phases only)

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the `reports-app/` monorepo structure (`api/`, `web/`, `shared/`) per plan.md
- [X] T002 [P] Initialize `reports-app/api` as a NestJS project (Node 20, TypeScript) with NestJS + Prisma deps in reports-app/api/package.json
- [X] T003 [P] Initialize `reports-app/web` as a Vite + React 18 project with `recharts` in reports-app/web/package.json
- [X] T004 [P] Initialize the shared DTO/types package in reports-app/shared/package.json
- [X] T005 [P] Configure eslint + prettier across reports-app/ in reports-app/.eslintrc + reports-app/.prettierrc
- [X] T006 [P] Configure the Nest test runner + Vitest + a throwaway SQLite test DB, and gitignore the SQLite file + build output in reports-app/.gitignore

**Checkpoint**: scaffolding builds and the empty test suites run.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: no user story can begin until this phase completes — every story reads from the ingested store.

- [X] T007 Define the Prisma schema for all entities (Run, ComparisonSet, Scenario, ScenarioTurn, Arm, ArmRole, Model, Patient, Result, ResultReference, IndepthResult, Trace, JudgeRow, JudgeBackground, ArmAggregate, Reviewer, Adjudication, PublishedReport, CatalogMeta) per data-model.md in reports-app/api/src/prisma/schema.prisma
- [X] T008 Generate the initial migration + Prisma client in reports-app/api/src/prisma/
- [X] T009 [P] Define the shared DTOs (the contracts/rest-api.md response shapes) in reports-app/shared/src/dto.ts
- [X] T010 [P] Red-first ingest tests — trace correlation by `modelName` not `backendId`, judged-sibling lineage (`parentRunId` + reused results), idempotent re-ingest, unscored cell (Result with no JudgeRow), required producer `summary.json` ingestion, and a guard that the platform does not synthesize ArmAggregate scores from JudgeRows — in reports-app/api/test/ingest.spec.ts
- [X] T038 **HARNESS REPO (separate branch / foundational dependency)**: add the per-arm aggregate export (`summary.json`) to `judge-finalize` (research Decision 5) before durable T011 validation; until it lands, tests may use only a documented compatibility fixture containing already-computed producer aggregate fields — no TypeScript benchmark/per-arm scoring shim
- [X] T011 Implement the ingest core (read `artifacts/validate/<run>/{results,judge,events}.jsonl` + manifests + `hub-trace/trace.jsonl` + required producer `summary.json` → idempotent upsert of Run/Result/ResultReference/IndepthResult/JudgeRow/JudgeBackground/ArmAggregate/Trace, with the trace-correlation + judged-sibling rules and no scoring derivation in TypeScript) in reports-app/api/src/ingest/ingest.service.ts — makes T010 green
- [X] T012 Implement the `reports-ingest <run_dir>` CLI in reports-app/api/src/ingest/ingest.command.ts
- [X] T013 [P] Scaffold the base NestJS app (module wiring, PrismaService, error handling, the 404/409/422 + `scored:false` conventions) in reports-app/api/src/app.module.ts
- [X] T014 [P] Scaffold the base SPA shell (routing for catalog/report/live/review + the typed API client consuming the shared DTOs) in reports-app/web/src/main.tsx

**Checkpoint**: a real run ingests into a clean DB; ingest tests green; the app shell renders.

---

## Phase 3: User Story 1 - Read a run's report from stored data (Priority: P1) 🎯 MVP

**Goal**: browse the catalog and read a per-run report rendered from the store through one shared presentation.

**Independent Test**: ingest one judged run → it appears in the catalog with correct headline scores → drill into the report → per-arm scores, answers, citations, and the team-arm reasoning trace all render; no per-run HTML artifact involved.

### Tests for User Story 1

- [X] T015 [P] [US1] Contract test for GET /api/catalog + GET /api/runs/:id/report (headline = ingested ArmAggregate; unscored cells flagged, not dropped) in reports-app/api/test/catalog-report.spec.ts
- [X] T016 [P] [US1] Rendering test — trace displays for a team-arm cell (modelName correlation), an unscored cell shows "not scored", and report rendering uses the shared ArmCard/ConfidenceSection/TraceSteps/ScoreTable/AnswerTile/RefList components rather than route-local duplicates — in reports-app/web/test/report.spec.tsx

### Implementation for User Story 1

- [X] T017 [P] [US1] Runs read module (GET /api/runs/:id, /report, /cells/:scn/:arm) in reports-app/api/src/runs/runs.controller.ts
- [X] T018 [P] [US1] Catalog read endpoints (GET /api/catalog, /api/catalog/meta) in reports-app/api/src/catalog/catalog.read.ts
- [X] T019 [P] [US1] The shared component set (ArmCard, ConfidenceSection, TraceSteps, ScoreTable, AnswerTile, RefList) in reports-app/web/src/components/, exported for reuse by catalog/report/live/review routes (SC-002)
- [X] T020 [US1] Catalog route (cards from /api/catalog) in reports-app/web/src/routes/catalog.tsx (depends on T018, T019)
- [X] T021 [US1] Report route (per-run, from /api/runs/:id/report, using the shared components) in reports-app/web/src/routes/report.tsx (depends on T017, T019)
- [X] T022 [US1] Render unscored/partial + judged-sibling cells and surface record-level evidence (citations + judge notes) in reports-app/web/src/routes/report.tsx

**Checkpoint**: US1 is the MVP — a clean, data-backed catalog + report with no per-run HTML.

---

## Phase 4: User Story 2 - Publish + curate the catalog (Priority: P2)

**Goal**: publish and edit the catalog in-app (prose, order, feature/hide), O(1), with no file editing.

**Independent Test**: publish a second run → it appears and the first run's report is untouched; edit its takeaway, reorder it, and hide a third — all in the UI — and each persists.

### Tests for User Story 2

- [X] T023 [P] [US2] Contract test for POST /api/catalog (publish leaves all other runs' output unchanged) + PATCH /api/catalog/:slug (prose/order/feature/hide persist; scores stay data-derived) in reports-app/api/test/catalog-curate.spec.ts

### Implementation for User Story 2

- [X] T024 [P] [US2] Catalog write module (POST /api/catalog, PATCH /api/catalog/:slug) in reports-app/api/src/catalog/catalog.write.ts
- [X] T025 [US2] Catalog curation UI (publish a run, edit prose, reorder, feature/hide) in reports-app/web/src/routes/catalog.tsx
- [X] T026 [US2] Assert publish is O(1) — no whole-index regen, no other run re-rendered (SC-001) — in reports-app/api/test/catalog-curate.spec.ts

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 - Human adjudication/review (Priority: P3)

**Goal**: reviewers score cells; human scores show alongside the advisory LLM judge; a calibrated headline appears over a reviewed subset.

**Independent Test**: a reviewer scores cells → persisted per reviewer + tier → shown beside the LLM scores → a calibrated headline with uncertainty appears for the reviewed subset.

### Tests for User Story 3

- [X] T027 [P] [US3] Contract test for POST/GET /api/runs/:id/reviews (multi-reviewer, no overwrite; calibrated block only on a reviewed subset, with subset label, reviewed-cell count, source tier(s), estimate, and uncertainty representation) in reports-app/api/test/reviews.spec.ts

### Implementation for User Story 3

- [X] T028 [P] [US3] Reviews module (Reviewer + Adjudication persistence; POST/GET /api/runs/:id/reviews; calibrated-headline response scoped to the reviewed subset with subset label, reviewed-cell count, source tier(s), estimate, and uncertainty representation) in reports-app/api/src/reviews/reviews.controller.ts
- [X] T029 [US3] Review UI — score a cell (axes, harm, note) as reviewer/tier; show human vs advisory-LLM distinctly; render the calibrated headline — in reports-app/web/src/routes/review.tsx
- [X] T030 [US3] Extend the ingest to load any `adjudication.jsonl` present in a run dir in reports-app/api/src/ingest/ingest.service.ts

**Checkpoint**: US1–US3 work independently.

---

## Phase 6: User Story 4 - Watch a run in progress (Priority: P4)

**Goal**: a live view of an executing run, cells appearing as they complete, using the same components as the report.

**Independent Test**: start a run → open the live view → cells appear with status/latency and a drill-in trace, reusing the report's components.

### Tests for User Story 4

- [X] T031 [P] [US4] Contract test for GET /api/runs/:id/live SSE (emits `cell`, `cell:detail`, `done`) in reports-app/api/test/live-sse.spec.ts

### Implementation for User Story 4

- [X] T032 [P] [US4] Live SSE endpoint + the `reports-ingest --watch` tail (tail results.jsonl/trace.jsonl → SSE events) in reports-app/api/src/runs/live.controller.ts + reports-app/api/src/ingest/watch.ts
- [X] T033 [US4] Live route (subscribe to the SSE, render cells with the shared components from T019) in reports-app/web/src/routes/live.tsx

**Checkpoint**: US1–US4 work independently.

---

## Phase 7: User Story 5 - Query + machine-readable consume (Priority: P5)

**Goal**: filter the catalog (model/arm, comparison set, date) and retrieve run data machine-readably.

**Independent Test**: filter by a model and a date range → the correct subset returns; fetch a run's export → it matches the rendered report.

### Tests for User Story 5

- [X] T034 [P] [US5] Contract test for catalog filters (?model=&comparisonSet=&from=&to=) + GET /api/runs/:id/export (matches the report payload) in reports-app/api/test/query-export.spec.ts

### Implementation for User Story 5

- [X] T035 [P] [US5] Catalog filtering (the query params) in reports-app/api/src/catalog/catalog.read.ts
- [X] T036 [P] [US5] Export + agent-readable endpoints (GET /api/runs/:id/export, /api/runs.json, /llms.txt) in reports-app/api/src/runs/export.controller.ts
- [X] T037 [US5] Catalog filter controls in reports-app/web/src/routes/catalog.tsx

**Checkpoint**: all five stories work independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T039 [P] Deploy: flip the `reports.openclinai.org` block from `file_server /srv/reports` to `reverse_proxy` → the Nest service in compose/Caddyfile, and provision the Node service + SQLite on the VM
- [X] T040 [P] Reconcile/migrate the in-flight worktrees (`feat/editable-reports-homepage` → US2, `feat/report-human-feedback` → US3) into this app — do NOT double-build
- [X] T041 [P] Run quickstart.md end-to-end (ingest → catalog → report → publish → review → live) as a smoke
- [X] T042 [P] Docs: a reports-app/README.md + update the repo README / site nav for the new reports surface
- [X] T043 Perf: confirm catalog/report API + page loads <1s for a typical run, reader locate-and-open workflow <30s, publish O(1), and per-report payload materially smaller than today's 1–2 MB self-contained HTML / no per-run presentation bundle inline (SC-001, SC-004, SC-007)
- [X] T044 [P] Verify the machine-readable export covers every published run without HTML scraping (SC-006)

---

## Phase 9: Final Code QA Polishing & Validation

**Goal**: use the `DIGI-UW/code-qa` validation skills as the final merge/release gate after implementation,
story tests, polish, and quickstart smoke are complete.

- [X] T045 Run `code-qa` spec-code-alignment against `spec.md`, `plan.md`, `tasks.md`, `contracts/rest-api.md`, and the implemented `reports-app/`; remediate any drift between artifacts and shipped behavior
- [X] T046 Run `code-qa` meaningful-test-coverage to verify the test suite is not theater, each key guard would fail against a broken implementation, and coverage includes the scoring seam, trace correlation, judged siblings, unscored rendering, review calibration, live SSE, and machine-readable exports
- [X] T047 Run `code-qa` simplicity-review over the final diff; remove speculative abstractions, duplicated presentation logic, dead code, and any accidental scoring logic in TypeScript
- [X] T048 Run `code-qa` evidence-bundle for the quickstart/Playwright smoke where available, preserving screenshots/video/logs plus a short verification report for review
- [X] T049 Run `code-qa` commit-pr-hygiene before PR/merge: ensure comments are timeless, docs and evidence are linked, and the PR summary explains the producer `summary.json` dependency and validation proof

**Checkpoint**: final review evidence shows the implementation matches the spec, meaningful tests prove the
critical guards, and no avoidable complexity or scoring-boundary drift remains.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: depends on Setup — BLOCKS all stories (the schema + ingest are shared).
- **User Stories (P3–P7)**: each depends on Foundational; then independent (US2–US5 build on US1's read API/components but each is independently testable).
- **Polish (P8)**: after the desired stories.
- **Final Code QA (P9)**: after Polish — blocks merge/release readiness.

### User-story dependencies

- **US1 (P1)**: after Foundational. No story dependencies — the MVP.
- **US2 (P2)**: after Foundational; reuses US1's catalog read but adds writes — independently testable.
- **US3 (P3)**: after Foundational; reuses US1's report/cell components — independently testable.
- **US4 (P4)**: after Foundational; reuses US1's components over an SSE source — independently testable.
- **US5 (P5)**: after Foundational; extends US1's catalog read + adds export — independently testable.

### Within each story

- Tests written and FAILING before implementation (Constitution V).
- Schema/DTOs before services; services before endpoints; endpoints before UI.
- Commit after each task or logical group.

---

## Parallel Example: User Story 1

```bash
# Tests first (parallel — different files):
Task: "Contract test GET /api/catalog + /report in reports-app/api/test/catalog-report.spec.ts"   # T015
Task: "Rendering test for trace + unscored cell in reports-app/web/test/report.spec.tsx"           # T016

# Then implementation in parallel where files differ:
Task: "Runs read module in reports-app/api/src/runs/runs.controller.ts"                              # T017
Task: "Catalog read endpoints in reports-app/api/src/catalog/catalog.read.ts"                       # T018
Task: "Shared components in reports-app/web/src/components/"                                         # T019
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL — ingest + schema) → 3. Phase 3 US1 →
4. **STOP and VALIDATE**: ingest a real judged run, confirm the catalog + report render correctly from
data (scores = ingested aggregates, trace correlates, unscored handled) → 5. demo as the MVP.

### Incremental delivery

Foundational → US1 (MVP: data-backed catalog + report) → US2 (in-app publish/curate) → US3 (human
review) → US4 (live) → US5 (query/export) → Polish → final `code-qa` validation. Each story adds value
without breaking the previous; the final gate proves the complete implementation is aligned, tested,
simple, and reviewable.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- The load-bearing seam (research Decision 5): the platform NEVER computes scores — T011 ingests the
  producer's `summary.json`; T038 (harness repo) produces it as a foundational dependency. A temporary
  compatibility fixture may only load already-computed producer aggregate fields; no scoring logic in
  reports-app/.
- Red-first is enforced for the priority targets (T010, T015–T016, T023, T027, T031, T034) — write them
  to fail first, then implement.
- US2/US3 absorb the in-flight `editable-reports-homepage` / `report-human-feedback` work — T040 migrates
  it rather than building twice.
- The final Code QA phase uses the `DIGI-UW/code-qa` skills as a validation gate; if the skills are not
  installed in the repo, install or reference them before T045–T049 rather than replacing the gate with an
  informal manual checklist.
