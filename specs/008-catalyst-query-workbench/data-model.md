# Data Model: Catalyst Query Workbench

All identifiers are UUIDs, timestamps are UTC RFC 3339 values, and JSON payloads
carry explicit contract versions. Query versions and events are append-only.
Iteration turns, editor snapshots, and revision contexts are contract entities
projected from the append-only event stream; they do not require a separate
mutable conversation-history table.

## WorkbenchSession

- `session_id`, original `question`, and initial/default `profile_id`; the active
  UI selection is derived separately from the final turn when one exists
- `dataset_id`, `dataset_version`, and `catalog_version`
- `current_version_id`, `current_turn_id`, and optional active-generation turn ID
- last saved editor snapshot ID/digest and presentation preferences; when no
  saved snapshot exists, the current immutable version is the editor source
- response-derived `draft_seed`, only while no immutable version exists: exact
  recoverable SQL, editable typed parameter rows, unresolved JSON paths, and
  `raw_model_output` source; it is derived from persisted raw provenance rather
  than stored as accepted query state
- `browser_state`: expanded flag, filters, limit, and offset
- `status`, `created_at`, and `updated_at`

Creating a session invokes the real Hub generation path. A malformed or rejected
candidate is still persisted whenever SQL/parameters can be recovered.
If the Hub withholds a contract-invalid candidate but preserves one parseable raw
JSON object, the response may expose an unresolved editor seed without creating
a QueryVersion or changing the raw evidence. A later immutable version always
supersedes that seed.

New sessions record the initial question through `query_turn.requested` and
exactly one terminal `query_turn.completed` or `query_turn.failed` event. Turn
synthesis is used only to restore sessions whose evidence predates these events.

At most one turn may be generating for a session. Follow-up acceptance atomically
claims the generation slot, compares the observed CAS base to the session's
current version, reconciles the editor snapshot to an effective base, and
appends the requested event. An already-active generation is rejected before
stale-base evaluation, so a concurrent loser consistently receives the
generation-in-progress conflict even if the accepted request created a human
effective base. A stale or concurrent loser performs none of those mutations
and makes no Hub call.

## IterationTurn

- `turn_id`, `session_id`, and unique session-relative ordinal
- `kind`: initial or followup
- exact user instruction and its canonical digest
- compact selected profile reference, writer/reviewer role/model labels,
  prompt reference/digest, schema digest, and correlation/trace identifiers;
  full model configuration and prompt content live in GenerationEvidence
- observed CAS base version ID/digest, required whenever the session had a
  current immutable version when the follow-up was submitted
- effective base version ID/digest: observed for an unchanged snapshot, the new
  human version for any contract-valid changed snapshot or valid snapshot when
  no immutable version exists, and null only for unresolved input
- resulting current-anchor version ID/digest: effective when non-null, otherwise
  observed when present, otherwise null
- exact nonempty editor snapshot ID/digest, required for every follow-up and
  absent only for the initial question
- revision-context record ID/digest when the turn is a follow-up
- status: requested, completed, or failed
- ordered writer and reviewer-correction output-version IDs when produced, plus
  `selected_version_id` only when the full turn completes successfully
- failure stage, bounded diagnostic, raw-response evidence reference, and
  terminal timestamp when failed
- requested, started, and completed timestamps

`query_turn.requested`, `query_turn.completed`, and `query_turn.failed` events
are the canonical records. The ordered turn timeline is their deterministic
projection. The initial turn contains the session question; each follow-up
contains only its new instruction. A failed turn remains in the timeline but
never changes the session's selection away from its resulting current anchor. It
may reference a contract-valid but unselected writer output version.

## EditorSnapshot

- `snapshot_id`, `session_id`, active `turn_id`, and capture timestamp/actor
- exact SQL, ordered typed parameters, and advisory expected columns
- canonical snapshot digest covering executable content
- observed source version ID/digest, nullable only when no immutable version
  exists, and persisted relationship: reused, promoted_human, or unresolved
- effective base version ID/digest after reconciliation: observed when reused,
  the new human version when promoted (including valid no-version input), and
  null only when unresolved
- resulting current-anchor version ID/digest: effective when non-null, otherwise
  observed when present, otherwise null
- unresolved JSON paths and contract findings when not executable
- source evidence reference when hydrated from a malformed model response

For a reused buffer, the snapshot references its observed version. For any
contract-valid changed buffer—or valid buffer submitted when no version
exists—one human QueryVersion is promoted first and becomes the effective base
for follow-up, Validate, or Run. An unresolved snapshot may be supplied as model
correction context but is never represented as a QueryVersion.

`empty` is a local editor/UI state, not an EditorSnapshot relationship. The UI
disables submission while empty and may restore the current immutable version
without creating a snapshot, turn, or version.

The promoted human version becomes current before the Hub call. If writer or
reviewer generation later fails, the resulting current anchor remains current:
effective when non-null, otherwise observed when present, otherwise null. No
earlier model version is silently reselected.

