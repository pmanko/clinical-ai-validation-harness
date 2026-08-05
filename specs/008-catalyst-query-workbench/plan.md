# Implementation Plan: Catalyst Query Workbench

**Branch**: `codex/dashboard-builder-mvp` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-catalyst-query-workbench/spec.md`

## Summary

Build a persistent manual query workbench around the real Catalyst Gateway →
generic Med-Agent Hub role executor → model router path, with exact execution
through Catalyst → PostgreSQL. Catalyst Gateway owns the governed-query profile
registry, prompts, writer/reviewer composition, deterministic lint/repair, and
query evidence; Hub supplies one structured model completion per requested role.
The first delivery slice makes the complete generated SQL and
typed parameters editable, keeps deterministic validator findings visible but
advisory, executes the exact displayed draft under the database role, returns
useful database errors, restores the session after refresh, and collapses detailed
dataset context by default. The SQL editor provides PostgreSQL highlighting,
line numbers, default-on toggleable wrapping, catalog-and-keyword completion,
and deterministic formatting without weakening immutable version lineage.
That workbench foundation is accepted. Remaining data, repair, evaluation,
narrative, and production work is organized as parallel pathways rather than a
single implementation queue.

Before G3 closes, add a linear iterative-query notebook inside the same
workbench session. A follow-up instruction is grounded in the exact visible SQL
and parameter buffer, produces a complete successor query through the
Gateway-owned writer → lint → optional reviewer → lint path, and retains a
compact turn timeline. Each model role receives bounded, typed revision context
through Hub's generic executor rather than an undifferentiated chat transcript or
returned result rows.

The active change set also contains multi-source workbench plumbing and a
lossless-ingestion/generated-catalog architecture. Its formal acceptance is a
separate checkpoint: implementation presence and unit tests do not establish
lossless live ingestion, per-source provenance, or two-source correctness.

Catalyst validation/report parity with ChartSearchAI is governed by the
standalone [validation integration roadmap](../artifacts/planning/catalyst-validation-integration-roadmap.md)
and its [status artifact](../artifacts/planning/catalyst-validation-integration-roadmap-status.md).
Phase 9 of `tasks.md` mirrors that roadmap's delivery state; it does not silently
close G2.9, multi-source acceptance, W2 remediation, or the W3 one-click session
export feature.

## Parallel pathways after the accepted workbench

| Pathway | State | Planning boundary |
| --- | --- | --- |
| **Superset-backed Dashboard Builder MVP** | **Selected next product milestone** | Depends only on the accepted query/version/execution/table foundation. Persist supervised Dataset/Widget/Dashboard drafts and publish a deterministic native asset bundle to the local Superset outbox. |
| G2.10 data foundation | Candidate implementation; acceptance evidence open | Complete multi-source, lossless-projection, generated-catalog, readiness, and provenance gates independently. |
| W2 query assistance | Planned, not selected | Re-enter only after the G4 scope decision; bounded AST repair remains separate from internal generation correction. |
| W3/CVR evaluation | Report parity implemented; session export/comparative expansion open | PR #43 MS-D/merge is release closeout. Additional export and experiments require their own selection. |
| R4 narrative reporting | Planned | Starts from a governed table and is not a prerequisite for Dashboard MVP. |
| R5 productionization | Future | Authentication, authorization, data scope, audit, and supported deployment require a separate program. |

Dashboard Builder MVP implements the supplied iterative Ask → Dataset → Widget →
Dashboard design while using Superset as the renderer. It explicitly defers the
Superset REST API, embedded viewing, cross-system undo/reconciliation, model-
generated visualization specifications, narrative reports, sharing,
scheduling, automatic refresh, and production access control. Its first slice
must not absorb G2.10, W2, W3, R4, or R5 merely because those paths can later
enrich dashboards.

### Dashboard Builder MVP design boundary

- Extend the existing append-only Gateway/SQLite operating-metadata store with
  immutable-versioned `DatasetDraft`, `WidgetDraft`, `DashboardDraft`, and
  `SupersetBundleExport` records. Clinical rows remain on their immutable source
  execution; builder metadata references the exact execution and canonical
  result digest instead of copying rows.
- Implement the supplied high-fidelity shell and iterative flow: the fixed Ask
  composer and chronological work stay available while Dataset, Widget, and
  Dashboard review panels and libraries progressively promote the same governed
  artifact. One dashboard may contain multiple saved widgets.
- Derive the initial presentation deterministically from the typed result shape,
  support table, big-number KPI, time-series line/area, grouped/stacked bar, and
  proportion bar, explain incompatibility, and let the user review or override
  the compatible presentation type while keeping deterministic bindings
  reviewable/read-only. Catalyst renders only schematic thumbnails; Superset is
  the authoritative renderer. Configuration never invokes a model or reruns SQL.
- Generate a native Superset asset ZIP with a stable logical Dashboard UUID,
  immutable version-derived Dataset/Widget UUIDs, and deterministic
  serialization. Compile named parameters from exact typed execution values,
  preserve the parameterized form in a Catalyst manifest, and never place result
  rows in the bundle.
- `Publish to Superset` atomically writes the bundle to a host-visible outbox
  bind-mounted read-only into Superset and offers the same ZIP for download. A
  bootstrap importer loads the current bundle into a clean instance; an explicit
  CLI helper imports or updates it in a running instance and records success or
  failure against the exact digest. No Superset REST API is introduced.
- Add pinned Apache Superset 6.1.0 plus its metadata database to the isolated
  Compose stack. Superset queries the analytics database with the demo read-only
  role; production secrets and deployment are deferred.
- Test contracts/storage, deterministic bundle generation, and UI behavior
  before implementation. Finish with a real clean import and versioned-child
  dashboard update, plus
  PostgreSQL value reconciliation, refresh/staleness, keyboard/reflow evidence,
  and a PCCP-style change record.

## Technical Context

**Language/Version**: Python 3.11–3.13; TypeScript 6 / React 19

**Primary Dependencies**: FastAPI, psycopg 3, SQLGlot, jsonschema, deterministic
YAML/ZIP serialization, Carbon React, direct CodeMirror 6 with
`@codemirror/lang-sql`, `sql-formatter`, Apache Superset 6.1.0, and the
med-agent-hub generic structured role-execution API

**Storage**: Existing Gateway SQLite store for workbench and builder operating
metadata; existing read-only PostgreSQL analytics database for query execution
and Superset virtual datasets; persistent Superset metadata database; and a
host-visible, gitignored bundle outbox bind-mounted read-only into Superset

**Testing**: pytest/pytest-asyncio, Vitest/Testing Library, Playwright, real-path
harness Catalyst suite

**Target Platform**: Local Docker Compose demo in a modern desktop browser with
Catalyst and a pinned local Superset instance

**Project Type**: React web application + FastAPI gateway + external model hub

**Performance Goals**: Restore a local session in under 1 second excluding
network startup; deterministic validation in under 500 ms for MVP query sizes;
render the first 100 returned rows without blocking interaction; from initial
question submission through successor-query visibility, complete the workflow in
under 3 minutes after subtracting only the exact `durationMs` values recorded for
every initial/follow-up writer and reviewer invocation. Reconcile those values
to each invocation's `startedAt`/`endedAt`, role/stage/attempt/model identity,
request digest, and response-or-failure digest. Record unadjusted wall time and
explicit Run/database duration separately as secondary measures.

**Constraints**: The isolated validation stack may use a documented demo fixture,
while the product reads whichever registered analytics source is selected;
synthetic/real classification comes only from authoritative dataset provenance
and is otherwise unknown. Catalyst owns query profiles/orchestration but never
serves model weights; model inference crosses the generic Hub role-execution
boundary. Manual execution is never gated by validator status; database
permissions and a read-only transaction remain authoritative; statement timeout
and fetch bounds must not rewrite SQL; no preview expiry; editor dependencies
must pass keyboard, screen-reader naming, narrow-layout, deterministic-format,
and bundle/build review. Base ingestion preserves upstream FHIR Data Pipes
multiplicity; semantic curation occurs in repeatable SQL and catalogs are
generated from live metadata plus reviewed overlays.

**Scale/Scope**: One evaluator and a small number of local sessions; queries are
single-user research artifacts, not multi-tenant production records

## Constitution Check

*The original W1 and G2.8a written gates passed. G2.8b and the post-UI automated
gate passed for the earlier Hub-owned query engine. The later Gateway-ownership
refactor passed its July 30 PR-head model/PostgreSQL matrix and the reconciled
merged-Hub pins passed the definitive T111 live rerun. The user confirmed the
actual keyboard-only and 200%-browser-zoom checks passed and accepted the MVP on
2026-08-04; the deterministic Playwright path now guards the equivalent focus
and reflow boundary.
Multi-source/lossless acceptance remains separately open. Dashboard Builder MVP
is now the selected preimplementation slice: its stack, contract/bundle, and UI
tests are red-first; its automated acceptance proves deterministic export,
clean import/versioned-child update, restoration, lineage, and PostgreSQL value parity; and
its final gate requires the real Catalyst/Superset/accessibility checkpoint.*

- **Real production paths — PASS**: The browser calls the deployed Catalyst
  Gateway, which composes the query flow, calls the real generic Hub role
  executor, and uses the selected PostgreSQL analytics database. Fixtures are
  scaffolding, not behavior evidence. The clean-pin live accessibility/user
  checkpoint is accepted for the MVP.
- **Deterministic reviewed transforms — PASS**: SQL parsing, finding
  classification, patch scopes, patch application, frozen-unit verification, and
  version digests live in reviewed code/contracts. Model patches remain proposals.
- **Record-level evidence — PASS**: Every execution records the exact query
  version, parameters, returned columns/rows or database error. G2.8c additionally
  records the reproducible PostgreSQL cross-check, dataset/session/turn/version
  IDs, inspected record identifiers and values, and a rationale for why those
  records demonstrate the requested behavior rather than relying on counts.
- **Metadata and provenance — PASS (staged)**: The first slice persists complete
  session events and model/profile/prompt/catalog/dataset/validator provenance.
  Compact turns retain profile/prompt references and digests; typed generation
  evidence retains full role prompts and one timing/digest record for every
  successful or failed invocation. The harness-integration slice materializes
  the same lineage as versioned `run_manifest.json` and `events.jsonl` artifacts.
- **Tests define behavior — PASS for implemented slices; acceptance open**:
  Hub, store/gateway, root-runtime, and UI red tests are separate prerequisites
  for their implementation tasks. Coverage
  includes atomic concurrent claims, crash-orphan recovery, non-mutating legacy
  timeline synthesis across model-current/human-current/draft-only/raw-only
  fixtures, newly recorded initial turns, shared follow-up/Validate/Run editor
  resolution, malformed output, parse/binding/semantic findings, selected-output/
  current-pointer integrity, stale and out-of-scope changes, successful/failed/
  timed-out/cancelled execution context, refresh, context-exclusion negatives,
  warning-bearing success, complete recorded invocation timings, and legacy
  null-plus-typed-omission behavior without invented provenance. The
  Gateway-owned refactor and multi-source path require their current clean-pin
  and live acceptance gates before release claims.
- **Data boundaries and governance — PASS for the single-source notebook;
  multi-source gate open**: PostgreSQL remains the clinical
  evidence source; SQLite stores only operating metadata and bounded execution
  evidence for the isolated demo. The G2.8 PCCP preserves the earlier
  Hub-owned implementation history. The Gateway-ownership refactor requires its
  own change record before T111 acceptance, and source onboarding requires a
  PCCP amendment before a new projection, overlay, curation, or generated
  catalog can be accepted.
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
├── followup-notebook-research.md
├── pccp/
│   └── 2026-07-18-iterative-query-notebook.md
└── contracts/
   ├── workbench-api.md
   ├── query-patch-v1.schema.json
   ├── catalyst-query-request-v2.schema.json
   ├── catalyst-query-revision-context-v1.schema.json
   ├── catalyst-workbench-editor-snapshot-v1.schema.json
   ├── catalyst-workbench-editor-snapshot-record-v1.schema.json
   ├── catalyst-workbench-turn-request-v1.schema.json
   ├── catalyst-workbench-turn-v1.schema.json
   ├── catalyst-workbench-turn-timeline-v1.schema.json
   └── catalyst-workbench-generation-evidence-v1.schema.json
```

