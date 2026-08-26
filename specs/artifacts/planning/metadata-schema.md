# Metadata Schema v0

The metadata schema supports the constitution's provenance and traceability
requirements in `.specify/memory/constitution.md`.

Each run emits:

- `run_manifest.json`
- `events.jsonl`

## Manifest Fields (minimum)

- `run_id`
- `project`
- `component`
- `git_sha`
- `dataset_id`
- `dataset_version`
- `schema_mapping_version`
- `generated_at`
- `otel.gen_ai.provider.name` for runs that invoke an LLM; non-LLM runs omit it
- `otel.gen_ai.operation.name`
- `target_provenance`

Publishable Catalyst notebook runs additionally require:

- `report_family = "catalyst"`
- `suite_id`
- `suite_sha256` (SHA-256 of the exact input suite bytes)
- `resumedFrom` when this recovers an interrupted Catalyst run;
- `resumeAncestry`, ordered oldest to newest, when recovery spans one or more
  interrupted runs;
- `evidence_status = "development"` until the active Phase 1 roadmap's
  comparison-publication and real-product closeout requirements are met; live
  publication alone does not promote the evidence status

The runner writes `run-config.json` before discovery, warm-up, or measured
conversation calls. It is the exact public run seed: database passwords and
password-bearing URLs, absolute workstation paths, non-local private addresses,
and security-group rule identifiers are rejected. The local password is resolved
only in memory when a database check is requested. Review, reporting, and
publication read the frozen file without resolving that password.

A Phase 1 comparison run records one conversation for every declared
team-and-scenario cell. A repeated measure is a separate complete run with its
own identity; legacy notebook suites that repeat an individual cell do not
define the Phase 1 collection shape.

`run-status.json` is an atomically replaced lifecycle projection with
`state = incomplete | invalid | complete`, `measurementValid`, the direct and
full recovery ancestry, and infrastructure failures retained across that chain.
An abrupt stop therefore leaves an actionable `incomplete` source; a normal
completion writes `complete` only when every measured conversation is valid.
Because Catalyst can persist an upstream or process interruption inside a
successful workbench response, these entries retain both the actual HTTP status
and the persisted `failureStage` and `failureCode`. Completed model answers and
model-quality failures are not relabeled as interruptions. Harness-observed
availability changes use separate `interruptionKind` and `interruptionCode`
fields, so they cannot be mistaken for Catalyst's own turn-failure stages. Each
interruption is also appended to signed `interruptions.jsonl`; recovery combines
that record with the lifecycle projection without duplicating it. A recovery
copies each inherited interruption file into its own source-qualified evidence
directory, points the carried failure at that copy, and retains the original
path as `sourceEvidencePath`.

The evidence index and checksum are refreshed through temporary files as
evidence is written. Each completed `rows.jsonl` prefix is indexed before
collection proceeds. A recovery accepts that signed prefix, ignores an entirely
unsigned stream or unsigned tail, and rejects changed signed rows, missing
indexed files, unindexed conversation files, or a bad index checksum.

Every profile with new model calls records one excluded warm-up under
`warmups/<profile>/` before those calls. A recovery that only reuses completed
cells makes no new warm-up call; it copies the source warm-up beneath that same
profile directory and records its source run. Warm-up sessions never appear in
`rows.jsonl`, `results.jsonl`, `results.json`, or the recorded conversation
count.
Each measured row records `evidencePrefix`, `measurementValid`, and an
outcome-specific `measurementEvidence` projection, plus its original start and
end times so recovered feeds retain trace correlation. Ready paths state the
validation decision, execution decision, and oracle result. Clarification and
unsupported paths prove that no new query, validation, execution, or oracle call
occurred.

A recovery run writes `recovery-import.json`. Before any warm-up or measured
model call, the runner checks the exact suite, frozen seed, revisions, discovery
identities, scenario order, and every eligible source-evidence digest. Imported
files are copied without rewriting, hashed again in the recovery run, and indexed
with their source run and source digest. Model-quality failures remain eligible;
infrastructure failures, pre-turn failures, partial cells, and duplicate cells do
not. Recovered cells regenerate the normal result feed and events from their
copied evidence, so the new run directory remains a complete reader-facing unit.

