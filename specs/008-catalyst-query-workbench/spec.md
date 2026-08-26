# Feature Specification: Catalyst Query Workbench

**Feature Branch**: `codex/dashboard-builder-mvp`

**Created**: 2026-07-17

**Status**: Iterative-query notebook foundation accepted. Program P3's
Superset-backed Dashboard Builder completed M3 on 2026-08-06: its binding 4c
product surface, real notebook-to-Superset path, focused automated D1d checks,
durable visual evidence, and explicit user acceptance are recorded. M4 release
hardening and deployed acceptance are in progress. Actual 200% browser zoom is
deferred polish, not an MVP gate.

**Input**: Refine the Catalyst query experience with manageable dataset context,
targeted query remediation, complete validator feedback, editable SQL,
frictionless manual execution of imperfect drafts, execution-error feedback,
iterative human correction, and contextual follow-up generation from the exact
current editor state.

**Current architecture (2026-08-05)**: Med-Agent Hub owns one shared profile
schema for hosted clinical and caller-orchestrated Catalyst workflows. The
Hub-owned Catalyst profile contains role models, prompts, and knobs and exposes
live discovery plus named-role execution. Catalyst Gateway owns catalog/context,
writer/reviewer composition, deterministic SQL lint/repair/finalization,
execution, lineage, and query evidence. Historical G2.1–G2.8 evidence below is
retained as evidence of the path tested at that time, not as current ownership
guidance.

## Portfolio position after query-workbench MVP acceptance

Feature 008 delivered the accepted query/workbench foundation. It no longer
acts as one linear queue in which every remaining item blocks the next product
feature.

| Pathway | Status | Relationship to feature 008 |
| --- | --- | --- |
| **Superset-backed Dashboard Builder MVP** | **M3 accepted 2026-08-06; M4 release hardening in progress** | Depends only on the accepted Query vN/execution/table foundation. Catalyst supervises Dataset/Widget/Dashboard drafts and publishes a native bundle to a shared outbox; the pinned Superset CLI imports and renders it. |
| G2.10 multi-source/lossless data foundation | Evidence incomplete | Parallel reliability work; it can broaden dashboard sources later but does not block D1's one-source/one-catalog Dashboard rule |
| W2 targeted query assistance | Planned, not selected | Parallel optional repair workflow; requires its own G4/G5 approval |
| W3/CVR evaluation | Report parity merged in PR #43; session export/comparative expansion remains | Parallel evidence work; not a Dashboard product dependency |
| R4 narrative reporting | Not started | Parallel table-to-narrative pathway; not a dashboard prerequisite |
| R5 productionization | Future | Authentication, authorization, security and supported deployment remain outside the local Dashboard MVP |

Dashboard Builder MVP follows the authoritative reconciled design in
`targets/catalyst/docs/dashboard-builder-mvp-design.md`; the populated
`Catalyst Dashboard Builder 4c.dc.html` page is its binding visual reference.
One successful execution becomes a reusable dataset draft, the user reviews a
deterministic widget suggestion, and one or more saved widgets can be arranged
as a dashboard draft. Catalyst persists the supervised draft lineage and atomically publishes
a deterministic native Superset asset ZIP to its gitignored runtime outbox.
Stack bootstrap may invoke the pinned Superset CLI only for an eligible current
desired digest; an explicit helper owns retries. The CLI queries the analytics
database and renders the dashboard; only its digest-addressed receipt and
validated latest projection establish import state. Superset API automation, embedded viewing, cross-system
sync/undo, sharing, scheduling, automatic refresh, production credentials, and
production authorization are deferred.

## Clarifications

### Session 2026-07-17

- Q: Which validation classes remain non-overridable for manual execution in
  the isolated proof of concept? → A: None. Validator findings are
  advisory for manual execution; database credentials and permissions are the
  authority, with timeout and returned-row limits retained only as operational
  bounds.
- Q: Should both SQL and typed parameters be directly editable in the first
  iteration? → A: Yes. Provide a full expert editor for both, with validator
  notes alongside and optional guided fixes.
- Q: Should the first proof of concept preserve the current question, query
  versions, parameters, validator notes, and execution results across a browser
  refresh? → A: Yes. Persist and restore the active workbench session.
- Q: Must one-click validation-harness export block the first manual-workbench
  slice? → A: No. Persist export-complete lineage in the first slice, then add
  `run_manifest.json` and `events.jsonl` materialization after manual editing,
  advisory validation, execution feedback, and refresh restoration work end to
  end.

### Session 2026-07-18

- Q: How should an evaluator continue after generating, editing, validating, or
  running a query? → A: Keep one linear notebook-style session. A follow-up
  instruction derives one complete successor query from the exact current
  editor state; `New session` remains the path for unrelated work.
- Q: Which editor state becomes the follow-up base? → A: Reuse the current
  immutable version when unchanged, first preserve a dirty contract-valid
  buffer as a human version, and retain a dirty unresolved buffer as explicit
  turn input evidence without promoting it to a query version.
- Q: How much prior context should models receive? → A: The exact base editor
  snapshot, current instruction, relevant retained instructions, and matching
  validation or execution information. Record what was supplied and why
  anything was omitted. Do not send result rows, credentials, hidden reasoning,
  or an undifferentiated transcript. Older fixed-window request versions remain
  readable but do not set the Phase 1 limit.
- Q: How many active query inputs should an evaluator see? → A: One canonical
  SQL editor plus one reusable natural-language composer. The composer handles
  the initial Ask before a session and every Refine instruction afterward; the
  original question remains in history instead of a disabled duplicate form.
- Q: What should “Know what to ask” describe? → A: The runtime catalog—exact
  relation names, columns, types, nullability, meanings, and truthful runtime
  capabilities—from the same source used for model grounding and editor
  completion. It includes every relation the configured read-only role can
  read. Reviewed metadata may guide use but cannot hide a readable relation.
- Q: Does “based on execution results” include returned row values? → A: The
  current approved boundary includes exact-digest status, schema, row count,
  timing, and diagnostics. Value-level context is pending the G2.9 user decision
  on an explicit bounded result attachment; it must not happen silently.

### Session 2026-07-22 — multi-source and lossless ingestion

- Q: Should Catalyst support more than one data source? → A: Yes. A
  data-source registry (`GET /v1/catalyst/data-sources`) lists every
  registered source (own analytics database, own catalog); a workbench
  session is source-agnostic — any turn may target a `dataSourceId`, and an
  untargeted turn inherits the session's most-recently-targeted source
  (falling back to the session's initial source). This lets a follow-up
  literally "adapt this query to the other data source" mid-session instead
  of requiring a new session per source. A source registered but not yet
  provisioned (its catalog file absent) lists `available: false` and cannot
  be targeted.
- Q: How is catalog staleness (`409 stale_catalog_version`) judged when a
  session can target multiple sources? → A: Per source, against the
  baseline that source was last seen at in this session. Switching to a
  source the session hasn't used yet has no baseline and never trips a
  false conflict.
- Q: How should ingestion for a new data source be authored — hand-written
  projections, or something else? → A: Never hand-write ingestion
  projections. The ingestion layer is the upstream fhir-data-pipes default
  ViewDefinitions used essentially verbatim (lossless: one row per resource
  per coding, via `forEachOrNull`), plus documented additive extensions and
  gap-fill views only for resources upstream ships none for. ALL curation —
  collapsing the per-coding cross product to one row per resource, picking a
  canonical display, pivoting known coding systems into typed columns —
  happens afterward in SQL (`sql/NNN_analytics_*.sql`), where a mistake costs
  a `CREATE OR REPLACE VIEW` instead of a full FHIR re-fetch. This
  supersedes the original G2.x hand-written single-select projection
  approach (see plan.md N59); no ingestion-layer information loss (e.g. a
  `.first()` over multiple codings) is acceptable when the resource can
  legitimately carry more than one.
- Q: How is the catalog kept in sync with the ingestion/curation layer
  across every data source, without hand-updating it per source? → A: The
  catalog is GENERATED, never hand-maintained. A harness script
  (`scripts/generate-catalyst-source-catalog.py`) introspects the curated
  SQL's `COMMENT ON VIEW` (grain) and `COMMENT ON COLUMN` (descriptions,
  authored alongside the views) plus one small hand-maintained
  `catalog-overlay.json` per source (identity, reviewed metadata, semantic
  canonical values — validated against live data at generation time, so a
  guessed display string that matches zero rows fails generation instead of
  silently producing empty results). Only the sections the gateway actually
  reads are emitted (approval, name, version, grain, typed columns/units,
  semantic dimensions) — allowed-filters, terminology notes, freshness, and
  example-query sections some earlier hand-written catalogs carried are
  inert and are not part of the generated shape.
- Q: What's the readiness-check scope with multiple sources registered? → A:
  `readiness()` intentionally reflects the default data source only; full
  per-source readiness across the registry is not yet implemented and is
  tracked as follow-up work, not a gap in the current check.

### Session 2026-08-08 — workbench UX v2

Recorded after implementation, not before it: these behaviours were built
from the design handoff and then reshaped by manual walkthroughs, and this
session states what was decided and why. Where an answer supersedes an
earlier one, it says so. Every item below is implemented and covered by a
test unless explicitly marked otherwise.

- Q: A session could only be created *from* a question, so the rail's "new
  session" form offered a name and a source with nothing to do with them.
  Can a session exist before there is a question? → A: Yes. `POST
  /workbench/sessions` accepts a request with no `question`, and `POST
  /workbench/sessions/{id}/question` asks the first one later —
  `409 session_already_started` on a second attempt. Both paths run the same
  seeding routine, so a session created *with* a question behaves exactly as
  it did. `claim_initial_turn` is untouched: `kind: initial` still means
  nothing observed, nothing revised, no editor snapshot.
- Q: What names a session? → A: Its first question, unless renamed. `name`
  is optional at creation and backfills from the first question's text;
  `PATCH /workbench/sessions/{id}/name` renames the thread and never touches
  `question`, which is evidence of what was asked rather than a label. A
  session with neither reads "New session".
- Q: Does a session still allow the mid-session source switching decided on
  2026-07-22? → A: **No — that answer is superseded.** Query versions chain
  through `parentVersionId` and each follow-up is written relative to the
  previous query, so a version whose parent was written against a different
  schema would describe a lineage that never existed. A turn or version
  naming a different `dataSourceId` is `409 data_source_immutable`; catalog
  staleness is judged against one baseline rather than per source. Querying
  another source means starting another session.
- Q: What is a turn, now that a person can also edit and run SQL by hand? →
  A: A cell in one thread. Model generations live in the turn timeline and
  hand edits live among the session's versions; the thread is the two
  merged. Query versions are numbered in the order they were appended — the
  one clock both kinds share — so that ordering is authoritative, and a
  cell's `[n]` is simply its position in the thread. A hand-edited version
  that has not been run is not yet a cell; it is the draft in the editor.
- Q: Where does a run's result appear? → A: In the cell whose query produced
  it, expanded by default, spanning the thread's width, minimisable per
  cell. Not in a standalone panel, and never in two places at once.
- Q: Saving a version and running one were separate actions. Should they
  stay separate? → A: No. Running already saved the editor as an immutable
  version and checked it on the way, so a separate save could only ever add
  a version with no result to show for it — and, pressed before Run, added
  two. **One Run action.** The advisory check reports beside it and never
  blocks.
- Q: What leads after a run? → A: The result, whichever way it went. A
  completed run — success *or* database failure — closes the editor, moves
  to the cell carrying the outcome, and offers editing again as a choice.
  Only a failure of the action itself, where no execution was recorded and
  there is nothing to read, leaves the editor open with the error above it.
  A failed run is a result, not an absence.
