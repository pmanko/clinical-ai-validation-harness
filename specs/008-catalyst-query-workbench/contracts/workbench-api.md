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

Request: a non-blank question of at most 100,000 Unicode code points, profile
ID, and optional initial browser state. Follow-up instructions remain limited to
8,000 code points. The gateway persists the session and a recorded initial
`query_turn.requested` event before calling the real med-agent-hub v1 generation
path, then atomically appends the generated versions/evidence and a recorded
terminal `query_turn.completed` or `query_turn.failed` event. New post-G2.8
sessions therefore use `origin: recorded`, have null `recoveryReferences`, and
never depend on legacy synthesis. The response remains the complete session
representation; GET `/sessions/{sessionId}/turns` exposes the initial turn.

The initial turn snapshots the resolved writer/reviewer profile and receives a
`catalyst.workbench.generation-evidence-ref.v1` exactly like a follow-up. Initial
generation continues to send Hub `catalyst.query.request.v1`; the turn's
instruction digest still binds the exact question to its evidence.

A pre-G2.8 persisted question longer than 100,000 code points is never truncated
to fit the turn contract. Session restore remains available, but GET turns
returns `422 legacy_turn_unprojectable` with the observed length and limit so the
source can be migrated explicitly.

For current Hub `catalyst.query.v1` responses, recovery is deterministic:

- a ready response contributes its top-level SQL, parameters, validation, and
  provenance;
- a rejected response may contribute both
  `diagnosticCandidate.candidate.sql`/`parameters` and
  `diagnosticCandidate.rawOutput`, plus every ordered attempt finding;
- raw output is retained byte-for-byte whether or not a recoverable candidate
  exists, and raw evidence alone never fabricates an executable query version;
- when no immutable version exists, one exact raw JSON object containing a SQL
  string and representable typed parameter objects may also produce a separate
  `draftSeed` with `status: unresolved` and `source: raw_model_output`.
  Missing parameter names remain blank, unsupported/malformed shapes produce no
  seed, and fields are never inferred from placeholder order. The seed is
  derived from persisted evidence on create and restore, so it survives refresh;
  any immutable current version takes precedence and suppresses the seed.

Hub transport failures remain session-level generation failures; they are not
misrepresented as validator findings.

`GET /sessions/{sessionId}`

Returns session metadata, browser state, ordered version summaries, current full
version, its latest validation, repair proposals, and execution attempts.

## Iterate within a session

`POST /sessions/{sessionId}/turns`

Creates one linear follow-up turn using
`catalyst.workbench.turn.request.v1`. The request carries the current
`instruction`, selected `profileId`, nullable `observedBase`, and the complete
`catalyst.workbench.editor-snapshot.v1` displayed by the browser.

`observedBase` is only a compare-and-swap observation: it is the version ID and
query digest the browser believes is current, or null when it observed no
immutable current version. It is not automatically the artifact supplied to the
models. The gateway compares the pair atomically with the session pointer;
ID/digest mismatch, including null versus non-null, returns
`409 stale_query_version` and appends no turn event.

### Editor snapshot identity

`catalyst.workbench.editor-snapshot.v1` is the exact digestable editor content
sent by the browser and used as the model base. `editorDigest` is defined as:

1. form the JSON value with exactly the keys `sql`, `parameters`, and
   `expectedColumns` from the snapshot; exclude `contractVersion` and
   `editorDigest`;
2. serialize that value with RFC 8785 JSON Canonicalization Scheme, preserving
   array order;
3. encode the canonical JSON as UTF-8; and
4. SHA-256 those bytes and encode all 32 bytes as 64 lowercase hexadecimal
   characters.

The same algorithm defines immutable workbench `queryDigest`, so a
contract-valid snapshot and version with identical content have identical
digests. Non-I-JSON values such as NaN or Infinity are not representable. The
gateway recomputes the digest; mismatch returns 422 and creates no turn.

Shared golden vector:

```text
value:     {"sql":"SELECT 1","parameters":[],"expectedColumns":[]}
canonical: {"expectedColumns":[],"parameters":[],"sql":"SELECT 1"}
sha256:    82d9696f92e64acb0c4edba843633c97eb23fd3f22887d93755eb86971855105
```

On acceptance the gateway wraps that content in the server-owned, first-class
`catalyst.workbench.editor-snapshot-record.v1`. The record assigns `snapshotId`,
`sessionId`, and `turnId`; captures timestamp and actor; preserves the request's
source observed-base reference; records classification and effective-base
resolution; and retains unresolved paths/findings plus an optional source
evidence reference. `editorDigest` is the content identity, while `snapshotId`
identifies this persisted occurrence. The turn's top-level observed/effective
base, classification, and unresolved paths must equal the embedded snapshot
record; this cross-object identity is enforced at commit.

