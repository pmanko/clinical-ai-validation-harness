# Implementation plan: Catalyst Query Workbench and Dashboard Builder

**Status:** Current delivery roadmap. The roadmap and compatible baseline are
merged, and the specification set is consolidated. All four usability iterations
are merged and the first local dual-source walkthrough passed. On 10 September
2026 the owner authorized continuing into saved-work and Dashboard functionality,
with subsequent feedback bringing typography and composer style alignment into
the saved-query iteration. Final local/server evidence
and final owner acceptance remain open.

**Specification:** [spec.md](spec.md)

## Next owner checkpoint — server release and refreshed demos

Approved on 10 September 2026: the next reviewable checkpoint is a working
server release with the current Workbench design and newly recorded demos for
both sources. Finish the current saved-work and Dashboard delivery before this
checkpoint; follow-on A/B/C and model comparison remain separately scheduled.

- Validate the current working UI locally as changes are made, including the
  on/off Advanced mode switch and direct mock-style alignment. Local development
  and testing do not wait for a merge or a release build.
- Complete saved-query reuse, compatible charts/tables, persistent Dashboard
  arrangement, publication and actual Superset import/rendering. Use both retained
  real sources and resolve concrete failures before calling the build ready.
- Merge the tested compatible revisions and release them to the existing demo
  server through the harness wrapper. Keep the final local acceptance build on
  the same merged revisions, preserve retained data, and verify the real journey
  in each environment.
- Re-record the server demos with the new styles. Focus on asking, browsing data,
  reviewing/refining results, reusing saved SQL, creating charts and arranging
  and publishing a Dashboard. Limit FHIR Data Pipes to a brief context segment
  (about 10–15 seconds); retain the detailed ingestion proof in the evidence.
- Present the working server link, the two refreshed videos, local proof and
  any unresolved findings for asynchronous owner review. Update existing public
  video/poster references together. Record owner acceptance separately.

Shorter demos remove repeated explanation; they do not accelerate reading or
shorten the caption/result holds required in step 5 below.

## Authority and scope

This file is the authoritative implementation roadmap and delivery goal for
Feature 008. [tasks.md](tasks.md) is its sole detailed progress and acceptance
register. Scope or sequence changes amend these files rather than creating a
parallel plan.

The [program roadmap](../catalyst-program-roadmap.md) retains evaluation,
comparison, and broader-conversation decisions. The approved delivery priority
is **usability first, then Dashboard Builder functionality**. Model comparison
and broader conversation work remain visible, separately scheduled work and are
not prerequisites for this delivery. The retired
[Catalyst implementation plan](../catalyst-implementation-plan.md) and
[Dashboard delivery goal](dashboard-mvp-delivery-goal.md) point here and define
no current work.

Feature 008 includes the accepted conversation, query notebook, manual Run flow,
typed results, and Dashboard Builder experience over the generic connection.

## Design extension review

The HIV workflow and output proposals are gathered in Catalyst's existing
[staff Workbench design home](../../targets/catalyst/docs/specs/staff-workbench-ux/proposals/catalyst-output-integrations-hiv-draft.md).
The owner approved this disposition on 10 September 2026: keep **Explore /
Saved work**, integrate the richer saved-work structure and saved-SQL reuse,
and schedule the larger extensions after the current usability and Superset
delivery. There is one implementation effort and one approved shell.

