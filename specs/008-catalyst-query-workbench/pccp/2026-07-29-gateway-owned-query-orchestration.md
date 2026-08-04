# PCCP-style Change Record: Gateway-owned Query Orchestration

**Status:** Implemented candidate on reconciled pins; final live evidence and user acceptance pending

**Date:** 2026-07-29

**Governance timing:** This record was created after the ownership refactor was
implemented in the then-active component PRs, when roadmap reconciliation exposed
that the earlier G2.8 PCCP still described Hub-owned query profiles. It is a
retrospective implementation record, not a claim of preimplementation approval.
It was complete before T111 acceptance. Hub #15 has since merged; Catalyst and
Harness remain unmerged pending the final gate.

## Modification and rationale

The earlier notebook implementation placed Catalyst query profiles, prompts, and
writer/reviewer orchestration in Med-Agent Hub. That coupled a reusable model
runtime to one product's SQL catalog, validation policy, evidence shape, and
revision semantics.

The active refactor moves those product-specific responsibilities to Catalyst
Gateway:

1. `query_profiles.py` owns query profile IDs, role/model mappings, exact
   required model aliases, prompt references, and sampling/output configuration.
2. `LocalHub` derives point-in-time profile availability from Hub's versioned
   backend model inventory. It does not treat Hub's clinical profile list as
   Catalyst profile discovery and fails closed when inventory cannot be verified.
3. `query_engine.py` owns writer request construction, deterministic lint,
   optional reviewer correction, deterministic re-lint, finalization, and query
   evidence.
4. Med-Agent Hub exposes `POST /v1/hub/generate`, which executes one
   Gateway-selected structured model role. It does not select a Catalyst
   profile, inspect a catalog, lint SQL, call a reviewer, access PostgreSQL, or
   execute a query.
5. Hub's clinical-answer/report profiles remain a separate product surface and
   are not used as Catalyst query-profile discovery.

