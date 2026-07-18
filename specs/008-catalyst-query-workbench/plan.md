# Implementation Plan: Catalyst Query Workbench

**Branch**: `codex/catalyst-mvp-umbrella` | **Date**: 2026-07-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-catalyst-query-workbench/spec.md`

## Summary

Build a persistent manual query workbench around the real Catalyst → med-agent-hub
→ PostgreSQL path. The first delivery slice makes the complete generated SQL and
typed parameters editable, keeps deterministic validator findings visible but
advisory, executes the exact displayed draft under the database role, returns
useful database errors, restores the session after refresh, and collapses detailed
dataset context by default. The SQL editor provides PostgreSQL highlighting,
line numbers, default-on toggleable wrapping, catalog-and-keyword completion,
and deterministic formatting without weakening immutable version lineage. The
next slice constrains automated remediation to
versioned SQL AST units with frozen-unit digests. Harness artifact materialization
follows once the session event model is stable; the first slice still records all
lineage needed for that export.

## Technical Context

**Language/Version**: Python 3.11–3.13; TypeScript 6 / React 19

**Primary Dependencies**: FastAPI, psycopg 3, SQLGlot, jsonschema, Carbon React,
direct CodeMirror 6 with `@codemirror/lang-sql`, `sql-formatter`, and the
med-agent-hub OpenAI-compatible profile API

**Storage**: Existing gateway SQLite store for workbench operating metadata;
existing read-only PostgreSQL analytics database for query execution

**Testing**: pytest/pytest-asyncio, Vitest/Testing Library, Playwright, real-path
harness Catalyst suite

**Target Platform**: Local Docker Compose demo in a modern desktop browser

**Project Type**: React web application + FastAPI gateway + external model hub

**Performance Goals**: Restore a local session in under 1 second excluding
network startup; deterministic validation in under 500 ms for MVP query sizes;
render the first 100 returned rows without blocking interaction

**Constraints**: The isolated validation stack currently uses demo data, while
the product reads whichever connected OpenELIS-to-FHIR analytics projection is
loaded and does not infer its classification; model inference remains in
med-agent-hub; manual execution is never gated by validator status; database
permissions and a read-only transaction remain authoritative; statement timeout
and fetch bounds must not rewrite SQL; no preview expiry; editor dependencies
must pass keyboard, screen-reader naming, narrow-layout, deterministic-format,
and bundle/build review

**Scale/Scope**: One evaluator and a small number of local sessions; queries are
single-user research artifacts, not multi-tenant production records

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

- **Real production paths — PASS**: The browser calls the deployed Catalyst
  gateway, which calls the real med-agent-hub profile and the seeded PostgreSQL
  analytics database. Fixtures are scaffolding, not behavior evidence.
- **Deterministic reviewed transforms — PASS**: SQL parsing, finding
  classification, patch scopes, patch application, frozen-unit verification, and
  version digests live in reviewed code/contracts. Model patches remain proposals.
- **Record-level evidence — PASS**: Every execution records the exact query
  version, parameters, returned columns/rows or database error, and scenario
  assertions retain patient identifiers when available.
- **Metadata and provenance — PASS (staged)**: The first slice persists complete
  session events and model/profile/prompt/catalog/dataset/validator provenance.
  The harness-integration slice materializes the same lineage as versioned
  `run_manifest.json` and `events.jsonl` artifacts.
- **Tests define behavior — PASS**: Gateway, UI, live browser, and harness tests
  cover malformed output, parse/binding/semantic findings, stale and out-of-scope
  repairs, successful and failed execution, refresh, and warning-bearing success.
- **Data boundaries and governance — PASS**: PostgreSQL remains the clinical
  evidence source; SQLite stores only operating metadata and bounded execution
  evidence for the isolated demo. Prompt/profile/validator changes receive a
  PCCP-style change record before experiment comparisons are claimed.
- **Why this is sufficient — PASS**: Exact-version lineage plus real database
  outcomes makes manual behavior inspectable, while AST integrity tests prove
  targeted repairs do not silently modify frozen query units. Diverse real-path
  scenarios limit prompt-specific overfitting.

## Project Structure

### Documentation (this feature)

```text
specs/008-catalyst-query-workbench/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── roadmap.md
└── contracts/
    ├── workbench-api.md
    └── query-patch-v1.schema.json
```

### Source Code

```text
harness/
├── catalyst/validation.py        # real-path scenario runner and later importer
└── metadata.py                   # canonical run manifest/event writers