After the CAS succeeds, the server classifies the snapshot and records the
resolution separately from `observedBase`:

| Classification | Condition | `effectiveBaseVersion` | `manualVersion` |
| --- | --- | --- | --- |
| `reused` | snapshot content/digest exactly equals the observed immutable version | observed version | null |
| `promoted_human` | snapshot differs or no version exists, and it satisfies the immutable-version contract | newly appended human version | same new version |
| `unresolved` | snapshot is representable but cannot satisfy the immutable-version contract | null | null |

An unresolved snapshot remains durable turn evidence and is still sent to the
models for correction; it is never falsely promoted. `unresolvedPaths` records
the exact failing JSON paths. The writer output's immutable parent is the
effective base when one exists, otherwise the observed base when one exists,
otherwise null; a reviewer correction's parent is that writer output. Every
output also records the snapshot digest and turn ID, so the unresolved artifact
remains in the lineage even though it is not a version.

### Atomic lifecycle and failures

Conflict precedence is deterministic. The gateway first resolves the route and
session, then validates request shape, instruction/snapshot digests, and profile
availability. In the immediate state transaction it checks the active-generation
guard before comparing `observedBase`. Therefore a request that is both stale
and concurrent returns `409 turn_generation_in_progress`; after that turn
terminates, retrying the same observation returns `409 stale_query_version`.
Neither response appends an event.

In that immediate transaction the gateway:

1. verifies no requested turn is active, then compares `observedBase`;
2. allocates the turn ordinal/ID and generation run ID;
3. persists the exact snapshot, immutable writer/reviewer profile snapshot, and
   frozen revision context;
4. appends the optional human version and makes it current when the snapshot is
   `promoted_human`; and
5. appends `query_turn.requested` with the process owner instance.

The Hub call occurs outside that transaction. While it is active, all endpoints
that could change the session current-version pointer return
`409 turn_generation_in_progress`; validation and execution of an already
immutable version may continue, but cannot alter the frozen revision context.

A second immediate transaction appends any contract-valid writer/reviewer
versions and validations, updates the current pointer, and appends exactly one
terminal `query_turn.completed` or `query_turn.failed` event. No observer can see
a terminal event without its version links or the corresponding pointer state.
Events are append-only and ordered `requested -> completed|failed` for one
generation run.

A completed turn selects one complete output and makes it current. The runtime
invariant is that `selectedVersionId` identifies exactly one member of
`outputVersions`, that member has `selected: true`, every other member has
`selected: false`, and `resultingCurrentVersion` is the selected version. JSON
Schema cannot express cross-array identity, so the gateway enforces this before
commit.

A failed turn has `selectedVersionId: null`. Its current pointer remains the
effective base, or the observed base when the snapshot was unresolved; its
`resultingCurrentVersion` records that exact result. Contract-invalid candidates
remain diagnostic evidence only and never become QueryVersions. If the writer
is contract-valid but the reviewer transport, output contract, or validation
fails, the writer is retained as an unselected immutable `outputVersions`
member while the current pointer still remains at the base. Failure records
include a typed `stage` and `rawEvidenceRef`; raw evidence is retained outside
the compact timeline and the reference never points to execution result rows.
When no raw bytes exist (for example persistence failure or orphan recovery),
`evidenceAvailable` is false and `rawEvidenceRef` is null. Every failure still
has a bounded `catalyst.workbench.turn-failure-diagnostic.v1`; when evidence is
available, its non-null reference resolves the separately retained raw payload.

The POST is synchronous and returns 201 with the terminal turn projection for
both completed and failed generation. While generation is active, GET may show
the one-event `requested` projection. Shape, profile, stale-base, and concurrency
errors are 4xx responses and create no turn. Execution remains an explicit user
action.

Requested turns do not expire. Each requested event records a
`generationRunId` and boot-scoped `ownerInstanceId`. In the supported
single-gateway runtime, startup or first session access atomically marks a
requested turn owned by a prior, absent process instance as failed with stage
`orphan_recovery` and code `generation_interrupted`; this is based on process
ownership, never elapsed time, and is idempotent. Cancellation/error paths append the same terminal failure before
releasing the active-turn guard. A multi-gateway deployment requires a durable
job coordinator before enabling turn generation.

`GET /sessions/{sessionId}/turns`

