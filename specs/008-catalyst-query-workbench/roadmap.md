# Catalyst Query Workbench Roadmap

## Current architecture and PR topology (2026-07-29)

**Status:** Current implementation is in the active draft chain Harness
[#37](https://github.com/pmanko/clinical-ai-validation-harness/pull/37) →
Catalyst [#5](https://github.com/DIGI-UW/openelis-catalyst/pull/5) → Med-Agent Hub
[#15](https://github.com/pmanko/med-agent-hub/pull/15). Catalyst #4 and Hub #14
are closed, unmerged, and superseded; references to them below are historical
publication evidence only.

Catalyst Gateway now owns governed-query profiles, prompts, writer/reviewer
composition, deterministic lint/repair/finalization, and query evidence.
Med-Agent Hub exposes a generic `POST /v1/hub/generate` role executor and does
not own Catalyst query profiles or their orchestration. Hub's separate
clinical-answer/report profile engine is unchanged. The candidate umbrella pins
are Catalyst `95515a2` (active #5 head) and Hub `198d5f6` (active #15 head).
The 12/12 model/PostgreSQL matrix and bounded-failure recovery passed on
Catalyst parent `bb36126` with the current Hub pin. Catalyst `95515a2` changes
only the standalone fallback Hub SHA from `946afa9` to `198d5f6`; the umbrella
runtime supplies the sibling Hub context and does not execute that fallback
clone path. Focused pin/layout coverage and a clean candidate-head real-model/
PostgreSQL smoke pass. Manual keyboard/zoom checks and explicit user acceptance
remain open, so no merge occurs before that pause.

The 2026-07-29 lightweight cross-artifact rerun found no unresolved
CRITICAL/HIGH inconsistency after aligning the exact component revisions,
optional reviewer language, runtime inventory ownership, unavailable-profile
negative paths, and the discovery/invocation race. Task and requirement IDs are
unique, and T123/T124 explicitly block T111. This written result does not replace
the clean-pin runtime evidence.

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

**Status:** G2.1–G2.7 passed; G2.8a accepted; historical G2.8b backend/runtime
and post-UI checkpoints passed; the current-pin G2.8c model/PostgreSQL matrix
and bounded-failure recovery pass. The Gateway-owned refactor still awaits the
live accessibility matrix and user acceptance before T094/T095/T111 close.
G2.9 remains at its written user checkpoint; G2.10 multi-source/lossless
acceptance is newly traced and open; G3 and W2 have not started.

- Collapse detailed dataset context while retaining state.
- Persist sessions and immutable query versions in the gateway.
- Show full SQL, typed parameters, and validator findings together.
- Preserve the best parsed draft and latest malformed raw generation response
  when structured-output retries fail.
- Provide PostgreSQL highlighting, line numbers, wrap control, catalog/keyword
  completion, deterministic Format, and immutable editor-version transitions.
- Validate edits without resubmitting the natural-language question.
- Run the exact displayed draft regardless of findings.
- Return typed rows, empty/truncated states, or useful PostgreSQL diagnostics.
- Restore the active session after refresh.
- Route one complete writer query through Gateway-owned deterministic lint.
  Writer-only profiles may finalize it; reviewed profiles give the complete
  query and findings to their declared reviewer, with the comparative profile
  using a different model family, then deterministically lint any correction.
- Persist and display both model-authored query versions and their role/model/
  finding trace when the reviewer changes the query.
- Retain one linear sequence of natural-language turns inside a workbench
  session. Ground every follow-up in the exact visible editor snapshot and
  produce a complete successor query without replaying a raw chat transcript.
- Keep prior turns compact and read-only, attach validation/execution evidence
  to exact versions, label stale results, and restore the complete timeline.
- Cover the flow with gateway, UI, Playwright, and live-stack tests.

**Exit:** An evaluator can generate, edit, validate, run, inspect failure, revise,
and rerun across a refresh without losing lineage.

### W1 checkpoints

- **G1 internal:** persistence/API contract tests pass.
- **G2 user:** real-stack exact-query success and failure demonstrated; pause.
- **G2.1 corrective:** prove canonical Gemma identity and preview-free workbench
  generation through the real stack before any UI work.
- **G2.2 internal:** resolve the reproduced unnamed-parameter contract boundary,
  prove failed drafts/raw output remain inspectable, and land failing SQL-editor
  acceptance tests before editor implementation.
- **G2.3 corrective internal:** replace the observed whole-candidate retry with
  strict localized patch operations and repeat the same E4B/12B real-stack case.
- **G2.4 corrective internal:** hydrate one structurally parseable raw JSON
  response into a separately labelled unresolved editor seed without changing
  the retained raw evidence or creating a model query version. Prove blank
  missing names, refresh restoration, immutable-version precedence, and
  evidence-only handling for malformed/prose output before closing G3.
- **G2.5 corrective internal:** relax only the model-facing generation schema so
  `name` and `source` may be omitted. Pair unnamed parameter values with SQL
  placeholders in their existing order, without an LLM retry whose only purpose
  is adding names. If counts do not line up, retain the editable draft. Repeat
  the real 12B query through execution before closing G3.
- **G2.6 corrective internal:** replace generator self-patching with one complete
  writer candidate, deterministic findings, one complete correction from a
  different reviewer-model family, and deterministic re-lint. Persist the writer
  and reviewer queries as linked immutable versions and expose their model/stage
  evidence before closing G3.
- **G2.7 corrective internal:** add separate New session and Clear draft controls
  while preserving retained server evidence and selected profile.
- **G2.8a user (historical, accepted):** write and cross-check the
  iterative-notebook research, requirements, turn/context contracts, task order,
  then-current sibling-Hub ownership, and issue register; pause before product
  code.
- **G2.8b internal (historical architecture):** prove the revision/turn
  contracts, exact snapshot and
  lineage rules, atomic concurrent claim/orphan recovery, bounded context and
  exclusions, shared follow-up/Validate/Run resolution, recorded/legacy initial
  evidence, typed evidence detail and schema registries, terminal execution
  diagnostics, explicit lint instruction, semantic reviewer correction,
  selected output, sibling-Hub runtime source, and event-envelope compatibility
  before UI implementation.
- **G2.8c user:** prove the full initial → manual edit → Validate/Run →
  follow-up → successor Run → refresh path across the required scenario matrix
  through real Gemma 4 12B/Qwen 2.5 14B inference and PostgreSQL; include
  record-level rationale, initial-submit-to-successor-visible adjusted timing,
  wall/Run secondary timing, and complete keyboard/narrow/200%-zoom evidence;
  pause before G3/W2/W3.
- **G2.9a user:** review the measured UX/catalog audit, one-composer/one-editor
  workbench-dock architecture, supported-versus-database-accessible schema
  boundary, execution-summary disclosure, responsive rules, and acceptance
  cases; pause before product-code changes.
- **G2.9b internal:** publish the truthful catalog contract and physical-view
  drift tests, then implement the single active-session workspace, bounded
  result area, compact chronology, adjacent editor actions, bottom dock, and
  grounding labels; pass UI/Gateway/contract/accessibility checks.
- **G2.9c user:** demonstrate edit → stale results → Run → execution-grounded
  Refine through the isolated browser, plus exact 16-column schema discovery,
  refresh, keyboard, narrow, and 200%-text behavior; pause before resuming the
  broader G2.8c model matrix or final documentation/pinning.
- **G2.9d corrective internal:** replace the optional-only Patient display-name
  projection with an explicit-text-then-given/family fallback; distinguish zero
  rows from rows whose projected columns are entirely blank/NULL; retain the
  successful table with actionable feedback; and include only that bounded,
  exact-digest diagnostic in follow-up context. Re-run the reproduced viral-load
  patient query against PostgreSQL and the isolated browser.

### G2.9d evidence — PASS (2026-07-19)

- The defect was projection loss, not an empty source cohort: all 96 Patient
  resources carried structured `given`/`family` names while the original
  `name_display` expression read only optional `HumanName.text`. The repaired
  FHIRPath preserves explicit text and otherwise composes the available given
  and family values; focused tests cover full, text-only, and one-sided names.
- A full Data Pipes refresh materialized 96/96 populated display names. Direct
  PostgreSQL reproduction of the reported query returned 191 qualifying lab
  result rows across 72 distinct patients and zero blank display names.
- The isolated browser retained the historical successful run as inspectable
  evidence, visibly labelled every blank string, and showed the deterministic
  all-blank-column warning. Re-running the unchanged query produced Run 2 with
  100 named rows, normal configured-limit truncation, and no blank warning.
- Gateway results now carry non-blocking warnings, legacy stored results derive
  the same warning on hydration, and only the bounded warning for an exact base
  digest enters follow-up context; result values remain excluded. Zero-row
  results receive separate filter/join guidance.
- Validation passed: 124 Gateway tests, 365 Hub tests, 105 UI tests plus UI
  typecheck/lint/production build, 26 analytics tests, contract-copy equality,
  diff checks, and the live isolated MVP health/provenance gate using Gemma 4
  12B as writer and Qwen 2.5 14B as reviewer.
- **G3 user:** integrated browser/manual acceptance and refresh retest; pause
  before W2.

### G1 evidence — PASS (2026-07-17)

- Added published, versioned request, session-response, and advisory-finding
  schemas; the registry now loads and validates 15 normative contracts.
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
to the approved checkpoint. SQL and typed-parameter editing, version history,
exact Run controls, retained failed-generation evidence, and refresh restore are
now integrated and manually proven. Dataset-browser session persistence plus the
browser/live-smoke/documentation/pinning/user-gate tasks T021–T027 remain before
W1 closure.

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

### G2.2 pre-implementation evidence — PASS (2026-07-17)

- The question “how many patients had viral load tests above 1000 count/ml?”
  reached real query generation in two profiles and exposed the same structured-
  output failure. Gemma E4B failed attempts 2–3 at 02:56 UTC and Gemma 4 12B
  failed attempts 1–3 at 02:58 UTC, each at
  `parameters.1: 'name' is required`.
- E4B evidence is session `2bed91de-fa7d-4ffa-b4ae-0a454a883930`, Hub trace
  `07740499-387c-40b4-97c3-2bf7c4e08b7e`. The workbench preserved editable
  version `d801dc1d-fc94-435b-bee6-2b45c3173af1` from schema-valid attempt 1,
  including SQL literals and an advisory unbound-literal finding. Best-draft
  retention is proven.
- The missing field belongs to the second query-generation parameter object. It
  is not the Hub profile name and not a query-review field. Every executor-bound
  parameter requires a name matching its SQL `:placeholder`.
- **N14 resolved at the reproduced boundary:** the shared Hub normalizer handles
  analytes, dates, and turnaround thresholds but not a sole remaining question-
  grounded unnamed parameter and sole remaining placeholder. The approved fix
  is limited to that deterministic 1:1 join. Ambiguous or ungrounded cases remain
  invalid findings; `name` stays required. The focused red run failed three tests
  for the intended reasons; the new five-test boundary, 63 focused Hub tests,
  the full 312-test Hub suite, and the same 63 tests after applying the durable
  patch to a fresh clone now pass.
- **N15 resolved through the UI:** Hub diagnostics previously chose a parsed candidate OR `rawOutput`.
  Because attempt 1 yielded a candidate, malformed raw responses from attempts
  2–3 were not preserved. The response now retains both independently, with the
  ordered per-attempt findings and existing profile/model/prompt/schema/config
  provenance; the live UI displays both simultaneously with attempt and
  provenance evidence.
- **N16 open, non-blocking:** the question says `count/ml`, while the catalog and
  live records use `copies/ml`; the retained candidate copied the ungrounded unit
  literal and current validators did not flag it. Add a catalog-grounded unit
  warning in the next validation iteration without rewriting the question or
  gating manual Run.
- **N17 open, non-blocking for the reproduced no-date case:** the older
  single-date normalizer still assumes that a sole placeholder in a one-date
  question is the date placeholder. A malformed response containing one numeric
  placeholder plus one date mentioned only in the question could therefore be
  misbound before the new conservative 1:1 normalization runs. Add a focused red
  regression at the next validation iteration before changing that older helper.
- Direct CodeMirror 6 with `@codemirror/lang-sql` and `sql-formatter` is selected
  for PostgreSQL parsing/completion, line numbers, wrapping, and deterministic
  manual Format. Monaco's worker/provider overhead and unsupported mobile-browser
  target do not fit this focused workbench.
- Cross-artifact analysis found one implementation gap: the UI had no typed path
  to the gateway's approved catalog. The roadmap now requires a read-only
  `catalyst.workbench.editor-catalog.v1` route sourced from that same catalog;
  catalog failure removes identifier suggestions only and never blocks editing.
- The catalog contract/route red run failed for the intended missing-contract and
  404 reasons. Its focused four tests, 77 affected gateway tests, full 86-test
  gateway suite, Ruff checks, and deterministic repeated-response checks pass.
- The SQL editor red run failed because the component did not yet exist. Direct
  CodeMirror integration now passes six focused tests and the then-current 45 UI
  tests plus lint, typecheck, and production build. App-level immutable-version,
  invalid-but-runnable, and evidence-display tests are recorded red before the
  QueryWorkspace integration.
- Reviewed dependency inputs are pinned in `package-lock.json`:
  `codemirror@6.0.2`, `@codemirror/lang-sql@6.10.0`,
  `@codemirror/state@6.7.1`, and `sql-formatter@15.8.2`.
- The workbench API contract was corrected to the implemented
  `catalyst.workbench.version.request.v1`; `authorType` is assigned by the
  gateway and is not accepted from the browser. No CRITICAL/HIGH consistency
  findings remain. G2.2 is closed and editor integration may proceed.

### G2.3 correction decision — PASS (2026-07-17)

- Live E4B session `24b27aca-c2f5-4977-8560-679448db2052` used
  `catalyst-query-gemma-e4b` / `gemma-e4b`. Attempt 1 produced a recoverable
  candidate; the conservative one-to-one normalizer supplied
  `threshold_value`. The candidate still had an unbound unit literal and an
  expected-column mismatch, so the current Hub requested another complete
  candidate. Attempts 2–3 regressed by omitting parameter names.
- The evaluator changed the threshold type from `string` to `number`, bound the
  catalog's `copies/ml` unit, validated immutable version
  `10f8b6b3-ebac-4816-83f2-5c7d79144cab` with no findings, and ran immutable
  version `80622451-b67d-4a34-abc3-e8a89bb69c31`; PostgreSQL returned one typed
  row with `patient_count=72` in 10 ms. Refresh restored the exact session.
- The same session then proved findings are advisory: invalid version
  `95228981-0880-446c-9445-04589bc202c0` retained
  `gateway_sql_policy.unbound_literal` yet executed unchanged and returned the
  same `patient_count=72` in 9 ms.
- Live 12B session `708a11bc-bf1e-448d-bee8-6fe63ab090b7` used
  `catalyst-query-gemma-4-12b` / `gemma-4-12b`. All three responses omitted
  required parameter names; the latest raw response also referenced
  unapproved `analytics.lab_test_fact_v1`. Raw output and ordered failures
  remained visible, but no unambiguous model version could be recovered.
- **Approved correction:** after a response is structurally parseable, the Hub
  asks only for typed operations on finding-derived JSON Pointer paths. SQL
  changes use an exact old fragment that must occur once; unaffected candidate
  fields are frozen. Full replacements, duplicate/out-of-scope paths,
  ambiguous text patches, and frozen-field mutations are rejected. The rebuilt
  candidate is fully revalidated after every patch; exhaustion still returns
  the best editable candidate and latest raw response.
- The G2.3 red run added seven focused cases for anchored SQL text replacement,
  exact parameter-name leaves, frozen valid parameters, ambiguous text,
  duplicate/overlapping paths, target metadata, and full-candidate retries.
  All seven failed against the old whole-object loop for the intended reasons
  (`7 failed, 53 deselected`) before production changes.
- The green implementation adds strict private patch schemas, finding-derived
  paths, exact SQL-fragment anchoring, JSON Pointer leaf application, frozen
  unaffected fields, conservative single-name recovery, and full reconstructed
  candidate validation. It reuses the existing question-grounded 1:1 name
  normalizer after patch application; multiple or ambiguous missing names remain
  unresolved. Fourteen parametrized retry/name cases across 11 test functions
  and the full 323-test Hub suite pass.
- Post-fix E4B session `11c585d8-c8ab-4fa6-a421-d6435b81845d` used profile
  `catalyst-query-gemma-e4b` and physical model `gemma-e4b`. The Hub retained the
  unit patch, then localized the last retry to the remaining threshold/column
  findings. Workbench version `ff6f4fcd-6a6e-48c9-9dd3-9a694861a674` passed the
  gateway validator; immutable execution version
  `d2928614-02ec-4529-9ef9-c99b549bf904` returned one row (`count=0`) in 7 ms.
  Zero is consistent with the model preserving the question's `count/mL` while
  the loaded records use `copies/ml`; it is evidence, not a correctness claim.
- The E4B run retained both its best parseable model candidate and the latest raw
  patch after exhausting its generation budget, with all three ordered attempt
  findings visible. This directly proves the post-fix best-plus-raw behavior.
- Post-fix 12B session `902bd844-e8f1-403d-90ee-8fccd9417f99` used profile
  `catalyst-query-gemma-4-12b` and physical model `gemma-4-12b`. Attempts 1–3
  omitted multiple parameter names at indices 1, 0, and 1. The Hub correctly did
  not guess among ambiguous bindings; the latest raw response, exact failure
  paths, and 12B provenance remain visible for manual work. Refresh restored both
  the 12B session and 12B picker selection.
- Router `18077` identified the loaded E4B file as
  `gemma-4-E4B-it-Q4_K_M.gguf` (7,518,069,290 parameters; 5,335,289,664 bytes on
  disk; SHA-256 `3f72a20a06f626c78e6c475ae07a64c88b2663149c0f6197b56bf7cf1f37585c`)
  and the loaded 12B file as `gemma-4-12b.gguf` (11,907,350,576 parameters;
  12,669,646,240 bytes on disk; SHA-256
  `e38d4060b562a1772cb4367ff6677a46d641763d0069f5024ae5b62d172fb535`).
  Both runs used context 24,576, temperature 0, and seed 42.
- This is a narrow generation-loop integrity correction in W1, not the broader
  user-reviewed remediation workflow planned for W2.

### G3 observed issues added during integrated manual testing

- **N18 open, non-blocking:** the production UI build succeeds but reports a
  roughly 1.06 MB JavaScript bundle (324.9 KB gzip), above Vite's 500 KB warning
  threshold. Evaluate code splitting before production.
- **N19 open, manually correctable:** E4B emitted numeric threshold `1000` as a
  string. The editor change to `number` validated and executed; add a grounded
  type warning in the next validation iteration rather than silently coercing.
- **N20 resolved at G2.3:** once a parseable base exists, retries now accept only
  finding-scoped patches and preserve unaffected fields. E4B live evidence shows
  the unit patch surviving later threshold/column correction; full-candidate and
  ambiguous repairs remain rejected.
- **N21 open, manually inspectable:** Hub candidate validation and gateway SQL
  validation cover different contracts. The final E4B draft still had a Hub
  `expectedColumns` projection finding while the same SQL/parameters passed the
  gateway validator and executed. Keep both statuses visible; align or label the
  scopes before comparative harness scoring.
- **N22 open provenance variance:** the earlier G2.1 record captured an E4B
  router-reported size of 4,961,343,656 bytes, while the post-G2.3 loaded file is
  5,335,289,664 bytes on disk and has the SHA-256 above. The post-G2.3 comparison
  is now physically pinned, but do not combine earlier and current E4B sessions
  as one model revision until the deployment-cache history is reconciled.
- **N23 resolved at G2.4:** session `902bd844-e8f1-403d-90ee-8fccd9417f99`
  preserves a syntactically valid raw JSON object, but the editor was empty
  because the Hub correctly withheld a contract-invalid candidate and the UI
  initializes only from an immutable current version. The correction must not
  promote raw output to a model version or guess multiple parameter names. It
  will derive an explicitly unresolved manual seed from the persisted raw
  evidence, leaving missing names blank and the original raw string unchanged.

### G2.4 unresolved raw-draft hydration — PASS (2026-07-17)

- The gateway now derives an optional `draftSeed` from persisted raw evidence
  only when no immutable current version exists. It accepts one exact JSON
  object with a non-empty SQL string and representable typed parameters; invalid
  JSON, arrays, fenced output, missing values, and unsupported types remain
  evidence-only. No workbench database migration or Hub behavior change was
  introduced.
- The seed is explicitly `status: unresolved` and
  `source: raw_model_output`. Missing or invalid parameter names remain blank;
  missing parameter source is represented as `human` for the future manual
  version and its original path remains listed in `unresolvedPaths`. No
  placeholder-order inference or SQL correction occurs.
- The original raw string remains unchanged under
  `provenance.generationRawOutput` and the generation outcome. Once a human
  creates an immutable version, the response suppresses the seed and the
  immutable current version is authoritative.
- Gateway red tests failed on the absent response field before implementation.
  Focused green coverage is `3 passed`; the full gateway suite is `89 passed`
  with Ruff lint/format clean. UI tests cover create, refresh, editable blank
  names/typed values, parentless manual persistence, raw evidence, and current-
  version precedence; the full suite is `63 passed` with ESLint, typecheck, and
  production build green. The existing N18 chunk-size warning remains.
- The gateway and UI were rebuilt without restarting the Hub or model router.
  A read-only GET of retained 12B session
  `902bd844-e8f1-403d-90ee-8fccd9417f99` returned no current version, the exact
  persisted raw response, and an unresolved seed containing its original SQL,
  `Viral Load` string value, `1000` integer value, and two blank names. Browser
  refresh restored the same editor buffer and selected Gemma 4 12B profile;
  the warning, raw evidence, and all three attempt failures remained visible,
  while Validate and Run were enabled. No new model call or session mutation was
  made, and the page was left open for evaluator edits.

### G2.5 decision — APPROVED FOR IMPLEMENTATION (2026-07-17)

- The repeated missing-`name` failures are an output-shape problem, not useful
  evidence about whether the SQL targets the right data. Rejecting before SQL
  lint hides material problems such as the 12B response's misspelled analytics
  view and prevents the deterministic/patch loop from addressing them.
- The model-facing generation parameter shape will require only `type` and
  `value`; `name` and `source` remain preferred, especially for longer queries.
  The final `catalyst.query.v1` parameter contract remains unchanged and still
  requires `name`, `type`, `source`, and `value` before review or execution.
- When a generated parameter omits a name, pair it with the SQL placeholder at
  the same position and default a missing source to `question`. This is plumbing
  for the current named-parameter executor, not an additional semantic policy.
  Do not use an LLM retry solely to add names.
- If the placeholder and parameter counts do not line up, retain the unresolved
  draft for editing rather than inventing or dropping bindings. Normal final
  schema and SQL/catalog validation still run after successful pairing.
- **N24 open at G2.5:** relaxing only generation may expose later SQL/catalog,
  type, unit, or projection failures that the old contract error masked. Those
  downstream findings are desired evidence and must not be misreported as a
  binding-normalization regression. The real 12B rerun must distinguish SQL
  validity, execution success, and result correctness rather than equating any
  one of them.

### G2.5 evidence — PASS; exposed orchestration defect (2026-07-17)

- Real session `1422a1d8-19b2-4c0a-8b9d-4d24a5ec87a2`, Hub trace
  `7f6c8a23-d168-4243-bcbf-0d6bb0de45b7`, used the physically loaded
  `gemma-4-12b` model. Its two unnamed values were paired with `:test_name` and
  `:threshold` without a name-only model call.
- Deterministic lint then reached the material issue
  `output.projection_mismatch`: `COUNT(DISTINCT patient_id)` lacked the declared
  `AS count` alias. This proves optional generated names no longer mask SQL
  findings.
- Attempts 2–3 sent patch-only corrections back to the same Gemma writer. Both
  patches referenced SQL not present in the retained candidate and were rejected
  as `generation.patch_ambiguous`. The gateway retained the complete writer query
  as version `3fa95d41-fcd2-47cd-8972-a5a7e3776a57`; its narrower validator
  reported valid. This is the input evidence for G2.6, not a binding regression.

### G2.6 decision — APPROVED FOR IMPLEMENTATION (2026-07-17)

- The writer produces exactly one complete candidate. Deterministic lint records
  specific findings but does not ask the writer to patch itself.
- A reviewer from a different model family receives the original question,
  catalog, complete writer candidate, and deterministic findings. For the 12B
  MVP profile, `gemma-4-12b` writes and `qwen2.5-14b` reviews/corrects.
- When findings exist, the reviewer returns one complete corrected candidate,
  not text/JSON-pointer patches. The Hub validates its strict contract and reruns
  all deterministic lint. A remaining finding rejects the collaboration result;
  lint-clean output proceeds to finalization without asking the reviewer to
  approve its own correction in a second model call.
- The Hub result and trace retain writer candidate/findings and reviewer
  candidate/decision/checks. The gateway persists the writer as `model` and the
  corrected query as a child `model_repair` version. The workbench displays both
  SQL/parameter sets with role and model provenance.
- **N25 resolved at G2.6:** the collaborative profile performs one writer call;
  `_generate` returns the complete parsed candidate and its findings directly to
  the reviewer rather than invoking writer self-patches.
- **N26 resolved at G2.6:** the advertised and traced roles use physically loaded
  `gemma-4-12b` and `qwen2.5-14b` aliases with different architectures and model
  files.

### G2.6 evidence — PASS; two follow-up inconsistencies recorded (2026-07-18)

- The first post-implementation live session
  `364d5dbb-9172-4fb4-85d8-142c06261a26` correctly routed Gemma to Qwen, but
  Qwen repeated the same two unnamed parameter objects twice. Strict validation
  rejected that response before a reviewer version was created. The structured
  boundary now drops exact duplicate objects only when the deduplicated count
  exactly equals the SQL placeholder count, then performs the existing ordered
  name pairing. It does not infer values, predicates, or SQL meaning. Hub tests
  cover that observed shape and all 327 Hub tests pass.
- Successful API session `39f71423-1a3b-4dde-9996-943c6985ddd6`, Hub trace
  `86b6f495-45b4-4afd-a9ef-71240ce5e820`, used one physically loaded
  `gemma-4-12b` writer call and one physically loaded `qwen2.5-14b` reviewer
  call. The advertised profile configuration digest was
  `sha256:a73b62aa2a470dd93cb8d997b84ec07792c142ba03e9de61516449e5846cce65`;
  router metadata reported 11,907,350,576 and 14,770,033,664 parameters,
  respectively, with temperature 0 and seed 42.
- Gemma writer version `b625a2ba-aec6-4a50-9757-d5303807563e` (digest
  `7e75a31233aeee5076df9c2b812318bef040c59a6cdc0692863c2542292bdd75`)
  produced `COUNT(DISTINCT patient_id)` without an alias. Deterministic lint sent
  `output.projection_mismatch` plus the complete candidate to Qwen. Reviewer
  version `12b07a96-a800-4d9c-8135-ff52a13ff2b5` (digest
  `b7b3db7e51cf4f06a24c8e21b367d181ba922ba9f39ec811d8c20a1e21e0d3c4`)
  returned the complete query with `AS count`; deterministic re-lint was clean.
  Refresh restored both linked versions, models, roles, current version, and the
  execution without another model call.
- Exact gateway execution `f5ccb870-f90d-4b1f-9f08-4c347b6ec703` succeeded in
  8 ms and returned one typed integer row with `count = 72`. An independent
  direct PostgreSQL count over the same view and predicates also returned 72.
  SQL syntax, execution, and the selected database rows are therefore proven;
  N24 remains open because the question said `count/ml` while the catalog unit is
  `copies/ml`, and the current semantic layer does not explicitly normalize or
  reject that unit wording.
- The browser-created session `50ef0f16-1e7b-4a9a-b362-17bf6bf3335d` visibly
  showed both complete SQL/parameter artifacts, Gemma's finding, Qwen's decision
  and checks, linked model roles, valid status, and a successful `count = 72`
  table. It was left open for manual evaluation.
- **N27 open after G2.6 (non-blocking):** clicking Run in the UI appended an
  ordinal-3 `human` version with the same digest as the current reviewer version
  even though the editor content was unchanged. Direct execution of an existing
  version does not do this. Decide at G3 whether unchanged runs should reuse the
  current immutable version instead of adding duplicate lineage.
- **N28 open after G2.6 (non-blocking nondeterminism):** two temperature-zero,
  seed-42 runs produced identical writer/reviewer SQL, parameters, and result 72,
  but differed on `expectedColumns[0].nullable` (`false` versus `true`), yielding
  different query digests. Model and/or GPU inference remains nondeterministic;
  comparisons must retain full candidates and digests rather than assuming the
  configured seed makes runs byte-identical.

### G2.7 manual reset controls — PASS (2026-07-18)

- Add an unobtrusive **New session** action to the active workbench. It clears
  the browser's active-session pointer and all in-memory question, draft, and
  result state, but does not delete the retained server session or its evidence.
  The selected available model profile remains selected and focus returns to
  the Ask OpenELIS question input for the next experiment.
- Add a separate **Clear draft** action for resetting only the editable SQL and
  parameters inside the current session. The question, immutable versions,
  model evidence, validations, executions, and provenance remain available.
- Do not add a delete-session API, confirmation workflow, or new persistence
  contract for this proof-of-concept control. Validate with focused UI tests,
  the full UI quality gates, and one live browser iteration.
- Focused integration tests prove both boundaries, and the full UI suite is 66
  passing tests with ESLint, typecheck, and production build green. The existing
  bundle-size warning remains unchanged.
- In the live browser, **Clear draft** emptied SQL and parameters and disabled
  Validate/Run while retaining session `2b34b590-94db-4dc4-a75e-73cb60db3fe2`,
  its two model versions, validation, writer/reviewer evidence, and provenance.
  **New session** then removed the workbench, cleared the question, retained the
  mixed Gemma/Qwen profile selection, and focused `catalyst-question`. A direct
  read afterward confirmed the detached server session remained active with two
  immutable versions.

### G2.8a iterative-query notebook — WRITTEN REMEDIATION; ACCEPTED (2026-07-18)

#### Current-state and model-context audit

- The gateway already persists the original question, selected profile,
  immutable query versions, validations, executions, and append-only events.
  Refresh restores the current stored version, but unsaved editor changes remain
  browser-local until Validate or Run.
- Every question submission currently creates a new unrelated workbench session.
  The Hub receives only that standalone question plus target/catalog/policy;
  current SQL, parameters, prior instructions, validation, execution feedback,
  and workbench history are absent. There is no follow-up endpoint.
- The Hub trace records generation/review evidence but is not model input for a
  subsequent request. Existing strict request validation intentionally permits
  one user message, so G2.8 adds typed revision context instead of overloading a
  chat array or concatenating SQL into the question.

#### Approved interaction and lineage

- A workbench session is one linear notebook. Turn 1 is the initial question;
  each later turn is a query-refinement instruction grounded in the exact active
  editor buffer. Unrelated work uses New session. There is no chat-only response,
  arbitrary-old-version branching, automatic execution, or result-row reference
  mode in this MVP.
- The current turn owns the editable SQL, parameters, validation, and results.
  Earlier turns collapse to read-only summaries and may be expanded for
  inspection without becoming the active base.
- The follow-up composer is labelled `Refine Query vN`, names the exact base and
  selected profile plus writer/reviewer models, and submits `Generate next
  query`. The existing sticky jump targets the initial composer when no session
  exists and the follow-up composer while a session is active.
- A changed contract-valid editor buffer becomes one immutable human version
  before generation. Identical content reuses the current version, resolving
  N27. An unresolved buffer is retained byte-for-byte in the requested-turn
  event and used as revision context without being promoted to a valid
  QueryVersion. The request separately records the client's observed CAS base,
  the exact snapshot, and the reconciled effective base: observed for unchanged,
  the new current human version for dirty-valid, and null for unresolved. Empty
  Clear-draft state exposes Restore Query and disables refinement until SQL is
  restored or entered.
- A failed turn retains raw/parsed model evidence and the exact input snapshot
  while leaving the base/current anchor current and editable: effective when
  non-null, otherwise observed when present, otherwise null. A contract-valid
  writer survives reviewer failure as an immutable but unselected output;
  invalid or merely parseable candidates remain diagnostic evidence. Successful
  output appends `effective base → writer → reviewer correction` as applicable.
  Results remain labelled by their executed Query version and become visibly
  stale after edits or successor generation.

#### Contracts and bounded model context

- Add `POST /v1/catalyst/workbench/sessions/{sessionId}/turns` and matching GET
  timeline projection. Requests carry the new instruction, per-turn profile,
  observed CAS base ID/digest, and exact editor snapshot/digest. The gateway
  atomically claims generation, checks the observation, and reconciles the
  effective base before recording the requested turn. It reuses the existing
  409 stale-query behavior and permits one in-flight turn per session.
- Fold `query_turn.requested|completed|failed` events into a versioned timeline;
  store `turnId` in version provenance rather than adding a parallel history
  table. New sessions record initial requested/terminal events and generation
  evidence. Only pre-event sessions synthesize Turn 1; deterministic fixtures
  cover model-current, later-human-current, draft-only, and raw-only evidence
  without changing the actual current pointer or mutating storage.
- One store-owned editor resolver classifies the same buffer for follow-up,
  Validate, and Run. Unchanged content reuses its version; dirty-valid content
  creates one current human version with active-turn provenance. Compact turns
  resolve typed provenance through
  `GET /sessions/{sessionId}/turns/{turnId}/generation-evidence`.
- Hub `catalyst.query.request.v2` carries the exact editor snapshot and
  observed/effective base evidence, initial question plus the five most recent
  follow-up instructions, and only
  validation/execution summaries whose query digest matches the exact editor
  snapshot. It never
  carries prior result rows, credentials, raw traces, or every historical SQL
  copy. Truncation and supplied entity IDs/digests are recorded as provenance.
- The writer returns one complete successor candidate. Deterministic lint
  receives the effective instruction explicitly. The different-family reviewer
  may approve, reject, or return one complete correction even when initial lint
  is clean; every correction passes strict validation and deterministic re-lint.
- The Hub publishes/registers the v2 request/revision schemas; the gateway does
  the same for turn, snapshot, timeline, and generation-evidence contracts.
  Failed, timed-out, and cancelled execution contexts retain bounded sanitized
  diagnostics only when their query digest matches the editor snapshot.

#### Runtime ownership correction

- The harness pins Catalyst and med-agent-hub as siblings, but the current MVP
  runner delegates to Catalyst's disposable `.med-agent-hub` clone and 6,484-line
  patch. The harness sibling is therefore not the actual runtime source.
- G2.8 lands the existing query profile plus revision behavior in the real Hub
  sibling, pins that commit in the harness, and passes the sibling build context
  into Catalyst. Catalyst keeps only an unpatched clone-at-the-same-commit
  fallback for standalone development; it does not contain Hub as a submodule.

#### Checkpoint boundary

- G2.8a changes documentation/contracts only. Read-only Spec Kit analysis must
  find no unresolved CRITICAL/HIGH inconsistency before this checkpoint is
  presented to the user.
- No Hub, gateway, UI, runtime, submodule pin, or model-prompt implementation may
  begin until the user accepts this written checkpoint. G2.8b and G2.8c remain
  separately testable gates.

#### Cross-artifact analysis and remediation — FINAL RERUN CLEAN; HISTORICAL GATE ACCEPTED

The first G2.8 Spec Kit consistency/coverage pass found the following blocking
written-plan gaps. Documentation remediation is complete; no product code,
runtime wiring, prompt/profile change, or submodule pin was authorized.

- **CRITICAL — pre-change governance:** The plan promised PCCP-style tracking
  but did not require a record before changing the Hub prompt, profile, or
  collaboration pipeline. Remediation: establish
  `pccp/2026-07-18-iterative-query-notebook.md` now, make it a completed written
  prerequisite, and leave its implementation evidence pending.
- **HIGH — test-first ordering:** Hub, store/gateway, runtime, and UI work was
  grouped too coarsely for red tests to block its implementation. Remediation:
  split each red-test task from the implementing task and encode explicit
  dependencies through the deterministic, real-path, live, documentation, and
  pin gates.
- **HIGH — state/recovery coverage:** Concurrent claims, interrupted requested
  turns, selected-output/current-pointer agreement, dirty/unchanged/unresolved
  bases, and the complete prohibited-context negative set were not all assigned
  to blocking tests. Remediation: require atomic one-active-turn tests, terminal
  `generation_interrupted` recovery without retry, explicit observed CAS base →
  reconciled effective base → exact snapshot evidence, valid-but-unselected
  writer retention on reviewer failure, selected-output invariants, digest-bound
  context, deterministic truncation, and every negative before implementation.
- **HIGH — runtime ownership proof:** The sibling-Hub decision lacked a root
  failing runtime test and ordered the user-facing documentation together with
  pinning. Remediation: require the root harness test before runtime wiring,
  separately retire the Catalyst patch/fallback, update root `README.md` only
  after accepted live evidence, and make that update block both sibling pins.
- **HIGH — real-path evidence depth:** One happy-path follow-up did not satisfy
  diverse-scenario or record-level constitution requirements. Remediation: the
  live gate now covers narrowing, aggregation/output-shape change, unresolved
  correction, lint-clean semantic correction, and Hub/tool failure; it records
  reproducible PostgreSQL SQL, dataset/query/version IDs, inspected records and
  rationale, conditional temperature-zero digest differences when outputs
  differ, precisely adjusted initial-submit-to-successor timing, and keyboard/
  narrow/200%-zoom results.
- **HIGH — contract publication and evidence detail:** The Hub v2/revision and
  workbench turn/snapshot/evidence schemas were not assigned to their runtime
  registries, and the compact timeline lacked a typed detail route. Remediation:
  T081 owns Hub publication; T086 owns workbench publication plus the typed
  generation-evidence GET; the pre-UI backend gate detects drift.
- **HIGH — lineage resolver ownership:** Follow-up had exact snapshot rules, but
  unchanged/dirty Validate and Run could still diverge or lose active-turn
  provenance. Remediation: blocking store and route tests plus one shared
  resolver owned by T084/T086 cover all three actions.
- **HIGH — recorded versus legacy initial evidence:** New sessions and restored
  pre-event sessions were not sharply separated, and initial output selection
  could be confused with a later human current version. Remediation: new sessions
  record requested/terminal events; deterministic model-current, human-current,
  draft-only, and raw-only fixtures prove read-only legacy projection.
- **HIGH — gate/provenance completeness:** The former full gate occurred after
  UI work, timed-out/cancelled diagnostics were not assigned, and new events had
  no compatibility assertion. Remediation: T092 is now a pre-UI Hub/backend/
  store/root contract gate with schema registries, all terminal diagnostics, and
  lightweight `events.jsonl` mapping; T093 is the separate post-UI full gate.

The final read-only Spec Kit consistency, constitution, and coverage reruns are
**clean**:

- **0 unresolved CRITICAL and 0 unresolved HIGH findings**;
- **34/34** scoped G2.8 requirements have concrete test, implementation, and
  evidence owners;
- **16/16** iterative-notebook acceptance scenarios have assigned coverage;
- all **9/9** feature JSON Schemas parse, pass Draft 2020-12 meta-validation,
  and resolve their registered references; and
- `git diff --check`, schema examples, task-ID uniqueness, and the documentation-
  only scope check pass.

The last blockers resolved before this clean rerun were typed per-invocation
model timing, explicit omissions for unavailable legacy provenance, an offline-
resolvable Hub schema dependency bundle, removal of stale Validate/Run and
conditional-review guidance, and retargeting deferred W2 work away from the
retired Catalyst-owned Hub patch.

G2.8a was accepted by the user before product implementation began.

### G2.8b backend/runtime gate — PASS (2026-07-18)

- The real sibling Hub passes its complete suite (`356 passed`), including the
  offline v1/v2 contract bundle, exact revision context, Gemma 4 12B writer and
  Qwen 2.5 14B reviewer roles, complete-candidate review, deterministic re-lint,
  selected/unselected output invariants, and per-invocation timing/digests.
- The Gateway passes its complete suite (`106 passed`) and focused notebook/
  route matrix (`35 passed`). Atomic turn claims, dirty/unchanged/unresolved
  editor resolution, four deterministic legacy projections, orphan recovery,
  exact-digest context, failure evidence, refresh, and no-auto-Run behavior are
  covered. Ruff and diff checks pass.
- Umbrella runtime/event checks pass (`4 passed`) and Catalyst sibling-Hub
  assembly checks pass (`14 passed`). Recorded initial/follow-up turn, snapshot,
  and generation-evidence events map losslessly into the existing versioned
  `events.jsonl` envelope without implementing the deferred W3 exporter.
- Contract drift detected during the gate was resolved before UI work: legacy
  turns now carry a null trace plus a typed omission instead of invented
  provenance, and recorded pre-dispatch/orphan failures may truthfully contain
  zero model invocations while failures with Hub-supplied invocation evidence
  retain it. Root and Gateway schema copies now have identical digests.
- Remaining warnings are non-functional: an upstream FastAPI test-client
  deprecation and a disabled pytest-cache write in the isolated test command.

T091 UI implementation is complete. G2.8c real-model/browser acceptance remains
pending; the explicitly user-directed draft publication checkpoint is recorded
below and does not waive T094–T096 as merge gates.

### G2.8c exploratory manual run — FUNCTIONAL MANUAL LOOP; MODEL-SUCCESSOR ACCEPTANCE PENDING (2026-07-18)

The isolated notebook is available at `http://localhost:13000/` with Gemma 4
12B as writer and Qwen 2.5 14B as reviewer. Session
`f51b08c7-7cd1-4955-ac92-51f5baa3a1af` proved the core manual loop:

- initial model Query v1 → human Query v2 → Validate/Run → failed contextual
  follow-up with retained evidence → successful reviewer-selected Query v5 →
  stale prior results → explicit rerun → refresh restoration;
- Query v2 execution `1b184fee-c2b2-4a8a-bf17-fe0c6bb2262d` returned 25 rows
  in 17 ms, and every displayed value/order matched an independent PostgreSQL
  execution of the exact SQL and parameters;
- Query v5 returned 100 rows in 22 ms from 194 matches, with its top values and
  row-100 boundary independently matched against PostgreSQL; ordering inside
  equal-key groups is not deterministic because the SQL has no final unique
  tiebreaker;
- exact revision requests contained the active human SQL/parameters/digest,
  initial and follow-up instructions, matching validation and execution summary,
  and excluded result rows and credentials;
- the refreshed browser restored three turns, the selected Query v5 editor,
  parameters, validation, execution, profile, and the stale-result label.

A fresh uninterrupted session `038c4207-3df2-426c-a61a-c14f29f6aa80`
revalidated the current build and exposed the remaining model-quality boundary:

- the initial turn `7628f3a7-e3b5-4a0d-ba59-a6225a59401f` completed in
  70,328.495 ms of event-wall time: Gemma writer 34,556 ms, Qwen reviewer
  34,997 ms, and 775.495 ms reconciled non-model overhead. Gemma's malformed
  `observed at` was rejected; Qwen produced selected Query v2;
- human Query v3 `ba3cb28f-7faa-4a51-97d6-fde9d673a4f6` added stable output
  ordering plus `LIMIT 25`, validated, and execution
  `8017417f-dcca-44c5-a375-d620396234f8` returned 25 rows in 18 ms. All 25
  displayed rows matched independent PostgreSQL output exactly; PostgreSQL
  reported 49 total matching latest-per-patient rows;
- the first aggregation follow-up exposed a Hub rejected-response serialization
  defect: the models ran, but location-bearing lint findings violated the Hub's
  own response schema and surfaced as HTTP 500. N50 fixes this path and a focused
  regression now proves structured HTTP-200 `rejected` evidence instead;
- the post-fix one-line refinement turn
  `2288ddaf-1a52-4487-95c0-c0f16efc0ece` recorded 80,185.101 ms event-wall,
  79,399 ms model time, and 786.101 ms non-model overhead. Gemma corrupted three
  identifiers while deleting `LIMIT 25`; Qwen repaired two but introduced
  `analytics.lab_result Fact_v1`. Deterministic lint correctly rejected the
  repair, retained writer Query v4 unselected, and preserved both invocation
  timestamps/request-response-failure digests and full structured evidence;
- the evaluator then applied the intended edit manually as Query v5
  `2df486c4-dc95-4612-a137-caae3884bce3`; execution
  `318989fb-e4f6-44ad-96dc-cd1bd18f9ec4` returned all 49 rows in 20 ms with no
  false truncation label. Refresh restored Query v5, results, all three turns,
  and the failed-turn evidence;
- the exact follow-up request reused Query v3's SQL/parameters/digest, included
  matching validation and execution summaries plus bounded instruction history,
  and omitted result rows, credentials, raw traces, and historical SQL copies.

The responsive blocker found during this run is fixed: at 390 × 844 the sticky
`Refine Query v5` control is visible/tabbable, the document has no horizontal
overflow, and activation focuses the canonical follow-up textarea. Deterministic
keyboard/narrow/200%-text coverage passes.

The post-UI automated gate is green after replacing the retired preview
Playwright flow: Hub `363`, Gateway `113`, root harness `582` passed/`36`
skipped/`3` deselected, Catalyst contract/assembly `25` plus `20` subtests, UI
`98`, and Playwright `2` projects pass. Lint/format on changed files, type checks,
production build, all 23 normative schemas, live Hub/Gateway contract copies,
shell syntax, and diff checks pass. Remaining warnings are the existing Vite
chunk-size advisory, one Starlette/httpx deprecation, root Pydantic deprecations,
and React test `act(...)` warnings in sticky-navigation tests.

This is an exploratory manual build, not yet full G2.8c acceptance. Infrastructure
and manual recovery are functional, but N52 shows that the configured 12B/Qwen
pair did not select a valid successor even for a one-line contextual edit. N53
also leaves only one revision-capable choice in the follow-up selector. A diverse
T094 scenario matrix, at least one successful model-selected successor, and the
user checkpoint remain required by T095. Evidence-backed final documentation and
ready-for-review acceptance remain pending. Draft publication and sibling pins
were completed later under explicit user direction; they do not start W2/W3.

### Draft publication checkpoint — COMPLETE (2026-07-20; user-directed)

- Med-Agent Hub commit `bcbfa74e8af9b2171eefe00cfc3a97b2926b4312`
  is published in draft PR `pmanko/med-agent-hub#14`; its complete test suite
  passed (`365 passed`). Generated `uv.lock` was excluded because the repository
  uses Poetry and the file contained no dependency graph.
- Catalyst commit `964a0fd39b39863a6a2aba7e910b634ceccff5b2` is published in draft PR
  `DIGI-UW/openelis-catalyst#4`; the disposable Hub patch is retired and the
  standalone fallback pins the same native Hub commit. A clean disposable clone
  verified that the exact pin contains the query implementation, contracts, and
  checked/Gemma 4 12B profiles.
- Umbrella PR `pmanko/clinical-ai-validation-harness#37` pins both sibling
  commits. The canonical revision-context schema was synchronized before the
  pin; generated Catalyst `.claude/tdd-guard` data was excluded.
- This checkpoint publishes reviewable drafts because the user explicitly
  requested commits and pushes. It does not claim full G2.8c acceptance:
  T094–T096 remain open and block marking the PRs ready or merging them.

### Merge-readiness checkpoint — IN PROGRESS (2026-07-20)

The three-PR review found substantive blockers despite green existing checks:
follow-up instruction/profile/catalog lineage, Hub revision prompting and SQL
lint correctness, concurrent execution idempotency, incomplete Catalyst CI,
clean umbrella boot drift, stale canonical docs/PR descriptions, and incomplete
Harness provenance. T106–T112 track the bounded remediation.

The tracked clean-boot remediation is complete at Harness `921220e`, Catalyst
`8b7c110`, and Hub `099d233`. Starting from reset disposable volumes,
`./scripts/catalyst-mvp.sh --fake boot` completed with the pinned OpenELIS
3.2.1.11 deployment, 96 patients, 1,152 Observations, 1,152 ServiceRequests,
1,152 Specimens, 1,152 DiagnosticReports, nine analytes, the exact analytics
mart row count, and passing Hub profile/router, Gateway, UI, health, and
provenance gates. Readiness probes are now bounded, an empty successful
OpenELIS backfill response is accepted, and clean matching sibling pins are
enforced.

That run also caught a count-only false success: all Observation and
ServiceRequest code/name fields were initially blank because the selected
OpenELIS tests had neither active terminology mappings nor `test.loinc` values.
Catalyst now seeds the reviewed fixture mappings deterministically, rejects
conflicting nonblank mappings, and fails boot unless every one of the 1,152
Observation and ServiceRequest rows is coded and named. The fixture mapping
basis, including explicitly identified inference, is test provenance rather
than production terminology governance.

The functional stack was then rebuilt in external mode at Harness `1118858`,
Catalyst `428b9c7`, and Hub `57d916b`. The same health/provenance gates passed
against loaded `gemma-4-12b` and `qwen2.5-14b`. A fresh notebook session
`283df3f4-3cc8-4449-9a2f-3f294dab9d86` generated and ran the baseline viral-load
query, then selected a complete successor adding only
`ORDER BY t1.observed_at DESC` in turn
`0fe5cccd-3ee3-497d-8204-8af1edc6efa8`. Both persisted invocations record
temperature and DRY multiplier zero. Successor execution
`0edea8b7-bfbe-47e1-a770-7652058730af` returned the bounded first 100 rows; an
independent PostgreSQL check found 194 matching rows across 96 patients, values
30–9000, one `copies/ml` unit, and the same latest timestamp. Harness run
`50cd5c25-8dc4-42d1-af4d-da12c872da58` passed its one selected real-model
scenario with exact clean target provenance.

The repeated-token corruption observed earlier was traced to the router-wide
DRY repetition penalty (`0.8`) reaching SQL roles. Hub query profiles now
require and forward `dry: 0`; effective per-invocation configuration survives
Catalyst persistence and Harness event export. Deterministic lint was not
weakened. The focused live path is functional, but this does not complete the
full T094/T095 matrix, accessibility sweep, nondeterminism repetitions, or the
user acceptance pause required by T111.

The final downstream PR heads add documentation-only alignment and pin Catalyst
`24cef7f` with Hub `d4c09ee`; their contract schemas remain byte-identical.

Squash order is a dependency invariant, not a preference: Hub must merge first;
Catalyst must then pin and validate the resulting Hub `main` commit before it is
squashed; the harness must finally pin both resulting `main` commits and rerun
its gates. No PR-head SHA may remain as the final umbrella pin.

### T094/T095 acceptance execution — IN PROGRESS (2026-07-20)

The merge-readiness review has entered the complete G2.8c acceptance pass on the
clean PR pins. This pass does not reuse the focused sort-order smoke as evidence
for scenario families it did not exercise, and no task is marked complete until
the corresponding durable evidence and user checkpoint exist.

1. Reconfirm the external sibling-Hub stack, dataset/catalog identity, exact
   Catalyst and Hub pins, loaded Gemma 4 12B writer/Qwen 2.5 14B reviewer, and
   effective `temperature: 0`/`dryMultiplier: 0` invocation configuration.
2. Run the five required real-path families: predicate narrowing,
   aggregation/output-shape change, unresolved-snapshot correction, a
   structurally lint-clean semantic reviewer correction, and a bounded Hub/tool
   failure followed by successful recovery. Exercise unchanged, dirty-valid,
   and unresolved bases; selected/unselected outputs; stale results; refresh;
   and New Session isolation. Independently cross-check every successful data
   claim in PostgreSQL with record identifiers, values, and a correctness
   rationale rather than counts alone.
3. Verify exact-digest context membership/exclusions, timed-out and cancelled
   diagnostic presentation, stale/concurrent rejection, orphan recovery, and
   the initial-submit-to-successor latency calculation using every recorded
   invocation timestamp, duration, model, request digest, and response-or-
   failure digest. Run three fresh-session repetitions of the same input and
   report candidate/query digest equality or variance without assuming
   reproducibility.
4. Complete the live keyboard-only desktop flow plus 390 x 844, 320 CSS-pixel
   reflow, and 200%-text checks for jump focus, timeline, profile selection,
   editor/completion/wrap/Format, Restore, Validate/Run, results, and New
   Session. Automated accessibility assertions support but do not replace this
   live pass.

Two issues were explicit before the run. At that time N53 left only one
revision-capable profile. The current Gateway registry now has two reviewed
choices, but current-pin switching/provenance still requires T111 evidence. A
lint-clean semantic reviewer correction is model-observed evidence, not a
deterministically forceable outcome; the run may reveal that this case needs a
reviewed fixture/fault-control seam rather than repeated prompting. Likewise,
Hub/tool failure injection must be bounded to this isolated stack and preserve
the exact failed-turn evidence; it must not rely on or disrupt another running
environment.

Any reproducible code defect found here receives a focused regression and an
affected-gate rerun. Model-output variance is recorded as evidence rather than
patched to match an expected string. After the matrix and final clean-pin gates
pass, the evidence is appended to this roadmap and the G2.8 PCCP, T094/T095/T111
are updated, and work pauses for user acceptance before the squash/repin
sequence.

#### Gold execution-match layer (2026-07-21)

The T094 runner previously proved a generated turn was well-formed (lineage,
digests, profile/config identity) and that its *visible* page agreed between
the Gateway and a direct read-only Postgres connection. Neither check proved
the SQL's `WHERE`/`GROUP BY` actually answered the question: the Gateway caps
every UI-visible result at 100 rows, so a predicate matching 962 real rows and
one matching 200 would both read back as `returned: 100, truncated: true`.

`PostgresGoldExecutionChecker` closes this gap: it executes the model's own
generated SQL directly against the analytics database, unbounded (no UI row
cap), and compares it against a hand-authored reference query for the same
intent — the standard text-to-SQL "execution accuracy" pattern. Four
comparison modes cover the suite's scenario shapes:

- `count` — row-count equality
- `row_set` — multiset equality on key columns (catches a wrong predicate even
  when the count coincidentally matches)
- `aggregate_by_key` — match rows by key column(s), compare value columns with
  a numeric tolerance (for the monthly-aggregation scenario)
- `scalar` — exact single-value comparison (for the distinct-patient-count
  scenario)

Reference SQL is hand-authored per scenario as `baseGoldCheck` /
`successorGoldCheck` in the suite JSON, defense-in-depth guarded against
write/DDL verbs, and executed in the same read-only, statement-timeout-bounded
transaction the existing Postgres cross-check already uses.

Gold values were independently verified against the live seeded dataset
before authoring the suite (not guessed):

| Predicate | True count |
|---|---|
| `observed_at >= '2026-01-01'` (narrowing/aggregation base) | 962 |
| `+ test_name='Viral Load' AND result_status='final'` | 194 |
| `test_name='Viral Load'` (all-time, unresolved-correction successor) | 384 |
| Distinct months in the aggregation window | 4 (Jan 96/Feb 1/Mar 349/Apr 516, summing to 962) |
| Distinct patients since 2026-01-01 | 96 |

A single-scenario smoke against the live stack (real Gemma 4 12B writer / Qwen
2.5 14B reviewer) confirmed the design works against real, non-deterministic
model output, not just the mock server: the model's own base SQL, executed
unbounded, returned exactly 962 rows against the reference's 962 (0
missing/extra), and its successor SQL returned exactly 194 against 194 — proof
the model's predicate is correct, not merely that its visible page is
self-consistent.

The full automatic matrix (4 families x 3 repetitions, run
`5794eb05-5c63-48c9-9aa2-c04b914a3712` under
`artifacts/catalyst-validation/t094-t095-20260721T143955Z/notebook-gold/`) then
confirmed this at scale: all 18 applicable gold-execution-match checks passed
against real model output, across all four comparison modes —

- `narrowing-unchanged-base`: base 962/962, successor 194/194 (`row_set`), x3
- `aggregation-dirty-base-profile-switch`: successor 4/4 months, no key or
  value mismatches (`aggregate_by_key`, writer/reviewer profile-switched), x3
- `unresolved-parameter-correction`: successor 384/384 (`row_set`, model's own
  free-form base plus a repaired binding), x3
- `semantic-distinct-patient-review`: base 962/962 (`row_set`), successor
  scalar 96 == 96 (`scalar`), x3

No mismatch was observed in this pass. The full 12/12-run matrix (1 skip: the
manual bounded-failure family) is otherwise unchanged from the prior
structural-only pass.

This closes gap "A" from the deterministic-vs-LLM-judge fork the user
confirmed (execution-match over static gold counts). It does not by itself
close T094/T095/T111. The bounded Hub/tool-failure run and three-repetition
digest-variance analysis were completed later and are indexed in
`specs/artifacts/planning/catalyst-validation-integration-roadmap-status.md`;
the live accessibility matrix and current-refactor clean-pin acceptance remain
open. A Catalyst-specific LLM-judge rubric (gap "B", for cases a fixed predicate
can't adjudicate) remains a deliberate follow-up, not started.

### G2.9a UX and schema audit — USER REVIEW (2026-07-18)

The measured audit is recorded in
`ux-audit-2026-07-18.md`. The restored active session was approximately 7,859
CSS pixels tall: the follow-up composer, SQL editor, Run controls, results,
evidence, and version history were separated by several viewport heights. The
sticky jump reaches only the composer and does not create a continuous
edit/Run/inspect/refine workflow. An active session also retains a disabled copy
of the initial question alongside the follow-up input and SQL editor.

The proposed G2.9 product shape is deliberately small:

- one reusable natural-language Ask/Refine composer and one canonical SQL
  editor;
- one compact chronological history, with technical evidence under Details;
- adjacent Format/Validate/Run controls and a bounded results viewport;
- one responsive bottom workbench dock showing exact query, validation,
  execution/staleness, and model-grounding state; and
- one runtime-backed schema guide replacing record counts as the primary answer
  to “what can I query?”

The audit also found catalog drift. The supported model/editor catalog lists 8
columns for `analytics.lab_result_fact_v1`; the live view has 16. The read-only
database role can technically SELECT seven business relations, but the six
low-level/pipeline relations do not yet have reviewed product descriptions. The
recommended boundary is to present the completed 16-column fact view as the
supported query surface and treat broader manual SQL access as database-role
governed, not as implicit product support.

The existing follow-up context includes matching execution status, row count,
column schema, timing, and database diagnostics, but no row values. G2.9 makes
that boundary visible. Sending actual result values remains a separate explicit
attachment decision because it reverses G2.8's approved exclusion; the UI must
not imply value-level context until that decision is made.

Product-code changes are paused at T098. T099–T104 remain pending until the user
accepts the architecture and decides whether G2.9 should include bounded result
row attachments or execution summaries only.

### Gateway-owned query-orchestration refactor — IMPLEMENTED; CURRENT-PIN ACCEPTANCE OPEN

The active Catalyst #5 / Hub #15 design supersedes the Hub-owned Catalyst query
profile architecture used by the historical G2.8 evidence:

- Catalyst Gateway's `query_profiles.py` owns five configured revision-capable
  query profiles and their exact required model aliases, including writer-only,
  self-reviewed, bundled-Qwen, and cross-family reviewed variants. The runtime
  subset is not fixed: `LocalHub` derives point-in-time availability from Hub's
  versioned backend model inventory and fails closed when that inventory cannot
  be verified.
- Gateway's `query_engine.py` owns request construction, role prompts,
  writer/lint/reviewer/repair/finalize control flow, contract checks, and
  invocation/query evidence.
- Hub's `POST /v1/hub/generate` performs one generic structured completion using
  the Gateway-selected model/messages/output settings. It has no Catalyst query
  profile, catalog, lint, review policy, or SQL execution authority.
- Existing typed turn/version/execution evidence contracts remain the Catalyst
  public boundary. Writer-only profiles omit reviewer evidence; reviewed profiles
  preserve every role call and deterministic disposition.

The refactor is not accepted merely because component tests exist. T111 must run
the full Hub/Catalyst/harness gates and live notebook matrix on exact current
pins, including profile discovery/switching, writer-only and reviewed evidence,
PostgreSQL checks, the accessibility matrix, and the user pause. T114 records the
ownership-refactor PCCP; its evidence remains pending T111.

The first current-pin runbook audit found the committed T094 suite still named a
removed Hub-era profile and required every profile to have a reviewer. T123
replaced that input with the real Gateway writer-only and Gemma 4 12B/Qwen 2.5
14B reviewed profiles, preserved a real per-turn switch, and made discovery,
evidence, and report checks distinguish an absent reviewer from missing
provenance. This removes the deterministic preflight blocker; it does not count
as the live T111 run.

The 2026-07-30 clean-pin run exposed a further runtime blocker before T111 could
be accepted. Query profiles recorded `maxTokens: null`; a Qwen 2.5 14B reviewer
request timed out at the Gateway but continued decoding inside llama.cpp,
eventually reaching 20,226 decoded tokens and the 24,575-token context boundary.
That orphaned generation contended with later Gemma calls and inflated a
writer-only invocation to 314,177 ms. The Gateway correctly classified the
terminal record as `reviewer_transport` / `reviewer_timeout` and preserved the
human base, but the profile is not fit for manual testing while structured
output is unbounded. T125 therefore blocks the definitive T111 rerun: set and
prove an explicit output-token limit for each query role, reset the router to
clear pre-fix work, retain exact configuration provenance, and rerun the full
matrix. Increasing the harness HTTP observation window merely allows sequential
role evidence to be collected; it does not relax the product's model timeout.

The first post-limit smoke completed both roles in 58,380 ms
(Gemma writer 34,006 ms; Qwen reviewer 24,374 ms), and both invocation records
proved `maxTokens: 1024`. It did not pass: Qwen stopped normally after 336
decoded tokens but returned a review object that failed the strict candidate
schema. The failed turn correctly left the effective human base current, yet
its exact reviewer output was discarded (`evidenceAvailable: false`) and the
lint-clean writer was not retained as an unselected output. Inspection also
found that the comparative profile lost its approved `collaborative_review`
policy flag during the Gateway-ownership move even though the orchestration
path still exists. T126 restores that existing policy and failure evidence
invariant, with no added retry or workflow, before the reviewed smoke and full
T111 matrix continue.

The immediate post-T126 smoke reproduced the same reviewer response digest
`15234ba5…` and exposed the reason: the saved raw Qwen object demanded
`test_name` because lint-clean review was incorrectly switched from the active
aggregation instruction back to the session's initial row-level question. That
violates FR-044/FR-046 and the recorded same-revision-context design. The same
evidence projected the malformed reviewer payload as a second `writer`
candidate. T126 therefore also restores the active instruction/revision context
for review and derives the diagnostic raw-evidence role from the terminal model
invocation/failure stage. These are contract-alignment fixes, not new repair
rules or retries.

At Catalyst `bb36126`, the identical aggregation/profile-switch smoke passed.
The active instruction and exact dirty editor snapshot are present in revision
context digest `f7cb6e07…`; Gemma wrote candidate/query digest `8ca32d51…`,
Qwen review request digest `c4dd4da9…` returned successful response digest
`e38065a9…`, and the writer version was selected after approval. The selected
query returned four monthly rows with columns `observed_month`,
`result_count`, `distinct_patient_count`, and `median_result_value`; Gateway and
an independent read-only PostgreSQL execution produced identical row digests.
Initial plus follow-up model wall time was 83,406 ms, reconciling to 83,087 ms
of recorded invocations plus 319 ms. Both live role records retain
`maxTokens: 1024`. T126 is complete; the complete repetition/failure matrix
below closes T125, while T111 remains open for accessibility and the user
checkpoint.

The definitive pre-review-fix repetition run remains historical supporting
evidence at
`artifacts/catalyst-notebook-validation/t111-owned-router-final-20260730/`
`85fadc7a-370c-4ec0-af0e-81ecc68d2115`. Its manifest records harness
`2320bee`, clean Catalyst `bb36126`, clean Hub `946afa9`, dataset/pipeline
`full-20260730T041145Z`, and catalog
`analytics-catalog-v1+schema.665109d58952e881`. All 12/12 repetitions passed
through the real Gateway → sibling Hub → llama.cpp path with independent
read-only PostgreSQL and gold-query checks:

- unchanged-base narrowing: 3/3, 75,143/68,217/67,842 ms, one identical
  selected SQL;
- dirty-base aggregation plus per-turn switch to the Gemma/Qwen reviewed
  profile: 3/3, 87,651/75,175/74,164 ms;
- unresolved editor correction: 3/3, 65,793/54,207/54,597 ms, with the
  unresolved snapshot not promoted and one identical complete successor;
- lint-clean distinct-patient semantics: 3/3, 49,900/43,746/43,864 ms, with
  `COUNT(DISTINCT patient_id)` and exact PostgreSQL agreement.

Every live writer/reviewer invocation retained `temperature: 0`,
`dryMultiplier: 0`, and `maxTokens: 1024`; no candidate was truncated or
timed out. The only observed output variance was aggregation repetition 2 using
`COUNT(observation_id)` where repetitions 1 and 3 used `COUNT(*)`. Both
executed to the same independently verified dataset, so this is recorded as
bounded syntactic/digest nondeterminism rather than hidden or rewritten.

The bounded failure run is
`artifacts/catalyst-notebook-validation/t111-bounded-failure-20260730/`
`5bf746e1-0f7f-4f67-8053-db994bfffdee` (1/1 passed). A worktree-local proxy
forwarded discovery and injected exactly one typed HTTP 502 for the next
`POST /v1/chat/completions`. Turn
`7c26a4f5-c889-40f8-b420-9ec4092b24c1` terminated once as
`writer_transport` / `writer_transport_failed`, selected no version, retained
request/failure digests and an 8 ms failed invocation, and left human base
`c3013e01-6d40-46f8-b778-3c1b5ef2c5d3` current. After immediately restoring
the real router, same-session turn
`c535bc2d-08b6-428c-ac2f-4e9e99538b6e` completed in one 36,262 ms writer
invocation and selected version `78dda6ac-c60b-4d3f-9dc6-de50d9f59bf9`.
Its bounded revision context contains only prior instructions plus
digest-matched validation/execution summaries; it contains no transport-failure
payload or prohibited raw evidence.

T125 is complete. Hub then advanced from `946afa9` to `198d5f6` to address two
valid suppressed Copilot findings: the generic role executor now returns the
provider content verbatim, and profile digests include `selection_priority` and
`supplemental_sources`. Hub's focused 28-test slice and full 633-test suite
passed before `198d5f6` was pinned in the umbrella at `e475d7a`.

The authoritative exact-current-pin repetition run is
`artifacts/catalyst-notebook-validation/t111-review-fix-final-rerun-20260730/`
`cbc41bcd-56f7-4074-931f-98ed42fea202`. Its manifest records harness
`e475d7a`, clean Catalyst `bb36126`, clean Hub `198d5f6`,
dataset/pipeline `full-20260730T041145Z`, and catalog
`analytics-catalog-v1+schema.665109d58952e881`. All 12/12 repetitions again
passed through the real Gateway → sibling Hub → llama.cpp path and independently
matched PostgreSQL/gold execution:

- unchanged-base narrowing: 3/3, 81,724/74,498/75,063 ms, identical selected
  SQL;
- dirty-base aggregation plus profile switching: 3/3,
  109,032/87,123/87,654 ms; repetitions 1 and 2 used `COUNT(*)`, while
  repetition 3 used semantically equivalent `COUNT(observation_id)`;
- unresolved editor correction: 3/3, 75,177/60,267/59,530 ms, identical
  complete successor and no promotion of the unresolved snapshot;
- lint-clean distinct-patient semantics: 3/3, 62,234/54,267/53,568 ms, all
  selected `COUNT(DISTINCT patient_id)`.

The current-pin bounded-failure proof is
`artifacts/catalyst-notebook-validation/`
`t111-review-fix-bounded-failure-final-20260730/`
`68da21db-2178-4010-9fd4-5c73fd477261` (1/1 passed). In session
`b24956c1-4b9a-4038-9f8f-17e311579418`, a fresh worktree-local proxy injected
one typed HTTP 502 on the first follow-up model call. Turn
`856d88bf-c03f-408b-8867-04239925d191` failed once as
`writer_transport` / `writer_transport_failed` in 161 ms, selected no output,
and preserved human base version `a8dee8ed-d347-4f6f-978d-1973798b4fdf`.
After restoring the direct router, same-session turn
`bbd77610-2660-4ae8-84fa-6dffe57d760e` completed and selected successor
`b5021739-a0fa-4540-a6fa-1ab001b3c031`. Its revision context contains the
failed instruction plus validation and execution summaries that match the exact
base digest; it does not promote the failure or include raw failure content.

Two non-product interruptions are retained rather than hidden. Run
`699fa9fc-bf98-4445-8d7e-76e1e7c33a7a` stopped after 2/2 passing narrowing
repetitions when the local OrbStack engine exited and Docker clients blocked.
Run `7302b5dc-527f-4ad9-ba93-a302d50f2b53` injected the fault on the second
overall model call, which was still part of initial contract repair, so it is a
fault-targeting procedure failure rather than follow-up failure evidence.

Current-pin responsive inspection passed at 390 × 844 and 320 × 844 CSS
viewports with no horizontal overflow, one contained textarea, and the composer
fixed to the viewport bottom. A 640 × 720 CSS viewport provided the
layout-equivalent 200%-zoom reflow check with the same no-overflow and
focusable-composer geometry. Browser automation could directly focus the data
source control, and DOM inspection preserved the intended focusable order, but
the automation surface did not advance focus for Tab key events. Therefore an
actual keyboard-only Tab traversal and an actual browser-zoom interaction
remain explicitly unverified. T094/T095/T111 stay open for that manual
accessibility confirmation and explicit user acceptance; no merge is
authorized by the model/PostgreSQL or responsive evidence alone.

The focused umbrella pin test then exposed that Catalyst's standalone fallback
bootstrap still named Hub `946afa9` even though the umbrella sibling pin was
`198d5f6`. Catalyst `95515a2` corrects that single default SHA; focused harness
coverage is 57/57. Clean umbrella `93689d5` smoke
`4dd70443-ba23-4415-b0cd-d393d2352061` then passed 1/1 unchanged-base
narrowing through the real model path and independent PostgreSQL/gold checks
with Catalyst `95515a2` and Hub `198d5f6`. The completed 12/12 repetition matrix
remains correctly attributed to direct parent `bb36126`; this scoped smoke
establishes the one-line fallback-pin delta without relabelling that evidence.

### G2.10 multi-source/lossless onboarding — WRITTEN TRACE COMPLETE; EVIDENCE OPEN

The 2026-07-22 clarification is now traced to User Story 6, FR-064–FR-070,
SC-030–SC-034, plan gates G2.10a–c, and T116–T122. The active change set contains
registry, per-turn `dataSourceId`, two-source UI/test plumbing, upstream-style
lossless ViewDefinitions, deterministic SQL curation/comments, and generated
catalog code. Those facts establish an implementation candidate, not acceptance.

- **G2.10a written gate — PASS:** ownership, data boundaries, requirements,
  entities, success criteria, task order, quickstart checks, and residual risks
  are recorded without predeclaring the live result.
- **G2.10b internal gate — OPEN:** inventory/close contract gaps; prove
  unavailable-source behavior and per-source stale baselines; prove
  ViewDefinition provenance and repeated-coding multiplicity; prove curated
  SQL/comment metadata, catalog-generation failure modes/byte stability, live
  information-schema agreement, and default-only readiness disclosure.
- **G2.10c user gate — OPEN:** recreate two independently provisioned analytics
  sources and run A → B → inherited B → A plus unavailable-source rejection,
  refresh, exact query execution, and record-level PostgreSQL evidence. Pause for
  explicit acceptance before describing multi-source/lossless onboarding as
  complete or using it in release evidence.

## W2 — Targeted remediation

**Status:** Planned

- Normalize current lint output into stable findings.
- Derive AST repair units and freeze unaffected-unit digests.
- Apply deterministic substitutions where unambiguous.
- Add a user-initiated med-agent-hub proposal stage for only the selected AST
  units; this is separate from G2.3's internal generation-correction patches.
- Show before/after units and require explicit acceptance.
- Reject stale, full-replacement, or out-of-scope proposals.

**Exit:** Seeded single-finding scenarios change only permitted units in at
least 90% of cases and every accepted repair passes full revalidation.

### W2 checkpoints

- **G4 user:** revalidate the plan from W1 evidence before model patching.
- **G5 user:** review integrity metrics and decide W3 versus another W2 loop.

## W3 — Harness experiment integration

**Status:** Planned only after G5 user approval

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