Editor presentation state such as wrapping is outside the snapshot digest. The
last submitted or explicitly saved snapshot is restorable after refresh; raw
unsaved keystrokes are not claimed as immutable history.

## RevisionContextRecord

- `context_id`, `turn_id`, selection-policy revision, and canonical context
  digest
- current instruction and its digest
- initial question plus zero to five most-recent preceding follow-up
  instructions, in deterministic chronological order
- exact editor snapshot ID/digest plus observed and effective base IDs/digests
- latest matching validation-run/finding references
- latest matching execution diagnostic and result-shape summary: column
  metadata, returned count, and truncation only
- catalog, policy, dataset, profile, prompt, and correlation references/digests
- explicit included/omitted entity references and truncation reason

Validation or execution evidence is included only when its query digest matches
the submitted editor snapshot. Result rows, database credentials, connection
details, hidden reasoning, raw traces, unrelated-session history,
undifferentiated transcript content, and historical SQL copies other than that
exact snapshot are prohibited. Writer and reviewer roles receive the same
revision context; their role-specific prompts and the writer candidate are
separately recorded.

## GenerationEvidence

- `evidence_id`, `turn_id`, and ordered event references
- observed CAS base, effective base, exact editor snapshot, and revision-context
  IDs/digests
- context-selection policy revision, included/omitted references, instruction
  ancestry, deterministic truncation point, and exclusion reasons
- selected profile, writer/reviewer role and model/configuration identities, and
  full role-specific prompt content plus prompt/schema/catalog/policy/dataset
  revisions and digests
- correlation/trace identifiers and correlation digest; Hub request, response,
  and candidate digests; and raw-output evidence references/digests for each
  stage
- ordered inference invocations, including failures: role, stage, attempt, model,
  effective temperature/DRY/max-token/response-format configuration, start/end
  timestamps, duration milliseconds, request digest, and response or
  normalized-failure-envelope digest
- candidate contract/lint disposition, omitted evidence references/reasons, and
  immutable output-version ID when valid
- final selected-version ID or failure stage/diagnostic
- typed `omissions`: empty for recorded turns; for synthesized legacy turns,
  one stable field/reason/source-reference item for every unavailable fact whose
  public field is explicitly null

The public turn exposes either this typed detail or a typed reference resolving
to the same authorized fields. Output QueryVersions link its ID/reference. It is
a projection of turn and generation events, not a source of result rows,
credentials, or hidden chain-of-thought. A contract-invalid candidate is
retained only as raw or parsed diagnostic evidence. A contract-valid writer
candidate is an immutable output version even if reviewer transport, contract,
or deterministic validation later fails; its disposition is unselected and the
resulting current anchor remains selected when non-null. Recorded evidence has
complete invocation timing/digests even for failed calls and `omissions: []`;
legacy evidence never invents a missing prompt, timing, digest, or model fact.

## QueryVersion

- `version_id`, `session_id`, `parent_version_id`, and ordinal
- active `turn_id`; observed CAS base, effective base, lineage-parent version,
  and input editor snapshot IDs/digests when derived from a follow-up
- `author_type`: model, human, deterministic_repair, or model_repair
- exact `sql` and ordered typed `parameters`
- advisory `expected_columns`, when present
- canonical `query_digest`
- profile snapshot, prompt digest, model roles, and catalog provenance
- source finding IDs, repair proposal ID, and creation timestamp
- selection disposition: selected, unselected_output, or superseded_by_reviewer
- generation-evidence ID/reference for generated output versions

The `(session_id, ordinal)` pair is unique. Existing versions never change.
An unchanged submitted buffer reuses its matching version. Any contract-valid
changed buffer, including valid input with no existing version, creates exactly
one human version inheriting the active turn ID and becomes the effective base/
current version before generation. A follow-up writer version has the effective
base as parent and records the actual input snapshot; a valid reviewer correction
is the writer version's `model_repair` child. If the input snapshot was
unresolved and therefore has no effective base, the writer records that snapshot
as its derivation source while `parent_version_id` uses the observed immutable
version as a lineage anchor when one exists. Producing a version never executes
it.

The current-version pointer advances from the resulting current anchor to a
model output only after the full turn succeeds. Reviewer failure leaves a valid
writer version unselected and leaves the anchor current. Invalid writer/reviewer
candidates never create a version.

## ValidationRun and Finding

A validation run identifies the exact version, validator revision/digest,
ordered checks, aggregate status, duration, and timestamp. A finding contains a
stable ID and rule code, severity, stage, message, JSON path, AST unit/span when
available, bounded evidence, suggested action, repairability, and validator
revision. Validation status never controls workbench execution.

Intent-sensitive validation also records the active turn ID and instruction
digest. The instruction is supplied independently from the executable candidate
contract; a candidate does not carry or invent its own question.

## RepairScope and RepairProposal

