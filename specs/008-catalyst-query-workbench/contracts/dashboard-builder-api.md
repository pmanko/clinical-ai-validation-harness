# Catalyst Dashboard Builder API v1

Status: proposed D1 contract. This contract extends, and does not replace, the
accepted `/v1/catalyst/workbench` API. Its resources contain configuration and
lineage only. Clinical result rows remain in the bounded workbench execution
record and are never copied into a Dataset, Widget, Dashboard, bundle/publication record,
outbox pointer, receipt, or Superset ZIP.

Base path: `/v1/catalyst/dashboard-builder`

## D1 invariants

1. **One source per Dashboard.** A Dataset version binds exactly one successful
   workbench execution and therefore exactly one `dataSourceId` and
   `catalogVersion`. Every Widget version binds one exact Dataset version. Every
   Widget placed on one Dashboard version MUST transitively resolve to the same
   `dataSourceId` and `catalogVersion`. A mixed-source or mixed-catalog save or
   publish fails; it is never split, coerced to the default source, or silently
   rebound. D1 may use any ready registered source, but one Dashboard produces
   one Superset database binding.
2. **Immutable versions, mutable pointers.** Dataset, Widget, and Dashboard IDs
   identify logical draft containers. Each explicit save appends one immutable
   version and advances only that container's `latestVersion` pointer. Version
   content is never edited in place.
3. **Exact execution promotion.** A Dataset can be created only while its
   successful execution's query version/digest is the current immutable version
   of that workbench session. A dirty browser buffer is not server-observable;
   the UI MUST disable Save Dataset unless its editor digest also equals the
   execution query digest. The server independently enforces every persisted
   reference and digest it can observe.
4. **Bounded evidence is not a data snapshot.** The execution result digest
   binds the exact ordered columns, bounded typed rows, and truncation facts
   returned by Run. A truncated or zero-row successful execution may be saved,
   but remains labelled as such. Superset later executes the compiled SQL
   against PostgreSQL; the result digest MUST NOT be described as a digest of
   all source rows.
5. **No hidden work.** Save, restore, suggestion, library read, export, and
   download MUST NOT call a model or rerun SQL. Only the existing explicit
   workbench Run creates an execution.
6. **One-way publication.** Catalyst is the source of desired configuration.
   Superset 6.1.0 is the renderer. Catalyst never claims that writing a ZIP
   imported it, never reads or preserves Superset-only edits, and never writes
   Superset's metadata database directly.

The unsaved Dataset/Widget forms shown by the UI are browser-held candidates,
not additional mutable server resources. The first explicit Save creates the
logical draft and version 1 in one operation. This keeps the MVP's server model
append-only without inventing a second autosave lifecycle.

## Shared identity, digest, and concurrency rules

### Canonical digests

Unless a field says otherwise, each `*Digest` is lowercase SHA-256 over UTF-8
RFC 8785 canonical JSON of the named object. Arrays retain their documented
order. UUID strings are lowercase canonical UUID text. Date-times are UTC RFC
3339 strings ending in `Z`. Non-I-JSON numbers are invalid. The one binary
exception is `bundleDigest`: it is SHA-256 over the exact stored ZIP bytes, not
JSON. `parameterizedSqlDigest` and `compiledSqlDigest` hash the RFC 8785 JSON
string representation of the exact SQL string, including every whitespace
character.

- `resultSchemaDigest`: ordered execution `columns` array.
- `resultDigest`: the exact `catalyst.dashboard-builder.execution-result-digest-
  input.v1` object below. Localized warning prose is excluded so wording changes
  do not alter result identity.
- `typedParametersDigest`: complete ordered typed-parameter array.
- `configurationDigest`: the resource version's `configuration` object only;
  it excludes IDs, ordinal, parent, author, and timestamps.
- `requestDigest`: the complete mutation request excluding `idempotencyKey`.
- `receiptDigest`: complete immutable receipt object excluding `receiptDigest`.
- `compatibilityDigest`: the exact object containing `revision`,
  `suggestedKind`, and the seven ordered compatibility entries. Each entry has
  exactly `presentationKind`, `compatible`, nullable `bindings`, and nullable
  `reasonCode`; localized reason prose is excluded.
- `assetContentDigest`: the exact ordered `assetMembers` array in the bundle
  manifest.

The canonical execution-result digest input is:

```json
{
  "contractVersion": "catalyst.dashboard-builder.execution-result-digest-input.v1",
  "columns": [
    {
      "ordinal": 0,
      "name": "month",
      "databaseType": "date",
      "typeOid": 1082,
      "logicalType": "date"
    }
  ],
  "rows": [
    [{ "type": "date", "value": "2026-01-01" }]
  ],
  "returnedRows": 1,
  "maxRows": 500,
  "truncated": false,
  "truncationReason": null,
  "warningCodes": []
}
```

`columns` and typed `rows` are copied in database-return order from the
persisted execution. Each column is the exact accepted `AnalyticsColumn` wire
object: `ordinal`, `name`, `databaseType`, nullable `typeOid`, and
`logicalType`. The complete logical-type vocabulary is `string`, `integer`,
`decimal`, `boolean`, `date`, `date-time`, `time`, `interval`, `json`,
`binary`, `array`, and `unknown`; this contract does not invent a `nullable`
column property. Each row has exactly one cell per column. Cell objects use the
accepted workbench execution's closed forms: `{ "type": "null" }`, or
`{ "type": <logical type>, "value": ... }`. Decimal and interval values are
strings; date, date-time, and time retain their accepted canonical strings;
binary is base64 text; array is a JSON-safe array; and JSON is a JSON-safe
value whose object keys are strings. Nested non-I-JSON numeric values and
temporal, UUID, or binary values retain the execution serializer's accepted
string form. An `unknown` column can contain null cells or the execution
serializer's inferred/fallback typed cell; `unknown` is not itself a cell
type. `warningCodes` is the de-duplicated ordered list of stable codes in
their persisted execution order. D1 v1 maps the known all-blank-columns warning
to `all_blank_columns` and any retained unmapped legacy warning prose to
`legacy_unclassified_warning`; no other code is valid without a contract
revision. Runtime validation requires
`returnedRows == rows.length`, `returnedRows <= maxRows`, and every row width to
equal `columns.length`. When `truncated` is true, `returnedRows == maxRows` and
`truncationReason` is non-null; when false, `truncationReason` is null.

The server recomputes every supplied digest. A mismatch is
`422 digest_mismatch` and creates no version, pointer, export, or receipt.

### Parent compare-and-swap

Every successor save carries:

