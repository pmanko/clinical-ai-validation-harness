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

- [X] T053 [US1] Inspect E4B session `2bed91de-fa7d-4ffa-b4ae-0a454a883930`, trace `07740499-387c-40b4-97c3-2bf7c4e08b7e`, retained attempt-1 version `d801dc1d-fc94-435b-bee6-2b45c3173af1`, attempts 2–3 failures and Gemma 4 12B attempts 1–3 failures at `parameters.1: 'name' is required` for “how many patients had viral load tests above 1000 count/ml?”, document the candidate-or-raw diagnostic gap, decide the owning contract/normalization layer, and record the G2.2 disposition and variance in `specs/008-catalyst-query-workbench/roadmap.md` and `specs/008-catalyst-query-workbench/research.md`
- [X] T008 [P] [US1] Add failing tests for exhausted-retry raw-output/best-draft retention and one-to-one missing-parameter normalization plus UI tests for PostgreSQL highlighting, line numbers, default-on wrap/toggle retention, deterministic keyword/catalog completion, deterministic Format, graceful catalog failure, immutable Validate/Run versions, findings, parameters, and history in `targets/catalyst/.med-agent-hub/tests/test_catalyst_query.py`, `targets/catalyst/catalyst-gateway/tests/test_workbench_routes.py`, `targets/catalyst/catalyst-ui/src/App.test.tsx`, and `targets/catalyst/catalyst-ui/src/features/query/components/SqlEditor.test.tsx`
- [X] T056 [US1] Preserve both the best parsed candidate and latest malformed raw generation response, implement the conservative one-question-grounded-parameter/one-placeholder normalization without auto-naming ambiguous cases, and regenerate the durable Hub patch in `targets/catalyst/.med-agent-hub/server/catalyst_query.py`, `targets/catalyst/catalyst-gateway/src/catalyst/service.py`, and `targets/catalyst/patches/med-agent-hub/catalyst-query-profile.patch`
- [X] T054 [US1] Record the G2.2 TDD checkpoint with the diagnostic-retention and missing-parameter regressions, failing editor tests, reviewed editor/formatter version decision, missing-`name` contract disposition, and nondeterminism/inconsistency flags in `specs/008-catalyst-query-workbench/roadmap.md` before SQL editor implementation
- [X] T009 [US1] Add session/create-version/validate routes in `targets/catalyst/catalyst-gateway/src/catalyst/routes.py`
- [X] T010 [US1] Implement workbench orchestration and immutable validation runs in `targets/catalyst/catalyst-gateway/src/catalyst/service.py` and `targets/catalyst/catalyst-gateway/src/catalyst/workbench.py`
- [X] T057 [P] [US1] Add failing contract/route tests for a read-only editor catalog sourced from the gateway's active approved catalog in `targets/catalyst/catalyst-gateway/tests/test_workbench_routes.py` and `targets/catalyst/catalyst-gateway/tests/test_catalyst_mvp.py`
- [X] T058 [US1] Add and register `catalyst.workbench.editor-catalog.v1`, expose `GET /v1/catalyst/workbench/catalog`, and derive its ordered PostgreSQL schema/view/column vocabulary from the existing gateway catalog in `targets/catalyst/docs/contracts/`, `targets/catalyst/catalyst-gateway/src/catalyst/routes.py`, and `targets/catalyst/catalyst-gateway/src/catalyst/service.py`
- [X] T011 [US1] Add workbench API types/client calls in `targets/catalyst/catalyst-ui/src/features/query/api.ts`
- [X] T012 [US1] Implement the reviewed PostgreSQL editor with highlighting, line numbers, default-on retained wrap toggle, approved-catalog/keyword completion, deterministic Format, exact immutable child-version persistence, exhausted-retry raw-output/best-draft inspection, typed parameters, findings, and timeline in `targets/catalyst/catalyst-ui/src/features/query/components/SqlEditor.tsx` and `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`
- [X] T013 [US1] Restore the active server session after refresh in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`

## Phase 4 — User Story 3: run exact drafts

- [X] T014 [P] [US3] Add exact-SQL, advisory-status, dynamic-type, and DB-diagnostic tests in `targets/catalyst/catalyst-gateway/tests/test_manual_analytics.py` and `targets/catalyst/catalyst-gateway/tests/test_workbench_routes.py`
- [X] T015 [US3] Extend PostgreSQL execution to preserve diagnostics and derive dynamic columns in `targets/catalyst/catalyst-gateway/src/catalyst/analytics.py`
- [X] T016 [US3] Add ungated workbench execution route without changing governed previews in `targets/catalyst/catalyst-gateway/src/catalyst/routes.py`
- [X] T017 [US3] Render rows, empty/truncated states, and database errors by version in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx` and `targets/catalyst/catalyst-ui/src/features/query/components/WorkbenchPanel.tsx`
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

## Phase 4.6 — Corrective G2.3: localized generation retry