### Source Code

```text
harness/
├── catalyst/validation.py        # real-path scenario runner and later importer
└── metadata.py                   # canonical run manifest/event writers

targets/catalyst/                 # pinned Catalyst submodule
├── catalyst-gateway/src/catalyst/
│   ├── analytics.py              # exact SQL execution + DB diagnostics
│   ├── query_profiles.py         # Gateway-owned query profile registry
│   ├── query_engine.py           # writer/lint/reviewer/finalize orchestration
│   ├── local_hub.py              # local engine/profile discovery adapter
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
└── docs/roadmap.md

targets/med-agent-hub/            # pinned sibling generic model runtime
├── server/generic_role.py        # POST /v1/hub/generate
└── tests/                        # generic-role transport/error contract checks

scripts/generate-catalyst-source-catalog.py
                                  # live metadata + reviewed overlay → catalog
```

**Structure Decision**: Keep Catalyst query profiles, prompts, deterministic
query logic, writer/reviewer composition, workbench state, and execution in
Catalyst Gateway; keep provider/model transport and single-call serialization in
Hub; keep presentation in Catalyst UI; and keep experiment orchestration/artifact
validation in the umbrella harness. Hub's clinical-answer/report profile engine
remains separate. The existing governed preview endpoints remain compatible; the
workbench receives a separate API so advisory manual execution cannot weaken
governed behavior. The umbrella runtime builds its pinned sibling Hub checkout;
Catalyst may bootstrap an unmodified clone at the identical pinned commit only as
a standalone fallback.

