# Catalyst Workbench API v1

Base path: `/v1/catalyst/workbench`. All successful and error payloads carry a
`contractVersion`. Workbench validation is advisory; only request-shape errors,
unknown/stale entity references, or database behavior can prevent a Run.

## Editor catalog

`GET /catalog`

Returns the currently loaded, approved editor vocabulary from the same gateway
catalog used to build Hub requests and deterministic validation. The response
contains `contractVersion: catalyst.workbench.editor-catalog.v1`, catalog and
schema versions, dialect, and ordered approved schemas/views/columns with their
logical types. It contains no independent UI mapping and no unapproved relation.

The UI uses this response only for completion and editor labels. Failure to load
it disables catalog-identifier suggestions but never disables editing,
formatting, validation, or Run; PostgreSQL dialect completion remains available.

## Create and restore sessions

`POST /sessions`

Request: question, profile ID, and optional initial browser state. The gateway
calls the real med-agent-hub generation path, persists any recoverable draft and
findings, and returns the complete session representation.

For current Hub `catalyst.query.v1` responses, recovery is deterministic:

- a ready response contributes its top-level SQL, parameters, validation, and
  provenance;
- a rejected response may contribute both
  `diagnosticCandidate.candidate.sql`/`parameters` and
  `diagnosticCandidate.rawOutput`, plus every ordered attempt finding;
- raw output is retained whether or not a recoverable candidate exists, but raw
  evidence alone never fabricates an executable query version.

Hub transport failures remain session-level generation failures; they are not
misrepresented as validator findings.

`GET /sessions/{sessionId}`

Returns session metadata, browser state, ordered version summaries, current full
version, its latest validation, repair proposals, and execution attempts.

`PATCH /sessions/{sessionId}/browser-state`

Persists expanded state, filters, page limit, and offset. It does not create a
query version.

## Create and validate query versions

`POST /sessions/{sessionId}/versions`

Request fields:

- `contractVersion: catalyst.workbench.version.request.v1`
- `parentVersionId` and `parentQueryDigest`
- complete `sql`
- complete ordered typed `parameters`
- optional `expectedColumns`

`authorType` is not accepted from the browser. The gateway assigns
`authorType: human` to every successfully created manual version.

Creates an immutable version and runs deterministic validation. Returns 409 if
the parent ID/digest is stale. Validator findings return with 201 and never turn
the request into a policy rejection.

`POST /versions/{versionId}/validate`

Runs the current validator revision again and appends a validation run. This is
useful after validator code/config changes; it never mutates the query version.

## Execute exact drafts

`POST /versions/{versionId}/execute`

Request fields include the version digest and an idempotency key. The gateway
loads the immutable version and submits its exact SQL and typed parameters to
the configured database role. It does not invoke the governed preview policy or
rewrite the SQL. The transaction remains read-only, statement timeout remains
configured, and the adapter fetches at most the configured row bound plus one.

Success returns dynamically derived column metadata, bounded typed rows, row
count/truncation facts, duration, and the validation status visible when Run was
selected. Database failure returns a persisted execution representation with
SQLSTATE, severity, message, detail, hint, and position when supplied by
PostgreSQL. Credentials and DSNs are excluded.

## Targeted remediation

`POST /versions/{versionId}/repairs`

Creates a repair scope from selected finding IDs. Deterministic rules return a
proposal immediately; contextual rules call the configured Hub profile with the
typed patch contract.

`POST /repairs/{repairId}/apply`

Verifies source digest, permitted units, and every frozen-unit digest. A valid
proposal creates a new immutable version and full validation run. Stale or
out-of-scope proposals return 409/422 without changing session state.

`POST /repairs/{repairId}/decline`

Records the disposition without changing the query.

## Error shape

```json
{
  "contractVersion": "catalyst.workbench.error.v1",
  "error": {
    "code": "stale_query_version",
    "message": "The current query version changed before this operation.",
    "details": {}
  }
}
```

## Compatibility

The existing governed endpoints remain unchanged:

- `POST /v1/catalyst/queries`
- `POST /v1/catalyst/previews/{previewId}/execute`

They continue to enforce current policy/preview semantics. UI manual testing
migrates to the workbench API; existing harness suites may continue using the
governed API until W3 adds explicit workbench scenarios.
