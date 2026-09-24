# CSiM reported issues and demonstrated coverage

Assessment: 10 September 2026. Dashboard implementation baseline:
`b0bfa88c1c9ff79304e09dfdc2e9cf6e80f4ee48`.

The demonstration addresses the reported date and filter problems, but it does
not close every CSiM issue. It uses the development dashboard's 21 charts with
invented records. Production equivalence and the WordPress user journey are not
established. A passing workflow means the stated example works; it does not mean
every related product defect is fixed.

## Ian's three issues and Beth's date report

| Reported problem | What the demonstration establishes | What remains |
| --- | --- | --- |
| **Dashboard transfers retain internal identifiers.** Ian's September 2 repair attachment explicitly maps chart IDs, filter exclusions and dataset targets. | Native import into an independent 6.1.0 instance changes all 21 chart IDs. Dataset SQL, UUID relationships, six filter defaults and exclusions match. The recorded imported dashboard loads and changes to Quarter correctly. | **Partially addressed.** The imported `chartsInScope` caches still contain source IDs in all six filters and the global configuration. The previous relationship check did not inspect these caches. Superset's newer importer includes a repair; that specific repair still needs an import test with changed IDs. Updating existing shared charts and production permalinks also remains unverified. |
| **Time Unit choices are global in the released version.** | The 6.1.0 menu offers Month/Quarter/Year through an instance restriction. The separate upstream snapshot gives CSiM Month/Quarter/Year and an hourly dashboard Hour/Day/Week on the same instance. Reload and native export/import preserve those lists and defaults. | **Fixed in the unreleased snapshot; workaround in 6.1.0.** The native setting is each control's `time_grains`, not the separately proposed dashboard-wide `time_grain_allowlist`. Production adoption needs a tested build containing the feature. |
| **Date labels do not adapt to Month/Quarter/Year.** | The full dashboard uses `2025-11`, `2026 Q1` and `2026`. The recorded trend checks the actual drawn labels and numerical results for all three units. | **Working label workaround.** Friendly month-name labels such as `Nov 2025` with independently chronological ordering are not demonstrated on the full comparison charts. A general Superset formatter that automatically follows the grain is not implemented. |
| **Beth: the alternate `time_aggregate` approach sorts but drops missing periods; other date filters remain inconsistent.** | Calendar joins retain absent periods. The fixture distinguishes February with no submissions, March with a valid zero, and April with submissions but no eligible denominator. Date filtering occurs before grouping; the partial-quarter example excludes January and retains the February–March result. | **Demonstrated for the stated examples.** The tests cover selected hospitals, locations and ranges, not every possible empty series or production data shape. This completes the calendar approach Beth proposed; it is not a new reporting requirement. |