## Delivery Slices

1. **Manual workbench MVP**: compact dataset disclosure, persistent sessions,
   immutable query versions, PostgreSQL-aware SQL/parameter editing with line
   numbers, wrap control, catalog/keyword completion and deterministic Format,
   advisory validation, exact-draft execution, database diagnostics, and refresh
   restoration. A selected Gateway profile produces one complete writer
   candidate and deterministic lint. Writer-only profiles finalize that candidate
   when it passes; reviewed profiles pass the complete candidate and findings to
   their declared reviewer. The comparative profile uses a different model
   family. Any correction is linted again, and both valid model-authored versions
   remain immutable and inspectable.
2. **Iterative query notebook**: append-only turns, exact editor snapshots,
   contextual complete-query generation, compact prior-turn inspection,
   per-turn profile selection, stale-base rejection, failure recovery, and
   refresh restoration. Unchanged buffers reuse the current immutable version;
   unresolved buffers remain exact turn inputs without being promoted to valid
   query versions. New sessions record initial requested/terminal events and
   typed generation evidence; pre-event sessions use deterministic read-only
   legacy projection. One shared resolver applies unchanged/dirty rules and
   active-turn provenance to follow-up, Validate, and Run. The compact timeline
   links to typed generation detail at
   `GET /sessions/{sessionId}/turns/{turnId}/generation-evidence`.
