# Catalyst Query Workbench Roadmap

## W0 — Durable specification and research

**Status:** Complete; W1 approved 2026-07-17

QA decisions, UX research, execution boundary, persistence model, targeted patch
contract, test strategy, and staged harness integration are recorded here.

### G0 exit checklist

- [x] Generate dependency-ordered tasks with explicit test and user gates.
- [x] Run read-only cross-artifact consistency/coverage analysis.
- [x] Resolve all CRITICAL and HIGH findings.
- [x] Re-run the lightweight consistency checks after remediation.
- [x] Present the nondeterminism/inconsistency register and plan diff to the user.
- [x] Receive user approval to begin W1 product-code changes.

### G0 issue dispositions

- N1 open and non-blocking for manual behavior; record available sampling data.
- N2 confirmed: alias/model-file mismatch must be resolved before comparisons.
- N3 open and deferred until a Gemma router leg is explicitly prepared.
- N4 bounded in W1 by a normalized advisory finding representation.
- N5 open and assigned to exact-execution type contract tests.
- N6 deferred to W3 artifact-contract work.
- N7 assigned to the evidence-backed W1 documentation task.
- N8 user-decided: database role/read-only transaction is authoritative for this POC.

## W1 — Manual workbench MVP

**Status:** G2.1 passed — paused at the requested user checkpoint before the
full editable workbench UI slice

- Collapse detailed dataset context while retaining state.
- Persist sessions and immutable query versions in the gateway.
- Show full SQL, typed parameters, and validator findings together.
- Validate edits without resubmitting the natural-language question.
- Run the exact displayed draft regardless of findings.
- Return typed rows, empty/truncated states, or useful PostgreSQL diagnostics.
- Restore the active session after refresh.
- Cover the flow with gateway, UI, Playwright, and live-stack tests.

**Exit:** An evaluator can generate, edit, validate, run, inspect failure, revise,
and rerun across a refresh without losing lineage.

### W1 checkpoints

- **G1 internal:** persistence/API contract tests pass.
- **G2 user:** real-stack exact-query success and failure demonstrated; pause.
- **G2.1 corrective:** prove canonical Gemma identity and preview-free workbench
  generation through the real stack before any UI work.
- **G3 user:** integrated browser/manual acceptance and refresh retest; pause
  before W2.

### G1 evidence — PASS (2026-07-17)

- Added published, versioned request, session-response, and advisory-finding
  schemas; the registry now loads and validates 14 normative contracts.
- Store tests prove append-only query versions, validations, findings,
  executions, and events; stale-parent rejection; immutable-row triggers;
  additive migration of an existing preview database; and refresh restoration.
- Gateway route tests cover real Hub orchestration, rejected-candidate retention,
  exact-draft execution, database diagnostics, and stale-write conflicts.
- Gateway validation: `70 passed`; Ruff lint and format checks pass. The only
  warning is an upstream Starlette/httpx deprecation warning.

### G2 evidence — PASS; USER PAUSE (2026-07-17)

- Isolated stack health is ready at `http://localhost:13000` with gateway API at
  `http://127.0.0.1:18000`; the primary checkout remains untouched.
- Real Hub generation used profile `catalyst-query-checked` for session
  `8a9e8d3e-9e93-4151-bf3d-6fca75430caa`. The model router logs show actual
  inference, not a fixture response.
- Generated version `c48762e1-aa0c-4547-b93f-a882ba3caf3d` has digest
  `72b3c74614b79f5d8bed032da87a702bbb2a725003ca096a1caf1ec0dd10d9ff`.
  Its exact SQL and typed parameters were sent unchanged to PostgreSQL.
- Successful execution `54ab71b8-e4fd-4f1a-9039-91436f994fbd` returned 100
  rows with eight cursor-derived columns in 7 ms and explicitly reported
  `truncated=true`, reason `configured_limit`.
- A human-created invalid version `70a777ed-957d-44d9-abf6-37a303802b11`
  (`SELECT missing_column FROM analytics.not_a_view`) retained two advisory
  errors and still ran unchanged. Execution
  `11af634f-72c0-4588-ab54-f53b8a62f274` returned PostgreSQL SQLSTATE `42P01`,
  severity `ERROR`, message `relation "analytics.not_a_view" does not exist`,
  and position 28 in 12 ms.
- Focused gateway logs contain the session, both executions, and only expected
  2xx responses; no traceback or service error was emitted.

### G2 open issue disposition

- **N1 open:** real generation is proven, but repeatability/seed evidence is not.
- **N2 confirmed:** profile role alias `qwen2.5-coder-14b` resolves to the loaded
  file `Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf`; no comparative model claim is
  valid until the identity is corrected.
