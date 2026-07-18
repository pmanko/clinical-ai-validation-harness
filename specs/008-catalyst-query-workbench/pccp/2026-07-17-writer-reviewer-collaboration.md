# PCCP-style Change Record: Writer–Reviewer Query Collaboration

**Status:** Validated on the isolated real stack

**Date:** 2026-07-17
**Reviewer decision:** The project owner approved replacing generator
self-patching with a complete-query collaboration between distinct model
families for the MVP flow.

## Modification and rationale

The prior query pipeline asked the writer model to repair deterministic lint
findings with localized text/JSON patches. In the live Gemma 4 12B case, the
writer produced a useful complete candidate and deterministic lint identified a
missing aggregate alias, but two self-repair patches referenced SQL that was not
the retained candidate. The configured review role used the same model and did
not run until generation lint was clean, so the advertised roles did not
collaborate.

The approved MVP flow is:

1. one writer model returns one complete query candidate;
2. deterministic lint emits specific structured findings;
3. a reviewer from a different model family receives the question, catalog,
   complete writer candidate, and findings;
4. when correction is needed, the reviewer returns one complete corrected
   candidate rather than a fragile patch;
5. deterministic lint checks the reviewer candidate before finalization; and
6. Catalyst persists the writer and reviewer candidates as linked immutable
   `model` and `model_repair` versions with visible model/stage evidence.

For the real MVP checkpoint, `gemma-4-12b` is the writer and `qwen2.5-14b` is
the reviewer. This internal collaboration does not change the later W2
user-accepted, scope-frozen repair workflow.

## Validation protocol

- Hub tests prove one writer call, distinct writer/reviewer model IDs, complete
  reviewer correction, deterministic findings in the review request, strict
  result-contract validation, and deterministic re-lint rejection of an invalid
  reviewer candidate.
- Gateway tests prove the writer version is immutable, the reviewer correction
  is its `model_repair` child, both carry role/model/trace provenance, and both
  restore after refresh.
- UI tests prove both SQL/parameter artifacts, model identities, writer findings,
  reviewer decision/checks, and linked version details are inspectable without
  exposing hidden chain-of-thought.
- The real-stack checkpoint must use the advertised physical Gemma 4 12B and
  Qwen 2.5 14B identities, preserve both query digests, execute the final exact
  version against read-only PostgreSQL, and record returned rows or diagnostics.

## Impact, rollback, and residual risk

The change replaces the G2.3 self-patch retry only for the collaborative 12B MVP
profile. Existing manual editing, advisory validation, exact execution, database
permissions, and governed preview endpoints remain unchanged. Rollback restores
the prior 12B profile policy/model mapping and durable Hub patch; persisted query
versions remain valid evidence.

Residual risks are correlated errors despite model-family diversity, reviewer
full-candidate regressions that deterministic lint does not yet detect, validator
scope divergence between Hub and gateway, and model nondeterminism despite
temperature-zero/seeded routing. The two retained versions make those failures
inspectable; they do not establish semantic correctness by themselves.

## Evidence

- Hub: 327 tests pass, including the observed duplicated-reviewer-parameter
  regression, one-call writer/reviewer routing, full-candidate correction, and
  invalid reviewer re-lint rejection.
- Gateway: 90 tests pass and prove linked immutable writer/reviewer versions and
  restoration. UI: 64 tests, TypeScript, lint, and production build pass and
  expose both structured model artifacts without hidden chain-of-thought.
- Live API session `39f71423-1a3b-4dde-9996-943c6985ddd6` and trace
  `86b6f495-45b4-4afd-a9ef-71240ce5e820` record one Gemma 4 12B writer call,
  `output.projection_mismatch`, one Qwen 2.5 14B full correction, and a clean
  deterministic re-lint. Writer digest
  `7e75a31233aeee5076df9c2b812318bef040c59a6cdc0692863c2542292bdd75`
  and reviewer digest
  `b7b3db7e51cf4f06a24c8e21b367d181ba922ba9f39ec811d8c20a1e21e0d3c4`
  restore with their linked versions.
- Exact read-only execution `f5ccb870-f90d-4b1f-9f08-4c347b6ec703`
  returned typed integer `72`; an independent PostgreSQL query returned the same
  count. The in-app browser repeated the full flow and visibly returned 72.
- Residual N24 unit grounding, N27 duplicate unchanged-run versioning, and N28
  nullable-field nondeterminism are recorded in the roadmap for G3 decisions;
  none blocks manual evaluation of the collaboration flow.