3. **Targeted remediation**: AST repair units, deterministic fixes, a
   Gateway-owned typed proposal/orchestration contract using Hub only for a
   generic role call, frozen-unit verification, before/after review, full
   revalidation, and sibling runtime verification.
4. **Harness integration**: one-click `run_manifest.json`/`events.jsonl`
   materialization, importer/contract tests, and expanded repeatable suites.
5. **Experiment iteration**: richer datasets and scenario matrices across
   Gateway query profiles/models. Agent teams remain explicitly deferred.
6. **Multi-source/lossless onboarding**: source registry and per-turn selection,
   per-source catalog baselines, upstream-default lossless projections,
   deterministic SQL curation, generated catalogs, default-readiness disclosure,
   and real two-source acceptance. Existing code is an implementation candidate,
   not accepted evidence.

### Current ownership-refactor and source-onboarding order

1. Keep the historical G2.8 plan and evidence intact; record the ownership
   change in a separate PCCP rather than rewriting the earlier run as if it used
   the current architecture.
2. Prove Hub's generic role endpoint and absence of Catalyst query logic in Hub;
   prove Gateway profile discovery, prompt/config digests, writer-only behavior,
   reviewed behavior, and deterministic re-lint.
3. Run the full Catalyst/Hub/harness gates and T094/T095/T111 live workflow on
   exact current pins. Complete the accessibility matrix and pause for acceptance.
4. Separately audit every registered source's ViewDefinition provenance,
   multiplicity, curated SQL/comments, overlay, generated catalog, and live
   information-schema agreement.
5. Exercise one session across two real analytics sources, including A → B →
   inherited B → A, unavailable-source rejection, per-source stale baselines,
   refresh, exact query execution, and record-level PostgreSQL checks. Pause at
   the new source-onboarding user checkpoint before declaring multi-source
   acceptance.

### G2.8 test-first implementation order

1. Establish the preimplementation PCCP and complete the final written-artifact
   reanalysis/user gate.
2. Land failing Hub tests before the v2 request, prompt, lint, reviewer, profile,
   timing, or pipeline changes. The Hub implementation owns an offline-resolvable
   bundle containing request v1/v2, revision context, editor snapshot, turn
   request, and all transitive schema references.
3. Land failing store tests before recorded initial turns, legacy projection,
   shared editor resolution, the atomic one-active-turn projection, and orphan
   recovery; land failing gateway/context/route tests before the bounded context
   builder, schema/detail publication, or orchestration routes.
4. Land a failing root harness runtime test before wiring the sibling Hub build;
   only after that wiring is proven retire Catalyst's disposable Hub patch and
   retain an unpatched same-commit standalone fallback.
5. Land failing UI tests, but do not implement the UI until the Hub/backend/store/
   root schema and contract-drift checkpoint passes. Then implement the UI and
   pass the post-UI full gate.
6. Run diverse automated real-path cases and the G2.8c live/user checkpoint;
   only afterward update user-facing status, root README, PCCP evidence,
   commits, and submodule pins.

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
9. **G2.5 — Generator binding normalization (corrective internal gate)**:
   Relax only the model-facing parameter-name/source requirement. Deterministic
   post-processing pairs unnamed parameter values with SQL placeholders in their
   existing order and defaults missing source metadata, without a name-only LLM
   retry. A count mismatch remains an editable unresolved draft. Re-run the exact
   12B case through the real database and report SQL, execution, and result
   correctness separately.
10. **G2.6 — Writer–reviewer collaboration (corrective internal gate)**: Replace
   generator self-patching with one complete writer candidate, deterministic
   findings, a complete corrected candidate from a different reviewer-model
   family, and deterministic re-lint. Persist both linked query versions and
   expose role/model/finding traces in the workbench. Re-run the exact 12B case
   with Gemma 4 12B writing and Qwen 2.5 14B reviewing.
11. **G2.7 — Manual reset controls (corrective internal gate)**: Keep New
   session and Clear draft separate, preserve retained server evidence, restore
   focus to the canonical question input, and prove both controls in the live
   isolated browser.
12. **G2.8a — Iterative-notebook written plan (user gate)**: Update the feature
   research, specification, plan, data model, contracts, tasks, quickstart,
   roadmap, and issue register; run read-only cross-artifact analysis; resolve
   every CRITICAL/HIGH finding; rerun the analysis; then pause for user review
   before product code. The final clean reanalysis is recorded in `roadmap.md`;
   user acceptance remains the only open G2.8a gate.