- Q: When is the SQL editor open? → A: Whenever there is something to do in
  it — a query not yet run, unsaved edits, or an explicit request to edit.
  Otherwise the thread's last cell offers "Edit query" and the composer
  offers the next question.
- Q: How much internal numbering reaches the surface? → A: As little as
  possible. Cells are numbered; query versions and execution runs are not
  cited in the thread, in the composer's heading, in the execution summary
  sent to the model, or in a result table's caption. Version and run
  ordinals remain in the Details panel and the dataset review panel, which
  are the provenance surfaces and where identity belongs.
- Q: What does the section nav call the query surface? → A: **Workbench** —
  the place, not the gesture ("Ask"). The label is the button's own text and
  accessible name, not an `aria-label` on a bare icon, and it collapses to
  icon-only only when the rail is dragged near its 200px minimum. The
  section states the same word in a visible heading above the session's
  name, matching Datasets, Widgets and Dashboards.
- Q: What happens when a result is saved as a Dataset? → A: The gateway
  records an immutable entity pinning `sessionId`, `turnId`,
  `queryVersionId`, `queryDigest`, `executionId`, `dataSourceId`,
  `catalogVersion`, a `resultSchemaDigest` and a `resultDigest` over the
  exact returned rows, the parameterized and compiled SQL, the typed
  parameters, and the row bounds. It refuses unless the execution succeeded
  **and** is the currently-visible query's run. The review panel then offers
  **Build a widget from this Dataset** in place: saving used to close onto
  the thread while the next step lived in a nav section the analyst had to
  already know about, ending the chain at the moment it should have
  continued.
- Q: Is the promotion chain past a Dataset complete? → A: The promotion
  *path* exists and is verified end to end (this answer records that the
  chain works, not that Dashboard M4 acceptance is complete — the D1e/M4
  gate remains open). Dataset → Widget (presentation kinds filtered against the
  saved column types, with the incompatible ones explained) → Dashboard
  (one or more Widgets, single source) → **Publish**, which writes a
  deterministic zip and a `current.json` pointer and reports
  `bundle_ready`. The Superset **import itself is out of band** — a local
  helper consumes that bundle — after which the publication reports
  `imported` with a receipt id, receipt digest and dashboard URL, and the
  Dashboard row offers "Open Superset". A publication claiming `imported`
  without all three pieces of receipt evidence is reported as failed rather
  than trusted.

## User Scenarios & Testing

### User Story 1 - Understand and refine a generated query (Priority: P1)

As a technical evaluator, I can see the generated query, its bound values, and
specific validator findings together, edit the draft, validate the revision, and
understand exactly what remains wrong without restarting from the original
natural-language question.

**Why this priority**: Manual comparison across local models is the primary use
case. A rejected response that cannot be edited or iterated does not support the
experiment loop.

**Independent Test**: Submit a question that produces an invalid draft, correct
one reported defect, validate again, and confirm a new version retains the
question, prior draft, findings, and edit provenance.

**Acceptance Scenarios**:

1. **Given** a generated query with multiple findings, **When** validation
   completes, **Then** the full draft, typed values, findings, locations,
   evidence, and suggested updates are visible together.
2. **Given** an invalid draft, **When** the user directly edits its SQL or typed
   parameters and requests validation, **Then** a new immutable version is
   created and every validator runs again against that version.
3. **Given** two or more versions, **When** the user reviews the session,
   **Then** they can distinguish model-authored, system-remediated, and
   human-authored changes.
4. **Given** an active session with edits or execution feedback, **When** the
   browser is refreshed, **Then** the same current version and complete session
   history are restored.
5. **Given** a persisted session in the export slice, **When** the user exports it, **Then** the
   resulting validation-harness artifacts validate against their versioned
   metadata contracts and preserve every query version, finding, repair, manual
   edit, and execution outcome.
6. **Given** a generated or human-edited draft, **When** it is opened for
   editing, **Then** PostgreSQL syntax is highlighted, logical lines are
   numbered, and wrapping is on by default with an explicit wrap toggle.
7. **Given** the runtime-readable catalog is available, **When** the user requests
   completion, **Then** PostgreSQL keywords/functions and catalog-backed schemas,
   views, and columns are suggested without a hard-coded UI vocabulary.
8. **Given** an unformatted draft, **When** the user chooses Format twice on
   the same content, **Then** both operations produce identical SQL without a
   model call or a semantic query change.
9. **Given** a persisted query version, **When** the evaluator chooses Validate
   or Run, **Then** a dirty contract-valid buffer creates exactly one immutable
   human child containing the exact submitted SQL and typed parameters, while
   an unchanged buffer reuses the existing version and presentation-only changes
   create no version.
10. **Given** query generation returns a partially parseable draft whose
    parameter object is missing required `name`, **When** contract validation
    fails, **Then** the workbench retains the raw output, best parsed draft,
    per-attempt contract findings, and complete generation provenance for manual
    diagnosis and correction.
11. **Given** a parseable generation draft with localized contract or lint
    findings, **When** the Hub requests a correction retry, **Then** the model
    returns only typed patch operations for those failing paths, the Hub freezes
    every unaffected field, applies each operation deterministically, and reruns
    the complete contract and lint suite. A full replacement, stale path,
    ambiguous text replacement, or out-of-scope operation is rejected while the
    best editable draft and latest raw response remain visible.

---

### User Story 2 - Receive targeted automated remediation (Priority: P1)

As an evaluator, I can ask the configured model to repair only the invalid part
of a draft while approved parts remain unchanged, so correction attempts are
smaller, more reliable, and easier to compare.

**Why this priority**: The current full-regeneration loop repeatedly changes or
repeats an entire query when only a literal, predicate, projection, or binding
needs correction.

**Independent Test**: Start with a draft whose only defect is one unbound
threshold. Run automatic remediation and prove the resulting version changes
only the permitted query unit and associated typed value while immutable units
retain their digests.

**Acceptance Scenarios**:

1. **Given** validator findings localized to one repairable unit, **When**
   remediation begins, **Then** the system identifies the editable unit and
   freezes every unaffected unit.
2. **Given** a proposed repair, **When** it modifies a frozen unit or no longer
   applies to the source version, **Then** the repair is rejected without
   altering the draft.
3. **Given** a valid repair, **When** it is applied, **Then** the complete query
   is reconstructed and all deterministic checks run from the beginning.
4. **Given** a simple value, identifier, or operator substitution with an
   unambiguous deterministic correction, **When** remediation runs, **Then** the
   system can apply it without asking a model to rewrite unrelated query text.

---

### User Story 3 - Deliberately execute and diagnose a draft (Priority: P1)

As a technical evaluator, I can deliberately execute an editable draft in the
isolated demo environment even when quality validation has not passed, inspect
returned rows or execution errors, and use that feedback for another manual or
model-assisted revision.

**Why this priority**: Execution behavior is an important experimental signal;
lint-only rejection hides whether a syntactically imperfect or semantically
questionable draft would fail, return no rows, or return the wrong shape.

**Independent Test**: Execute a user-edited draft with validator findings,
capture either its typed results or database error, revise the draft, and
execute the next version while preserving the full version lineage.

**Acceptance Scenarios**:

1. **Given** any displayed draft, including one with error findings, **When** the
   user selects Run, **Then** the exact displayed query and values are submitted
   to the isolated analytics database and the validator state is recorded but
   does not disable execution.
2. **Given** a draft the database role does not permit, **When** the user runs
   it, **Then** the database rejects it and the resulting database feedback is
   attached to that draft version.
3. **Given** a database error, **When** execution finishes, **Then** the user
   sees its error code and useful message linked to the exact draft version and
   can use it as feedback for the next revision.
4. **Given** a successful execution of a draft with warnings, **When** results
   appear, **Then** warnings remain visible and the result is not relabeled as
   validated merely because execution succeeded.

---

### User Story 4 - Keep dataset context available without dominating the task (Priority: P2)

As an evaluator, I can orient myself from a compact live dataset summary, reveal
filters and record rows only when needed, and return focus to the query
workbench without losing browser state or being primed by example questions.

**Why this priority**: The current always-expanded browser pushes the question,
query, findings, and results below a large context card.

**Independent Test**: Load the page, confirm a compact summary is available,
expand and filter dataset details, collapse them, complete a query iteration,
and reopen the browser with its filters and page preserved.

**Acceptance Scenarios**:

1. **Given** a first visit on a desktop-sized screen, **When** the workspace
   loads, **Then** essential dataset identity and scale are visible while
   detailed tables and filters begin collapsed.
2. **Given** collapsed details, **When** the user expands them with mouse or
   keyboard, **Then** state, focus, and control relationships are conveyed
   accessibly.
3. **Given** an active query session, **When** context is collapsed and reopened,
   **Then** filters, pagination, and loaded rows are retained.
4. **Given** a narrow viewport, **When** context is expanded, **Then** it remains
   usable without obscuring the query editor or introducing nested horizontal
   scrolling.

---

### User Story 5 - Continue from the current query (Priority: P1)

As a technical evaluator, I can give a follow-up instruction based on the exact
query I am viewing or editing, receive a complete successor query, and retain a
compact chronological record of how the question, manual edits, model roles,
validation, and results evolved.

**Why this priority**: A standalone generation followed by manual editing is not
an iterative experiment. The evaluator needs an obvious continuation path that
uses the work already completed without turning the workbench into a chat
transcript or losing query-level evidence.

**Independent Test**: Generate an initial query, edit it, validate or run it,
submit a related follow-up with another available profile, and confirm the new
complete query is linked to the exact submitted editor snapshot while the
base/current anchor, results, failure evidence, and profile/model provenance remain
inspectable after refresh.

**Acceptance Scenarios**:

1. **Given** an active immutable query version whose editor is unchanged,
   **When** the evaluator submits a follow-up, **Then** that version is reused as
   the exact base and no duplicate human version is created.
2. **Given** a contract-valid editor buffer that differs from the observed
   current version or a session with no immutable version, **When** the evaluator
   submits a follow-up, **Then** the exact buffer is first preserved as exactly
   one human-authored version and that non-null version is the effective base.
3. **Given** an editor buffer whose SQL or parameter structure remains
   unresolved, **When** the evaluator submits a follow-up, **Then** the exact
   unresolved snapshot is retained and sent as correction context without being
   represented as an accepted query version.
4. **Given** a current query and related follow-up instruction, **When**
   generation succeeds, **Then** one complete writer query and any complete
   reviewer correction are linked in order to the effective base and exact
   editor snapshot, and neither query executes automatically.
5. **Given** a follow-up generation failure, **When** the failure is displayed,
   **Then** the failed turn, raw response evidence, model/profile provenance,
   and base snapshot remain inspectable while the base/current anchor stays
   current and editable: the effective base when non-null, otherwise the
   observed version when one exists, otherwise no current version.
6. **Given** an active session, **When** the evaluator reviews its history,
   **Then** compact ordered turns identify each instruction, base query version,
   selected profile and writer/reviewer models, produced versions, validation,
   execution, and failure state; earlier turns are collapsed and read-only.
7. **Given** results from Query vN, **When** the editor changes or a successor is
   generated, **Then** those results remain visible as `Results from Query vN`
   and are marked stale rather than relabeled or hidden.
8. **Given** an active session and a nonempty editor, **When** the evaluator
   traverses long dataset or result content, **Then** a persistent,
   non-obscuring action focuses the follow-up composer and identifies the query
   version on which it will operate.
9. **Given** an active session, **When** the evaluator clears the draft, **Then**
   refinement is disabled only while the editor is empty and `Restore Query vN`
   restores the current immutable version without creating another version.
