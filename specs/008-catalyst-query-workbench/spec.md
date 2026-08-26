# Feature specification: Catalyst Query Workbench and Dashboard Builder

**Status:** The query notebook and binding Dashboard Builder design are
accepted. The generic connection, Phase 1 comparison, and final browser-visible
Dashboard Builder acceptance remain open.

## Purpose

Catalyst helps a person turn a question into reviewable SQL, run the exact query
they select against a configured data source, inspect rows or the database
diagnostic, refine the query in conversation, and promote a successful result
into a Superset dashboard.

Catalyst is a generic SQL-connected application. It does not own ingestion, a
clinical warehouse, or a preferred database engine.

## Authorities

- `../catalyst-program-roadmap.md` owns program order and the Phase 1
  comparison.
- `../catalyst-implementation-plan.md` owns the current
  implementation sequence and acceptance.
- `targets/catalyst/docs/dashboard-builder-mvp-design.md` and its populated
  binding 4c page own Dashboard Builder interaction and visual behavior.

## Product boundary

A data source supplies:

- a stable identifier and label;
- connection information;
- an explicit SQL dialect;
- availability; and
- the complete set of tables, views, columns, and types readable through that
  connection.

Optional source annotations may add descriptions, relationships, units, or
examples. They cannot hide, approve, or rank readable relations.

A session binds one data source when it is created. A person starts another
session to use another source. An unavailable source is reported without
preventing the application from starting or another source from being used.

A Dashboard Builder `Dataset` is an immutable saved query and execution
artifact. It is not a data source, warehouse, or restricted schema copy.

## User journeys

### Ask, inspect, and run

1. The person starts a session against a configured source and asks a question.
2. The model receives the source's declared dialect and the same complete
   readable schema shown by the editor.
3. Catalyst retains the generated SQL, parameters, findings, and provenance.
4. The person may edit and format the query.
5. Run saves the visible draft as an immutable version, records advisory
   findings, and submits the exact selected SQL through the configured
   connection.
6. Catalyst shows bounded typed rows or the database's native diagnostic.
7. A follow-up uses the current visible editor state and retained session
   instructions to produce a complete successor query.
8. Refresh restores the session, selected version, findings, executions, and
   result state.

### Clarify or decline

The writer has three outcomes:

- `ready`: a query candidate is available;
- `needs_clarification`: one clarifying question and no SQL;
- `unsupported`: a concise explanation and no SQL.

Clarification and unsupported turns do not execute SQL or replace the previous
selected query. Gateway contract or orchestration failures remain failures, not
writer outcomes.

### Build and publish a dashboard

1. A successful current execution creates or refreshes one Dataset draft.
2. The person saves an immutable Dataset version.
3. Catalyst suggests a compatible visualization from the typed result shape;
   the person reviews or changes the compatible type.
4. The person saves Widgets, arranges one or more in a Dashboard, and publishes.
5. Catalyst creates a deterministic native Superset bundle in its outbox.
6. The explicit importer records success or an actionable failure.
7. The stable Superset URL opens the rendered dashboard.

Superset renders the saved query against the same configured data source.
Catalyst does not implement a second chart runtime or embed result rows in the
bundle.

## Requirements

### Connection and schema

- A source configuration MUST contain an identifier, label, connection
  configuration or reference, and explicit dialect. Credentials MUST NOT appear
  in browser payloads, logs, or stored evidence.
- Catalyst MUST use the simplest connection implementation supported by the
  chosen client. It MUST NOT require a connector framework or translate SQL
  between engines.
- Schema discovery MUST include every table, view, column, and type readable
  through the connection. Tests MUST prove inclusion with arbitrary fixture
  names rather than a fixed count.
- The model request, Available data view, editor completion, validation, and
  execution MUST use the same source identity, dialect, and schema snapshot.
- Optional annotations MAY enrich the live schema but MUST NOT filter it.
- A schema refresh MUST show changed access without making ordinary application
  startup depend on a previous schema snapshot.
- One unavailable source MUST NOT prevent another source or the application
  shell from remaining usable.

### Query generation and context

- The current instruction is authoritative.
- A follow-up MAY receive prior user instructions, the current editor snapshot,
  relevant failure information, and verified examples from the same session.
- Evidence MUST record the context actually sent and any omitted item with its
  reason. The application MUST NOT silently summarize, rank, or substitute
  context.
- Result rows MUST NOT enter model context.
- Writer and checker identities, prompts, settings, source, dialect, schema
  snapshot, and query lineage MUST remain inspectable.

### Editor and execution

- Exactly one editable SQL control exists in the active turn.
- Highlighting, formatting, and keyword/function completion MUST follow the
  selected source's declared dialect. Relation and column completion MUST come
  from the shared live schema.
- Formatting and validation MUST NOT execute SQL.
- Validation is advisory. Findings MUST remain visible but MUST NOT disable Run
  or rewrite the selected SQL.
- Run MUST submit the exact visible SQL and typed parameters through shared
  connection-execution code used by generated and manually edited queries.
- The configured connection or deployment MUST enforce read-only access.
  Catalyst MUST apply a time limit and returned-row limit.
- Successful execution MUST retain typed columns, bounded rows, counts, source,
  dialect, query digest, and timing. Failure MUST retain the database's native
  diagnostic without pretending it was a model failure.
