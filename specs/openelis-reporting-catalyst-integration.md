# OpenELIS–Catalyst reporting pathways

**Status:** Four-pathway delivery and consolidation were approved on 14 September
2026. The mock additions and chart controls are approved and implemented. Local
browser proof now covers native CSV upload into Superset, CSV upload/type recovery
in Catalyst through tables/charts/publication, and PostgreSQL query correction
through exact rendered results. The verified local deployment is harness #187
(`659190e`) with Catalyst #138 (`364c5bc`), preserving all saved artifacts and
storage mounts. CSV summary repairs and full-file table pagination are included.
Browser review confirms the original two rows render without a false limit warning;
the 1,101-row regression table retains pagination and reaches its final row.
The reporting instance's FHIR connection still requires approval in the native
implementation task. Complete server journeys, paced videos, public references
and owner acceptance remain open. This roadmap owns cross-project sequence;
the [task register](008-catalyst-query-workbench/tasks.md#immediate-four-pathway-test-checkpoint)
contains current per-lane evidence and gaps.

## Outcome

| Lane | Journey | Purpose |
| --- | --- | --- |
| 1 | OpenELIS report builder → CSV → Superset upload → charts/dashboard | Use a deliberately configured report through conventional visualization tools. |
| 2 | OpenELIS report builder → CSV upload inside Catalyst → imported Dataset → charts/dashboard → Superset | Continue from an existing report without requiring SQL interaction. |
| 3 | OpenELIS PostgreSQL source → Catalyst question/refinement → Dataset → charts/dashboard → Superset | Explore the native database independently of the report builder. |
| 4 | OpenELIS FHIR store → FHIR Data Pipes → Parquet/Spark → Catalyst question/refinement → Dataset → charts/dashboard → Superset | Explore FHIR-derived analytics with its actual coverage and freshness. |

These are complementary pathways, not equivalent competitors to rank. Shared
examples provide continuity and support checking overlapping records; they do
not establish a winner. Each lane is a foundation for later enhancement.
This goal ends with four verified local/server journeys, paced demonstrations,
current references and explicit owner acceptance.

Use synthetic demonstration records and existing sign-ins. Preserve existing
protections and read-only source access. Shared sign-in and equivalent per-user
authorization remain a separately scheduled production integration milestone.
OpenELIS reporting works without AI or Catalyst. No embedded application,
automatic application handoff or transferred report criteria is required.

## Workflow acceptance and scope

Catalyst is a human-in-the-loop tool. For lanes 3 and 4, manual SQL correction
is a valid completion path: ask a question, review the generated query or error,
edit SQL where needed, explicitly execute, verify the returned records, save the
Dataset, and continue through Dashboard publication and rendered Superset results.
Retain generated and human-edited versions and show the correction honestly in
the demonstration. Correct final outputs and working recovery are required;
AI-only success is not required. An incorrect model proposal is an observation,
not a delivery blocker when the supported correction workflow works.

Model accuracy optimization, repeated prompt coaching, model comparison and
performance benchmarking are outside this four-pathway delivery goal. Do not
turn a model mistake into a prerequisite to resume delivery. Repair application
failures that prevent the user from reviewing, correcting, executing, retaining,
saving or publishing work; otherwise record the limitation and continue the lane.
Any separately authorized performance test must use at least a Gemma 4 12B
writer with the Qwen reviewer/validator enabled and retain evidence of both roles.
That configuration requirement does not authorize a performance investigation.

This restores the intended workflow; it does not add a new product requirement
or relax verification of final data, deployment, videos or owner acceptance.
Older model investigations remain dated evidence or separately scheduled work,
not prerequisites for this goal.

## Authority and consolidation

| Responsibility | Authoritative home | Other records |
| --- | --- | --- |
| Shared scope, lanes, order and cross-pathway acceptance | This roadmap | Link here; do not reproduce its sequence. |
| Native reporting behavior and implementation | [Native specification/plan/tasks][native-plan], aligned with [OpenELIS design][export-spec] | Existing native effort owns export, saved reports, queue and its acceptance. |
| Catalyst application behavior and APIs | [Product specification][product] and existing contracts | Imported/query-backed Datasets, PostgreSQL, visualization and publication belong there. |
| Interaction and appearance | Product-owned [OpenELIS mock][preview], [Catalyst binding design][binding] and [integration design][integration-design] | Harness publishes Catalyst's source copy and links out to OpenELIS. |
| Detailed Catalyst/shared integration tasks | [Catalyst integration and delivery tasks](008-catalyst-query-workbench/tasks.md#four-pathway-delivery) | One task per shared capability, even when several lanes depend on it. |
| Existing Catalyst release and subsequent AI design | [Catalyst delivery plan](008-catalyst-query-workbench/plan.md) and existing Follow-on A | Preserve responsibilities; do not recreate that milestone. |
| Native execution and human review | Native execution/UAT records and live checklist | Link actual results; do not copy the human checklist. |
| Browsable overview | [Project dashboard][dashboard] | Dated summaries and links, not another task register. |

Feature 008 is the harness Catalyst integration/delivery register, not the parent
specification for OpenELIS reporting. Keep its identifier and use descriptive
navigation titles. The [program roadmap](catalyst-program-roadmap.md) retains
evaluation and broader-conversation decisions.

Extend existing documents. Move unique requirements to their proper owner before
replacing superseded bodies with short successor links. Git retains historical
text. Reconcile mock/product-spec disagreements before implementing the affected
behavior. Frozen mocks, research and dated run reports are evidence, not competing
current requirements. Include documentation alignment in each implementation PR
and refresh the dashboard at meaningful events.

Use consistent terms: a **data source** is a queryable connection; a **Dataset**
is reusable typed data from a query or imported file; a **Widget** is a saved
chart/table over a Dataset; a **Dashboard** arranges Widgets. A **lane** is a
pathway, an **iteration** is a delivery step, and a **review checkpoint** is a
concrete result ready for inspection.

### Disposition of preceding decisions

| Previous material or boundary | Current disposition |
| --- | --- |
| CSV only as comparison evidence; no ingestion | Amended by lane 2: direct Catalyst upload and imported Datasets approved. Comparison remains review material, not a staff-facing ranking feature. |
| FHIR/Spark as the only integration starting path | Retained as lane 4; lane 3 adds ordinary PostgreSQL. Neither replaces the other. No curated relation allowlist or SQL translation. |
| Shared identity/access required for initial completion | Retained for production, separately scheduled after this demonstration goal. Current sign-ins do not implement it. |
| September 10–12 mock/readiness milestones | Historical baseline, replaced by the iteration register below. Design PRs #313/#315/#320 and Catalyst #98/#100 remain in Git history. |
| August fictional example | Dated mock evidence. New demonstrations reuse the actual native synthetic fixture period and align illustrative labels. |
| Fixed CSV order/private saved settings | Current native authority owns user ordering, shared named definitions, fresh periods and immutable jobs; no older rule is restored. |
| Queue and export companion delivery | Retained in native milestones. One working report does not close the full reporting MVP. |
| Patient printing/Jasper replacement, scheduling, OGC-1031 and report-template management | Separate native efforts; not absorbed. Earlier [Catalyst reporting proposals][earlier-catalyst] do not expand scope. |
| Multi-artifact AI design, Metabase and Evidence | Preserve existing Follow-on A/B/C. A supports both Dataset origins; no duplicate AI milestone. |

## Approved implementation direction

Extend the approved Explore / Saved work shell, logo, typography, composer,
spacing, light/dark appearance and Advanced mode directly. The combined saved
collection is **Datasets**, with query/import origin and appropriate actions.
The integration design owns interaction detail; review additions before implementation.

Lane 2 is **Upload CSV → review columns/types → confirm import → save Dataset →
create visualizations**. Preserve existing query-backed save APIs and artifacts.
An import records file identity, checksum, reviewed schema, complete row count
and immutable version; it has no fabricated query/session history. Failed
imports create no ready Dataset or partially published data. Replacement is
explicit and never silently changes an existing published dashboard.

Use a dedicated persistent PostgreSQL database on existing demo PostgreSQL
infrastructure for imported data, separate from OpenELIS operational data and
Superset metadata. Keep storage details out of the staff workflow. Lane 1 uses
Superset's native file upload; lane 2 uploads inside Catalyst.

PostgreSQL is reusable source support, not an OpenELIS-specific connector. Review
compatible historical driver/tests without restoring relation restrictions.
Address transport, schema discovery, parameters, types, execution bounds, editor
behavior and source-aware publication. Keep exact selected SQL and the complete
readable schema; preparation does not execute it. Source changes start another
session and do not retarget saved work.

Reuse supported visualization families and add shared grouping/aggregation
controls needed for raw imported records, including record counts. Do not apply
pre-aggregated-query assumptions silently to raw rows or change data meaning as
a presentation edit. Superset renders against the artifact's actual backing
connection, with explicit publication, deterministic bundles and actual receipts.

## Iterations and acceptance

This is the sole cross-project sequence. Detailed tasks stay in linked registers.

| Iteration | Outcome and exit criteria | Current state / detailed owner |
| --- | --- | --- |
| 0. Consolidate and establish authority | Persist direction, reconcile work, remove competing sequences without losing requirements, refresh dashboard references. | Harness #173 and Catalyst #127 merged; native cleanup retains its owner. FP-001. |
| 1. Align mocks and contracts | Interactive CSV import/review and PostgreSQL source journeys reuse approved styles; failure/recovery and saved work represented; specs agree and owner reviews additions. | Catalyst #127/#128 merged; all five checks pass on #128 head `9728294`; owner approved additions for implementation on 14 September. FP-002. |
| 2. Reporting example and lane 1 | Native saved-report rerun and real CSV → Superset table plus meaningful summary chart; inspect values, repeated results and dates. Begin FHIR coverage check. | Local native saved-period rerun and CSV upload/table/chart verified; broader fixture and server proof remain. Native milestones plus FP-003. |
| 3. PostgreSQL and lane 3 | Full readable schema, question/refinement, explicit Run, save/reopen, publish and rendered Superset; Spark regression passes. | Connection/editor and publication support are merged. Local manual query/save/Superset proof passes. Model join failures are retained observations; manual correction now passes through saving/reopening and actual Superset rendering. Complete the broader demonstration, server run and paced video. Relationship metadata #136 is deployed locally through merged harness #183. FP-004 and FP-005 own detailed evidence. |
| 4. Imported Dataset foundation | Lane-1 CSV uploads/reviews/saves without SQL; values/order/types survive reload/restart; retry works and a table publishes. | Catalyst #131 merged and verified in the retained local stack, including the same native CSV and Superset table. Upload repair #132 merged; server and broader fixture acceptance remain. FP-006 and FP-005. |
| 5. Lane 2 visualization | Correct grouping/aggregation, saved/restored arrangement and rendered publication without SQL interaction. | Catalyst #133–#135 are integrated locally. Native count 2, average 60 and total 120 render after grouping/chart-identity repairs; a 101-row table proves pagination. Fresh native CSV error recovery and saved chart/arrangement/publication checks pass. Browser file attachment, broader fixtures and server acceptance remain. FP-007 owns detailed evidence. |
| 6. Lane 4 | Actual reporting-instance FHIR output reaches the existing pipeline; useful Dataset/dashboard, traceable records, coverage and freshness. | Pending; FP-008. |
| 7. Complete local review | Four real journeys, desktop/narrow light/dark mock comparison, retained state, owner feedback and unresolved findings. | Pending; FP-009. |
| 8. Server demonstration and closeout | Compatible reviewed revisions, four server journeys, verified rendered data, paced recordings, current references and owner acceptance. | Pending; FP-010. |

Native and Catalyst work proceed independently where dependencies allow. Use
small cohesive PRs and matching existing work without elaborate branch stacks.
Implementation, checks, PR/merge state, environment verification and owner
acceptance are separate facts. No date or automatic acceptance is implied.

### Current baseline — checked 14 September 2026

- Native [spec PR #4291][native-spec-pr] and [implementation PR #4292][native-pr]
  are open; implementation head is `948cdf3b0a13adc23c7b556b780fbf3f78eb245e`.
  Its records describe a publicly deployed Sample & Testing stage, spreadsheet
  and detailed-result layouts, shared definitions and queue work. Full native
  MVP and human acceptance remain open. These are owner-recorded results, not
  new runtime verification by this documentation change.
- Native packaging is the existing ten-PR sequence #4304, #4305, #4307,
  #4308, #4309, #4310, #4312, #4313, #4314 and #4315. #4306 identifies a
  GitHub stack, not a missing implementation PR. Its implementation owner
  confirmed that #4291/#4292/#4295 await coverage/disposition before retirement.
  The native [review stopping point][native-review] owns packaging and evidence.
  Native merges and retirement remain with that owner; this integration effort
  owns harness/Catalyst changes. Do not start a replacement stack or duplicate
  native cleanup. Check each current head and required checks before merging.
- [OpenELIS mock PR #322][export-pr] merged as `2ff6cbe` on 14 September:
  grouped search, initially collapsed sections and drag ordering. Tests/build
  passed at `5b2df7e`; the failed auto-merge setup had run while the PR was a
  draft. This mock merge does not establish native runtime or human acceptance.
- Native UAT's owner reports app `9baa356345489bf16d197c4ea6db48a615f894f9`,
  review tooling `9995411a6bab5954fe4476b602d5df35102218ee`, and checklist
  revision `1ad52b20` on 14 September. Referrals is available; Non-Conformance
  remains pending. The existing native checklist owns human review, not a copy
  in this roadmap. These identities are owner-reported, not independently
  exercised by this documentation change.
- At consolidation start, Catalyst main was `bb783c8`; harness main was `3de714b`.
  Existing implementation saves query-backed Datasets and uses Spark. Imported
  Datasets and reusable PostgreSQL are approved work, not existing capabilities.
  Design-only Catalyst #127 subsequently merged as `8524925`; the published
  preview manifest and all eleven assets were verified against that revision.
- Harness PRs #168 (queue deferral) and #171 (query date context) are separate
  open proposals. This change does not silently adopt or overwrite them.

### Early integration readiness — checked 14 September 2026

- The native owner exercised the actual local saved-report journey: export 5 May
  2026, reopen the saved configuration with blank dates, then export 6 May.
  Both downloads and job/definition receipts are retained privately. Frontend
  revision `36eb98edda492e7419b5486ba35d1c14baab18c7`, backend `8005e4`.
  May 5 preserves distinct results `1154`/`1155`, both `450`, with zero-minute
  validation intervals. May 6 preserves `1158`/`1159`, both `450`, at 30/90
  minutes. The uniquely named test definition was removed after success; the
  completed jobs remain. This was a bounded synthetic check without reseeding.
- That exact **local** May 6 CSV was uploaded through native local Superset into
  Dataset `32`, preserving identifiers as text and CSV column order. Saved and
  reopened dashboard `32` contains raw table `63` and interval bar chart `64`;
  rendered rows and chart values match `1158 → 30`, `1159 → 90`. The screenshot
  was inspected. This establishes the local saved-period example, not broader
  fixture coverage, server delivery, final styling or owner acceptance.
- Earlier dashboard `31` used the published server CSV in local Superset and
  remains distinguishable as preliminary import/rendering proof. Both use the
  separate `catalyst_imports` database and `report_uploads` schema on the existing
  PostgreSQL service. [Upload operations](../docs/catalyst-demo-operations.md#native-csv-reporting-uploads)
  remain the operator reference; no Catalyst import implementation is implied.
- Catalyst [#129](https://github.com/DIGI-UW/catalyst-ai/pull/129) merged as
  `6513c886e44b5c68a0bcf99cc92d7543a33288eb`: shared PostgreSQL transport,
  readable catalog, result typing, server timeout and editor grammar. All five
  hosted checks passed at `10397a1`; local checks passed 389 Gateway tests
  (including real PostgreSQL), 302 UI tests, 17 browser workflows and 57 assembly
  tests. One opt-in live Spark and eight live-demo browser tests were skipped.
  The existing Spark-driver typing warning and bundle-size warning remain.
  The harness now pins this merged code. It is not yet deployed; native query
  refinement/save/reopen and source-aware Superset publication remain open.

- At the initial readiness check, the native public [deployment receipt][native-deployment] identified application,
  frontend and backend `8005e4cc0b2b05d054489730aef969027d773093`, deployment
  `20260914T234348Z-8005e4cc0b2b`. This verifies the published identity, not the
  completed journey. The updated receipt reports public browser checks and CI
  passed; human acceptance remains pending. The published [native evidence
  bundle][native-evidence] identifies the same application and test revision.
  All six report/queue CSV downloads match its checksums and each pair is
  byte-identical. Parsed Sample & Testing files preserve two `450` readings
  with 30/90-minute turnaround; the detailed layout retains separate Result IDs
  `1158`/`1159`. Referrals retains two completed results and a blank pending
  result. This audit inspected the CSVs, not the owner's video recordings; it
  does not establish their final four-lane demonstration pacing.
- The local reporting database contains four synthetic results: two independent
  `450` readings for `REPORTING-MVP-REPEAT` on 5 May, and two for
  `REPORTING-MVP-TURNAROUND` on 6 May. The first pair shares one analysis but has
  distinct result identities. Preserve both; identical values are not duplicate
  records. No CSV was generated by this readiness audit.
- The local reporting stack defines the application and database, and maps
  `fhir.openelis.org` to its own loopback address. A read-only check of the
  separate Catalyst HAPI store found none of the four known fixture Observation
  IDs. The native owner also reports no proof of normal FHIR emission. Coordinate
  actual reporting-instance emission/routing before lane 4; do not manufacture
  matching resources or treat the existing Catalyst cohort as parity evidence.
- The subsequent native-owner update identifies frontend/test `7cca586e`, with
  backend `8005e4c` and synthetic records/CSV evidence unchanged. The owner
  reports the change only clears a stale shared-report conflict warning.
- Local Catalyst Superset retains both OpenELIS/OpenMRS Hive connections with
  upload disabled. The separate reporting-upload connection above now supplies
  lane 1; clinical data and Superset metadata remain outside its destination.

These are scoped readiness findings, not lane acceptance. Native deployment,
PR cleanup and UAT remain with their existing owners. Raw audit output stays
outside Git; FP-003 and FP-008 track the resulting integration work.

[native-deployment]: https://reporting.catalyst.openelis-global.org/__review/target.json
[native-evidence]: https://reporting.catalyst.openelis-global.org/reporting-evidence/20260914-review-8005/

## Verification and demonstration contract

Reuse synthetic viral-load fixtures, recording their actual period and IDs.
Native UAT documents May 5 repeated results and May 6 turnaround examples.
Use detailed-result CSV for reconciliation and retain spreadsheet output as
another native capability. Collection-date filtering follows the native anchor
and laboratory timezone; filtering and grouping remain distinct. Inspect source
records before using the CSV as a reference.

Within each environment, all lanes originate from one reporting OpenELIS
instance. Lane 4 consumes its actual FHIR output, not separately manufactured
matching records. Verify included/excluded records, repeated results, nulls,
identifiers, units, statuses, corrections and date boundaries. Compare genuinely
shared fields/meanings; explain unsupported coverage and freshness. Never invent
values, silently omit records or equate matching counts with correctness.

Distinguish complete imported files, bounded query previews and live query
definitions. Check CSV escaping/BOM, order, leading zeros, mixed values, empty
output, invalid files, type correction, interruption and retry. Verify both
Dataset origins, existing artifacts, source isolation, chart aggregation,
arrangement, publication receipts and rendered values.

Run focused behavioral tests and existing documentation, lint, type, build and
browser checks. Inspect desktop/narrow light/dark screenshots against the
approved design. Real application validation is required; mock checks are not
production proof. Native workload, recovery and broader field coverage stay in
the native acceptance plan rather than duplicated here.

Use the harness lifecycle wrapper and native reporting deployment procedure.
Preserve retained records, sessions and unrelated deployments; record exact
revisions/configuration. Add source identities rather than silently rebinding
sessions. Seeding/reset remains explicit. Keep raw footage, traces, screenshots,
transcripts and personal handoffs outside Git; commit concise acceptance records
and appropriate evidence links.

Produce a brief overview and four independently watchable demonstrations. Keep
FHIR infrastructure explanation brief. Hold captions/cards at least five seconds
and results/details at least eight, extending for reading time. Retain captions
through holds, label accelerated waits, avoid covering relevant content and
watch final cuts at normal speed. Synchronize public videos/posters, review hub
and status links after verified publication.

### Review checkpoint: four pathways, videos and public explanation

Iteration 8 is reviewable when
`https://openclinai.org/catalyst/reporting-pathways/` presents the four pathways
together, with a brief overview and four independently watchable videos. The
homepage introduces Catalyst; its project overview links to this reporting page. Use the existing `landing/`
site and publication flow; do not create another tracker or documentation site.
FP-010 owns this delivery, with FP-009 supplying the local validation.

Acceptance requires:

- Each pathway explains its starting point, complete journey, when it is useful,
  and its data coverage/freshness limits. Present complementary choices without
  ranking them as equivalent alternatives.
- Each of the four pathway entries embeds its own verified server recording,
  with playback controls, a descriptive poster, duration and readable transcript
  or step summary. Clearly identify the environment and link the corresponding
  local proof. Existing earlier walkthroughs remain labeled as earlier examples,
  not evidence that these four journeys passed.
- The videos show the actual lane-specific steps through rendered Superset
  results, including file upload for lanes 1 and 2 and model question/refinement
  with review, manual SQL correction when needed, and explicit execution for lanes
  3 and 4. Show human edits and verify the final results. API-only upload checks
  do not substitute for recorded file selection; AI-only SQL success is not a gate.
- The pacing rules above pass normal-speed viewing. The published page works on
  desktop and narrow screens; all four videos, posters and evidence links load.
  Verify deployed HTML/media against the reviewed revisions and checksums.
- Record the four journey results, publication verification and explicit owner
  acceptance separately in the existing task and acceptance records. Synchronize
  the existing status dashboard to link here and to the live reporting page. Keep raw
  recordings, traces and personal handoffs outside Git.

A page draft or partial recording can be reviewed earlier, but does not close
this checkpoint. As of 15 September, four final recordings remain unpublished. The owner-approved
website hierarchy and reporting page are delivered through website PR #184;
earlier Catalyst videos remain labelled as earlier examples. Website sequence and acceptance
live in `landing/README.md`; this roadmap retains four-pathway acceptance.

### Cross-pathway acceptance record

| Evidence | Current state |
| --- | --- |
| Owner approval of direction | Approved 14 September 2026; recorded here. |
| Updated mock/spec owner review | Approved 14 September 2026 after local CSV journey review; Catalyst #128 merged as `5164449`. |
| Lane 1 / 2 / 3 / 4 local proof | Pending; native stage evidence alone does not establish a lane. |
| Four server journeys and rendered values | Pending. |
| [Four-pathway videos and public explanation](#review-checkpoint-four-pathways-videos-and-public-explanation) | Pending: four final server recordings, openclinai.org reporting page, playback/publication verification and owner review. Existing videos document earlier capabilities. |
| Specification/dashboard consistency and owner acceptance | Pending final review. |

Completion requires every line above, distinguishing implementation, merge,
deployment, checks and owner acceptance. Shared production identity remains
outside this goal. Existing **Follow-on A** then extends conversational Widget
and Dashboard design to both Dataset origins; Metabase/Evidence retain their
existing subsequent milestones.

## Copyable delivery goal

Deliver all four pathways through iterations 0–8. Consolidate existing specs
first, preserving unique requirements and one owner per decision/task. Follow
approved product mocks, reviewing extensions before implementation. Reuse native
reporting, Catalyst components, Superset and compatible PostgreSQL history.
Preserve query-backed artifacts while adding immutable imported Datasets without
SQL interaction. Verify real synthetic records, local/server journeys, actual
rendered publication, paced videos and owner acceptance. Keep raw evidence
private and status references current. Finish with consistent scope, terms and
remaining work across the roadmap, product specs, mocks, task registers and
dashboard. Preserve existing AI-assisted Widget/Dashboard refinement as the next
stage, supporting both Dataset origins. Accept the supported human correction
workflow when AI fails; preserve the edits and verify final results. Do not expand
this delivery into model optimization or performance benchmarking. Separately
authorized performance tests require at least a 12B writer plus Qwen validation.

[native-plan]: https://github.com/DIGI-UW/OpenELIS-Global-2/blob/codex/reporting-ui/specs/479-reporting-mvp/plan.md
[native-review]: https://github.com/DIGI-UW/OpenELIS-Global-2/blob/codex/reporting-ui/specs/479-reporting-mvp/review-stopping-point.md
[native-spec-pr]: https://github.com/DIGI-UW/OpenELIS-Global-2/pull/4291
[native-pr]: https://github.com/DIGI-UW/OpenELIS-Global-2/pull/4292
[export-spec]: https://github.com/DIGI-UW/openelis-work/blob/main/designs/reports/custom-data-export.md
[export-pr]: https://github.com/DIGI-UW/openelis-work/pull/322
[preview]: https://digi-uw.github.io/openelis-work/#/reports/custom-data-export
[product]: https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md
[binding]: https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/dashboard-builder-mvp-design.md
[integration-design]: https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specs/openelis-reporting-integration/spec.md
[earlier-catalyst]: https://github.com/DIGI-UW/openelis-work/blob/main/assets/requirements-docs/catalyst-functional-requirements.md
[dashboard]: https://pmanko.github.io/clinical-ai-validation-harness/status/
