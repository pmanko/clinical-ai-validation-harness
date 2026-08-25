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

Existing v1/v2 records with a fixed instruction window remain readable. The
Phase 1 successor uses a new version and does not treat that historical window
as the product limit.

- `context_id`, `turn_id`, selection-policy revision, and canonical context
  digest
- current instruction and its digest
- relevant preceding instructions, with their order and inclusion recorded
- exact editor snapshot ID/digest plus observed and effective base IDs/digests
- latest matching validation-run/finding references
- latest matching execution diagnostic and result-shape summary: column
  metadata, returned count, and truncation only
- catalog, policy, dataset, profile, prompt, and correlation references/digests
- explicit included/omitted entity references and omission reason

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

## Dashboard Builder entities

### DatasetDraft

A DatasetDraft is rooted in one successful `ExecutionAttempt` and records:

- dataset-draft ID and immutable version ID/parent;
- session, source query-version/digest, execution, data-source ID, catalog
  version, typed result schema, and canonical result digest;
- the original parameterized SQL and typed parameters;
- the deterministically compiled Superset virtual-dataset SQL and compiler
  revision;
- name, description, author actor kind, creation time, and configuration digest;
- latest-version pointer and derived source state: current, stale, or missing.

It references the immutable execution result but does not copy clinical rows.
Promotion is permitted only while that execution's query version and editor
digest still match the session's current stored state. A later edit or successor
keeps the old result inspectable as stale but cannot promote an unsaved stale
execution. Named parameters are compiled only from the execution's typed values
with PostgreSQL-aware literal escaping; the parameterized source remains
preserved.

The canonical bounded result object is the RFC 8785 serialization of
`{contractVersion, columns, rows, returnedRows, maxRows, truncated,
truncationReason, warningCodes}`. `resultDigest` is its SHA-256. `columns` and
typed cells reuse every accepted workbench table wire form, preserving database
column and row order. The Dataset's row-free `executionBounds` projection and
the manifest's `resultBounds` projection are byte-identical and retain the
ordered schema, counts, truncation fields, and warning codes while omitting
rows. Codes are de-duplicated in persisted execution order: the existing
all-blank-column condition maps to `all_blank_columns`; retained legacy warning
prose without a recognized mapping maps to `legacy_unclassified_warning`.
Localized prose remains attached to execution display evidence and is not part
of the digest. The adapter rejects invalid row widths or counts rather than
coercing them. A truncated result has `returnedRows = maxRows` and a non-null
reason; an untruncated result has a null reason. This is not a claim about rows
the Gateway did not fetch. Truncated views persist `rowsShown` and
`totalKnown: false` and never invent a full row count.

### WidgetDraft

A WidgetDraft is an immutable-versioned presentation over one exact
DatasetDraft version. It records:

- widget ID, version ID/parent, and dataset version ID/digest;
- presentation kind: table, big-number KPI, time-series line/area,
  grouped/stacked bar, or proportion bar;
- title, column/axis bindings, labels, sort, aggregation, and display options;
- whether the initial suggestion was accepted or overridden plus deterministic
  compatibility evidence;
- author, timestamps, configuration digest, and source provenance.

### DashboardDraft

A DashboardDraft is an immutable-versioned supervised composition. It records:

- dashboard ID, version ID/parent, title, description, and layout;
- an ordered list of exact WidgetDraft version IDs and stable placement IDs;
- one locked `dataSourceId` and `catalogVersion`, established by the first
  Widget and enforced for every later placement;
- author, timestamps, configuration digest, and complete transitive source
  provenance;
- latest-version pointer and derived current/stale source state.

D1 creates a Dashboard from a user-supplied name. Widgets append in saved order
to deterministic full-width rows in a versioned 12-column layout; arbitrary
resize/rearrange controls are deferred. A source or catalog-version mismatch is
rejected before a new version is written. After a catalog refresh, D1 requires
an explicitly new Dashboard rather than mutating the locked pair. Layout-only
versions reuse unchanged Widget and Dataset version identities.

### SupersetBundle

A SupersetBundle records deterministic artifact identity:

- bundle ID derived from immutable configuration inputs, exact Dataset/Widget/
  Dashboard version IDs, the logical Catalyst Dashboard ID, one stable derived
  Superset Dashboard UUID, and immutable version-derived Dataset/Widget
  Superset UUIDs;
- deterministic dashboard slug
  `catalyst-<lowercase-logical-catalyst-dashboard-id>` and local route
  `/superset/dashboard/<slug>/`;
- bundle contract version, target Superset version, deterministic content digest,
  canonical outbox filename, and optional download name;
- generator and parameter-compiler revisions plus immutable source-version
  creation time;
- credential policy (`local_demo_read_only` or `receiver_supplied`) without
  logging credentials.

### SupersetPublicationAttempt and SupersetImportAttempt

Dynamic operating evidence remains outside the deterministic ZIP:

- publication/attempt ID, Dashboard ID/version, bundle ID/digest, pointer path,
  actual start/end time, actor, and outcome;
- importer/runtime/image/driver revision, CLI exit status, bounded diagnostic,
  and exact receipt path when an import is attempted;