10. **Given** multiple turns, profiles, manual edits, or a failed turn, **When**
    the browser refreshes, **Then** the same active session, turn timeline,
    current version, editable state, results labels, and profile selection are
    restored.
11. **Given** an active iterative session, **When** the evaluator selects `New
    session`, **Then** the next question starts without instructions, query
    content, validation, execution, or model context from the prior session.
12. **Given** two follow-up requests with the same observed current-version ID
    and digest, **When** they arrive concurrently, **Then** exactly one request
    atomically claims generation and enters Gateway query orchestration, making
    only the Hub role calls declared by the selected Hub query profile, while the
    other receives `409 turn_generation_in_progress`, makes no Hub role call,
    appends no event or version, and changes no current-version or current-turn
    pointer.
13. **Given** a follow-up or a newly created session, **When** its writer and
    reviewer request evidence is inspected, **Then** it contains only the
    permitted bounded context and contains no result rows, credentials, hidden
    reasoning, raw traces, unrelated-session history, or historical SQL copies
    other than the exact submitted editor snapshot.
14. **Given** a contract-valid writer candidate followed by reviewer transport,
    contract, or deterministic-validation failure, **When** the turn fails,
    **Then** the writer candidate remains an immutable but unselected output
    version, invalid reviewer candidates remain evidence only, and the
    base/current anchor remains selected and current when non-null. If the
    unresolved input had no observed version, the current pointer remains null;
    if valid editor input created a human effective base, that version remains
    current.
15. **Given** a session created before turn events existed, **When** its timeline
    is restored, **Then** one stable legacy initial turn is synthesized from
    persisted session, version, draft-seed, and generation-provenance references
    without appending events, fabricating a valid query, or making a model call;
    its output/selection references include only initial `model`/`model_repair`
    versions while the timeline separately restores the actual persisted current
    version, including a later human version.
16. **Given** an initial question for a newly created session, **When** its
    generation begins and terminates, **Then** recorded requested and exactly one
    completed or failed turn event are emitted; synthesis is reserved for
    sessions that predate recorded turn events.

---

### User Story 6 - Query more than one losslessly ingested source (Priority: P1)

As a technical evaluator, I can select any provisioned analytics source for an
initial or follow-up turn, adapt a query to another source inside the same
session, and trust that its generated catalog describes losslessly ingested data
rather than a hand-maintained or information-dropping projection.

**Why this priority**: A source switch changes the analytics database, catalog,
schema semantics, and evidence boundary. Treating it as a cosmetic selector can
silently apply stale catalog assumptions or erase valid repeated codings during
ingestion.

**Independent Test**: Register two independently provisioned sources plus one
unprovisioned source, generate and execute a query against the first, adapt it to
the second in a follow-up turn, refresh the session, and prove per-source catalog
baselines, query/version provenance, lossless projection multiplicity, generated
catalog agreement, and independent PostgreSQL results.

**Acceptance Scenarios**:

1. **Given** multiple registered sources, **When** the registry is requested,
   **Then** every source has a stable ID, label, and availability state, the
   default is explicit, and an unprovisioned source remains visible but cannot be
   targeted.
2. **Given** a session that last targeted source A, **When** a turn explicitly
   targets source B, **Then** that turn uses B's database and catalog and the next
   untargeted turn inherits B without rewriting earlier A-bound evidence.
3. **Given** a session has not previously used source B, **When** it first
   switches to B, **Then** B has no stale-catalog baseline and no false conflict;
   later B turns compare only against the last B catalog version observed by that
   session.
4. **Given** a FHIR resource with multiple codings or repeated elements, **When**
   ingestion runs, **Then** the raw projection preserves every applicable row
   through upstream `forEachOrNull` semantics and performs no `.first()`-style
   lossy selection.
5. **Given** a role-readable database and a reviewed source overlay, **When**
   the catalog generator runs, **Then** it emits every readable relation and
   column. Missing descriptions remain visible metadata gaps rather than hiding
   data. An overlay that names a nonexistent relation or a canonical semantic
   value that matches no live row fails validation.
6. **Given** a generated source catalog, **When** the schema guide, completion,
   deterministic validator, and model request are inspected, **Then** all four
   use the same source ID and catalog version and preserve that binding in
   session, turn, version, execution, and harness evidence.
7. **Given** more than one registered source, **When** default readiness is
   requested, **Then** it reports only the documented default-source boundary;
   the UI and documentation do not imply that every registered source was
   checked. Full registry readiness remains a separately tracked follow-up.

---

### User Story 7 - Build and publish a Superset dashboard (Priority: P1)

As a reporting user, I can promote exact governed results through reviewable
Dataset and Widget drafts, compose saved widgets into a Dashboard draft, and
publish the desired configuration to the local Superset renderer without losing
which query and execution produced each asset.

**Why this priority**: The accepted workbench proves query-to-table iteration.
The next useful supervised outcome is a durable dashboard built with an
existing dashboard platform rather than a Catalyst-only renderer or another
model-only output.

**Independent Test**: Execute governed queries, save Dataset and compatible
Widget versions, compose at least two widgets into one Dashboard, publish a
byte-deterministic bundle, import it into clean Superset, publish a changed
version, and verify the stable Dashboard points to new version-addressed child
assets. Refresh, source staleness, failed import, PostgreSQL value parity,
keyboard use and 200% zoom remain independently observable. Before promotion,
the accepted Ask/query-notebook regression path must still prove profile/model
selection, generation evidence, one editable SQL buffer, Format, Validate, Run,
manual versions, diagnostics, results, contextual follow-up, timeline, staleness,
refresh restoration, and New session without a duplicate editor or automatic
execution.

**Acceptance Scenarios**:

1. **Given** the accepted query workbench, **When** the Dashboard Builder shell
   is enabled, **Then** the same Ask session still supports the full generation,
   manual-edit/version, Format, Validate, explicit Run, diagnostic/result,
   contextual-follow-up, history, refresh, and New session workflow through the
   point where the user elects to save a Dataset. The runtime schema/catalog
   guide remains available, and no example prompts are introduced.
2. **Given** one successful, current execution, **When** the user promotes it,
   **Then** the Dataset draft binds the exact session, query version/digest,
   execution, source/catalog, typed schema/parameters, and result digest without
   copying rows. The executed-result preview may move from its current page
   section into the design's chronological Dataset tile and review panel, but its
   typed rows, query/version label, findings, database diagnostics, and provenance
   remain accessible before save.
3. **Given** saved Dataset v1, **When** the user asks a contextual follow-up,
   reviews and explicitly runs the complete Query v2 successor, and promotes it
   while current, **Then** Dataset v2 preserves its own exact lineage and Dataset
   v1 remains immutable and inspectable.
4. **Given** a Dataset draft, **When** Catalyst suggests a compatible Widget,
   **Then** the user can review or override table, big-number KPI, time-series
   line/area, grouped/stacked bar, or proportion-bar type without a model call
   or query execution; deterministic bindings are reviewable/read-only and
   incompatible choices explain why.
5. **Given** saved Widget versions, **When** the user places one or more on a
   Dashboard and saves, **Then** immutable Dataset/Widget/Dashboard versions
   preserve author, timestamps, complete configuration, and transitive source
   provenance; every Widget has the Dashboard's locked `dataSourceId` and
   `catalogVersion`, and refresh restores their libraries.
6. **Given** a saved Dashboard, **When** the user selects **Publish to
   Superset**, **Then** Catalyst atomically writes a native ZIP and current
   pointer to the host-visible outbox, offers the identical ZIP for download,
   and reports `Bundle ready` without claiming import success.
7. **Given** an eligible selected outbox bundle or an explicit retry, **When**
   stack bootstrap or the import helper runs, **Then** the exact CLI receipt reports `Imported` or
   `Import failed`. A changed publication keeps the logical Catalyst Dashboard
   ID, derived Superset Dashboard UUID, and deterministic
   `catalyst-<lowercase-dashboard-id>` slug, uses new
   Dataset/Widget version UUIDs, and treats an identical digest idempotently.
   Pointer, bundle, manifest, credential, and other preflight failures plus a
   transactionally rolled-back CLI failure preserve the previously verified
   Dashboard. A failure after the CLI returns success
   but post-import verification fails makes no rollback claim: it reports
   `Import failed`, disables Open Superset/current-success claims, retains the
   bounded diagnostic, and directs the operator to a full reset of the
   Superset-local metadata database/home volumes plus reimport and verification
   of that logical Dashboard's last-verified bundle. Recovery never deletes
   selected assets through the ORM or REST API. A missing or corrupt
   per-Dashboard last-verified projection stops before reset. Recovering verified
   A leaves failed desired B selected and `import_failed`; bootstrap/automatic
   retry of B remains suppressed until explicit retry or a new publication.
8. **Given** imported assets, **When** Superset renders them, **Then** it uses the
   native fixture's persisted analytics Database asset through a proven driver/
   network path and the database-enforced read-only role, and representative
   values reconcile to PostgreSQL. Changing the active source preserves saved drafts with explicit
   stale-source state and never silently rebinds them.
9. **Given** keyboard-only navigation or the required responsive reflow matrix, **When** the user
   completes Ask → Dataset → Widget → Dashboard → Publish and reviews import or
   error state, **Then** every control and value remains operable, readable, and
   unobscured.

**D1 acceptance identifiers** (used by T137–T182 and live evidence):

| ID | Observable acceptance |
| --- | --- |
| ASK-01 | Initial generation and every follow-up expose exactly one enabled natural-language composer, one editable control named `SQL query`, and one visible New session action. Opening review panels adds read-only SQL only. |
| ASK-02 | Profile plus writer/reviewer models, completion, Format, wrapping, parameters, Clear/Restore, advisory Validate, explicit Run despite findings, raw candidate evidence, diagnostics, typed results, provenance, versions, failed turns, staleness, refresh, and New session match the accepted baseline. |
| ASK-03 | Follow-up sends the exact visible SQL/parameter buffer and digest; unchanged buffers create no duplicate human version, dirty valid buffers promote once, and unresolved nonempty buffers can be corrected without false promotion. |
| ASK-04 | Before generation, Available data exposes every runtime relation/column plus the current filter, page, failure, and zero-match behavior from a compact keyboard-accessible surface. |
| DATASET-01 | Only an explicit successful Run creates one Dataset tile bound to its exact Query version/execution/digest; failure creates none and zero-row success retains an explicit typed empty state. |
| DATASET-02 | The tile panel is the sole full result presentation and retains bounded typed rows, schema, parameters, SQL, provenance, blank/empty/truncation warnings, and diagnostics. |
| DATASET-03 | Editing or generating marks the prior result/Dataset snapshot stale without hiding or rebinding it. Save records exactly the displayed execution/version/digest only while it still matches the session's current version and editor digest; a stale unsaved execution remains inspectable but cannot be promoted. |
| DATASET-04 | Save is idempotent, appends one immutable Dataset version, updates the library, survives refresh, and leaves the draft intact with an actionable error after persistence failure. |
| WIDGET-01 | Exact predicates select compatible types/bindings deterministically; table fallback and manually selected proportion behavior are explained; all five mappings clean-import into pinned Superset. |
| DASH-01 | A user creates a named Dashboard, adds at least two saved Widgets with the same `dataSourceId` and `catalogVersion` in deterministic append order, saves immutable versions, and receives an actionable rejection for either mismatch. A refreshed catalog requires an explicit new Dashboard. |
| PUB-01 | Publish and download bytes match; only an exact valid receipt establishes Imported; Open Superset lands on `/superset/dashboard/catalyst-<lowercase-dashboard-id>/`. Pointer/bundle/manifest/credential and other preflight failures plus transactionally rolled-back CLI failures preserve the previously verified Dashboard. Post-import verification failure reports Import failed, disables Open/current-success, retains its diagnostic, and exposes only full Superset-local metadata/home reset plus verified reimport of the logical Dashboard's atomic last-verified projection. Missing/corrupt projection data stops before reset. Recovery of verified A does not replace desired failed B in `current.json` or clear B's `import_failed`; automatic bootstrap/retry of B remains suppressed until explicit retry or a new publication. |
| PERF-01 | From an already eligible successful execution to Bundle ready is under 180 seconds, measured start/end, with zero model and database calls during configuration/publication. |
| EVIDENCE-01 | A schema-valid `acceptance.json` resolves component/image revisions, bundle/pointer/receipt/last-verified digests, stable Superset UUID/slug/URL, query/execution/entity IDs, reproducible PostgreSQL SQL plus inspected IDs/values, reviewer rationale, accessibility evidence, the fixed six-step `orderedWorkflow`, and versioned `run_manifest.json`/`events.jsonl` with structured `query_turn`, `query_version`, `query_execution`, Dataset/Widget/Dashboard/publication/import/reconciliation/acceptance payloads. |
| A11Y-01 | Empty/populated Ask, all panels, and all libraries pass keyboard traversal, Escape/focus return, status announcements, reduced motion, desktop, 390×844, 320 CSS px, and a 640-CSS-pixel equivalent reflow boundary without obscured controls or document overflow. Actual 200% browser zoom is deferred polish and is not an MVP gate. |