```json
{
  "observedParent": {
    "versionId": "8c5b2464-7414-4fb4-9aa0-83257e150304",
    "configurationDigest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
}
```

Both values MUST equal the logical resource's latest-version pointer in the
same immediate transaction that appends the successor. A mismatch returns the
resource-specific `409 stale_*_version` error and performs no mutation. Create
requests have no parent. Concurrent saves from the same parent have one winner;
all losers are stale.

### Idempotency

Every POST mutation requires `idempotencyKey` (1-200 characters). Keys are
scoped to operation plus logical resource (or to the create collection before a
logical ID exists) and retained with the canonical `requestDigest`.

Evaluation order is request/path validation, digest recomputation, idempotency
lookup, then parent/source CAS. Therefore:

- a completed replay with the same key and request digest returns the original
  IDs and representation with HTTP 200 and `replayed: true`, even if a pointer
  later advanced;
- the same key with another request digest returns
  `409 idempotency_conflict`;
- an identical request still running returns `409 mutation_in_progress`;
- a different key racing from the same parent reaches the CAS and the loser
  returns the relevant stale-version error; and
- a failed request is retained as an attempt. An explicit user retry uses a new
  idempotency key, so a network replay can never create an extra version or
  export.

A terminal failed mutation replayed with the same key and request digest returns
the originally recorded HTTP status, error code, and bounded diagnostic with
`replayed: true`; it performs no source check, serialization, filesystem write,
model call, or database call. A new attempt after failure always uses a new key.

Logical Dataset/Widget/Dashboard IDs and their immutable version IDs are
server-assigned UUIDv4 values allocated once after the idempotency claim; a
replay receives the same values. Version ordinals are positive integers scoped
to the logical resource. Placement IDs are client-assigned UUIDs and remain
stable across Dashboard versions until that placement is removed. Only the
Superset asset and export identities below are deterministic UUIDv5 values.

## Shared representations

### Execution source

The Dataset create request identifies, but does not reproduce, a workbench
execution:

```json
{
  "sessionId": "...",
  "queryVersionId": "...",
  "queryDigest": "<sha256>",
  "executionId": "...",
  "resultSchemaDigest": "<sha256>",
  "resultDigest": "<sha256>"
}
```

The server loads the execution and requires `status: succeeded`, exact ownership
by the session/query version, and exact recomputed digests. It copies into the
immutable Dataset version:

- `dataSourceId` and `catalogVersion` from the query/session lineage;
- ordered result columns and execution bounds: `returnedRows`, `maxRows`,
  `truncated`, nullable `truncationReason`, and ordered `warningCodes`;
- parameterized SQL and ordered typed parameters from the exact Query version;
- compiled Superset SQL produced by the pinned typed PostgreSQL compiler; and
- compiler revision and all source/configuration digests.

It stores no result rows in Dashboard Builder tables. `previewRef` points back
to the existing workbench session/execution representation. Missing execution
evidence is `422 source_evidence_missing`; digest disagreement is
`422 source_evidence_mismatch`; a non-successful execution is
`422 execution_not_succeeded`; and an execution whose Query version is no
longer the session current version is `409 stale_execution`.

### Derived source state

Every read returns:

```json
{
  "sourceState": {
    "status": "current",
    "reasons": []
  }
}
```

`status` is `current`, `stale`, or `missing`. It is derived on read and publish,
never stored in or used to rewrite an immutable version:

- `missing` if any referenced entity is absent or its stored digest disagrees;
- `stale` if all evidence exists but the source session query pointer or live
  catalog version advanced; otherwise
- `current`.

A stale source is visible and advisory for this supervised local MVP; publish
may proceed and returns the same warnings. Missing or digest-mismatched evidence
fails closed and cannot be exported.

### Version references

All transitive references carry both immutable identity and digest:

```json
{
  "id": "logical-resource-id",
  "versionId": "immutable-version-id",
  "configurationDigest": "<sha256>"
}
```

The server never resolves an omitted version to "latest" while saving or
publishing.

## Dataset routes

| Method and route | Result |
| --- | --- |
| `POST /datasets` | Create a DatasetDraft and its first immutable version from one exact successful execution. |
| `POST /datasets/{datasetId}/versions` | Append a metadata-only successor version. The execution, SQL, parameters, schema, result digest, source, and compiler revision remain frozen. |
| `GET /datasets` | Cursor-paginated Dataset library. |
| `GET /datasets/{datasetId}` | Logical Dataset plus latest version and derived source state. |
| `GET /datasets/{datasetId}/versions` | Immutable versions in ascending ordinal order. |
| `GET /dataset-versions/{versionId}` | One full immutable Dataset version. |

Create request (`catalyst.dashboard-builder.dataset.create.v1`):

```json
{
  "contractVersion": "catalyst.dashboard-builder.dataset.create.v1",
  "sourceExecution": { "sessionId": "...", "queryVersionId": "...", "queryDigest": "<sha256>", "executionId": "...", "resultSchemaDigest": "<sha256>", "resultDigest": "<sha256>" },
  "name": "Recent viral load results",
  "description": "Current governed result definition",
  "idempotencyKey": "save-dataset-01"
}
```

`name` is 1-160 Unicode code points after rejecting all-whitespace input;
`description` is 0-2,000 code points. The server preserves accepted text
byte-for-byte and does not normalize case or Unicode.

Success is 201 and returns `catalyst.dashboard-builder.dataset.v1` with
`datasetId`, `createdAt`, `updatedAt`, `latestVersion`, `sourceState`, and
`replayed: false`. The full version includes `ordinal`, nullable
`parentVersionId`, `author: {"actorKind":"human"}`, `createdAt`, `configuration`,
`configurationDigest`, and `previewRef`. `configuration` contains exactly
`name`, `description`, `source`, `resultSchema`, `executionBounds`,
`parameterizedSql`, `typedParameters`, `compiledSql`, and `compilerRevision`.

A successor request (`catalyst.dashboard-builder.dataset.version.create.v1`)
contains `observedParent`, complete replacement `name` and `description`, and
`idempotencyKey`. The server copies every frozen field from the parent.

```json
{
  "contractVersion": "catalyst.dashboard-builder.dataset.version.create.v1",
  "observedParent": {
    "versionId": "...",
    "configurationDigest": "<sha256>"
  },
  "name": "Recent viral load results",
  "description": "Reviewed definition",
  "idempotencyKey": "save-dataset-version-02"
}
```