- [X] T059 Record the live E4B/12B whole-object retry regression, manual valid and invalid execution evidence, N18–N20, and the approved patch-only retry contract in `specs/008-catalyst-query-workbench/`
- [X] T060 [P] Add failing Hub tests for strict finding-scoped patch responses, frozen unaffected fields, uniquely anchored SQL text changes, missing-name leaf patches, and rejection/diagnostic retention for full, duplicate, ambiguous, stale, or out-of-scope changes in `targets/catalyst/.med-agent-hub/tests/test_catalyst_query.py`
- [X] T061 Implement localized generation patch contracts/application and regenerate the durable Hub patch in `targets/catalyst/.med-agent-hub/server/catalyst_query.py`, `targets/catalyst/.med-agent-hub/server/contracts/`, and `targets/catalyst/patches/med-agent-hub/catalyst-query-profile.patch`
- [X] T062 Rebuild the isolated Hub and repeat the exact E4B/12B question, proving physical model identity, frozen-unit integrity, full revalidation, best/raw retention, and manual Validate/Run behavior in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 4.7 — Corrective G2.4: unresolved raw-draft hydration

- [X] T063 Record the raw-visible/editor-empty boundary, minimal unresolved-seed contract, acceptance cases, and N23 in `specs/008-catalyst-query-workbench/`
- [X] T064 [P] Add failing gateway contract/route tests and UI create/refresh tests proving exact raw preservation, unresolved SQL/parameter hydration with blank missing names, immutable-version precedence, and evidence-only fallback for malformed or non-object output in `targets/catalyst/catalyst-gateway/tests/` and `targets/catalyst/catalyst-ui/src/App.test.tsx`
- [X] T065 Implement a response-derived unresolved draft seed and hydrate the editor from it only when no immutable current version exists in `targets/catalyst/catalyst-gateway/src/catalyst/service.py`, `targets/catalyst/docs/contracts/`, and `targets/catalyst/catalyst-ui/src/features/query/`; then rebuild the isolated stack and verify the retained 12B session before continuing G3

## Phase 4.8 — Corrective G2.5: generator binding normalization

- [X] T066 Record the generator/final-contract boundary, simple ordered pairing, count-mismatch fallback, real 12B execution checkpoint, and N24 in `specs/008-catalyst-query-workbench/`
- [X] T067 Add failing Hub tests for optional generated names/source, ordered pairing for the exact 12B and longer-query shapes, count-mismatch retention, final-contract strictness, lint continuation, and no name-only retry in `targets/catalyst/.med-agent-hub/tests/test_catalyst_query.py`
- [X] T068 Relax only the backend generation parameter schema, implement ordered placeholder/parameter pairing before final validation/lint, update the generation prompt, and regenerate the durable Hub patch in `targets/catalyst/.med-agent-hub/server/` and `targets/catalyst/patches/med-agent-hub/catalyst-query-profile.patch`
- [X] T069 Rebuild the isolated Hub, rerun the exact Gemma 4 12B question through generation, lint/review, manual execution, and refresh, then record SQL validity, database outcome, returned-data evidence, physical model identity, and remaining inconsistencies in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 4.9 — Corrective G2.6: writer–reviewer collaboration

- [X] T070 Record the approved one-writer/one-reviewer flow, distinct-model requirement, complete-candidate correction, deterministic re-lint, two-version persistence/visibility, N25–N26, and the live checkpoint in `specs/008-catalyst-query-workbench/`
- [X] T071 Add failing Hub, gateway, and UI tests proving one writer call, deterministic findings delivered to a different reviewer model, complete corrected-candidate return, deterministic re-lint, linked `model`/`model_repair` versions, and visible model/stage evidence in `targets/catalyst/.med-agent-hub/tests/`, `targets/catalyst/catalyst-gateway/tests/`, and `targets/catalyst/catalyst-ui/src/`
- [X] T072 Implement the writer–lint–reviewer–re-lint orchestration, mixed Gemma 4 12B/Qwen 2.5 14B role profile, collaboration result contract, gateway lineage persistence, workbench evidence UI, durable Hub patch, and PCCP record in `targets/catalyst/.med-agent-hub/`, `targets/catalyst/catalyst-gateway/`, `targets/catalyst/catalyst-ui/`, and `targets/catalyst/patches/med-agent-hub/`
- [X] T073 Rebuild the isolated stack, rerun the exact Gemma 4 12B writer/Qwen 2.5 14B reviewer question through PostgreSQL execution and refresh, then record both candidates/versions, lint/review trace, physical model identities, exact query digest/result rows, and any nondeterminism in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 4.10 — Corrective G2.7: manual reset controls