### Edge Cases

- A finding points to a query unit that no longer exists in the current version.
- Two findings overlap or require coordinated edits across query units.
- A model returns a full replacement when only a patch was requested.
- A human edit changes placeholders without updating typed values, or vice versa.
- A draft parses but references a missing field, incompatible type, or stale
  catalog version.
- A saved Widget has the same source identity but a different catalog version
  from the target Dashboard; D1 rejects the placement and directs the user to
  create a new Dashboard rather than mixing catalog meanings.
- Superset CLI exits successfully but UUID/slug/relationship verification fails;
  Catalyst must not infer that either the changed Dashboard or the prior one is
  usable. It records `Import failed`, disables Open Superset, and presents the
  full Superset-local reset and per-Dashboard last-verified reimport recovery.
  If that projection is missing or corrupt, recovery stops before reset. If
  verified A is recovered while desired B remains the global current target,
  B remains `import_failed` and automatic bootstrap/retry is suppressed until
  an explicit retry or new publication.
- A structured Hub response repeatedly or intermittently omits a required
  parameter `name`; unnamed parameter values are paired with SQL placeholders
  in their existing order. A count mismatch remains visible for manual correction.
- A question names a result unit that differs from the active catalog's unit;
  validation warns without rewriting the question or disabling manual Run.
- Execution succeeds but produces zero rows, an unexpected column shape,
  truncation, or a semantically suspicious result.
- Execution fails with a database error code and message that must remain useful
  for iteration without exposing connection credentials.
- A user switches profiles or changes the original question midway through a
  versioned query session.
- Dataset context fails to load while query generation and editing remain usable.
- Page refresh, browser back/forward navigation, or multiple tabs encounter an
  unfinished editing session.
- Another tab or request advances the current version after a follow-up captures
  its base version or digest.
- Two follow-up generations are requested for the same session before the first
  reaches a terminal state.
- The local editor is empty, contains valid SQL with unresolved parameters, or
  differs from its current version only in presentation state; an empty editor
  is disabled locally and is never submitted as an Editor Snapshot.
- The latest validation or database diagnostic belongs to a different query
  digest than the editor snapshot selected for refinement.
- A session contains more prior instructions than the bounded context window or
  a prior instruction conflicts with the current one.
- A follow-up writer produces a contract-valid output but the reviewer fails,
  rejects it, or returns an invalid correction; the valid writer output remains
  inspectable but must not silently become selected.
- A model returns the same SQL for a follow-up whose requested change is
  meaningful, or returns different content across nominally identical
  temperature-zero runs.
- A registered source exists but its catalog file is absent, its analytics
  database is unreachable, or its source ID conflicts with the default source.
- A session alternates A → B → A while either source changes catalog version;
  stale checks must use the last baseline for the targeted source only.
- An upstream FHIR ViewDefinition changes, contains a lossy selector, or produces
  a different repeated-coding cross product than the reviewed input.
- A curated view lacks a grain or column comment, or its overlay names a
  canonical semantic value that is absent from live data.
- A result has no valid bindings for a requested presentation; the unsupported
  choice is explained and the deterministic suggestion falls back to a table.
- A draft is unsaved when the source query changes, a saved draft is opened with
  stale source, or two tabs attempt to save from the same parent version.
- Saved source evidence is missing or digest-mismatched; restoration/export
  fails closed without substituting the current result.
- A bundle is malformed, targets another Superset version, has a digest mismatch,
  or the CLI exits nonzero; Superset remains usable and the exact diagnostic is
  retained without claiming import.
- The identical bundle is imported twice, or two import commands race; only one
  digest-addressed operation runs and duplicates are not created.
- A changed Dataset/Widget reuses an old UUID, a database connection changes,
  or old versioned children accumulate. Publication must follow the pinned
  6.1.0 overwrite constraints and direct the evaluator to explicit local reset
  when connection state or cleanup requires it.
- A user changes layout directly in Superset and republishes from Catalyst; the
  UI warns that the one-way MVP replaces Superset-only layout edits.

## Requirements

### Functional Requirements

- **FR-001**: The workspace MUST present connected OpenELIS-to-FHIR dataset
  identity and key live scale facts in a compact summary and make one detailed
  filter-and-record browser progressively revealable. It MUST NOT duplicate the
  browser with a static distribution table or present example questions that
  could prime evaluator behavior.
- **FR-002**: Expanded or collapsed dataset context MUST preserve its filters,
  pagination, and loaded content throughout a query session.
- **FR-003**: Dataset disclosure controls MUST expose their names, expanded
  states, controlled regions, keyboard behavior, and focus order to assistive
  technology.
- **FR-004**: The workspace MUST display the complete current query draft,
  typed values, validation status, and validator findings in one review surface.
- **FR-005**: Each finding MUST include a stable code, severity, stage, human
  message, query location when available, minimal evidence, and a suggested
  update when one can be determined.
- **FR-006**: Users MUST be able to directly edit the current SQL and its typed
  parameters and request full revalidation without resubmitting the original
  question.
- **FR-007**: Every contract-valid generated, automatically remediated, or
  human-edited draft MUST be an immutable version linked to its parent, author
  type, profile, source findings, validation outcome, and execution outcome.
  Contract-invalid candidates remain diagnostic evidence rather than versions.
- **FR-008**: Automatic remediation MUST identify the smallest meaningful
  repair unit that contains each correctable finding and freeze unaffected units.
- **FR-009**: A remediation proposal MUST identify its source version and
  permitted edit units; stale proposals or proposals that alter frozen units
  MUST be rejected.
- **FR-010**: Every applied remediation MUST reconstruct a complete query and
  rerun all deterministic validation from the beginning; findings remain
  advisory to manual execution in this proof of concept.
- **FR-011**: The system MUST prefer deterministic transformations for
  unambiguous corrections and reserve model calls for repairs that require
  contextual generation.
- **FR-012**: Users MUST receive a before/after representation of every proposed
  automatic repair and be able to accept or decline it.
- **FR-013**: Users MUST be able to run the exact displayed draft regardless of
  its validator status; validator findings MUST NOT disable the Run action.
- **FR-014**: Database authentication, permissions, and transaction behavior
  MUST be authoritative for whether a submitted query can execute. The
  application MUST return database rejection feedback rather than preemptively
  blocking manual execution based on validator findings.
- **FR-015**: Execution MUST use the exact displayed version and existing
  isolated database credentials. Statement timeout and returned-row limits MAY
  remain as operational bounds, but MUST NOT rewrite the submitted query.
- **FR-016**: The workspace MUST display successful rows, empty results,
  truncation, and database error code/message details as distinct outcomes
  linked to the executed version.
- **FR-017**: A successful execution MUST NOT automatically change an unvalidated
  or warning-bearing draft into a validated draft.
- **FR-018**: Execution outcomes and validator findings MUST be reusable as
  inputs to a subsequent manual or model-assisted revision.
- **FR-019**: The first iteration MUST expose a full expert SQL-and-typed-
  parameter editor. Guided clause/value fixes MAY be offered alongside it, but
  MUST NOT replace or restrict direct editing.
- **FR-020**: The system MUST retain a visible version timeline for the active
  session and permit inspection of earlier drafts without silently making them
  current.
- **FR-021**: The system MUST persist the active workbench session and restore
  its question, selected profile, query versions, typed parameters, validator
  findings, execution outcomes, dataset-browser state, and current-version
  pointer after a browser refresh.
- **FR-022**: The system MUST preserve exact model/profile/prompt/catalog/dataset,
  validator, editor/formatter revision, query-version, manual-run, and execution
  provenance.
- **FR-023**: The system MUST cover diverse validation cases, including malformed
  output, syntax errors, binding errors, semantic errors, unsafe operations,
  empty results, execution failures, and successful warning-bearing execution.
- **FR-024**: The harness-integration slice MUST provide one-click export of a persisted
  workbench session as versioned validation-harness `run_manifest.json` and
  `events.jsonl` artifacts covering every query version, validator finding,
  repair proposal, manual edit, manual Run action, and execution outcome.
- **FR-025**: The SQL editing surface MUST provide PostgreSQL syntax
  highlighting and logical line numbers while retaining a labelled,
  keyboard-operable editing control.
- **FR-026**: SQL line wrapping MUST be user-toggleable, MUST default to on for
  a new workbench session, and MUST retain the active session's preference
  without changing query content or version digests.
- **FR-027**: Completion MUST include PostgreSQL keywords/functions plus schema,
  view, and column identifiers derived from the active runtime catalog. Completion ordering MUST
  be deterministic for the same catalog and prefix, and the UI MUST NOT maintain
  a separate schema-name mapping.
- **FR-028**: Format MUST be an explicit deterministic action: the same SQL and
  formatter revision MUST produce byte-identical output, MUST NOT call a model,
  and MUST preserve the parsed query's meaning or return a useful no-change
  failure.
- **FR-029**: Editor keystrokes, completion, wrap changes, and formatting MUST
  NOT overwrite an immutable query version. Validate and Run MUST persist the
  exact SQL and typed parameters as a new child version before operating on a
  dirty contract-valid buffer; when the buffer is unchanged, they MUST reuse
  the matching immutable version. Earlier versions remain inspectable and
  unchanged.
- **FR-030**: Editor behavior MUST remain usable when catalog completion is
  unavailable: editing, formatting, validation, and manual Run continue, and
  the missing completion source is reported without inventing identifiers.
- **FR-031**: A generation or structured-contract failure MUST NOT discard
  research evidence. The workbench MUST persist and display the raw model output,
  best parseable draft/parameters, attempt number, exact failing object path and
  message, and profile/model/prompt/schema provenance. Any deterministic repair
  of missing parameter names MUST pair the existing parameter array with ordered
  unique SQL placeholders and MUST NOT invoke a model solely to add names. The
  model-facing generation schema MAY omit names/source, but the final executable
  contract MUST remain fully named. A count mismatch leaves the draft explicitly
  unresolved for manual correction. When the only retained candidate is one parseable raw JSON object,
  the editor MUST hydrate its representable SQL and typed values as a separate
  unresolved manual buffer, leave missing names blank, preserve the raw evidence
  exactly, and MUST NOT create a model query version until a human submits a
  contract-valid draft.