- **N3 open:** `catalyst-query-gemma-e4b` remains unavailable with
  `model_not_loaded:google/gemma-4-e4b`.
- **N4 bounded but visible:** the first Hub lint attempt warned and the second
  passed, yet aggregate generation history makes the workbench status `warning`.
  G3 should display generation-history warnings separately from current-draft
  deterministic findings.
- **N5 bounded:** cursor metadata drives result types; unrecognized PostgreSQL
  types deterministically fall back to `unknown`.
- **N6 deferred to W3. N7 remains assigned to T025. N8 is user-decided for this
  POC.**
- **N9 open:** generated SQL contained no `LIMIT`; the operational fetch bound
  correctly truncated without rewriting SQL, but the UI must explain that split.
- **N10 bounded technical debt:** generation currently leaves an unused governed
  preview record while preserving the workbench version independently.

The user reviewed G2 and approved the G2.1 correction on 2026-07-17.

### G2.1 evidence — PASS; USER CHECKPOINT (2026-07-17)

- The isolated Hub now targets a worktree-owned llama.cpp router at
  `host.docker.internal:18077`, separate from the two-day-old main-checkout
  router on `8077`. Profile `catalyst-query-gemma-e4b` is available; generation
  and review both use `gemma-e4b`.
- The router advertised the loaded model as 7,518,069,290 parameters,
  4,961,343,656 bytes, context 24,576, temperature 0, and seed 42. The host
  artifact resolves to Gemma 4 E4B IT Q4_K_M at Hugging Face snapshot
  `653803f092503c04a65164346f3208a36e707693`.
- Hub discovery now retains sanitized backend metadata, role knobs, the immutable
  profile-configuration digest, and per-role system-prompt digests. The gateway
  copies that exact evidence into both session and query-version provenance.
- The original generic request, “Show the 10 most recent laboratory results…,”
  exposed a deterministic catalog-preflight false positive before inference.
  The modifier parsing was fixed and regression-tested; counted/recent generic
  subjects now reach generation while unknown named analytes remain rejected.
- The same request then invoked two real `gemma-e4b` router completions
  (generation and independent review) and created session
  `c398ba8e-b154-4dae-9362-216b1291c44c`, trace
  `1f0b1751-5b86-4020-83ce-6e9438317a54`, version
  `df10de55-35f7-4bef-9957-2d5f9eb2de87`, and digest
  `7ecd980f141c91abafaaf476f13aa2314f9b5db189b1f99789fc74da98409d98`.
- Gemma produced a general all-tests query with no analyte predicate:
  `SELECT patient_id, test_name, result_value, result_unit, observed_at FROM
  analytics.lab_result_fact_v1 WHERE observed_at >= :date_1 ORDER BY
  observed_at DESC LIMIT 10`. Deterministic lint and Hub review passed.
- Exact execution `364fb466-6398-414f-a984-d9ba993c3b0b` sent that immutable
  SQL and its typed date parameter unchanged to read-only PostgreSQL. It returned
  10 cursor-typed rows in 8 ms and reported `query_limit_reached`.
- Governed preview count remained exactly `22 → 22`; session creation no longer
  leaves an unused preview. The existing governed endpoint still creates one
  preview in its regression test.
- Validation is green: Hub `307 passed`; gateway `84 passed` with Ruff
  lint/format; UI `35 passed` with ESLint/typecheck/build; router policy
  `25 passed`; MVP assembly `13 passed` plus 7 subtests.

### Profile catalog extension evidence

- The selector omits unavailable profiles rather than presenting disabled
  options. Each visible option is derived from the Hub profile label followed by
  its unique `roleModels` aliases; the UI has no model-name mapping of its own.
- The live catalog exposes four available profiles: checked Qwen 2.5 14B,
  Gemma 4 E4B, Gemma 4 12B, and Qwen 2.5 Coder 1.5B. The 12B profile uses exact
  alias `gemma-4-12b` for both roles; the bundled profile uses exact alias
  `qwen2.5-coder-1.5b-instruct-q4_k_m` for both roles.
- All four profiles completed real generation and review against the isolated
  router. Sessions were `e89d46a1-e86d-4f23-9539-5fc3416a8ab7` (Qwen 14B),
  `cde4ad38-9a62-4e3c-9090-ccde44d65955` (E4B),
  `ed39b0fd-a00b-4285-bb51-0868db00dcd0` (12B), and
  `4f76bfca-5a28-4321-9bf6-a8923b9911ee` (Qwen Coder 1.5B). Every current
  version passed Hub validation and deterministic gateway validation.
- The two newly enabled drafts executed unchanged against read-only PostgreSQL:
  Qwen Coder execution `1f89476d-2113-4a85-b658-5464244d4826` and Gemma 12B
  execution `eaed3ba0-0e5c-4730-8e49-8293ea19d2c6` each returned 10 typed rows.
