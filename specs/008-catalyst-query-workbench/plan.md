# Implementation plan: Catalyst Query Workbench and Dashboard Builder

**Status:** Current delivery roadmap. The roadmap and compatible baseline are
merged, and the specification set is consolidated. All four usability iterations
are merged and the complete local dual-source walkthroughs passed. On 10 September
2026 the owner authorized continuing into saved-work and Dashboard functionality,
with subsequent feedback bringing typography and composer style alignment into
the saved-query iteration. The replacement light-mode videos are published.
The exact merged server release is healthy, but its first full evidence run
failed during a slow follow-up generation and exposed missing downstream
cancellation. Final full server evidence and owner acceptance
remain open. Responsiveness and URL-addressable sessions are the next product
checkpoint after the current release is stabilized and accepted.

**Specification:** [spec.md](spec.md)

## Next owner checkpoint — deployed release and local verified demos

Approved on 10 September 2026: the next reviewable checkpoint is a working
server release with the current Workbench design and newly recorded demos for
both sources. Keep both published walkthroughs in light mode throughout, including
saved-SQL reuse and Advanced mode; dark appearance remains a separate validation
concern. The owner clarified the recording environment on 10 September:
**record both replacement videos locally with a verifier**. Use the available
Gemma 4 12B writer / Qwen 2.5 14B reviewer profile and retain evidence that both
roles actually ran. Label the recordings as local; server validation remains
separate and does not delay publication of verified local cuts.
Finish the current saved-work and Dashboard delivery before this
checkpoint; follow-on A/B/C and model comparison remain separately scheduled.

- Validate the current working UI locally as changes are made, including the
  on/off Advanced mode switch and direct mock-style alignment. Local development
  and testing do not wait for a merge or a release build.
- Verify visual fidelity against the approved public mock with matched light/dark
  and wide/narrow screenshots. Match its type hierarchy, spacing, cards, borders,
  controls and mark directly; inspect Saved work and review panels as well as
  Explore. Fix demonstrated drift before the release checkpoint.
- Complete saved-query reuse, compatible charts/tables, persistent Dashboard
  arrangement, publication and actual Superset import/rendering. Use both retained
  real sources and resolve concrete failures before calling the build ready.
- Merge the tested compatible revisions and release them to the existing demo
  server through the harness wrapper. Keep the final local acceptance build on
  the same merged revisions, preserve retained data, and verify the real journey
  in each environment.
- Record the local demos with the new styles and the writer/reviewer profile.
  Focus on asking, browsing data,
  reviewing/refining results, reusing saved SQL, creating charts and arranging
  and publishing a Dashboard. Limit FHIR Data Pipes to a brief context segment
  (about 10–15 seconds); retain the detailed ingestion proof in the evidence.
- Present the working server link, the two refreshed videos, local proof and
  their local recording environment and any unresolved server findings for
  asynchronous owner review. Update existing public
  video/poster references together. Record owner acceptance separately.

Shorter demos remove repeated explanation; they do not accelerate reading or
shorten the caption/result holds required in step 5 below.

The first exact-release server run on 11 September is preserved as failure
evidence. Its initial OpenELIS question required three model calls and became
ready after about 10 minutes; the database query itself took 165 milliseconds.
The recovered turn evidence records one follow-up Hub invocation lasting
1,800,003 milliseconds before a writer timeout. Router logs show expensive
prompt processing, low prefix reuse, and continuing activity, but do not establish
which later router tasks belong to that invocation. The earlier attribution of
those tasks to follow-up repairs is withdrawn. Measure queue wait separately from
active model time; do not repeat the full journey until the incomplete-response
and cancellation behavior is corrected or deliberately dispositioned.

### Remediate the observed generation failure

The 11 September owner feedback rejects the observed performance. Fix the
request lifecycle and avoidable model work before another full server journey;
the model options and session-navigation expansion in step 6 remain separately
tracked. Increasing timeouts alone is not remediation.

Code inspection at Catalyst `c93a3d6` and Hub `75d0ff0` identifies the actual
path: the Gateway runs `query_engine` through `LocalHub`, calls Hub's named-role
`/v1/hub/query-profiles/{profile_id}/roles/{role}/generate` endpoint, and awaits
each whole response. Neither the Workbench turn route nor that Hub role route
watches for client disconnect. The separate chat-completions streaming adapter
does not govern this path; changing `stream: false` in the request builder alone
cannot fix it. The rendered query payload also places the changing question
before the complete catalog, defeating reuse of that catalog as a stable prefix.