- **FR-032**: A reviewed Hub query profile MUST obtain one complete writer
  candidate, run deterministic lint, and give the complete candidate plus
  specific findings to its declared reviewer role. For the comparative
  cross-family profile, the reviewer MUST be a different model family. When
  correction is required, the reviewer MUST return one complete corrected
  candidate rather than a text or JSON-pointer patch. The Gateway MUST validate
  the correction contract and rerun every deterministic check before
  finalization. Each model role is executed through one configured Hub role
  request. Hub MUST select the role model, prompt, and knobs from the named
  profile; Gateway MUST compose the roles and MUST NOT override those settings.
- **FR-033**: When the reviewer changes a structurally valid writer query, the
  workbench MUST persist the writer query as an immutable `model` version and the
  corrected query as its immutable `model_repair` child. Both SQL/parameter sets,
  role/model identities, lint findings, reviewer decision/checks, prompt/config
  digests, and shared trace ID MUST remain inspectable after refresh. This
  generation-internal collaboration does not enable the broader user-accepted
  remediation workflow in User Story 2.
- **FR-034**: An active workbench session MUST support a linear sequence of
  initial and follow-up turns. Each follow-up MUST derive from the current
  editor state; branching from an arbitrary historical version is out of scope.
- **FR-035**: The workspace MUST present turns in chronological order, keep
  earlier turns collapsed and read-only by default, and give only the latest
  turn the active SQL editor, validation controls, and result workspace.
- **FR-036**: The follow-up composer MUST identify the exact base query version
  and its author/model, allow selection of any currently available profile, show
  that profile's writer model and its reviewer model only when one is configured,
  and expose one explicit action that generates the next complete query.
- **FR-037**: When the editor matches the current immutable version, follow-up,
  Validate, and Run MUST reuse that version instead of creating a duplicate.
  When a submitted editor buffer differs and is contract-valid, or is
  contract-valid when no immutable version exists, the system MUST preserve it
  as exactly one new human-authored version before taking the requested action.
- **FR-038**: An unresolved editor buffer MUST be retained as an exact,
  digest-addressed turn input snapshot and MAY be supplied for model correction,
  but MUST NOT become an immutable Query Version until it satisfies the
  executable query contract.
- **FR-039**: A follow-up request MUST identify its observed CAS base—the
  current immutable version ID/digest seen by the client—and the exact nonempty
  submitted editor snapshot/digest. The observed CAS base is nullable only when
  the session has no immutable version. If stored lineage has advanced, the
  request MUST fail as stale without generation or mutation; only one follow-up
  generation may be active per session.
- **FR-040**: A successful follow-up MUST return a complete successor query,
  preserve `base → writer → reviewer correction` lineage, and require a separate
  explicit Run action. Chat-only answers, textual patches, and automatic
  execution are out of scope.
- **FR-041**: A failed follow-up MUST create a terminal failed turn containing
  its observed CAS base, effective base, exact editor snapshot, raw response or
  error evidence, stage, output-version dispositions, and profile/model/prompt
  provenance. It MUST leave the base/current anchor current and editable: the
  effective base when non-null, otherwise the observed version when one exists,
  otherwise null. When a human version was promoted, the base/current anchor is
  that human version.
- **FR-042**: Each execution result MUST remain labelled with its exact query
  version and digest. Any later editor-content change or successor version MUST
  mark that result stale without deleting, hiding, or reassigning it.
- **FR-043**: Clearing the editor MUST provide a one-action restore of the
  current immutable query, disable follow-up only while the editor is empty, and
  create no version. Starting a new session MUST exclude all prior-session
  question, query, validation, execution, turn, and model context.
- **FR-044**: Follow-up model context MUST contain the current instruction,
  exact editor snapshot and parameters, observed/effective base identifiers and
  digests, relevant retained instructions, active catalog/policy/profile, and
  only validation findings or an execution diagnostic/shape summary that
  matches the exact editor digest. Existing fixed-window request versions remain
  readable but do not set the Phase 1 context limit.
- **FR-045**: Follow-up model context MUST NOT contain returned result rows,
  credentials, hidden reasoning, raw traces, unrelated-session history,
  historical SQL copies other than the exact submitted editor snapshot, or an
  undifferentiated full transcript. Context selection and truncation MUST be
  deterministic and its included and explicitly omitted entity references and
  digests MUST remain inspectable as generation evidence.
- **FR-046**: The writer MUST return one complete successor candidate. The
  different-family reviewer MUST receive that complete candidate, the same
  bounded revision context, and deterministic findings, and MUST either approve
  it or return one complete correction even when structural lint is clean.
- **FR-047**: Deterministic intent-sensitive validation MUST evaluate the active
  turn instruction supplied independently from the candidate query contract.
  Every writer or reviewer correction MUST be checked against the complete
  executable contract and full deterministic suite before it can become current.
- **FR-048**: Profile selection MAY change per turn. Each turn and produced
  version MUST preserve the selected profile snapshot, writer/reviewer role and
  model identities, model configuration, prompt/schema digests, correlation
  identifiers, and candidate/output digests.
- **FR-049**: The ordered turn history MUST persist requested, completed, and
  failed states and remain reconstructable from append-only session evidence.
  Human versions MUST inherit their active turn identifier; generated versions
  MUST additionally identify their exact base version and editor snapshot.
- **FR-050**: Refresh MUST restore the turn timeline, current-version pointer,
  saved editor state, profile selection, validations, executions, and result
  staleness. A persistent non-obscuring jump action MUST focus the initial
  question when no session exists and the latest follow-up composer otherwise.
- **FR-051**: The effective base MUST be derived after the observed CAS check:
  it equals the observed version for an unchanged snapshot, equals the one newly
  created human version for any contract-valid changed snapshot or valid
  snapshot submitted without an immutable version, and is null only for an
  unresolved snapshot. The exact nonempty editor snapshot remains required and
  authoritative in every accepted follow-up. The base/current anchor is the
  effective base when non-null, otherwise the observed version when present,
  otherwise null.
- **FR-052**: Acceptance of a follow-up MUST atomically verify the observed CAS
  base, claim the session's single generation slot, preserve any promoted-human
  human effective base, and append the requested turn. Of concurrent requests
  against the same observed base, exactly one MAY call the Hub; every rejected
  request MUST return a conflict and make no event, version, or pointer change.
  An active-generation conflict MUST take precedence over stale-base evaluation
  so the concurrent loser receives `turn_generation_in_progress` even when the
  accepted request has already advanced to a promoted-human effective base.
- **FR-053**: Query selection MUST occur only after the full writer/reviewer
  pipeline succeeds. If the writer candidate is contract-valid but the reviewer
  or its correction fails, the writer MUST remain an immutable unselected output
  version and the base/current anchor MUST remain current when non-null. For
  unresolved input with no observed version, the current pointer MUST remain
  null. Contract-invalid writer or reviewer candidates MUST remain diagnostic
  evidence and MUST NOT become Query Versions.
- **FR-054**: Every turn MUST preserve normative request evidence identifying
  observed and effective bases, exact editor snapshot, context-selection policy
  and membership, instruction ancestry and truncation, selected profile and
  role/model configuration, prompt/schema/catalog/policy/dataset digests,
  correlation identifiers, Hub request/response/candidate digests, raw evidence
  references, candidate dispositions, event references, failure stage, and final
  selection decision. The public turn representation MUST expose this as typed
  detail or a typed resolvable reference and MUST expose no hidden reasoning,
  result rows, or credentials. The detail MUST contain every inference
  invocation, including failed calls, with role, stage, attempt, model, effective
  sampling/output configuration, start/end timestamps, duration, and request
  and response-or-failure digests.
  Recorded turns MUST populate all required evidence fields with an empty typed
  omissions list; unavailable legacy facts MUST be explicit nulls with typed
  omission reasons and MUST NOT be inferred. Timeline rows carry only compact
  profile and prompt references/digests; full role-specific prompt content is
  available only in evidence detail.
- **FR-055**: A session without recorded turn events MUST expose one
  deterministic, read-only synthesized initial turn with stable identity and
  explicit legacy-recovery references to the persisted session, ordered
  initial-generation `model`/`model_repair` versions, actual current pointer,
  draft seed, and raw generation provenance. Synthetic ID, owner, and timestamps
  MUST derive deterministically from those references. Turn output and selection
  MUST exclude later human versions even while the timeline restores one as its
  current version. Failed, draft-only, and raw-only cases MUST remain failed or
  unresolved. Its terminal timestamp MUST be the selected initial output time,
  otherwise the raw/generation-outcome time, otherwise session creation time.
  All unavailable evidence MUST be null with typed recovery omissions. Synthesis
  MUST append no event, call no model, and never infer executable content or
  provenance absent from persisted evidence.
- **FR-056**: Every newly created session MUST record its initial question as an
  initial requested turn followed by exactly one completed or failed terminal
  turn event. `synthesized_legacy` origin MUST be used only when restoring a
  session whose persisted evidence predates turn events. A recorded requested
  turn found without a terminal event during recovery MUST use failure stage
  `orphan_recovery` and code `generation_interrupted`.
- **FR-057**: The workspace MUST render exactly one reusable natural-language
  Ask/Refine composer and one canonical SQL editor. Once a session exists, the
  initial composer MUST NOT remain as a disabled duplicate; its question MUST
  remain available through the chronological turn history.
- **FR-058**: An active session MUST expose a compact bottom workbench dock that
  remains reachable while browsing editor, validation, and results content. The
  dock MUST identify the current query/editor state, validation state, matching
  execution or stale/unexecuted state, and the available Edit, Validate, Run,
  and Refine actions. It MUST expand the existing editor or composer rather than
  create a duplicate floating input.
- **FR-059**: Format, Validate, and Run MUST remain adjacent to the canonical SQL
  editor. Results MUST use a bounded labelled scroll area, remain linked to the
  exact executed version, and preserve the stale state. Chronological history
  MUST summarize initial/follow-up instructions, generated/manual versions,
  execution row counts, and failures while keeping technical IDs and raw model
  evidence behind an explicit details action.
- **FR-060**: The queryable-data guide, editor completion, deterministic
  validation, and model grounding MUST derive from the same runtime catalog and
  include every relation the configured read-only database role can read.
  Reviewed metadata may enrich that catalog but MUST NOT filter it.
- **FR-061**: The Refine composer MUST visibly state whether its exact base has a
  matching execution summary, stale displayed results, or no execution. Until a
  bounded result-row attachment is explicitly approved and versioned, it MUST
  describe attached context as an execution summary and MUST NOT imply that row
  values are supplied to either model.
- **FR-062**: Med-Agent Hub MUST own the shared workflow-typed profile catalog,
  including Catalyst query-profile IDs, model-role mapping, role prompts, and
  sampling/output knobs. Catalyst Gateway MUST own deterministic writer/reviewer
  orchestration, correction policy, SQL validation, execution, lineage, and
  query evidence without duplicating Hub model configuration. Runtime
  availability MUST require Hub's exact versioned backend inventory and every
  unique required writer/reviewer alias. Unknown profiles, missing aliases, an
  unreachable router catalog, and missing/malformed inventory MUST fail closed
  before events, previews, or model calls without silent substitution.
- **FR-063**: Med-Agent Hub MUST expose Catalyst query-profile discovery and a
  configured structured single-role execution boundary that accepts a profile
  ID, role, non-system messages, and response format; selects the configured
  model/prompt/knobs; and returns assistant content without Catalyst SQL lint,
  review composition, database access, execution, or lineage. Caller attempts
  to override model, prompt, or knobs MUST be rejected.
- **FR-064**: `GET /v1/catalyst/data-sources` MUST list the default source and
  every registered source with stable identity, label, and availability. A
  registered source whose required catalog is absent MUST remain discoverable as
  unavailable and MUST fail closed when targeted.
