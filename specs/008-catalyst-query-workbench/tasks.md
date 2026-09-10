# Feature 008 tasks — current work only

**Status:** The owner approved usability-first delivery followed by Dashboard
Builder functionality. This file is the sole detailed progress and acceptance
register for the [Feature 008 roadmap](plan.md). Model comparison and broader
conversation work remain separately scheduled.

## Authoritative roadmap

- [X] Record the approved delivery sequence, acceptance gates, deployment
  targets, and video pacing requirements in `plan.md`.
- [X] Point current authority entry points to the Feature 008 plan and this task
  register without attempting the full specification consolidation.
- [X] Repair the stale integration gitlinks and canonical conformance fixture
  exposed by the unchanged source-pair and conformance gates, using the exact
  reviewed baseline already present in the integration pull request; do not
  include baseline product code.
- [X] Merge the roadmap pull request before baseline, specification, or product
  changes begin.

## Stable Harness/Catalyst/Hub baseline

- [X] Reconcile the accepted Catalyst and med-agent-hub repair revisions into
  the existing harness integration baseline and pin merged, remote-reachable
  revisions.
- [X] Preserve valid OpenMRS integration pins while recording upstream
  publication as separately deferred work.
- [X] Run focused integration checks and the repository-line check allowed for
  the harness branch; resolve concrete failures without weakening the gate.
- [X] Merge the baseline and run the strict ordinary repository-line check from
  harness `main` before local or server deployment.
- [X] Close superseded child pull request #108 after accounting for its Catalyst
  and Hub repair revisions in the merged baseline.
- [X] Record a disposition for every superseded child pull request before
  closing it; finish reconciling dependent dashboard and cloud-evidence branches
  onto current `main` so stale pins cannot undo the baseline.

## Specification consolidation

- [X] Move legacy implementation sequence, physical ownership, checkpoints, and
  complexity constraints into the Feature 008 plan; replace the retired
  implementation-plan body with a successor link.
- [X] Move the separate Dashboard delivery goal's unique integration and
  acceptance requirements into the Feature 008 specification; replace its body
  with a successor link.
- [X] Apply the frozen navigation, composer, palette, Advanced-mode, nonmodal
  data-browser, result-review, and focus requirements to the Catalyst product
  specification and binding design without leaving contradictory old text.
- [X] Preserve frozen mocks, research, overlap findings, and prior handoffs as
  dated evidence with current-authority pointers rather than live status.
- [X] Align README, AGENTS, CLAUDE, SpecKit, quickstart, and document checks with
  the consolidated authority set.
- [X] Inventory prior efforts as completed with evidence, active in this
  delivery, superseded with a destination, or deferred with a next action.
- [X] Verify no unique capability or acceptance criterion disappeared; run
  current link, secret, architecture, and documentation checks.

## Usability iteration 1 — question writing

- [X] Share one presentation and sizing behavior across initial, follow-up, and
  clarification question inputs.
- [X] Preserve an eight-line draft, selection, and focus through manual vertical
  resize, Expand/Restore, request failure, and retry.
- [X] Make Enter insert a newline and Ctrl/Command+Enter prepare once; preparing
  never runs SQL.
- [X] Remove automatic composer tucking without making actions unreachable at
  narrow widths or short heights; replace obsolete expectations deliberately.