- [X] T074 Add separate New session and Clear draft controls without deleting retained server evidence or changing the selected available profile in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`
- [X] T075 Prove both reset boundaries with focused/full UI checks and one live isolated-browser iteration, and record the evidence in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 4.11 — Corrective G2.8: iterative query notebook

The tasks in this phase record the then-current Hub-owned query-profile
implementation and its evidence. They remain completed historical work; the
Gateway-ownership refactor is tracked separately in Phase 4.14.

- [X] T076 Record the approved artifact-first linear notebook, current-state/Hub audit, UX research, turn/data/context contracts, sibling-Hub ownership decision, G2.8a–c checkpoints, and N27–N42 across `specs/008-catalyst-query-workbench/`
- [X] T077 Record the initial Spec Kit analysis findings and remediate the written PCCP timing, test-order, runtime-ownership, failure-recovery, and live-evidence gaps in `specs/008-catalyst-query-workbench/`; leave the final reanalysis result pending
- [X] T078 Create the preimplementation PCCP change record for all G2.8 Hub prompt/profile/pipeline, gateway, UI, and runtime changes in `specs/008-catalyst-query-workbench/pccp/2026-07-18-iterative-query-notebook.md`
- [X] T079 Re-run the read-only Spec Kit cross-artifact analysis, resolve any remaining CRITICAL/HIGH written-plan finding, record the final result, and pause for G2.8a user acceptance before product-code changes
- [X] T080 Add failing Hub tests for the v2 revision request with observed/effective/snapshot evidence, exact current instruction, deterministic five-prior-follow-up truncation, typed-context rejection of result rows/credentials/connection details/hidden reasoning/raw traces/historical SQL/full chat/unrelated sessions, the reviewer invocation even for lint-clean writer output, complete semantic reviewer correction, selected writer-versus-reviewer output, valid-but-unselected writer on reviewer failure, invalid-candidate evidence, Hub/tool failure evidence, writer/reviewer provenance, and one timing record for every successful or failed invocation containing role, stage, attempt, model, start/end timestamps, duration, request digest, and response-or-normalized-failure digest in `targets/med-agent-hub/tests/`; these tests block T081
- [X] T081 Publish and register an offline-resolvable Hub contract bundle containing `catalyst-query-request-v1.schema.json`, `catalyst-query-request-v2.schema.json`, `catalyst-query-revision-context-v1.schema.json`, `catalyst-workbench-editor-snapshot-v1.schema.json`, and `catalyst-workbench-turn-request-v1.schema.json` plus their transitive references; then implement the profile, explicit-instruction linting, always-invoked complete revision writer/reviewer flow, selected-output and valid-unselected-writer invariants, invalid-candidate/failure evidence, trace provenance, and per-invocation timing/digests for successful and failed model calls in the real sibling Hub in `targets/med-agent-hub/`
- [X] T082 [P] Add failing store tests for newly recorded initial requested/terminal turns and generation evidence; deterministic read-only legacy fixtures with model-current, later-human-current, draft-only, and raw-only evidence; append-only requested/completed/failed projection; the shared unchanged/dirty editor resolver for follow-up, Validate, and Run with active-turn provenance; atomic one-active-generation claim; paired concurrency; orphan recovery without inference retry; observed/effective/snapshot/current-anchor integrity; valid-but-unselected writer persistence; invalid-candidate non-version evidence; and unresolved input in `targets/catalyst/catalyst-gateway/tests/`; these tests block T084
- [X] T083 [P] Add failing gateway context/contract/route tests for recorded initial turns with complete per-invocation timing/digests and empty omissions; model-current, later-human-current, draft-only, and raw-only legacy fixtures whose unavailable prompt/model/config/timing/digest fields remain null with typed omissions and no invented provenance; the deterministic legacy terminal-time precedence of selected initial output, then raw/generation outcome, then session creation; typed turn detail and generation-evidence retrieval; compact timeline profile/prompt references with full prompts only in evidence detail; shared unchanged/dirty Validate/Run resolution without duplicate versions and with active-turn provenance; exact observed/effective/snapshot/current-anchor digests; stale and unavailable-profile rejection before events; per-turn profile switching; deterministic five-instruction truncation; every prohibited-context negative; exact-digest validation/execution summaries including bounded `timed_out` and `cancelled` diagnostics; normal/legacy refresh without inference; exact orphan stage `orphan_recovery` and code `generation_interrupted`; failure recovery; and no automatic execution in `targets/catalyst/catalyst-gateway/tests/`; these tests block T084–T086
- [X] T084 Implement the atomic event-backed turn store, recorded initial requested/terminal events and generation evidence, deterministic non-mutating four-fixture legacy synthesis, shared follow-up/Validate/Run editor resolution with active-turn provenance, one-active-generation compare-and-set claim, observed/effective/snapshot/current-anchor reconciliation, selected-current and valid-unselected-writer invariants, invalid-candidate non-version handling, and startup orphan reconciliation to one terminal failure with stage `orphan_recovery` and code `generation_interrupted` in `targets/catalyst/catalyst-gateway/src/catalyst/storage.py`
- [X] T085 Implement the deterministic bounded revision-context builder, explicit included/omitted evidence, exact-digest matching, five-follow-up truncation, bounded failed/`timed_out`/`cancelled` execution diagnostics, and all prohibited-context filters in `targets/catalyst/catalyst-gateway/src/catalyst/`
- [X] T086 After T081, T084, and T085, publish/register the turn-request, editor-snapshot, editor-snapshot-record, turn, timeline, and generation-evidence schemas with recorded invocation timing/digests and typed legacy omissions; implement session creation with recorded initial events and empty omissions, the shared resolver in follow-up/Validate/Run orchestration, GET/POST turn routes, `GET /sessions/{sessionId}/turns/{turnId}/generation-evidence`, compact timeline profile/prompt references with full prompts only in evidence detail, exact Hub timing preservation, deterministic legacy terminal-time precedence and null-plus-omission projection without invented provenance, per-turn profile provenance, Hub v2 calls, effective-base-to-writer-to-reviewer persistence, valid-but-unselected writer recovery, invalid-candidate evidence, and explicit no-auto-Run behavior in `targets/catalyst/catalyst-gateway/` and `targets/catalyst/docs/contracts/`
- [X] T087 [P] Add a failing root harness test in `tests/test_catalyst_submodule_layout.py` proving the umbrella runner builds sibling `targets/med-agent-hub`, pins the same Hub ref supplied to Catalyst's standalone fallback, and never applies the Catalyst patch; this test blocks T088–T089
- [X] T088 Wire `scripts/catalyst-mvp.sh` and isolated compose assembly to use the harness-owned sibling Hub build context and record the exact sibling commit in health/provenance
- [X] T089 After T088, retire Catalyst's disposable Hub patch/runtime source and keep only an unpatched, same-pinned-commit standalone clone fallback in `targets/catalyst/`; prove Catalyst still declares no nested submodule
- [X] T090 [P] Add failing UI tests for compact/read-only prior turns, latest-turn editor ownership, Refine Query base/profile/model labels, dirty/unchanged/unresolved/empty drafts, Restore Query, selected output, failed-turn recovery, stale result labels, per-turn profile switching, refresh, New Session isolation, adaptive jump focus, keyboard use, narrow viewport, and 200% zoom in `targets/catalyst/catalyst-ui/src/`; these tests block T091
- [X] T092 After T081 and T084–T089, pass the Hub, gateway/store, root runtime, schema-publication/registry, contract, lint, and diff checks before UI implementation; add a lightweight assertion that recorded initial/follow-up turn, snapshot, and generation-evidence events map without loss into the existing versioned `events.jsonl` envelope, without implementing W3 export; record contract drift and block T091 on any failure
- [X] T091 After T090 and T092, implement the linear notebook UI, exact active-buffer submission, compact timeline, Restore Query, per-turn available-profile picker, typed generation-evidence detail, complete successor selection, result version/staleness labels, failure state, and adaptive canonical-composer focus in `targets/catalyst/catalyst-ui/src/features/query/`
- [X] T093 Pass the post-UI full Hub, gateway/store, root harness, UI, Playwright, accessibility, lint, typecheck, build, contract-registry, and diff gate; record any contract drift or conditional model-output digest difference before real-path validation
- [X] T094 Add and run diverse real-path validation for narrowing, aggregation/output-shape change, unresolved correction, lint-clean semantic reviewer correction, and Hub/tool failure; include dirty/unchanged bases, profile switching, stale results, New Session isolation, exact selected output, timed-out/cancelled diagnostic presentation, and record-level PostgreSQL cross-check fixtures/evidence
- [X] T095 Rebuild the isolated sibling-Hub stack and complete G2.8c with Gemma 4 12B writing/Qwen 2.5 14B reviewing at temperature zero with the DRY repetition penalty disabled: run the T094 scenario families, inspect typed generation evidence and exact context/trace/model/effective-configuration provenance, conditionally report candidate/output digest differences when observed under that configuration, verify initial-question submit through successor-query visible in under 3 minutes after subtracting only the exact recorded durations of every initial/follow-up writer/reviewer invocation and reconcile those durations to their start/end timestamps and request/response-or-failure digests, report unadjusted wall time and explicit Run/database time separately, complete keyboard-only/narrow/200%-zoom checks, record reproducible SQL/parameters plus dataset/session/turn/query/version/execution IDs and inspected-record rationale, then pause for user acceptance
- [X] T096 After G2.8c/T111 user acceptance, update the root `README.md`, Catalyst user docs/status, final quickstart, roadmap, and applicable PCCP evidence/rollback/residual-risk dispositions; documentation follows evidence and precedes ready-for-review/merge acceptance
- [X] T097 Commit/push the companion Hub and Catalyst changes, pin both sibling submodules in harness PR #37, rerun root pin/provenance checks, and update the PR without starting W2/W3. Published as drafts under explicit 2026-07-20 user direction; T094–T096 still block ready-for-review/merge acceptance

## Phase 4.12 — Corrective G2.9: unified workbench UX and queryable schema

- [X] T098 Measure the restored active-session scroll/focus flow, audit the exact execution-context boundary and live PostgreSQL/catalog surfaces, research primary database-assistant/schema-browser and WCAG patterns, record N55–N58 plus the one-composer/one-editor workbench-dock proposal and acceptance cases in `specs/008-catalyst-query-workbench/`, and pause for G2.9a user acceptance before product-code changes
- [X] T099 Superseded by T108/T127's deterministic component and Playwright coverage for one composer/editor, history, adjacent actions, bounded results, grounding labels, dock/reflow, refresh, focus, narrow layouts, and 200%-equivalent behavior
- [X] T100 Superseded by the shipped generated 16-column `analytics.lab_result_fact_v1` catalog plus T108/T111 runtime/catalog/provenance gates; G2.10's broader multi-source metadata acceptance remains separately open
- [X] T101 Superseded by the runtime-backed `DatasetBrowser`/editor catalog path and its component/live catalog coverage accepted through T108/T111
- [X] T102 Superseded by the shipped `WorkbenchPanel`/`TurnNotebook` workspace and complete iterative-browser flow accepted through T108/T127/T111
- [X] T103 Superseded by the shipped matching/stale/unexecuted execution-summary boundary and negative exclusion of result rows accepted through T108/T111; no value-level attachment was approved
- [X] T104 Superseded by T111's complete real-profile/PostgreSQL acceptance plus T127's accessibility regression; its exact historical file-list command was not rerun verbatim
- [X] T105 Correct `patient_flat_v1.name_display` with a tested FHIRPath fallback; emit and render deterministic all-blank/NULL result-column feedback without hiding successful rows; forward only the bounded exact-digest warning to refinement context; and reproduce the original query through the isolated stack

## Phase 4.13 — PR merge-readiness audit

- [X] T106 Audit Hub #14, Catalyst #4, and harness #37 against their base branches, canonical specs, review threads, CI, local full suites, pinned dependency graph, clean-boot path, provenance, and squash behavior; record substantive findings even when GitHub reports green
- [X] T107 Resolve the Hub follow-up-prompt, parameter-normalization, analyte-detection, table/column lint, CTE-relation, metadata-redaction, timing-contract, and reviewer-decision findings with focused and full regression tests
- [X] T108 Resolve the Catalyst active-instruction, profile-binding, catalog-lineage, execution-idempotency, current-version provenance, stale expected-column, and complete iterative-browser-flow findings; add UI and analytics/assembly jobs to CI
- [X] T109 Make the tracked umbrella boot reproducible from a clean recommended environment: correct fake-mode/port propagation, enforce clean matching sibling pins, tolerate an empty successful OpenELIS backfill response, pin OpenELIS deployment source/images, and rerun the health/provenance gate
- [X] T110 Align `docs/specification.md`, `docs/roadmap.md`, `docs/med-agent-hub.md`, root README/quickstart, Harness provider/component/profile provenance, real-suite model IDs, and PR descriptions with the tested implementation
- [X] T111 Rerun the complete Hub/Catalyst/harness automated gates plus the T094/T095 live iterative workflow on clean pins; prove the versioned Hub backend inventory, exact required model aliases, available-profile subset, unavailable initial/governed/follow-up rejection before state or model calls, writer-only and reviewed provenance, independent PostgreSQL evidence, and pause for user acceptance
- [X] T112 Hub #15 is already merged and pinned. After T111 acceptance, squash Catalyst, repin the resulting Catalyst `main` commit while retaining Hub `main` in the harness, rerun the required pin/live gates, obtain the required harness approval, and squash harness last

T112 progress note (2026-08-04): Catalyst #5 source head `5f23c4e` passed all
five CI jobs and squash-merged to `main` as `e7eba21`. The harness working tree
now pins Catalyst `e7eba21` and Hub `092b5cd`. Full health/provenance passed;
real-model run `70d76a43-d687-4f2a-afe6-e23ca75fe6df` passed 1/1 with 2/2
independent PostgreSQL checks and 2/2 gold-result comparisons. Harness #37 then
passed required CI and squash-merged to `main` as `776a363`, completing T112.

T111 historical execution note (2026-07-30): the PR-head 12/12 model/PostgreSQL
matrix and bounded-failure/same-session recovery passed on harness `e475d7a`,
Catalyst `bb36126`, and Hub `198d5f6`. Responsive 390/320 CSS-pixel and
200%-layout-equivalent checks passed. Catalyst candidate `95515a2` subsequently
aligned the standalone fallback Hub SHA with `198d5f6`; focused umbrella
pin/layout coverage passes 57/57, and clean umbrella `93689d5` run
`4dd70443-ba23-4415-b0cd-d393d2352061` passed a scoped 1/1 real-model/
PostgreSQL candidate-head smoke. Catalyst `be3f95c` then removed only the stale
literal-Hub-SHA assembly assertion; the exact 38-test CI command is green with
one expected local driver skip. This historical checkpoint preceded the actual
keyboard-only traversal, actual 200% browser zoom, and user acceptance recorded
on 2026-08-04.

T111 reconciliation note (2026-08-03): Hub #15 is merged at `092b5cd`.
Catalyst #5 is clean and pushed at `9aa0e0f`; Harness #37 is clean, has
evidence-receipt parent `6f58d45`, and pins Catalyst `9aa0e0f` plus Hub
`092b5cd`. Final-pin run
`0671dc34-26c6-4d52-8443-47e0a833a539` passed 12/12 real-model repetitions,
24/24 independent PostgreSQL comparisons, and 18/18 gold-result comparisons.
Bounded-failure run `fb6377c1-0b60-492a-8053-cc668a201d15` passed 1/1; after
the expected failed turn preserved its base, a same-session recovery generated,
validated, executed, and independently matched PostgreSQL. The PHI-safe
accepted receipt is `evidence/t111-final-acceptance-2026-08-03.json`. The user
confirmed actual keyboard-only traversal and actual 200% browser zoom both
passed and accepted the MVP on 2026-08-04, completing T094/T095/T111. Catalyst
#5 and harness #37 have since squash-merged; `main` pins Catalyst `e7eba21` and
Hub `092b5cd`, and T112 is complete.

## Phase 4.14 — Gateway-owned query orchestration reconciliation

- [X] T113 Record the current Catalyst Gateway-owned query profile/prompt/writer-reviewer/lint architecture, generic Hub role-executor boundary, active PR chain (#37/#5/#15), and pre-refactor evidence limitation in the feature spec/plan/roadmap/status artifacts without rewriting historical G2.8 results
- [X] T114 Add a PCCP change record for the query-orchestration ownership change with validation protocol, rollback boundary, current pin state, and residual risk; leave final evidence pending T111
- [X] T115 Update Catalyst and Hub submodule user docs plus active PR descriptions in their owning PRs so no current claim assigns Catalyst query profiles/orchestration to Hub; preserve explicitly labelled historical design records

## Phase 4.15 — G2.10 multi-source and lossless source onboarding

- [X] T116 Trace the 2026-07-22 amendment into User Story 6, FR-064–FR-070, SC-030–SC-034, source/catalog entities and boundaries, plan gates G2.10a–c, this task phase, roadmap checkpoints, and quickstart checks without claiming implementation acceptance
- [ ] T117 Inventory existing source-registry, per-turn source inheritance, unavailable-source, refresh, and per-source stale-catalog tests against FR-064–FR-066; add failing contract tests for any uncovered behavior before changing implementation
- [ ] T118 Verify every accepted base ViewDefinition against its pinned upstream default or documented additive/gap-fill provenance; add multiplicity fixtures proving repeated resources/codings survive lossless `forEachOrNull` projection with no `.first()`-style selection
- [ ] T119 Verify deterministic curated SQL grain and column comments, generator byte stability, missing-metadata/unknown-relation/zero-match failures, overlay validation, and live information-schema agreement for each acceptance source
- [ ] T120 Preserve `dataSourceId`, per-source catalog baseline/version, projection/curation/catalog digests, and source readiness scope across session, turn, query version, validation, execution, generation evidence, `run_manifest.json`, and `events.jsonl` contracts
- [ ] T121 Recreate a clean two-source stack and run A → B → inherited B → A plus unavailable-source rejection, per-source stale conflicts, refresh, exact query execution, and independent record-level PostgreSQL checks; explicitly verify default-only readiness does not claim full-registry health
- [ ] T122 Record G2.10b evidence, run the G2.10c user checkpoint, and pause for explicit acceptance before describing multi-source/lossless onboarding as complete or using it in release evidence

## Phase 4.16 — T111 current-profile validation repair

- [X] T123 Align the committed T094 suite and notebook-validation runner with the Gateway's current revision-capable writer-only and Gemma 4 12B/Qwen 2.5 14B reviewed profiles; preserve a real per-turn profile switch, require exact optional-reviewer discovery/evidence, and label writer-only reports without inventing reviewer provenance

## Phase 4.17 — Runtime profile availability and provenance repair

- [X] T124 Publish Hub's versioned backend model inventory; derive Catalyst availability from exact advertised writer/reviewer aliases; fail closed on missing, malformed, unreachable, or incomplete inventory; omit unavailable UI choices; reject unavailable initial, governed-preview, and follow-up selections before mutation/model calls; preserve truthful transport evidence; and use Gateway-owned profile/prompt references with focused and full component coverage

## Phase 4.18 — Bounded structured-output generation

- [X] T125 Bound every Catalyst query-profile writer/reviewer completion to an explicit output-token budget; prove the limit is sent to Hub/router and retained in invocation provenance; reset the external router after the pre-fix runaway request; rerun focused component gates and the complete clean-pin T094/T095/T111 matrix without treating a truncated or timed-out candidate as success

## Phase 4.19 — Current-profile collaboration evidence repair

- [X] T126 Restore the comparative Gemma/Qwen profile's already-approved collaborative-review policy after the Gateway ownership move; give the reviewer the same current instruction and bounded revision context as the writer; on reviewer output-contract failure preserve and correctly label the exact malformed reviewer output and the contract-valid writer as unselected evidence while leaving the effective base current; add focused regressions and rerun the reviewed-profile smoke before the complete T094/T095/T111 matrix

## Phase 4.20 — Accepted accessibility regression

- [X] T127 Record the user's actual keyboard-only and 200%-browser-zoom PASS; add deterministic Playwright coverage for uninterrupted Tab navigation and 200%-equivalent reflow; fix the expanded-composer scroll obstruction exposed by that regression; and rerun UI unit, lint, typecheck, build, and Playwright gates

## Phase 6 — W1 integrated validation (superseded closeout)

The later G2.8/T111 merge-readiness sequence exercised a stricter superset of
this legacy G3 checklist. The items below are closed by explicit supersession,
not by claiming their original file-specific wording was executed verbatim.
This does not start or approve W2.

- [X] T022 Superseded by T108/T127 deterministic complete-flow and accessibility browser coverage
- [X] T023 Superseded by the diverse real-path T094 matrix and clean-pin T111 rerun
- [X] T024 Superseded by T094/T095/T111 Gateway, browser, real-stack, digest, and PostgreSQL evidence recorded in `specs/008-catalyst-query-workbench/roadmap.md`
- [X] T055 Superseded by the accepted T095/T127 editor, keyboard, responsive-layout, and actual 200%-zoom validation
- [X] T025 Superseded by T096/T110/T115 documentation reconciliation
- [X] T026 Superseded by T112's merged Catalyst/Hub pins and post-merge harness provenance verification
- [X] T027 Superseded by the T095/T111 user-acceptance checkpoint; W2 remains separately gated by T028/G4

## Phase 7 — Parallel query-assistance pathway: User Story 2 (not selected)

- [ ] T028 [US2] Revalidate repair scope from W1 findings and pause at G4 in `specs/008-catalyst-query-workbench/roadmap.md`
- [ ] T029 [P] [US2] Add AST unit/frozen-digest/patch-integrity tests in `targets/catalyst/catalyst-gateway/tests/test_query_repairs.py`
- [ ] T030 [US2] Implement repair scopes and deterministic patching in `targets/catalyst/catalyst-gateway/src/catalyst/repairs.py`
- [ ] T031 [US2] Implement a user-initiated typed repair-proposal contract in Catalyst Gateway, limited to selected AST units and frozen digests; execute any model proposal role only through Hub's generic role endpoint, and do not reuse the internal G2.3 retry as an accept/decline workflow
- [ ] T032 [US2] Verify the Gateway-owned proposal contract and generic Hub runtime path through the pinned sibling `targets/med-agent-hub`, including the umbrella sibling build/pin and Catalyst's unmodified same-commit standalone fallback; do not add Catalyst query logic to Hub or restore the retired patch
- [ ] T033 [US2] Add before/after accept/decline repair UI in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`
- [ ] T034 [US2] Run repair integrity/scenario metrics and pause at G5 in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 8 — Parallel evaluation pathway: session export (not selected)