Deliver these repairs in order, retaining the existing state owners and tests:

1. **Bound and cancel the whole operation.** Use one elapsed-time deadline across
   queueing, generation, repairs, and optional review, with downstream timeouts
   bounded by its remaining time. Propagate explicit cancellation, request loss,
   and deadline expiry through Gateway, Hub role calls, and the model connection;
   do not start another repair afterward. Record a terminal turn state, release
   the session's busy state, and preserve the draft and prior result. Return a
   structured error when the client is still connected; handle empty or truncated
   responses without exposing a JSON parser exception as the user message.
2. **Preserve useful prompt work.** Put stable instructions, target, complete
   schema, and policy ahead of question, correlation IDs, and revision context.
   Keep equivalent schema serialization stable and remove only proven duplicate
   context. Preserve every readable relation/column and required session context.
   Measure the actual rendered prefix on initial, follow-up, and repair calls,
   including alternating sources; a same-question cache hit alone is insufficient.
3. **Correct the avoidable repair cycle.** Replay the initial question's preserved
   projection and patch failures and repair the
   prompt/output-contract mismatch. If a correction can be derived unambiguously
   from the SQL parser, change only that metadata and retain provenance; never
   guess types, rewrite selected SQL, or bypass ambiguous-patch checks. Count all
   retries against the shared deadline. The failed follow-up records one timed-out
   invocation and no returned validation findings, not a proven repair loop.
   Verify useful output, not just earlier
   failure, on the unchanged count and follow-up scenarios plus varied cases.
4. **Make a measured capacity decision.** Compare the writer-only E4B candidate
   from step 6 with the repaired 12B path on both actual sources. Retain the
   chosen model's identity and explicit reviewer setting. If CPU execution still
   misses the reviewed target, present measured GPU-backed deployment options
   and cost before changing infrastructure. Neither extra CPU concurrency nor a
   pre-warm request is assumed to make the current capacity adequate.

Proposed targets for owner review, not measured results or silently adopted
acceptance changes: visible acknowledgement or queue state within 1 second;
usable simple initial/follow-up queries within 30 seconds on a warm fast profile;
a 120-second total interactive deadline including queue and repair; and no active
downstream call or later repair within 5 seconds of cancellation. Report each
observed timing, cold and repeated requests, query correctness, and two-session
contention. A small case set does not establish production percentiles. If a
target is missed, keep the finding open rather than extending the test wait.

First prove the failure/timeout/cancellation boundaries with focused tests, then
repeat the short real dual-source questions on the intended server hardware.
Only after that passes, rerun the full saved-work-to-Superset journey. Live stage
feedback in step 6 improves visibility but does not substitute for these timing
and correctness checks.

### Current release integration

The owner-authorized release sequence is roadmap #142; combined Catalyst
#106–#109 and Hub #25–#27; router #143 with their exact merged revisions;
local/server deployment; then the distinct light-mode OpenMRS replacement
walkthrough and publication in #141. Record each stage in [tasks.md](tasks.md).
Keep #134 and #111 outside this release. Local recordings use the real reviewed
profile; server model-capacity decisions require the measured checks above.

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

Separate [OpenELIS reporting integration planning](../openelis-reporting-catalyst-integration.md)
coordinates two parallel efforts: OpenELIS's reporting MVP and source
preparation, and this Catalyst upgrade with source readiness. They meet at a
working OE connection and native CSV/generated Dataset comparison. The
integration plan links Catalyst work here rather than creating a second
implementation effort; it adds no prerequisite or acceptance requirement to
this delivery's current release checkpoint.

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

Record the two public replacement demos locally with both the writer and
reviewer enabled. Verify actual role execution in the saved generation evidence;
the selected profile alone is not proof that review ran. Identify the local
environment, models and application revisions in the recording evidence and
public context. Preserve server validation findings separately.

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

### 6. Improve responsiveness and session navigation

This is the first product checkpoint after the current deployment is stable and
accepted. It precedes follow-on A/B/C and does not change the one-source-per-session
rule or the current Dashboard acceptance contract.