The full Dataset-version response contract is a closed object with
`contractVersion: catalyst.dashboard-builder.dataset-version.v1`, `datasetId`,
`versionId`, `ordinal`, nullable `parentVersionId`, `configuration`,
`configurationDigest`, `author`, `createdAt`, and `previewRef`. `previewRef`
contains only `sessionId`, `queryVersionId`, `executionId`, and the existing
workbench execution detail path. The configuration's `resultSchema` contains
the exact ordered execution columns; `executionBounds` contains
`returnedRows`, `maxRows`, `truncated`, nullable `truncationReason`, and ordered
`warningCodes`. The bundle manifest calls the byte-identical projection of this
object `resultBounds`; this is a deliberate wire name, not a second semantic
object. No
`rows` property is permitted anywhere in this response.

## Widget routes

| Method and route | Result |
| --- | --- |
| `POST /widget-suggestions` | Return the deterministic initial presentation and compatibility matrix for one exact Dataset version; persists nothing. |
| `POST /widgets` | Create a WidgetDraft and version 1 from an exact Dataset version and selected compatible presentation. |
| `POST /widgets/{widgetId}/versions` | Append a successor Widget version. |
| `GET /widgets` | Cursor-paginated Widget library. |
| `GET /widgets/{widgetId}` | Logical Widget plus latest version and derived source state. |
| `GET /widgets/{widgetId}/versions` | Immutable versions in ascending ordinal order. |
| `GET /widget-versions/{versionId}` | One full immutable Widget version. |

Suggestion request (`catalyst.dashboard-builder.widget-suggestion.request.v1`)
contains one exact Dataset version reference. Response
`catalyst.dashboard-builder.widget-suggestion.v1` contains the deterministic
`suggestedKind`, compiler `revision`, `compatibilityDigest`, and all seven
serialized kinds (five UI families) in fixed order with `compatible`, read-only
derived `bindings`, and a stable reason code/message when incompatible. Kinds
are `table`, `big_number`,
`time_series_line`, `time_series_area`, `grouped_bar`, `stacked_bar`, and
`proportion_bar`; line/area and grouped/stacked are separate serialized kinds
even if grouped as five UI families. A no-match result MUST make `table` the
suggestion. This endpoint makes no model call and does not access PostgreSQL.

Compatibility uses only the stored `resultSchema`, `returnedRows`, and
`truncated` fields; it never inspects row values. Numeric means `integer` or
`decimal`, temporal means `date` or `date-time`, and categorical means `string`
or `boolean`. Within a role the lowest column ordinal wins. The seven entries
are always serialized in this order: `table`, `big_number`,
`time_series_line`, `time_series_area`, `grouped_bar`, `stacked_bar`,
`proportion_bar`.

Bindings are closed, read-only objects made from `{ordinal, name, logicalType}`
column refs:

- table is always compatible and binds `columns` to every result column in
  ordinal order;
- big number is compatible only for one returned row and exactly one result
  column whose type is numeric; it binds that column as `metricColumn`;
- time-series line and area require at least one temporal and one numeric
  column; they bind the first temporal `xColumn` and
  first numeric `metricColumn`;
- grouped and stacked bar require at least one categorical and one numeric
  column; they bind the first categorical
  `categoryColumn`, the first numeric `metricColumn`, and the second categorical
  column as nullable `seriesColumn`; and
- proportion bar requires two categorical columns plus one numeric column so
  its category and series bindings form a meaningful
  100%-stacked bar. It is never suggested and is available only as an explicit
  override.

The saved Dataset SQL owns the report calculation, including any aggregation.
Widget review selects only a chart type over that table and its derived column
bindings; it does not ask the user to calculate the table again. Superset's
native chart configuration contains its renderer-required metric detail, but
that detail is exported from the saved result schema and is not a Catalyst
reporting choice. Stable incompatibility codes are
`requires_one_numeric_cell`, `requires_temporal_numeric`,
`requires_categorical_numeric`, and `requires_two_categorical_numeric`.
Localized explanation text is
derived from the code and excluded from `compatibilityDigest`.

Suggestion priority is exact and short-circuiting: compatible `big_number`,
then `time_series_line`, then `grouped_bar`, otherwise `table`. Area, stacked,
and proportion variants are compatible supervised overrides but are never the
initial suggestion. `compatibilityDigest` covers the exact revision,
suggested kind, ordered entries, bindings, and reason codes defined above.

Widget create (`catalyst.dashboard-builder.widget.create.v1`) and successor
requests carry an exact Dataset version reference, `title`, selected
`presentationKind`, `displayOptions`, and `idempotencyKey`; successors also
carry `observedParent`. Both carry the exact observed suggestion `revision` and
`compatibilityDigest`; a changed compiler result is
`409 stale_widget_suggestion` and creates no version. `title` is 1-160 non-blank Unicode code points.
`displayOptions` is a complete object with `showLegend`, `showValues`, nullable
`numberFormat` (at most 80 code points), and `sort` (`derived`, `ascending`, or
`descending`); no other keys are accepted. The client does not submit arbitrary
column/axis bindings. The server recomputes bindings and compatibility from the
referenced Dataset schema. It rejects incompatible kinds with
`422 incompatible_presentation` and persists the suggestion revision,
compatibility digest, derived bindings, and disposition `accepted_suggestion`
or `overridden_suggestion` in the immutable configuration.

```json
{
  "contractVersion": "catalyst.dashboard-builder.widget.create.v1",
  "datasetVersion": {
    "id": "...",
    "versionId": "...",
    "configurationDigest": "<sha256>"
  },
  "observedSuggestion": {
    "revision": "superset-viz-map-1",
    "compatibilityDigest": "<sha256>"
  },
  "title": "Viral load by month",
  "presentationKind": "time_series_line",
  "displayOptions": {
    "showLegend": true,
    "showValues": false,
    "numberFormat": null,
    "sort": "derived"
  },
  "idempotencyKey": "save-widget-01"
}
```

Success returns a closed
`catalyst.dashboard-builder.widget-version.v1` nested in
`catalyst.dashboard-builder.widget.v1`. Its immutable configuration contains
the exact Dataset version ref, title, presentation kind, derived bindings,
display options, suggestion revision/digest/disposition,
and compiler revision.
Successor requests change the create `contractVersion`, add
`observedParent`, and otherwise submit the same complete fields.

## Dashboard routes

| Method and route | Result |
| --- | --- |
| `POST /dashboards` | Create a DashboardDraft and version 1. |
| `POST /dashboards/{dashboardId}/versions` | Append an immutable Dashboard version. |
| `GET /dashboards` | Cursor-paginated Dashboard library with publication summary. |
| `GET /dashboards/{dashboardId}` | Logical Dashboard plus latest version, source state, and publication summary. |
| `GET /dashboards/{dashboardId}/versions` | Immutable versions in ascending ordinal order. |
| `GET /dashboard-versions/{versionId}` | One full immutable Dashboard version. |

