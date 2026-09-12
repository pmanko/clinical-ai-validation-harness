# CSiM dashboard dates, filters and synthetic examples

The reporting requirement is consistent meaning across hospital, care-location,
date-range and time-unit selections. Missing periods, valid zeroes and undefined
rates must remain distinct. Moving a dashboard between installations must preserve
its data and filter relationships.

- [Problem overview](https://catalyst.openelis-global.org/superset/design/)
- [Full 21-chart synthetic dashboard](https://catalyst.openelis-global.org/superset/superset/dashboard/csim-full-synthetic/)
- [Workflow evidence](https://catalyst.openelis-global.org/superset/design/evidence/)
- [Native dashboard ZIP](https://catalyst.openelis-global.org/superset/design/definitions/csim-full-native.zip)

The full example uses the September 9 CSiM development layout, six filters and
existing hospital/cohort calculations. It includes trends, overall measures,
comparison tables, antibiotic and care-location breakdowns, all-time submission
cards and the newest-data date. Its date/filter changes span all 21 charts.
Production parity and clinical acceptance remain separate requirements.

## Data and access

Both examples use 262 invented records, two fictional hospitals (`91`, `92`),
two care locations and November 2025–May 2026. No patient records were downloaded.
Only dashboard, chart and dataset definitions were read from development metadata.

The full source snapshot is private and ignored:
`output/source-dashboard-20260910.json`. It contains SQL and layout definitions,
without database credentials, accounts or source rows. See
[SOURCE-AND-REMEDIATION.md](SOURCE-AND-REMEDIATION.md) for source authority and limits.

Local login: `demo`; the generated password is in `.env.local`.
The shared `csim-viewer` login is displayed on the public overview. Server
administration uses separate private credentials in `output/server-access.txt`.

## Reproduce the full dashboard from files

`bundle/` is the native Superset representation: one dashboard, 21 charts,
eight datasets (with SQL), a database connection template and stable UUIDs.
The original private development snapshot is not needed for this path.

```sh
bash tools/csim-superset/local.sh bundle-boot # initialize and seed invented data, then import
bash tools/csim-superset/local.sh full-test   # 91 chart requests and assertions
bash tools/csim-superset/local.sh bundle-pack # native ZIP for Superset's Import dashboard dialog
```

For the clean independent import check (port 18094):

```sh
bash tools/csim-superset/bundle-check.sh up
bash tools/csim-superset/bundle-check.sh import
bash tools/csim-superset/bundle-check.sh test
bash tools/csim-superset/bundle-check.sh browser
bash tools/csim-superset/bundle-check.sh down
```

The test stack has its own metadata, database and account. Its `up` command
explicitly loads the invented fixture. `down` retains its volumes for diagnosis;
use a fresh test environment to establish first-import behavior. No clinical
source or production connection is needed. The SQL is retained exactly in the
native dataset files. Supply the destination database password at import.

For edits, review changes to the YAML, dataset SQL and expected results together.
Import into a clean test instance and rerun the workflows. Native import behavior
when overwriting shared datasets/charts on an existing installation needs separate
verification before using this as a production update pipeline.

## Original example setup

```sh
bash tools/csim-superset/local.sh boot        # first initialization; explicitly seeds invented records
bash tools/csim-superset/local.sh test        # focused lab: ten scenario groups
bash tools/csim-superset/local.sh full-setup  # requires the private definition snapshot; adds synthetic antibiotic flags
bash tools/csim-superset/local.sh full-test   # full dashboard: 91 chart-data requests with assertions
bash tools/csim-superset/local.sh export      # focused lab: sanitized native ZIP and test results
bash tools/csim-superset/local.sh up          # start without reseeding
bash tools/csim-superset/local.sh down        # stop; retain volumes
```

`full-setup` updates only the synthetic dashboard objects and adds invented
antibiotic fields. It does not replace the fixture or the focused lab.
Local full dashboard:
<http://127.0.0.1:18089/superset/dashboard/csim-full-synthetic/>.
Local focused lab:
<http://127.0.0.1:18089/superset/dashboard/csim-date-lab/>.

This independent lab uses its own Compose wrapper. Catalyst's actual application
stack continues to use `scripts/catalyst-mvp.sh`.

## Demonstrated behavior

| Hospital 91, Inpatient | Counted cases / eligible records | Submissions | Meaning |
| --- | --- | --- | --- |
| November 2025 | 2 / 10 | 10 | 20% |
| December 2025 | 9 / 90 | 90 | 10% |
| January 2026 | 1 / 1 | 1 | 100% |
| February 2026 | no row | no row | Missing period |
| March 2026 | 0 / 9 | 9 | Valid 0% |
| April 2026 | 0 / 0 | 10 | Undefined rate |
| May 2026 | 2 / 8 | 8 | 25% |

Q4 is 11%; Q1 is 10%, rather than the maximum monthly rate of 100%.
For February–March alone, Q1 is 0%: January is outside the selected range.

The full example filters original reporting dates before grouping and applies the
existing hospital calculations to the selected period. Its cohort calculation
retains submission-volume weighting. The focused lab instead demonstrates a
pooled eligible-count calculation. These definitions are intentionally distinct;
neither choice is established as the approved clinical rule by this demo.

Calendar rows retain missing periods. `time_aggregate` supplies sortable labels (`2025-11`, `2025 Q4`, `2026`);
`period_sort` supplies chronological ordering. A separate `filter_anchor` column
handles Superset's outer date predicate without dropping partial quarters or
excluding overall charts that have no date axis. Clearing required selections
returns no totals that could combine overlapping hospital/state/cohort rows.

The full example retains deliberate filter exceptions: all-time total cards
ignore the date range; care-location breakdowns show all locations; paired charts
use their own hospital/comparison selectors. The newest-data card uses actual
observations and only the main hospital selector.

## Remaining issues

- **Measure definitions:** ASB prevalence and treatment divide by all submissions
  in the current SQL; their displayed definitions name positive urine cultures
  and ASB cases respectively. The full example retains the formulas and displays
  the discrepancy. Clinical agreement is required.
- **Time choices:** the released 6.1.0 instance restricts Month, Quarter and Year
  globally. The separate upstream snapshot demonstrates per-control choices;
  stable-release adoption remains open.
- **Transfer:** the native bundle's tested interactions work after independent
  import. Its SQL, UUIDs, defaults and exclusions match, but 6.1.0 leaves cached
  chart references stale. The newer importer and actual production route need
  separate remapping and promotion checks.
- **Production:** development has 21 charts; equivalence with
  `superset.uwcsim.org` is not established. Production data, permissions, WordPress
  embedding, printing and accessibility need their own acceptance.
- **Reporting completeness:** a calendar cannot establish whether all expected
  records arrived or whether current/historical sources contain duplicates.

## Validation and runtime

`verify_full.py` uses the real authenticated Superset chart-data API and PostgreSQL.
It checks all 21 charts at three grains, expected values, gaps, original cohort
weighting, partial date ranges, overall measures, hospital/location changes,
all-time exceptions, newest-data dates, cleared selections, and filter/layout
references. Browser validation additionally exercises native controls and charts.
Receipts and results are in ignored `output/`.

The pinned base is an official Superset **6.1.0-dev** image that reports 6.1.0.
The local image adds Hive dependencies, while this lab queries PostgreSQL only.
SQLite holds demo metadata. These choices do not establish behavior of a
separately built production release.

The focused lab's ZIP export helper masks its database password and checks for
generated credentials. Supply the destination password when importing. The full
native bundle has also been imported into an independent instance: all 21 chart
identifiers changed, eight dataset SQL definitions and six filter defaults and
exclusions matched, 91 chart-data requests with targeted assertions passed, and
six browser workflows passed. Cached scope references are reported separately;
they do not match after the 6.1.0 import.

See [reported-issue coverage](REPORT-COVERAGE.md) for Ian's three original issues,
Beth's missing-period report, other client requests, and the limits of each check.

See [DEPLOYMENT.md](DEPLOYMENT.md) for runtime paths, publication and rollback.

The full comparison charts use sortable date labels because Superset pivots and
re-sorts text axes. The focused single-series lab can use a hidden date-sort metric
with descriptive labels. Preserving that descriptive style in multi-series charts
requires additional Superset support. See [the workflow harness](e2e/README.md)
for browser assertions and screenshot/video evidence.

The treatment numerator is also broader than its displayed definition: the SQL
counts all treated submissions (`tx___1 = 0`), rather than only treated ASB cases.
The synthetic version retains that existing formula and labels the discrepancy.
