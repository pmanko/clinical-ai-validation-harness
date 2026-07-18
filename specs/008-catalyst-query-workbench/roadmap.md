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

**Status:** G2.1–G2.4 passed; G3 evidence preparation is in progress and broader
W2 remediation has not started

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
- Make post-parse generation retries patch-only: apply typed operations only to
  reported failing paths, freeze unaffected fields, and fully revalidate.
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