Create (`catalyst.dashboard-builder.dashboard.create.v1`) and successor requests
contain complete replacement `title`, `description`, and ordered `placements`;
successors also contain `observedParent`. Every placement contains a unique
stable `placementId` and exact Widget version reference. D1 accepts no client
geometry. The server derives a versioned 12-column layout in list order with
`x = 0`, `y = index * 4`, `width = 12`, and `height = 4`. Reordering the list is
a layout change; resize/freeform placement is deferred. At least one placement
is required.

`title` is 1-160 non-blank Unicode code points, `description` is 0-2,000 code
points, and one Dashboard version has 1-50 placements. Create and successor
requests are otherwise closed objects and always include `idempotencyKey`.

```json
{
  "contractVersion": "catalyst.dashboard-builder.dashboard.create.v1",
  "title": "Laboratory operations",
  "description": "Reviewed local dashboard",
  "placements": [
    {
      "placementId": "6d28c553-b570-4ddd-b20f-898a6e8156c1",
      "widgetVersion": {
        "id": "...",
        "versionId": "...",
        "configurationDigest": "<sha256>"
      }
    }
  ],
  "idempotencyKey": "save-dashboard-01"
}
```

Success returns a closed
`catalyst.dashboard-builder.dashboard-version.v1` nested in
`catalyst.dashboard-builder.dashboard.v1`. The immutable configuration contains
the complete title, description, ordered placements, derived source/catalog
binding, and ordered transitive Widget and Dataset version refs. Successor
requests change the create `contractVersion`, add `observedParent`, and submit
the complete desired replacement configuration.

The server resolves every Widget and Dataset reference and persists complete
transitive references plus the derived D1 `dataSourceId` and `catalogVersion`.
Mixed sources return `422 mixed_data_sources`; mixed catalog versions return
`422 mixed_catalog_versions`.

## Library reads

All three collection GETs accept optional `cursor`, `limit` (default 25,
1-100), `q` (at most 200 code points), `dataSourceId`, and `sourceState`. Results use
`catalyst.dashboard-builder.library.v1`, sort by `updatedAt` descending then
logical ID ascending, and return `items` plus nullable opaque `nextCursor`.
Paging is snapshot-consistent for the cursor lifetime. An invalid/expired cursor
is `400 invalid_cursor`; the service never silently starts over. Library items
contain the logical ID, display name/title, latest version reference, source
state, timestamps, and for Dashboards the publication summary. Full SQL,
parameters, layout, and provenance require the detail/version routes.

```json
{
  "contractVersion": "catalyst.dashboard-builder.library.v1",
  "resourceType": "dashboard",
  "items": [
    {
      "id": "...",
      "title": "Laboratory operations",
      "latestVersion": {
        "id": "...",
        "versionId": "...",
        "configurationDigest": "<sha256>"
      },
      "sourceState": { "status": "current", "reasons": [] },
      "publication": { "status": "bundle_ready", "bundleId": "...", "publicationId": "..." },
      "createdAt": "2026-08-05T20:00:00Z",
      "updatedAt": "2026-08-05T20:05:00Z"
    }
  ],
  "nextCursor": null
}
```

`resourceType` is `dataset`, `widget`, or `dashboard` and MUST match the route.
Dataset and Widget items omit `publication`; Dashboard items require it.

## Publish, download, and status

| Method and route | Result |
| --- | --- |
| `POST /dashboards/{dashboardId}/publish` | Generate/select one deterministic native bundle for the exact current Dashboard version and atomically advance the outbox pointer. |
| `GET /dashboards/{dashboardId}/publications` | Publication attempts for the Dashboard in descending time order. |
| `GET /dashboards/{dashboardId}/publication-status` | Status of the Dashboard's exact current version; this is the only status route that may return `draft`. |
| `GET /bundles/{bundleId}` | Immutable deterministic bundle record and derived current import status. |
| `GET /bundles/{bundleId}/status` | Compact status for one real immutable bundle plus current-pointer and receipt evidence; it never returns `draft`. |
| `GET /bundles/{bundleId}/download` | Exact stored ZIP bytes. |

Publish request (`catalyst.dashboard-builder.publish.request.v1`):

```json
{
  "contractVersion": "catalyst.dashboard-builder.publish.request.v1",
  "observedDashboardVersion": {
    "versionId": "...",
    "configurationDigest": "<sha256>"
  },
  "credentialPolicy": "local_demo_read_only",
  "idempotencyKey": "publish-dashboard-01"
}
```

The observed version MUST be the Dashboard's latest version; mismatch is
`409 stale_dashboard_version`. Before producing bytes, the server verifies all
transitive references/digests, the D1 single-source/catalog invariant, supported
Superset 6.1.0 visualization mappings, every frozen parameter/viz compiler
revision, credential policy,
and bundle-manifest contract. Publication does not query PostgreSQL.

Success is 201 with `catalyst.dashboard-builder.publication.v1`, state
`bundle_ready`, a dynamic `publicationId`, deterministic `bundleId`, the exact
Dashboard/Dataset/Widget version references,
deterministic Superset UUIDs, `assetContentDigest`, final ZIP `bundleDigest` and
byte length, filename, download path, target version, publication time,
stable Dashboard UUID/slug/path, warnings, and `replayed: false`. An idempotent replay returns the same
publication; a new-key publication of identical inputs appends a new attempt but
reuses the same ZIP bytes, digest, and bundle ID. A later publication of a
changed version keeps the Dashboard UUID and derives new child UUIDs.

Download returns `application/zip`, `Content-Length`, a quoted attachment name,
`Digest: sha-256=<base64 digest bytes>`, and the exact stored bytes. A missing or
hash-mismatched file fails `503 export_artifact_unavailable`; it is never
regenerated during GET.

Dashboard status (`catalyst.dashboard-builder.dashboard-publication-status.v1`)
is derived for the exact latest Dashboard version. It has `scope:
"dashboard_current_version"`, a non-null exact Dashboard version reference,
the deterministic non-null `supersetDashboard` UUID/slug/path, and may return
`draft` with null `bundleId`, `bundleDigest`, `outboxPointer`, and
`receipt` when that version has never been published. Once published, it carries
the same non-null bundle identity and evidence as bundle status.