targets/catalyst/                 # pinned Catalyst submodule
├── catalyst-gateway/src/catalyst/
│   ├── analytics.py              # exact SQL execution + DB diagnostics
│   ├── routes.py                 # workbench endpoints
│   ├── service.py                # governed path remains unchanged
│   ├── storage.py                # persistent session/version/event store
│   └── workbench.py              # advisory validation and execution orchestration
├── catalyst-gateway/tests/
├── catalyst-ui/src/
│   └── features/query/
│       ├── api.ts
│       ├── QueryWorkspace.tsx
│       └── components/
│           ├── DatasetBrowser.tsx
│           └── SqlEditor.tsx     # PostgreSQL editing + completion + format UI
├── catalyst-ui/e2e/
├── patches/med-agent-hub/
└── docs/roadmap.md
```

**Structure Decision**: Keep inference/profile behavior in the Hub, workbench
state and execution in the Catalyst gateway, presentation in Catalyst UI, and
experiment orchestration/artifact validation in the umbrella harness. The
existing governed preview endpoints remain compatible; the workbench receives a
separate API so advisory manual execution cannot weaken governed behavior.

## Delivery Slices

1. **Manual workbench MVP**: compact dataset disclosure, persistent sessions,
   immutable query versions, PostgreSQL-aware SQL/parameter editing with line
   numbers, wrap control, catalog/keyword completion and deterministic Format,
   advisory validation, exact-draft execution, database diagnostics, and refresh
   restoration. Generation correction retries are patch-only once a response is
   structurally parseable: exact JSON Pointer leaves and uniquely anchored SQL
   fragments may change, while unaffected candidate fields remain frozen.
2. **Targeted remediation**: AST repair units, deterministic fixes, typed Hub
   patch contract, frozen-unit verification, before/after review, and full
   revalidation.
3. **Harness integration**: one-click `run_manifest.json`/`events.jsonl`
   materialization, importer/contract tests, and expanded repeatable suites.
4. **Experiment iteration**: richer datasets and scenario matrices across Hub
   profiles/models. Agent teams remain explicitly deferred.

## Validation and Check-in Gates

No implementation task may silently cross a gate. Gate evidence and unresolved
issues are appended to `roadmap.md`; product-code work pauses at the user gates.

1. **G0 — Plan readiness (user gate, before implementation)**: Generate
   `tasks.md`, run read-only Spec Kit analysis across spec/plan/tasks, resolve all
   CRITICAL and HIGH findings, run requirement/checkpoint consistency checks,
   and present nondeterminism/inconsistency register to the user.
2. **G1 — Persistence/API foundation (internal validation)**: Contract and store
   tests prove append-only versions, refresh restoration, stale-write conflicts,
   and export-complete event capture before UI wiring.
3. **G2 — Manual execution boundary (user gate)**: Demonstrate through the real
   stack that a finding-bearing draft can run unchanged, and show both a useful
   PostgreSQL failure and a successful result. Pause for user review before UX
   completion.
4. **G2.1 — Model identity and generation boundary (corrective user gate)**:
   Before UI work, connect the isolated patched Hub to the canonical host
   llama.cpp router, align the Catalyst Gemma role model with the router's
   `gemma-e4b` identity, eliminate the false Qwen 14B alias, and make workbench
   generation side-effect-free from governed preview/policy persistence. Re-run
   the real generation and exact-execution evidence with physical model
   provenance. Approved by the user on 2026-07-17.
5. **G2.2 — Editor contract and TDD readiness (internal gate, before editor
   implementation)**: Use the reproduced `parameters.1: 'name' is required`
   query-generation failures to assign ownership among response schema, prompt,
   Hub normalization, and gateway retention. The best prior draft is retained,
   but fix and test the mutually exclusive candidate/raw diagnostic so the best
   parsed candidate and latest malformed response are both retained; permit
   deterministic naming only when exactly one question-grounded unnamed
   parameter maps to exactly one remaining SQL placeholder. Use direct
   CodeMirror 6 and `sql-formatter`, expose the gateway's approved vocabulary
   through the typed read-only editor-catalog contract, then land failing tests
   for highlighting, line numbers, default-on wrap/toggle retention, catalog/
   keyword completion, deterministic Format, and immutable Validate/Run
   persistence. Record cross-profile or cross-attempt variance in the
   nondeterminism register before implementation.
6. **G3 — W1 integrated workbench (user gate)**: Run gateway/UI/Playwright/live
   checks, repeat the acceptance scenarios manually, audit exact-query digests,
   manually exercise editor keyboard/zoom/wrap/completion/format/version behavior,
   and have the user test the isolated browser before starting W2. Any mismatch
   between automated editor assertions and the real browser is raised rather
   than normalized away.
7. **G2.3 — Localized generation retry boundary (corrective internal gate)**:
   Reproduce the cross-attempt regression with E4B and 12B, land strict
   patch-contract red tests, then prove retry output cannot replace the complete
   candidate or mutate unaffected parameter/SQL/metadata fields. Re-run the
   same question through both real profiles before closing G3.
8. **G2.4 — Unresolved raw-draft hydration (corrective internal gate)**: Before
   G3, add a response-derived editor seed for one structurally parseable raw JSON
   object when no immutable version exists. Preserve the raw string exactly,
   leave missing names blank, label the buffer unresolved, reject malformed or
   unrepresentable shapes, restore it after refresh, and prove a later immutable
   version always wins.
9. **G4 — Targeted-remediation design validation (user gate)**: Re-run artifact
   analysis after incorporating W1 evidence; review repair-unit coverage,
   nondeterministic model behavior, and deterministic fallback cases with the
   user before enabling model-authored patches.
10. **G5 — W2 remediation evidence (user gate)**: Report frozen-unit integrity,
   stale/out-of-scope rejection, and the seeded 90% single-finding metric. Decide
   with the user whether results justify W3 harness export or more repair work.
11. **G6 — Harness experiment readiness (user gate)**: Validate artifact schemas,
   provenance, scenario diversity, and profile/model identity before making any
   comparative model claim.

## Nondeterminism and Inconsistency Register

The following items must remain visible until evidence resolves them:

- **N1 — Model sampling (bounded, still open for experiments)**: The canonical
  router now advertises temperature 0, seed 42, context 24,576, and its full
  launch preset; the Hub records profile knobs and config/prompt digests. A
  single successful run is not repeatability evidence, so comparative runs still
  require repetitions and variance reporting.
- **N2 — Advertised versus physical model (resolved for Gemma and bundled
  fallback)**: `gemma-e4b` maps to the loaded Gemma 4 E4B IT Q4_K_M artifact;
  the bundled Qwen fallback is truthfully named as a 1.5B Q4_K_M model. The Hub
  persists the router-advertised model object instead of inferring identity.
- **N3 — Gemma target availability (resolved for this isolated stack)**: The
  `catalyst-query-gemma-e4b` profile is available and both query roles resolve to
  the loaded `gemma-e4b` backend. Physical revision evidence is deployment-owned
  and comes from the router/artifact cache, not an alias alone.
- **N4 — Validator drift**: Hub lint and gateway policy overlap but produce
  different shapes and do not yet share one versioned finding schema. W1 must
  normalize without claiming the layers are identical; W2 cannot scope repairs
  from free-form messages.
- **N5 — Dynamic result typing (resolved for W1)**: Manual execution derives
  result types from PostgreSQL cursor metadata with deterministic tests for
  scalar, array, JSON, null, and unknown fallbacks. Future database types can
  still surface as the explicit `unknown` logical type.
- **N6 — Metadata terminology**: The planning doc mentions
  `otel.gen_ai.system`, while the current writer emits
  `otel.gen_ai.provider.name`. W3 must reconcile this before contract validation.
- **N7 — Documentation drift**: Catalyst's roadmap still describes the earlier
  expiry/one-time preview baseline and deferred harness state. It must be updated
  only after the corresponding behavior/evidence gate, not predeclared complete.
- **N8 — Database authority boundary**: The workbench intentionally relies on
  the configured role and read-only transaction rather than application policy.
  Any database permission or function-side-effect concern discovered in manual
  tests is raised to the user as an environment decision, not silently blocked.
- **N9 — Row-limit signal drift**: Hub lint can pass a generated query with no
  SQL `LIMIT`, while the executor independently applies a fetch bound and marks
  the returned table truncated. The UI and experiment artifacts must distinguish
  exact SQL from operational result truncation.
- **N10 — Generation preview side effect (resolved)**: Workbench session
  creation calls the real Hub generation pipeline without creating a governed
  preview. The governed endpoint remains unchanged. Unit tests and the live
  Gemma run both prove the preview count is unchanged.
- **N11 — Dataset snapshot identity (open, non-blocking for manual POC)**: The
  session records the latest successful FHIR Data Pipes run ID and live counts,
  but there is no reviewed load manifest, content digest, or authoritative
  synthetic/real classification. Do not treat `pipelineRunId` as a content hash.
- **N12 — Concurrent execution idempotency (open, non-blocking for one-user
  manual POC)**: Workbench idempotency is currently check-then-execute rather
  than one atomic claim. Concurrent retries with the same key could reach the
  database twice; parallel experiment runners need an atomic lease/claim first.
- **N13 — Validator identity (open before comparative experiments)**: The
  validator digest is deterministic but currently hashes a static definition,
  not the complete parser, catalog, policy, and implementation configuration.
  Current manual findings are useful, but the digest is not yet strong enough
  to prove validator equivalence across experiment runs.
- **N14 — Unnamed generated parameter (resolved at the reproduced boundary)**:
  For “how many patients had viral
  load tests above 1000 count/ml?”, Gemma E4B session
  `2bed91de-fa7d-4ffa-b4ae-0a454a883930` / trace
  `07740499-387c-40b4-97c3-2bf7c4e08b7e` failed query-generation attempts 2–3
  at `parameters.1: 'name' is required`; Gemma 4 12B failed attempts 1–3 at the
  identical path. This is the second generated parameter object, not a Hub
  profile name or review-stage field. Executor binding requires every parameter
  name to match its `:placeholder`. The shared Hub normalizer handles analytes,
  dates, and turnaround thresholds but has no conservative fallback for one
  remaining question-grounded unnamed parameter and one remaining placeholder.
  The Hub now adds only that 1:1 normalization; ambiguous or ungrounded cases
  remain invalid and `name` remains required.
- **N15 — Lossy failed-attempt diagnostics (resolved through the UI)**: The E4B
  workbench session preserved editable version
  `d801dc1d-fc94-435b-bee6-2b45c3173af1` from schema-valid attempt 1, including
  SQL literals and an advisory unbound-literal finding. Hub diagnostics
  previously retained a parsed candidate OR `rawOutput`, so an earlier candidate
  hid the latest malformed attempt. Hub diagnostics and the live UI now preserve
  and display both independently with ordered attempts and provenance evidence.
- **N16 — Question/catalog unit mismatch (open; non-blocking for the editor)**:
  The reproduced question says `count/ml`, while the connected catalog and live
  records use `copies/ml`. The generated candidate copied the ungrounded unit
  literal and current deterministic validation did not flag it. Add a catalog-
  grounded unit warning in the next validation iteration; do not silently change
  the evaluator's question or block manual execution.
- **N17 — Older single-date placeholder inference (open; non-blocking for the
  reproduced no-date case)**: `_normalize_single_date_binding` can still infer
  that a sole placeholder belongs to the one date mentioned in the question,
  even when that placeholder is numeric. Add a focused failing regression before
  changing that helper in the next validation iteration; do not expand the
  current missing-name repair without evidence.
- **N18 — UI bundle size (open; non-blocking for the local MVP)**: The direct
  CodeMirror integration builds successfully, but the production JavaScript
  bundle is approximately 1.06 MB (324.9 KB gzip) and crosses Vite's 500 KB
  warning threshold. Evaluate route/component splitting before production; do
  not block the isolated manual research loop on this warning.
- **N19 — Numeric parameter type drift (open; manually correctable)**: The live
  E4B run emitted threshold value `"1000"` with type `string` for a numeric
  comparison. The editor allowed the evaluator to change it to `number`, and
  the exact revised query validated and executed. Add a catalog/parser-grounded
  type warning in the next validation iteration rather than silently coercing
  model output.
- **N20 — Whole-object correction regression (resolved at G2.3)**:
  Generation retries previously received precise findings but returned a complete
  replacement candidate. In the original live E4B run, attempt 1's unambiguous missing
  name was repaired, but retries for unrelated SQL/column findings dropped
  parameter names again. The live 12B run omitted names on all three attempts
  and its latest raw response also referenced an unapproved view. G2.3 replaced
  post-parse whole-object retries with typed, finding-scoped patch operations,
  deterministic application, frozen unaffected fields, and full revalidation.
  The post-fix E4B run preserved earlier unit work across later corrections;
  ambiguous multi-name 12B responses remained unresolved instead of guessed.
- **N21 — Hub/gateway validation-scope divergence (open before comparative
  scoring)**: The post-fix E4B candidate retained a Hub projection-vs-
  `expectedColumns` finding while its SQL and parameters passed the gateway
  validator and executed. Preserve both statuses and label or align their scopes
  before treating either one as the experiment's single validity outcome.
- **N22 — E4B physical artifact variance (open across historical sessions)**:
  G2.1 recorded a different E4B size than the file loaded for G2.3. The G2.3
  runs are anchored to SHA-256
  `3f72a20a06f626c78e6c475ae07a64c88b2663149c0f6197b56bf7cf1f37585c`;
  do not aggregate earlier and current E4B outcomes until cache history explains
  the revision change.
- **N23 — Raw evidence/editor hydration gap (resolved at G2.4)**: The post-G2.3 12B
  response is valid JSON with SQL and typed values but is not a valid Hub
  candidate because multiple parameters omit required names. The raw string is
  correctly persisted, yet the editor initializes only from a QueryVersion and
  is therefore blank. Derive a separate unresolved manual seed without guessing
  names or treating raw evidence as accepted model output. The gateway now
  derives that seed from persisted raw provenance on both create and restore;
  live refresh proves it hydrates while any immutable version takes precedence.

## Complexity Tracking

No constitution violations are required by this plan.
