# OpenELIS reporting and Catalyst integration

**Status:** Mock/spec construction approved on 10 September 2026. Two parallel
delivery streams meet at a real source connection and CSV/Dataset parity review.
The first new checkpoint is the integrated mock/spec set below; owner design
acceptance and production implementation remain separate.

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

## Approved next checkpoint: create and review the mock/spec set

The clarification session established these decisions:

- OpenELIS reporting is fully independent of AI and Catalyst.
- The applications open independently with shared organizational sign-in and
  equivalent lab-unit/identifying-field access. No application links, embedded
  Catalyst or report-criteria transfer are included.
- The first OpenELIS mock covers configurable CSV export, saved configurations
  and My Report Queue. Patient printing and Jasper replacement remain separate.
- The common example is monthly virology results. CSV/Dataset comparison is
  solely our parity review, not a staff-facing comparison feature.

Build the interactive mock and one integration design specification in Catalyst's
existing design documentation, reusing the approved Workbench assets directly.
Keep the applications separate in the reviewer hub. Include preparation versus
explicit execution, retained drafts, source-bound sessions, save/reopen, queue
failure/retry/expiry, fresh dates after loading a configuration, shared sign-in
and restricted-access examples. All data and identity behavior are fictional.

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

Review artifacts: [integration draft][integration-preview] · [design specification][integration-design] · [Catalyst design PR #98](https://github.com/DIGI-UW/catalyst-ai/pull/98).
The design source lives in Catalyst; the harness keeps a generated publication
copy. The review hub's source link and `source.json` identify the exact published
revision, independently of the runtime Catalyst pin.

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
| [Custom Data Export & My Report Queue, v1.1][export-spec] — OGC-479 / OGC-481 / OGC-483 | Reuse the existing draft for the wizard, saved choices and personal export queue. It couples export and required asynchronous retrieval in one release. Keep the stories distinct. |
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
| Smallest export and replacement scope | Select an initial reporting scenario; confirm fields, date meaning, lab-unit and other filters, result/order status, saved choices and completed-output delivery. Decide whether the routine CSV entry point is replaced or coexists. Jasper and patient-report replacement remain separate questions. |
| Data meaning and coverage | Define what one row represents, joins, duplicate handling, derived values, units, missing values, status interpretation and date boundaries. Explain incompatible selections separately from permission restrictions. Verify mappings against actual data. |
| Execution and database impact | Evaluate the OpenELIS export draft's native application query approach against a representative workload and an agreed acceptable effect on normal laboratory operations. Consider a read-oriented layer only where evidence justifies it. Verify reporting-field coverage/freshness on Catalyst's existing FHIR/Spark path separately; changing that selected reference path needs an explicit roadmap amendment. |
| Permissions and retrieval | Confirm who may request which fields/sections, when authorization is checked, ownership and download behavior, and what happens when access changes after submission. The export draft silently drops some unauthorized selections: decide how users learn that output differs from their request. A program filter is not a program-access policy. |
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
| 0. Build and review the mock/spec set | Interactive independent OE/Catalyst workflows and review-only parity examples; published source revision; browser, screenshot and documentation checks; explicit owner design review. | Mock/spec constructed and locally validated; source publication in this PR; owner design acceptance pending. |
| 1. Agree where the streams meet | Reviewed initial report/comparison definition; field coverage on the existing source path; disposition of overlapping proposals; named ownership and links to each product's tasks. | Two-stream direction confirmed; specific scenario and ownership pending. |
| 2A. Build from OpenELIS | Settle export permissions/workload choices; deliver the bounded export, saved choices and required queue; generate a verified CSV and prepare the source mapping/access information. Link existing OE issues, PRs and real-path evidence. | Implementation/release status not audited; existing draft is the starting point. |
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
- Current Catalyst product specification and delivery plan linked above.

[export-spec]: https://github.com/DIGI-UW/openelis-work/blob/main/designs/reports/custom-data-export.md
[preview]: https://digi-uw.github.io/openelis-work/#/reports/custom-data-export
[gallery]: https://digi-uw.github.io/openelis-work/catalog.html
[report-management]: https://github.com/DIGI-UW/openelis-work/blob/main/designs/admin-config/report-management.md
[earlier-catalyst]: https://github.com/DIGI-UW/openelis-work/blob/main/assets/requirements-docs/catalyst-functional-requirements.md

[integration-preview]: https://pmanko.github.io/clinical-ai-validation-harness/catalyst-design/?view=integration
[integration-design]: https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specs/openelis-reporting-integration/spec.md