Bundle status (`catalyst.dashboard-builder.bundle-status.v1`) has `scope:
"bundle"`, a path-matching non-null `bundleId`, non-null `bundleDigest`, and an
exact Dashboard version reference. A missing bundle is 404, never a synthetic
draft response. It also carries the same deterministic non-null
`supersetDashboard` object. Both shapes derive import state from the immutable bundle, exact
outbox pointer, live digest-labelled importer lock, and validated latest receipt
projection. Persisted state is `bundle_ready`, `imported`, or `import_failed`;
the Dashboard-current-version response additionally permits `draft`. Either
response may transiently report `importing` only while the importer holds the OS
lock for that exact digest:

- `draft`: the current Dashboard version has no publication (Dashboard route
  only);
- `bundle_ready`: the bundle/pointer exist with no terminal receipt;
- `importing`: the importer currently holds the OS lock for that exact digest;
- `imported`: the latest receipt attempt for that digest passed CLI and
  post-import verification, or a prior identical verified success made the run
  a no-op; or
- `import_failed`: the latest terminal attempt failed.

An old bundle can remain `imported` after another Dashboard becomes the global
outbox selection; `selectedForBootstrap` separately reports whether
`current.json` references it. The UI MUST NOT label `bundle_ready` as imported
or synced.

```json
{
  "contractVersion": "catalyst.dashboard-builder.bundle-status.v1",
  "scope": "bundle",
  "bundleId": "...",
  "dashboard": {
    "id": "...",
    "versionId": "...",
    "configurationDigest": "<sha256>"
  },
  "bundleDigest": "<sha256>",
  "supersetDashboard": {
    "uuid": "<stable Superset Dashboard UUID>",
    "slug": "catalyst-<lowercase logical Dashboard ID>",
    "path": "/superset/dashboard/catalyst-<lowercase logical Dashboard ID>/"
  },
  "status": "imported",
  "selectedForBootstrap": true,
  "outboxPointer": {
    "path": "outbox/current.json",
    "schemaVersion": "catalyst.superset.outbox.current.v1"
  },
  "receipt": {
    "path": "receipts/latest/<bundleDigest>.json",
    "latestProjectionDigest": "<sha256>",
    "receiptDigest": "<sha256>",
    "latestReceiptId": "..."
  },
  "recovery": null,
  "diagnostic": null
}
```

For Dashboard-current-version `draft`, `bundleId`, `bundleDigest`,
`outboxPointer`, and `receipt` are null.
For `bundle_ready`, `receipt` is null. For `importing`, `receipt` refers only to
the latest prior terminal projection, if any; it does not manufacture an in-flight
receipt. For `import_failed`, `diagnostic` is the bounded latest failure; other
states require null diagnostic. `recovery` is null except for `import_failed`,
where it is copied exactly from the referenced immutable receipt and includes
the prior-state guarantee, whether Open Superset/current-success controls are
enabled, the required recovery action, and the last-verified projection
generation/path/digest plus its exact publication/bundle/receipt identity (or a
stable omission reason). The latest projection's `recoveryAction` MUST
equal `receipt.recovery.requiredAction`; a mismatch invalidates the projection
and cannot enable an Open Superset action or current-success claim.

## Deterministic Superset identities

UUIDs use RFC 4122 UUIDv5 with `NAMESPACE_URL` and these exact UTF-8 names:

- database:
  `https://openelis-global.org/catalyst/superset/6.1.0/data-sources/{dataSourceId}`
- logical Dashboard:
  `https://openelis-global.org/catalyst/dashboard-builder/dashboards/{dashboardId}`
- virtual Dataset:
  `https://openelis-global.org/catalyst/dashboard-builder/datasets/{datasetId}/versions/{datasetVersionId}`
- chart:
  `https://openelis-global.org/catalyst/dashboard-builder/widgets/{widgetId}/versions/{widgetVersionId}`
- bundle:
  `https://openelis-global.org/catalyst/dashboard-builder/dashboards/{dashboardId}/versions/{dashboardVersionId}/bundles/{assetContentDigest}`

IDs are derived after exact references are validated. The stable database UUID
does not make Superset 6.1.0 overwrite a changed connection; a local connection
configuration change requires the documented reset path. Percent encoding or
case normalization MUST NOT be added to these names; stored IDs are inserted
byte-for-byte.

The imported Dashboard slug is
`catalyst-{lowercase logical Catalyst Dashboard ID}`. Its stable local path is
`/superset/dashboard/{slug}/`; the configured Superset origin is prepended only
when producing an absolute Open-Superset URL. Post-import verification requires
the exact derived Superset Dashboard UUID, logical-ID-derived slug, and expected
Dataset/chart relationships.
Neither a Superset numeric primary key nor a publication/version ID appears in
the URL.

## Canonical native assets and ZIP bytes

The same immutable inputs under one generator revision MUST serialize to the
same bytes on every supported platform:

1. Native YAML is UTF-8 without BOM, uses LF line endings and one final LF,
   two-space block indentation, no aliases/tags/document marker, lowercase
   `true`/`false`/`null`, base-10 integers, and double-quoted JSON-escaped
   strings. Mapping keys are sorted by Unicode code point. Floating-point YAML
   scalars are forbidden; release-coupled chart `params` are canonical compact
   JSON strings with lexicographically sorted keys.
2. Widget refs are ordered by Dashboard placement order. Dataset refs are
   ordered by first Widget use in that placement order and then de-duplicated.
   UUID-map object keys are serialized lexicographically. `assetMembers` contains
   only native YAML paths and is sorted lexicographically.
3. The ZIP contains regular files only, all beneath the one `bundleRoot`; it has
   no explicit directory entries. All member paths, including
   `catalyst/manifest.json`, are emitted in lexicographic relative-path order.
   Each entry uses `ZIP_STORED`, UTF-8 filename flag, DOS timestamp
   `1980-01-01T00:00:00`, Unix creator, regular-file mode `0644`, zero internal
   attributes, no extra field, and no file or archive comment.
4. Native member filenames are their lowercase deterministic Superset UUID plus
   `.yaml` inside `databases/`, `datasets/`, `charts/`, or `dashboards/`;
   `metadata.yaml` and `catalyst/manifest.json` have their fixed names.

D1b records one checked-in golden fixture containing the generator revision,
canonical input digest, ordered member paths/lengths/digests, final ZIP length,
and `bundleDigest`. D1c MUST reproduce it byte-for-byte before publication code
is accepted. A serializer/library change that alters any byte requires an
explicit generator-revision bump and a newly reviewed fixture; it cannot retain
the old revision.

## Credential and data-sensitivity boundary

