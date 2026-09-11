# Feature 008 tasks — current work only

**Status:** The owner approved usability-first delivery followed by Dashboard
Builder functionality. This file is the sole detailed progress and acceptance
register for the [Feature 008 roadmap](plan.md). Model comparison and broader
conversation work remain separately scheduled.

## Next owner checkpoint

- [X] Record the owner's 10 September request in the existing plan: finish a
  working server release and re-record both demos using the new styles, with
  FHIR Data Pipes kept to a brief introduction.
- [ ] Complete the saved-work, Dashboard, local/server verification and video
  acceptance items below; present the working server and both refreshed videos
  together with unresolved findings for owner review.
- [ ] Verify the app against the approved mock with matched light/dark and
  wide/narrow screenshots. Resolve the observed dense Saved queries table,
  clipped actions and stray follow-up control; carry direct mock spacing/type
  and component treatment across Explore, Saved work and review panels.
- [ ] Record owner acceptance of that checkpoint. Implementation or green checks
  alone do not mark this accepted.

Local development now serves the working Catalyst UI at `localhost:13000`
against the retained local Gateway and both real sources. Local testing does
not wait for merges. Final release/acceptance revisions remain pinned and merged.

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

Post-gate correction: the earlier checks preserved draft/focus but did not
measure actual expansion. The deployed field remained 96 pixels high after
Expand because its layout effect reapplied the remembered height. Catalyst
[#90](https://github.com/DIGI-UW/catalyst-ai/pull/90) corrects that effect and
adds real browser height checks for initial and follow-up questions. Local
validation passed all 274 UI unit tests, type checking, lint, build and ten
deterministic browser checks; live development measurements were 96 → 288 → 96
pixels at a 720-pixel window height. The correction merged as `ae3ad4b` with all
five hosted jobs passing and is pinned by this integration update. Keep deployment
and measured resize proof in the private local review bundle, separately from
its original query-workflow recordings. The broader composer/Run layout remains
part of owner review.

## Combined Dashboard design review

The approved disposition is in [the plan](plan.md#design-extension-review).

- [X] Audit the HIV/output proposal against current storage, UI, turn contracts,
  Spark exports, approved design and vendor documentation; gather the proposal,
  prompt drafts and research in the Catalyst design home.
- [X] Keep Explore / Saved work; integrate grouped saved queries, charts/tables
  and Dashboards plus saved-SQL reuse into current delivery. Schedule larger
  extensions after current UX and Superset completion.
- [X] Prepare the saved-work browsing and saved-SQL reuse mock extension in
  Catalyst [#91](https://github.com/DIGI-UW/catalyst-ai/pull/91), tested at
  `61c0805`. Four focused offline browser checks cover draft preservation,
  cancellation, immutable SQL/typed values, another source, missing historical
  results, and the retained chart-to-dashboard route. Light/dark and 320/390px
  screenshots were inspected privately. The existing UI suite passed 274 unit
  tests, type/lint/build and ten deterministic browser checks; documentation
  checks passed. The private preview is supplied through the owning task.
- [X] Review and merge the saved-work mock interaction before implementing it,
  then update the Catalyst pin and public preview together. The owner approved
  continuing on 10 September 2026. Catalyst
  [#91](https://github.com/DIGI-UW/catalyst-ai/pull/91) merged as `f925176` after
  all five hosted checks passed. This integration pins that revision and copies
  all six preview assets, with its specification link pinned to the same source.
  Follow-on A retains the combined Widget/Dashboard request and SQL-dependent
  failure review.
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
- [ ] Complete owner acceptance and final local/server delivery at the gates
  below.

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
The compatible harness pin merged in [harness #119](https://github.com/pmanko/clinical-ai-validation-harness/pull/119).
The first local dual-source proof is recorded below; final server delivery and
owner acceptance remain open.

## Usability iteration 4 — result review

- [X] Give Dataset review the sole full result table, including access to each
  retained earlier execution without saving the wrong current result; keep useful thread
  summaries and make database errors, warnings, and row limits plain and visible.
- [X] Keep exact provenance in a named disclosure and restore focus to the
  control that opened review.
- [X] Apply clear Saved work labels without changing Dataset, Widget, Dashboard,
  immutable-save, stale-result, publication, or receipt identities.
- [X] Run affected component/API tests, UI type checking, lint, build, and
  deterministic desktop/narrow browser checks for all four usability iterations.

Implementation, merge and self-validation: Catalyst
[#88](https://github.com/DIGI-UW/catalyst-ai/pull/88), merged as `60cc7b5`
on 10 September 2026 with all five hosted jobs passing. All 274 UI unit tests,
type checking, lint, build and nine deterministic browser checks passed. Coverage
includes exact earlier-run review, save guards, missing saved-query evidence,
full-table paging and types, keyboard focus, disclosure, 320/390/640px layouts,
and the existing save-to-publication regression. Light/dark/narrow screenshots
were inspected privately; warning overlap was corrected and covered. Documentation
links, consistency and drift checks passed. The compatible harness pin merged in
[#120](https://github.com/pmanko/clinical-ai-validation-harness/pull/120).
The first local deployment and remaining acceptance are recorded below.

## First owner gate — complete usability design locally

- [X] Merge the complete usability implementation and deploy exact compatible
  revisions locally with `scripts/catalyst-mvp.sh`, preserving retained data.
- [X] Exercise the real OpenELIS and OpenMRS sources through schema browse,
  drafting, preparation, explicit Run, results, refinement, and Advanced mode.
- [X] Provide private side-by-side design evidence and a paced local walkthrough for
  asynchronous owner review; record implementation, deployment, self-validation,
  and owner feedback separately.
- [X] Record owner feedback before starting Dashboard functionality expansion.
  On 10 September 2026 the owner authorized continuing, with minor padding and
  typography issues to polish later.
- [ ] Finish visual alignment with the approved mock, including composer/Run
  padding on desktop and narrow layouts. The owner clarified on 10 September
  that the heading weights, font presentation and Catalyst mark should closely
  match the mock in the current iteration; reusable Carbon controls are retained.
  The owner also identified the follow-up form's old inner border and toolbar
  padding; their correction is merged in Catalyst #92. Deployment review follows.

Local implementation/deployment/self-validation, 10 September 2026: harness
`e8f6cb3`, Catalyst `60cc7b5`, and Hub `75d0ff0` passed the strict repository-line
check, wrapper startup and health checks in the checkout owning the isolated
stack. Retained mount locations and environment configuration were unchanged;
no seed or reset was run. Both real-source browser journeys passed, each with
two explicit executions and no execution during preparation. The selected real
profile was `catalyst-query-gemma-4-12b-qwen2.5-14b-checked`.

The private review bundle is `catalyst-ux-gate-20260910`, supplied through the
owning task rather than committed or publicly published. It retains raw footage,
traces, exact revisions/configuration and execution responses. Both final cuts
were checked at normal playback speed: OpenELIS 2:18 and OpenMRS 2:15, with
readable cards, eight-second result/details holds and labeled accelerated model
waits. The SQL reading view was scrolled clear of the panel footer before the
final recording. Screenshots compare the approved mock with the deployed
light/dark entry screen and result review.

Owner feedback was received on 10 September 2026: continue implementation and
polish the minor padding and font presentation issues later. The local UX gate
is cleared for saved-work and Dashboard functionality. Carry the composer/Run
spacing at a 720-pixel window height into final polish. The owner's subsequent
feedback brought font hierarchy, the Catalyst mark and direct composer style
alignment into the current iteration. This
does not close the later saved-work, server, Superset or final owner acceptance.

The live walkthrough exposed an incorrect execution URL in two browser-test
observers. Catalyst [#89](https://github.com/DIGI-UW/catalyst-ai/pull/89), merged as
`4d9c1e9`, corrects those observers and proves an explicit Run is counted in the
existing query-to-Dashboard test. Four focused browser checks, type checking and
lint passed, as did all five hosted jobs. It changes tests only; this harness
pins that merged revision while preserving the exact application revision of
the recorded local proof above.

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

Saved-query iteration, 10 September 2026: Catalyst
[#92](https://github.com/DIGI-UW/catalyst-ai/pull/92), merged as `905e1e6`,
implements confirmed reuse,
preserved question/follow-up/SQL/typed values, return to the earlier draft,
independent access to saved configuration, and explicit dialect metadata on new
saves. It also aligns typography, labels, buttons and the Catalyst mark with the
rendered approved mock. Both composers use the mock's padding and focus spacing;
the follow-up form's nested border and old toolbar layout are removed.
Local checks passed: 277 UI tests, 77 focused Gateway
tests, type/lint/build, 11 deterministic browser checks and documentation checks.
The final composer correction passed 41 focused component tests and all 11
browser checks against the active development checkout. Light, dark and narrow
screenshots were inspected and remain private. All five hosted jobs passed on
the final PR head `cf4e99d`. Compatible deployment and the real-source
reuse/Run/successor-save proof are recorded separately before closing these
acceptance items. Harness [#125](https://github.com/pmanko/clinical-ai-validation-harness/pull/125)
merged the compatible pin as `61ea6fd`. Local services were updated and wrapper
health checks passed with retained data; the working UI is served directly for
ongoing development. Catalyst [#93](https://github.com/DIGI-UW/catalyst-ai/pull/93) adds the on/off
Advanced mode switch and fixes the source identity defect exposed by live reuse:
the raw session stores its source in provenance, while Dataset save previously
read a missing top-level field and defaulted to OpenELIS. Saving now uses the
recorded identity and refuses to guess a missing source. A regression through
the real operating store and public save route failed for both source identifiers
before the fix and passed afterward. All 83 focused Gateway, saved-object and
canonical Superset fixture tests passed, with formatting/lint checks. The
local refresh and wrapper health checks passed with retained data. Real-source
browser checks now pass for both OpenELIS and OpenMRS: saved SQL opens without
execution, explicit Run succeeds, a separate immutable save retains source/SQL/
parameters, and Return to previous draft restores the draft. Catalyst #93 merged
as `05eda3d`; earlier incorrect private test saves were not rewritten. This is
not final server or owner acceptance. The preview assets include the same switch.

Visual alignment follow-up, 10 September: screenshots confirmed the dense Saved
queries table, clipped actions and stray composer jump differed from the mock.
Catalyst [#94](https://github.com/DIGI-UW/catalyst-ai/pull/94) replaces these with the approved
cards and in-page category navigation, retains additional metadata in a
disclosure, and matches the measured logo/wordmark font, dimensions and spacing.
The binding design's obsolete table prescription is replaced. All 99 focused
component tests, 11 deterministic browser checks, build/type, lint and current
documentation/link checks passed. Light/dark, wide/narrow screenshots remain in
the private review bundle. The broader screen-by-screen comparison remains open.

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

Arrangement iteration, 10 September: Catalyst
[#95](https://github.com/DIGI-UW/catalyst-ai/pull/95), merged as `0109b5b`, implements
saved chart revisions, Dashboard review/reordering and full/half/third-row widths.
Reopening restores the immutable configuration; saving changes preserves the
logical Dashboard identity and Superset address. Same-source charts can span
catalog refreshes while their saved-query schema provenance stays intact.
Chart placement into an existing Dashboard retains the saved chart and selection
on failure, and retry does not create another chart version. The review panel
uses the approved mock's full height and width, and chart/Dashboard libraries
share its card treatment. The current binding design incorporates these details.

| Stage | Arrangement iteration status |
| --- | --- |
| Implementation | Catalyst #95, tested head `3876098` |
| Self-validation | 87 Gateway/public-route/canonical bundle tests; 284 UI tests across the main run and loopback-permitted fixture rerun; 12 deterministic browser checks; build/type/lint and documentation/link checks passed. Light/dark arrangement screenshots inspected privately. |
| Merge | Catalyst #95 merged as `0109b5b`; all five hosted checks passed |
| Local real-source validation | Both sources passed chart creation, arrangement save/reload/revision, repeat deterministic publication, actual import receipts and native table/bar rendering after the provenance fix. Tested harness `d136098`, Catalyst `3876098`, Hub `75d0ff0`; final merged release refresh remains separate. |
| Server deployment and demos | Pending the complete compatible release checkpoint |
| Owner acceptance | Remains open separately from implementation and tests |

The first real import rejected both reused-SQL bundles before Superset mutation:
Dataset save converted an absent question-turn ID to the string `"None"`.
The correction records `turnId: null` for manual/reused SQL with no generated
turn and retains all actual session/query/execution references. The public-route
regression fails for both source identities with the old producer and passes
with the correction; all 115 Gateway, public-route, canonical bundle and importer
tests pass. Existing immutable saves and failed receipts remain untouched. Corrected saves
and real imports now pass for both sources. Inspected Superset screenshots show
two half-width charts in the saved order; visible values match the originating
Catalyst result (OpenELIS 49; OpenMRS 3,578), without a separate database query.
Raw footage, requests, traces, exact revisions/configuration fingerprints, bundles
and receipts are archived in the private review folder. This is local iteration
proof; it does not close the full server/demo checkpoint or final owner review.

## Local/server deployment and evidence

Release verification, 10 September: harness [#129](https://github.com/pmanko/clinical-ai-validation-harness/pull/129)
merged as `4726687`, pinning Catalyst `d5c4c0d` and Hub `75d0ff0`.
At that checkpoint, the local owning checkout ran these merged revisions; the strict repository
check and full wrapper health gate passed without reseeding. The refreshed
full-scenario recording test passed for **both real sources** (2 tests, 11.3 minutes):
drafting and schema browsing, explicit execution and refinement, exact saved-SQL
reuse with draft preservation, chart/table creation, arrangement save/reload and
revision, deterministic publication, actual import receipts and native Superset
rendering. Visible table values match the originating Catalyst result. Raw videos,
screenshots, traces, requests, receipts, milestones and a revision/configuration
manifest are archived privately under run `release-4726687-local-2`.
Both settled Superset screenshots were inspected: female/male counts are
49/47 for OpenELIS and 3,578/1,806 for OpenMRS, matching the originating results.

During server staging, transferred retained-data hashes matched, the restored
OpenELIS/FHIR database passed PostgreSQL backup verification, and the old
saved-work database received a verified online backup. All 54 retained Spark
table/view definitions were restored across both source namespaces. Disk
capacity and ARM compatibility initially blocked startup; the current release
status below supersedes that staging checkpoint.

Catalyst [#96](https://github.com/DIGI-UW/catalyst-ai/pull/96), merged as `9ff0a89`,
adds the hosted Superset path/public-link repair separately from the recording
rewrite: 37 focused tests, root/prefix Compose resolution, lint and documentation
checks passed, followed by all five hosted checks. Final deployment and browser
verification remain separate.

The owner approved the recording-contract update on 10 September. Catalyst
[#97](https://github.com/DIGI-UW/catalyst-ai/pull/97), merged as `d5c4c0d`, contains the refreshed
two-source scenario, retaining the laboratory fixture assertions, repeat-publication
digest check and originating-result comparison. The recording guide now describes
the actual capture and private evidence workflow. The remaining Workbench header
and composer spacing were aligned directly with the frozen mock; saved-query
review keeps the immutable name readable and the recorded source visible.
Light/dark and narrow screenshots were inspected. Local checks passed: 284 UI tests, 52 analytics
tests, 12 deterministic browser checks, type checking, lint, production build and
documentation/link checks. The real-source recording now passes on the merged
release described above; final server proof remains separate.
All five Catalyst hosted checks passed on the final pull-request head before merge.

Import isolation: Catalyst [#99](https://github.com/DIGI-UW/catalyst-ai/pull/99),
merged as `3439c97`, removes implicit service startup from Dashboard import.
Import requires healthy services in the owning checkout with matching resolved
configuration; inherited port changes fail before import or service mutation.
All 57 analytics/assembly tests and all five hosted jobs passed. This follow-up
changes the operator script only; the UI and query code in the recorded journey
above are unchanged. Harness [#130](https://github.com/pmanko/clinical-ai-validation-harness/pull/130),
merged as `c69ee22`, pins this correction. The local owning checkout passed
the strict repository and full health checks. A real import with a conflicting
port was rejected before mutation; the correctly configured repeat import
returned `already_imported`. Service identities, start times and ports were
unchanged in both cases. Private proof: `import-isolation-3439c97`.

Recovery follow-up: Catalyst [#101](https://github.com/DIGI-UW/catalyst-ai/pull/101),
merged as `e163726`, fixes a real failure hidden in reused-SQL sessions without
question turns. The diagnostic remains visible once, with the error color,
and the SQL stays available for correction. The regression failed before the
fix; 285 UI tests, 12 deterministic browser checks, five recording-contract
tests, type/lint/build and all five hosted checks passed. Both complete real-source
journeys passed again, including native database failure/retry and successor
save (2 tests, 9.3 minutes). Private run `recovery-a3bab21-local` used the working
UI and the merged owning services; its application code matches this merge.
Both Superset screenshots and matching bundle/receipt digests were verified.
The final recording-only adjustment brings the diagnostic into the viewport
before its eight-second hold; final server recording remains separate.

The renderer now supports an 80-pixel caption band below the full 1280×720
picture. A rendered sample was inspected privately; an encoded-frame test proves
the caption remains below the picture during a hold. All 29 renderer and
documentation-check tests passed. Final edited videos have not been reviewed
or published; the sample does not close the video acceptance items below.

Current release: harness `d070fe7`, Catalyst `e163726` and Hub `75d0ff0` are
running in the local acceptance stack and on the public demo server. The local
two-source recording passed again (2 tests, 11.2 minutes), with matching bundle
and import-receipt digests archived privately as `replacement-demo-d070fe7-local`.

The server root volume was expanded from 50 to 100 GiB after a recovery snapshot;
targeted cache pruning preserved application volumes. Persistent QEMU registration
and a server-only Data Pipes entrypoint correction resolved the observed ARM
startup failures. Strict repository verification and full wrapper health passed
in the server's owning checkout. The public proxy now serves the new UI, API and
`/catalyst-dashboards/`; existing Superset routes and media were preserved. The
rendered public Workbench was inspected, and HTTPS checks passed for the UI,
source registration and Superset routes. See the
[operator guide](../../docs/catalyst-demo-operations.md) for the exact server
configuration and lifecycle entry point.

The first server capture was invalidated by a service restart during preparation
and is retained only as failure evidence. The next take reached its ten-minute
preparation wait while the UI still showed generation in progress. An unchanged
retry completed the initial OpenELIS query but did not complete the full journey.
CPU-based model preparation remains an observed responsiveness issue.

Recording direction, 10 September: the owner explicitly requested **local
recordings with a verifier**. The new capture uses the existing real-source
scenario and `catalyst-query-gemma-4-12b-qwen2.5-14b-checked`: Gemma writes and
Qwen reviews. Verify both actual role invocations in the saved evidence. The
replacement videos will identify the local environment; server journey proof
remains separate and does not block publication of the verified local cuts.

The new local run `replacement-demo-d070fe7-verified-local` passed both complete
journeys (2 tests, 9.5 minutes) on the same merged revisions. Saved generation
evidence confirms the Gemma writer and Qwen reviewer actually ran for both initial
and follow-up turns on each source. One initial writer output was marked
`validation_failed`; its reviewer completed and the session produced the selected
query. This outcome is preserved in the evidence rather than relabelled successful.
All four reviewer invocations completed successfully. Bundle and actual import
receipt digests were checked and archived with raw video, traces and model evidence.
Both cuts are approximately 3:05, with a 13-second pipeline introduction and
captions below the application image. Final review and publication are tracked
below; server workflow and owner acceptance remain separate.

Publication completed on 10 September (11 September UTC), from merged harness
[PR #132](https://github.com/pmanko/clinical-ai-validation-harness/pull/132),
`320090d`. Both final cuts were watched at normal speed. The immutable videos and
posters were uploaded and verified by HTTPS byte hashes; the separate
[OpenClinAI homepage](https://openclinai.org/#catalyst) now embeds both. Browser
inspection confirmed both 1280 × 800 players load without errors. Raw evidence,
media checksums, homepage backup and publication receipts remain private.

A public OpenMRS preparation at 05:02–05:08 UTC failed with `writer_timeout`
before any SQL execution. The new isolated stack had inherited a 360-second
Gateway timeout and the Hub's 600-second default, whereas the former demo stack
configured 1,800 seconds at both layers. Server-only settings now restore those
budgets; wrapper health passed after applying them. Slow CPU inference remains
an observed limitation. A fresh public OpenMRS browser journey subsequently
prepared and ran the query, returning 5,384 patients without a database error;
preparation took 674 seconds. Public OpenELIS also prepared and ran successfully,
returning 96 patients after 536 seconds of preparation. SQL execution took 118 ms
and 111 ms respectively. These checks verify the reported timeout repair, not
full server workflow acceptance.

The owner then requested light appearance throughout both videos. The new local
run `replacement-demo-d070fe7-light-local` passed both full journeys (2 tests,
10.9 minutes). All 665 captured application theme observations were light.
Gemma and Qwen actually ran on all four turns; both initial writer drafts were
recorded as `validation_failed` and their reviewers succeeded. All bundle/import
receipt digests match. The replacement cuts are 3:08 and 3:06; both were reviewed
at normal speed and published under new immutable light-only filenames with
verified HTTPS hashes. The homepage and demo canvas reference those same assets.
[Catalyst #102](https://github.com/DIGI-UW/catalyst-ai/pull/102) preserves light
appearance in recording mode while retaining the ordinary dark-theme test path.
Runtime application revisions are unchanged; the recorder is separately pinned.

On 11 September, the owner asked that the public OpenMRS walkthrough stop
duplicating the OpenELIS patient-count workflow. The replacement run
`openmrs-cd4-monitoring-light-local` uses aggregate 2026 CD4 counts by month,
then a gender breakdown; it displays no patient-level rows. The recorder change
merged in Catalyst [#105](https://github.com/DIGI-UW/catalyst-ai/pull/105) as
`c93a3d6`. Its local commit `373cac8` passed the complete real local path
before capture, then passed again while recording: six initial aggregate rows,
ten refined aggregate rows, the visible database-error/retry path, saved-query reuse,
widgets, arrangement, deterministic import and a native Superset table checked
cell-by-cell against the originating result. Generation evidence records the
Gemma 4 12B writer and Qwen 2.5 14B reviewer for both question turns. The
3:08 light-only cut, raw footage, trace, requests, proof, timing plan and exact
runtime revisions are archived privately under that run. It was watched at 1×;
its eight-second FHIR Data Pipes introduction is shorter than the prior cut.
The new immutable [OpenMRS video](https://catalyst.openelis-global.org/media/catalyst-openmrs-cd4-monitoring-local-light-20260911-373cac8.mp4)
and [poster](https://catalyst.openelis-global.org/media/catalyst-openmrs-cd4-monitoring-local-light-20260911-373cac8-poster.jpg)
were HTTPS hash-verified before the homepage reference changed. The prior
OpenMRS asset remains immutable evidence; OpenELIS is unchanged.

Final server-proof release candidate, 11 September: Catalyst `c93a3d6` combines
the configurable server generation window from
[#103](https://github.com/DIGI-UW/catalyst-ai/pull/103), accurate FHIR Data Pipes
Parquet and Spark warehouse provenance from
[#104](https://github.com/DIGI-UW/catalyst-ai/pull/104), and the distinct OpenMRS
CD4 workflow plus complete rendered-row verification from #105. All five
Catalyst jobs passed on #105 after its companion analytics contract was aligned;
the focused five-test contract and full 57-test analytics suite also passed
locally. This harness update pins that exact merged revision. Deployment and the
full server run remain separate evidence below.

- [X] Deploy exact merged compatible revisions locally and to
  `catalyst.openelis-global.org` using the owning checkout and harness wrapper;
  preserve retained data. Full server importer and journey proof remains below.
- [ ] Prove the full real path for OpenELIS and OpenMRS on both deployments and
  retain revisions, source/model configuration, traces, screenshots, timestamps,
  bundles, receipts, and visible-result evidence under one run identity.
- [X] Capture with the existing Playwright video project and archive raw footage
  before another run removes it.
- [X] Use the current styles in both new local demos with an actual writer and
  verifier run recorded for each source. Keep the FHIR Data Pipes
  introduction to about 10–15 seconds and focus the walkthrough on Catalyst;
  preserve detailed pipeline evidence separately.
- [X] Render short cards/captions for at least 5 seconds, longer text at about 3
  words/second plus 2 seconds, and results/details for at least 8 seconds; retain
  captions during holds and label accelerated waits.
- [X] Watch each final cut at normal speed, confirm captions neither disappear
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
