# Feature Specification: Catalyst Query Workbench

**Feature Branch**: `codex/catalyst-mvp-umbrella`

**Created**: 2026-07-17

**Status**: Implemented through the iterative-query notebook and Gateway-owned
query-orchestration refactor; final clean-pin model/PostgreSQL validation is
complete, while actual keyboard/zoom evidence and user acceptance remain open

**Input**: Refine the Catalyst query experience with manageable dataset context,
targeted query remediation, complete validator feedback, editable SQL,
frictionless manual execution of imperfect drafts, execution-error feedback,
iterative human correction, and contextual follow-up generation from the exact
current editor state.

**Current architecture (2026-07-29)**: Catalyst Gateway owns the governed-query
profile registry, role prompts, writer/reviewer composition, deterministic lint,
repair, finalization, and query evidence. Med-Agent Hub remains the shared model
transport/provider boundary and exposes one generic structured role-execution
primitive (`POST /v1/hub/generate`) per Gateway-selected role. Hub continues to
own its separate clinical-answer/report profiles; those profiles are not the
Catalyst query engine. Historical G2.1–G2.8 evidence below may describe the
earlier Hub-owned query-profile implementation and is retained as evidence of
the path that was tested at that time, not as current ownership guidance.

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
  snapshot, initial question, at most five most-recent follow-up instructions,
  and only matching validation/execution summaries. Do not send result rows,
  credentials, hidden reasoning, or an undifferentiated transcript.
- Q: How many active query inputs should an evaluator see? → A: One canonical
  SQL editor plus one reusable natural-language composer. The composer handles
  the initial Ask before a session and every Refine instruction afterward; the
  original question remains in history instead of a disabled duplicate form.