- A normal bad query or database diagnostic is a valid experimental observation.

### Notebook and state

- Each generated, manually edited, or checker-produced query version is
  immutable and has one explicit parent when applicable.
- Only the latest turn owns the editor. Earlier turns remain readable summaries.
- A stale successful result remains inspectable after an edit and is visibly
  marked stale until the new digest runs successfully.
- New session is explicit and is the only action that clears the active thread.
- Refresh MUST restore durable product state without reseeding the source data.
- The working surface MUST remain keyboard operable with visible focus, usable
  error announcements, and the accepted desktop and narrow-layout behavior.

### Dashboard Builder

- Only a successful execution for the exact current query digest may create a
  Dataset draft.
- The Dataset panel owns the sole full row-table presentation for that result.
- Dataset, Widget, and Dashboard saves MUST be immutable, idempotent for the same
  content, and retain their source and query lineage.
- Visualization compatibility and the initial suggestion MUST be deterministic
  from the typed result shape. The person MUST be able to review and choose
  another compatible type.
- A Dashboard MUST contain Widgets from one source. Every saved Dataset retains
  the readable-schema snapshot used for its query; a harmless later schema
  refresh does not by itself prevent combining same-source Datasets.
- Publication MUST create a deterministic Superset bundle and expose the same
  bytes for download.
- Import status MUST be based on an explicit importer receipt. A bundle's
  existence alone MUST NOT be shown as imported.
- The stable Dashboard URL MUST open only after the selected bundle imports
  successfully.
- Superset MUST render the originating saved Dataset through the configured
  connection. Acceptance inspects one rendered value against the originating
  Catalyst result and performs no second database query.
- Superset application programming interface publication, embedded viewing,
  bidirectional synchronization, sharing, scheduling, and model-generated chart
  specifications are outside this milestone.

### Phase 1 evaluation

- Each ready-turn scenario reference is authored, run, and reviewed once after
  the accepted Spark-readable source exists or when the scenario deliberately
  changes. Clarification and unsupported turns have reviewed expected responses.
- A comparison MUST NOT rerun reference SQL.
- Each ready model turn submits its selected SQL through Catalyst exactly once
  and retains either rows or the database error.
- Clarification and unsupported turns execute no SQL.
- The reader packet MUST contain the complete conversation, actual model
  context, selected SQL, result or diagnostic, static reference, one
  human-readable rubric, and relevant provenance.
- Automated checks MAY establish collection and contract facts. They MUST NOT
  compute factual equivalence, a score threshold, rank, tie-break, automatic
  disqualification, or winner.
- One full suite per selected model team and one full-context reader pass are the
  default. Additional complete runs or readers require a deliberate choice.
- An incomplete collection MUST be reported as incomplete rather than accepted
  or invalidated by an arbitrary failure allowance.

## Selected reference deployment

The selected demonstration will use retained demo data only:

```text
OpenELIS or OpenMRS FHIR
  -> FHIR Data Pipes -> Parquet -> Spark SQL
  -> Catalyst and Superset
```

Each reference source actually included in the demonstration or comparison MUST
prove one live source-to-browser path when integrated. Its ingestion files,
ViewDefinitions, and optional descriptions belong to the source deployment, not
Catalyst core. The retained demo data is reused; ordinary development does not
require reseeding, environment parity, or a live Spark service on every pull
request.

## Phase 1 acceptance

Phase 1 is accepted when:

- repository instructions and active contracts contain no conflicting engine,
  catalog, evaluation, or evidence requirements;
- a generic source exposes arbitrary readable relations to both model and editor;
- a warning does not block exact SQL and a native engine error is shown;
- FHIR Data Pipes produces nonempty Parquet and Spark exposes the expected
  reference relations;
- Catalyst completes one successful and one invalid browser query through Spark;
- one intentional write attempt reaches the Spark connection, is visibly
  refused, and leaves source data unchanged;
- one successful result is saved, published, imported, and rendered in Superset;
- the harness has no direct analytics-database or per-run reference path;
- the report gives a human or selected frontier reader the complete case and
  rubric without an automatic verdict, and identifies a frontier-model review
  as one model-reader pass rather than independent human review; and
- the owner inspects the real product path and accepts the Phase 1 report.

The Dataset-to-Superset step above is a regression smoke for the generic
connection. It does not complete Dashboard Builder.

## Phase 3 Dashboard Builder acceptance

Dashboard Builder completes only when the live Workbench, Dataset review and
library, Widget review and library, Dashboard library and arrangement, and all
publish/import states are compared side by side with the binding design. The
comparison must confirm that profile selection, generation and failure evidence,
Clear/Restore, complete Available data browsing, the fixed composer and thread,
the single editor, review panels, multiple Widgets, and actionable publication
states remain present. Final acceptance requires the owner's browser review.

## Out of scope

- a curated or approved application schema;
- fixed relation counts, relation ranking, or silent context truncation;
- a universal connector framework or cross-engine SQL translation;
- a shadow analytics warehouse or automatic database fallback;
- per-run reference execution or a second direct-database comparison;
- automatic factual-equivalence scoring, numerical thresholds, or
  mandatory repeated judges;
- production authentication, authorization, row-level access, or sensitive-data
  policy for this demo-only stage;
- restart, reseed, worktree-persistence, local/demo parity, exhaustive failure
  matrices, or live-database checks on every pull request.
