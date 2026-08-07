# PCCP-style Change Record: Iterative Query Notebook

**Status:** Implemented and accepted for the manual MVP on 2026-08-04

**Date:** 2026-07-18
**Reviewer decision:** The project owner approved the G2.8 artifact-first,
linear follow-up plan. This record is established before any related Hub
profile, prompt, pipeline, gateway, UI, or runtime product change.

## Modification and rationale

The workbench persists the initial question, immutable query versions,
validations, executions, and model evidence, but a later Hub call receives only
a new standalone question. Submitting that question starts another session.
The running Hub is also a Catalyst-owned disposable clone plus patch rather than
the sibling Hub pinned by the umbrella harness.

G2.8 will add a linear query notebook in which one follow-up instruction derives
one complete successor query from the exact visible editor snapshot. It will:

1. add append-only requested/completed/failed turn evidence and an atomic
   one-active-generation claim per session;
2. pass a versioned, digest-bound revision context to the existing complete
   writer -> deterministic lint -> different-family reviewer -> deterministic
   re-lint pipeline;
3. allow the reviewer to correct a lint-clean but semantically wrong complete
   candidate without exposing hidden reasoning or returning a text patch;
4. retain a compact turn timeline, per-turn profile choice, stale result labels,
   exact failure evidence, and explicit New Session isolation; and
5. land the Catalyst query profile and revision path in the real Hub sibling,
   make that sibling the umbrella runtime source, and retire the Catalyst-owned
   patch.

New sessions record their initial requested and terminal events plus typed
generation evidence. Only pre-event sessions receive deterministic, read-only
legacy synthesis. A shared server resolver owns unchanged/dirty reconciliation
for follow-up, Validate, and Run, including the current pointer and active-turn
provenance. Compact turns resolve full authorized evidence through
`GET /sessions/{sessionId}/turns/{turnId}/generation-evidence`.

Timeline turns retain compact profile and prompt references/digests. Full role-
specific prompt text and one invocation record for every successful or failed
writer/reviewer call—including identity, stage/attempt, timing, request digest,
outcome, and response-or-failure digest—live only in typed generation evidence.

The bounded context contains the initial question, at most five preceding
follow-up instructions, exact current SQL/parameters and digests, catalog and
profile evidence, and only digest-matching validation or execution summaries.
It excludes returned rows, credentials, connection details, hidden reasoning,
raw traces, historical SQL copies, unrelated sessions, and a replayed chat
transcript.

## Controlled output and recovery invariants

- A recorded completed turn selects exactly one version returned by the Hub
  collaboration. Reviewer approval selects the writer version; reviewer
  correction selects its immutable `model_repair` child. The recorded session's
  current-version pointer must equal that `selectedVersionId`. A synthesized
  legacy completed turn is the explicit exception: it selects only its last
  attributable initial model output, while the timeline current pointer may be a
  later persisted human version.
- A rejected/failed collaboration selects no output and leaves its base/current
  anchor current: effective when non-null, otherwise observed when present,
  otherwise null. A contract-valid writer persists as an immutable but
  unselected output when review fails; contract-invalid or merely parseable
  writer/reviewer candidates remain diagnostic evidence and are never promoted.
- The request carries an observed CAS base and exact snapshot. Reconciliation
  reuses that version for an unchanged editor, creates and selects one human
  effective base for a dirty contract-valid editor, and keeps unresolved input
  only as a snapshot with no effective version.
- The observed-version and editor digests are compare-and-set inputs. Concurrent
  follow-ups allow exactly one atomic claim; the other returns
  `turn_generation_in_progress` without an event or model call.
- On service recovery, a requested turn with no terminal event is appended as
  one failure with stage `orphan_recovery` and code `generation_interrupted`, its
  active claim is released, and no inference is retried automatically. Its base/
  current anchor remains usable, including a human effective base created from
  dirty input.
- Synthesized legacy terminal time is the selected initial output time, otherwise
  the raw/generation-outcome time, otherwise session creation. Every unavailable
  prompt/model/config/timing/digest field is null with a typed omission; no
  provenance is inferred. Recorded evidence instead has complete required fields
  and an empty omissions list.

## Validation protocol

Implementation is test-first and remains blocked until the corresponding red
tests fail for the expected reason:

