# PCCP-style Change Record: Gateway-owned Query Orchestration

**Status:** Implemented candidate; clean-pin evidence and user acceptance pending

**Date:** 2026-07-29

**Governance timing:** This record was created after the ownership refactor was
implemented in the active component PRs, when roadmap reconciliation exposed
that the earlier G2.8 PCCP still described Hub-owned query profiles. It is a
retrospective implementation record, not a claim of preimplementation approval.
It is complete before T111 acceptance and before any component merge.

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

The candidate component revisions are Catalyst `bb36126` (PR #5) and Hub
`946afa9` (PR #15). Harness `2320bee` pins those exact revisions for the
current T111 evidence.

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

Current-pin runtime evidence is partially complete:

- Harness `2320bee` pins clean Catalyst `bb36126` and Hub `946afa9`.
- Run `85fadc7a-370c-4ec0-af0e-81ecc68d2115` passed 12/12 live repetitions
  across narrowing, dirty-base aggregation/profile switching, unresolved
  correction, and distinct-patient semantics. Every successful data claim
  matched independent PostgreSQL/gold execution.
- All role records retain `temperature: 0`, `dryMultiplier: 0`, and
  `maxTokens: 1024`. Aggregation produced one semantically equivalent
  `COUNT(observation_id)` variant among two `COUNT(*)` outputs.
- Run `5bf746e1-0f7f-4f67-8053-db994bfffdee` passed the bounded one-shot Hub
  transport failure; same-session recovery turn
  `c535bc2d-08b6-428c-ac2f-4e9e99538b6e` then completed without importing the
  failure payload.
- Component PR checks are green at these pins: Catalyst #5, Hub #15, and
  harness #37 are mergeable; harness approval and the documented final
  squash/repin order remain required.

T111 is still pending the current-pin live keyboard/narrow/200%-text
accessibility matrix and the explicit user decision. Do not merge from this
partial evidence.