Catalyst Dashboard Builder acceptance runs use
`report_family = "catalyst_dashboard"` and additionally require:

- `dashboard_evidence_schema_version = "harness.catalyst-dashboard.acceptance.v1"`;
- exact Harness and Catalyst revisions plus clean/dirty and pin state;
- selected Gateway profile and writer/reviewer provider, model, configuration,
  prompt, candidate, and output digests for the model-backed query turns;
- `data_source_id` and `catalog_version` for the Dashboard's locked source pair;
- Superset application image digest, platform version, metadata-database image
  digest, PostgreSQL driver package/version, and bundle-contract version;
- references to the exact `acceptance.json`, bundle, desired `current.json`,
  import receipt/latest-per-digest projection, atomic per-Dashboard last-
  verified projection, PostgreSQL reconciliation, and accessibility
  evidence, including the scoped import-failure boundary and any explicit
  full-reset/reimport-last-verified recovery sequence; and
- `evidence_status = "development"` until the D1e user acceptance event exists.

Dashboard evidence extends the existing manifest rather than rewriting it after
the run. Later import, reconciliation, accessibility, and acceptance facts are
append-only events and the separately validated `acceptance.json` projection.

For Catalyst query-validation runs, `target_provenance` contains separate,
control-plane-compatible Catalyst and Med-Agent Hub entries. The runner rejects
an uninitialized, dirty, or pin-mismatched target before contacting either
service. The Catalyst entry records the suite and the preflight dataset-overview
and editor-catalog payloads with canonical SHA-256 digests; the exact runtime
catalog version becomes `schema_mapping_version`. The Hub entry records the
selected profile discovery payload and digest. Writer/reviewer provider evidence
must agree, and the resulting provider becomes `otel.gen_ai.provider.name`; the
suite's provider is an expected value, not the evidence source. A run that fails
before profile discovery records the provider as unresolved. Catalyst model
operations use `otel.gen_ai.operation.name = chat`.

Each recorded turn preserves its own `revisionContext`. For a follow-up this
includes the current instruction, the complete retained prior-instruction
history, the observed and effective base, the editor snapshot, relevant
validation and execution summaries, verified examples, explicit experimental
guidance, and the selection/omission facts supplied for that turn. Initial
turns have no revision context. The harness compares this per-turn context with
the revision context inside every actual writer and reviewer request; raw result
rows and the other prohibited context classes remain excluded.

Every actual writer or reviewer invocation also retains the Hub's
`med-agent-hub.catalyst-role-request-evidence.v1` record: the configured role,
model, exact system and caller messages, response format, effective model
configuration, rendered prompt and digest, tokenizer, context window, output
reserve, prompt-token count, required-token total, and fit decision. The
invocation `requestDigest` must equal the nested Hub `requestDigest`. A
successful invocation must have exact counts that fit and agree with its
four-field `tokenAccounting` projection. A known pre-dispatch capacity rejection
must instead prove that `promptTokens + outputReserve` exceeds `contextWindow`
and retain Hub error code `context_window_exceeded` with HTTP status 422. A
catalog preflight may answer `needs_clarification` or `unsupported` with an
affirmatively empty invocation list; it owes no model-request or token evidence.

### Reader-led comparison review

A complete reader-led comparison freezes `reader-rubric.md` beside the run
evidence. `reader-review-input.json` is then prepared from that exact run. It
contains the rubric and its SHA-256 digest, the full suite including each
question-specific reference query, the run manifest and public run
configuration, the model-team definitions, the collection-completeness facts,
and every conversation and turn with its stored generation, validation,
PostgreSQL, cross-check, and independent-answer evidence. A wrong answer or
database diagnostic stays in this package as experimental evidence.