Evidence: Catalyst [#83](https://github.com/DIGI-UW/catalyst-ai/pull/83)
merged as `c181b6b` on 10 September 2026. All five hosted jobs passed. The
complete UI unit suite (265 tests), type, lint, production build, deterministic
composer checks, and the full deterministic query-to-table journey passed.

## Combined Dashboard design review

The approved disposition is in [the plan](plan.md#design-extension-review).

- [X] Audit the HIV/output proposal against current storage, UI, turn contracts,
  Spark exports, approved design and vendor documentation; gather the proposal,
  prompt drafts and research in the Catalyst design home.
- [X] Keep Explore / Saved work; integrate grouped saved queries, charts/tables
  and Dashboards plus saved-SQL reuse into current delivery. Schedule larger
  extensions after current UX and Superset completion.
- [ ] Extend the approved mock with saved-work browsing and saved-SQL reuse;
  review the interaction before implementing it. Follow-on A owns the combined
  Widget/Dashboard request and SQL-dependent failure review.
- [X] Merge Catalyst [#85](https://github.com/DIGI-UW/catalyst-ai/pull/85), which
  consolidates the proposals and saved-SQL contract, and update the harness pin
  in [#117](https://github.com/pmanko/clinical-ai-validation-harness/pull/117).
  Preview synchronization follows the current-scope mock extension; future scenarios stay with their follow-on milestone.

## Usability iteration 2 — shell and appearance

- [X] Implement Explore/Saved work, frozen light/dark styling, View options, and
  workspace-wide Advanced mode using current Carbon controls and theme state.
- [X] Relocate session creation, reopening, renaming, source selection, and turn
  navigation before removing the current rail.
- [X] Preserve question, SQL, parameters, source, profile, execution, result,
  selected asset, and browse state through mode, theme, and navigation changes.
- [X] Keep every analyst capability directly reachable and avoid a second
  preference, editor, or state owner.

Implementation and self-validation: Catalyst
[#86](https://github.com/DIGI-UW/catalyst-ai/pull/86), merged as `e7b0896`
on 10 September 2026 with all five hosted jobs passing. All 269 UI unit
tests, lint, type/build checks and seven deterministic browser checks passed.
The browser checks cover draft/profile retention, SQL selection and undo,
keyboard and narrow layouts, and the existing execution-to-publication flow.
Light/dark/narrow screenshots were inspected privately. Live/demo recordings
were not run for this shell-only iteration.

- [X] Merge the shell PR.
- [X] Merge the compatible harness pin and task-register update in
  [#118](https://github.com/pmanko/clinical-ai-validation-harness/pull/118).
- [ ] Complete local/server deployment and owner acceptance at the gates below,
  after Available data and result review are ready.

## Usability iteration 3 — Available data

- [X] Provide complete, nonmodal whole-schema search over relation names,
  reviewed descriptions, and columns while the question remains available.
- [X] Show exact identifiers and types and use exact names when reviewed friendly
  metadata is absent; do not invent clinical descriptions.
- [X] Separate schema browsing from legacy Dataset row effects so opening,
  searching, and retrying never fetches clinical result rows.
- [X] Prevent stale-source schema during source changes and cover loading,
  no-match, empty, error/retry, close/reopen, keyboard return, and narrow layout.

Implementation and self-validation: Catalyst
[#87](https://github.com/DIGI-UW/catalyst-ai/pull/87), merged as `f50e6ce`
on 10 September 2026 with all five hosted jobs passing. All 271 UI unit
tests, type/build, lint and eight deterministic browser checks passed. Checks
cover whole-schema search across pages, no incidental row/execution requests,
source-change races and retry, and preserved focus, draft and browser scroll.
Desktop/narrow screenshots and the real OpenELIS schema were inspected privately.
The compatible harness pin is included with this register update. Complete
dual-source deployment and owner acceptance remain open.

## Usability iteration 4 — result review

- [ ] Give Dataset review the sole full result table, including access to each
  retained earlier execution without saving the wrong current result; keep useful thread
  summaries and make database errors, warnings, and row limits plain and visible.
- [ ] Keep exact provenance in a named disclosure and restore focus to the
  control that opened review.
- [ ] Apply clear Saved work labels without changing Dataset, Widget, Dashboard,
  immutable-save, stale-result, publication, or receipt identities.
- [ ] Run affected component/API tests, UI type checking, lint, build, and
  deterministic desktop/narrow browser checks for all four usability iterations.

## First owner gate — complete usability design locally

- [ ] Merge the complete usability implementation and deploy exact compatible
  revisions locally with `scripts/catalyst-mvp.sh`, preserving retained data.
- [ ] Exercise the real OpenELIS and OpenMRS sources through schema browse,
  drafting, preparation, explicit Run, results, refinement, and Advanced mode.
- [ ] Publish side-by-side design evidence and a paced local walkthrough for
  asynchronous owner review; record implementation, deployment, self-validation,
  and owner feedback separately.
- [ ] Start Dashboard functionality expansion only after feedback from this
  local gate is recorded in the plan/tasks.

## Dashboard functionality — saved work

- [ ] Save only a successful current execution; preserve exact SQL, typed values,
  source, dialect, schema, query, and execution identity in immutable versions.
- [ ] Restore saved Dataset versions and protect against stale or mismatched
  results.
- [ ] Browse Saved queries, Charts and tables, and Dashboards within Saved work;
  show source, saved version, dependencies and available review/reuse actions.
  Returning to Explore preserves the ongoing draft and selected work.
- [ ] Start from this SQL loads the exact saved parameterized SQL and typed
  values into the one editor, retaining the Dataset version and source/dialect.
  Preserve an existing draft; a different source requires an explicit new or
  matching session. Loading never runs SQL or modifies saved versions.
- [ ] Keep saved SQL/parameters accessible when historical execution details
  are unavailable; label that evidence separately. Verify reuse, explicit Run,
  failure/retry and a successful successor save for both real sources.
- [ ] Finish deterministic visualization compatibility and allow a person to
  review, select, and save supported Widget versions.

## Dashboard functionality — arrangement and publication

- [ ] Arrange and restore multiple same-source Widgets without losing accepted
  layout behavior.
- [ ] Generate deterministic native Superset bundles and expose publication
  status only from actual importer receipts.
- [ ] Keep import failures actionable and open the stable Superset URL only
  after successful import.
- [ ] Inspect one rendered value against the originating Catalyst result without
  a second database query.
- [ ] Compare the live Workbench, Dataset and Widget review/libraries, Dashboard
  arrangement/library, and every publish/import state with the binding design.

## Local/server deployment and evidence

- [ ] Deploy exact merged compatible revisions locally and to
  `catalyst.openelis-global.org` using the owning checkout and harness wrapper;
  preserve retained data and run importer actions in the tested environment.
- [ ] Prove the full real path for OpenELIS and OpenMRS on both deployments and
  retain revisions, source/model configuration, traces, screenshots, timestamps,
  bundles, receipts, and visible-result evidence under one run identity.
- [ ] Capture with the existing Playwright video project and archive raw footage
  before another run removes it.
- [ ] Render short cards/captions for at least 5 seconds, longer text at about 3
  words/second plus 2 seconds, and results/details for at least 8 seconds; retain
  captions during holds and label accelerated waits.
- [ ] Watch each final cut at normal speed, confirm captions neither disappear
  early nor cover demonstrated information, then publish new immutable media
  filenames and update all public video/poster references together.
- [ ] Record final local/server evidence, current public links, and explicit
  owner acceptance before marking this delivery complete.

## Follow-on milestones after current delivery

These milestones start after current UX/Superset deployment and owner acceptance.
Their detailed contracts and vendor choices require review when each starts;
they are not additional completion gates for the current goal.

### A. Multi-artifact design requests and shared controls

- [ ] Extend the approved mock within Explore / Saved work: one ask proposes a
  Widget and Dashboard revision in one turn; a SQL-dependent variant shows
  explicit Run, dependency order and failure recovery. Obtain design review.
- [ ] Define and implement the reviewed proposal contract using existing state
  owners and Hub-owned prompts. Prove compare/apply/discard/undo, immutable
  saves, explicit downstream adoption and independent versus waiting changes.
- [ ] Review HIV metric definitions against the live Spark source: deduplicated
  visits, absolute-CD4 observations, unknown gender and undated medication
  requests. Validate chronological grouping, partial periods, visible filter
  exemptions and explicit saved defaults without changing metric meaning.
- [ ] Verify the complete interaction and native Superset controls; record
  implementation, merge, deployment, validation and owner acceptance separately.

### B. Metabase publication

- [ ] Select a supported runtime and ordinary object API or paid serialization
  path; prove connection to the same configured Spark source before publishing.
- [ ] Publish reviewed saved versions, verify native rendering and the agreed
  period/grouping/filter semantics, then repeat publication without duplicates.
- [ ] Prove actual receipts, actionable failures and independent configured
  destinations. Record deployed revisions and owner acceptance.

### C. Evidence publication

- [ ] Pin compatible self-hosted runtime, components and a direct source
  connector. Prove standalone Spark compatibility; if unavailable, retain the
  draft and report the concrete limitation before any export implementation.
- [ ] Publish a reviewable project from saved versions; prove native rendering,
  selected grouping/filter behavior and repeat publication. Do not substitute
  copied preview rows or introduce a replacement warehouse.
- [ ] Prove actual deployment receipts, failure recovery and independent
  destinations. Record deployed revisions and owner acceptance.

## Before product code

- [ ] Review the current program roadmap, implementation plan, product
  specification, tasks, and binding Dashboard design with the owner.

## Phase 1 — generic Catalyst connection

- [X] Replace the required analytics address and generated-catalog configuration
  with source ID, label, connection configuration or reference, explicit dialect,
  and optional non-filtering descriptions.
- [X] Make source availability independent so one unavailable source does not
  prevent application startup or use of another source.
- [X] Limit shared connection behavior to availability, complete readable schema
  discovery, exact SQL execution with typed parameters and bounds, and rows or
  the database error.
- [X] Route generated and manually edited queries through the same shared
  connection-execution code.
- [X] Supply the same source, dialect, and readable-schema snapshot to the model,
  Available data, editor, validation, and recorded execution.
- [X] Preserve database-native relation and column identifiers and the active
  engine's qualification rules; remove the PostgreSQL-shaped name restriction.
- [X] Make editor highlighting, formatting, and keyword/function completion use
  the declared dialect.
- [X] Keep validation advisory and prove that a warning cannot block exact
  selected SQL.
- [X] Add focused tests with arbitrary fixture relation names, successful
  execution, database failure, and an unavailable source. Do not assert a
  relation count.

**Pause:** Review the connection behavior and focused proof before changing a
reference deployment.

## Phase 1 — Spark reference sources

For each source actually included in the demonstration or comparison:

- [ ] Enable the pinned FHIR Data Pipes Parquet path and materialize applicable
  ViewDefinitions against retained demo data.
- [ ] Run one manual Spark query to prove materialization and one known fact.
- [ ] Connect Spark through the generic Catalyst connection and prove Catalyst
  discovers the same readable tables.
- [ ] Connect Superset to the same Spark source.
- [ ] Prove one successful browser query, one database error, and one saved
  Dataset-to-Superset render.
- [ ] Submit one intentional write attempt through the Spark connection, show
  its visible refusal, and confirm source data is unchanged.
- [X] Remove the separate clinical analytics store, generated catalog, copied
  marts, sink scripts, preferred-engine wiring, fallback, and dedicated tests.
- [ ] Carry forward only descriptions or relationships demonstrated to help the
  accepted readable schema.
- [X] Remove the standalone `catalyst-agents` and `catalyst-mcp` packages and
  their development wiring; the active Gateway/med-agent-hub path owns model
  execution.

The manual Spark query is only a one-time connection/materialization check. Do
not create a per-scenario or per-run Spark comparison path.

**Pause:** Review the live Catalyst and Superset smoke before merge.

## Phase 1 — reader-led harness and scenario references

- [ ] Pin the accepted Catalyst revision.
- [ ] Confirm the OpenMRS source used by the comparison does not mix another
  source's readable schema.
- [ ] If scenario design reveals a concrete missing semantic need, pause for
  owner review before adding one minimal source-owned view.
- [X] Remove direct analytics-database access, separate read-only and “gold”
  execution, automatic result matching, their options/events, and dedicated
  tests. Do not translate them to Spark.
- [ ] After the accepted readable schema exists, author and run each ready-turn
  reference once through Catalyst and store its expected facts.
- [ ] Review clarification and unsupported expected responses without SQL,
  including whether each data-availability question is answerable.
- [ ] Make each ready model turn execute selected SQL once through Catalyst;
  clarification and unsupported turns execute none.
- [ ] Present the conversation, actual model context, SQL, rows or error, static
  reference or expected response, rubric, and recorded configuration without an
  automatic verdict.
- [ ] Add focused tests for the simplified runner, incomplete-collection label,
  and reader packet.

**Pause:** Review the scenario references and reader packet before paid live
model runs.

## Separately scheduled — model comparison

- [ ] Start a new result set after the generic connection, included reference
  sources, and scenario references are accepted.
- [ ] Hold the selected suite, rubric, data, and model-team definitions constant
  for this batch and record the identities actually used.
- [ ] Run the complete suite once for each selected model team.
- [ ] Verify every case contains the complete reader packet and an incomplete
  collection is labelled incomplete.
- [ ] Apply the shared rubric once through a deliberately selected full-context
  human or frontier-model reader.
- [ ] If the reader is a frontier model, state in the report that this is one
  model-reader pass rather than independent human review.
- [ ] Publish the report and linked evidence without an automatic score,
  disqualification, rank, tie-break, winner, or production-readiness claim.
- [ ] Pause for owner review before Phase 1 closeout.

## Separately scheduled — broader conversation scope

- [ ] Review the Phase 1 report with the owner.
- [ ] Define the broader conversation-mode behavior and acceptance before
  implementation. Do not infer it from Phase 1.

## Phase 3 — Dashboard Builder completion

- [ ] Cover Dataset, Widget, Dashboard, and publication actions through their
  public Gateway routes.
- [ ] Convert a successful typed execution into an immutable Dataset without
  engine-specific literal rules.
- [ ] Preserve exact SQL and typed values for the active dialect and return an
  actionable error when publication cannot represent them safely.
- [ ] Finish deterministic compatibility and reviewable suggestions for the
  accepted visualization families.
- [ ] Finish deterministic native Superset bundle generation and publication
  status based on explicit importer receipts.
- [ ] Run the real model-assisted browser workflow through Spark: ask, edit,
  format, Run, save Dataset versions, save Widgets, arrange and publish a
  Dashboard, import it, and open its stable Superset URL.
- [ ] Inspect one rendered value against the originating Catalyst result without
  a second database query.
- [ ] Compare the live Workbench, Dataset review/library, Widget review/library,
  Dashboard library/arrangement, and publish/import states side by side with the
  binding design.
- [ ] Confirm profile selection, generation/failure evidence, Clear/Restore,
  complete Available data browsing, resizable composer/thread, single editor,
  review panels, multiple Widgets, and actionable publication states remain.
- [ ] Pass focused API, component, bundle, publication, keyboard, focus, error,
  desktop, and narrow-layout checks.
- [ ] Obtain final owner acceptance of the browser-visible workflow.

Phase 3 does not require repeated model runs, restart/reset matrices, environment
parity, independent database reconciliation, or exhaustive infrastructure
failure simulation.

## Guardrails

- Use the smallest change that satisfies a current acceptance item.
- Remove behavior with no current requirement and its tests; do not preserve it behind a
  compatibility flag or port it to Spark.
- Do not add a connector framework, SQL translator, second catalog service,
  relation allowlist, schema ranking, fixed context count, shadow warehouse, or
  automatic fallback.
- Do not add per-run reference execution, result hashing, automatic factual
  equivalence, numerical thresholds, mandatory repeated readers, reseeding,
  restart-persistence proof, local/demo parity, or live Spark on every pull
  request.
- If the thin connection, complete readable schema, or pinned FHIR Data Pipes
  path fails, record the concrete failure and return to the owner before adding
  another subsystem.