Every local-demo manifest carries the exact notice
`demo_clinical_identifiers_may_be_present_in_sql_parameters`; a receiver-
supplied manifest uses `clinical_identifiers_may_be_present_in_sql_parameters`.
Every manifest carries `containsResultRows: false` and
`manifestContainsCredentials: false`. SQL parameter values may therefore be
sensitive identifiers even though result rows are excluded. The manifest, pointer,
events, receipts, and diagnostics never contain a credential or DSN.

`local_demo_read_only` permits only the explicitly labelled local-demo,
database-enforced read-only credential in the native database YAML. Publication
fails if its role can write or if another credential is present.
`receiver_supplied` never embeds or substitutes a secret in the bundle or a
temporary derivative. Before import, the receiving environment MUST already
contain the deterministic database UUID with a usable read-only connection; the
importer verifies it and fails at `credential_resolution` if it is absent,
writable, or unreachable. Superset 6.1.0 then preserves that pre-provisioned
connection because related database imports use `overwrite: false`. Environment
secrets are neither read into Catalyst nor copied into evidence.

## Outbox contract and crash behavior

The host layout is:

```text
runtime/superset/
  outbox/publish.lock
  outbox/<bundleDigest>.zip
  outbox/current.json
  receipts/import.lock
  receipts/attempts/<bundleDigest>/<receiptId>.json
  receipts/attempts/unresolved/<receiptId>.json
  receipts/latest/<bundleDigest>.json
  receipts/last-verified/<logicalDashboardId>.json
```

`current.json` validates against
`catalyst-superset-outbox-current-v1.schema.json`. The Gateway is the only
writer of `outbox/`. Publication acquires an exclusive advisory lock on
`outbox/publish.lock`, creates
and validates the complete ZIP in memory, then:

1. writes `<bundleDigest>.zip.tmp-<random>`, flushes and `fsync`s the file;
2. atomically renames it to `<bundleDigest>.zip` in the same directory (an
   existing file is reused only after byte length and SHA-256 match);
3. `fsync`s the outbox directory;
4. writes and `fsync`s a complete `current.json.tmp-<random>`;
5. atomically replaces `current.json` and `fsync`s the directory again; and
6. finalizes the publication as `bundle_ready` only after rereading and
   validating that the pointer names the same publication/bundle/digest.

The durable publication attempt exists before step 1 with internal state
`generating`. Startup/retry reconciliation makes a matching pointer and ZIP
`bundle_ready`; a generating record without both remains failed/retryable and
does not change the prior pointer. No reader observes a partial ZIP or pointer.
Temporary files are never considered artifacts and may be removed after proving
that no live writer owns the lock.

Superset and the importer mount `outbox/` read-only. The importer alone writes
immutable receipts and their latest projections. It acquires one exclusive
advisory lock on `receipts/import.lock`, snapshots and validates
`current.json`, verifies the exact ZIP digest/version/manifest before invoking
`superset import-dashboards`, and retains the captured digest even if the
Gateway later advances the pointer.

While holding the import lock, the importer replaces the lock file contents with
one fsynced bounded JSON marker containing exactly `schemaVersion:
catalyst.superset.import-lock.v1`, nullable `publicationId`, nullable `bundleId`,
nullable `bundleDigest`, `receiptId`, and `startedAt`. A status reader first
tries a non-blocking shared lock: if it succeeds, no import is live and stale
marker bytes are ignored; if it fails, `importing` is reported only when the
marker is valid and its non-null digest equals the requested bundle. A held lock
with an absent/malformed/mismatched marker is an importer diagnostic, not an
`importing` claim for another bundle. The marker is ephemeral process evidence,
not an import state or receipt.

Each immutable attempt validates against
`catalyst-superset-import-receipt-v1.schema.json`; the atomic projection
validates against `catalyst-superset-import-latest-v1.schema.json`; the
per-logical-Dashboard verified pointer validates against
`catalyst-superset-last-verified-v1.schema.json`. A retry
writes a new receipt under `attempts/<digest>/` and atomically replaces only the
latest projection; no prior attempt changes or disappears. The importer uses
same-directory temp + file `fsync` + rename + directory `fsync`. A prior verified
`imported` projection for the exact digest returns that success without running
the CLI or appending another attempt, except an explicit recovery reimport after
a Superset-local reset. Failure or post-import verification writes an
`import_failed` receipt. A crash before a terminal receipt releases the OS lock
and records no result; the next run safely reimports stable UUIDs and verifies
them.

The exclusive `receipts/import.lock` also serializes the generation counter in
`receipts/last-verified/<logicalDashboardId>.json`. Only an import whose CLI and
post-import relationship verification both succeed may create or advance this
projection. Its `generation` starts at 1 and increases by exactly one from the
previous valid projection for that logical Dashboard. The importer writes it by
same-directory temp + file `fsync` + atomic rename + directory `fsync`, after
the immutable success receipt and digest-specific latest projection are durable.
It points to that exact publication, immutable ZIP path/digest/byte length,
latest-projection path/digest, immutable receipt path/digest, Dashboard
version, Superset runtime, and stable Superset Dashboard identity. Its
`projectionDigest` hashes the complete object with only `projectionDigest`
excluded. A failure never creates, advances, rolls back, or deletes a
last-verified projection. If a crash leaves a verified latest receipt newer
than this projection, startup reconciliation under the same lock may advance it
only after revalidating every referenced immutable artifact and cross-field
identity; it never infers success from Superset state alone.

Pointer, bundle, manifest, credential, and other preflight failures occur before
Superset mutation. The CLI import is run as a transaction; a terminal
`cli_import` failure is valid only when rollback has been confirmed. Those
failures record `supersetMutationDisposition: not_started` or
`transaction_rolled_back`, respectively, and guarantee that any prior verified
Dashboard state is preserved. They disable Open Superset/current-success for
the failed target and prescribe `retry_same_bundle`.

The importer can commit before relationship verification completes. Therefore
a `post_import_verification` failure records
`supersetMutationDisposition: committed_unverified` and explicitly does **not**
claim that the prior Dashboard is preserved. It marks the target
`import_failed`, disables Open Superset and every current-success claim, retains
the bounded diagnostic, and prescribes the documented
`full_reset_then_reimport_last_verified_bundle` recovery. The receipt links the
last-verified projection generation/path/digest and its exact
publication/bundle/receipt identity when one exists, or a stable omission reason
when none exists.

