# OpenELIS–Catalyst reporting pathways

**Status:** Four-pathway delivery and specification consolidation approved by the
owner on 14 September 2026. Iteration 0 is in progress. This is the parent
roadmap; plan approval is not implementation, deployment or acceptance.

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
| 0. Consolidate and establish authority | Persist direction, reconcile work, remove competing sequences without losing requirements, refresh dashboard references. | In progress; FP-001. |
| 1. Align mocks and contracts | Interactive CSV import/review and PostgreSQL source journeys reuse approved styles; failure/recovery and saved work represented; specs agree and owner reviews additions. | Next; FP-002. |
| 2. Reporting example and lane 1 | Native saved-report rerun and real CSV → Superset table plus meaningful summary chart; inspect values, repeated results and dates. Begin FHIR coverage check. | Native milestones plus FP-003 integration verification. |
| 3. PostgreSQL and lane 3 | Full readable schema, question/refinement, explicit Run, save/reopen, publish and rendered Superset; Spark regression passes. | Pending; FP-004 and shared publication FP-005. |
| 4. Imported Dataset foundation | Lane-1 CSV uploads/reviews/saves without SQL; values/order/types survive reload/restart; retry works and a table publishes. | Pending; FP-006 and FP-005. |
| 5. Lane 2 visualization | Correct grouping/aggregation, saved/restored arrangement and rendered publication without SQL interaction. | Pending; FP-007. |
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
- Catalyst main is `bb783c8`; harness main at branch creation is `3de714b`.
  Existing implementation saves query-backed Datasets and uses Spark. Imported
  Datasets and reusable PostgreSQL are approved work, not existing capabilities.
  The preview manifest still identifies `ed22781`.
- Harness PRs #168 (queue deferral) and #171 (query date context) are separate
  open proposals. This change does not silently adopt or overwrite them.

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

### Cross-pathway acceptance record

| Evidence | Current state |
| --- | --- |
| Owner approval of direction | Approved 14 September 2026; recorded here. |
| Updated mock/spec owner review | Pending iteration 1. |
| Lane 1 / 2 / 3 / 4 local proof | Pending; native stage evidence alone does not establish a lane. |
| Four server journeys and rendered values | Pending. |
| Paced videos and public references | Pending. Existing videos document earlier capabilities. |
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
stage, supporting both Dataset origins.

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
