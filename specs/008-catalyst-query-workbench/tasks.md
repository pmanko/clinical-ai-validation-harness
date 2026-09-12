# Feature 008 tasks — current work only

**Status:** Functional Workbench, saved-work, and Dashboard implementation is
merged. The owner has not accepted the complete browser-visible design. The
current checkpoint is the visual-coherence remediation in the
[Feature 008 roadmap](plan.md), followed by remaining runtime/server evidence
and explicit owner acceptance. This file is the sole detailed progress and
acceptance register. Model comparison and broader conversation work remain
separately scheduled.

## Next owner checkpoint

- [X] Record the 11 September owner finding that the opening shell is more
  polished than the working multi-turn, result, disclosure, notice, Saved-work,
  and dark-mode states. Earlier functional checks and videos do not establish
  visual acceptance.
- [X] Save the research-backed remediation sequence and acceptance criteria in
  the existing Feature 008 plan and this register, without creating another
  roadmap or mock authority.
- [ ] Amend the Catalyst product specification and binding design, extend the
  existing staff Workbench mock through the complete state matrix, and obtain
  owner approval of that multi-state direction before production styling work.
- [ ] Implement and merge the shared visual/control foundation, compact
  completed-turn query summary, supporting-surface cleanup, and current visual
  baselines described below.
- [ ] Run matched light/dark and wide/narrow browser comparison plus real local
  OpenELIS and OpenMRS journeys, then record explicit owner acceptance.
- [ ] Complete cancellation, warmup, final server, and post-remediation video
  items before closing the current release. Keep broader responsiveness, model
  choice, streaming, and session URLs as the follow-on checkpoint already
  defined in the roadmap.

Local development now serves the working Catalyst UI at `localhost:13001`
against the retained local Gateway and both real sources. Local testing does
not wait for merges. Merged implementation revisions are pinned; final release
evidence and owner acceptance remain open.

## Current release integration — 11 September 2026

The owner authorized this sequence: roadmap #142, combined Catalyst #106–#109
and Hub #25–#27, router #143 with exact merged pins, local/server deployment,
then the OpenMRS replacement recording and publication in #141. This checkpoint
supersedes earlier unmerged-status notes below. Harness #134 and the independent
Superset remediation in harness #111 remain separate.

| Deliverable | Implementation and merge | Validation | Deployment / acceptance |
| --- | --- | --- | --- |
| Roadmap #142 | Merged as `6d7a327` | All PR checks passed | Authoritative plan updated |
| Catalyst #106–#112 | #106–#109 merged as `f2a46b0`; the current harness pin is `18bd9ef2` after the recording correction and finite schema-warmup changes | Earlier combined tree: 364 Gateway tests passed, one existing skip; 294 UI tests; 16 deterministic browser checks, eight live-only skips; type/lint/build passed; later focused validation is recorded below | `18bd9ef2` and its warmup are running locally; the server still runs the earlier application pin; full workflow acceptance remains open |
| Hub #25–#28 | Merged; current pin `1ddaa1e51ebb88735808ae9775ec046ba0b3101b` | #25–#27 combined suite: 720 tests passed; #28: 71 focused tests and CI passed | Running locally and on the server; local OpenMRS query-grain check passed |
| Router #143 and release follow-up #144 | Merged as `a6980ce` and `b6fe09a` | Release CI passed; five router tests and 18 focused router/documentation/repository checks passed | Server router repair deployed at `735ad53`; persistent local source continuity verified; cold-query and full server workflow acceptance remain open |
| Replacement OpenMRS walkthrough / #141 | Corrected local take 8 passed on runtime `b6fe09a`; recorder fix #110 merged as `1fd4a03` | Full real-model browser test passed: monthly totals preserved, saved SQL reused, two visualizations arranged, repeat publication/import and rendered Superset checked | Merged as `dfee0e2`; both videos and posters published and verified over HTTPS; owner acceptance separate |

The combined review reproduced a conflict between #106's metadata-only repair
and #109's duplicate alias-repair regression. Both tests are retained. Named,
complete projections now repair declared output names; unnamed expressions or
a different projection count may still request SQL repair. This does not rewrite
user-selected SQL. The repaired engine tests pass together.

The initial `b6fe09a` release ran locally and on the demo server; both wrapper
health checks and the public two-source discovery endpoint passed. The server
used the maintained router with one resident model and its original 12B default;
the legacy router is stopped and retained for rollback. Full server workflow and
latency acceptance remain open.

The first server timing probe used `a6980ce` and the exact question “How many
patients are there?” for both sources with each writer-only profile. All four
requests ended with `generation_timeout`: OpenELIS/12B 120.134 s,
OpenMRS/12B 120.167 s, OpenELIS/E4B 120.202 s, and OpenMRS/E4B
120.136 s. Router logs show E4B still processing its roughly 11,000-token prompt
at 271.74 s (9,477 tokens processed), after the caller timed out. Its process
used about 15 CPU cores. These are failed sequential requests, not valid warm
latency measurements: abandoned model work interfered with subsequent requests.
The pinned inference build is llama.cpp `12127def` (`b10015`). Its proxy cleanup
closes the local pipe without stopping the downstream HTTP client; this is a
concrete cancellation gap to reproduce independently before a fix. Do not claim
that releasing the Hub lock proves release of the actual model slot. Keep the
public default unchanged; no extra hardware or inference subsystem is approved
by these observations. Raw timing responses and logs remain private review
artifacts, not checked-in media.