- [X] T035 Superseded by T129/T130's authoritative notebook manifest/event contract and tests under `evals/metadata/`, per the approved validation integration roadmap; governed-preview export remains outside that replacement
- [ ] T036 Implement session artifact export/import in `harness/catalyst/validation.py`
- [ ] T037 Add one-click export in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx` and validate W3 artifacts in `harness/catalyst/validation.py`
- [ ] T038 Present G6 provenance/model-identity/scenario evidence before comparative claims in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 9 — Evaluation release closeout: Catalyst report parity (PR #43)

- [X] T128 Reconcile merged Hub #15, Catalyst #5, and harness #37 state; audit the real Catalyst notebook runner, judge/finalizer, report, CLI, publisher, and curated index against ChartSearchAI; record the exact implemented-versus-missing P4/P5 boundary without claiming gate completion
- [X] T129 Add red metadata/integration tests for publish-ready Catalyst `run_manifest.json`, versioned run/scenario/turn/version/execution `events.jsonl`, resolvable evidence references, and judge-finalization evaluation events without rewriting the run-start manifest
- [X] T130 Implement the CVR-G13 manifest/event contract, update the shared metadata schema, and preserve compatibility with existing notebook evidence/result artifacts
- [X] T131 Add red CLI parity tests, then implement `harness-cli catalyst run` with every notebook-runner option and `harness-cli catalyst report <run_dir>` while retaining the script as a thin compatibility wrapper
- [X] T132 Add red mixed-family dry-run publishing/index tests, then implement `scripts/publish-report.sh` and family-aware metadata, result loading, badges, deterministic gold rate, and advisory Catalyst judge median without routing Catalyst through Scout or freezing a ChartSearchAI dashboard
- [X] T133 Dry-run stage one ChartSearchAI fixture and one Catalyst fixture; pass and record CVR-G13–G15 before starting release claims
- [X] T134 Produce the five independent D13 code-QA artifacts, resolve every BLOCKER, and pass CVR-G16
- [X] T135 Run the complete real T094 suite on clean merged pins, apply the recorded Catalyst judge exactly three times, finalize, render, publish, and verify record-level evidence at the live URL for CVR-G17
- [X] T136 Pass release CI/pin/docs/PCCP hygiene, record CVR-G18, and pause for MS-D user signoff before calling Catalyst report parity released

## Phase 10 — Selected next product milestone: Superset-backed Dashboard Builder MVP

This milestone depends only on the accepted query/version/execution/table
foundation. T117–T122 multi-source acceptance, T028–T034 query assistance,
T036–T038 session export, narrative reporting, and production hardening remain
parallel and do not block it.

- [X] T137 [US7] Complete the written-plan checkpoint: align the supplied high-fidelity design, `spec.md`, `plan.md`, `data-model.md`, `quickstart.md`, both roadmaps, Catalyst's canonical specification, the Superset research/load-reload notes, and matching `contracts/catalyst-superset-bundle-v1.schema.json` copies in feature 008 and Catalyst docs; run the read-only cross-artifact analysis and record all nondeterminism/deferrals before product-code changes
- [ ] T138 [US7] Add red Compose/launcher/health/import tests, then pin Apache Superset 6.1.0 plus persistent metadata storage and the read-only outbox mount in `targets/catalyst/docker-compose.mvp.yml`, Catalyst `scripts/mvp-*.sh`, `compose/catalyst-mvp-isolated.override.yml`, and `scripts/catalyst-mvp.sh`; provide bootstrap import and an explicit running-instance import/update command
- [ ] T139 [US7] Add failing schema/storage/generator tests for Dataset/Widget/Dashboard immutable versions, exact execution lineage, stale/missing sources, deterministic typed parameter compilation, a stable logical Dashboard UUID with version-derived child UUIDs, byte-identical native ZIPs, atomic outbox publication, and import outcomes in `targets/catalyst/catalyst-gateway/tests/test_dashboard_builder.py` plus the versioned bundle contract
- [ ] T140 [US7] Implement Gateway draft libraries, deterministic visualization compatibility/suggestion, Superset bundle generation/download/outbox publication, append-only provenance, and typed create/read/save/export routes without model calls or automatic query execution in `targets/catalyst/catalyst-gateway/src/catalyst/`
- [ ] T141 [US7] Add failing typed UI/API/E2E tests, then implement the supplied Ask/Datasets/Widgets/Dashboards shell, persistent Ask composer, chronological draft tiles, one slide-over review panel, five supported visualization families with a compact compatible-type selector/read-only bindings and schematic thumbnails only, libraries, stale states, `Publish to Superset`, download, import status, and `Open Superset` in `targets/catalyst/catalyst-ui/src/features/`
- [ ] T142 [US7] Prove deterministic refresh restoration, zero model/database calls during configuration, byte-identical export, clean Superset import, changed publication through a stable Dashboard UUID plus new versioned child UUIDs, and rendered-value parity with PostgreSQL in automated real-path tests; also cover idempotent same-digest import, failed import recovery, keyboard traversal, narrow layout, and actual 200% zoom
- [ ] T143 [US7] Record the implemented contract, validation/rollback protocol, provenance/credential boundary, residual risks and explicit API/narrative/security deferrals in the PCCP and roadmap/status docs; demonstrate the real Catalyst → outbox → Superset workflow and pause for user acceptance

## Dependencies and implementation strategy

G0 (T001–T002) blocks all product code. T003–T007 block US1/US3/US4. T053 and
T008 block T056, and T057 blocks T058. T056 and T058 must complete before the
G2.2 record in T054; T054 blocks T011–T013 editor wiring. T059 blocks T060,
T060 blocks T061, and T061 blocks the real-profile revalidation in T062. T063
blocks T064, and T064 blocks T065. T066 blocks T067, T067 blocks T068, and T068
blocks T069. T070 blocks T071, T071 blocks T072, and T072 blocks the combined
real-profile validation in T073 before G3. US1 and US3 share
session/version state; US4 can proceed after that
foundation. T018 and T027 are mandatory user pauses, and T055 is required G3
manual evidence before T027. The narrow generation retry integrity work in
T059–T069 does not authorize the broader W2 remediation workflow. US2 and harness integration do not start until
their preceding user gates. W1 MVP includes T003–T027 and the corrective G2.1,
G2.2, G2.3, G2.4, G2.5, G2.6, G2.7, and G2.8 phases (T039–T097); W2/W3
remain separate decisions. T076–T078 are written prerequisites; T079 is the
mandatory G2.8a user pause before any product task. Hub red tests T080 block
T081. Store and gateway red tests T082–T083 block T084–T086; T081, T084, and
T085 additionally block T086. The root runtime red test T087 blocks T088, and
T088 blocks T089. UI red tests T090 may be written in parallel, but T090 and the
backend/Hub/store/root contract-drift checkpoint T092 both block UI implementation
T091. T081 and T084–T089 block T092. T091 blocks the post-UI full gate T093;
T093 blocks diverse real-path validation T094, which blocks the G2.8c/user pause
T095. The user-directed draft publication in T097 was an explicit exception to
the original T096-before-pinning order; T096 still blocks ready-for-review/merge
acceptance, not the already-completed draft publication. T123 and T124 block the
live T111 run; T111 blocked the now-complete T112. T113
documents the post-G2.8 ownership refactor; T114 and T115 must land before T111
acceptance, with T115 applied in the owning component PRs. T116 is the written
G2.10a traceability gate. T117–T120 block the clean two-source run T121, which
blocks the G2.10c
user pause T122. G2.10 acceptance is separate from and does not silently close
T094/T095/T111, W2, or W3. T125 and the live-smoke repair T126 were the final
model-runtime blockers for the definitive current-profile matrix and are now
complete. T127 records the passed accessibility/user checkpoint and its E2E
regression; no G2.8 merge-chain task remains. T128 records the P4/P5 baseline;
T129 blocks T130, T131 and T132 are independently test-first, T130–T132 block
the P4 dry-run gate T133, and T133 blocks P5 tasks T134–T136. The accepted
US1/US3/US5 workbench foundation opens selected US7 without waiting for G2.10,
W2, W3, R4, or R5. For Dashboard Builder MVP, T137 blocks all product changes;
T138 and T139 are red-first and may proceed independently after T137; both block
T140. UI red tests in T141 may start after the T139 contract stabilizes, but UI
implementation requires T140. T140 and T141 block the real-path T142 gate; T142
blocks the documentation/user checkpoint T143. PR #43 MS-D and merge remain
evaluation release closeout and do not block T137.