- **FR-065**: A workbench session MUST remain source-agnostic. Every initial or
  follow-up turn MAY explicitly target one `dataSourceId`; an untargeted turn
  MUST inherit the most recently targeted source in that session, falling back
  to the session's initial source. Source identity MUST persist on all produced
  versions, validations, executions, and generation evidence.
- **FR-066**: Catalog staleness MUST be evaluated independently per source using
  the last catalog version that source contributed to the session. First use of
  a source MUST establish its baseline without a false stale conflict, and a
  stale result for one source MUST NOT be inferred from another source's
  baseline.
- **FR-067**: Base FHIR ingestion MUST use reviewed upstream FHIR Data Pipes
  default ViewDefinitions essentially verbatim and preserve repeated resources,
  codings, and nested elements through `forEachOrNull`-equivalent semantics.
  Additive extensions MUST be documented; gap-fill projections are allowed only
  for resources with no upstream default. Ingestion MUST NOT collapse legitimate
  multiplicity or select an arbitrary first coding.
- **FR-068**: Source-specific curation MUST occur after lossless ingestion in
  deterministic, repeatable SQL. Curated views MUST declare their grain and each
  exposed column's meaning through database comments, with tests that relate
  source rows, raw projection multiplicity, and curated output.
- **FR-069**: Each source catalog MUST be generated from the complete
  role-readable information schema plus optional reviewed descriptions and
  semantic metadata. Missing descriptions MUST remain visible gaps and MUST NOT
  remove readable relations or columns. Generation MUST reject overlay claims
  about nonexistent relations and guessed or zero-match semantic values.
  Hand-edited generated catalogs are prohibited.
- **FR-070**: Current readiness MUST explicitly describe its default-source-only
  scope. Full per-source readiness and live two-source acceptance MUST remain
  open until dedicated tasks and evidence prove every registered source; the
  presence of implementation plumbing or unit tests alone MUST NOT close that
  checkpoint.
- **FR-071**: A dataset draft MUST be promoted only from a successful query
  execution that still matches the session's current stored version and exact
  editor digest, and MUST bind the exact session, query version/digest, execution,
  data source/catalog version, typed result schema, result digest, parameterized
  SQL, and typed parameters. `resultDigest` MUST be the SHA-256 of the canonical
  RFC 8785 object `{contractVersion, columns, rows, returnedRows, maxRows,
  truncated, truncationReason, warningCodes}`. Columns and typed cells MUST
  reuse the complete accepted workbench table wire forms, preserving database
  column and row order without lossy type coercion. The row-free Dataset
  `executionBounds` and manifest `resultBounds` projections MUST be byte-
  identical. Stable warning codes MUST be de-duplicated in persisted execution
  order; D1 maps the known all-blank-column warning to `all_blank_columns` and
  any retained legacy prose without a recognized mapping to
  `legacy_unclassified_warning`. Localized prose remains display evidence and is
  excluded from the digest. Implementations MUST enforce
  `rows.length = returnedRows <= maxRows`, equal row/column widths,
  `truncated => returnedRows = maxRows` with a non-null reason, and
  `!truncated => truncationReason = null`. This bounded payload MUST NOT claim an
  unobserved full result set; a truncated UI MUST say how many rows are shown and
  that the total is unknown.
- **FR-072**: The builder MUST derive one deterministic, shape-compatible
  initial widget suggestion and allow the user to review or override it among
  table, big-number KPI, time-series line/area, grouped/stacked bar, and
  proportion-bar presentations. It MUST show derived bindings read-only,
  explain why incompatible choices are unavailable, and fall back to table when
  no chart mapping is valid. Suggestion and binding MUST use typed schema,
  returned-row count, and first-column ordinal precedence only: an exact
  one-row/one-numeric result suggests KPI; a temporal-plus-numeric result
  suggests time-series; a categorical-plus-numeric result suggests grouped bar;
  otherwise table. Proportion bar is compatible only with a two-categorical-
  plus-numeric result, is never
  suggested, and requires an explicit supervised override. The saved Dataset SQL
  owns any report aggregation. A non-table Widget MUST use only its read-only
  derived bindings over that saved table; Catalyst MUST NOT infer or silently
  substitute a reporting aggregation. Arbitrary column remapping,
  semantic-whole inference, and a Catalyst-owned chart renderer are out of
  scope; only a schematic type preview is local.
- **FR-073**: Catalyst MUST persist Dataset, Widget, and Dashboard drafts in
  corresponding libraries with immutable version lineage, exact source
  provenance, refresh restoration, and stale-source signaling. Configuration,
  save, restoration, and export MUST NOT invoke a model or automatically rerun
  the source query.
- **FR-074**: A dashboard draft MUST support placement of one or more saved
  widgets. Each explicit save MUST append an immutable version with parent,
  author, timestamp, complete presentation/layout configuration, and the exact
  dataset/widget source versions. D1 MUST let the user create a named Dashboard;
  widgets append in saved order to deterministic full-width grid rows. The first
  Widget fixes both the Dashboard `dataSourceId` and `catalogVersion`; adding a
  Widget with either a different source or catalog version MUST fail without
  saving a new version. After a source catalog refresh, D1 requires an explicit
  new Dashboard rather than mixing versions under the prior Dashboard identity.
- **FR-075**: `Publish to Superset` MUST generate a deterministic, versioned
  native Superset asset ZIP containing database, virtual-dataset, chart, and
  dashboard YAML plus a Catalyst provenance manifest beneath one enclosing
  bundle-root directory required by the pinned importer, save it atomically to a
  host-visible outbox bind-mounted read-only into Superset, and offer the same
  file for download. Catalyst MUST own `runtime/superset/` beneath its target
  root and MUST gitignore `/runtime/superset/` so publication cannot dirty the
  target worktree. One global `current.json` pointer MUST identify the exact
  digest and most recently published desired Dashboard; it is not an imported-
  success or last-verified pointer. Prior Dashboard bundles remain content-
  addressed and downloadable. Stack startup MAY import the selected current
  bundle only when its status permits automatic bootstrap; a post-import-
  verification failure suppresses automatic retry of that still-current target.
  One explicit local command MUST import or update it in an already running
  pinned Superset instance. Runtime import/state logic MUST be standalone,
  Python-3.10-compatible scripts under `targets/catalyst/scripts/`, import no
  Catalyst package, and use only the Python standard library plus dependencies
  already built into the pinned Superset image. No Superset API is required.
- **FR-076**: Named SQL parameters in an exported virtual dataset MUST be
  compiled from the exact successful execution's typed values into safely
  escaped PostgreSQL literals by a deterministic typed transformer. Raw string
  replacement is prohibited; the original parameterized SQL and ordered typed
  values remain in the Catalyst manifest together with the exact source/version
  provenance. The local-demo export MUST label that values may contain demo
  clinical identifiers; no credentials or returned result rows are included.
- **FR-077**: The Superset Dashboard asset MUST use a stable UUID derived from
  the immutable logical Catalyst Dashboard ID; Dataset and Widget/chart assets MUST use UUIDs
  derived from their immutable version identities. YAML/member ordering, ZIP
  timestamps, and permissions MUST be deterministic so identical inputs produce
  byte-identical ZIPs. The bundle MUST contain configuration and provenance, not
  duplicated clinical result rows. The in-bundle `bundleId` MUST be derived
  deterministically from immutable configuration inputs; dynamic publication,
  generation, and import-attempt IDs/times remain outside the ZIP so they cannot
  break byte determinism. The dashboard slug MUST be
  `catalyst-<lowercase-dashboard-id>` from the logical Catalyst Dashboard ID,
  distinct from the derived Superset Dashboard UUID, and its stable local route MUST be
  `/superset/dashboard/<slug>/`; import verification and acceptance evidence
  MUST match both UUID and slug. A layout-only change MUST reuse unchanged child
  UUIDs.
- **FR-078**: Superset MUST connect to the analytics database with a read-only
  role. A bundle MAY carry explicitly labelled local-demo credentials; any
  non-demo export MUST require the receiving Superset environment to supply its
  secret rather than embedding credentials. Runtime configuration MUST prove
  driver/network connectivity and DB-enforced write denial; the canonical
  clean-import fixture, not `superset_config.py` or a `set-database-uri` setup
  command, MUST provide the persisted deterministic analytics Database asset.
- **FR-079**: Catalyst MUST distinguish `Draft`, `Bundle ready`, `Imported`, and
  `Import failed`. Generating a file alone MUST NOT claim
  `Imported`; only the stack importer or explicit import command may record the
  Superset CLI outcome against the exact bundle digest. Missing, malformed,
  foreign-digest, or wrong-version receipts MUST NOT change the state. Importing
  is an ephemeral process/log condition, not a persisted D1 artifact state. The
  Dashboard-level publication projection is the authority for `Draft` and may
  have no bundle identity; a bundle-level projection exists only for a real
  non-null bundle ID/digest and never reports `Draft`. Failures before Superset
  mutation—pointer/bundle/manifest validation, credential resolution, and other
  preflight checks—and a transactionally rolled-back CLI import MUST leave the last verified Dashboard
  usable. If the CLI succeeds but post-import UUID/slug/relationship verification
  fails, the exact bundle state MUST be `Import failed`, Open Superset and any
  current-success claim MUST be disabled, and the bounded diagnostic plus last
  known verified bundle digest MUST remain available. The recovery action code is
  `full_reset_then_reimport_last_verified_bundle`. Every verified import MUST
  atomically update
  `runtime/superset/receipts/last-verified/<logicalDashboardId>.json` against
  `catalyst-superset-last-verified-v1.schema.json`; the digest-addressed latest
  attempt and this per-Dashboard recovery authority are distinct. Recovery MUST
  validate that projection and its referenced immutable bundle before mutation,
  stop without reset when either is missing/corrupt, then perform a full reset of
  only the Superset-local metadata database/home volumes and reimport/verify that
  bundle. Asset-selective deletion, direct ORM mutation, REST mutation, automatic
  rollback, and automatic retry are prohibited. When verified A is recovered
  while failed desired B remains in `current.json`, B MUST remain `import_failed`
  and automatic bootstrap/retry MUST stay suppressed; only an explicit retry or
  a new publication may change B.
  Superset API publication, embedded viewing, cross-system undo/reconciliation,
  sharing, scheduling, automatic refresh, and production authorization remain
  out of scope and MUST NOT block this milestone.
- **FR-080**: Dashboard Builder MUST extend rather than replace the accepted
  Ask/query-notebook behavior. Through the explicit **Save Dataset** transition,
  Catalyst MUST retain profile/model selection and evidence, one canonical
  completion/formatting-enabled SQL editor, exact manual versions and unresolved
  snapshots, advisory Validate, explicit Run, visible findings/raw generation
  evidence/database diagnostics, typed results, contextual follow-up, compact
  history, result staleness, refresh restoration, and New session. The supplied
  prototype's Ask shell, fixed composer, chronological thread, Dataset tile, and
  review panel ARE the target experience, but its abbreviated prompt-only state
  and example prompts do not supersede the accepted behavior. The runtime
  schema/catalog guide and executed-result preview MAY move into that target
  structure, provided their current information and actions remain accessible.
  Before generation, one compact keyboard-accessible **Available data**
  disclosure MUST retain every runtime catalog relation/column plus existing
  source filtering, pagination, failure clearing, and truthful zero-match state.
  The latest turn MUST contain the active SQL work surface before any Dataset
  tile. After a successful Run, its one Dataset tile/panel MUST retain the full
  bounded typed table, blank/empty/truncation warnings, diagnostics, exact Query
  vN label, and provenance, replacing rather than duplicating the inline result
  table. Failed execution creates no Dataset tile. Older turns and the Dataset
  panel use read-only snapshots and MUST NOT create another editable SQL control.
  Exactly one visible New session action remains in the Ask header with its
  current clearing/focus semantics. The implementation MUST NOT introduce a
  second SQL editor or automatically execute a generated query.