The exact-release local OpenMRS take was rejected: a direct join to `patient_flat`
doubled all six monthly totals, including January 200 to 400. That source view
expands names and identifiers, so patient ID is not unique. The recording checks
are unchanged. Hub #28 adds writer/reviewer guidance to preserve fact grain,
retain unmatched facts when missing categories are requested, and avoid arbitrary
conflict resolution. Its 71 focused tests and CI pass; this release follow-up pins
the merged repair. The next exact-release take passed in 5.9 minutes. The model used a left join
and distinct observation IDs; all six monthly totals were preserved. The real
Gemma 12B writer and Qwen 14B reviewer completed both preparations, followed by
saved-SQL reuse, table/chart arrangement, repeat publication, import and rendered
Superset verification. This proves the recorded scenario, not all joins. Final
video review and publication remain open.

The initial passing take was rejected in visual review because its bar chart
collapsed the month dimension. Catalyst #110 selects the existing recommended
monthly line chart and asserts month, gender, and count bindings. It changes
only the recording test; all clinical-total and publication assertions remain.
Take 6 failed model review and is retained privately as a reliability finding.
Take 7 exposed a recording-checkout/import-owner mismatch. After restoring the
runtime's exact pins and separating the recorder checkout, take 8 passed the
complete real-model browser workflow in 5.6 minutes, including Superset rendering.
The final edited replacement is 3:06. Full normal-speed local playback review
passed: light appearance, readable captions, labeled accelerated waits, no manual
SQL editing, and the monthly line chart beside its matching table. Both final
MP4s and posters were published under immutable names. PR #141 merged as
`dfee0e2`; the landing-only publication matches that exact merged source over
HTTPS (page SHA-256 `3f43dd488ca4050d7aa9edde6f86626174fff534a93f7a3852779fde94f8b74b`).
OpenMRS SHA-256 starts `6fa6917`; the previously reviewed OpenELIS cut
starts `abaf54f` and runs 3:04, with one brief supplied-SQL repair. The OpenELIS
cut predates the current release and is not current-release server evidence.
Raw footage, traces, and rejected takes remain private.

The owner reaffirmed that all recording and video verification are local.
Server work is deployment and query validation: a smaller model, warmup, and a
lightweight selectable alternative. The installed fast candidate is Gemma E4B;
A4B is a different model. No GPU was provisioned and the GPU proposal is withdrawn.
The base approach targets low-resource, non-GPU environments. Model loading and
repeated-query warmup must be measured separately; a loaded model alone does not
prove acceptable query latency. Success on the existing 16-core server alone is
not proof of low-resource suitability.

Server rollout found that the pinned router rejects `POST /models/load` for an
already-running model. The warm/smoke wrapper now checks actual loaded state
first and succeeds without another load request. The regression reproduced the
HTTP 400 before the fix; five router tests cover already-loaded and cold-load
paths. Candidate E4B inference returned a real response; this smoke alone does
not establish query quality or acceptable interactive latency.

### CPU server and local restoration follow-up

The installed Gemma E4B model was warmed after confirming the shared task was
inactive, the recording had exited, and the server model slot was idle. All new
performance probes prepare SQL without retrieving clinical rows and retain only
operating metadata. The first OpenELIS preparation hit the 120-second deadline;
router timing showed 373.342 seconds processing 11,278 prompt tokens and 7.103
seconds generating 102 tokens. The next same-question preparation succeeded in
50.8 seconds. Its reviewed SQL counted distinct patient IDs; execution through
Catalyst returned 96 in 924 ms. This establishes a useful warm-query improvement,
not the proposed 30-second target or general query reliability. The first
OpenMRS preparation timed out at 120.071 seconds; its repeat succeeded in 33.069
seconds. Reviewed distinct-patient-count SQL executed through Catalyst and
returned 5,384 in 193 ms. Both probes finished before the server was updated to
`dfee0e2` with the owner-selected E4B default and E4B model warmup. The strict
repository-pin check and full server health gate passed. Differently worded
questions after switching datasets also timed out at 120 seconds for both
sources. Model loading and repeated-query caching do not yet establish general
responsiveness; cold-start and abandoned-work findings remain open.

