# Research: Iterative Query Notebook

**Date:** 2026-07-18
**Scope:** Lightweight G2.8a current-state and interaction review. This records
the decision before follow-up contracts or product code are changed.

## Current-state audit

Catalyst already has most of the durable evidence needed for iteration, but it
does not yet have a follow-up operation.

- The gateway's SQLite workbench store retains the initial question, selected
  profile, current version, immutable SQL/parameter versions with parent links,
  validation findings, executions, browser state, provenance, and append-only
  events. A normal refresh can therefore reconstruct saved work.
- The browser retains only the active session identifier. Unsaved editor text is
  component state; Validate and Run currently create a new human version, even
  if the buffer is unchanged. Version history is inspectable but cannot be used
  as a branch or restore point.
- Every question-form submission calls `POST /workbench/sessions`. It creates an
  unrelated session and replaces the browser's active-session pointer; there is
  no turn or follow-up endpoint.
- The gateway sends Hub one user message containing only the new question plus
  catalog, policy, profile, and correlation metadata in
  `catalyst.query.request.v1`. It does not send the active SQL, parameters,
  validation, execution evidence, or session history.
- The writer/reviewer pipeline already preserves complete linked candidates and
  deterministic lint evidence. Follow-up should extend this pipeline with a
  typed base artifact and current instruction, not introduce a parallel chat
  path or fragile SQL text patches.

Consequently, **saved state is not the same as model context today**. A user can
manually version a query, but cannot ask Hub to revise that version.

## Selected interaction

Use a **linear, artifact-first notebook**:

`initial question -> generated query -> manual versions -> follow-up -> complete successor query`

- Keep one active SQL editor and result area. Collapse earlier turns into a
  compact, read-only sequence that names the instruction and resulting query
  version.
- Put one `Refine Query vN` composer next to the active artifact. It identifies
  the exact base version and author/model and offers one explicit
  `Generate next query` action. An instruction and a related question use the
  same operation: each asks for one complete successor query.
- Use New Session for unrelated work. Do not add chat-only answers, an
  artificial refine/new mode choice, or arbitrary-version branching to this
  MVP.
- Keep the existing in-page jump control. With no active session it focuses the
  initial question; with an active session it focuses the one follow-up
  composer. Do not duplicate or float the editor.

This matches the user's unit of work: an executable SQL artifact and its result,
not an assistant message. Database copilots commonly ground assistance in the
active editor, while notebook systems keep code, output, and history together.
Immutable version history also makes rollback and comparison comprehensible.
Context-dependent text-to-SQL research supports carrying the previous query as
an explicit editing base rather than asking the model to rediscover it from an
undifferentiated transcript.

Sources:

