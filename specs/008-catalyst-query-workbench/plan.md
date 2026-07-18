# Implementation Plan: Catalyst Query Workbench

**Branch**: `codex/catalyst-mvp-umbrella` | **Date**: 2026-07-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-catalyst-query-workbench/spec.md`

## Summary

Build a persistent manual query workbench around the real Catalyst → med-agent-hub
→ PostgreSQL path. The first delivery slice makes the complete generated SQL and
typed parameters editable, keeps deterministic validator findings visible but
advisory, executes the exact displayed draft under the database role, returns
useful database errors, restores the session after refresh, and collapses detailed
dataset context by default. The next slice constrains automated remediation to
versioned SQL AST units with frozen-unit digests. Harness artifact materialization
follows once the session event model is stable; the first slice still records all
lineage needed for that export.

## Technical Context

**Language/Version**: Python 3.11–3.13; TypeScript 6 / React 19

**Primary Dependencies**: FastAPI, psycopg 3, SQLGlot, jsonschema, Carbon React,
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

**Constraints**: Synthetic demo only; model inference remains in med-agent-hub;
manual execution is never gated by validator status; database permissions and a
read-only transaction remain authoritative; statement timeout and fetch bounds
must not rewrite SQL; no preview expiry; no new editor framework in the first slice

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
│       └── components/DatasetBrowser.tsx
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
   immutable query versions, direct SQL/parameter editing, advisory validation,
   exact-draft execution, database diagnostics, and refresh restoration.
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
5. **G3 — W1 integrated workbench (user gate)**: Run gateway/UI/Playwright/live
   checks, repeat the acceptance scenarios manually, audit exact-query digests,
   and have the user test the isolated browser before starting W2.
6. **G4 — Targeted-remediation design validation (user gate)**: Re-run artifact
   analysis after incorporating W1 evidence; review repair-unit coverage,
   nondeterministic model behavior, and deterministic fallback cases with the
   user before enabling model-authored patches.
7. **G5 — W2 remediation evidence (user gate)**: Report frozen-unit integrity,
   stale/out-of-scope rejection, and the seeded 90% single-finding metric. Decide
   with the user whether results justify W3 harness export or more repair work.
8. **G6 — Harness experiment readiness (user gate)**: Validate artifact schemas,
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

## Complexity Tracking

No constitution violations are required by this plan.