The merged revisions are Catalyst `e7eba21` (PR #5) and Hub `092b5cd` (PR #15);
the Harness evidence-receipt parent is `6f58d45`. The July 30
supporting evidence remains
attributed to Harness `e475d7a`, Catalyst parent `bb36126`, and Hub `198d5f6`;
it is not relabelled as final-pin evidence. Final live evidence ran at Catalyst
`9aa0e0f`; source head `5f23c4e`, squash-merged as `e7eba21`, adds only
accepted-status documentation, the deterministic keyboard/reflow E2E
regression, and the focus-scroll correction it exposed.

## Controlled behavior and invariants

- Unknown or unavailable Gateway query profiles fail closed; there is no silent
  profile or model fallback.
- Hub inventory must use
  `med-agent-hub.backend-model-inventory.v1`; every unique writer/reviewer alias
  required by a profile must be present in `advertised_model_ids`. An
  unreachable router catalog, missing/malformed inventory, or missing alias
  makes the profile unavailable before any event, preview, or model call.
- Writer-only, self-reviewed, and cross-family reviewed profiles remain
  distinguishable in discovery and evidence.
- Every model call records its selected profile, role, model,
  prompt/configuration digests, request timing/digest, outcome, and
  response-or-failure digest.
- A reviewer correction is a complete successor query and is deterministically
  re-linted. Partial JSON-pointer repair patches are not the orchestration
  contract.
- Manual Run remains explicit. The model runtime receives no database
  credentials and never executes SQL.
- Session, turn, editor-snapshot, immutable-version, validation, execution, and
  stale-result behavior remain Catalyst contracts.
- Historical G2.8 evidence remains labelled with the architecture and exact pins
  that produced it; it is not relabelled as current-refactor evidence.

## Validation protocol

Before acceptance:

1. Run Hub's full unit/contract suite and prove the generic role request,
   structured-response, invalid-URL, timeout, and provider-error contracts.
2. Run Catalyst's Gateway, MCP, Agents, UI, and MVP-assembly gates. Prove profile
   discovery, writer-only behavior, self/cross-family review, complete correction,
   re-lint, provenance, exact required-alias matching, versioned-inventory
   handling, and fail-closed unknown/unavailable profiles.
3. Run umbrella pin/provenance and metadata-contract checks from a clean clone or
   worktree using the committed component SHAs.
4. Recreate the isolated stack from the persistent umbrella worktree. Exercise
   the initial question, exact editor/manual version, Validate, Run, contextual
   follow-up, successor Run, refresh restoration, failure retention, profile
   switching, and New Session isolation.
5. Use the Gemma 4 12B writer and Qwen 2.5 14B reviewer lane where available.
   Inspect exact role/model/configuration evidence and independently compare
   successful results with PostgreSQL at record level.
6. Repeat the scenario matrix, report candidate/query digest variance, complete
   keyboard-only, narrow-viewport, 320 px, and 200%-text checks, then pause for
   explicit user acceptance.

The pre-refactor live matrix is supporting historical evidence only. T111 is the
authoritative clean-pin acceptance run for this change.

## Impact and rollback

The public workbench and immutable-evidence contracts remain the compatibility
boundary. The internal owner of query orchestration changes, and Hub gains a
generic single-role endpoint.

Rollback is coordinated:

- repin Catalyst and Hub to the last mutually compatible pre-refactor revisions;
- rebuild both components from those pins;
- retain append-only session/run evidence rather than rewriting it; and
- do not mix a Gateway-owned Catalyst revision with a Hub revision that lacks
  the generic endpoint.

No database migration rollback or clinical-data rewrite is required.

## Residual risk and nondeterminism

- Temperature zero and a configured seed do not guarantee byte-identical model
  output. Repetitions record candidate/query digests and judge semantic/result
  agreement separately.
- A generic runtime boundary can still drift in response-format, timeout, or
  provider-error semantics; component contract tests and the exact-pin stack
  check remain required.
- Discovery and invocation are separate operations. A model advertised during
  profile discovery may become unavailable before generation; invocation must
  preserve a truthful bounded transport failure rather than silently substitute
  a profile or model.
- Different writer/reviewer families can agree on structurally valid but
  semantically incorrect SQL. Deterministic lint is an early signal, not a
  correctness oracle; live PostgreSQL comparison remains authoritative.
- The active changes also contain multi-source/lossless-ingestion plumbing.
  That work has a separate G2.10 gate and is not accepted by T111 unless its own
  T117–T122 evidence is completed.

## Evidence

The following July 30 PR-head evidence remains valid supporting evidence. The
reconciled final-pin live rerun is now complete; the manual accessibility/user
checkpoint remains pending:

- Harness `e475d7a` pins clean Catalyst `bb36126` and Hub `198d5f6` for the
  complete live matrix. Catalyst candidate `95515a2` subsequently aligns the
  standalone fallback Hub SHA; focused umbrella pin/layout coverage passes
  57/57. Clean umbrella `93689d5` run
  `4dd70443-ba23-4415-b0cd-d393d2352061` passed a scoped 1/1 real-model/
  PostgreSQL narrowing smoke at Catalyst `95515a2` and Hub `198d5f6`.
- Catalyst `be3f95c` changes no runtime code. The exact MVP assembly CI command
  completes 38 tests with one expected local `psycopg` skip.
- Run `cbc41bcd-56f7-4074-931f-98ed42fea202` passed 12/12 PR-head
  live repetitions across narrowing, dirty-base aggregation/profile switching,
  unresolved correction, and distinct-patient semantics. Every successful data
  claim matched independent PostgreSQL/gold execution.
- All role records retain `temperature: 0`, `dryMultiplier: 0`, and
  `maxTokens: 1024`. Aggregation produced one semantically equivalent
  `COUNT(observation_id)` variant among two `COUNT(*)` outputs.
- Run `68da21db-2178-4010-9fd4-5c73fd477261` passed the corresponding PR-head
  bounded one-shot Hub transport failure. Failed turn
  `856d88bf-c03f-408b-8867-04239925d191` preserved the current human base;
  same-session recovery turn `bbd77610-2660-4ae8-84fa-6dffe57d760e` then
  completed without importing the failure payload.
- Responsive inspection passed at 390 × 844 and 320 × 844 with no horizontal
  overflow. A 640 × 720 CSS layout-equivalent check covered 200%-zoom reflow
  geometry. At this PR-head checkpoint the automation surface could not advance
  keyboard focus or browser zoom; those actual manual checks were completed and
  accepted at the final-pin checkpoint below.

The definitive final-pin run is now complete. Run
`0671dc34-26c6-4d52-8443-47e0a833a539` passed 12/12 real-model repetitions,
24/24 independent PostgreSQL comparisons, and 18/18 hand-authored gold-result
comparisons. Run `fb6377c1-0b60-492a-8053-cc668a201d15` passed the one-shot
Hub transport failure; its same-session recovery then generated a contract-valid
successor and passed validation, execution, and an independent PostgreSQL
record-digest check. The accepted PHI-safe receipt is
`../evidence/t111-final-acceptance-2026-08-03.json`.

Two observed model facts remain visible rather than normalized away:
temperature-zero aggregation produced two correct selected query digests, and
the live checked-profile browser turn retained a valid Gemma writer output after
the Qwen reviewer returned a contract-invalid repair response with a spurious
test-name concern. Compact responsive geometry passes without horizontal
overflow or covered focus targets, but the fixed composer remains 336 px tall.

On 2026-08-04 the user confirmed actual keyboard-only traversal and actual 200%
browser zoom passed, accepted the model/UX observations as non-blocking future
work, and accepted the MVP. The deterministic Playwright path now guards
uninterrupted focus and 200%-equivalent reflow; it exposed and drove correction
of an expanded-composer focus obstruction. T111 is complete. Hub #15 and
Catalyst #5 are merged; the harness is pinned to those `main` commits and must
be approved and merged under T112. Post-merge health/provenance passed, and run
`70d76a43-d687-4f2a-afe6-e23ca75fe6df` passed 1/1 with 2/2 independent
PostgreSQL checks and 2/2 gold-result comparisons.