Returns `catalyst.workbench.turn.timeline.v1`, ordered by ascending turn ordinal.
The first entry represents the initial question; later entries represent
follow-ups. `currentTurnId` identifies the final entry and `currentVersion`
identifies the session pointer after projecting every entry. The timeline embeds
the bounded revision context and its validation/execution references, but never
execution rows, credentials, DSNs, raw model outputs, or reasoning traces. Every
entry is explicitly labelled `origin: recorded` or
`origin: synthesized_legacy`; the latter is never presented as recorded history.

Only sessions created before G2.8 turn events synthesize an initial entry, and
GET does so without writing events. IDs are UUIDv5 using `NAMESPACE_URL` over:

- `https://openelis-global.org/catalyst/workbench/sessions/{sessionId}/turns/initial`
- that URL plus `/runs/generation`;
- that URL plus `/events/requested` and `/events/completed` or `/events/failed`;
  and
- that URL plus `/generation-evidence`.

The synthesized requested event uses `ownerInstanceId: legacy_synthesis` and
the session `createdAt`; its terminal timestamp is the last selected initial
model version's `createdAt`; when no initial output exists it uses the persisted
generation-outcome timestamp, then raw-generation evidence timestamp, then
session `createdAt`, in that order. The initial instruction/profile come from
persisted session evidence; no current-time value participates in synthesis.

Synthesized turns have non-null
`catalyst.workbench.legacy-recovery-references.v1` containing the source session
reference, every persisted version ID in version ordinal order, the persisted
current version reference, and nullable draft-seed, raw-generation, and
generation-outcome evidence references. Recorded turns require this field to be
null.

Legacy `outputVersions`, `selectedVersionId`, and `resultingCurrentVersion`
describe only the initial contiguous `model`/`model_repair` versions before the
first human version; the last such version is selected. They never relabel a
later human version as initial model output. Timeline `currentVersion` remains
the actual persisted current pointer, including a later human version. With no
initial model output, the synthesized turn is failed with null selection/result,
while recovery references still preserve the real current pointer and draft/raw
evidence. Available profile/model/config/prompt provenance is copied exactly;
unavailable legacy fields remain null and are enumerated in profile `omissions`,
never invented. Initial turns have no editor snapshot, observed/effective base,
manual version, or revision context. Repeated GETs produce stable IDs,
timestamps, ordering, selection, and evidence digests.

### Generation evidence detail

`GET /sessions/{sessionId}/turns/{turnId}/generation-evidence`

Returns `catalyst.workbench.generation-evidence.v1`. Each turn exposes only a
compact `catalyst.workbench.generation-evidence-ref.v1` containing evidence ID,
digest, and this detail path; every output-version link repeats that same ref,
and the immutable QueryVersion provenance records it as well. The compact turn
timeline remains raw-free.

The evidence detail preserves the exact instruction/digest; snapshot and
observed/effective/manual bases; frozen revision context; dataset, catalog,
policy, required output schema, profile, correlation, and selection-policy
references plus digests; and included/omitted history references/digests. It
also records the Hub request and response and every writer/reviewer attempt with
candidate digest, disposition, optional version/validation links, raw evidence,
and final selection or failure.

`invocations` contains one record for every attempted initial/follow-up writer
or reviewer model call, including transport failure, timeout, and cancellation.
Each record binds invocation ID, role, stage, attempt, provider/model IDs,
start/end, Hub-measured duration, request digest, nullable response digest,
failure digest, and outcome. Hub measures `durationMs` around its provider call
with a monotonic clock; wall-clock timestamps are correlation evidence, not the
duration source. Requested/in-progress calls have null end/duration and null
response/failure digests, while `requestDigest` is always present; every
terminal call has end and duration. Terminal
`totalInvocationDurationMs` is exactly the integer sum of every invocation
duration, including failed calls. Harness metric SC013 uses that same sum and
does not substitute Gateway wall time or omit reviewer/retry attempts.

An available inspectable external Hub payload is returned exactly in
`exactPayload` with its content type, payload digest, and stable evidence ref.
Unavailable or non-inspectable payloads return null exact content and an
explicit omission reason. Provider-hidden reasoning, credentials/connection
details, execution result rows, unrelated-session history, and historical SQL
copies are never made inspectable; the detail contains externally observable
request/response evidence, not a reasoning trace. `evidenceDigest` uses UTF-8
RFC 8785 canonical JSON over the complete evidence object excluding
`evidenceDigest`. Evidence ID is stable; its requested projection may gain
append-only response/candidate/terminal facts, while a terminal digest never
changes.