- Post-run router discovery reports all four exact aliases loaded with no pending
  download. Governed preview count remains `22`; the four workbench generations
  and two exact executions created no preview records.

### Annotation-driven UX evidence

- “Know what to ask” and general live OpenELIS-to-FHIR framing replace the
  synthetic-cohort copy. The overview and record rows come from the connected
  analytics projection; runtime classification is reported as unknown rather
  than inferred.
- Prompt examples and the duplicate static distribution table are gone. One
  compact Carbon disclosure now owns live filters, rows, pagination, empty/error
  states, and retains filter/row state across collapse/reopen.
- “Ask OpenELIS” is input-first: question, Hub profile, and submit action share
  one composer. A single canonical textarea remains in the DOM.
- A small up/down jump action lives in the existing sticky demo banner only while
  the composer is offscreen. It transfers focus to the real textarea, remains
  mounted while focused, respects reduced motion, and re-enables the composer in
  terminal result/error states while preview/polling remain locked.
- In-app verification passed at the default viewport and at 390 px (mobile/
  200%-zoom equivalent): no horizontal page overflow, no jump/pagination
  collision, retained live Glucose filtering after disclosure toggles, correct
  focus transfer, selected Gemma profile, and no console warnings/errors. A
  second live DOM check confirmed exactly four available picker options, each
  with its Hub label and role-model alias, and no unavailable option.

The annotation-driven shell was completed during G2.1 because the user added it
to the approved checkpoint. This is not the full manual workbench UI: SQL and
typed-parameter editing, version history, exact Run controls, and refresh restore
(T008, T011–T013, T017, T021–T027) remain the next large slice. Work pauses here
for the requested user check-in before that slice.

### G2.1 issue disposition

- **N1 bounded/open for experiments:** temperature 0 and seed 42 are now
  recorded, but one run is not repeatability evidence; comparisons need repeats.
- **N2 resolved:** Gemma and bundled Qwen aliases are truthful and router model
  metadata is retained.
- **N3 resolved:** the canonical Gemma profile is live and both roles use it.
- **N4 bounded:** current and historical findings are separated and normalized;
  Hub and gateway validators intentionally remain distinct.
- **N5 resolved for W1:** execution types come from PostgreSQL cursor metadata.
- **N6 deferred to W3. N7 remains assigned to T025. N8 remains user-decided.**
- **N9 still open for UI/artifacts:** exact SQL limits and operational fetch
  truncation need distinct presentation.
- **N10 resolved:** live and deterministic tests prove preview-free workbench
  generation.
- **N11 open:** pipeline run ID/live counts are not a content digest or reviewed
  data-classification manifest.
- **N12 open:** concurrent duplicate Run requests need an atomic idempotency
  claim before parallel experiment runners.
- **N13 open:** validator digest does not yet identify the complete parser,
  catalog, policy, and implementation configuration.

## W2 — Targeted remediation

**Status:** Planned

- Normalize current lint output into stable findings.
- Derive AST repair units and freeze unaffected-unit digests.
- Apply deterministic substitutions where unambiguous.
- Add a med-agent-hub stage that returns only typed patch operations.
- Show before/after units and require explicit acceptance.
- Reject stale, full-replacement, or out-of-scope proposals.

**Exit:** Seeded single-finding scenarios change only permitted units in at
least 90% of cases and every accepted repair passes full revalidation.

### W2 checkpoints

- **G4 user:** revalidate the plan from W1 evidence before model patching.
- **G5 user:** review integrity metrics and decide W3 versus another W2 loop.

## W3 — Harness experiment integration

**Status:** Planned after W1

- Materialize a session as `run_manifest.json` and `events.jsonl`.
- Validate bundles against versioned contracts in the umbrella harness.
- Expand suites across malformed, syntax, binding, semantic, database,
  empty-result, warning, and success cases.
- Compare profiles/models with repetitions and retained record-level evidence.

**Exit:** A manual session can become a reproducible harness run without
re-entering its question, profile, drafts, findings, or outcomes.

### W3 checkpoint

- **G6 user:** review artifact validity, model identity, provenance, and scenario
  diversity before accepting comparative experiment claims.

## Open issue log

The canonical nondeterminism and inconsistency register is in `plan.md`.
Each gate report must mark every item as open, bounded, resolved, or user-decided
and link the evidence or decision. New issues receive the next stable `N#` ID;
they are never silently removed.

## W4 — Rich datasets and experiment iteration

**Status:** Planned

Add broader synthetic cohorts, question families, known-answer fixtures, and
model/profile matrices based on W1–W3 evidence. Agent-team experiments remain
deferred until single-profile behavior and repair telemetry identify a need.