| Work | Current state | Roadmap disposition and acceptance |
| --- | --- | --- |
| Saved queries, charts/tables, Dashboards | Existing object storage and libraries; accepted scope | Keep these three groups in Saved work, using existing immutable object identities and review surfaces. The proposed permanent Workbench / Library sidebar is superseded. |
| Start from saved SQL | Confirmed reuse is merged in Catalyst #92; compatible deployment and real-source acceptance remain open | Approved for current saved-work delivery. Load exact saved SQL and typed parameters into the one editor without execution or overwriting saved work; preserve the saved reference and ongoing draft; explicitly handle another source and unavailable historical execution evidence. |
| HIV dashboard walkthrough | Useful proposed scenario; exploratory counts are synthetic and older PostgreSQL links are retired | Check current Spark schema, record deduplication, CD4 count versus percentage, join meaning and unknown gender. The current medication export is undated and uses `doNotPerform`; keep any period exemption visible. Live proof remains required. |
| One request changing several artifacts | Current turns carry SQL writer/reviewer versions; no combined Widget/Dashboard proposal contract | Follow-on A. One turn retains affected artifacts and dependencies; review/apply/discard/undo; exact SQL Run remains explicit; save Dataset → Widget → Dashboard dependencies; failures leave independent work reviewable and dependent work waiting. Demonstrate the combined request in the approved mock before implementation. |
| Design advisors and shared date/filter controls | Proposed prompts and output behavior; currently deferred | Follow-on A. med-agent-hub owns installed prompts/profiles; Catalyst supplies context and validates proposals. Preserve metric meaning, explicit downstream adoption, true date ordering, partial periods, visible exemptions and saved defaults. No required competing agent team. |
| Metabase output | No Catalyst publisher; vendor documents SparkSQL and time grouping | Follow-on B. Select runtime and API versus paid serialization; prove the same source, native render, filter/label semantics, repeat publication, actual receipts and separate configured destinations. |
| Evidence output | No Catalyst publisher; standalone Spark connection unproven | Follow-on C. Pin a compatible self-hosted runtime and components; prove a direct source connection before export/publication work. No copied preview-row dataset or replacement warehouse. |
| Superset date/filter remediation ([harness #111](https://github.com/pmanko/clinical-ai-validation-harness/pull/111)) | Separate active remediation effort; current Catalyst Compose still pins the 6.1.0-dev digest | Preserve existing Superset ownership and acceptance. Integrate only reviewed, merged compatible revisions; verify filters, chronological labels and import behavior in the existing deployment. Do not duplicate remediation in the new output work. |

The current delivery finishes through step 5 below, including owner acceptance.
Then schedule **A: multi-artifact design and shared controls**, **B: Metabase**,
and **C: Evidence**. Each starts with a bounded design/compatibility review and
the acceptance items in [tasks.md](tasks.md#follow-on-milestones-after-current-delivery).
Scheduling these milestones does not approve their draft interfaces or vendor
choices. They do not block current completion. Broader conversation and
model-team comparison retain their separate scheduling.

Extend the approved mock with current saved-work/reuse behavior before its
implementation. Combined Widget/Dashboard requests and SQL-dependent failure
states belong to follow-on A's review. Catalyst remains the design home; the
harness owns publication. When preview files change, sync all six assets under
`site/public/catalyst-design/` and its pinned specification link alongside the
Catalyst revision; the gitlink alone does not change the website.

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

### Physical ownership

| Concern | Owner |
| --- | --- |
| Application behavior, sessions, queries, results, saved objects, and bundles | Catalyst |
| Interaction and visual contract | Catalyst product specification and binding design |
| Profiles, prompts, role mapping, and model settings | med-agent-hub |
| OpenELIS Spark reference assets | Catalyst `analytics/` |
| OpenMRS Spark reference assets | Harness `catalyst-sources/openmrs-hiv/` |
| Combined lifecycle, exact pins, deployments, evidence, and status dashboard | Harness |
| Dashboard rendering and import target | Superset |

The former plan's proposed removal of experimental Catalyst packages is
superseded; assess a package only when an active iteration finds a concrete
owner or dependency. Its comparison and reader-packet work remains separately
scheduled in the program roadmap. Its direct-database replay, automatic scoring,
repeated-judge, engine-specific core, and extra-framework proposals are excluded
by the current authorities.

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

The selected demonstration will use the following path. Harness `main` contains
the accepted compatible integration baseline from pull request #100; live
dual-source acceptance remains open:

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

Land this roadmap and its task register before the baseline implementation.
Only the minimum authority pointers change with it. If the existing source-pair
or conformance gates expose stale integration gitlinks or their canonical
mirrored fixture on `main`, the roadmap pull request may advance them to the
already-reviewed current integration baseline; it does not absorb baseline
product code. Specification consolidation and product behavior begin after this
source of truth is merged.

Exit: current authority entry points name this plan and its task register;
documentation checks and links pass; any required integration repair is limited
to existing reviewed heads and their canonical fixture and passes the unchanged
source-pair and conformance gates.

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

**First owner gate:** run the complete usability design locally against the
real OpenELIS and OpenMRS sources. Publish a side-by-side design comparison,
focused browser evidence, and a paced walkthrough for asynchronous review.
Dashboard functionality expansion starts after feedback from this gate.

### 4. Complete Dashboard Builder functionality

First complete saved queries and visualizations: only a successful current
execution may be saved; immutable versions restore; typed results retain their
meaning; compatible visualizations can be reviewed, selected, and saved. Saved
work groups queries, charts/tables, and Dashboards. **Start from this SQL**
creates a draft from the saved parameterized SQL and typed values without
executing or modifying the saved version, even when historical run details are
unavailable. Preserve the existing draft and source-bound session.

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

Local development serves the current working UI against the real local services.
It may include unmerged work; it is not a release or a final acceptance claim.
The merged-revision requirement applies to the server release and final
reproducible acceptance evidence.

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
- the complete local/server delivery journey and owner review.

A live Spark service is not required for ordinary unrelated pull requests.
Retained demo data is reused. Do not add reseed, restart-persistence,
environment-parity, exhaustive-failure, row-hash, or repeated-judge gates.

## Implementation rule

New code or checks must correspond to a requirement in
[spec.md](spec.md) and an acceptance item in the implementation plan. When a thin
connection, full readable schema, or pinned upstream path fails, record the
specific failure and return to the owner before adding selection, translation,
fallback, or another subsystem.