Recorded evidence requires non-null dataset/catalog/policy/output-schema,
profile detail (including full prompt text), correlation, selection policy, and
Hub request/response records, plus at least one invocation and empty root
`omissions`. The compact turn profile carries only typed prompt
ID/version/ref/digest. Synthesized legacy evidence may use null for those root
fields but must enumerate every unavailable field in typed `omissions`; values
are never reconstructed or invented. Evidence `status` and
`finalSelection.status` must be identical, enforced by schema and again when the
projection is built.

### Med-Agent Hub revision request

Initial generation remains compatible with `catalyst.query.request.v1`: one
user message contains the initial question and `catalystQuery` contains the
target, approved catalog, policy, correlation, and required output contract.

Follow-up generation uses `catalyst.query.request.v2`. Its outer OpenAI-compatible
request still contains exactly one user message (the current instruction), and
its `catalystQuery` retains every v1 field while adding
`catalyst.query.revision-context.v1`:

The Hub contract registry must publish and preload this exact dependency bundle
by `$id` before validating v2; runtime network reference resolution is forbidden:

- `catalyst-query-request-v1.schema.json` for the shared target/catalog/policy/
  correlation definitions;
- `catalyst-query-request-v2.schema.json`;
- `catalyst-query-revision-context-v1.schema.json`;
- `catalyst-workbench-editor-snapshot-v1.schema.json`; and
- `catalyst-workbench-turn-request-v1.schema.json` for the shared `versionRef`.

The bundle is the deployable schema unit even though the files retain separate
contract identities. Missing or duplicate `$id` registrations fail Hub startup,
not an individual generation request.

```json
{
  "contractVersion": "catalyst.query.request.v2",
  "requiredOutputContract": "catalyst.query.v1",
  "revision": {
    "contractVersion": "catalyst.query.revision-context.v1",
    "turnId": "c0a8017e-27be-4cdd-b70a-b10526e099a2",
    "currentInstruction": "Only include finalized observations",
    "instructionDigest": "4a91e2560e49039e6c909e8b93f800bab81d90ba96ceac998f8e16a7ae95ea82",
    "baseClassification": "promoted_human",
    "observedBase": {
      "versionId": "66a5a36e-eaf5-4b54-8809-c52321e97743",
      "queryDigest": "1111111111111111111111111111111111111111111111111111111111111111"
    },
    "effectiveBaseVersion": {
      "versionId": "77b6b47f-fbf6-4c65-991a-d63432fa8854",
      "queryDigest": "eb16a193e6b17cca358fe2a13dc09802f88ea29022261ee26c4ac2033dd40cec"
    },
    "editorSnapshot": {
      "contractVersion": "catalyst.workbench.editor-snapshot.v1",
      "sql": "SELECT observed_at FROM catalyst_analytics.lab_observations",
      "parameters": [],
      "expectedColumns": [],
      "editorDigest": "eb16a193e6b17cca358fe2a13dc09802f88ea29022261ee26c4ac2033dd40cec"
    },
    "instructionHistory": [
      {
        "turnId": "9334914a-7af4-5abe-80ee-728b06c958d3",
        "ordinal": 1,
        "kind": "initial",
        "instruction": "Show recent laboratory observations",
        "instructionDigest": "d0452f679b9cc7f27f6febc1f754a15528d4bc6b10027b300018a6215358fb83"
      }
    ],
    "validationContext": null,
    "executionContext": null,
    "selection": {
      "includedHistoryTurnIds": ["9334914a-7af4-5abe-80ee-728b06c958d3"],
      "validationRef": null,
      "executionRef": null,
      "omissions": {
        "historyInstructionsOmitted": 0,
        "validationFindingsOmitted": 0,
        "executionColumnsOmitted": 0,
        "diagnosticTextTruncated": false,
        "prohibitedClasses": [
          "database_credentials",
          "database_connection_details",
          "database_dsn",
          "execution_result_rows",
          "hidden_reasoning",
          "historical_sql_copies",
          "raw_chat_transcript",
          "raw_model_outputs",
          "raw_reasoning_traces",
          "unrelated_session_history",
          "unrelated_historical_sql"
        ],
        "omittedHistory": [],
        "omittedHistoryDigest": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
      }
    },
    "contextDigest": "23c7e85656cb1c3c88a1950548bdb5a59e1aac606055a1f7548f9a0259f522d6"
  }
}
```

Context selection is deterministic and bounded:

- `currentInstruction` is byte-for-byte the sole user-message content and
  `instructionDigest` is lowercase SHA-256 of its exact UTF-8 bytes, with no
  trimming or Unicode normalization; both equal the turn instruction/digest;
