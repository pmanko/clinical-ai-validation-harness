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
- [ ] T094 Add and run diverse real-path validation for narrowing, aggregation/output-shape change, unresolved correction, lint-clean semantic reviewer correction, and Hub/tool failure; include dirty/unchanged bases, profile switching, stale results, New Session isolation, exact selected output, timed-out/cancelled diagnostic presentation, and record-level PostgreSQL cross-check fixtures/evidence
- [ ] T095 Rebuild the isolated sibling-Hub stack and complete G2.8c with Gemma 4 12B writing/Qwen 2.5 14B reviewing at temperature zero with the DRY repetition penalty disabled: run the T094 scenario families, inspect typed generation evidence and exact context/trace/model/effective-configuration provenance, conditionally report candidate/output digest differences when observed under that configuration, verify initial-question submit through successor-query visible in under 3 minutes after subtracting only the exact recorded durations of every initial/follow-up writer/reviewer invocation and reconcile those durations to their start/end timestamps and request/response-or-failure digests, report unadjusted wall time and explicit Run/database time separately, complete keyboard-only/narrow/200%-zoom checks, record reproducible SQL/parameters plus dataset/session/turn/query/version/execution IDs and inspected-record rationale, then pause for user acceptance
- [ ] T096 After G2.8c/T111 user acceptance, update the root `README.md`, Catalyst user docs/status, final quickstart, roadmap, and applicable PCCP evidence/rollback/residual-risk dispositions; documentation follows evidence and precedes ready-for-review/merge acceptance
- [X] T097 Commit/push the companion Hub and Catalyst changes, pin both sibling submodules in harness PR #37, rerun root pin/provenance checks, and update the PR without starting W2/W3. Published as drafts under explicit 2026-07-20 user direction; T094–T096 still block ready-for-review/merge acceptance

## Phase 4.12 — Corrective G2.9: unified workbench UX and queryable schema

- [X] T098 Measure the restored active-session scroll/focus flow, audit the exact execution-context boundary and live PostgreSQL/catalog surfaces, research primary database-assistant/schema-browser and WCAG patterns, record N55–N58 plus the one-composer/one-editor workbench-dock proposal and acceptance cases in `specs/008-catalyst-query-workbench/`, and pause for G2.9a user acceptance before product-code changes
- [ ] T099 [P] After G2.9a acceptance, add failing UI/Playwright tests for exactly one reusable Ask/Refine composer and one SQL editor, compact chronological history, adjacent editor actions, bounded results, truthful matching/stale/unexecuted grounding labels, responsive dock pin/collapse behavior, refresh restoration, keyboard focus, 390 × 844, 320 CSS px reflow, and 200% text
- [ ] T100 [P] After G2.9a acceptance, publish and register a truthful versioned editor/schema catalog containing the complete reviewed 16-column `analytics.lab_result_fact_v1`, view grain/descriptions, column types/nullability/descriptions/unit relationships, and actual read-only/advisory/max-row/timeout capabilities; add deterministic Gateway and live information-schema drift tests before UI integration
- [ ] T101 Implement one runtime-backed queryable-schema guide using the same catalog as model grounding/completion, keep record preview secondary, remove example prompts and synthetic/demo claims not backed by load metadata, and distinguish the supported fact view from broader database-role access
- [ ] T102 Implement the active-session workspace with the disabled initial form removed, compact artifact chronology, one canonical SQL editor, adjacent Format/Validate/Run actions, bounded Results/Validation/Evidence panes, and one responsive bottom dock expanding the existing editor or Ask/Refine composer without duplicating either input
- [ ] T103 Expose exact matching/stale/unexecuted execution-grounding state in the dock and generation evidence; if and only if G2.9a approves value-level context, first publish a bounded explicit result-attachment contract with digest/provenance and negative tests against silent or unrelated row sharing
- [ ] T104 Pass focused/full Gateway, Hub-if-contract-affected, UI, Playwright, schema-registry, accessibility, typecheck/build, live information-schema, and diff gates; demonstrate edit → stale results → Run → execution-grounded Refine plus schema discovery/refresh at G2.9c and pause for user acceptance
- [X] T105 Correct `patient_flat_v1.name_display` with a tested FHIRPath fallback; emit and render deterministic all-blank/NULL result-column feedback without hiding successful rows; forward only the bounded exact-digest warning to refinement context; and reproduce the original query through the isolated stack

## Phase 4.13 — PR merge-readiness audit