- Hub tests cover publication/registration of an offline-resolvable bundle with
  request v1/v2, revision context, editor snapshot, turn request, and all
  transitive references; explicit instruction linting; the reviewer call even
  when writer lint is clean; one typed identity/timing/digest record for every
  successful or failed model invocation;
  deterministic five-follow-up truncation, every prohibited-context negative,
  lint-clean semantic reviewer correction, complete selected-output behavior,
  tool/model failure, and full provenance.
- Gateway/store tests cover atomic claims, concurrency, crash-orphan recovery,
  recorded initial turns, requested/completed/failed projections, the shared
  follow-up/Validate/Run resolver and active-turn provenance, observed/effective/
  snapshot/current-anchor reconciliation, dirty/unchanged/unresolved bases,
  valid-but-unselected writer persistence, deterministic legacy model-current/
  human-current/draft-only/raw-only fixtures, bounded failed/timed-out/cancelled
  diagnostics, stable legacy timestamp precedence, null-plus-typed omissions
  without invented provenance, preservation of every Hub invocation timing/
  digest, compact timeline prompt references with full prompts only in evidence
  detail, stale conflicts, profile switching, typed generation-evidence detail,
  exact context selection, result staleness, refresh, and New Session isolation.
- A root harness test proves the isolated compose build uses sibling
  `targets/med-agent-hub` and does not apply the retired Catalyst patch. UI red
  tests cover the notebook timeline, editor ownership, recovery, focus, and
  responsive/accessibility behavior before UI implementation.
- Before UI implementation, the Hub/backend/store/root gate proves all Hub and
  workbench schemas are registered, and lightly asserts that new turn/snapshot/
  generation-evidence events map losslessly to the existing versioned
  `events.jsonl` envelope without implementing W3 export.
- Real-path validation covers narrowing, aggregation/output-shape change,
  unresolved correction, lint-clean semantic reviewer correction, and Hub/tool
  failure. Each successful data claim is independently checked in PostgreSQL
  with exact SQL/parameters, dataset/session/turn/version IDs, inspected record
  identifiers and values, and a written correctness rationale rather than
  counts alone.
- From initial-question submission through successor-query visibility, wall
  time minus only the exact recorded `durationMs` values for every initial/
  follow-up writer/reviewer invocation must be under three minutes. Each value is
  reconciled to its `startedAt`/`endedAt`, role/stage/attempt/provider/model,
  request digest, outcome, and response-or-failure digest. Unadjusted wall time
  and later explicit Run/database time are separate secondary measures. Keyboard-
  only, narrow viewport, and 200%-zoom passes are required.
- Repeated temperature-zero runs preserve distinct candidate and query digests
  when they differ; configured seed/temperature are not reported as proof of
  byte reproducibility.

## Impact, rollback, and residual risk

The governed preview API, explicit manual Run, read-only PostgreSQL boundary,
and existing immutable version contracts remain compatible. No follow-up runs
automatically. Rollback disables the turn routes/UI and restores the prior
single-question workbench while retaining append-only evidence. The umbrella
runtime may roll back both sibling pins together; Catalyst's standalone fallback
uses its own immutable, unpatched Hub pin and cannot restore the retired patch.

Residual risks are semantic agreement between two model families, inference
variance at temperature zero, model/tool availability, validator-scope drift,
and a live scenario failing the three-minute target. Any such outcome remains a
reported failed checkpoint, not a reason to weaken deterministic assertions.

## Evidence

The later Gateway-ownership record supersedes this plan's original Hub-owned
profile/orchestration placement without changing the artifact-first notebook
contract. On the reconciled merged-Hub pins, run
`0671dc34-26c6-4d52-8443-47e0a833a539` passed 12/12 real-model repetitions,
24/24 independent PostgreSQL comparisons, and 18/18 gold-result comparisons.
Run `fb6377c1-0b60-492a-8053-cc668a201d15` passed the expected one-shot Hub
failure and the next turn in the same session recovered, validated, executed,
and independently matched PostgreSQL. The PHI-safe accepted receipt is
`../evidence/t111-final-acceptance-2026-08-03.json`.

The user confirmed actual keyboard-only Tab traversal and actual browser 200%
zoom passed, accepted the observed reviewer-contract and compact-composer issues
as non-blocking future work, and authorized the merge sequence. A deterministic
Playwright regression now guards the accepted focus/reflow boundary and exposed
one fixed-composer Tab-scroll obstruction, which was corrected before merge.
Catalyst #5 is squash-merged and the Harness working tree is repinned to its
`main` commit; final Harness verification, approval, and squash remain tracked
by T112.
