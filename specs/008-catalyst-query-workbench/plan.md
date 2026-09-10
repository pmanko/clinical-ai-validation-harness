# Implementation plan: Catalyst Query Workbench and Dashboard Builder

**Status:** Approved delivery roadmap. Persist this plan before baseline, product,
deployment, or specification changes. The current work order is stable baseline,
specification consolidation, the complete frozen usability design, Dashboard
Builder functionality, and local/server evidence.

**Specification:** [spec.md](spec.md)

## Authority and scope

This file is the authoritative implementation roadmap and delivery goal for
Feature 008. [tasks.md](tasks.md) is its sole detailed progress and acceptance
register. Scope or sequence changes amend these files rather than creating a
parallel plan.

The [program roadmap](../catalyst-program-roadmap.md) retains evaluation,
comparison, and broader-conversation decisions. The approved delivery priority
is **usability first, then Dashboard Builder functionality**. Model comparison
and broader conversation work remain visible, separately scheduled work and are
not prerequisites for this delivery. The legacy
[Catalyst implementation plan](../catalyst-implementation-plan.md) remains a
source during the consolidation iteration; it no longer sets delivery order.

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

The selected demonstration will use the following path. Harness `main` does not
yet contain the accepted integration baseline; candidate integration exists and
live acceptance remains open:

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

## Approved delivery sequence

### 0. Persist this roadmap

Land this roadmap and its task register in a documentation-only pull request.
Only the minimum authority pointers change with it. Specification consolidation,
baseline code, and product behavior begin after this source of truth is merged.

Exit: the pull request is documentation-only; current authority entry points name
this plan and its task register; documentation checks and links pass.

### 1. Establish a stable Harness/Catalyst/Hub baseline

Use the existing harness integration work as the baseline. Account for the
accepted Catalyst and med-agent-hub repair revisions, pin merged product
revisions, preserve valid OpenMRS integration pins, and run existing repository
and integration checks before merging the baseline to `main`. OpenMRS upstream
publication is tracked separately and does not block Catalyst delivery.

Exit: one merged harness baseline names clean remote-reachable Catalyst and Hub
revisions; the ordinary repository-line check passes from `main`; superseded
child work has a recorded disposition; local Catalyst lifecycle uses that exact
baseline without reseeding retained data.

### 2. Consolidate current specifications and planning

Preserve one responsibility per current authority:

| Authority | Responsibility |
| --- | --- |
| Catalyst product specification | Application behavior and contracts |
| Catalyst binding design | Current interaction and visual requirements |
| Harness program roadmap | Evaluation, comparison, and separately scheduled conversation decisions |
| Feature 008 specification | Integration requirements and delivery acceptance |
| This plan | Implementation sequence and delivery goal |
| Feature 008 tasks | Detailed progress and acceptance evidence |

Absorb the legacy implementation plan into this plan and the separate Dashboard
delivery goal into the Feature 008 specification. Replace retired bodies with
successor links. Preserve frozen mocks, research, overlap findings, and prior
handoffs as dated evidence. Align README, agent instructions, SpecKit pointers,
and existing document checks without adding prose hashes or another status
ledger.

Exit: no unique current requirement is lost; no competing implementation
sequence remains; current documents agree on approved UX behavior; every prior
effort is completed with evidence, active here, superseded with a destination,
or deferred with a next action.

### 3. Implement the frozen usability design

Deliver small reviewable product changes in this order:

1. **Question writing:** shared resizable initial and follow-up composer with
   Expand/Restore; preserve drafts and focus across failure and retry; preparing
   a question never executes SQL.
2. **Shell and appearance:** Explore/Saved work, frozen light/dark design, quiet
   View options, and workspace-wide Advanced mode; retain every session and
   analyst capability without losing question, editor, parameter, source,
   profile, execution, or result state.
3. **Available data:** complete nonmodal schema search beside the draft; expose
   exact identifiers and types without fetching clinical result rows; handle
   loading, retry, source changes, focus, and narrow layouts.
4. **Result review:** one full result table, plain warnings and limits,
   accessible provenance, and preserved save/publication behavior.

**First owner gate:** deploy the complete usability design locally against the
real OpenELIS and OpenMRS sources. Publish a side-by-side design comparison,
focused browser evidence, and a paced walkthrough for asynchronous review.
Dashboard functionality expansion starts after feedback from this gate.

### 4. Complete Dashboard Builder functionality

First complete saved queries and visualizations: only a successful current
execution may be saved; immutable versions restore; typed results retain their
meaning; compatible visualizations can be reviewed, selected, and saved.

Then complete Dashboards and publication: multiple Widgets can be arranged and
restored; publication is deterministic; import status follows actual receipts;
failures remain actionable; successful import opens the rendered Superset
Dashboard. Inspect one visible value against its originating Catalyst result
without a second database query.

Exit: the live Workbench, Dataset review/library, Widget review/library,
Dashboard library/arrangement, and every publish/import state are compared with
the current binding design and pass focused API, component, accessibility,
desktop, and narrow-layout checks.

### 5. Deploy and publish evidence

Deploy exact merged compatible revisions locally and to
`catalyst.openelis-global.org` with the harness lifecycle wrapper and retained
data. For OpenELIS and OpenMRS in each environment, prove drafting, schema
browsing, generation, explicit execution, refinement, saving, visualization,
Dashboard arrangement, publication, import, and Superset rendering. Run importer
operations from the checkout that owns the tested environment.

Reuse the existing Playwright capture and deterministic video renderer. Cards
and short captions remain visible for at least five seconds; longer text uses
approximately three words per second plus two seconds. Results and detailed
views remain for at least eight seconds. Reading and interaction stay at normal
speed, accelerated waits remain visible and labelled, holds retain captions,
and captions do not cover the demonstrated information. Watch every final cut
at normal speed before publication.

Archive raw footage immediately with traces, timestamps, exact revisions,
source/model configuration, and importer receipts. Use new immutable media
filenames and update every public video/poster reference together.

Exit: both local and server deployments have real-path evidence for both
sources; paced public videos identify the matching revisions; current public
references and explicit owner acceptance are recorded.

## Iteration and tracking rules

Each product iteration may use multiple small pull requests. Each pull request
updates affected behavior tests and documentation, runs the relevant unit or
contract tests plus UI type checking, lint, build, and deterministic browser
checks, and records what ran and what remains unresolved. Live model and Spark
proof is required at the named integration gates rather than every presentation
pull request.

Owner review is asynchronous. Implementation, merge, deployment,
self-validation, and owner acceptance remain separate task states. The project
status dashboard links to this plan, tasks, pull requests, deployments, and
evidence; it does not duplicate this checklist.

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
