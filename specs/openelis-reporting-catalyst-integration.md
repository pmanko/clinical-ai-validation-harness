# OpenELIS reporting and Catalyst integration

**Status:** Mock/spec construction approved on 10 September 2026. Two parallel
delivery streams meet at a real source connection and CSV/Dataset parity review.
The baseline mock/spec set is published. The current checkpoint is
[OpenELIS design revision and implementation readiness][export-readiness].
OpenELIS [design PR #320][export-pr] carries the v1.4 field browser and editable
CSV-column order, following the owner's approval on 12 September. Local tests,
gallery build and desktop/narrow browser checks pass. It is merged and published
at `6028d4d`, with exact live assets verified. The first-slice reporting
defaults remain approved; final visual acceptance and production implementation
remain separate milestones.

## Purpose and authority

Give laboratory and program staff a simple way to choose and export the data
they need in OpenELIS, and use the upgraded Catalyst to produce the equivalent
dataset by querying a connected OpenELIS data source.
The reported problem is a routine CSV export with fixed, sometimes irrelevant
columns and long-running work that is difficult to return to.

This document owns the proposed cross-project scope, unresolved decisions and
milestones. The existing OpenELIS requirements own its export and queue details;
Catalyst's [product specification](../targets/catalyst/docs/specification.md)
owns its application contracts. Amend those documents when a decision changes
their behavior; do not maintain competing copies here.

The current [Catalyst delivery plan](008-catalyst-query-workbench/plan.md)
continues through the server release and refreshed demos. This initiative has
no assigned delivery date and adds no prerequisite to that checkpoint or its
already scheduled follow-ons. Use this document as the planning home while
scope is reviewed; implementation tasks belong with the product that delivers
them. The project dashboard should link here rather than duplicate the register.

## Mock/spec baseline and ownership

The clarification session established these decisions:

- OpenELIS reporting is fully independent of AI and Catalyst.
- The applications open independently with shared organizational sign-in and
  equivalent lab-unit/identifying-field access. No application links, embedded
  Catalyst or report-criteria transfer are included.
- The first OpenELIS mock covers configurable CSV export, saved configurations
  and My Report Queue. Patient printing and Jasper replacement remain separate.
- The common example is monthly virology results. CSV/Dataset comparison is
  solely our parity review, not a staff-facing comparison feature.

The owner clarified the design homes during review: extend Casey's existing
OpenELIS reporting mock and specification in `openelis-work`, using its existing
OpenELIS styles. Catalyst owns only its independent connected-source experience
and the integration design specification, reusing the approved Workbench assets.
The reviewer hub links out to OpenELIS's gallery; it does not copy or embed those
screens. Review links are outside the application surfaces.

The OpenELIS draft covers field/filter selection, saved configurations, CSV
output and queue failure/retry/expiry, including fresh dates when loading a
configuration or expired job. The Catalyst draft covers preparation versus
explicit execution, retained drafts, source-bound sessions and Dataset save/reopen.
Both show fictional sign-in and restricted-access examples independently; the
previews do not synchronize credentials or implement shared sign-in.

Use August 2026 collection dates, a selected HIV viral-load test and validated
results. Include one row per result, repeated accessions, blank values and date
boundaries. Provide a downloadable example CSV and a separately represented
Catalyst Dataset. These illustrate comparison; they prove no live integration.

Publish the draft beside the approved reference in the existing design-preview
hub. Display the actual source revision and verify copied assets. Check the
complete journeys, keyboard/focus, desktop/narrow and light/dark screenshots,
CSV output, documentation links and the site build before owner review.
Screenshots and raw test evidence stay outside Git. The exact approved product
implementation continues; new OE/integration implementation follows this design
review. Shared sign-in and equivalent authorization are requirements for that
integration, not functionality already supplied by the current Catalyst demo.

| Review artifact | Source and status |
| --- | --- |
| [OpenELIS reporting mock][preview] and [export specification][export-spec] | `openelis-work`; [column-builder PR #320][export-pr] updates the existing mock/spec to v1.4. Its ordered columns replace the fixed-order/checkbox rule while retaining new/saved paths, permissions, drafts and queue recovery. Publication evidence follows below; detailed acceptance stays in its own register. |
| [Catalyst integration draft][integration-preview] and [design specification][integration-design] | Catalyst; initial PR #98 followed by merged [ownership correction PR #100](https://github.com/DIGI-UW/catalyst-ai/pull/100), which removes the duplicate OpenELIS screen. Published source is recorded in the hub manifest. |
| Cross-project decisions and publication | This roadmap and the harness review hub; owner design acceptance remains pending. |

Catalyst is the source for its published preview files; the harness keeps a
generated copy. The hub's source link and `source.json` identify that exact
revision independently of the runtime Catalyst pin. OpenELIS remains in its own
gallery; the hub links to its canonical permalink.

## Current checkpoint: OpenELIS design readiness

The owner expects a roughly even mix of new exports and rerunning familiar
reports. The v1.3 landing, builder and queue revision is retained. Feedback then
approved a searchable **Available fields** browser beside **Your CSV columns**,
with Add/Remove and editable order. PR #320 reconciles that direction in the
existing mock, specification and implementation slices; saved settings, submitted
jobs, retries and CSV output preserve the chosen order. This amends the former
mandatory catalog-order rule without reducing field coverage or permissions.

The authoritative sequence, acceptance register and copyable goal live in
[section 14 of the OpenELIS specification][export-readiness]. Update that register
rather than duplicating tasks here. Final visual review remains open; approval
of the design direction is not final acceptance or production implementation.

OpenELIS owns the interactive HTML, fictional CSV helper and its component
reference. The existing Catalyst integration spec/mock remain the independent
Catalyst-side review; the harness owns cross-project decisions and publication
links. Do not create another OpenELIS screen or implementation checklist here.

Readiness requires an inspected current-code baseline, resolved product decisions
for the first slice, tested and published mock/spec agreement, explicit owner
review and implementation slices linked to the existing OpenELIS stories. Start
with a complete export/retrieval journey, preserving the export/queue companion
release requirement. Staff usability testing is distinct from automated checks;
if participants are unavailable, record it as pending rather than claiming it
passed. Application implementation, real-source parity and shared authorization
remain later milestones; Catalyst's current upgrade continues independently.

Cross-thread and GitHub coordination was checked on 12 September: Catalyst
visual remediation remains in #117, runtime release #157 is merged, and closed
harness #151 does not amend the original roadmap. This reporting change adds no
new prerequisite to Catalyst delivery. The [dated PR review](artifacts/project-status/reviews/2026-09-12.md)
records lane boundaries and remaining backlog disposition.

Publication receipt — 12 September 2026: [PR #320][export-pr] merged as
`6028d4df603b3a482179b96148de4eeb30dd2394`; GitHub test/build checks and
[gallery deployment](https://github.com/DIGI-UW/openelis-work/actions/runs/34718413037)
passed. The live HTML, specification and CSV helper match the tested source byte
for byte. The published gallery was exercised and screenshot-inspected with a
reordered first column and field search; the selected list preserved the order.
The preceding v1.3 publication and return-to-overview fixes (PRs #315, #317–319)
remain the baseline. The new revision has 273 passing repository tests and a
passing gallery build; desktop and 390-pixel browser checks cover ordered columns
and retained workflows. Final visual acceptance is still an owner checkpoint.

## Two delivery workstreams and one integration checkpoint

| Workstream | Delivery target | Boundary |
| --- | --- | --- |
| OpenELIS reporting | Implement the agreed reporting MVP from Casey's [export design][export-spec]: choose fields and filters, save and rerun choices, generate CSV output and retrieve queued jobs. Prepare the source-side field mapping, data access and freshness information needed by Catalyst. | Export works without AI. The required export queue remains a separately tracked deliverable within this stream. Patient printing and Jasper replacement need their own disposition. |
| Catalyst upgrade and source readiness | Complete the approved redesign, saved-work and Dashboard delivery; use that same Workbench for the real OpenELIS source connection, schema browsing, question/refinement, explicit execution and saved Dataset flow. | Keep one Catalyst implementation effort. Application changes belong in its product specification/tasks; connection and validation work belong with the harness integration. This initiative does not reopen the approved shell or add requirements to the current release checkpoint. |

The streams meet at a **required integration checkpoint**: an authorized user
exports an agreed report from OpenELIS, then independently generates the
equivalent dataset through Catalyst's connected OpenELIS source. Compare the
actual records and field values. The CSV is comparison evidence, not the data
source uploaded into Catalyst. A video can demonstrate the result; it does not
replace this working integration or its validation.

Source preparation starts alongside reporting work. Catalyst's selected
reference path remains FHIR Data Pipes → Parquet → Spark SQL. Start with the
existing OpenELIS source configuration and verify coverage/freshness for the
agreed reporting fields; a different Catalyst source path requires an explicit
roadmap amendment. OpenELIS's native export query implementation is a separate
decision. Distinguish preparation of the real source connection from any future
shared export API; the latter is not required for this checkpoint. The two
streams must agree field meaning and the source boundary early, rather than
discover incompatible assumptions only when both implementations are finished.

Use familiar visual language where useful while keeping the OpenELIS workflow
small. Do not make it inherit Catalyst's full Workbench or Dashboard experience.
Charts and Dashboards remain Catalyst capabilities, outside the bounded OpenELIS
export deliverable. Monthly reuse does not establish automatic scheduling.

## Existing efforts and overlap

These are inspected design documents, not evidence of implementation or Jira
completion. Product owners and delivery assignees remain to be confirmed.

| Existing material | Responsibility and disposition |
| --- | --- |
| [Custom Data Export & My Report Queue][export-spec] — OGC-479 / OGC-481 / OGC-483 | Reuse the existing draft for the wizard, saved choices and personal export queue. Its [design-readiness checkpoint][export-readiness] owns the next revision and handoff. It couples export and required asynchronous retrieval in one release. Keep the stories distinct. |
| [Patient Report Print Queue][gallery] — OGC-1031 | Reconcile with the meeting's common-queue idea before combining printing and export jobs. Do not absorb this effort by implication. |
| [Report Management][report-management] | Owns report-template administration; configurable CSV export does not decide replacement of patient reports or Jasper templates. |
| [Earlier Catalyst functional requirements, November 2025][earlier-catalyst] | Broader draft proposing reporting replacement, a wizard, multiple formats and scheduling. Retain as a proposal requiring disposition; it does not expand current delivery. |
| [Current Catalyst delivery](008-catalyst-query-workbench/plan.md) and [program roadmap](catalyst-program-roadmap.md) | Retain the approved UX, saved-work, Dashboard and Superset delivery, plus separately scheduled research and output integrations. This new planning work does not reopen the frozen shell design. |

Two overlaps require explicit reconciliation. The export draft proposes future
shared `filterSpec`, variable catalog and queue use by Catalyst; the closing
discussion did not settle that contract. Its FR-4-004 also specifies HQL/JPA
queries with a possible mapped read view, while the discussion left the data
platform open. Neither proposal becomes an integration decision merely by
linking it here.

## Decisions needed before implementation

The delivery decisions above are approved. Implementation details in these rows remain **open**. Record decisions and their rationale here, then update
the affected product specification. Do not infer acceptance from a mock or a
passing technical test.

| Decision | What the review must settle |
| --- | --- |
| Smallest export and replacement scope | First slice approved in OpenELIS Section 14: result rows, collection-period virology CSV and Routine CSV coexistence. Verify actual field/status mappings and later replacement acceptance. Jasper and patient printing remain separate. |
| Data meaning and coverage | Define what one row represents, joins, duplicate handling, derived values, units, missing values, status interpretation and date boundaries. Explain incompatible selections separately from permission restrictions. Verify mappings against actual data. |
| Execution and database impact | Evaluate the OpenELIS export draft's native application query approach against a representative workload and an agreed acceptable effect on normal laboratory operations. Consider a read-oriented layer only where evidence justifies it. Verify reporting-field coverage/freshness on Catalyst's existing FHIR/Spark path separately; changing that selected reference path needs an explicit roadmap amendment. |
| Permissions and retrieval | Approved: recheck before generation/download, retain the draft and explicitly deny unauthorized requests; BR-003/004 now remove silent scope/column omission. Implement and test real enforcement and ownership. A program filter is not a program-access policy. |
| Queue responsibility | Resolve personal export jobs versus patient printing, failure/retry behavior, retained-file access and expiry, and which existing story owns each behavior. Preserve the export/queue companion-release rule unless explicitly amended. |
| Catalyst connection and equivalence | The target is an independently generated Catalyst dataset queried from the connected OpenELIS source. Select the initial reporting scenario, check existing source coverage and agree the connection path, snapshot/freshness and comparison rules below. A shared export-request interface remains an optional later decision. |
| Shared sign-in and authorization | Required integration direction: the same signed-in person receives equivalent lab-unit and identifying-field access. Select and implement the enforcement and identity wiring; shared sign-in alone does not establish equivalent permissions. Embedding, application links and report-criteria transfer are excluded from the approved mock. |

## Proposed acceptance examples

These criteria are for scope review; product-specific details stay in the
linked requirements. They are not completed tests or owner acceptance.

| User story | Reviewable acceptance |
| --- | --- |
| As a laboratory user, I can export the data for my reporting purpose without AI. | With AI unavailable, select the agreed fields and filters, save and reopen the choices, rerun for a different period and receive a valid CSV. Inspect included and excluded records, column values, dates, statuses and empty-output behavior against the agreed meaning. |
| As a user, I can return to a report without keeping the generating screen open. | Submit work that uses the queue, navigate away, return and retrieve the result. Exercise generation failure, retry and expiry; verify direct download access and changed permissions with the agreed policy. Ordinary laboratory work remains within the workload limits agreed above. |
| As a Catalyst user, I can produce the equivalent dataset from OpenELIS data. | Browse the real configured schema, draft and refine the question, inspect the selected SQL, explicitly run it, and save/reopen the result definition. Compare records and values against the CSV generated by the agreed OpenELIS reporting build, including exclusions, duplicate/missing values and time boundaries. Record source freshness and explain any differences. |

Before the streams proceed past their initial reporting scenario, agree a small
comparison definition in this document: source snapshot or freshness cutoff,
what each row represents, permitted stable record references, selected fields
and units, date field/timezone/boundaries, result status and correction handling,
filters, duplicate/missing-value rules and expected completeness. Leave the
specific values open until the actual source and scenario have been inspected.

Validate the OpenELIS export against inspected source records before using it as
a comparison reference. Agreement between two wrong results is not acceptance.
Start with a small complete report and include meaningful variations such as
an excluded status, an empty period and missing/duplicate values. This initial
comparison does not substitute for the reporting MVP's wider acceptance cases.

Catalyst exposes the complete schema readable through its configured generic
SQL connection. OpenELIS's curated export fields must not become a core
Catalyst relation allowlist. A Catalyst preview has a row limit; saving its
query definition is not proof of a complete CSV export. The demo must label
limits and establish completeness separately when claiming equivalence.

Use retained demonstration data for the Catalyst exercise. Its current demo
scope does not implement production identity or sensitive-data authorization;
production use needs the separate permission decision and implementation.

## Roadmap and progress

Keep this milestone register small. Link product issues, PRs and evidence as
they exist; track implementation, validation and owner acceptance separately.
No release date or new product task is approved by this draft.

| Milestone | Exit evidence | Current state |
| --- | --- | --- |
| 0. Revise and review the mock/spec set | Independent OE/Catalyst workflows, synchronized specifications, published source revision, relevant checks and explicit owner design review. OpenELIS revision and implementation handoff follow [its own acceptance register][export-readiness]. | Baseline: OpenELIS PR #313, Catalyst correction PR #100 and harness publication [PR #128](https://github.com/pmanko/clinical-ai-validation-harness/pull/128). v1.4 column-builder direction approved; PR #320 merged and published with local/CI tests and exact live verification passing (receipt above). Final owner visual acceptance remains open. |
| 1. Agree where the streams meet | Reviewed initial report/comparison definition; field coverage on the existing source path; disposition of overlapping proposals; named ownership and links to each product's tasks. | Two-stream direction confirmed; fictional scenario and design ownership agreed; real-source comparison definition pending. |
| 2A. Build from OpenELIS | Settle export permissions/workload choices; deliver the bounded export, saved choices and required queue; generate a verified CSV and prepare the source mapping/access information. Link existing OE issues, PRs and real-path evidence. | No matching OGC-479/481/483 implementation PR identified in the September 12 metadata scan. Production-code mapping/workload verification remains part of the first slice. |
| 2B. Build from Catalyst | Continue the existing redesign/release tasks and prepare the real OE source connection; show schema browsing, question/refinement, explicit execution and saving through the approved Workbench. Link existing Catalyst tasks rather than duplicate them here. | Existing delivery remains active; integration-specific source gaps and readiness to be assessed. |
| 3. Connect and validate together | Query the connected OE source through Catalyst and compare the generated Dataset with the verified native CSV using the agreed definition. Record exact builds, source state, limitations, technical validation and owner acceptance separately. | Required integration checkpoint; date unassigned. |
| 4. Complete shared identity and access | Real shared sign-in and equivalent authorization across both applications, including download and access-revocation behavior; verification separate from source parity. Shared export APIs remain optional later scope. | Required for production integration; implementation approach open. |

Workstreams 2A and 2B proceed in parallel once their necessary initial decisions
are settled. Exercise an early complete reporting scenario before expanding
coverage. Each product can be reviewed and released independently; completion
of this integration initiative requires source parity at checkpoint 3 and real
shared identity/access at checkpoint 4. A new
Catalyst capability discovered here gets one task in its owning plan and a
dependency link here; it does not silently expand the current release scope.

## Validation and evidence

Documentation changes receive existing consistency and link checks. Later
behavior changes need focused product tests and real user-path validation;
record-level comparisons catch incorrect joins and meanings that matching
counts would miss, while workload measurements address the operational concern
that a queue demonstration cannot answer.

Follow the existing [harness constitution](../.specify/memory/constitution.md):
record exact revisions, source/schema identities, accepted mappings, query or
export configuration and relevant model/prompt provenance with each validation
run. Use existing manifests and traces where applicable. Preserve raw evidence
in ignored/private storage and link reviewable summaries; do not commit meeting
transcripts, patient exports or generated screenshots as planning content.
Explicitly label limitations and record owner acceptance separately from tests.

## Sources

- Owner-supplied consolidated discussion, reviewed 10 September 2026. It records
  a working direction with scope still being decided; the transcript remains
  private. Current application implementation was not comprehensively audited.
- Subsequent owner clarification on 10 September 2026: two parallel efforts,
  OE-side reporting readiness and Catalyst-side upgrade/source readiness,
  converging on a connected-source comparison of the native CSV and generated
  Catalyst Dataset.
- [OpenELIS export design preview][preview] and [functional draft][export-spec],
  v1.1 dated 15 July 2026, inspected 10 September 2026.
- [OpenELIS design catalog][gallery] and [earlier Catalyst proposal][earlier-catalyst].
- Owner clarification on 10 September 2026: OpenELIS mock/spec/style stay in
  `openelis-work`; Catalyst owns its independent source workflow; the review
  hub links out to OpenELIS. MVP changes are reviewed in PR #313.
- Current Catalyst product specification and delivery plan linked above.

[export-spec]: https://github.com/DIGI-UW/openelis-work/blob/main/designs/reports/custom-data-export.md
[export-readiness]: https://github.com/DIGI-UW/openelis-work/blob/main/designs/reports/custom-data-export.md#14-design-revision-and-implementation-readiness
[export-pr]: https://github.com/DIGI-UW/openelis-work/pull/320
[preview]: https://digi-uw.github.io/openelis-work/#/reports/custom-data-export
[gallery]: https://digi-uw.github.io/openelis-work/catalog.html
[report-management]: https://github.com/DIGI-UW/openelis-work/blob/main/designs/admin-config/report-management.md
[earlier-catalyst]: https://github.com/DIGI-UW/openelis-work/blob/main/assets/requirements-docs/catalyst-functional-requirements.md

[integration-preview]: https://pmanko.github.io/clinical-ai-validation-harness/catalyst-design/?view=integration
[integration-design]: https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specs/openelis-reporting-integration/spec.md
