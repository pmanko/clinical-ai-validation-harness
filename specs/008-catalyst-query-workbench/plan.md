# Implementation plan: Catalyst Query Workbench and Dashboard Builder

**Status:** Generic connection, Spark reference deployment, and final product
acceptance remain open.

**Specification:** [spec.md](spec.md)

## Authority and scope

This plan describes how Feature 008 fits together. The implementation sequence,
review pauses, and acceptance for the current implementation live in
`../catalyst-implementation-plan.md`. The Catalyst program
order and comparison method live in `../catalyst-program-roadmap.md`.

Feature 008 includes the accepted conversation, query notebook, manual Run flow,
typed results, and Dashboard Builder experience over the generic connection.

## Architecture

```text
person
  -> Catalyst UI
  -> Catalyst Gateway
       -> med-agent-hub for model calls
       -> configured SQL connection for schema and query execution
       -> SQLite for Catalyst operating metadata
       -> outbox for Superset bundles
  -> Superset connected to the same data source
```

The configured data source is external to Catalyst. Its ingestion pipeline and
warehouse lifecycle are deployment concerns.

### Connection boundary

Use the existing `AnalyticsProtocol` and `DataSourceBundle` seams. The common
connection behavior is limited to:

- availability;
- complete readable schema discovery;
- exact SQL execution with typed parameters, a time limit, and a row limit; and
- typed rows or the error returned by the database.

The source configuration contains a stable identifier, label, connection
configuration or reference, and explicit dialect. Use the simplest client shape
that works. Do not add a connector framework, translation layer, or
source-specific product interface.

Both generated and manually edited queries use the same shared
connection-execution code. Their existing product endpoints may remain separate.

### Schema and model context

Live discovery is the source of truth for visible relations and columns.
Optional annotations add descriptions without filtering the schema. The same
source identity, dialect, and schema snapshot feed:

- the model request;
- Available data;
- editor completion and formatting;
- advisory validation; and
- recorded execution identity and configuration.

A session stays bound to one source. Another source uses another session.

### Product state

Catalyst stores session, turn, query-version, execution, Dataset, Widget,
Dashboard, publication, and importer-receipt metadata in its existing operating
store. Clinical result rows remain bounded execution evidence and are not copied
into model context or a second warehouse.

The browser retains one active editor, immutable query versions, explicit Run,
database errors, stale-result behavior, refresh restoration, and the
accepted Dashboard Builder shell.

### Dashboard publication

A successful current execution may become an immutable Dataset. Deterministic
typed-result rules suggest a compatible Widget. One or more saved Widgets form a
Dashboard. Publication writes a deterministic native Superset bundle to the
outbox; the explicit importer records success or failure.

Superset connects to the same configured data source and renders the saved
query. Acceptance compares one visible value with the originating Catalyst
result. It does not open a second database path.

## Selected reference deployment

The selected demonstration will use the following path. Its implementation and
acceptance are open:

```text
OpenELIS or OpenMRS FHIR
  -> pinned FHIR Data Pipes
  -> Parquet and applicable ViewDefinitions
  -> Spark SQL
  -> Catalyst and Superset
```

OpenELIS deployment assets live with Catalyst. OpenMRS HIV deployment assets live
under `catalyst-sources/openmrs-hiv/`. The harness assembles the local stack
through `scripts/catalyst-mvp.sh`.

Whether the two sources share a Spark endpoint is an implementation finding.
Use the pinned upstream path first and return to the owner before adding a
namespace service, fork, or shadow store.

## Documentation status

Current documents state one product and evaluation design, and local links and
central architecture checks pass. Owner review of the planning diff remains
open.

## Delivery sequence

### 1. Generic Catalyst connection

Implement the thin connection boundary, live schema discovery, active-dialect
editor behavior, advisory Run, rows/native diagnostics, and independent source
availability.

Exit:

- arbitrary readable fixture relations reach model and editor;
- descriptions do not filter;
- valid and invalid exact SQL both reach the connection;
- an unavailable source does not prevent startup;
- focused connection and UI tests pass.

Pause for review before changing the reference deployment.

### 2. Spark reference path

Enable the pinned FHIR Data Pipes Parquet and Spark path, connect Catalyst and
Superset, and prove each reference source actually included as it is integrated.

Exit:

- nonempty Parquet and applicable ViewDefinitions exist;
- Spark and Catalyst return a known source fact;
- one successful browser query and one native error are visible;
- one Dataset-to-Superset render works;
- no substituted clinical analytics store or fallback participates.

Pause for owner review of the live product.

### 3. One runtime path and reader-led harness

Delete engine-specific analytics code, generated-catalog filtering, copied
marts, sink scripts, direct-database harness checks, automatic result matching,
automatic verdicts, and their dedicated tests. Re-author scenario references
once against the accepted Spark surface.

Exit:

- the harness executes only selected model SQL through Catalyst;
- design-time references are never rerun during comparison;
- the reader receives complete cases and a human-usable rubric;
- an incomplete collection is labelled incomplete;
- focused harness/report tests and ordinary repository checks pass.

### 4. Fresh Phase 1 comparison

Run each selected model team through the same complete scenario suite once.
Store the complete reader packet, apply one shared rubric in one deliberately
initiated full-context review, publish the report, and pause for owner review.

### 5. Define Phase 2

Review the Phase 1 report, then set the broader conversation-mode scope and
acceptance. Do not infer Phase 2 requirements during Phase 1 implementation.

### 6. Complete Phase 3 Dashboard Builder

Finish the accepted product behavior against the generic connection:

- route coverage for Dataset, Widget, Dashboard, and publication actions;
- lossless typed execution-to-Dataset conversion for the active dialect;
- deterministic compatible visualization suggestions and overrides;
- deterministic native Superset bundle and publication status;
- browser-visible publish, import, stable URL, and rendered result;
- evidence sufficient to trace the visible flow and diagnose failure; and
- accepted keyboard, focus, error, desktop, and narrow-layout behavior.

Compare the live Workbench, Dataset review and library, Widget review and
library, Dashboard library and arrangement, and publish/import states side by
side with the binding design. Do not turn acceptance into repeated-run, restart,
reset, recovery, or independent database-reconciliation programs.

## Validation strategy

Use the smallest proof that establishes each boundary:

- focused unit and contract tests for connection, schema, exact execution, and
  reader-packet behavior;
- one live source-to-Spark-to-Catalyst path as each reference source is
  integrated;
- one successful browser query and one native engine error;
- one Dataset-to-Superset render; and
- the final full comparison.

A live Spark service is not required for ordinary unrelated pull requests.
Retained demo data is reused. Do not add reseed, restart-persistence,
environment-parity, exhaustive-failure, row-hash, or repeated-judge gates.

## Implementation rule

New code or checks must correspond to a requirement in
[spec.md](spec.md) and an acceptance item in the implementation plan. When a thin
connection, full readable schema, or pinned upstream path fails, record the
specific failure and return to the owner before adding selection, translation,
fallback, or another subsystem.