13. **G2.8b — Turn contract and deterministic foundation (internal gate)**:
   Historical gate for the then-current Hub-owned query engine. It landed
   subsystem-specific red tests and then the atomic append-only turn
   projection, recorded initial turns, four-fixture legacy synthesis, shared
   follow-up/Validate/Run resolver with active-turn provenance,
   one-active-generation claim, orphan recovery, stale-base and exact snapshot/
   current-anchor rules, bounded context and failed/timed-out/cancelled
   diagnostics, typed generation-evidence detail, registered Hub/workbench
   schemas and the Hub's offline dependency bundle, explicit lint instruction,
   an always-invoked reviewer with lint-clean semantic correction, complete
   per-invocation timing/digests, compact prompt references with full prompts in
   evidence detail, typed legacy omissions without invented provenance,
   selected-output invariant, sibling-Hub runtime wiring, and a lightweight
   new-event-to-`events.jsonl` mapping assertion. Pass this backend contract-
   drift checkpoint before UI implementation.
14. **G2.8c — Live iterative notebook (user gate)**: In the isolated browser,
   prove narrowing, aggregation/output-shape change, unresolved correction,
   lint-clean semantic reviewer correction, and Hub/tool failure through initial
   generation, manual edit, Validate/Run, follow-up, successor Run, and refresh.
   Retain typed generation evidence, exact model/context traces, record-level
   PostgreSQL cross-checks, conditional digest differences when model outputs
   differ, and full keyboard/narrow/200%-zoom evidence. Measure initial submit
   through successor visibility against the under-three-minute target after
   subtracting only exact recorded `durationMs` values for every initial/follow-
   up invocation and reconciling them to the typed timestamps and digests; report
   wall time and Run/database time separately. Pause before closing G3 or
   beginning W2/W3.
15. **G2.10a — Multi-source/lossless written gate (internal)**: Trace the
   multi-source amendment to user scenarios, FR-064–FR-070, SC-030–SC-034,
   source/catalog entities, tasks, quickstart checks, PCCP scope, and roadmap
   checkpoints. Inventory existing implementation without marking acceptance.
16. **G2.10b — Source implementation and real-path gate (internal)**: Prove
   source-registry and per-turn inheritance contracts; per-source stale
   baselines; unavailable-source failure before model/database calls; upstream
   ViewDefinition provenance and repeated-coding losslessness; deterministic SQL
   curation/comments; catalog-generation failure modes and byte stability; live
   information-schema agreement; and default-readiness scope.
17. **G2.10c — Two-source acceptance (user gate)**: Run A → B → inherited B → A
   in one clean session across two independently provisioned analytics
   databases, retain source/catalog/version/turn/execution provenance, compare
   each successful query independently in PostgreSQL with record-level evidence,
   refresh the session, and pause for user acceptance. Do not infer this pass
   from existing plumbing or unit tests.
18. **G4 — Targeted-remediation design validation (user gate)**: Re-run artifact
   analysis after incorporating W1 evidence; review repair-unit coverage,
   nondeterministic model behavior, and deterministic fallback cases with the
   user before enabling model-authored patches.
19. **G5 — W2 remediation evidence (user gate)**: Report frozen-unit integrity,
   stale/out-of-scope rejection, and the seeded 90% single-finding metric. Decide
   with the user whether results justify W3 harness export or more repair work.
20. **G6 — Harness experiment readiness (user gate)**: Validate artifact schemas,
   provenance, scenario diversity, and profile/model identity before making any
   comparative model claim.

## Nondeterminism and Inconsistency Register

The following items must remain visible until evidence resolves them:

- **N1 — Model sampling (bounded, still open for experiments)**: The canonical
  router advertises temperature 0, seed 42, context 24,576, and its full launch
  preset; Catalyst query roles override the router-wide DRY repetition penalty
  to zero. Gateway profile and invocation evidence records declared/effective
  role configuration around each generic Hub call. A single successful run is
  not repeatability evidence, so
  comparative runs still require repetitions and variance reporting.
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
- **N7 — Documentation drift (partly resolved; target docs still open)**: The
  feature artifacts now distinguish current Gateway-owned query orchestration
  from historical Hub-owned evidence. Catalyst's submodule README/specification/
  roadmap/client-contract still describe Hub-owned query profiles and must be
  updated in Catalyst PR #5 without rewriting historical validation claims.
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
- **N12 — Concurrent execution idempotency (resolved by T108)**: Workbench
  execution uses an atomic lease/claim and focused concurrency tests; retain this
  item as the historical reason the merge-readiness remediation was required.
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
- **N24 — Binding validity versus query correctness (open at G2.5)**: Missing
  generated names currently prevent catalog/SQL lint from evaluating the
  candidate. Generator-facing optional names plus ordered pairing should expose
  downstream errors, but a schema-valid or executable query is
  not automatically the right query. Real validation must report catalog/view
  correctness, execution outcome, and returned-data semantics separately.