- [X] T106 Audit Hub #14, Catalyst #4, and harness #37 against their base branches, canonical specs, review threads, CI, local full suites, pinned dependency graph, clean-boot path, provenance, and squash behavior; record substantive findings even when GitHub reports green
- [X] T107 Resolve the Hub follow-up-prompt, parameter-normalization, analyte-detection, table/column lint, CTE-relation, metadata-redaction, timing-contract, and reviewer-decision findings with focused and full regression tests
- [X] T108 Resolve the Catalyst active-instruction, profile-binding, catalog-lineage, execution-idempotency, current-version provenance, stale expected-column, and complete iterative-browser-flow findings; add UI and analytics/assembly jobs to CI
- [X] T109 Make the tracked umbrella boot reproducible from a clean recommended environment: correct fake-mode/port propagation, enforce clean matching sibling pins, tolerate an empty successful OpenELIS backfill response, pin OpenELIS deployment source/images, and rerun the health/provenance gate
- [X] T110 Align `docs/specification.md`, `docs/roadmap.md`, `docs/med-agent-hub.md`, root README/quickstart, Harness provider/component/profile provenance, real-suite model IDs, and PR descriptions with the tested implementation
- [ ] T111 Rerun the complete Hub/Catalyst/harness automated gates plus the T094/T095 live iterative workflow on clean pins; prove the versioned Hub backend inventory, exact required model aliases, available-profile subset, unavailable initial/governed/follow-up rejection before state or model calls, writer-only and reviewed provenance, independent PostgreSQL evidence, and pause for user acceptance
- [ ] T112 After T111 acceptance, squash Hub first, repin/validate/squash Catalyst, repin both resulting `main` commits in the harness, obtain the required harness approval, and squash harness last

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

- [ ] T125 Bound every Catalyst query-profile writer/reviewer completion to an explicit output-token budget; prove the limit is sent to Hub/router and retained in invocation provenance; reset the external router after the pre-fix runaway request; rerun focused component gates and the complete clean-pin T094/T095/T111 matrix without treating a truncated or timed-out candidate as success

## Phase 4.19 — Current-profile collaboration evidence repair

- [ ] T126 Restore the comparative Gemma/Qwen profile's already-approved collaborative-review policy after the Gateway ownership move; give the reviewer the same current instruction and bounded revision context as the writer; on reviewer output-contract failure preserve and correctly label the exact malformed reviewer output and the contract-valid writer as unselected evidence while leaving the effective base current; add focused regressions and rerun the reviewed-profile smoke before the complete T094/T095/T111 matrix

## Phase 6 — W1 integrated validation

- [ ] T022 Add invalid-edit-run-refresh-rerun browser coverage in `targets/catalyst/catalyst-ui/e2e/workbench.spec.ts`
- [ ] T023 Add diverse real-path workbench smoke scenarios in `targets/catalyst/tests/e2e/test_mvp_live.sh`
- [ ] T024 Run gateway, UI, browser, and real-stack checks and record exact-query digest evidence in `specs/008-catalyst-query-workbench/roadmap.md`
- [ ] T055 Manually validate editor highlighting, line numbers, wrap default/toggle retention, keyword/catalog completion and no-catalog fallback, repeated deterministic Format, exact immutable Validate/Run versions, keyboard use, narrow layout, and 200% zoom; record mismatches and nondeterminism at G3 in `specs/008-catalyst-query-workbench/roadmap.md`
- [ ] T025 Update Catalyst user docs and actual status in `targets/catalyst/docs/roadmap.md`
- [ ] T026 Pin the verified Catalyst commit and update harness provenance in `targets/catalyst`
- [ ] T027 Present G3 evidence and unresolved N-items to the user before starting W2 in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 7 — User Story 2: targeted remediation (after G3)

- [ ] T028 [US2] Revalidate repair scope from W1 findings and pause at G4 in `specs/008-catalyst-query-workbench/roadmap.md`
- [ ] T029 [P] [US2] Add AST unit/frozen-digest/patch-integrity tests in `targets/catalyst/catalyst-gateway/tests/test_query_repairs.py`
- [ ] T030 [US2] Implement repair scopes and deterministic patching in `targets/catalyst/catalyst-gateway/src/catalyst/repairs.py`
- [ ] T031 [US2] Implement a user-initiated typed repair-proposal contract in Catalyst Gateway, limited to selected AST units and frozen digests; execute any model proposal role only through Hub's generic role endpoint, and do not reuse the internal G2.3 retry as an accept/decline workflow
- [ ] T032 [US2] Verify the Gateway-owned proposal contract and generic Hub runtime path through the pinned sibling `targets/med-agent-hub`, including the umbrella sibling build/pin and Catalyst's unmodified same-commit standalone fallback; do not add Catalyst query logic to Hub or restore the retired patch
- [ ] T033 [US2] Add before/after accept/decline repair UI in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx`
- [ ] T034 [US2] Run repair integrity/scenario metrics and pause at G5 in `specs/008-catalyst-query-workbench/roadmap.md`

## Phase 8 — Harness integration (after G5)

- [ ] T035 Add versioned workbench event/manifest contract tests in `tests/test_metadata.py`
- [ ] T036 Implement session artifact export/import in `harness/catalyst/validation.py`
- [ ] T037 Add one-click export in `targets/catalyst/catalyst-ui/src/features/query/QueryWorkspace.tsx` and validate W3 artifacts in `harness/catalyst/validation.py`
- [ ] T038 Present G6 provenance/model-identity/scenario evidence before comparative claims in `specs/008-catalyst-query-workbench/roadmap.md`

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
live T111 run; T111 blocks T112. T113
documents the post-G2.8 ownership refactor; T114 and T115 must land before T111
acceptance, with T115 applied in the owning component PRs. T116 is the written
G2.10a traceability gate. T117–T120 block the clean two-source run T121, which
blocks the G2.10c
user pause T122. G2.10 acceptance is separate from and does not silently close
T094/T095/T111, W2, or W3. T125 and the live-smoke repair T126 both block the
definitive current-profile T111 matrix.
