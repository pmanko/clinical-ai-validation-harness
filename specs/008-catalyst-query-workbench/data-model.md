# Data Model: Catalyst Query Workbench

All identifiers are UUIDs, timestamps are UTC RFC 3339 values, and JSON payloads
carry explicit contract versions. Query versions and events are append-only.

## WorkbenchSession

- `session_id`, original `question`, and selected `profile_id`
- `dataset_id`, `dataset_version`, and `catalog_version`
- `current_version_id`
- `browser_state`: expanded flag, filters, limit, and offset
- `status`, `created_at`, and `updated_at`

Creating a session invokes the real Hub generation path. A malformed or rejected
candidate is still persisted whenever SQL/parameters can be recovered.

## QueryVersion

- `version_id`, `session_id`, `parent_version_id`, and ordinal
- `author_type`: model, human, deterministic_repair, or model_repair
- exact `sql` and ordered typed `parameters`
- advisory `expected_columns`, when present
- canonical `query_digest`
- profile snapshot, prompt digest, model roles, and catalog provenance
- source finding IDs, repair proposal ID, and creation timestamp

The `(session_id, ordinal)` pair is unique. Existing versions never change.

## ValidationRun and Finding

A validation run identifies the exact version, validator revision/digest,
ordered checks, aggregate status, duration, and timestamp. A finding contains a
stable ID and rule code, severity, stage, message, JSON path, AST unit/span when
available, bounded evidence, suggested action, repairability, and validator
revision. Validation status never controls workbench execution.

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

## WorkbenchEvent

An ordered append-only stream links session creation, generation, validation,
manual edits, repair proposals/dispositions, Run actions, execution outcomes,
profile changes, and browser-state updates. Each event has an ID, sequence, type,
contract version, timestamp, actor, entity references, and payload.

This stream is the source for later `events.jsonl` materialization. Clinical
result rows remain labeled synthetic execution evidence and separate from the
operating metadata tables.