- **N25 — Reviewer starvation (resolved at G2.6)**: One complete writer
  candidate and its deterministic findings now reach the reviewer without
  writer self-patching.
- **N26 — Correlated query roles (resolved at G2.6)**: The checked profile uses
  physically distinct Gemma 4 12B writer and Qwen 2.5 14B reviewer artifacts
  and preserves both router-advertised identities.
- **N27 — Duplicate unchanged versions (resolved by G2.8b)**: Validate, Run, and
  follow-up reuse the current version whenever the exact editor content is
  unchanged and snapshot only actual changes.
- **N28 — Seeded inference variance (open, bounded)**: Repeated temperature-zero,
  seed-42 runs produced identical SQL/results but different nullable metadata.
  The current-pin 2026-07-30 matrix added one concrete SQL spelling variance:
  two aggregation repetitions used `COUNT(*)` and one used
  `COUNT(observation_id)`. Independent PostgreSQL checks proved identical
  result semantics. Every turn retains full candidates and digests; acceptance
  reports semantic/result agreement separately from byte identity.
- **N29 — Follow-up context discontinuity (resolved by G2.8b)**: Bounded current
  SQL, prior instructions, and exact-digest validation/execution summaries reach
  later query roles; prohibited context remains excluded.
- **N30 — Duplicate Hub runtime ownership (resolved; architecture later
  superseded)**: G2.8 retired the disposable patched Hub and made the harness
  sibling the runtime source. The later refactor moved Catalyst query profiles
  and orchestration into Gateway while retaining the sibling Hub as the generic
  role executor.
- **N31 — Context growth and truncation (bounded by contract)**: Revision
  context includes the initial question plus at most five most recent follow-up
  instructions, exact current editor state, and exact-digest feedback. The turn
  records the supplied IDs and deterministic omissions; raw result rows and
  historical SQL copies are excluded.
- **N32 — Lint-clean semantic review restriction (resolved by G2.8b)**:
  Reviewed Gateway profiles invoke their reviewer even when structural lint is
  clean and permit approval or a complete correction followed by deterministic
  re-lint.
- **N33 — Intent-sensitive lint input gap (resolved by G2.8b)**: Lint receives
  the effective turn instruction explicitly and tests both initial and revision
  behavior.
- **N34 — Interrupted requested turns (resolved by G2.8b)**: A process can stop
  after `query_turn.requested` but before a terminal event. On recovery the store
  appends one terminal failure with stage `orphan_recovery` and code
  `generation_interrupted`, releases the atomic claim, preserves the base/current
  anchor—effective when non-null, otherwise observed when present, otherwise
  null—and never retries inference automatically.
- **N35 — Selected output/current pointer drift (resolved by G2.8b)**: A
  completed reviewed profile may contain writer and reviewer artifacts. Contract tests
  require a recorded completed turn's `selectedVersionId` to name exactly one
  produced version and the session current pointer to match it. A synthesized
  legacy completed turn instead selects only its last attributable initial model
  output while the timeline current pointer may be a later human version. A
  reviewer failure leaves a contract-valid writer immutable but unselected and
  the base/current anchor current; invalid/parseable candidates remain
  diagnostics rather than versions.
- **N36 — Real-path coverage depth (bounded by G2.8c plan)**: A single aggregate
  success cannot establish iterative behavior. The gate requires narrowing,
  output-shape change, unresolved correction, lint-clean semantic correction,
  and Hub/tool failure, with record-level PostgreSQL evidence and rationale.
- **N37 — Interactive latency (open for G2.8c)**: Initial-question submission
  through successor-query visibility targets under three minutes after
  subtracting only each recorded initial/follow-up invocation's exact
  `durationMs`. Evidence reconciles each duration to role/stage/attempt/model,
  `startedAt`/`endedAt`, and request/response-or-failure digests, and also retains
  unadjusted wall time; explicit Run and database time are secondary and not part
  of the primary threshold.
- **N38 — Editor-resolution divergence (resolved by G2.8b)**:
  Follow-up, Validate, and Run can otherwise disagree about unchanged versus
  dirty content and append duplicate human versions. One store-owned resolver
  applies the same classification/current-pointer rules and attaches the active
  turn ID to every promoted human version.
- **N39 — Initial versus legacy turn provenance (resolved by G2.8b)**:
  New sessions need recorded initial requested/terminal events; synthesis is only
  for pre-event sessions. Deterministic fixtures cover model-current, later-human-
  current, draft-only, and raw-only evidence without mutating state, inventing
  prompt/model/config/timing/digest provenance, or confusing initial selection
  with the actual current pointer. Legacy terminal time is the selected initial
  output time, otherwise raw/generation-outcome time, otherwise session creation.
- **N40 — Public generation-evidence and schema drift (resolved for G2.8;
  refactor compatibility rechecked at T111)**: Gateway publishes the workbench
  turn/snapshot/evidence schemas; compact turns carry prompt references/digests
  and each turn exposes full typed invocation evidence through a stable GET
  route. The current Gateway-owned engine must preserve that contract at T111.
