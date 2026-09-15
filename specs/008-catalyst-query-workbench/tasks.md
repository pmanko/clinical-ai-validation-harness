# Catalyst integration and delivery tasks

**Status:** The owner approved usability-first delivery followed by Dashboard
Builder functionality. This file is the sole detailed progress and acceptance
register for the [Feature 008 roadmap](plan.md). Model comparison and broader
conversation work remain separately scheduled.

## Four-pathway delivery

The [integration roadmap](../openelis-reporting-catalyst-integration.md) owns
scope, iteration order and cross-pathway owner acceptance. This is the one
detailed Catalyst/shared-integration register; native implementation tasks stay
in OpenELIS's existing reporting register. Existing release tasks below remain
their own scope. Plan approval does not mark implementation or acceptance done.

| Task | Implementation and behavioral acceptance | Implementation | Checks | Merge | Local/server | Owner acceptance |
| --- | --- | --- | --- | --- | --- | --- |
| FP-001 | Persist the approved roadmap; reconcile authorities and existing work; refresh linked dashboard records without duplicate checklists. | Harness authority/inventory aligned; product alignment in Catalyst #127; native cleanup assigned to its implementation owner | 25 focused tests, five dashboard tests, documentation checks and site build pass; harness CI passes | Harness #173 merged as b21a920 | Dashboard inspected locally and published through Pages | Direction approved; final consolidation review pending |
| FP-002 | Extend the existing integration mock/spec for CSV import, origin-aware Dataset review and PostgreSQL source selection. Preserve approved shell, drafts and explicit execution; review desktop/narrow and light/dark. | Catalyst #127 plus #128: upload within Saved work / Datasets and review-only Try CSV import shortcut | Six fixture tests and syntax checks pass; file/type/failure/cancel/retry, source/query/save and retained drafts checked in browser; desktop/narrow light/dark inspected; all five CI checks pass at 9728294 | #127 merged as 8524925; #128 merged as 5164449 | Exact merged design synchronized for publication; application runtime unchanged | Approved by owner on 14 September 2026; final application acceptance remains separate |
| FP-003 | Reuse the native reporting effort's actual export and saved-report rerun; verify lane-1 CSV, native Superset upload, table and summary chart. Record early FHIR field coverage against this same OE instance. | Native saved-period rerun and local Superset Dataset 32/dashboard 32 | Native owner verified blank dates on reopen, May5/May6 exports; local native upload preserves text IDs/order, table 63 and chart 64 render 1158→30 and 1159→90; screenshot/reopen checked | Native PR status separate; harness baseline #177 merged | Same-instance local example verified; broader fixtures and server journey pending | Pending |
| FP-004 | Ordinary PostgreSQL connection, complete readable catalog, parameters/types/bounds, editor, native question/refinement/Run/save/reopen. Reuse compatible history; retain Spark behavior and no relation allowlist. | Connection/catalog/types/bounds and editor implemented in Catalyst #129; native workflow integration remains | 389 Gateway tests including real PostgreSQL, 302 UI, 17 browser and 57 assembly tests passed; all five hosted checks green | Catalyst #129 merged as 6513c88 | Code deployed locally at c91ae23 with harness a988bb8; native-source connection and full lane proof remain | Pending |
| FP-005 | Resolve publication by actual Dataset backing connection and declared dialect. Preserve exact saved artifacts, deterministic bundles, retry/receipts and verify PostgreSQL/Spark rendering. | Query-backed source resolution and dialect-aware compiler merged in Catalyst #130; imported-file publication follows FP-006 | 403 Gateway tests including real PostgreSQL, 50 final focused checks, legacy bundle byte parity and all five CI checks pass at 6ad1d09 | Catalyst #130 merged as 3b8882f | Code deployed locally at c91ae23; imported table rendering verified below; native query-backed rendering remains | Pending |
| FP-006 | Add origin-aware Dataset contracts and CSV upload/review/confirmation with durable import storage. Verify types/order/values, no fabricated SQL, invalid/empty/interrupted import, retry, reload/restart and existing saved artifacts. | CSV upload/type review, durable drafts, immutable PostgreSQL storage and raw-table publication implemented in Catalyst #131; grouping remains FP-007 | Latest 70 focused backend checks including real PostgreSQL, 306 UI checks across full/retry runs, real Gateway import browser journeys in light/dark; desktop/narrow screenshots inspected; all five hosted checks pass at 0011cd7 | Catalyst #131 merged as c91ae23; upload-size repair #132 merged as 4d41978 with all five checks green | Retained local a988bb8/c91ae23 verified through wrapper health, unchanged mounts/ports and both-theme browser checks. Native May6 CSV yields exact 1158→30 and 1159→90 rows in Catalyst and Superset chart 65. Server and broader fixtures remain | Pending |
| FP-007 | Shared meaningful chart controls over imported rows, including grouping/counts. Verify values, immutable versions, saved arrangement and publication without required SQL interaction. | Approved controls and aligned mock/contracts implemented in Catalyst #133; #134 repairs PostgreSQL publication for an ungrouped whole-file summary and advances its mapping revision | #133: 440 Gateway, 309 UI, 26 component and five real CSV/browser checks. #134: 443 Gateway checks against PostgreSQL plus all five hosted checks; count/sum/average regression uses 122 persisted rows beyond the preview bound | #133 merged as f548e04; #134 merged as a15ecb8 | Retained runtime at harness f0ff2c7/Catalyst f548e04 preserves saved artifacts. Native Superset shows count 2 and average 60; ungrouped total exposed the repaired adapter defect. A 101-row table proves native pagination. Apply a15ecb8 and verify total 120 plus retained results next | Chart-control design approved 14 September; application/lane acceptance pending |
| FP-008 | Consume the reporting instance's real FHIR output through existing Data Pipes/Spark; verify useful query/Dataset/dashboard, record provenance and explain coverage/freshness differences. | Existing reference path; reporting-instance emission/routing pending | None of the four known reporting Observation IDs found in local Catalyst HAPI; native owner has no emission proof | Pending | Existing separate cohort is not reporting-instance parity | Pending |
| FP-009 | Exercise four complete local journeys, compare approved mocks at desktop/narrow and light/dark, inspect rendered values, retain drafts/state, record findings and owner review. | Pending | Pending | Pending | Pending | Pending |
| FP-010 | Deploy compatible reviewed revisions with retained data; prove four server journeys and deliver the [four-pathway videos and openclinai.org review checkpoint](../openelis-reporting-catalyst-integration.md#review-checkpoint-four-pathways-videos-and-public-explanation), including readable recordings, live playback, local evidence links and reconciled authoritative documents. | Existing homepage draft explains four pathways and separates earlier videos; four new recordings remain pending | 10 landing tests passed; desktop and 390px review-frame screenshots inspected | Homepage draft in harness #183 | Local preview only; public section/server recordings pending | Pending |

AI-assisted Widget/Dashboard refinement remains the existing
[Follow-on A](#follow-on-milestones-after-current-delivery), not another task
family here. Its context must support both Dataset origins; file imports must
not acquire fabricated SQL provenance. Shared identity/per-user authorization
remain a later production milestone in the integration roadmap.

## Immediate four-pathway test checkpoint

Owner direction, 15 September: prioritize four runnable paths for a short owner
test. Run a bounded smoke per lane, record its first failing step, fix that
integration, and repeat the path. This advances FP-003 through FP-009 without
replacing full local/server acceptance. CSV tests do not depend on AI availability.

Latest local check: retained checkout `~/code/catalyst-dev`, Catalyst `b90f95f`
(merged as `387de1e` in [repair PR #135](https://github.com/DIGI-UW/catalyst-ai/pull/135)); harness
integration remains in [PR #183](https://github.com/pmanko/clinical-ai-validation-harness/pull/183).
Local testing used `b90f95f`; the checkout now pins its identical merged tree. Neither server deployment nor owner
acceptance is claimed.

| Lane | Observed working step | Next obstacle to resolve |
| --- | --- | --- |
| 1 | Fresh native May5 CSV uploaded through Superset's native API into Dataset 38. Browser-created table 80 preserves column order and IDs 1154/1155, both value 450; chart 81 groups by accession and counts 2. Dashboard 38 saves/reopens and its rendered screenshot was inspected. Earlier dashboard 32 remains a separate May6 interval example. | Browser file attachment, broader fixtures, paced recording and server journey remain. API upload is partial evidence, not the complete recorded user journey. |
| 2 | Existing imported CSV retains both rows. Repaired publication now renders count 2, average 60 and total 120 in Superset; screenshots inspected. | Fresh native upload/type-recovery/save and browser chart/arrangement/publication smoke now pass (details below). Browser file-picker automation, narrow/theme review, broader failures and server validation remain. |
| 3 | `openelis-reporting` uses a restricted PostgreSQL reader and discovers all 380 readable relations. Browser schema search preserves the draft. Explicit manual execution returned IDs 1154/1155/1158/1159 with values 450; Dataset `1dd3de0a-6754-4cc2-9097-56a49cb3c8dd` saves and reopens with the correct source. Its table dashboard publishes/imports and renders all four exact rows in Superset. | Model preparation rejects the complete schema: 63,582 input tokens exceed 24,576 configured context. Resolve model capacity, then prove the complete question/refinement journey. Manual execution does not complete that journey. |
| 4 | Existing Spark/HAPI services run. Native owner verified the reporting instance still points at an isolated loopback FHIR endpoint; Catalyst's existing endpoint requires its trusted client connection. | Native owner is connecting the retained app using the existing Catalyst network/certificates, with metadata/readiness first. No seeding/backfill or real reporting FHIR emission has been performed. |

Retained services and model router were restored through existing launchers,
without seeding or replacing data. A newly opened manual session still requires
an available model profile; the unavailable-profile response was reproduced
before router recovery and remains a product finding.

Actual Superset reimport exposed an additional publication defect: dashboard
import keeps existing chart UUIDs, so the SQL repair alone left old charts active.
Merged PR #135 includes the generated mapping in native chart identity, preserving the
Dashboard address and saved versions. The successful local import bundle digest
is `ba09c4c8e75bf91c2adba6ab5c53c33e83cc2e3000f623f64fe4db9314cbc851`.
The rendered CSV Dashboard is
`http://localhost:18088/superset/dashboard/catalyst-913de3ca-ae7a-48aa-9f36-8b7421345b83/`.
PostgreSQL table dashboard `955959c8-0b99-4bfd-991b-0523c32c4360` renders the
four exact result/analysis/value rows (screenshot inspected), using bundle
`ef96afe25250fb1739e6830bceb0c8c76e9474f6a25673abc96c00df4d47c67e`.
All five Catalyst PR #135 CI checks passed before merge.
Publication/fixture tests: 25 passed; focused lint/type/diff checks passed. The
broader Gateway run had 419 passed, 25 skipped and the expected fixture mismatch;
the regenerated fixture subsequently passed its focused checks. Raw evidence
and runtime credentials remain outside Git. Repository-wide OpenMRS CI is owned
by its separate effort and is not being repaired in this Catalyst task.

Fresh native Superset lane-1 smoke (15 September) uses the same May5 CSV and
checksum as lane 2 below. The supported native upload endpoint returned 201;
the dedicated Reporting CSV uploads connection created
`report_uploads.oe_native_may5_c6ace949`, Dataset `38`. Identifier columns remain
text and the value column is numeric. Browser controls created/saved raw table
`80` and grouped-count chart `81`; reopening
`http://localhost:18088/superset/dashboard/38/` restored both exact result rows
and count 2. The visible screenshot was inspected. The dashboard remains a local
Superset draft; this is not public publication or owner acceptance. File-picker
automation remains unsupported in the current browser-control surface.

Fresh native-file lane-2 smoke (15 September): the recovered native detailed CSV
`reporting-detailed-2026-05-05.csv` has SHA-256
`c6ace94933a1e2377d28d3d89bf96995e46474b0009c6594c8eece8e1cad56f4`.
The application upload API accepted those exact bytes; invalid numeric conversion
was rejected at confirm, retained its draft/error, and succeeded after type
correction. Identical confirmation retry retained Dataset version
`2072efc1-129b-4c4d-acb9-6f4a0c5fcd06`. Every returned value and column matched
the file, preserving the two distinct repeated result records.

Browser review then opened that Dataset, saved a full-row table and a record-count
chart grouped by accession, retained the chart draft across close/reopen, and
saved/reopened table-first order with full/half-row widths. Explicit browser
publication showed Bundle ready before the operator import and Imported/Open
Superset afterward. Dashboard `d050f4a1-e68a-4d39-b722-0f990f62e94b` renders both
native rows and grouped count 2, with the saved layout; screenshot inspected.
Import bundle: `55b3a1ff5fe8d5369a992a390ef42865a1f6592db01e9dbf0b8c068789a7be93`.
No SQL or model request was needed for the import/chart/dashboard path. The
browser-control surface does not support file attachment, so initial upload/type
review/save used the actual application endpoints, not browser controls. The
remaining browser-file-picker check is explicit, not treated as passed.

Dashboard validation also passed its five model tests and production status
build. Cached GGUF metadata declares Gemma E4B context 131,072 and Qwen 14B context
32,768; the existing serving configuration is 24,576. The proposed existing
E4B-only profile/larger-context test is awaiting owner preference. FHIR runtime
connection remains pending the native task's approval review; normal emission
has not run. These are not four-pathway or server acceptance claims.

## Current local reporting checkpoint

On 15 September, the retained local stack was updated through the lifecycle
wrapper to harness `f0ff2c74b5f50a1415f90961a6648937cefddc13` and Catalyst
`f548e04d4dcc4220ff211b7783fa5a842cb40127`. Health and strict repository checks
passed; retained mount destinations, ports, 72 Datasets, 67 Widgets and 64
Dashboards matched the pre-update receipt.
The same native May6 CSV used for lane 1 was imported through Catalyst and
published through the owning checkout's native Superset importer. Dataset
`30d520f1-460e-475d-98d9-56596233efad` and its detailed table preserve the two distinct
results: IDs 1158/1159, values 450/450 and intervals 30/90. The file checksum is
`ed64b5bd7a084f56d0bc712f8305dcb41eca90ffbe73a45cf3f0f125a2e38680`.
The local Superset dashboard was inspected alongside Catalyst's saved rows.
Count renders as 2 and grouped average as 60. A separate 101-row imported table
renders rows 1–100 and row 101 on its second page, proving the configured bound
does not hide later rows. Raw receipts/screenshots remain outside Git. This is
local validation, not server or owner acceptance.

Two presentation findings stay with FP-007: native Superset's small
raw table shows “0 entries per page” despite a saved page size of 100, and its
search selector shows the physical field name. Pagination itself is verified
above. The local proxy now accepts supported files above 1 MB and retains an
actionable response above 10 MB. The summary run also exposed one functional
finding: an ungrouped total emitted a bare text constant that PostgreSQL treated
as an invalid grouping position. Catalyst #134 changes that axis to an explicit
text expression and advances the imported-summary mapping revision; its 443-test
Gateway suite and all five hosted jobs pass. Pin, deploy and verify the expected
total of 120 next. Server deployment, four complete pathways and final owner
acceptance remain open.

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

The retained local release runs from `/Users/pmanko/code/catalyst-dev` at
`localhost:13000`, on merged harness `8cd18f6` with both real sources.
The server checkout is `/home/ubuntu/catalyst-release` at `78169be`.
Both retain Catalyst `a59d883` and Hub `6120c31`; the UI-only rollout tracked
below updates the harness and Catalyst pins without replacing backend services.
Separate UI development and its owner review do not change this release evidence.

The owner merged Catalyst #117 (`ed22781`) on 12 September and requested a live
rollout. That UI was deployed through harness #160 (`f4998f5`) and is retained in
the current release, along with parser repair `699d700`. Local/server light/dark
browser checks confirmed the new assets and retained results. The public design
copy's 11 asset hashes match `ed22781`. The earlier video predates this UI patch;
final visual and owner acceptance remain separate.

## Current release integration — 11 September 2026

The owner authorized this sequence: roadmap #142, combined Catalyst #106–#109
and Hub #25–#27, router #143 with exact merged pins, local/server deployment,
then the OpenMRS replacement recording and publication in #141 (now merged).
The 12 September replacement below is its follow-up. #134 merged separately as
reporting-planning documentation; #111 remains a separate dashboard draft.

| Deliverable | Implementation and merge | Validation | Deployment / acceptance |
| --- | --- | --- | --- |
| Roadmap #142 | Merged as `6d7a327` | All PR checks passed | Authoritative plan updated |
| Catalyst #106–#109 | Merged as `f2a46b0`; baseline pin `1fd4a03` adds the recording-only correction | Combined tree: 364 Gateway tests passed, one existing skip; 294 UI tests; 16 deterministic browser checks, eight live-only skips; type/lint/build passed; final #106 CI passed | Running locally and on the server; full workflow acceptance pending |
| Hub #25–#28 | Merged; baseline pin `1ddaa1e51ebb88735808ae9775ec046ba0b3101b` | #25–#27 combined suite: 720 tests passed; #28: 71 focused tests and CI passed | Running locally and on the server; local OpenMRS query-grain check passed |
| Router #143 and release follow-up #144 | Merged as `a6980ce` and `b6fe09a` | Release CI passed; five router tests and 18 focused router/documentation/repository checks passed | Server router repair deployed at `735ad53`; persistent local source continuity verified; cold-query and full server workflow acceptance remain open |
| Replacement OpenMRS walkthrough / #141 | Corrected local take 8 passed on runtime `b6fe09a`; recorder fix #110 merged as `1fd4a03` | Full real-model browser test passed: monthly totals preserved, saved SQL reused, two visualizations arranged, repeat publication/import and rendered Superset checked | Merged as `dfee0e2`; both videos and posters published and verified over HTTPS; owner acceptance separate |
| Hub #29/#30 and Catalyst #118 lifecycle warmup | Merged as `88b48c4`, `d806c90`, and `2f85f1c`; harness #156 pins the compatible baseline as `ecf8647` | Hub #29: 32 focused role/lifecycle tests; Hub #30: 35 focused tests; Catalyst: 27 focused warmup/query tests; all hosted CI sets passed | Local and server two-source lifecycle warmups passed. Ordinary-question evidence remains separate. |
| Normal query lifecycle and Spark-function diagnostic | Hub #31 `6120c31`, Catalyst #119 `a1f52cc`, and Catalyst #120 `742ee58` are merged; harness #157 pins them as `a5703cc` | Hub #31: 716 tests; Catalyst #119: 367 tests; Catalyst #120: 366 tests, each with hosted CI green | Exact release deployed; local post-warmup source switching and the OpenMRS replacement capture passed. Server ordinary-question completion remains open. |

### 12 September release evidence

- **Deployed repair:** harness #159 (`b632d2c`) pins merged Catalyst #124 (`699d700`) with
  unchanged Hub `6120c31`. Tokenization errors now reach the existing model
  correction flow, retaining raw non-executable evidence on failure. Six
  regression cases cover Spark backticks, unfinished string literals, model
  correction and retained diagnostics. Gateway tests: 374 passed, one existing
  skip; formatting, lint and all five hosted CI jobs passed. Type checking
  reports 10 findings in unchanged analytics/service files. Harness verification:
  31 focused tests, documentation consistency, local links and repository-line
  checks passed; hosted CI passed. Deployment and the three ordinary questions
  now pass on this pin in both environments.
- **Runtime:** harness #162 (`8070237`), Catalyst #125 (`a59d883`), and unchanged
  Hub `6120c31` are deployed locally and on the CPU server. The strict
  repository-line checks and both lifecycle health gates passed. Server neutral
  warmup completed for both sources. Model configuration and datasets are retained.
- **Local neutral-warmup validation:** OpenELIS test counts, OpenMRS encounter
  counts, and a return to OpenELIS for distinct patients all prepared and executed
  through Catalyst. Their recorded writer requests contain no warmup exchange or
  conversation history. The model processed 523, 528, and 516 new prompt tokens
  for requests containing 14,965, 8,930, and 14,964 tokens respectively; the
  source-specific warmups processed 14,960 and 7,483 tokens. These are observed
  cache reuse and source-switch behavior, not speed requirements. One explicit
  local client Stop after writer activity returned `generation_cancelled`,
  released both model slots, and executed no SQL.
- **OpenMRS replacement:** local take C passed the complete real-model browser
  path with the planned Gemma 4 12B writer and Qwen 2.5 14B reviewer. Both queries
  were model-authored and approved; all six monthly totals survived refinement.
  Exact saved SQL was reused, table and time-series chart arrangement persisted,
  repeat publication retained its digest, and imported Superset rows matched.
  Merged Catalyst #123 makes the date-valued month requirement explicit in this recording
  and checks chart compatibility before selection. Type checks, lint, the live
  OpenMRS scenario, and all five hosted CI checks passed.
- **Observed limitations:** an earlier E4B/reviewer take doubled monthly counts
  despite reviewer approval; the unchanged total-preservation assertion rejected
  it. A successful 12B take does not resolve that E4B reliability finding.
  Catalyst #117 is deployed but is not included in the capture. Final visual
  and owner acceptance remain open.
- **Private evidence:** raw capture, requests/results, trace, screenshots and
  revision manifest are retained in the local Movies/Catalyst archive. The 3:56
  final cut completed normal-speed playback review and uses a ten-second data-pipe
  introduction, longer title cards, captions below the footage, labelled fast
  waits, and normal-speed interactions. Its MP4 and poster are published under
  immutable September 12 URLs; HTTPS bytes match the local SHA-256 hashes.
  Publication #158 merged as `0df04b8`. The landing-only publisher ran from
  that merged revision, and live HTML matches it byte for byte. Browser review
  confirmed the new poster, video and 3:56 label; earlier YouTube links remain.
- **Server ordinary questions:** OpenELIS test counts, OpenMRS encounter counts,
  and a return to OpenELIS for distinct patients all prepared and executed on
  `b632d2c`. Their recorded requests contain no warmup exchange. Catalyst #124
  repaired the previously observed unfinished-backtick tokenization failure;
  that failure was not a timeout.
- **Server refinement finding:** the gender breakdown of those OpenMRS visits
  produced syntactically valid SQL but zero rows. The candidate joined
  `encounter_flat.patient_id` to `patient_flat.identifier_value`; the checked-in
  source views define the patient resource key as `patient_flat.id`. The
  inner join also fails the requested retention of unmatched patients. External
  corrective-feedback attempts ended with `generation_cancelled` before producing
  an answer. The same payload subsequently completed through the server-local
  application API with the unchanged E4B profile (turn `aa9090e1`), using the
  patient resource key, a left join and distinct encounter counts. Its exact
  model-created SQL was executed from the browser: nine rows, with all five
  original encounter-type totals preserved (28,564 visits). No SQL hand edit,
  prompt change, model switch or new deadline was applied. The returned result has no
  missing-gender row, so that branch is supported by SQL inspection rather than
  observed fixture coverage. The failed candidates and corrected result remain
  separate private evidence. Laptop power logs show sleep during both the second
  browser failure and the public-API diagnostic; this confounds attribution to
  a server connection limit. The subsequent public-browser follow-up (turn
  `88887517`) completed with temporary sleep prevention and the unchanged E4B
  profile. Its exact model-created query executed from the browser; all nine
  aggregate rows matched the prior result and were sorted by encounter type,
  then gender as requested. Preparation did not execute SQL. Router evidence
  records 12,282 processed prompt tokens and 274 generated tokens; its roughly
  24-minute model invocation is an observation, not a response-time target or
  acceptance of responsiveness. The temporary sleep assertion was stopped after
  verification. No connection failure reproduced in this controlled run.
- **Server saved work:** the successful OpenELIS result was saved through the
  application API, with a table, chart and a second Dashboard version preserving
  the changed arrangement. Browser review confirmed the nine recorded rows and
  the reversed two-widget arrangement; publication produced a ready bundle.
  Import initially failed because the Gateway's root-owned bundle had mode
  `0600`. A narrowly scoped operational group/mode correction allowed the exact
  bundle to import; its receipt is persisted and the library shows Imported.
  Catalyst #125 (`a59d883`) makes the existing outbox group and mode `0640`
  permanent at publication, including repeat publication without changed bytes.
  Gateway tests: 374 passed, one existing skip; all five CI jobs passed. This
  release is deployed through harness #162 (`8070237`). Local and server repeat
  publication created mode `0640` automatically and retained the exact bundle
  bytes; the Linux server also retained the expected outbox group `1000` on the
  newly replaced file. Both wrapper imports returned `already_imported`. The
  public proxy's missing Dashboard route and stale Catalyst
  API deadline were repaired with a backed-up, validated graceful reload.
  The configured server credential works in the public browser; the local default
  is not the server credential. Both rendered-result checks passed on 13 September
  (see the closeout entry below). The corrected
  OpenMRS query was saved from the browser as Dataset version `ac279460`, then
  used for a table and grouped-bar chart. Dashboard version `c74e05e0` restores
  chart then table, each at half width; both order and widths were checked in
  the browser. Repeat publication preserved bundle digest
  `81358e8af557f13c404396f4d06286152a60b74010735b9fd608fd3e624abfb2`.
  The native import ran from the server checkout and returned receipt
  `049b44e0-83ce-466a-8aa1-7eb8ccd5e3cf`; the library displays Imported for both
  sources. Full requests, rows, receipts and screenshots are retained privately
  under `Movies/Catalyst/2026-09-12/release-evidence/8070237`.
- **Visual release:** harness #160 (`f4998f5`), Catalyst `ed22781`, and unchanged
  Hub `6120c31` were verified locally and on the CPU server. Browser light/dark
  checks
  confirmed the new assets and retained results on both; local draft text
  survived composer resizing, theme changes and Advanced mode. Server health
  and both neutral warmups passed. All 11 published preview assets match the
  approved Catalyst source. These checks do not constitute owner acceptance.

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
- [X] Correct the router preset to match ChartSearchAI's 4,096/1,024 batching;
  remove the arbitrary five-second cancellation probe, its tests, and the
  generation-smoke deadline, as explicitly directed by the owner.
  The earlier 128-token preset and cancellation timing gate are superseded.
  This changes neither model/prompt selection nor the downstream disconnect fix.
  [Harness #165](https://github.com/pmanko/clinical-ai-validation-harness/pull/165)
  merged as `78169be`; the corresponding local preset change in
  [#166](https://github.com/pmanko/clinical-ai-validation-harness/pull/166)
  merged as `8cd18f6`. Both hosted CI sets passed, with 11 existing server-router
  tests and 27 existing local-router policy tests passing locally.
- [X] Apply the correction to the CPU server and persistent local development
  checkout through their existing router lifecycle scripts. On 13 September,
  the server ran `78169be` and local ran `8cd18f6`, both with unchanged Catalyst
  `a59d883` and Hub `6120c31`. The running server child process and both restored
  local models were verified with 4,096/1,024 batch arguments. Strict repository
  verification and application health passed; neutral warmup completed for
  OpenELIS and OpenMRS in each environment. Model files, sampling, retained data,
  and the local model catalogue and two-model capacity were preserved. No new
  performance benchmark or timing criterion was introduced. Rollout logs and
  hashes are in the private release receipt under
  `Movies/Catalyst/2026-09-12/release-evidence/8070237/batch-correction-20260913`.
- [X] Recheck the published replacement after the rollout: the current OpenMRS
  MP4 and poster return HTTP 200 and match the reviewed SHA-256 hashes; the
  OpenClinAI homepage still references them and retains both YouTube convenience
  links. This confirms publication, not final owner acceptance.
- [ ] Resolve remaining long-running first-query and varied cross-source failures;
  complete the real saved-work through Superset journey for both sources before
  closing server acceptance. Videos are already published and remain local work.

## Release closeout — 13 September 2026

- [X] Verify the actual public Superset dashboards after authenticated sign-in.
  OpenMRS: all nine encounter/gender rows match the saved Catalyst execution,
  totaling 28,564 visits. OpenELIS: all nine test groups match, with eight groups
  of 96 and Viral Load 384. Rendered tables and charts were inspected; comparison
  uses retained Catalyst results, not a separate SQL replay. Private evidence:
  `Movies/Catalyst/2026-09-12/release-evidence/8070237/`
  `superset-browser-verification-20260913/verification.json`.
- [X] Confirm Catalyst and CSiM deployment isolation: distinct Superset containers,
  metadata stores, volumes and proxy routes. No credential reset or CSiM change.
- [ ] Merge and apply the composer cleanup: padded Available data button; stable
  bottom clearance in narrow/wide layouts; no inner focus-border collision;
  shared Query settings dialog preserving profile, draft, focus and Stop behavior.
  [Catalyst #126](https://github.com/DIGI-UW/catalyst-ai/pull/126) is merged as
  `bb783c8`; all five hosted checks passed on its reviewed head. Harness #169
  pins this revision with unchanged Hub `6120c31` and adds a UI-only lifecycle
  update that leaves dependencies running. Runtime update and owner review
  remain separate.
  Unit suite: 300 passed. Deterministic browser suite: 17 passed, with 8 live-only
  scenarios skipped. Build and lint pass; existing bundle-size warning remains.
  The UI-only wrapper path has 19 passing focused lifecycle/layout tests,
  including retained isolation settings, dependency exclusion and failure
  propagation; ShellCheck passes. Exact-head harness CI is required before merge.
- [ ] Remediate snapshot pollution at the FHIR Data Pipes source boundary.
  Current local discovery exposes OpenELIS 10 stable views + 30 snapshot tables
  and OpenMRS 12 stable views + 12 snapshot tables. The pinned controller creates
  both in the same JDBC database. A clean current-data namespace preserving the
  original snapshots/saved SQL is proposed; the owner's history-browsing choice
  is pending. No tables, snapshots or source connections have been changed.
- [ ] Correct the Superset header logo/base-link visual defect.
- [ ] Deploy the merged cleanup through the harness wrapper and compare both
  real sources with the approved design in light/dark and narrow/wide layouts.
  Synchronize any required video/public references, then record owner acceptance.

## Next checkpoint — neutral-question warmup

- [X] Merge [Harness #155](https://github.com/pmanko/clinical-ai-validation-harness/pull/155),
  pinning Hub `88b48c4` and Catalyst `2f85f1c`; run the strict repository-line
  check from `main` before using these revisions locally or on the server.
- [X] Merge the follow-up pin for Hub `d806c90`, which removes the remaining
  client-level deadline only from lifecycle warmup, as harness #156 (`ecf8647`).
  Do not turn a diagnostic observation into a product timing requirement.
- [X] Implement a finite warmup through the existing lifecycle wrapper using
  “What information is available in this data source?” with each configured
  source's complete schema and ordinary writer profile. Discard the exchange;
  create no sessions, previews, saved examples, guidance, generated SQL, or
  clinical-row retrieval. Use only live schema metadata discovery. Catalyst
  #118 and Hub #29 establish the lifecycle route; Hub #30 also removes its
  underlying client deadline. Normal question transport and its Stop behavior
  are unchanged.
- [X] Verify with a different real question on each local source that common
  instructions/schema are reused and the warmup question/answer are absent from
  its request. Check switching sources, cache misses, failures and explicit Stop.
  The 12 September evidence above records actual cache reuse, a cold initial
  prefix, source switching, and explicit cancellation; model-loaded health alone
  is insufficient.
- [X] Merge the tested changes and pin the exact compatible Catalyst revision.
  [Catalyst #111](https://github.com/DIGI-UW/catalyst-ai/pull/111) merged as
  `c0a1b431`; [Catalyst #112](https://github.com/DIGI-UW/catalyst-ai/pull/112)
  merged as `18bd9ef2`. Hub #29 and Catalyst #118 supersede that deployment
  pin for warmup; harness #157 (`a5703cc`) records their later integration.
- [X] Deploy through the lifecycle wrapper to the existing CPU server and
  preserve retained data. Both lifecycle warmups passed on harness `a5703cc`.
- [X] Verify ordinary preparation and execution against both server sources;
  Catalyst #124 resolves the tokenization handling failure. The unchanged
  OpenMRS count and OpenELIS → OpenMRS → OpenELIS sequence pass on `b632d2c`.
- [ ] Complete the server refinement and saved-work-to-Superset journey on both
  sources, retaining the incorrect-join observation and any correction separately.
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

The 11 September owner review found misleading “unreviewed” badges and
formatting-only “human” versions despite recorded reviewer approvals. Public
recapture must fix both and focus on model-created SQL and plain-language
refinement. Include only one brief model repair of supplied broken SQL across
the two videos; retain deliberate engine-error/retry coverage separately.

- [X] Correct review recognition and formatting provenance, with regression tests
  ([Catalyst #106](https://github.com/DIGI-UW/catalyst-ai/pull/106), merged
  `f2a46b0`); focused tests and hosted CI passed.
- [X] Recapture both light-mode stories with actual reviewer decisions, one brief
  supplied-SQL repair, matching Superset results and no staged manual fixes.
  OpenELIS passed on 11 September; the successful 12 September OpenMRS replacement
  and rejected earlier takes are accounted for in the release evidence above.
- [X] Review the new cuts at normal speed and replace public video/poster links.
  Publication #141 (`dfee0e2`) and its replacement #158 (`0df04b8`) are merged;
  current page, MP4 and poster hashes were verified. Owner acceptance is separate.

The OpenELIS 3:04 light cut includes one 26-second supplied-query repair. Earlier
OpenMRS takes that changed monthly totals or produced inconsistent output names
were rejected; the later successful capture retains those checks. Scenario
verification does not establish general clinical correctness.

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
- [X] Remove the automatic total generation deadline from the normal
  Gateway-to-Hub named-role path. Hub #31 (`6120c31`) and Catalyst #120
  (`742ee58`) are merged with their full hosted CI sets green. Hub tests cover
  disconnect-driven cancellation and model-slot release; Catalyst tests prove it
  sends neither a timeout header nor a client deadline. Explicit Stop, retained
  draft/result, and incomplete-response handling remain product behavior and
  must be proven again in the exact two-source release. This removes an arbitrary
  cutoff; it does not set a substitute timing target or change model logic.
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
- [X] Withdraw the proposed timing targets. Record observed cold/warm behavior,
  cancellation, source switching and contention as evidence, without treating an
  agent-selected duration as a product requirement.
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
- [X] Record and verify the current OpenMRS replacement locally after the exact
  post-#119/#120 release. Keep light mode throughout, use model-created Spark
  SQL, and make its workflow distinct from the published OpenELIS cut. Do not
  record on the server or manually edit SQL to bypass a model/dialect failure.
  Local take C on `a5703cc`/`742ee58`/`6120c31` passed and was published through
  #158. The recording predates the later #117 visual patch.
- [ ] Record final local/server evidence, current public links, and explicit
  owner acceptance before marking this delivery complete.

## Question-led video gallery

- [X] Record the owner's 13 September approval in the existing delivery plan.
- [X] Produce three short clips from the verified local source recordings:
  OpenELIS patient count, OpenMRS monthly CD4 counts, and gender refinement.
  Preserve caption/result reading time, light appearance and labelled fast waits.
- [X] Add the static question gallery with accessible video controls, exact
  prompts, observed outcomes, recording dates and expandable model details;
  link it from the existing homepage and screenshot story.
- [X] Review final cuts at normal speed, verify source/evidence identity and
  desktop/narrow browser presentation, and run relevant site checks.
- [X] Add light-mode screenshots of the reports index and a representative
  ChartSearchAI report to the homepage Evaluation section, with a caption
  describing the wider clinical and health scenarios the AI engine can support.
- [X] Capture the approved date-independent question, gender follow-up and visible
  correction locally with Gemma 4 12B and Qwen 2.5 14B. Preserve the failed
  refinement (5,314) and show the complete corrected result (1,792 + 864 = 2,656).
- [X] Save that corrected query, chart and table; arrange and import the Dashboard
  through the owning checkout. Independently verify the originating result,
  saved objects, bundle, receipt and every cell in the rendered Superset table.
- [X] Package the captioned question-to-Dashboard sequence with supporting SQL
  details and the existing historical evaluation/report screenshots.
- [ ] Merge and publish using the landing-only workflow; verify live page and
  media hashes and retain local MP4s. Owner review remains separate from publication.

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
