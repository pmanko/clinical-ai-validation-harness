# Tasks: Catalyst Query Workbench

## Phase 1 — G0 plan gate

- [X] T001 Validate spec/plan/roadmap/task coverage and report only blocking inconsistencies in `specs/008-catalyst-query-workbench/`
- [X] T002 Record G0 dispositions for N1–N8 and obtain user approval in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 2 — Shared foundation

- [X] T003 Add failing workbench session/version/store tests in `targets/catalyst/catalyst-gateway/tests/test_workbench.py`
- [X] T004 Add versioned finding/session API schemas in `targets/catalyst/docs/contracts/`
- [X] T005 Implement append-only workbench storage and migrations in `targets/catalyst/catalyst-gateway/src/catalyst/storage.py`
- [X] T006 Implement canonical advisory validation normalization in `targets/catalyst/catalyst-gateway/src/catalyst/workbench.py`
- [X] T007 Complete G1 persistence/API validation and record evidence in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 3 — User Story 1: edit and validate drafts

- [ ] T008 [P] [US1] Add failing UI tests for full SQL/parameter editing, findings, and version history in `targets/catalyst/catalyst-ui/src/App.test.tsx`
- [X] T009 [US1] Add session/create-version/validate routes in `targets/catalyst/catalyst-gateway/src/catalyst/routes.py`
- [X] T010 [US1] Implement workbench orchestration and immutable validation runs in `targets/catalyst/catalyst-gateway/src/catalyst/service.py` and `targets/catalyst/catalyst-gateway/src/catalyst/workbench.py`
- [ ] T011 [US1] Add workbench API types/client calls in `targets/catalyst/catalyst-ui/src/features/query/api.ts`
- [ ] T012 [US1] Implement SQL/typed-parameter editor, findings, and timeline in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`
- [ ] T013 [US1] Restore the active server session after refresh in `targets/catalyst/catalyst-ui/src/App.tsx`

## Phase 4 — User Story 3: run exact drafts

- [X] T014 [P] [US3] Add exact-SQL, advisory-status, dynamic-type, and DB-diagnostic tests in `targets/catalyst/catalyst-gateway/tests/test_manual_analytics.py` and `targets/catalyst/catalyst-gateway/tests/test_workbench_routes.py`
- [X] T015 [US3] Extend PostgreSQL execution to preserve diagnostics and derive dynamic columns in `targets/catalyst/catalyst-gateway/src/catalyst/analytics.py`
- [X] T016 [US3] Add ungated workbench execution route without changing governed previews in `targets/catalyst/catalyst-gateway/src/catalyst/routes.py`
- [ ] T017 [US3] Render rows, empty/truncated states, and database errors by version in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`
- [X] T018 [US3] Demonstrate exact-query success/failure through the isolated stack and pause at G2 in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 5 — User Story 4: compact dataset context