- **N41 — Execution diagnostic status coverage (resolved by G2.8b)**:
  Revision context describes failed, timed-out, and cancelled executions, but
  planning previously tested only generic failure. The bounded sanitized
  diagnostic and no-row invariant now cover all three terminal statuses.
- **N42 — Event export compatibility (bounded by G2.8b; W3 still open)**: W3 export
  remains deferred, but new initial/follow-up turn, snapshot, and generation-
  evidence events must map without loss into the existing versioned
  `events.jsonl` envelope. A lightweight backend assertion catches drift without
  implementing export early.
- **N43 — Reviewer contract and semantic drift (open; observed live)**: The
  initial Qwen 2.5 14B review omitted required `checks`; later corrections
  repaired syntax but changed base semantics. The manual POC adds at most one
  reviewer-only contract correction and never reruns the writer. Preservation of
  base meaning remains a measured model-quality requirement, not an assumption.
- **N44 — Valid SQL rejected by POC policy (resolved for the manual POC)**: The live
  `ROW_NUMBER() AS rn` correction was rejected because `rn` was treated as an
  unknown catalog column and `rn = 1` as a forbidden literal. For this research
  phase, valid derived aliases and predicate literals are allowed; named
  parameters remain encouraged without blocking otherwise valid SQL. Focused
  and full Hub/Gateway coverage now enforces that boundary.
- **N45 — Typed evidence projection drift (partly resolved; naming ambiguity open)**: Live
  evidence exposed false-empty top-level history, stale evidence digests inside
  query-version provenance, a lost failed-review Hub trace, two differently
  defined values called `profileDigest`, and incomplete candidate/prohibited-
  class projection. History, immutable evidence digests, failed Hub provenance,
  candidates, and prohibited classes are now projected deterministically. The
  Gateway profile-selection digest and Hub profile-configuration digest remain
  semantically different values with confusingly similar names and must be
  disambiguated before final acceptance.
- **N46 — Successor preservation and stable ordering (open)**: A reviewer
  correction for “change only the sort order” removed `LIMIT 25`, changing the
  returned dataset, and equal sort keys have no stable tiebreaker. Independent
  PostgreSQL checks distinguish executable SQL from intent preservation; the
  next validation iteration must measure both explicitly.
- **N47 — Interactive timing sample (partly resolved; successful successor still open)**: The
  first live initial-request-to-successor window was 343,978.959 ms; subtracting
  all six exact model invocations yielded 215,944.959 ms, missing the target by
  35,944.959 ms. About 213 seconds were deliberate manual pauses and recorded
  non-model turn overhead was about 2.931 seconds. A fresh initial turn recorded
  70,328.495 ms event-wall time, 69,553 ms of model time, and 775.495 ms of
  non-model turn overhead. A fresh failed follow-up recorded 80,185.101 ms,
  79,399 ms of model time, and 786.101 ms of non-model turn overhead. These
  reconcile cleanly, but a successful selected successor is still required for
  the full threshold claim; browser polling delay is not platform processing.
- **N48 — Narrow sticky composer reachability (resolved)**: The first 390 px
  browser check hid the sticky jump. The canonical Refine control now remains
  visible and keyboard-focusable at compact widths, introduces no duplicate
  editor or horizontal overflow, and focuses the real follow-up composer.
- **N49 — Post-UI gate drift (resolved)**: Ruff formatting, a duplicate schema
  `$id` with divergent optional evidence definitions, and the sole Playwright
  spec's retired preview flow blocked T093. Formatting and schema copies are now
  aligned, and Playwright exercises the notebook/workbench path.
- **N50 — Rejected-response serialization crash (resolved)**: A reviewer repair
  with location-bearing lint findings caused the Hub's rejected payload to fail
  its own schema and surface as HTTP 500, erasing typed invocation evidence.
  Optional positive `line`/`column` fields are now normative diagnostics; the
  same path returns HTTP 200 with structured `rejected` evidence and preserves
  both model candidates and invocation timing/digests.
- **N51 — Explicit SQL LIMIT mislabeled as result truncation (resolved)**: The
  manual executor marked a complete 25-row `LIMIT 25` result as truncated even
  though the Gateway cap was 100. Manual execution now reports truncation only
  when the configured fetch cap actually omits rows; legacy behavior is unchanged.
- **N52 — Model identifier corruption on contextual edits (resolved for the
  query profiles; continue monitoring)**: The failing runs inherited the
  router-wide DRY repetition penalty (`0.8`), which is suitable for prose but
  penalized exact repeated SQL tokens such as `t1.` and `_v1`. Gateway query
  profiles now require `dry: 0`, and Hub forwards that generic invocation
  setting; deterministic lint remains unchanged. A
  fresh Gemma 4 12B/Qwen 2.5 14B run preserved the full base query and selected
  the requested `ORDER BY t1.observed_at DESC` successor. Model outputs remain
  nondeterministic evidence, so broader scenario coverage stays open.