Each attached review is a nonempty `reader-reviews/<name>.md` file with a
matching `reader-reviews/<name>.json` metadata file. The metadata names the
reviewer, provider, model, model version, and review time and records
`reviewInputSha256`, the SHA-256 digest of the exact
`reader-review-input.json` the reviewer received. Reporting and publication
reject an attached review when that digest does not match the current input. A
second perspective remains a separate review with its own metadata; reviews
are not combined into an automatic numerical result.

`otel.gen_ai.provider.name` is the canonical provider field. The deprecated
`otel.gen_ai.system` spelling is not emitted or accepted; this resolves the N6
field-name question without carrying two conflicting provider identities.

Validation comparison runs also emit `dataset_provenance` with:

- the selected comparison-set file and SHA-256;
- every selected scenario file and SHA-256;
- every patient chart fixture and both file and canonical-ledger SHA-256;
- any missing patient fixtures;
- the locally restored corpus receipt and source-dump SHA-256 when available; and
- one combined SHA-256 over that complete run input identity.

The corpus receipt is created by `scripts/seed-local.sh` only after the portable dump
and its provenance sidecar pass `scripts/verify-portable-dump.py`. Fixture/live ledger
equality is still enforced immediately before a run; manifest hashes make that checked
input identity auditable afterward.

## Event Types

- `run`
- `query`
- `retrieval`
- `model`
- `response`
- `evaluation`
- `profile_discovery_failed`
- `runtime_identity`
- `runtime_identity_failed`
- `reviewer_change_record`

Catalyst notebook streams use
`schema_version = "harness.catalyst-notebook.event.v1"` and additionally emit:

- `scenario` for one suite scenario/repetition outcome;
- `turn` for initial and follow-up turn lineage;
- `version` for the selected base and complete successor query identifiers and
  digests;
- `execution` for an explicit execution linked to its immutable query version.

Notebook event `evidence_paths` are run-directory-relative, traversal-safe, and
must resolve to materialized evidence. Reader-led reviews use the review
artifacts and digest binding described above; they do not emit an automated
judge event. The finalizer appends events idempotently and never rewrites the
run-start manifest. SQL result rows, credentials, and raw model traces are
excluded from the event stream.

Legacy notebook runs may contain `judge.jsonl`, `judge_manifest.json`, and an
`evaluation` event with `evaluation_type = "catalyst_sql_judge"`. Those files
describe the older automated scoring workflow only. They remain readable for
historical reports but are not produced, required, or consulted by reader-led
comparisons.

### Catalyst Dashboard Builder events and acceptance

Dashboard Builder streams use
`schema_version = "harness.catalyst-dashboard.event.v1"`. The D1 emitter keeps
the accepted notebook stream unchanged and projects its exact source lineage
into schema-valid `query_turn`, `query_version`, and `query_execution` records
with traversal-safe references to the source notebook/API evidence. It then
adds:

- `query_turn` for initial/follow-up role, instruction digest, exact base and
  selected Query versions, outcome, and source evidence;
- `query_version` for the selected base/successor Query version and digest,
  author role, turn, and source evidence;
- `query_execution` for one successful Run and its Query/result digests plus
  source evidence;
- `dataset_version` for one immutable Dataset version and its exact execution,
  query, source/catalog, canonical result, and configuration digests;
- `widget_version` for one immutable Widget version, Dataset parent, compatible
  presentation/bindings, and accepted-versus-overridden disposition;
- `dashboard_version` for one immutable Dashboard version, locked
  `dataSourceId`/`catalogVersion`, ordered Widget versions, and layout digest;
- `bundle_published` for the Dashboard version, deterministic bundle ID/digest,
  outbox pointer digest, stable Superset UUID/slug/URL, and publication timing;
- `superset_import_attempt` for exact bundle/pointer identity, importer/runtime
  revisions, outcome/stage, CLI status, stable error code, receipt reference to
  the separately bounded diagnostic,
  failure-boundary classification, preservation support, per-Dashboard last-
  verified projection/bundle identity, linked explicit recovery attempt,
  automatic-bootstrap/retry suppression, and verified
  UUID/slug/relationships when available;