Local recovery is complete at merged harness `cada140` (PR #145), with the
same Catalyst and Hub application pins. Runtime ownership is now a persistent
checkout; OpenELIS/HAPI use a project-scoped Docker volume. The approved fixture
rebuild restored 96 patients and 1,152 results through the real export and
analytics pipeline. A full harness restart without seeding passed every health
gate, with identical patient/result fingerprints before and after. Both Spark
sources remain readable: OpenELIS 96 patients; OpenMRS 5,384. Recovery receipts
remain private, outside Git. Server storage was not changed by this recovery.

### Downstream cancellation repair

The unchanged inference build reproduced continued generation after client
disconnect. Two concrete causes were isolated: proxy cleanup did not stop the
child HTTP request, and unrelated response-queue notifications repeatedly reset
its wait timeout. The merged repair fixes both against the exact deployed upstream
source. The short-prompt measurements below are operating observations, not
performance or product acceptance criteria.

Local CPU checks exercised cancellation and an ordinary response using the
cached E4B model. The local file differs from the server-pinned model revision.
They are diagnostic observations, not server acceptance or a product
responsiveness target. Image build provenance and raw results remain private,
outside Git.

- [X] Merge the reviewed CPU image patch, build/selection support, bounded batch
  preset and cancellation probe: PR #147 merged as `735ad53`. All CI checks
  passed, along with 17 focused local tests and the real CPU checks above.
- [X] Deploy the exact verified image through the existing router lifecycle and
  check cancellation plus ordinary generation on the CPU demo server. Harness
  `735ad53` runs the tested ARM64 CPU image (ID starts `b06299c`). Cancellation,
  ordinary inference, and full application health were checked. Small synthetic
  checks do not establish behavior under a real source schema, so no numeric
  cancellation target is accepted. Image/archive checksums and rollback
  configuration are retained privately. The application-level deadline and full
  workflow remain separate checks below.
- [ ] Resolve remaining long-running first-query and varied cross-source failures;
  complete the real saved-work through Superset journey for both sources before
  closing server acceptance. Videos are already published and remain local work.

## Parallel runtime checkpoint — neutral-question warmup

- [X] Implement a finite warmup through the existing lifecycle wrapper using
  “What information is available in this data source?” with each configured
  source's complete schema and ordinary writer profile. Discard the exchange;
  create no sessions, previews, saved examples, guidance, generated SQL, or
  clinical-row retrieval. Use only live schema metadata discovery.
- [X] Verify the safe local path with a different real question on each source.
  At the exact merged harness main, OpenELIS and OpenMRS warmup completed through
  the wrapper, and each subsequent ordinary draft reached ready with the selected
  `catalyst-query-e4b-qwen14b` profile (`gemma-e4b` writer and `qwen2.5-14b`
  reviewer), generated SQL present, no execution, and no warmup question in
  session history. The retained catalog identities start
  `live+schema.ddea0ff38989b137` and `live+schema.32eb5cbc4c336643`.
- [ ] Measure actual prefix/cache reuse and check source switching, cache misses,
  failures, and explicit Stop. The safe local path above is not a cache-hit or
  responsiveness measurement; model-loaded health alone remains insufficient.
- [X] Merge the tested changes and pin the exact compatible Catalyst revision.
  [Catalyst #111](https://github.com/DIGI-UW/catalyst-ai/pull/111) merged as
  `c0a1b431`; [Catalyst #112](https://github.com/DIGI-UW/catalyst-ai/pull/112)
  merged as `18bd9ef2`. The harness pins #112; it is not deployed yet.
- [ ] Deploy through the lifecycle wrapper to the existing CPU server, preserve
  retained data, and verify preparation and execution against both sources.
- [ ] Present the observed workflow and remaining limitations for owner review.
  No numeric responsiveness or cancellation threshold is approved; timings are
  diagnostic evidence. Videos remain locally recorded work.

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

## Earlier owner gate — functional continuation, visual acceptance open

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
- [ ] Superseded by the full visual-coherence checkpoint below. Composer/Run
  spacing, heading weights, font presentation, Catalyst mark, and the corrected
  follow-up border remain required, but no longer describe the whole gap.

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

Owner feedback on 10 September 2026 allowed saved-work and Dashboard
functionality to continue while retaining padding and type follow-up. The
broader 11 September review found that the later product states still lack a
coherent visual hierarchy. This earlier gate therefore proves functional
continuation and real-source exercise only. It does not close Workbench visual,
server, Superset, or final owner acceptance.

The live walkthrough exposed an incorrect execution URL in two browser-test
observers. Catalyst [#89](https://github.com/DIGI-UW/catalyst-ai/pull/89), merged as
`4d9c1e9`, corrects those observers and proves an explicit Run is counted in the
existing query-to-Dashboard test. Four focused browser checks, type checking and
lint passed, as did all five hosted jobs. It changes tests only; this harness
pins that merged revision while preserving the exact application revision of
the recorded local proof above.

## Current remediation — Workbench visual coherence

The current Catalyst pin already uses Carbon theme variables throughout the
Workbench CSS. The older hard-coded-color migration plan is historical and is
not revived. The remaining work is to reconcile the binding design and compose
the existing tokens and components consistently across real product states.
The details below are proposed acceptance for the Catalyst-owned amendment;
they become the application contract only after the product specification and
binding design are updated and reviewed.

### Iteration 1 — binding design and existing mock

- [ ] Amend Catalyst's product specification so a completed turn always shows
  the question, plain outcome, source, returned-row count or limit, relevant
  warning, and a compact query/execution summary; keep the full result table in
  Dataset review.
- [ ] Reconcile the binding design's conflicting square-turn, rounded-card, and
  result-ownership rules. Define one surface, radius, spacing, type, shadow,
  icon, and semantic-status role map for the whole Workbench and Saved work.
- [ ] Extend the existing staff Workbench mock in place. Do not create another
  mock or copy of the application. Cover first question, preparation/Stop,
  prepared query, successful multi-turn execution, clarification, empty and
  limited results, stale state, preparation and database failure/retry, query
  details closed/open, Advanced SQL preview, Available data while drafting,
  saved-query reuse, review panels, Dashboard arrangement, and publish/import
  success and failure.
- [ ] Show the applicable mock states in light/dark and desktop, short,
  640-, 390-, and 320-CSS-pixel layouts. Verify that its disclosure markers and
  controls express the proposed production treatment rather than retaining the
  mock's own browser-default carets.
- [ ] Record owner approval of the multi-state mock and binding amendment before
  implementation. Approval of the prior first-screen mock does not satisfy this
  item.

### Iteration 2 — shared visual and control foundation

- [ ] Use existing React, Carbon, CodeMirror, Catalyst theme variables, and
  current state owners. Add no UI framework, icon library, token system, theme
  service, global store, SQL engine, or dependency upgrade without a concrete
  missing capability.
- [ ] Implement shared labeled disclosure/menu controls with Carbon icons and
  consistent target size, focus, hover, expanded, disabled, and dark states.
  Remove user-visible native markers and literal `▸`/`▾` glyphs from the
  Workbench while preserving Enter, Space, Escape, `aria-expanded`, controlled
  region, and focus-return behavior.
- [ ] Apply the binding role map to page, surface, raised surface, border, text,
  muted text, action, focus, warning, error, success, spacing, radius, type, and
  shadow. Status remains labeled or icon-supported and never depends on color.
- [ ] Keep ordinary text neutral in light and dark. Reserve violet for the mark,
  action, selection, and focus; keep gold as the small brand detail. Preserve
  warning, error, and success meaning rather than recoloring them as branding.

### Iteration 3 — transcript and compact query evidence

- [ ] Replace the nested square-card treatment with one readable transcript
  hierarchy. The question, outcome, source, limitations, and next action remain
  visible when query details are closed.
- [ ] Build the compact summary from facts already recorded for the turn:
  instruction, source label, execution status, returned rows or limit, returned
  column labels, and safe supplied schema labels. If the revised mock needs
  source relations, filters, grouping, ordering, or date range, add one typed
  server-owned projection through the existing SQL parser and store it with the
  turn. Omit unknown facts. Do not parse SQL in the UI, add another model call or
  SQL parser, invent clinical meaning, or state that SQL captured intent.
- [ ] In Standard mode, expose one **View query details** action. In Advanced
  mode, also allow a one- or two-line formatted SQL preview. The same expansion
  shows complete selectable SQL, typed parameters, execution facts, warnings,
  and provenance without a second disclosure layer.
- [ ] Preserve chronological turns, current/earlier distinction, AI-review
  evidence, selected query, exact SQL, current editor ownership, stale result,
  retry, and access to every retained earlier result.
- [ ] Cover success, warning, empty, stale, clarification, unsupported,
  preparation failure, database failure, running, and cancelled states. A
  several-turn session must be distinguishable at a glance without sparse
  one-line headers or a full table in each turn.

### Iteration 4 — supporting surfaces and plain language

- [ ] Carry the same hierarchy and controls through the resizable composer,
  View options, Query settings, model selection when exposed, Available data,
  Saved work, review panels, Dashboard arrangement, and publication states.
  Preserve the approved Explore / Saved work navigation and existing
  saved-object identities.
- [ ] Replace the composer's heavy top accent and ordinary-progress warning box
  with the approved writing surface and persistent neutral status treatment.
  Show plain stages and recovery actions; keep raw model/profile IDs, attempts,
  tokens, traces, and internal status codes in Advanced or technical details.
- [ ] Keep the current workspace-wide Advanced toggle as a secondary setting,
  rather than a primary action. Entering or leaving it preserves session,
  source, draft, selection, editor, parameters, expanded state, results,
  selected saved work, theme, browse state, and focus.
- [ ] Preserve the implemented composer resize/Expand/Restore behavior and
  nonmodal complete-schema browser. Opening, searching, closing, retrying, and
  changing source never fetches result rows or discards the question.
- [ ] Match the approved logo and wordmark proportions, type hierarchy, padding,
  and icon treatment throughout the working screens, not only the first layer.

### Iteration 5 — deterministic visual matrix and owner acceptance

- [ ] Replace the stale rail-era visual test with named deterministic captures
  for the current header, first question, multi-turn history, compact and
  expanded query summary, composer, Available data, result review, Saved work,
  Dashboard review/arrangement, and publication states.
- [ ] Capture the agreed state matrix in light and dark at desktop,
  short-viewport, 640-, 390-, and 320-CSS-pixel layouts. Limit snapshots to
  representative combinations while ensuring every component and state appears
  at least once; do not create a Cartesian test matrix.
- [ ] Verify normal text contrast of at least 4.5:1 and large text of at least
  3:1, multiline body line height of at least 1.5, readable line length,
  keyboard order, visible focus, reduced motion, disclosure semantics, Escape
  and focus return, long SQL, long questions, warnings, and overflowing labels.
- [ ] Prove theme, Advanced mode, resizing, browsing, retry, disclosure, session
  switching, and navigation preserve the current draft and product state.
- [ ] Run focused component/accessibility tests, UI type checking, lint, build,
  and deterministic browser checks. Each PR records exactly which checks ran;
  live-model and Spark proof remains at the integration gate.
- [ ] Deploy exact compatible revisions locally through the harness wrapper and
  run real OpenELIS and OpenMRS journeys through question, multi-turn summary,
  query details, Run, result review, saved-query reuse, visualization,
  Dashboard arrangement, and publication.
- [ ] Present the approved mock and working product side by side, including dark
  and narrow states, and record explicit owner acceptance. Implementation,
  merge, local deployment, self-validation, feedback, and acceptance remain
  separate facts.

### Remediation release boundary

- [ ] Merge the Catalyst design/specification change before the styling PRs;
  merge each small implementation iteration only after its focused acceptance
  evidence passes.
- [ ] Pin only merged, compatible Catalyst revisions in the harness and update
  the existing public mock assets together when the approved mock changes. A
  Catalyst gitlink change alone does not update the public preview.
- [ ] Complete the current cancellation, warmup, and server gates before final
  release evidence. Keep broader responsiveness, model choice, streaming, and
  session URLs in the roadmap's follow-on checkpoint. Visual polish does not
  establish model performance, and performance evidence does not establish
  visual acceptance.
- [ ] Re-record final light-mode walkthroughs only after the remediated product
  and current server gates pass. Keep FHIR Data Pipes brief, use actual
  writer/reviewer evidence, preserve normal reading pace, and review each final
  cut at normal speed before replacing public references.

## Dashboard functionality — saved work

- [X] Save only a successful current execution; preserve exact SQL, typed values,
  source, dialect, schema, query, and execution identity in immutable versions.
- [X] Restore saved Dataset versions and protect against stale or mismatched
  results.
- [X] Browse Saved queries, Charts and tables, and Dashboards within Saved work;
  show source, saved version, dependencies and available review/reuse actions.
  Returning to Explore preserves the ongoing draft and selected work.
- [X] Start from this SQL loads the exact saved parameterized SQL and typed
  values into the one editor, retaining the Dataset version and source/dialect.
  Preserve an existing draft; a different source requires an explicit new or
  matching session. Loading never runs SQL or modifies saved versions.
- [X] Keep saved SQL/parameters accessible when historical execution details
  are unavailable; label that evidence separately. Verify reuse, explicit Run,
  failure/retry and a successful successor save for both real sources.
- [X] Finish deterministic visualization compatibility and allow a person to
  review, select, and save supported Widget versions.
- [ ] Reverify these merged behaviors on the exact remediated release and record
  server evidence and owner acceptance in the shared release section below.

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

- [X] Arrange and restore multiple same-source Widgets without losing accepted
  layout behavior.
- [X] Generate deterministic native Superset bundles and expose publication
  status only from actual importer receipts.
- [X] Keep import failures actionable and open the stable Superset URL only
  after successful import.
- [X] Inspect one rendered value against the originating Catalyst result without
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

The 11 September owner review found misleading “unreviewed” badges and
formatting-only “human” versions despite recorded reviewer approvals. Public
recapture must fix both and focus on model-created SQL and plain-language
refinement. Include only one brief model repair of supplied broken SQL across
the two videos; retain deliberate engine-error/retry coverage separately.

- [X] Correct review recognition and formatting provenance, with regression tests
  ([Catalyst #106](https://github.com/DIGI-UW/catalyst-ai/pull/106)); local
  implementation and CI pass, merge and final footage acceptance remain open.
- [ ] Recapture both light-mode stories with actual reviewer decisions, one brief
  supplied-SQL repair, matching Superset results and no staged manual fixes.
- [ ] Review the new cuts at normal speed and replace public video/poster links.

Recording validation, 11 September: OpenELIS passed the real writer/reviewer,
saved-work and rendered Superset path. Its 3:04 light cut includes one 26-second
supplied-query repair and passed normal-speed review. OpenMRS recapture remains
open: one take multiplied monthly totals; the next failed because generated SQL
and declared output names disagreed. Both were rejected. The recorder checks
unchanged totals. Gateway fixes preserve model authorship across formatter-only
changes and constrain projection-metadata repairs to output names, never SQL
([Catalyst #106](https://github.com/DIGI-UW/catalyst-ai/pull/106), all five CI
jobs and 56 focused checks pass). Local redeployment, successful OpenMRS
recapture and media-host access remain pending. These scenario checks do not
establish general clinical correctness.

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
- [X] Preserve the failed 11 September exact-release server run as evidence. The
  initial OpenELIS question became ready after about 10 minutes and three model
  calls; its SQL ran in 165 milliseconds. Recovered follow-up evidence records
  one Hub invocation with `writer_timeout` after 1,800,003 milliseconds. Later
  router activity is not reliably attributable to that turn; the earlier
  follow-up-retry attribution is withdrawn. OpenMRS did not run.
- [ ] Correct or explicitly disposition the incomplete follow-up response and
  cancellation defect before another full run. A client timeout or explicit
  cancel must stop the active downstream call and prevent later repair attempts;
  the typed draft and prior result remain available.
- [ ] Remove the automatic total generation deadline; retain explicit Stop and
  request-loss handling on the actual Gateway-to-Hub named-role path.
  Cancellation releases the busy session, records a terminal outcome, and closes
  the active model call. Test disconnect and Stop at each boundary, no later
  repair, preserved draft/result, and useful handling of incomplete responses.
  The original implementation, including the now-withdrawn deadline, is in
  [Catalyst #107](https://github.com/DIGI-UW/catalyst-ai/pull/107)
  (`fa3c38c`) and [Hub #25](https://github.com/pmanko/med-agent-hub/pull/25)
  (`8942322`), both submitted for review. Local checks: Gateway 357 passed / one
  existing skip; assembly/contracts 47 passed; Hub 720 passed, including two
  real loopback HTTP cancellation tests against a blocking fixture endpoint.
  New route/role interruption tests failed before the fixes. Formatting/lint
  passed. Gateway mypy retains the same ten findings verified on its clean base.
  Catalyst also includes **Stop preparing** in both composers, retained text and
  focus, Retry, and abort on unmount. A writer request for clarification or an
  unsupported question now produces a neutral next step rather than a red
  composer error; the question remains in the focused input, while genuine
  generation failures remain errors. UI suite: 290 passed, followed by 113
  focused tests after the final notice layout adjustment; four light/dark
  browser cases prove HTTP disconnect, no duplicate submission, preserved input
  and the previous rendered result using a real stalled local HTTP fixture.
  The browser checks caught and verified a cancel-click resubmission defect that
  component tests missed. Desktop/narrow screenshots were inspected privately;
  type check, lint and build passed. CI is green on both exact heads. Merge,
  paired deployment, and live-model/server
  verification remain pending; these checks do not establish model throughput.
- [ ] Move the stable complete schema/instructions before changing question and
  revision context in the rendered prompt. Verify full-schema/context coverage
  and measure reused prompt work for real follow-ups, repairs, and source changes.
  [Catalyst #108](https://github.com/DIGI-UW/catalyst-ai/pull/108) (`ecd949f`)
  contains the prompt-order repair with green CI. Its prefix regression failed
  before the change; 22 focused tests pass and verify complete schema retention,
  changed schema, and stable initial-to-follow-up request prefixes. Actual model
  cache reuse, timings on both sources, merge, and deployment remain pending.
- [X] Recover the follow-up's stored outcome: one timed-out Hub invocation, no
  returned model validation findings. Separate queueing from generation before
  attributing other router tasks to this turn.
- [ ] Fix the initial question's reproduced projection/ambiguous-patch cycle
  without weakening its checks. Verify useful
  count and follow-up results plus varied cases; preserve selected SQL and record
  any unambiguous parser-derived metadata correction. The retained server
  evidence identifies the full chain: the first model call returned an
  unaliased `COUNT(*)` while declaring the output name `count`; deterministic
  validation reported the projection mismatch; the second model call returned
  the same valid alias replacement twice; and Catalyst rejected those identical
  operations as overlapping edits, forcing a third model call. The narrow
  repairs are [Catalyst #109](https://github.com/DIGI-UW/catalyst-ai/pull/109)
  (`7b934be`), which collapses only exact duplicate operations while preserving
  rejection of conflicting edits, and
  [Hub #26](https://github.com/pmanko/med-agent-hub/pull/26) (`6ea4612`), which
  requires explicit aliases for aggregate/calculated projections matching
  `expectedColumns`. The exact engine regression now reaches ready in two model
  calls instead of three; the conflicting-edit control still fails closed.
  Complete local checks: Gateway 345 passed / one existing skip with Ruff
  format and lint; Hub 708 passed, plus the focused 44-test prompt/generic-role
  check. Merge, paired deployment, varied live questions and real timing remain
  pending.
- [ ] Review the proposed timing targets in the plan, then run a short real
  dual-source server check before repeating the full journey. Record usable-query
  timings, cancellation, cold/warm behavior, and two-session contention. If the
  repaired runtime is still too slow, make the measured model/hardware decision
  described in the plan rather than increasing waits or declaring success.
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
Responsiveness and session navigation are first; follow-on A/B/C retain their
existing order after it. Detailed contracts and vendor choices require review
when each starts; they are not additional completion gates for the current goal.

### Responsiveness and URL-addressable sessions

- [ ] Record one cold and repeated baseline for a simple initial question and a
  follow-up on both public sources: first honest status, first model output when
  available, usable-query time, tokens, prefix reuse, model calls/repairs,
  cancellation, and CPU/memory use.
- [ ] Serve and advertise a writer-only Gemma E4B Catalyst query profile alongside
  the standard 12B profile. Give both plain outcome-based labels, keep exact
  identities in Technical details, fail visibly when the selected profile is
  unavailable, and never fall back silently. Do not call the existing
  E4B-plus-Qwen-14B reviewed profile the fast path. The profile contract is in
  [Hub #27](https://github.com/pmanko/med-agent-hub/pull/27) (`b284ef4`): one
  `gemma-e4b` writer, no reviewer, **Faster question preparation** and
  **Standard question preparation** labels, exact model metadata, and an
  explicit unavailable reason when the router does not advertise E4B. The
  regression failed before configuration; 48 focused and 708 full Hub tests
  pass. Live inspection of both the public and isolated Hubs on 11 September
  found only `gemma-4-12b-q4` advertised, and the router model directory contains
  only the 12B artifact. The selected deployment artifact is Unsloth's
  [`gemma-4-E4B-it-Q4_K_M.gguf`](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/blob/eed1c5c07e1d365ec8769e33b396bdfce2f5f0a0/gemma-4-E4B-it-Q4_K_M.gguf)
  at revision `eed1c5c07e1d365ec8769e33b396bdfce2f5f0a0`, about 5 GB, with
  SHA-256 `e1bc442709fe780aa4b2ec9b22c16a7fcdff542f17f01ed0e3203114d28f9f34`.
  It is a quantization of Google's Apache-2.0 Gemma 4 E4B instruction model and
  matches the filename and quantization previously exercised through the harness.
  The server had 31 GB of disk free on 11 September, but no matching local file
  to reuse. Its fixed 12B router used 14.8 GiB of the host's 30.75 GiB RAM while
  the public and isolated stacks left 6.1 GiB available. Run the comparison
  serially and configure this host for one resident model, prewarming the
  selected/default model. Residency remains an operator setting: GPU-backed or
  higher-memory deployments may retain more models after capacity validation.
  Changing to a nonresident profile may require a visible cold load; the chooser
  must report actual state and never silently route to another model. Use measured
  cold, repeated, memory and concurrency behavior to set residency and warmup for
  each deployment. Live inspection also found that the shared public router is an
  orphan from an older Catalyst Compose definition: its Docker labels still name
  `docker-compose.demo.yml`, while the current file intentionally treats the
  router as external and no longer declares that service. The server has no host
  `llama-server` binary. Before a clean deployment, give the external router an
  explicit harness/deployment lifecycle with a pinned image, verified model files,
  configurable residency, selected-model warmup, health checks, and stable
  `model-router` reachability from both Catalyst networks. Remove the orphan only
  after that replacement passes direct Hub inference. The implementation is
  reviewable in [harness PR #143](https://github.com/pmanko/clinical-ai-validation-harness/pull/143)
  at `b1b7c56`; its default one-model cap is deployment-configurable so GPU and
  higher-memory hosts can use a separately validated capacity. Merge,
  checksum-verified installation, router replacement, deployment and direct E4B
  inference remain pending; the new profile does not change the default.
- [ ] Compare E4B and 12B on the same bounded dual-source Catalyst SQL cases.
  Record speed and observed query behavior; treat the published OpenClinAI
  E4B/A4B chart-answer results as candidate evidence rather than SQL proof, and
  review this direct evidence before changing the public default. The published
  [35-turn temporal comparison](https://reports.openclinai.org/temporal-ablation-7arm-2026-06-06/)
  recorded 11,557 ms average / 54,212 ms maximum for E4B and 28,456 ms average /
  248,720 ms maximum for the 12B baseline. Those chart-answer measurements select
  a candidate; they do not predict Catalyst's complete-schema SQL workload.
- [ ] Stabilize the reusable instruction/schema prefix and test the runtime's
  supported prompt cache using the neutral-question warmup checkpoint above. Prove the
  model is not merely loading, warm requests reduce prompt-processing work, a
  cache miss stays correct, and no warm-up executes SQL, reads result rows, or
  runs as a permanent background loop.
- [ ] Carry real Gateway query-engine and Hub named-role progress through to a
  persistent Workbench status region; the separate chat-completions stream is not
  the current Catalyst path. Use plain stages and expose partial
  user-facing text only when it is distinct from incomplete structured JSON or
  unvalidated SQL.
- [ ] Preserve the draft and prior result through disconnect, timeout, cancel,
  retry, and final failure. Prove cancellation stops the downstream model call
  and any later repair attempt.
- [ ] Replace the current standalone technical selectors/notices with the approved
  Workbench components: one quiet disclosure for infrequent model/view controls,
  radio choices where only two options exist, and an accessible long-running
  status treatment without fake progress or warning styling.
- [ ] Put the active session identifier in the query string. Direct open, reload,
  recent-session selection, and Back/Forward restore the exact source-bound
  session; a conflicting source parameter is normalized to the session source.
- [ ] Prove two tabs with different session URLs keep independent drafts, results,
  and generation status. Different sessions run or visibly queue according to
  measured capacity; same-session concurrent generation remains an explicit
  conflict, and leaving a view does not create unowned work.
- [ ] Pass focused Hub/Gateway streaming and cancellation tests, UI state and
  accessibility tests, session-URL/browser-history tests, matched light/dark and
  narrow screenshots, and a real dual-source server check. Record revisions,
  timings, limitations, deployment, and owner acceptance separately.

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

## Legacy checklist disposition

The sections below repeat pre-consolidation work. This table assigns each
responsibility to its current authority; the retained detail is traceability
only and does not define current order or status.

| Former section | Current owner and retained requirement |
| --- | --- |
| Before product code | Authority review is required by the roadmap's design iteration and the current remediation owner gate above. |
| Phase 1 generic connection | Product behavior remains in Catalyst's product specification; integration acceptance remains in [spec.md](spec.md#connection-and-source-acceptance); merged implementation evidence remains in **Stable Harness/Catalyst/Hub baseline** above. |
| Phase 1 Spark reference sources | Live materialization, Catalyst/Superset connection, write refusal, native error, and Dataset-to-Superset proof remain in [spec.md](spec.md#connection-and-source-acceptance) and **Local/server deployment and evidence** above. |
| Phase 1 reader-led harness and references | Evaluation method, reference authorship, complete reader packets, and the no-automatic-score boundary remain in the [program roadmap](../catalyst-program-roadmap.md); they are separately scheduled and are not current delivery tasks. |
| Model comparison | Team runs, reader review, publication, and owner review remain in the [program roadmap](../catalyst-program-roadmap.md#phase-1-completion). |
| Broader conversation scope | Definition after comparison review remains in the [program roadmap](../catalyst-program-roadmap.md#program-outcomes). |
| Phase 3 Dashboard Builder | Current implementation, live proof, visual comparison, and owner acceptance remain in **Dashboard functionality — saved work**, **Dashboard functionality — arrangement and publication**, **Current remediation — Workbench visual coherence**, and **Local/server deployment and evidence** above. |
| Guardrails | Current complexity limits remain in [plan.md](plan.md#implementation-rule) and [spec.md](spec.md#out-of-scope). |

## Retained legacy detail — superseded by the dispositions above

<details>
<summary>Show superseded pre-consolidation detail</summary>

This block is preserved for requirement-level traceability. It is not a second
current sequence or checklist; update the current sections and named authority
documents above.

### Before product code

- Review the current program roadmap, implementation plan, product
  specification, tasks, and binding Dashboard design with the owner.

### Phase 1 — generic Catalyst connection

- Replace the required analytics address and generated-catalog configuration
  with source ID, label, connection configuration or reference, explicit dialect,
  and optional non-filtering descriptions.
- Make source availability independent so one unavailable source does not
  prevent application startup or use of another source.
- Limit shared connection behavior to availability, complete readable schema
  discovery, exact SQL execution with typed parameters and bounds, and rows or
  the database error.
- Route generated and manually edited queries through the same shared
  connection-execution code.
- Supply the same source, dialect, and readable-schema snapshot to the model,
  Available data, editor, validation, and recorded execution.
- Preserve database-native relation and column identifiers and the active
  engine's qualification rules; remove the PostgreSQL-shaped name restriction.
- Make editor highlighting, formatting, and keyword/function completion use
  the declared dialect.
- Keep validation advisory and prove that a warning cannot block exact
  selected SQL.
- Add focused tests with arbitrary fixture relation names, successful
  execution, database failure, and an unavailable source. Do not assert a
  relation count.

**Pause:** Review the connection behavior and focused proof before changing a
reference deployment.

### Phase 1 — Spark reference sources

For each source actually included in the demonstration or comparison:

- Enable the pinned FHIR Data Pipes Parquet path and materialize applicable
  ViewDefinitions against retained demo data.
- Run one manual Spark query to prove materialization and one known fact.
- Connect Spark through the generic Catalyst connection and prove Catalyst
  discovers the same readable tables.
- Connect Superset to the same Spark source.
- Prove one successful browser query, one database error, and one saved
  Dataset-to-Superset render.
- Submit one intentional write attempt through the Spark connection, show
  its visible refusal, and confirm source data is unchanged.
- Remove the separate clinical analytics store, generated catalog, copied
  marts, sink scripts, preferred-engine wiring, fallback, and dedicated tests.
- Carry forward only descriptions or relationships demonstrated to help the
  accepted readable schema.
- Remove the standalone `catalyst-agents` and `catalyst-mcp` packages and
  their development wiring; the active Gateway/med-agent-hub path owns model
  execution.

The manual Spark query is only a one-time connection/materialization check. Do
not create a per-scenario or per-run Spark comparison path.

**Pause:** Review the live Catalyst and Superset smoke before merge.

### Phase 1 — reader-led harness and scenario references

- Pin the accepted Catalyst revision.
- Confirm the OpenMRS source used by the comparison does not mix another
  source's readable schema.
- If scenario design reveals a concrete missing semantic need, pause for
  owner review before adding one minimal source-owned view.
- Remove direct analytics-database access, separate read-only and “gold”
  execution, automatic result matching, their options/events, and dedicated
  tests. Do not translate them to Spark.
- After the accepted readable schema exists, author and run each ready-turn
  reference once through Catalyst and store its expected facts.
- Review clarification and unsupported expected responses without SQL,
  including whether each data-availability question is answerable.
- Make each ready model turn execute selected SQL once through Catalyst;
  clarification and unsupported turns execute none.
- Present the conversation, actual model context, SQL, rows or error, static
  reference or expected response, rubric, and recorded configuration without an
  automatic verdict.
- Add focused tests for the simplified runner, incomplete-collection label,
  and reader packet.

**Pause:** Review the scenario references and reader packet before paid live
model runs.

### Separately scheduled — model comparison

- Start a new result set after the generic connection, included reference
  sources, and scenario references are accepted.
- Hold the selected suite, rubric, data, and model-team definitions constant
  for this batch and record the identities actually used.
- Run the complete suite once for each selected model team.
- Verify every case contains the complete reader packet and an incomplete
  collection is labelled incomplete.
- Apply the shared rubric once through a deliberately selected full-context
  human or frontier-model reader.
- If the reader is a frontier model, state in the report that this is one
  model-reader pass rather than independent human review.
- Publish the report and linked evidence without an automatic score,
  disqualification, rank, tie-break, winner, or production-readiness claim.
- Pause for owner review before Phase 1 closeout.

### Separately scheduled — broader conversation scope

- Review the Phase 1 report with the owner.
- Define the broader conversation-mode behavior and acceptance before
  implementation. Do not infer it from Phase 1.

### Phase 3 — Dashboard Builder completion

- Cover Dataset, Widget, Dashboard, and publication actions through their
  public Gateway routes.
- Convert a successful typed execution into an immutable Dataset without
  engine-specific literal rules.
- Preserve exact SQL and typed values for the active dialect and return an
  actionable error when publication cannot represent them safely.
- Finish deterministic compatibility and reviewable suggestions for the
  accepted visualization families.
- Finish deterministic native Superset bundle generation and publication
  status based on explicit importer receipts.
- Run the real model-assisted browser workflow through Spark: ask, edit,
  format, Run, save Dataset versions, save Widgets, arrange and publish a
  Dashboard, import it, and open its stable Superset URL.
- Inspect one rendered value against the originating Catalyst result without
  a second database query.
- Compare the live Workbench, Dataset review/library, Widget review/library,
  Dashboard library/arrangement, and publish/import states side by side with the
  binding design.
- Confirm profile selection, generation/failure evidence, Clear/Restore,
  complete Available data browsing, resizable composer/thread, single editor,
  review panels, multiple Widgets, and actionable publication states remain.
- Pass focused API, component, bundle, publication, keyboard, focus, error,
  desktop, and narrow-layout checks.
- Obtain final owner acceptance of the browser-visible workflow.

Phase 3 does not require repeated model runs, restart/reset matrices, environment
parity, independent database reconciliation, or exhaustive infrastructure
failure simulation.

### Guardrails

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

</details>