### Key Entities

- **Workbench Session**: A persistent identity covering the original question,
  selected Hub query profile, initial and most-recently targeted data sources,
  per-source catalog baselines, current draft pointer, dataset-browser state, and
  ordered history of user and system actions.
- **Query Version**: An immutable query draft with SQL, typed values, expected
  columns, parent version, author type, content digest, applicable format action
  and formatter revision, and timestamps.
- **Validation Run**: The validator revision, ordered checks, findings, status,
  timing, and query version evaluated.
- **Finding**: A stable advisory validator observation with classification,
  severity, repairability, location, evidence, and suggested update.
- **Repair Scope**: The source query digest, frozen units, editable units, and
  constraints a remediation proposal must obey.
- **Repair Proposal**: A deterministic or model-authored patch, before/after
  representation, source findings, disposition, and resulting query version.
- **Execution Attempt**: The exact version executed, validator state at
  execution, database outcome, database error or typed result reference,
  duration, and truncation facts.
- **Dataset Browser State**: Disclosure state, active filters, pagination, and
  loaded context associated with the workbench session.
- **Iteration Turn**: One initial question or follow-up instruction with a
  stable order, exact base/editor snapshot, selected profile, lifecycle state,
  produced query versions, validation/execution references, and failure
  evidence.
- **Editor Snapshot**: The exact SQL and ordered typed-parameter buffer submitted
  for an action, its digest and relationship to the current immutable version,
  and its persisted reconciliation state: reused, promoted-human, or unresolved.
- **Observed CAS Base**: The immutable version ID/digest the client observed as
  current before submitting a follow-up; it is absent only when no immutable
  version exists and is used solely to reject stale or concurrent mutation.
- **Effective Base**: The immutable lineage and current-selection anchor after
  editor reconciliation: the observed version when unchanged, one new human
  version for any contract-valid changed or no-version input, or no version when
  the submitted input remains unresolved.
- **Base/Current Anchor**: The version that remains current if generation fails:
  the effective base when non-null, otherwise the observed CAS base when one
  exists, otherwise no current version.
- **Revision Context**: The bounded, digest-addressed set of question history,
  editor/base query, matching findings or diagnostic summary, catalog, policy,
  profile, and correlation evidence supplied to writer and reviewer roles.
- **Generation Evidence**: Public typed detail, or a typed resolvable reference,
  containing exact provenance, full role prompts, candidate dispositions, and
  one timing/digest record for every writer/reviewer invocation; legacy gaps are
  explicit typed omissions, never inferred values.
- **Result View State**: The execution/version relationship and derived current
  or stale presentation state retained while later edits and turns occur.
- **Data Source Registration**: A stable source ID and label plus its analytics
  database, generated catalog location, default/availability state, and
  credential-free provenance.
- **Source Catalog Baseline**: The last catalog version observed for one source
  in one session, used only for that source's stale-catalog comparison.
- **Lossless Projection**: A reviewed upstream-default or documented additive
  FHIR ViewDefinition that preserves legitimate repeated elements/codings before
  any semantic curation.
- **Curated Analytics View**: A deterministic SQL view over lossless projections
  with an explicit grain, described typed columns, tests, and live metadata used
  to generate the source catalog.
- **Catalog Overlay**: The small reviewed source-specific input containing
  identity, reviewed relation metadata, and semantic canonical values that cannot be derived
  from PostgreSQL metadata alone.
- **Dataset Draft**: A reusable governed virtual-dataset definition bound to one
  exact successful execution, including parameterized and compiled SQL, typed
  schema/parameters, immutable source lineage, and current/stale source state.
- **Widget Draft**: An immutable-versioned presentation over one Dataset Draft,
  containing a supported visualization type, reviewed column bindings, labels,
  sort configuration, compatibility evidence, and provenance.
- **Dashboard Draft**: An immutable-versioned supervised composition of one or
  more Widget Draft versions with title and layout configuration.
- **Superset Bundle**: A content-addressed native Superset asset ZIP and Catalyst
  provenance manifest targeting an exact Superset release, with deterministic
  in-bundle identity, stable asset UUIDs, and exact source draft versions. It
  contains no dynamic attempt time or result rows.
- **Publication/Import Attempt**: Append-only operating evidence outside the ZIP
  linking one publish/import attempt and time to the exact bundle digest,
  pointer, importer/runtime identity, outcome, and bounded credential-free
  diagnostic. An atomic latest projection drives the user-visible state without
  rewriting prior attempts.

### Evidence, Provenance & Data Boundaries

- **Clinical evidence records**: Records reachable through the selected data
  source's configured read-only role are in scope; row identifiers and
  aggregate assertions remain linked to the executing query version. Runtime
  synthetic/real classification MUST be carried from authoritative provenance
  when available and MUST NOT be inferred from data shape or demo deployment
  mode.
- **Decision rationale**: Each validation and repair-scope decision records the
  applicable rule and why it warned or proposed a repair; each execution records
  that manual Run bypassed validator gating and the database outcome was
  authoritative. Each turn records why its snapshot reused or created an
  effective base and why every produced candidate was selected, unselected, or
  retained only as invalid evidence.
- **Operating metadata**: Session lineage, query versions, validation runs,
  repair proposals, execution attempts, iteration turns, editor snapshots,
  recorded revision-context membership and omissions, result staleness,
  profile/prompt/catalog/dataset provenance, editor/formatter revision, and
  harness-compatible run events.
- **Accepted deterministic inputs**: Versioned validator rules, repair templates,
  SQL formatter and PostgreSQL keyword source, runtime-readable catalog, execution
  policy, Gateway query-profile registry/prompts, reviewed lossless
  ViewDefinitions, curated SQL/comments, catalog overlays/generator, and reviewed
  query-patch contract.
- **Advisory inputs**: Model-generated repair proposals, suggested updates, and
  human comments remain proposals until explicitly applied and revalidated.
  Follow-up instructions guide a successor candidate but do not themselves
  attest that its result set answers the intended question.
- **PCCP/change record needs**: Material changes to query prompts, profile roles,
  provider transport, orchestration ownership, ingestion projections, source
  overlays, curated analytics, catalog generation, validator classification,
  repair policy, manual-run policy, or execution policy require old/new
  behavior, evaluation protocol, rollback conditions, and residual-risk
  documentation.

## Success Criteria

### Measurable Outcomes

- **SC-001**: On initial load and while browsing long dataset or result content,
  the canonical question input and primary action are either visible or directly
  focusable through a persistent, non-obscuring jump action at desktop and narrow
  viewport sizes; detailed record rows are collapsed by default.
- **SC-002**: A user can reveal or hide detailed dataset context with one action,
  using mouse or keyboard, without losing filters or pagination.
- **SC-003**: For at least 90% of seeded single-finding repair scenarios, an
  automatic repair changes only the permitted query unit and passes integrity
  checks for every frozen unit.
- **SC-004**: Every applied repair and manual edit can be validated, and every
  automatic patch is checked for source-version and frozen-unit integrity before
  application; manual execution remains independently available.
- **SC-005**: A technical evaluator can move from a rejected model draft to a
  revised validation result in under two minutes, excluding model inference
  time.
- **SC-006**: Every execution attempt can be traced to the exact displayed query
  and values, validator status, manual Run action, profile, catalog, dataset,
  and resulting rows or database error.
- **SC-007**: The seeded acceptance suite distinguishes at least ten failure and
  success classes, and warning-bearing successful execution is never reported
  as fully validated.
- **SC-008**: Tests prove that validator findings never disable manual Run and
  that database permissions—not application validator classifications—produce
  the authoritative outcome for disallowed operations or inaccessible data.
- **SC-009**: All disclosure, editing, validation, repair, confirmation, and
  version-navigation tasks are keyboard operable with programmatically exposed
  names and states.
- **SC-010**: Manual sessions used in model comparison preserve enough structured
  evidence to reproduce each version, finding, repair, manual Run action, and
  execution outcome in the validation harness.
- **SC-011**: Automated and manual checks prove PostgreSQL highlighting, logical
  line numbers, default-on wrap and toggle retention, keyboard completion from
  keywords plus the runtime-readable catalog, and graceful no-catalog behavior at
  desktop, narrow viewport, and 200% zoom.
- **SC-012**: Repeating Format on the same input produces identical SQL, and
  tests prove editing or formatting never mutates a stored version while
  Validate and Run operate on one newly persisted exact child for dirty-valid
  content or reuse the matching version for unchanged content.
- **SC-013**: From initial-question submission until the successor query is
  visible, a technical evaluator can complete `initial query → manual edit →
  follow-up` in under three minutes after subtracting only the recorded initial
  and follow-up writer/reviewer inference durations recorded in the per-
  invocation evidence fields, without copying SQL between surfaces. No other
  stage is subtracted. The total wall-clock duration is also recorded; an
  explicit Run and its database duration are reported separately as a secondary
  measure.
- **SC-014**: In 100% of seeded follow-up cases, recorded generation evidence
  identifies the exact base/editor digests and selected profile/models; no model
  input contains result rows, credentials, hidden reasoning, raw traces,
  unrelated-session history, or historical SQL copies beyond the exact editor
  snapshot, including the first request after `New session`.
- **SC-015**: Automated acceptance checks cover reused, promoted-human,
  unresolved, locally empty, and stale editor states; failed generation; reviewer
  correction of lint-clean SQL; recorded context inclusion and omissions;
  profile switching; stale results; refresh; and New Session isolation.
- **SC-016**: In every seeded generation failure, the base/current anchor remains
  current and editable when non-null, and the failed turn retains enough raw
  evidence and provenance to identify the failing stage and reproduce the
  request context.
- **SC-017**: Refresh restoration reproduces the same ordered turn count,
  current query/editor digests, selected profile, validation/execution links,
  and result-currentness state in 100% of acceptance scenarios.
- **SC-018**: Every stale request and every losing concurrent request is rejected
  before its own model call with zero event, version, or pointer mutation
  attributable to that rejected request; the accepted concurrent winner may
  create its turn, effective base, output versions, and current pointer.
- **SC-019**: When nominally identical model runs produce different outputs,
  including with temperature zero and the DRY repetition penalty disabled,
  their candidate and output digests record those differences; no run is
  labelled reproducible solely from configured sampling values.
- **SC-020**: Keyboard-only evaluation can reach the applicable initial or
  follow-up input with one persistent jump action, identify its base version and
  profile models, submit it, and return to the produced query at desktop,
  narrow viewport, and 200% zoom.
- **SC-021**: Deterministic paired-concurrency automated coverage proves exactly
  one request per pair makes one Hub call and reaches a terminal turn; every
  losing request returns a conflict with zero event, version, or pointer
  mutations.
- **SC-022**: Automated recovery checks produce byte-identical synthesized
  legacy-turn projections for the same persisted evidence, including stable
  origin, ID, owner, timestamps, and recovery references; initial-turn outputs
  contain only initial model/model-repair versions, the timeline restores the
  actual current version, and recovery makes zero model calls or mutations.
  Unavailable legacy facts are explicit nulls with stable typed omission reasons,
  while newly recorded turn evidence is complete with an empty omissions list.
- **SC-023**: Failure-path tests prove that 100% of contract-valid writer outputs
  survive reviewer failure as unselected immutable evidence, 100% of invalid
  candidates remain non-version evidence, and the base/current anchor remains
  the current editable version or null for unresolved input with no observed
  version.
- **SC-024**: Active-session accessibility snapshots contain exactly one SQL
  editor and one editable Ask/Refine composer, with the initial question present
  in history and no disabled duplicate question form.