Recovery is a deliberate importer operation under `receipts/import.lock`, not
an asset-selective delete. Before any destructive step, it MUST validate the
last-verified projection schema and digest, its per-Dashboard path, generation,
logical Dashboard identity, immutable bundle and receipt paths/digests, imported
receipt outcome, completed verification, bundle contract version, and pinned
Superset/runtime identity. A missing, malformed, stale, mismatched, or
unresolvable projection fails before reset and leaves Superset untouched. There
is no fallback to deleting one Dashboard, Dataset, chart, or other subset.

After successful validation, recovery resets only the disposable Superset-local
metadata database and Superset home state, reinitializes the pinned runtime and
its deterministic read-only database binding, and imports and verifies the exact
linked last-known-good bundle. The outbox, receipts, Catalyst metadata, and
analytics database are outside the reset boundary. The recovery import writes a
new immutable receipt linked to the failed receipt; after verification it may
advance the same Dashboard's last-verified generation to that new receipt.

Recovery does not rewrite `outbox/current.json`, the failed bundle's immutable
receipt, or its digest-specific latest projection. Thus, when current bundle B
failed after commit and last-verified bundle A is restored, Superset contains A
but Dashboard-current status remains B / `import_failed`; Open Superset and every
current-success control remain disabled. Bootstrap observes B's terminal failed
latest projection and does not retry it automatically. Only an explicit retry
of B or publication of a new bundle may change the desired current state; the
older success for A never masks B's failure.

A failure before a trustworthy bundle digest is available validates against the
same receipt schema but is stored at
`receipts/attempts/unresolved/<receiptId>.json`. It records the exact failure
`stage`, an unavailable-verification `omissionReason`, and only identifiers that
were successfully parsed. It does not create or replace a digest-addressed
latest projection and therefore cannot change any Dashboard or bundle import
state. `pointer_read` and `pointer_validation` failures are therefore invalid in
`receipts/latest/<bundleDigest>.json`. Once both bundle identity and digest are
trustworthy, a failure attempt is stored under that digest and may advance only
that digest's latest projection.

Receipt `stage` is one of `pointer_read`, `pointer_validation`, `bundle_read`,
`bundle_validation`, `manifest_validation`, `credential_resolution`,
`cli_import`, `post_import_verification`, or `complete`. Only `outcome:
"imported"` may use `complete`; it requires all publication/bundle/Dashboard
identifiers, target version, exit code zero, and the full passed verification
object. `import_failed` uses the exact failed stage and the closed unavailable
verification shape `{ "status": "not_run" | "failed", "omissionReason":
<stable non-empty code> }`; full expected/observed asset identifiers are omitted
and any safe details remain in the bounded diagnostic. Thus pointer/ZIP/manifest
parse failures are recordable without inventing identifiers or claiming that
verification ran.

Every `import_failed` receipt and digest-specific latest projection carries a
non-empty stable `errorCode`; the receipt's bounded redacted diagnostic text is
also non-empty. `imported` requires a null error code. A `cli_import` failure is
valid only with a nonzero integer exit code and confirmed transactional rollback;
pre-CLI failures use null, post-import-verification failures use zero, and only a
fully verified `complete` receipt may use outcome `imported`.

Every terminal receipt also carries `supersetMutationDisposition` and a closed
`recovery` object. `imported` requires `verified`, enabled Open/current-success
controls, and `requiredAction: none`. Preflight failures require `not_started`;
transactionally rolled-back CLI failures require `transaction_rolled_back`;
post-import verification failures require `committed_unverified`. The latest
projection and status response expose only the linked receipt's recovery action
and never infer a stronger preservation guarantee.

Attempt receipts have unique UUIDv4 `receiptId` values. Start time MUST NOT
follow finish time. `commandDigest` hashes a canonical, non-secret
descriptor containing the importer revision, Superset version, CLI operation,
and fixed flags—not raw argv, environment variables, credentials, or a DSN.
For digest-addressed attempts, the attempt-directory digest, latest-projection
path digest, receipt `bundle.sha256`, current-pointer `bundle.sha256`, and ZIP
filename stem MUST match. The receipt filename stem MUST equal `receiptId`; the
ZIP filename stem MUST equal `bundle.sha256`. The latest projection's
`receiptId`, `receiptDigest`, `outcome`, `stage`, and `bundleId` MUST match the
referenced immutable receipt after `receiptDigest` is recomputed. The receipt's
Dashboard reference and Superset version MUST match the manifest and bundle.
These cross-file and ordering rules are runtime validations because JSON Schema
cannot express all of them. A missing, malformed, foreign-digest, or wrong-
version link is ignored for state projection and emits a bounded diagnostic.

`imported` requires all of: target runtime exactly 6.1.0, CLI exit code 0,
expected logical Dashboard UUID present, every expected chart/Dataset UUID
present, and Dashboard relationships equal the bundle. Diagnostics are UTF-8,
credential/DSN-redacted, at most 16,384 Unicode code points, and record whether
truncation occurred. Receipt files, locks, and times are outside the
deterministic ZIP.

## Error envelope

All API errors use the existing workbench shape:

```json
{
  "contractVersion": "catalyst.workbench.error.v1",
  "error": {
    "code": "stale_dashboard_version",
    "message": "The Dashboard changed before this operation.",
    "details": {}
  }
}
```

Stable codes include `invalid_request`, `invalid_cursor`, `digest_mismatch`,
`dataset_not_found`, `widget_not_found`, `dashboard_not_found`,
`version_not_found`, `stale_dataset_version`, `stale_widget_version`,
`stale_dashboard_version`, `stale_execution`, `execution_not_succeeded`,
`source_evidence_missing`, `source_evidence_mismatch`,
`incompatible_presentation`, `stale_widget_suggestion`, `mixed_data_sources`,
`mixed_catalog_versions`, `idempotency_conflict`, `mutation_in_progress`,
`unsupported_compiler_revision`, `unsupported_viz_mapping_revision`,
`receiver_connection_unavailable`,
`bundle_contract_invalid`, `bundle_generation_failed`, and
`export_artifact_unavailable`, `last_verified_projection_missing`,
`last_verified_projection_invalid`, `recovery_target_mismatch`,
`recovery_reset_failed`, and `recovery_reimport_failed`. Error details and
diagnostics never contain
credentials, DSNs, clinical rows, or hidden model reasoning.

Request/contract errors are HTTP 400; unknown resources are 404; stale,
idempotency, and in-progress conflicts are 409; validly shaped but incompatible
or unverifiable content is 422; unavailable runtime/outbox artifacts are 503;
and an unexpected bundle serialization/write failure is 500
`bundle_generation_failed`. A generation failure leaves the prior ZIP and
`current.json` byte-for-byte unchanged.

## Manifest runtime invariants