- `instructionHistory` contains the initial instruction plus the five most
  recent prior follow-up instructions, ordered by turn ordinal; it excludes the
  current instruction, and every included item carries the SHA-256 digest of its
  exact UTF-8 instruction;
- `validationContext` is null unless the latest validation by ordinal has a
  query digest exactly equal to the editor digest; when present it includes at
  most the first 50 findings in canonical validator order and records the
  omitted count;
- `executionContext` is null unless the latest terminal execution by session
  ordinal has an exactly matching query digest; when present it includes status,
  including `timed_out` or `cancelled`, validation status, duration,
  row-count/truncation facts, at most 128 columns in ordinal order, and a bounded
  sanitized database diagnostic; and
- selection references identify the exact included turns, validation, and
  execution. References and content must agree; a mismatch is a contract error.

Omitted history is explicit but content-free: `omittedHistory` records each
omitted turn ID, ordinal, kind, and instruction digest, while
`omittedHistoryDigest` binds the ordered omitted-reference array. The list is
bounded at 1,000 references; a request exceeding that session limit is rejected
rather than silently dropping provenance.

Both validation and execution contexts are null for dirty/unresolved snapshots
without exact-digest evidence. Result rows are prohibited even when the digest
matches. The schema's constant prohibited-class list also excludes credentials,
connection details, DSNs, hidden reasoning, historical SQL copies, raw chat/raw
model output, and history from unrelated sessions.

`contextDigest` is lowercase SHA-256 of UTF-8 RFC 8785 canonical JSON for the
complete revision object excluding `contextDigest`. `hubRequestDigest` applies
the same rule to the complete v2 Hub request, including the sole current user
message. The frozen context, membership, truncation counts, omissions, and both
digests are persisted before generation. The revision `turnId`, classification,
observed/effective bases, snapshot, and selection references must equal their
turn projection counterparts, with revision `editorSnapshot` equal to the turn
snapshot record's `content`; the gateway rejects any mismatch before calling
Hub.

The writer and different-family reviewer both receive the same revision
context. The reviewer is invoked even when the writer passes structural lint and
may approve that complete candidate or return one complete correction; neither
role returns a patch or chat response. Deterministic validation receives the
current instruction explicitly, and any reviewer correction is revalidated.

The accepted turn snapshots the selected profile name/digest and, for both
writer and reviewer, provider, model class, exact model ID, bounded generation
config, and typed system-prompt ID/version/ref/digest. Full prompt text appears
only in generation-evidence detail. Configuration excludes credentials, and the
two roles must resolve to different `modelClass` values. `promptDigest` hashes
the exact UTF-8 prompt text; `profileDigest` uses RFC 8785 canonical JSON over
the compact profile snapshot excluding `profileDigest`.
Every immutable output's provenance repeats `turnId`, profile and role,
observed/effective/manual base links, snapshot/context/request digests,
prompt/model identifiers, parent version, and trace IDs. Together with the turn
output links this reconstructs `snapshot/base -> writer -> reviewer` without a
reasoning trace.

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

The normative G2.8 contract names are:

- `catalyst.workbench.editor-snapshot.v1` — exact digestable editor content;
- `catalyst.workbench.editor-snapshot-record.v1` — persisted snapshot occurrence;
- `catalyst.workbench.turn.request.v1` — follow-up request;
- `catalyst.workbench.turn.v1` — recorded or labelled legacy turn projection;
- `catalyst.workbench.turn.timeline.v1` — ordered session timeline;
- `catalyst.query.revision-context.v1` — bounded Hub revision context;
- `catalyst.query.request.v2` — OpenAI-compatible Hub follow-up request;
- `catalyst.workbench.generation-evidence.v1` — detailed generation evidence;
- `catalyst.workbench.generation-evidence-ref.v1` — compact evidence link; and
- `catalyst.workbench.turn-failure-diagnostic.v1` and
  `catalyst.workbench.legacy-recovery-references.v1` — typed failure and recovery
  records.

The existing governed endpoints remain unchanged:

- `POST /v1/catalyst/queries`
- `POST /v1/catalyst/previews/{previewId}/execute`

They continue to enforce current policy/preview semantics. UI manual testing
migrates to the workbench API; existing harness suites may continue using the
governed API until W3 adds explicit workbench scenarios.

The session and immutable-version v1 contracts also remain valid. Initial query
generation continues to use Hub `catalyst.query.request.v1`; only follow-up turns
use v2 revision context. Adding the turn endpoints does not add turns to the
existing session payload, so older clients can ignore iteration while newer
clients fetch the timeline independently. Hub output remains
`catalyst.query.v1` for both request versions.
