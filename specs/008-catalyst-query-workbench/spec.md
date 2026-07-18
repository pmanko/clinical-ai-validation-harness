# Feature Specification: Catalyst Query Workbench

**Feature Branch**: `codex/catalyst-mvp-umbrella`

**Created**: 2026-07-17

**Status**: In implementation — G2.3 passed; G3 evidence preparation in progress

**Input**: Refine the Catalyst query experience with manageable dataset context,
targeted query remediation, complete validator feedback, editable SQL,
frictionless manual execution of imperfect drafts, execution-error feedback,
and iterative human correction.

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
9. **Given** a persisted query version, **When** editing, completion, wrapping,
   or formatting changes the working buffer, **Then** the persisted version is
   unchanged and Validate or Run creates a new immutable child containing the
   exact submitted SQL and typed parameters.
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

### Edge Cases

- A finding points to a query unit that no longer exists in the current version.
- Two findings overlap or require coordinated edits across query units.
- A model returns a full replacement when only a patch was requested.
- A human edit changes placeholders without updating typed values, or vice versa.
- A draft parses but references a missing field, incompatible type, or stale
  catalog version.
- A structured Hub response repeatedly or intermittently omits a required
  parameter `name`; only a sole question-grounded unnamed parameter and sole
  remaining SQL placeholder may be joined deterministically. All other cases
  remain visible for manual correction.
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
- **FR-007**: Every generated, automatically remediated, or human-edited draft
  MUST be an immutable version linked to its parent, author type, profile,
  source findings, validation outcome, and execution outcome.
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
  exact SQL and typed parameters as a new child version before operating on it;
  earlier versions remain inspectable and unchanged.
- **FR-030**: Editor behavior MUST remain usable when catalog completion is
  unavailable: editing, formatting, validation, and manual Run continue, and
  the missing completion source is reported without inventing identifiers.
- **FR-031**: A generation or structured-contract failure MUST NOT discard
  research evidence. The workbench MUST persist and display the raw model output,
  best parseable draft/parameters, attempt number, exact failing object path and
  message, and profile/model/prompt/schema provenance. Any deterministic repair
  of a missing parameter name MUST be proven against one unambiguous remaining
  SQL placeholder; otherwise the draft remains explicitly unresolved for manual
  correction.
- **FR-032**: After generation yields a structurally parseable draft, correction
  retries MUST use a strict patch-only response contract localized to the
  reported failing paths. SQL text changes MUST be anchored to one exact source
  fragment; parameter and expected-column changes MUST address explicit JSON
  Pointer paths. The Hub MUST reject full replacements, duplicate or
  out-of-scope paths, ambiguous text matches, and any mutation of unaffected
  fields, then revalidate the reconstructed complete candidate from the
  beginning. This generation-internal correction boundary does not enable the
  broader user-accepted remediation workflow in User Story 2.

### Key Entities

- **Workbench Session**: A persistent identity covering the original question,
  selected profile, dataset and catalog versions, current draft pointer,
  dataset-browser state, and ordered history of user and system actions.
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
  authoritative.
- **Operating metadata**: Session lineage, query versions, validation runs,
  repair proposals, execution attempts, profile/prompt/catalog/dataset
  provenance, editor/formatter revision, and harness-compatible run events.
- **Accepted deterministic inputs**: Versioned validator rules, repair templates,
  SQL formatter and PostgreSQL keyword source, approved catalog, execution
  policy, and reviewed query-patch contract.
- **Advisory inputs**: Model-generated repair proposals, suggested updates, and
  human comments remain proposals until explicitly applied and revalidated.
- **PCCP/change record needs**: Material changes to query prompts, profile roles,
  validator classification, repair policy, manual-run policy, or execution policy
  require old/new behavior, evaluation protocol, rollback conditions, and
  residual-risk documentation.

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
  Validate and Run each operate on a newly persisted exact child version.

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