The reviewed `catalyst-superset-bundle-v1.schema.json` now carries actual
parameterized SQL and ordered typed values, per-version author/time provenance,
the ordered native-member digest list, a deterministic `bundleId`, and the
required enclosing ZIP root. Runtime validation still MUST enforce facts JSON
Schema cannot express:

1. Dataset/Widget version references are unique and complete, Widget references
   resolve to the listed Dataset versions, and the UUID-map keys equal exactly
   those version IDs.
2. Member paths are unique and lexicographically ordered; each member byte length
   and digest matches the ZIP; `assetContentDigest` hashes the RFC 8785
   representation of that array; and the manifest/final ZIP digest are excluded
   to avoid self-reference.
3. Every Dataset source reference resolves to the stored workbench session,
   turn, query, execution, schema, canonical bounded result including warning
   codes, parameters, frozen parameter-compiler revision, and authorship.
4. `bundleId` and every Superset UUID recompute from the documented UUIDv5
   inputs, and `bundleRoot` matches the stable Dashboard UUID.
5. Pinned Superset 6.1.0 clean-imports the root-wrapped archive, ignores the
   extra JSON member, and renders each supported visualization fixture.
6. For every Dataset, the stored parameterized SQL and typed parameters compile
   under that Dataset's frozen compiler revision to the exact stored compiled
   SQL; both SQL digests recompute; and `compiledSqlDigest` equals the digest of
   the SQL value in that Dataset's native YAML. No generator may trust one side
   of this comparison or perform textual parameter replacement.
7. Every Widget's frozen visualization-mapping revision and compatibility digest
   recompute from its Dataset schema/bounds and selected kind; its native chart
   YAML uses that exact binding. The manifest generator's sorted revision arrays
   equal the unique revisions used by its Dataset and Widget refs. An unavailable
   historical revision fails closed rather than silently recompiling.
8. The manifest data-sensitivity notice and result-row exclusion flags are exact;
   the credential policy matches the native database asset and receiving-
   environment preflight; and no forbidden credential/DSN/result-row property or
   value appears in manifest, pointer, event, or receipt artifacts.
9. YAML and ZIP bytes satisfy the canonical serialization rules and the active
   generator revision's reviewed golden fixture.

## Harness event and final-acceptance contracts

Dashboard Builder evidence lines validate against
`catalyst-dashboard-builder-event-v1.schema.json` and use the existing harness
snake-case envelope with `schema_version:
harness.catalyst-dashboard.event.v1`. The closed D1 event vocabulary is
`query_turn`, `query_version`, `query_execution`, `dataset_version`,
`widget_version`, `dashboard_version`, `bundle_published`,
`superset_import_attempt`, `superset_status_observed`,
`postgresql_reconciliation`, `accessibility_observation`, and
`acceptance_decision`. The three `query_*` records are D1 projections of the
accepted notebook lineage; each links the immutable source notebook/API
evidence and does not alter the existing notebook stream. The event payload
digest covers the complete payload; payloads carry immutable IDs, digests,
stable outcomes, and traversal-safe evidence references, never SQL text,
parameter values, result rows, credentials/DSNs, free-form diagnostics, or
hidden reasoning. Widget events include the complete deterministic binding and
accepted-versus-overridden suggestion disposition. Import events include the
importer/runtime and CLI status, latest-projection digest when one exists, stable
error code, immutable receipt evidence, and explicit recovery linkage. Status
events include the receipt and latest-projection digests used for projection.
Accessibility events record viewport, zoom percentage, and input mode.
Acceptance events record the accepted version/digest set, residual-risk codes,
and evidence-index digest.

Final `acceptance.json` validates against
`catalyst-dashboard-acceptance-v1.schema.json` with `schema_version:
harness.catalyst-dashboard.acceptance.v1`. In addition to JSON Schema
validation, the acceptance validator MUST resolve every path beneath the run
directory, reject symlink/path escape, hash every referenced file, and require:

1. the referenced run manifest and every event to use the declared schema
   versions and same run ID; `eventCount` equals the number of valid JSONL lines;
2. component revisions, source/query/execution and immutable
   Dataset/Widget/Dashboard refs, publication/bundle/current/latest/receipt refs,
   last-verified projection generation/ref, and Superset expected/observed
   identities to agree across all artifacts;
3. `receiptDigest` to recompute with only that field excluded, the current
   pointer and latest projection to resolve the exact bundle/receipt digests,
   the last-verified projection digest to recompute with only its own digest
   excluded, and the URL slug to derive from the logical Catalyst Dashboard ID;
4. every PostgreSQL reconciliation's expected and observed result digests to
   match, with reproducible SQL/parameter digests, bounded inspected-value
   evidence, and reviewer rationale materialized by reference;
5. each repository pin's expected and observed commit to be equal and remotely
   reachable, and every named CI/schema/accessibility/scenario gate to pass;
6. precommit/transactionally rolled-back import-failure evidence to prove prior
   state preservation, while post-import-verification failure evidence proves
   disabled success controls and the full Superset-local reset/reimport recovery
   path without claiming preservation. Recovery evidence MUST prove the
   last-verified projection and every referenced immutable artifact were
   validated before reset, no asset-selective delete was used, restored bundle A
   is present in Superset, failed desired bundle B remains current and
   `import_failed`, and automatic bootstrap of terminal B was suppressed; and
7. `orderedWorkflow` to resolve six strictly increasing event sequences in this
   exact order: initial query selection, successful initial execution, Dataset
   v1 save from that execution, completed contextual follow-up from that base,
   successful successor execution, and Dataset v2 save from the successor.
   Every turn/query/execution/Dataset identifier MUST match the referenced
   `query_*`/`dataset_version` event, the lineage arrays, and the source evidence;
   Dataset v1 MUST precede the follow-up and Dataset v2 MUST follow the rerun; and
8. `evidence_status` and outcome to be `accepted`; the evidence-index digest to
   equal `runEvidence.evidenceIndex.sha256`; the accepted version/digest set to
   agree with lineage, publication, receipt, and last-verified projection; the
   pinned Superset application and metadata-database image digests and bundle
   contract version to match runtime evidence; and every residual risk to carry
   a stable code, disposition, and immutable evidence reference; and
9. `acceptance_decision` to be the last applicable builder event and to match
   the explicit accepted user, timestamp, acceptance ID, accepted artifacts,
   residual risks, evidence-index digest, and decision evidence digest.

The acceptance receipt is a projection over evidence, not a substitute for the
append-only event stream. Failure at any cross-artifact check keeps the run in
development state and prevents a D1 completion claim.