- **N53 — Per-turn profile choice (implementation resolved; live refactor
  acceptance open)**: Gateway now defines five configured revision-capable query
  profiles, including three writer-only choices and two reviewed choices
  (self-reviewed Q4 and cross-family 12B/Qwen). `LocalHub` derives the available
  subset from Hub's versioned router inventory; a configured profile is not
  presented as runnable unless every exact required alias is advertised. T111
  must prove discovery, switching, negative unavailable selection, and
  provenance on current pins before this is treated as accepted live behavior.
- **N54 — Standalone fallback contract drift (resolved; architecture
  superseded)**: The disposable patch/duplicated runtime source remains retired.
  Current Catalyst owns its query contracts and orchestration, while both the
  umbrella runtime and Catalyst's standalone fallback use the same unmodified
  generic Hub revision. T111 rechecks exact committed pins before acceptance.
- **N55 — Active-session surfaces are vertically fragmented (open; G2.9)**: The
  live page is about 7,859 CSS pixels tall and separates the follow-up composer,
  editor, actions, results, evidence, and history by several viewports. The
  current jump control focuses only the composer. G2.9 replaces the duplicate
  disabled initial form and scattered actions with one reusable Ask/Refine
  composer, one SQL editor, compact chronology, bounded results, and a responsive
  bottom workbench dock.
- **N56 — “Based on results” has two meanings (user decision required)**: The
  current exact-digest context includes execution status, column schema, row
  count, timing, and diagnostics, but deliberately excludes returned values.
  G2.9 will disclose this accurately. Value-level follow-ups require an explicit,
  bounded result attachment and would reverse the approved G2.8 exclusion; no
  silent row sharing will be introduced without the checkpoint decision.
- **N57 — Supported catalog omits half of the physical fact-view columns (open;
  G2.9)**: The editor/model catalog exposes 8 fields while the live approved
  `analytics.lab_result_fact_v1` has 16. The same runtime catalog must become the
  source for model grounding, completion, and the user-facing schema guide, with
  a live information-schema drift check.
- **N58 — Database permissions exceed the reviewed product catalog (open;
  intentional boundary)**: The read-only role can SELECT seven business
  relations, while only the fact view has reviewed query semantics. G2.9 proposes
  the completed 16-column fact view as the supported surface and labels manual
  execution as database-role governed. Advertising all seven relations requires
  a separate reviewed catalog decision.
- **N59 — Optional Patient display text erased structured names (resolved;
  superseded)**: `patient_flat_v1.name_display` read only optional FHIR
  `HumanName.text`, while OpenELIS populated `given` and `family`. The
  projection preserved explicit text and fell back to the structured
  components; 96/96 refreshed patients had nonblank display names. This
  hand-written single-select projection approach was later superseded
  entirely by the lossless-defaults-plus-SQL-curation architecture (see the
  spec's multi-source Clarifications session, 2026-07-22): `patient_flat` is
  now the upstream default view verbatim, with no `name_display` column —
  curation happens in `analytics/sql/001_analytics_v1.sql` instead of in the
  ingestion projection.
- **N60 — Full seed wrapper assumed a JSON backfill body (resolved by T109)**:
  The wrapper now accepts an empty body from an otherwise successful backfill
  endpoint, while the supported Data Pipes run and complete health/provenance
  gate remain authoritative.
- **N61 — Final merged-pin rerun follows the strongest PR-head live run
  (accepted at T111)**: The merged component pins are Catalyst `e7eba21` and
  Hub `092b5cd`; the Harness
  evidence-receipt parent is `6f58d45`. Final-pin run `0671dc34` passed 12/12
  plus PostgreSQL/gold checks,
  and `fb6377c1` passed the bounded failure and same-session recovery. Actual
  keyboard/zoom inspection passed, the user accepted the MVP, and Catalyst
  source head `5f23c4e` (squash-merged as `e7eba21`) adds the deterministic E2E
  regression/focus-scroll correction. Post-merge run `70d76a43` passed 1/1 on
  the exact merged Catalyst/Hub pins with 2/2 PostgreSQL checks and 2/2 gold-
  result comparisons.
- **N62 — Multi-source/lossless acceptance gap (open at G2.10)**: Registry,
  two-source UI, lossless projections, SQL curation, and generated-catalog code
  exist in the active change set, but the feature amendment previously had no
  traced requirements/tasks/checkpoint. FR-064–FR-070, SC-030–SC-034, and
  T116–T122 now define the missing proof; no acceptance is inferred from code
  presence.
- **N63 — Model inventory discovery/invocation race (bounded; monitor at
  T111)**: Router aliases may be advertised but load on demand, and availability
  can change after discovery. Gateway fails closed when the versioned inventory
  cannot be verified and never substitutes a missing model; an invocation-time
  change remains a truthful bounded transport failure recorded in generation
  evidence. T111 records any observed race rather than treating discovery as a
  reservation.

## Complexity Tracking

No constitution violations are required by this plan.