Start with one measured baseline for a simple initial question and a follow-up
against both public data sources. Record time to the first honest status update,
time to the first model output when available, time to a usable query, prompt and
output tokens, prompt-prefix reuse, model-call and repair counts, cancellation,
and CPU/memory use. Separate cold and repeated requests. Do not infer model speed
from SQL execution time or from a spinner.

Then deliver four small, reviewable iterations:

1. **Fast model option.** Start with a writer-only Gemma E4B candidate served
   through the existing Hub profile and discovery contracts. The published
   OpenClinAI [E4B comparison](https://reports.openclinai.org/small-model-answer-paths-2026-07-15/)
   and [A4B efficiency sweep](https://reports.openclinai.org/method-levers-dev-2026-06-26/)
   justify this as a candidate size class, but they
   measure chart answers rather than Catalyst SQL; the fixed Catalyst query set
   remains the decision evidence. Do not use the existing E4B-plus-Qwen-14B
   reviewed profile as the fast path because its second large-model call defeats
   the purpose. Present a short outcome-based label such as **Fast draft** and
   keep the exact model and profile in Technical details. A missing selected
   profile fails visibly; there is no silent fallback. Compare the E4B and
   standard 12B profiles on the same small dual-source query set and publish
   their measured timing and observed query behavior before choosing a default.
2. **Useful warm path.** Distinguish model-load warm-up from prompt-prefix reuse.
   The current llama.cpp process already keeps its model resident and performs
   startup warm-up; the observed cost is rereading a roughly 10–12-thousand-token
   follow-up after its reusable prefix was lost. Keep stable instructions and
   schema first, enable supported prompt caching explicitly, and evaluate the
   smallest slot/checkpoint or safe priming change that preserves useful prefixes
   for the active source/profile. Warm-up never runs SQL, fetches result rows, or
   loops in the background. A cache miss remains correct, and evidence must show
   whether the change reduces prompt processing rather than only moving the wait.
3. **Live progress and streaming.** Carry actual Gateway query-engine events and,
   where supported, Hub named-role progress through to the UI. The Hub's separate
   chat-completions staged adapter is not Catalyst's current execution path;
   preserve Catalyst-owned orchestration and extend the existing role contract
   only as needed. A profile flag or request-builder `stream` flag alone is not
   an implementation. Verify useful live events on the actual query path.
   Show plain stages such as
   **Checking available data**, **Writing the query**, and **Reviewing the query**
   in a persistent status region. Stream user-facing model content only when it
   can be separated from the structured query contract; partial JSON or unvalidated
   SQL is never presented as ready. Disconnect, timeout, explicit cancel, retry,
   and final failure preserve the draft and stop downstream work. If the current
   structured output cannot provide useful partial text, retain honest stage
   progress and record that limitation rather than simulating token progress.
4. **URL-addressable sessions.** Add a session identifier to the query string.
   Opening the URL restores that exact session and its bound source; selecting a
   recent session updates the URL, and browser Back/Forward restores the expected
   session. Two tabs with different session URLs retain independent drafts,
   results, and generation status. Different sessions may run or queue according
   to measured model capacity; the UI states which is happening. A second turn in
   the same running session retains the existing explicit conflict. Switching or
   closing a view does not leave unowned model work.

Use the same approved Workbench visual system for the model selector, View
options, and progress treatment. Keep infrequent choices in one quiet disclosure;
use labeled radios for two-choice appearance settings rather than another
dropdown. Long work uses a persistent, accessible status region without fake
percentages or a warning-style box. Technical model names, attempts, tokens, and
traces remain available in Advanced mode.

Review the implementation against the primary guidance for
[llama.cpp server warm-up, prompt caching, slots, and streaming](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md),
[Carbon disclosures](https://carbondesignsystem.com/patterns/disclosures-pattern/),
[Carbon dropdowns](https://carbondesignsystem.com/components/dropdown/usage/),
and [accessible status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html).

Exit: the public deployment offers a tested fast option and standard option;
cold/warm and cancellation evidence explains their actual behavior; progress is
plain, live, and accessible; separate session URLs survive reload and work in two
tabs; and exact profiles, revisions, and limitations are recorded. Product,
Hub, and harness changes land in their owning repositories and are pinned only
after their focused checks pass.

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