- [Microsoft SSMS Copilot context](https://learn.microsoft.com/en-us/ssms/github-copilot/chat-context)
- [Hex Notebook Agent](https://learn.hex.tech/docs/explore-data/notebook-view/notebook-agent)
- [Databricks notebook version history](https://docs.databricks.com/aws/en/notebooks/notebook-version-history)
- [Editing-based SQL query generation for cross-domain context-dependent questions](https://aclanthology.org/D19-1537/)

## Exact base and bounded model context

The visible editor is authoritative, while the client's observed immutable
version is a separate compare-and-swap precondition. After that check, the
gateway reconciles an effective base: an unchanged buffer reuses the observed
version, a dirty contract-valid buffer becomes one current human version before
generation, and an unresolved buffer has no effective version. The exact
snapshot is retained and sent in every case; unresolved input is not
misrepresented as a valid query version.

This classification is one shared server-owned resolver for follow-up,
Validate, and Run. Unchanged submissions reuse the same version; dirty-valid
submissions create exactly one human version, make it current, and inherit the
applicable active turn ID. The three actions must not maintain separate notions
of dirty state or lineage.

Each follow-up request provides Hub only:

- the current instruction and exact base SQL, typed parameters, and expected
  columns;
- the observed CAS base, reconciled effective base, and exact editor-snapshot
  identifiers/digests;
- the initial question and at most the five most recent follow-up instructions
  in ancestry order;
- deterministic findings and the latest database diagnostic or compact result
  schema/count only when their query digest matches the exact editor snapshot;
- the catalog, policy, selected profile, model-role configuration, and
  correlation identifiers.

Do **not** send result rows, credentials, raw reasoning/traces, all historical SQL
copies, or an undifferentiated chat transcript. Rows are not needed to revise
the query and would increase privacy exposure, prompt size, and accidental
dependence on a truncated sample. Digest matching prevents stale validation or
execution evidence from being attributed to a newer editor buffer. The fixed
five-instruction window makes truncation deterministic and inspectable.

The writer returns a complete successor candidate. Deterministic lint receives
the current instruction explicitly, and the different-family reviewer is always
invoked—even when the finding set is empty—with the same revision context and
complete candidate. It may approve the writer or return one complete correction.
Final deterministic re-lint remains authoritative evidence; execution stays an
explicit user action.

## Failure and recovery

- Persist requested, completed, and failed turns in the existing append-only
  event ledger, and associate generated/human versions with a turn in
  provenance. A generation failure remains visible with raw evidence but does
  not replace or erase the last usable query.
- A completed collaboration selects exactly one produced version: writer when
  the reviewer approves, or the reviewer's immutable correction child when it
  changes the query. That selected ID and the session current pointer must agree.
  A failed turn selects nothing. A contract-valid writer remains an immutable
  but unselected output if review fails; contract-invalid or merely parseable
  candidates remain diagnostic evidence and never become versions.
- Bind the request to the observed version and exact editor digests. A stale tab gets
  the existing `409 stale_query_version` behavior instead of silently generating
  from the wrong base, and only one generation may be active per session.
- Claim the active generation atomically. If the service restarts after a
  requested event but before its terminal event, append one terminal failure
  with stage `orphan_recovery` and code `generation_interrupted`, release the
  claim, leave the base/current anchor current—effective when non-null,
  otherwise observed when present, otherwise null—and do not retry a model call
  automatically.
- Label results `Results from Query vN`. Once the editor changes or a successor
  is generated, retain the result but mark it stale.
- Clear Draft empties only the working buffer and offers `Restore Query vN`.
  New Session clears the active pointer and excludes all prior context.
- Refresh restores turns, the active saved version, validation/result evidence,
  profile, and presentation state without invoking a model.

New sessions record the initial question as requested plus one terminal turn;
they never depend on later synthesis. Read-only synthesis is limited to sessions
whose evidence predates turn events and is tested with model-current,
later-human-current, draft-only, and raw-only fixtures. The synthesized initial
selection remains distinct from the timeline's actual later current pointer.
Its terminal time is the selected initial output time, otherwise the raw/
generation-outcome time, otherwise session creation. Every unavailable prompt,
model, configuration, timing, or digest field remains null with a typed omission
rather than invented provenance. Repeated projection is stable and makes no
model call or mutation.

The compact timeline links to typed generation detail at
`GET /sessions/{sessionId}/turns/{turnId}/generation-evidence`. That response
contains the request/context/candidate digests, output dispositions, selection,
full role-specific prompts, profile/model/catalog/policy/dataset provenance, and
one exact timing/digest record for every successful or failed writer/reviewer
invocation without result rows, credentials, or hidden reasoning. Timeline rows
carry only compact profile/prompt references and digests. Recorded evidence has
no omissions; legacy gaps are explicit nulls plus typed omissions. Failed,
`timed_out`, and `cancelled` execution context is bounded, sanitized, and
included only when its query digest matches the editor snapshot.

## Runtime ownership inconsistency

The umbrella harness pins both `targets/catalyst` and sibling
`targets/med-agent-hub`, but the current MVP runner delegates to Catalyst's
bootstrap. Catalyst clones a disposable `.med-agent-hub` at commit
`7869c629...`, applies `patches/med-agent-hub/catalyst-query-profile.patch`, and
builds that patched clone. The pinned sibling is therefore not the Hub source
running in the isolated stack.

G2.8 resolves this by landing the profile/follow-up work in the real Hub sibling
and making the umbrella runner build that pinned source. Catalyst may retain a
standalone fallback at the same pinned commit, but the disposable patch and two
different effective Hub sources must be retired. Until that change lands, live
evidence must name the actual patched checkout rather than imply that the sibling
pin ran.

The preimplementation change controls, rollback, and evidence protocol are in
[`pccp/2026-07-18-iterative-query-notebook.md`](pccp/2026-07-18-iterative-query-notebook.md).
That record precedes any G2.8 prompt, profile, model-pipeline, or runtime change.

## Nondeterminism and consistency register

- Temperature zero and a seed do not make different model calls byte-stable;
  retain writer/reviewer outputs, digests, model identities, prompts, and knobs,
  and report digest differences only when outputs actually differ.
- Profile availability and model aliases are runtime facts. Live validation
  must confirm Gemma 4 12B as writer and Qwen 2.5 14B as reviewer before making
  comparative claims.
- Context truncation is deterministic (initial instruction plus five latest
  follow-ups), recorded, and never silently summarized by another model.
- Validation and execution evidence is admissible only when its query digest
  matches the exact editor snapshot.
- Current-version/digest conflicts and concurrent generations fail visibly;
  neither is resolved by last-write-wins behavior.
- The Hub sibling/runtime mismatch above is a blocking consistency issue for the
  final umbrella pin, not for drafting the contracts.

## G2.8c live validation checkpoint

After deterministic contract, gateway, Hub, and UI tests pass, use the isolated
real stack and follow the scenario matrix in [`quickstart.md`](quickstart.md).
It covers narrowing, aggregation/output-shape change, unresolved correction,
lint-clean semantic reviewer correction, and Hub/tool failure, plus stale and
concurrent requests, orphan recovery, profile switching, New Session isolation,
and result staleness. The pre-UI backend gate also proves schema registration,
the Hub's offline-resolvable request-v1/v2/revision/editor-snapshot/turn-request
dependency bundle, recorded/legacy turn evidence, shared Validate/Run
resolution, and lossless mapping of new event types into the existing
`events.jsonl` envelope without implementing W3 export. Each successful data
claim requires reproducible SQL and record-level PostgreSQL evidence with
dataset/query/version identifiers and a correctness rationale. Measure initial-
question submit through successor-query visibility; require under three minutes
after subtracting only each recorded invocation's exact `durationMs`, reconciled
to its role/stage/attempt/model, `startedAt`/`endedAt`, request digest, and
response-or-failure digest. Report wall time and explicit Run/database time
separately. Then complete keyboard-only, narrow, and 200%-zoom passes. Pause for
user acceptance before closing G3 or starting W3 experiments.