- **SC-025**: Live desktop, 390 × 844, 320 CSS px reflow, and 200%-text checks
  prove the compact dock remains keyboard reachable, never obscures focused
  controls, and introduces no document-level horizontal overflow.
- **SC-026**: The seeded `edit → stale results → Run → matching execution →
  Refine` flow exposes the same version/execution references in the dock,
  result label, request evidence, and restored session; dirty and unexecuted
  states never claim matching execution context.
- **SC-027**: The runtime schema guide, SQL completion vocabulary, deterministic
  validator, and model request reference the same catalog version, and automated
  plus live information-schema checks prove that every role-readable relation
  and column appears exactly once with the correct name and type.
- **SC-028**: A 100-row execution keeps the document workflow bounded through a
  labelled result scroll region while its exact query-version label, stale
  status, row count, and keyboard navigation remain visible.
- **SC-029**: Contract and integration tests prove every advertised Catalyst
  query profile is Hub-owned, produces a digest-bound prompt/model/config
  snapshot, and invokes Hub only through the configured role endpoint; Gateway
  contains no duplicate model, prompt, or knob registry, while Hub contains no
  Catalyst SQL lint, correction orchestration, execution, or lineage
  implementation. Tests also prove the exact versioned Hub backend inventory,
  every required model alias, unavailable-profile omission, and rejection of an
  unavailable initial, governed-preview, or follow-up selection before state
  mutation or a model call.
- **SC-030**: A two-source session can execute A → B → inherited B → A across
  refresh with the same source IDs, per-source catalog baselines, version
  lineage, and independent PostgreSQL evidence, while an unavailable registered
  source is listed and rejected without model or database execution.
- **SC-031**: Lossless-projection tests include at least one resource carrying
  multiple codings/repeated elements and prove every expected projected row is
  retained before SQL curation; no upstream-default modification or additive
  projection is accepted without a reviewed provenance/diff record.
- **SC-032**: Catalog generation is byte-stable for unchanged live metadata and
  overlay inputs, preserves readable relations with explicit missing-description
  gaps, rejects nonexistent overlay references and zero-match canonical values,
  and matches live information-schema names/types for every role-readable
  relation in every acceptance source.
- **SC-033**: For each accepted source, schema guide, completion vocabulary,
  validator request, model request, query version, execution, and harness event
  carry one matching source ID and catalog version; cross-source leakage is zero
  in the seeded matrix.
- **SC-034**: The live two-source and default-readiness matrix is recorded as a
  separate user checkpoint. Until it passes, documentation labels multi-source
  implementation as present but not formally accepted.
- **SC-035**: From one successful execution, a user can create a Dataset draft,
  review a compatible Widget draft, add it to a Dashboard draft, and generate
  the first Superset bundle in under three minutes, measured from an already
  eligible execution to `Bundle ready`, with recorded start/end times and zero
  model or database calls during configuration/publication.
- **SC-036**: Every exported asset resolves to exactly one session, query
  version/digest, execution, data source/catalog version, typed result
  schema/digest, immutable Dataset/Widget/Dashboard versions, author, and
  timestamp; every Dashboard Widget has the same source/catalog pair and
  unresolved references are zero in the acceptance fixture.
- **SC-037**: Two exports from identical inputs are byte-identical. Refresh
  restores all saved drafts and versions without a model call or database
  execution.
- **SC-038**: A clean digest-pinned Superset 6.1.0 instance clean-imports one
  canonical fixture for each table/KPI/time-series/bar/proportion family. The
  definitive live Dashboard contains at least two heterogeneous Widgets backed
  by two exact Dataset versions and returns values independently reconciled to
  PostgreSQL. Importing a changed Dataset/Widget keeps the logical Dashboard
  UUID, creates new version-addressed changed children, and reuses unchanged
  children (including a layout-only update) without relying on Superset 6.1.0 to
  overwrite related definitions. The imported Dashboard resolves at
  `/superset/dashboard/catalyst-<lowercase-dashboard-id>/`, and the receipt
  proves the imported UUID and slug match the expected pair. Pointer/bundle/
  manifest/credential and other preflight failures plus transactionally rolled-
  back CLI failures preserve the last verified Dashboard. The
  post-import-verification failure fixture produces `Import failed`, no enabled
  Open/current-success action, a retained diagnostic and recovery target, then
  passes a full Superset-local metadata/home reset plus reimport of the exact
  per-Dashboard last-verified bundle. It also proves missing/corrupt projection
  refusal before reset and recovered-A/failed-desired-B automatic-bootstrap/
  retry suppression; it makes no automatic-rollback claim.
- **SC-039**: After source query changes, 100% of acceptance cases preserve the
  saved drafts, display stale-source state, and retain original source binding.
- **SC-040**: Deterministic UI and manual checks prove empty/populated Ask →
  Dataset → Widget → Dashboard → Publish, every library/review panel, and error
  recovery at desktop, 390×844, 320 CSS px, and a 640-CSS-pixel equivalent
  reflow boundary. Actual 200% browser zoom is deferred polish. Tests
  cover keyboard order, Escape and focus return/containment, status
  announcements, reduced motion, no document overflow, and no obscured
  composer/editor/control.
- **SC-041**: The accepted Ask/query-notebook E2E path passes unchanged in the
  Dashboard Builder shell from profile selection through initial generation,
  manual edit/version, Format, Validate, explicit Run, displayed findings and
  typed results, contextual successor, rerun, stale-result labeling, refresh
  restoration, and New session. The path exposes exactly one canonical SQL
  editor, saves Dataset v1 before requesting the successor, saves Dataset v2
  only after its explicit rerun, and reaches **Save Dataset** with zero missing
  prior actions or evidence.

## Assumptions

- The first release remains an isolated local demo over whatever data is loaded
  into its connected OpenELIS-to-FHIR pipeline and is not a production clinical
  reporting tool. The current dataset's synthetic/real classification is unknown
  unless an authoritative load manifest supplies it.
- Dashboard Builder MVP starts with one successful execution from any already
  accepted single source. Multi-source acceptance can broaden that source set
  later but is not a prerequisite for the first exported dashboard.
- D1 Dashboard membership is intentionally stricter than source identity alone:
  every Widget shares one exact `dataSourceId` plus `catalogVersion`. A catalog
  refresh requires a new Dashboard; rebasing an existing Dashboard to a newer
  catalog is a later migration workflow.
- The reconciled Dashboard Builder design specification and populated Ask
  reference state govern the target visual structure and interaction flow. The
  imported mock supplies layout inspiration only where consistent; the existing
  workbench supplies the complete behavior and evidence within that layout.
- Superset 6.1.0 is the pinned local renderer. Catalyst persists builder drafts
  and emits Superset-native configuration; it does not implement its own
  dashboard renderer or embed clinical result rows in the export.
- Dashboard configuration is fully supervised in this milestone. The initial
  visualization suggestion is a deterministic function of the typed result
  shape and may be overridden by the user; no model visualization call is
  required.
- `Publish to Superset` writes an atomic bundle into a host-visible outbox. A
  bootstrap importer handles an eligible desired bundle on clean startup and an
  explicit CLI helper handles a running instance or failed-target retry;
  API-based publication and reconciliation are deferred.
- D1 guarantees prior-Dashboard preservation only for failures before Superset
  mutation and transactional CLI failures. Post-import verification failure has
  an explicit operator recovery path through a validated per-Dashboard last-
  verified projection, full reset of the Superset-local metadata database/home
  volumes, and verified reimport. It never uses asset-selective deletion, direct
  ORM/REST mutation, automatic rollback, or automatic retry of a still-failed
  desired bundle.
- Only the isolated local demo bundle may contain a labelled read-only demo
  credential. Production secret distribution remains in R5.
- Because the local demo has no authentication, dashboard version `author`
  records the actor kind `human` and MUST NOT imply a verified user identity.
  Production identity attribution remains in R5.
- Users are technical evaluators comparing model and validator behavior; no
  authentication or production role model is introduced in this iteration.
- Existing isolated database credentials and permissions remain authoritative.
  The runtime catalog guides generation and validation but does not hide a
  readable relation or gate manual Run; statement timeout and returned-row
  limits remain operational controls.
- Detailed dataset context is secondary to the query/validation task and begins
  collapsed while a compact identity-and-scale summary remains visible.
- Query structure rather than arbitrary character offsets is the stable unit for
  freezing and remediation; locations may still highlight exact substrings in
  the editor.
- Line wrapping begins enabled to avoid mandatory horizontal scrolling in the
  narrow research workspace; the session preference is presentation state and
  never query content.
- A model repair is advisory until it satisfies scope integrity and complete
  revalidation.
- Validator findings are advisory to a technical evaluator during manual
  execution; a successful database execution does not erase those findings.
- Hidden chain-of-thought is out of scope; the UI exposes structured stages,
  findings, diffs, decisions, and provenance only.
- Iteration is linear for the MVP. Selecting an earlier turn is for inspection,
  not for branching or silently changing the current query.
- A follow-up is always an instruction to produce one complete successor query;
  conversational answers are deferred. Matching execution summaries are valid
  context; value-level result references require the separately approved,
  explicit bounded attachment described by the G2.9 decision.
- The exact visible editor buffer is authoritative for follow-up input. A dirty
  valid buffer becomes a human version, an unchanged buffer reuses its version,
  and an unresolved buffer remains evidence rather than accepted query state.
- The current instruction and relevant retained instructions provide the
  conversational context for this proof of concept. The supplied and omitted
  items are recorded without a fixed history count. Matching diagnostics and
  result schema/count summaries may be included. Result rows remain excluded
  unless the G2.9 checkpoint explicitly replaces this boundary with a
  versioned, user-visible bounded attachment.
- Profile changes are allowed per turn and recorded rather than treated as a
  new session. `New session` is reserved for unrelated work and begins with no
  inherited model context.
- Query profiles, role prompts, review composition, and deterministic query
  checks are owned by Catalyst Gateway. Med-Agent Hub is a generic model
  execution/provider boundary for those roles; its clinical-answer/report
  profile engine remains a separate product surface.
- Multi-source implementation is present in the active change set, but
  requirements FR-064–FR-070 and success criteria SC-030–SC-034 remain
  unaccepted until their dedicated task/checkpoint evidence is recorded.
- Model outputs are nondeterministic evidence even when sampling temperature is
  zero; comparison relies on captured inputs, configuration, and output digests
  rather than assumed repeatability.
- Full production authorization, facility scoping, PHI routing, and durable
  multi-user audit are deferred to the production-security roadmap.

## Research Basis

- Carbon Design System accordion guidance supports progressive disclosure for
  related secondary information, default-collapsed panels, brief descriptive
  headings, and consistent disclosure controls.
- W3C ARIA Authoring Practices requires button semantics, programmatic expanded
  state, controlled-panel relationships, and keyboard activation for disclosure
  and accordion patterns.
- Interactive text-to-SQL research supports clause-level or structured edits
  over token-only replacement, editable explanations for human correction, and
  deterministic transformations for simple identifier, operator, and literal
  changes.
- The existing Catalyst research establishes full revalidation, immutable
  catalog/policy boundaries, stable finding codes, bounded attempts, and result-
  level evaluation as non-negotiable controls.
- Notebook and database-assistant interaction patterns support keeping the
  editable query as the primary artifact, deriving follow-ups from the active
  editor, and retaining compact version history rather than presenting a
  conversational transcript as the main workspace.
- Context-dependent text-to-SQL research supports carrying prior intent and the
  preceding SQL into a follow-up while returning a complete revised query; long,
  unbounded conversation histories and prior result rows are unnecessary for
  this linear proof of concept.