A repair scope contains source version/digest, source finding IDs, permitted AST
units, frozen-unit digests, and a scope digest. A proposal contains the typed
patch, author/model provenance, before/after unit renderings, disposition, and
resulting version ID when accepted.

Transitions are proposed → accepted, declined, stale, or rejected_out_of_scope.
Applying a proposal is atomic and always creates a new query version followed by
a full validation run.

## ExecutionAttempt

- execution, session, and version IDs
- exact submitted SQL/parameter digest and visible validation status
- status: running, succeeded, failed, timed_out, or cancelled
- database diagnostic: SQLSTATE, severity, message, detail, hint, and position
- returned column metadata and bounded typed rows
- returned count, truncation, statement timeout, and duration

Connection strings, credentials, and server file paths are never recorded.
Successful execution does not modify validation status.

Result currentness is derived, not reassigned: an attempt is current only while
its version/digest matches the current immutable version and the active editor
content digest, including a not-yet-saved local buffer. Otherwise it is
displayed as stale and remains labelled with its original `Results from Query
vN` identity. No successor edit or turn deletes the attempt or attaches it to
another version.

## DashboardArtifact and DashboardVersion

A DashboardArtifact is one supervised presentation rooted in one successful
ExecutionAttempt. It records:

- dashboard, session, source query-version, and source execution IDs;
- source query/result digests, data-source ID, catalog version, and typed result
  schema;
- latest saved dashboard-version pointer; and
- a derived source state: current, stale, or missing evidence.

A DashboardVersion is immutable and records:

- dashboard-version ID, parent ID, and artifact ID;
- presentation kind: table, bar, or line;
- title, selected columns or axis bindings, labels, and sort;
- author actor kind (`human` in the unauthenticated demo), created time, and
  configuration digest; and
- the complete source binding copied from the artifact at save time.

The dashboard references the immutable execution result; it does not copy
clinical rows into operating-metadata fields. The result digest is the RFC 8785
canonical SHA-256 of the stored successful `catalyst.table.v1` payload.
Configuration, preview, save, and restoration make no model call and do not
execute the source query. A new active query or execution changes only the
artifact's derived source state—it never rewrites a saved version or rebinds its
evidence. Missing or digest-mismatched source evidence fails closed.

## WorkbenchEvent

An ordered append-only stream links session creation, generation, validation,
manual edits, repair proposals/dispositions, Run actions, execution outcomes,
profile changes, turn requests/completions/failures, editor snapshots,
revision-context construction, and browser-state updates. Each event has an ID,
sequence, type, contract version, timestamp, actor, entity references, and
payload.

Turn events preserve the exact instruction, base/snapshot/context digests,
selected profile and role/model provenance, produced-version references, and
terminal evidence. A per-turn profile change affects that turn and its produced
versions only. Human versions inherit the current turn ID. Starting a new
session creates a new event stream and never imports context from the prior one.
Initial turns in new sessions use these recorded events and `origin: recorded`;
only pre-event sessions use synthesized origin.

If recovery finds a recorded `query_turn.requested` event without a terminal
event, the recovered failed projection uses stage `orphan_recovery` and stable
code `generation_interrupted`; other orphan/interrupted terminology is invalid.

A rejected stale or concurrent follow-up has no turn ID and appends no event.
The conflict response therefore cannot appear in a turn timeline or advance any
session, version, turn, or editor pointer.

## LegacyTurnProjection

Sessions created before turn events existed expose one read-only initial turn
with `origin: synthesized_legacy`. Its stable turn ID is deterministically
derived from session ID and timeline-contract version; owner is the persisted
session ID; created time is session creation time; terminal time is the selected
initial output's creation time, otherwise the raw/generation-outcome time,
otherwise session creation time. `recovery_references` identify every persisted
field used, including session question/profile, initial-generation provenance,
current-version pointer, draft seed, and raw failure evidence.

Synthesized turn output IDs include only contract-valid `model`/`model_repair`
versions attributable to initial generation, and its selected ID is only the
initial generation's selected output. The timeline's separate
`current_version_id` restores the actual persisted current version, including a
later human version. A valid unselected writer may appear as output on a failed
turn; draft-only, raw-only, and other no-selected-output cases remain failed or
unresolved. Projection never appends an event, makes a model call, invents
executable content, or promotes a draft seed. The same evidence and contract
revision always produce identical origin, synthetic ID, owner, timestamps,
status, output/selection/current references, recovery references, and digests.
Every unavailable public evidence field is null and has a typed, deterministic
omission entry; recorded turns instead expose complete evidence with an empty
omissions list.

This stream is the source for later `events.jsonl` materialization. Clinical
result rows remain separate from operating metadata; their synthetic or real
classification comes only from authoritative dataset provenance. Model
nondeterminism is recorded through complete input/configuration and
candidate/output digests; temperature zero is never treated as proof that two
runs are reproducible.