- `superset_status_observed` for the exact dashboard/bundle status projection
  and receipt/latest digest used to derive it;
- `postgresql_reconciliation` for reproducible SQL, parameter and result
  digests, bounded inspected record identifiers/values, Superset observations,
  and reviewer rationale;
- `accessibility_observation` for viewport/zoom/input mode, assertion outcome,
  and screenshot/video/test evidence references; and
- `acceptance_decision` for the final user decision, timestamp, accepted D1
  version/digest set, residual risks, and evidence-index digest.

Dashboard event entity references are immutable and resolvable. Clinical rows,
database credentials, Superset secrets, raw model traces, and localized warning
prose are excluded. The canonical result reference uses the RFC 8785 digest of
`{contractVersion, columns, rows, returnedRows, maxRows, truncated,
truncationReason, warningCodes}`; row-free `executionBounds` and `resultBounds`
must be byte-identical. Stable warning codes are de-duplicated in persisted
execution order. D1 recognizes `all_blank_columns` and
`legacy_unclassified_warning`; adding another code requires a versioned
contract change.

`acceptance.json` uses
`schema_version = "harness.catalyst-dashboard.acceptance.v1"` and is valid only
when it resolves:

- the manifest/event schema versions, run ID, evidence status, and exact
  component/image/driver revisions;
- real writer/reviewer profile and candidate/output digests;
- session, turn, query-version, execution, Dataset, Widget, Dashboard, bundle,
  publication, and import-attempt identifiers/digests;
- the expected and observed stable Superset Dashboard UUID,
  logical Catalyst Dashboard ID, `catalyst-<lowercase-dashboard-id>` slug, and
  `/superset/dashboard/<slug>/` URL;
- exact bundle, desired-current-pointer, receipt/latest-per-digest,
  per-Dashboard-last-verified, and evidence-index copies and SHA-256 digests;
- PostgreSQL reconciliation SQL/parameters, inspected bounded IDs/values,
  comparison outcome, and reviewer rationale;
- restart, idempotency, changed-child, and layout-only evidence; preserving
  pointer/bundle/preflight/credential and transactionally rolled-back CLI
  failure evidence;
  post-import-verification `Import failed`, retained-diagnostic, and disabled
  Open/current-success evidence; missing/corrupt recovery-projection refusal;
  full Superset-local metadata/home reset and last-verified reimport evidence;
  recovered-A/failed-desired-B automatic-bootstrap/retry suppression without an
  automatic-rollback claim;
  read-only denial, five-family, and accessibility evidence references; and
- final user acceptance state and residual risks.

It also contains a fixed six-step `orderedWorkflow` projection whose event
sequences and identifiers must resolve, in order, to initial Query selection,
successful initial Run, Dataset v1 save, contextual follow-up, successful
successor Run, and Dataset v2 save. The cross-artifact validator rejects a
schema-valid receipt if sequences are not strictly increasing, Dataset v1 does
not precede the follow-up, either Dataset references the wrong execution/Query,
or Dataset v2 does not follow the successor Run.

Every referenced path is run-directory-relative, traversal-safe, and materialized
before acceptance validation. An early failure records typed omissions and its
failure stage; it never invents identifiers unavailable before parsing or
verification. A missing or invalid reference keeps the receipt and run in
`development` and prevents D1 completion.

## OTel GenAI Alignment

When available, map fields to:

- `gen_ai.provider.name`
- `gen_ai.operation.name`
- `gen_ai.agent.name`
- `gen_ai.request.model`
- `gen_ai.tool.name`

Keep clinical-specific fields in extension payload:

- retrieved record ids
- cited record ids
- claim support labels
- abstention label
- reviewer label
- decision rationale
- mapping version
- component pin and working-tree state
- profile/model/configuration/prompt digests
- canonical row digests and bounded record identifiers for query-table evidence

Evaluation and review events should record why the cited evidence supports,
does not support, or is insufficient for a validation decision. This keeps
alignment and safety claims reviewable instead of reducing them to outcome
labels alone.