Evidence: [date grouping](https://catalyst.openelis-global.org/superset/design/evidence/#time-grouping),
[partial date ranges](https://catalyst.openelis-global.org/superset/design/evidence/#date-range),
[native import](https://catalyst.openelis-global.org/superset/design/evidence/#native-import),
[released Time Unit workaround](https://catalyst.openelis-global.org/superset/design/evidence/#filter-options),
[per-dashboard snapshot fix](https://catalyst.openelis-global.org/superset/design/evidence/#dashboard-time-units).

## Other issues in the channel and client documents

### Time Period, Time Unit and the September 10 meeting

Beth's meeting transcript supplied in this thread makes the primary requirement
more specific: **keep the selected reporting window, grouping, labels and missing
periods consistent through ordinary dashboard use.** Per-dashboard lists of allowed
units address a separate configuration constraint.

A unit inside the Time Period editor describes the look-back window. The
dashboard's separate Time Unit control describes how charts group the selected
records. Two controls mentioning years do not make them interchangeable.

| Part | Required behavior |
| --- | --- |
| Time Period | Select the underlying observations, such as February–March 2026. |
| Time Unit | Group those selected observations into Month, Quarter or Year; it is not only a label selector. Quarter must not add January to that example. |
| Axis labels | Follow the selected grouping and stay chronological. A fixed Month–Year formatter cannot express all three groupings appropriately. |
| Missing data | Preserve missing periods within the selected window without turning absent observations into zero rates. A cohort with no test records can legitimately have no result. |
| Interaction state | Changing one control should preserve the other. Equivalent selections should give the same result in either selection order. Back/reload and cleared selections need explicit expectations. |

The demonstration shows date filtering, grouping, sortable labels and missing
periods in its stated examples.
The recordings do not yet close Beth's intermittent disappearing Time Period
selection, back-navigation behavior, or equality across both selection orders.
An empty cohort by itself is not evidence that filtering is broken.

Read-only API and page-configuration checks on the supplied test server at
18:45 UTC on September 10 establish:

- `ENABLE_TEMPLATE_PROCESSING` is enabled. This is the feature setting that lets
  SQL templates use context such as `{{ time_grain }}`. `ALLOW_ADHOC_SUBQUERY` is
  false; the two flags should not be conflated. See the
  [Superset templating documentation](https://superset.apache.org/docs/configuration/sql-templating/).
- Dataset **40, UTI Aggregate ALL DATA**, still contains the calculated string
  column `time_aggregate`. It produces `YYYY-MM (Mon)` for Month, `YYYY-Qn` for
  Quarter and `YYYY` for Year. This matches the original source snapshot.
- All five saved time-series charts reference dataset 40 and use `month_date`
  with fixed `%b %Y` formatting. They do not currently use `time_aggregate` as
  their X-axis. Their chart-level defaults differ: chart 73 uses Quarter, chart
  101 uses Year, and charts 80, 99 and 103 use Month. Check what happens when the
  dashboard's unit selection is cleared rather than assuming those defaults
  stay overridden.
- Dataset **43, UTI Individual Current**, has a different column, `time_adaptive`.
  Its saved expression includes literal Markdown code fences. That is an
  additional definition defect; no execution of it or connection to the meeting
  failure has been established. It is not used by those five saved trends.
- The preceding 18:20 UTC comparison found the same dashboard layout/filter
  metadata, 21 chart settings and six virtual-dataset SQL definitions as the
  baseline used for the demo. That comparison did not check calculated-column
  definitions; the specific column checks above extend it.

The meeting reports a wrong dataset, a calculated column that was not visible,
and lost customizations after changing datasets. **The saved test definitions
do not establish an automatic dataset switch or a deleted `time_aggregate`
column.** The transcript moves between production and test views and includes
unsaved edits. Capture the affected chart, instance, dataset identity, edit/save
action and before/after definitions to reproduce that authoring problem. Do not
attribute it to import references or treat it as repaired without that evidence.

Versioned dashboard coverage must therefore include **dataset bindings and
calculated-column expressions**, alongside SQL, chart settings, filter state and
layout. The remaining interaction checks should start from a known cohort with
records and then cover an empty test cohort separately. They should not require
Beth to reconstruct a column that is still present in the saved test dataset.

### Other reports

| Item | Coverage and disposition |
| --- | --- |
| Cohort selection sometimes shows every hospital | The client response document marks a prior repair done. Our hospital replacement and Clear all checks exercise related failure cases, but **do not reproduce and close the original intermittent cohort-only/permalink case**. Test the reported saved link and cohort-only state on a copy of the destination. |
| Hospital-only and cohort/state-only comparison menus | The team already specified and marked these fixed. The development definition contains `REGEXP` expressions; the demo uses a PostgreSQL-compatible numeric identity test and checks the available options. This is an adaptation and regression check, not a newly discovered requirement. |
| Entire-cohort submission count | The team already identified the default/filter problem. The demo fixes the card to the Cohort series and checks 248 invented submissions, including its intended all-time exception. It does not verify the real cohort's records. |
| Which selector controls “your hospital” submission count | The client response document leaves alignment with the first selector for review. The demo retains the separate Your hospital selector. **Not resolved by the date fix.** |
| Latest data indication | The demo shows the latest observation month, without advancing it for generated calendar periods. **This is not an import timestamp or dashboard-update timestamp**, both of which appear in the broader requirements. |
| Table-of-contents links lead to errors or the test server | The demo uses section anchors within the current dashboard and tests a jump without changing the route. Production links, saved filter state and embedded navigation need their own check. |
| Three dashboards / which one is current | The demo explicitly represents Individual Data. No production dashboard was renamed or removed. The training view shares 20 development charts, which matters for promotion. |
| Historical data / hospital 57 provenance | The client response identifies historical records as the source, while retaining a review action. Invented-data tests cannot establish real-data completeness or provenance. |
| Introductory text, chart titles, equations and whole-percent axes | Many were already marked done in the client response. The source charts already contain `%b %Y` date formatting and several `,.0%` axes. The full-chart recording shows the inherited layout; it is not a new editorial acceptance review. The requested removal of redundant qualifiers still needs clarification in that document. |
| WordPress login, guest links opening blank pages, image restrictions | The handover describes the embed/token route; the channel reports separate access and navigation problems. Our standalone viewer tests do not exercise that WordPress route or close its reports. The demo replaces the logo, so it does not prove the CSiM image-policy fix. |
| Whether users may inspect peer hospitals | The August discussion contains conflicting interpretations. The requirements page explicitly permits multiple-hospital comparisons. Restricting everyone to their own hospital would change the reporting contract; no such restriction is part of this remediation. |
| Service-worker console error | The August discussion treats this separately from blocked navigation and gives it low priority. The remediation makes no claim to fix it. A console message alone is not evidence of incorrect dashboard calculations. |
| Printing, accessibility, automated REDCap refresh | These appear in wider project materials. This date/filter demonstration does not establish their completion. Screenshots and workflow recordings are not a print or accessibility certification. |

## Necessary supporting work versus additional findings

- Grouping raw records before calculating a rate is necessary to make Quarter
  and Year meaningful. The source chart's `MAX` of already monthly rates can
  select the highest month. This is a source-backed consequence of the requested
  time-unit change, rather than a separate client complaint about a new measure.
- The outer-filter anchor protects partial periods and overall charts from a
  second date predicate. Calendar joins and the observation-only newest-date
  dataset prevent regressions introduced by retaining missing periods.
- Empty-selection guards stop overlapping hospital, state and cohort totals
  being combined. **They are not proof that the original initial-view requirement
  is met.** The requirements describe a cohort-only starting view; the demo starts
  with hospital 91 plus Cohort and deliberately returns no data after Clear all.
- Existing submission-weighted cohort calculations remain in the full dashboard.
  The three-chart example's alternative pooled rate is not a CSiM remediation
  requirement and is not evidence that the team's weighting was wrong.
- The ASB definition/SQL discrepancy is an additional source finding. Its
  formulas remain unchanged. It should not be counted as one of Ian's or Beth's
  resolved issues or used to expand the date/filter work without agreement.

## Why this requires more than chart formatting

There are separate configuration, data and rendering constraints. A date format
changes text, not the available Time Unit menu. A text label cannot create an
absent month. Retaining empty periods does not fix alphabetical ordering or
quarterly aggregation. A successful import does not guarantee every cached ID
was translated. Each needs a specific change and an observable check.

The released 6.1.0 source lacks both per-control time choices and the cached-scope
import repair. These are actual version limitations. The snapshot uses existing
upstream work, not a feature newly invented in this demonstration. See
[time choices](https://github.com/apache/superset/pull/38922),
[display-control follow-up](https://github.com/apache/superset/pull/40000),
[import repair](https://github.com/apache/superset/pull/40140) and
[additional scope remapping](https://github.com/apache/superset/pull/38171).

The team has a requirements checklist, client issue responses, saved SQL history,
dated export backups, a tutorial and a handover document. Those are change and
maintenance practices. The materials examined do not establish a current Git
dashboard revision tied to an automated destination regression run. The useful
addition here is that reproducible connection between files, fixtures and evidence;
it does not justify saying the previous team had no tracking or that the problems
were inherently unsolvable.

## Evidence limits and repeatable checks

- [CI at the recorded revision](https://github.com/pmanko/clinical-ai-validation-harness/actions/runs/34452222966)
  passed with fresh released, import and snapshot instances. It runs all ten
  combined workflows without video, then the six full-dashboard workflows on the
  snapshot.
- `verify_full.py` makes 91 chart-data requests: all 21 charts return data for
  each unit, followed by targeted numerical and filter assertions. This is **not
  91 independent client acceptance cases or a numerical oracle for every chart**.
- The browser verifies all charts load. Detailed drawn-label assertions center
  on the diagnosis trend; category missing-period and count checks also run via
  the chart-data endpoint. Remaining combinations should be chosen from the
  destination's actual reported failure cases.
- `verify_bundle.py` verifies UUIDs, exact SQL, defaults and exclusions and reports
  cached-scope mismatches separately. On the independent 6.1.0 import, all six
  cached filter lists and the global list differ from their expected remapping;
  all six exclusions match. A stale ID may refer to another existing chart, so
  checking only whether IDs exist is insufficient.
- Snapshot time-choice export/import overwrites the same objects to prove saved
  menus are restored. It does not yet establish the cached-ID repair after chart
  IDs change on that build.

## Sources

Ian's three-point overview is reproduced in the user's request. Supporting team
sources below require team access; their suggestions and status labels are source
statements, not instructions to change production or proof of current acceptance.

- [September 2 filter-reference repair and verification discussion](https://digi-team-uw.slack.com/archives/C09PMAC93PV/p1788384231145719), including `json_metadata_fixed.json`.
- [September 9 date-filter report](https://digi-team-uw.slack.com/archives/C09PMAC93PV/p1788993442778049) and [alphabetical-order report](https://digi-team-uw.slack.com/archives/C09PMAC93PV/p1788977311945449).
- [August 31 client issue document](https://docs.google.com/document/d/1sLIu0s-JQdtSy6bEyM6cSaQk3K7yOuHZ/edit), [May edits](https://docs.google.com/document/d/1if-23wJsfXA8E6C_M4AMMRXGFX4asBn1/edit), and [September client responses](https://docs.google.com/document/d/1YPqHSzG93kqgNCySb3QfcsUwUgAITtGAERFqGdFlZqo/edit).
- [Dashboard requirements](https://uwdigi.atlassian.net/wiki/spaces/CSiM/pages/929890354/CSiM+Dashboard+Requirements). Its linked live requirements database has not been independently reconciled item by item in this assessment.
- [Tutorial and maintenance procedures](https://docs.google.com/document/d/1ZJXriNttqVWN3w_vXwYR7HH6DcrqbcIb/edit) and [deployment/embedding handover](https://docs.google.com/document/d/1xRwl4IQwoJ_N17mfwurtP-W5tWQmDEPyMubUABNqDHM/edit).
- [August access, data and embedded-navigation discussion](https://digi-team-uw.slack.com/archives/C09PMAC93PV/p1785968531754959) and [Ian's peer-comparison clarification](https://digi-team-uw.slack.com/archives/C09PMAC93PV/p1785971204700989).
- [Source definition and adaptation details](SOURCE-AND-REMEDIATION.md).

The original Word attachments were readable through their Drive copies. Slack's
binary screenshot download and the September 8 Pastebin log were unavailable to
this audit; neither is treated as visually inspected or a verified root cause.