- expected and observed Dashboard UUID/slug plus relationship verification when
  import reaches post-import verification;
- failure boundary (`pointer`, `bundle`, `preflight`, `credential`,
  `cli_transaction`, or `post_import_verification`), whether prior-Dashboard
  preservation is contractually supported for that boundary, and the exact
  last-known-verified bundle ID/digest when one exists;
- recovery disposition `full_reset_then_reimport_last_verified_bundle` for a
  full reset of only the Superset-local metadata
  database/home volumes and verified reimport of the per-Dashboard last-verified
  bundle, recorded as linked append-only attempts rather than an implicit or
  automatic rollback;
- append-only attempt records, one atomic latest projection per digest, and one
  atomic last-verified projection per logical Dashboard ID at
  `receipts/last-verified/<logicalDashboardId>.json`;
- dashboard-level user-visible state `draft`, `bundle_ready`, `imported`, or
  `import_failed`; `draft` has no bundle identity. Bundle-level status exists
  only for a non-null bundle ID/digest and is never `draft`; `importing` is an
  ephemeral process condition only.

The per-Dashboard last-verified projection is the sole recovery authority. It
validates against `catalyst-superset-last-verified-v1.schema.json` and records
the exact verified bundle/receipt identity without replacing the global desired
publication pointer. Missing/corrupt projection data or a missing/digest-
mismatched referenced bundle stops before any destructive operation.

The ZIP contains one enclosing bundle-root directory with native Superset
database, virtual-dataset, chart, and dashboard YAML plus a Catalyst manifest.
It never contains result rows. Identical inputs
produce byte-identical archives through deterministic member ordering,
timestamps, permissions, YAML serialization, and UUID derivation. A changed
publication keeps the logical Catalyst Dashboard ID, slug, and derived Superset
Dashboard UUID but uses new child-version UUIDs
because Superset 6.1.0 does not overwrite related datasets/charts during
dashboard import.
`Publish to Superset` atomically creates the content-addressed ZIP beneath the
Catalyst-owned, gitignored `runtime/superset/` tree and replaces the one global
`current.json` pointer with the most recently published desired Dashboard. The
pointer is not imported-success or last-verified state; prior Dashboard bundles
remain content-addressed and downloadable.
Superset mounts the outbox read-only; stack bootstrap or an explicit CLI helper
performs the import and is the only authority allowed to append an import
attempt/update its latest projection. A new query or execution changes only
derived stale state; it never rewrites or silently rebinds saved versions or
prior bundles.

Pointer/bundle validation, preflight, credential, and transactionally rolled-
back Superset CLI failures occur before a committed import is accepted and preserve the
previously verified Dashboard. A zero-exit CLI followed by UUID, slug, or
relationship verification failure is different: it sets `import_failed`, keeps
the diagnostic, disables Open Superset/current-success claims, and makes no
claim that the previous Dashboard remains usable. Recovery first validates the
logical Dashboard's atomic last-verified projection and immutable bundle, then
performs a full reset of only the Superset-local metadata database/home volumes
followed by reimport and verification. It never selectively deletes assets,
writes through Superset ORM/REST, or runs automatically. If verified A is
recovered while failed desired B remains in `current.json`, B stays
`import_failed`; bootstrap/retry of B is suppressed until explicit retry or a
new publication.

## WorkbenchEvent

An ordered append-only stream links session creation, generation, validation,
manual edits, repair proposals/dispositions, Run actions, execution outcomes,
profile changes, turn requests/completions/failures, editor snapshots,
revision-context construction, and browser-state updates. Each event has an ID,
sequence, type, contract version, timestamp, actor, entity references, and
payload.

D1 acceptance uses a separate versioned dashboard-event vocabulary over the
same append-only evidence rules: `query_turn`, `query_version`,
`query_execution`, `dataset_version`, `widget_version`, `dashboard_version`,
`bundle_published`, `superset_import_attempt`,
`superset_status_observed`, `postgresql_reconciliation`,
`accessibility_observation`, and `acceptance_decision`. Every builder event
references immutable IDs/digests rather than embedding query-result rows. The
publication/import events also carry the expected stable Superset Dashboard
UUID, logical Catalyst Dashboard ID, slug, and URL; an import event records
observed identifiers only when the import
reaches verification. `acceptance.json` is a versioned projection over these
events and their traversal-safe evidence paths, not a replacement for
`events.jsonl`.

For recovery evidence, the failed `superset_import_attempt`, full-reset
attempt, per-Dashboard last-verified reimport attempt, and resulting
`superset_status_observed` event cross-reference their immutable attempt and
bundle/projection digests. No event may label a post-verification failure as a
successful rollback, imply recovered A changed desired B, expose Open Superset
for B, or permit automatic retry before a new verified B receipt exists.

The three `query_*` events are structured D1 projections over existing notebook
evidence rather than renamed notebook records. Final acceptance carries a fixed
six-step `orderedWorkflow`—initial Query selection, successful initial Run,
Dataset v1 save, contextual follow-up, successful successor Run, Dataset v2
save—and cross-validates every sequence and identifier against those projections
and the source evidence.

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