- [X] T019 [P] [US4] Add disclosure/state/accessibility UI tests in `targets/catalyst/catalyst-ui/src/App.test.tsx`
- [X] T020 [US4] Implement compact Carbon disclosure with retained filters/rows in `targets/catalyst/catalyst-ui/src/features/query/components/DatasetBrowser.tsx`
- [ ] T021 [US4] Persist dataset browser state through workbench session APIs in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`

## Phase 4.5 — Corrective G2.1: model identity and generation boundary

- [X] T039 [P] Add failing Hub profile tests for canonical `gemma-e4b` role identity and availability in `targets/catalyst/.med-agent-hub/tests/test_catalyst_query.py`
- [X] T040 [P] Add failing gateway tests proving workbench generation creates no governed preview and retains policy-bearing candidates in `targets/catalyst/catalyst-gateway/tests/test_workbench_routes.py`
- [X] T041 Align the Catalyst Gemma profile and durable Hub patch with canonical `gemma-e4b` in `targets/catalyst/.med-agent-hub/server/levels.yaml` and `targets/catalyst/patches/med-agent-hub/catalyst-query-profile.patch`
- [X] T042 Extract side-effect-free Hub generation for workbench sessions while preserving governed endpoint behavior in `targets/catalyst/catalyst-gateway/src/catalyst/service.py`
- [X] T043 Wire the isolated manual stack to a worktree-owned llama.cpp router and make every bundled fallback model alias truthful in `targets/catalyst/docker-compose.mvp.yml`, `targets/catalyst/env.recommended`, `targets/catalyst/scripts/`, and `scripts/llama-router-up.sh`
- [X] T044 Re-run real Gemma generation and exact execution, verify physical identity/provenance and no preview side effect, and record G2.1 evidence in `specs/008-catalyst-query-workbench/roadmap.md`
- [X] T045 Record the approved model/pipeline change, validation protocol, rollback, and residual risks in `specs/008-catalyst-query-workbench/pccp/2026-07-17-gemma-routing-and-workbench-generation.md`
- [X] T046 Research and implement an input-first composer with a non-overlapping, focus-preserving sticky jump control in `targets/catalyst/catalyst-ui/src/features/query/components/`
- [X] T047 Remove user-facing prompt examples and duplicate dataset summaries while keeping one live, state-retaining OpenELIS-to-FHIR record browser in `targets/catalyst/catalyst-ui/src/features/query/components/DatasetBrowser.tsx`
- [X] T048 Fix the Hub terminology preflight false positive for counted/recent generic laboratory-result questions and add regression coverage in `targets/catalyst/.med-agent-hub/`
- [X] T049 Omit unavailable profiles from the picker and derive every option label from the Hub profile label plus its unique role-model aliases in `targets/catalyst/catalyst-ui/src/features/query/components/QuestionForm.tsx`
- [X] T050 Add a truthful `catalyst-query-gemma-4-12b` profile and expose the checksum-pinned bundled Qwen Coder 1.5B alias through the umbrella router in `targets/catalyst/.med-agent-hub/server/levels.yaml` and `scripts/llama-router.ini`
- [X] T051 Give the isolated worktree its own router port, route only the isolated Hub to it, and prove all four displayed profiles with real generation/review calls in `scripts/llama-router-up.sh` and the isolated runtime configuration
- [X] T052 Execute the exact Qwen Coder 1.5B and Gemma 4 12B drafts, reconfirm zero governed-preview side effects, and record the checkpoint evidence in `specs/008-catalyst-query-workbench/`

## Phase 6 — W1 integrated validation

- [ ] T022 Add invalid-edit-run-refresh-rerun browser coverage in `targets/catalyst/catalyst-ui/e2e/workbench.spec.ts`
- [ ] T023 Add diverse real-path workbench smoke scenarios in `targets/catalyst/tests/e2e/test_mvp_live.sh`
- [ ] T024 Run gateway, UI, browser, and real-stack checks and record exact-query digest evidence in `specs/008-catalyst-query-workbench/roadmap.md`
- [ ] T025 Update Catalyst user docs and actual status in `targets/catalyst/docs/roadmap.md`
- [ ] T026 Pin the verified Catalyst commit and update harness provenance in `targets/catalyst`
- [ ] T027 Present G3 evidence and unresolved N-items to the user before starting W2 in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 7 — User Story 2: targeted remediation (after G3)

- [ ] T028 [US2] Revalidate repair scope from W1 findings and pause at G4 in `specs/008-catalyst-query-workbench/roadmap.md`
- [ ] T029 [P] [US2] Add AST unit/frozen-digest/patch-integrity tests in `targets/catalyst/catalyst-gateway/tests/test_query_repairs.py`
- [ ] T030 [US2] Implement repair scopes and deterministic patching in `targets/catalyst/catalyst-gateway/src/catalyst/repairs.py`
- [ ] T031 [US2] Implement typed Hub patch generation in `targets/catalyst/.med-agent-hub/server/catalyst_query.py`
- [ ] T032 [US2] Regenerate the reviewed Hub patch in `targets/catalyst/patches/med-agent-hub/catalyst-query-profile.patch`
- [ ] T033 [US2] Add before/after accept/decline repair UI in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`
- [ ] T034 [US2] Run repair integrity/scenario metrics and pause at G5 in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 8 — Harness integration (after G5)

- [ ] T035 Add versioned workbench event/manifest contract tests in `tests/test_metadata.py`
- [ ] T036 Implement session artifact export/import in `harness/catalyst/validation.py`
- [ ] T037 Add one-click export in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx` and validate W3 artifacts in `harness/catalyst/validation.py`
- [ ] T038 Present G6 provenance/model-identity/scenario evidence before comparative claims in `specs/008-catalyst-query-workbench/roadmap.md`

## Dependencies and implementation strategy

G0 (T001–T002) blocks all product code. T003–T007 block US1/US3/US4. US1 and
US3 share session/version state; US4 can proceed after that foundation. T018 and
T027 are mandatory user pauses. US2 and harness integration do not start until
their preceding user gates. W1 MVP is T003–T027; W2/W3 remain separate decisions.