- Q: What should “Know what to ask” describe? → A: The reviewed supported query
  catalog—exact relation names, columns, types, nullability, meanings, and
  truthful runtime capabilities—from the same versioned source used for model
  grounding and editor completion. Broad database grants are not implicit
  product support.
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
  `catalog-overlay.json` per source (identity, approved views, semantic
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
7. **Given** the approved catalog is available, **When** the user requests
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
    only the Hub role calls declared by the selected Gateway profile, while the
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
5. **Given** curated analytics views with complete view/column comments and a
   reviewed source overlay, **When** the catalog generator runs against the live
   database, **Then** it emits only the Gateway-consumed catalog shape and fails
   on missing metadata, unknown relations, or canonical semantic values that
   match no live row.
6. **Given** a generated source catalog, **When** the schema guide, completion,
   deterministic validator, and model request are inspected, **Then** all four
   use the same source ID and catalog version and preserve that binding in
   session, turn, version, execution, and harness evidence.
7. **Given** more than one registered source, **When** default readiness is
   requested, **Then** it reports only the documented default-source boundary;
   the UI and documentation do not imply that every registered source was
   checked. Full registry readiness remains a separately tracked follow-up.

### Edge Cases

- A finding points to a query unit that no longer exists in the current version.
- Two findings overlap or require coordinated edits across query units.
- A model returns a full replacement when only a patch was requested.
- A human edit changes placeholders without updating typed values, or vice versa.
- A draft parses but references a missing field, incompatible type, or stale
  catalog version.
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
  view, and column identifiers derived from the active approved catalog. Completion ordering MUST
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
- **FR-032**: A reviewed Gateway query profile MUST obtain one complete writer
  candidate, run deterministic lint, and give the complete candidate plus
  specific findings to its declared reviewer role. For the comparative
  cross-family profile, the reviewer MUST be a different model family. When
  correction is required, the reviewer MUST return one complete corrected
  candidate rather than a text or JSON-pointer patch. The Gateway MUST validate
  the correction contract and rerun every deterministic check before
  finalization. Each model role is executed through one generic Hub role request;
  Hub MUST NOT select the Catalyst profile or compose its roles.
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
  digests, original question, at most the five most-recent preceding follow-up
  instructions, active catalog/policy/profile, and only validation findings or
  an execution diagnostic/shape summary that matches the exact editor digest.
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
  validation, and model grounding MUST derive from the same versioned runtime
  catalog. The guide MUST show every reviewed supported relation and column with
  qualified name, type, nullability, description, grain, and unit relationship
  where applicable. It MUST distinguish the supported catalog from relations
  merely reachable through database-role permissions.
- **FR-061**: The Refine composer MUST visibly state whether its exact base has a
  matching execution summary, stale displayed results, or no execution. Until a
  bounded result-row attachment is explicitly approved and versioned, it MUST
  describe attached context as an execution summary and MUST NOT imply that row
  values are supplied to either model.
- **FR-062**: Catalyst Gateway MUST own the governed-query profile registry,
  model-role mapping, role prompts, sampling/output knobs, deterministic
  writer/reviewer orchestration, correction policy, and query-profile evidence.
  The registry MUST distinguish writer-only, self-reviewed, and cross-family
  reviewed profiles. Runtime availability MUST require Hub's exact versioned
  backend inventory and every unique required writer/reviewer model alias.
  Unknown profiles, missing aliases, an unreachable router catalog, and
  missing/malformed inventory MUST fail closed before events, previews, or model
  calls without silent profile or model substitution.
- **FR-063**: Med-Agent Hub MUST expose a generic structured single-role
  execution boundary that accepts the Gateway-selected model, messages,
  response format, and bounded invocation configuration and returns assistant
  content without Catalyst-specific profile selection, query lint, review
  orchestration, database access, or SQL execution.
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
- **FR-069**: Each source catalog MUST be generated from live curated
  view/column metadata plus one reviewed source overlay. Generation MUST validate
  approved relations, types, grain, semantic dimensions, and configured
  canonical values against the live source and MUST fail rather than publish a
  guessed or zero-match semantic value. Hand-edited generated catalogs are
  prohibited.
- **FR-070**: Current readiness MUST explicitly describe its default-source-only
  scope. Full per-source readiness and live two-source acceptance MUST remain
  open until dedicated tasks and evidence prove every registered source; the
  presence of implementation plumbing or unit tests alone MUST NOT close that
  checkpoint.

### Key Entities

- **Workbench Session**: A persistent identity covering the original question,
  selected Gateway profile, initial and most-recently targeted data sources,
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
  identity, approved views, and semantic canonical values that cannot be derived
  from PostgreSQL metadata alone.

### Evidence, Provenance & Data Boundaries

- **Clinical evidence records**: Only records currently projected from the
  connected OpenELIS instance through FHIR into versioned approved analytics
  views are in scope; row identifiers and aggregate assertions remain linked to
  the executing query version. Runtime synthetic/real classification MUST be
  carried from authoritative provenance when available and MUST NOT be inferred
  from the data shape or demo deployment mode.
- **Decision rationale**: Each validation and repair-scope decision records the
  applicable rule and why it warned or proposed a repair; each execution records
  that manual Run bypassed validator gating and the database outcome was
  authoritative. Each turn records why its snapshot reused or created an
  effective base and why every produced candidate was selected, unselected, or
  retained only as invalid evidence.
- **Operating metadata**: Session lineage, query versions, validation runs,
  repair proposals, execution attempts, iteration turns, editor snapshots,
  bounded revision-context membership, result staleness, profile/prompt/catalog/
  dataset provenance, editor/formatter revision, and harness-compatible run
  events.
- **Accepted deterministic inputs**: Versioned validator rules, repair templates,
  SQL formatter and PostgreSQL keyword source, approved catalog, execution
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
  keywords plus the approved catalog, and graceful no-catalog behavior at
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
  correction of lint-clean SQL; bounded-history truncation; profile switching;
  stale results; refresh; and New Session isolation.
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
  plus live information-schema checks prove that every reviewed physical
  fact-view column appears exactly once with the correct name and type.
- **SC-028**: A 100-row execution keeps the document workflow bounded through a
  labelled result scroll region while its exact query-version label, stale
  status, row count, and keyboard navigation remain visible.
- **SC-029**: Contract and integration tests prove every advertised Catalyst
  query profile is Gateway-owned, produces a digest-bound prompt/model/config
  snapshot, and invokes Hub only through the generic role endpoint; Hub contains
  no Catalyst query profile, query prompt, lint, correction, or orchestration
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
  overlay inputs, rejects missing view/column comments and zero-match canonical
  values, and matches live information-schema names/types for every approved
  relation in every acceptance source.
- **SC-033**: For each accepted source, schema guide, completion vocabulary,
  validator request, model request, query version, execution, and harness event
  carry one matching source ID and catalog version; cross-source leakage is zero
  in the seeded matrix.
- **SC-034**: The live two-source and default-readiness matrix is recorded as a
  separate user checkpoint. Until it passes, documentation labels multi-source
  implementation as present but not formally accepted.

## Assumptions

- The first release remains an isolated local demo over whatever data is loaded
  into its connected OpenELIS-to-FHIR pipeline and is not a production clinical
  reporting tool. The current dataset's synthetic/real classification is unknown
  unless an authoritative load manifest supplies it.
- Users are technical evaluators comparing model and validator behavior; no
  authentication or production role model is introduced in this iteration.
- Existing isolated database credentials and permissions remain authoritative.
  The approved-view catalog guides generation and validation but does not gate
  manual Run; statement timeout and returned-row limits remain operational
  controls.
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
- The initial question plus the five most-recent prior follow-up instructions
  provide sufficient conversational context for this proof of concept. Matching
  diagnostics and result schema/count summaries may be included. Result rows
  remain excluded unless the G2.9 checkpoint explicitly replaces this boundary
  with a versioned, user-visible bounded attachment.
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
