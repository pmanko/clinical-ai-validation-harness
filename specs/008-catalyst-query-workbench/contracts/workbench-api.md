# Catalyst Workbench API

This contract describes the current workbench route surface and the behavior it
must preserve while Catalyst moves to a generic SQL connection. Exact JSON field
shapes remain in Catalyst's versioned machine schemas until code and schema can
change together. [The contracts index](README.md) identifies fields present in
the running format but absent from this product contract.

The workbench base path is `/v1/catalyst/workbench`. Data-source discovery is at
`/v1/catalyst/data-sources`. Requests and responses use their declared
`contractVersion` values.

## Shared rules

- Catalyst is not tied to a database engine. Each registered source has a stable
  ID, label, connection configuration or server-side connection reference,
  availability, and an explicit SQL dialect. Credentials are never returned to
  the browser or written into evidence.
- A session is bound to one source when it is created. A different source uses a
  new session.
- Schema discovery exposes every table, view, column, and type readable through
  the configured connection. The connection's readable objects define the set;
  optional annotations may add descriptions without changing it.
- The model, Available data view, editor assistance, advisory validator, and
  execution record use the same source identity, dialect, and schema snapshot.
- Generated and manually edited SQL use the same execution path.
- Validation reports findings. It does not rewrite SQL or disable Run.
- Run submits the exact immutable query version selected by the person. A normal
  database error is a valid execution outcome and remains attached to that
  version.
- The configured connection or deployment enforces read-only access. Catalyst
  applies a time limit and returned-row limit.

## Sources and schema

### `GET /v1/catalyst/data-sources`

Lists the registered source IDs, labels, availability, and the default source.
An unavailable source is reported as unavailable; it does not make unrelated
sources or the application shell unusable.

### `GET /v1/catalyst/workbench/catalog`

Accepts optional `dataSourceId`; omission selects the default source. Returns
the selected source's declared dialect and complete readable schema for the
editor and model context. A source that is unknown or unavailable returns an
explicit source error.

## Sessions

### `POST /sessions`

Creates a session for `dataSourceId` or the default source. The request may also
provide a name, model profile, browser state, and initial question.

If the question is omitted, the session opens without calling a model. If it is
present, Catalyst records the initial turn and returns the resulting session.
The selected source cannot be changed after creation.

### `GET /sessions?limit={limit}`

Lists recent session summaries.

### `GET /sessions/{sessionId}`

Returns the session, its selected source, current query version, saved versions,
validation findings, execution outcomes, browser state, and active guidance.

### `PATCH /sessions/{sessionId}/name`

Sets a non-blank session name and returns the updated session.

### `POST /sessions/{sessionId}/question`

Asks the first question in a session that was created without one. Once a turn
exists, later instructions use the turns endpoint.

### `PATCH /sessions/{sessionId}/browser-state`

Stores the supplied `browserState` object and returns the updated session. This
state restores the workbench presentation; it does not alter query content.

## Turns

### `POST /sessions/{sessionId}/turns`

Creates a follow-up model turn. The request contains:

- the new instruction and selected model profile;
- the browser's observed current version, so a stale browser cannot silently
  replace a newer query; and
- the exact current editor snapshot, including SQL, typed parameters, expected
  columns, and its digest. The snapshot may be null only when the session has no
  query.

The session source remains fixed. The model receives the declared dialect,
complete readable schema, current editor content, and the applicable session
context. A completed model turn may produce a new immutable query version,
request clarification, or explain that the request is unsupported. Model output
is never executed automatically.

A stale observed version, mismatched editor digest, unavailable profile, or
concurrent generation returns an explicit conflict or request error rather than
changing the current query.

### `GET /sessions/{sessionId}/turns`

Returns the ordered turns and their selected query-version references.

### `GET /sessions/{sessionId}/turns/{turnId}/generation-evidence`

Returns the recorded model request and output evidence for that turn. Evidence
includes the context and provenance actually used; it excludes credentials and
private model reasoning.

## Optional guidance

Guidance is an experimental, optional addition to ordinary conversation and
editor context. The API does not require a particular user interface, item
count, ranking rule, or summarization policy.

### `POST /sessions/{sessionId}/guidance`

Adds the supplied text exactly as written to the session's active guidance. The
request may identify whether it came directly from a person or from an accepted
system finding, the originating turn, and an entry it replaces. Active guidance
is included in applicable later model turns.

### `DELETE /sessions/{sessionId}/guidance/{guidanceId}`

Removes that entry from the active guidance supplied to later model turns and
returns the updated session.

## Query versions, validation, and execution

Query versions are immutable. Generated, checker-produced, and manually edited
queries are separate versions with a parent reference when applicable. The
session points to one current version; saving a new version never mutates an
earlier one.

### `POST /sessions/{sessionId}/versions`

Saves the supplied SQL, typed parameters, and expected columns as a human query
version. When the session already has a version, the request identifies the
observed parent version and digest. A stale parent or a different source returns
a conflict instead of overwriting the current version.

The gateway records advisory findings for the saved version and returns the
updated session. Findings do not change the submitted SQL.

### `POST /versions/{versionId}/validate`

Runs advisory validation against the version's declared dialect and readable
schema and records the findings. Validation does not query the database and its
result does not enable or disable execution.

### `POST /versions/{versionId}/execute`

The request names the version, its query digest, and an idempotency key. The path
and body version IDs and the stored digest must agree. Catalyst then sends that
version's exact SQL and typed parameters through the configured source
connection.

The response is a stored execution record:

- success contains typed columns and bounded rows; or
- failure contains the database diagnostic available from the active driver.

Both are valid execution outcomes. Advisory findings may be attached to the
record, but they cannot prevent the SQL from reaching the database. Reusing the
same idempotency key for the same version returns the recorded outcome; using it
for another version returns a conflict.

## Errors

The API distinguishes request and state errors from database outcomes:

- malformed JSON or an invalid request shape returns a request error;
- unknown sessions, turns, guidance entries, or versions return not found;
- stale query identity, source mismatch, or concurrent mutation returns a
  conflict;
- an unavailable model or source dependency returns an explicit dependency
  error; and
- SQL rejected by the database is stored and returned as a failed execution,
  not reclassified as an invalid experiment or model failure.
