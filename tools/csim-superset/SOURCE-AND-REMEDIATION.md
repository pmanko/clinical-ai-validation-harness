# CSiM source definitions and remediation boundaries

Status date: September 9, 2026 Pacific / September 10 UTC.

## Dashboard authority

The development Superset metadata contains **CSiM UTI/ASB Dashboard [Individual
Data]**, dashboard 13, with 21 charts. Its last saved timestamp is
`2026-09-09 21:40:25.284791` UTC. The training dashboard shares 20 of those chart
objects; editing a shared chart also changes the training view. Historical
aggregate reporting is a separate 28-chart dashboard.

The development endpoint is `http://34.223.100.228:8088/`, as named in the
[dashboard tutorial](https://docs.google.com/document/d/1ZJXriNttqVWN3w_vXwYR7HH6DcrqbcIb/edit).
Production is <https://superset.uwcsim.org/>. Equality between the two definitions
is not established; production remains at its login page in the available session.

[The GitHub repository](https://github.com/DIGI-UW/superset-mini) contains deployment
files rather than the current saved dashboards. The development checkout is
`master`, commit `05c9b0538990e9b1274f710e4a7bb012427a1a3e` (September 26, 2024),
with local changes in the Dockerfile, Compose, nginx and Superset configuration.
The running 6.1.0 image therefore cannot be identified solely by that Git revision.

The [April backup folder](https://drive.google.com/drive/folders/112_5mM_l7SEClWWZAeW7bJhqQuq7Qhyp)
contains the older dashboard ZIP, SQL and styling. The tutorial identifies the ZIP
as the primary restore artifact. It is not evidence of September production parity.

## Definition snapshot

`output/source-dashboard-20260910.json` contains dashboard 13, its 21 charts and
18 dataset definitions. It excludes source rows, credentials and user accounts.
The source SQLite database was opened read-only. The local file has mode 600 and
is ignored by Git. Its compressed transport SHA-256 is:

```
53323218f6f6a093642995df0545a7a2cc9d98c7e42351611db884b48d962095
```

The full synthetic setup uses six virtual datasets (source IDs 35, 36, 37, 38,
40, 41). Their physical dependencies are `v1."UTI Individual Current"`,
`v1."UTI Individual Historical"` and `v1."CSiM Hospitals and States"`.
Those relations contain generated records in the demonstration database only.
The native bundle contains eight datasets, including the hospital lookup and a
separate dataset supplying actual observation dates for the newest-data card.
A clean native import preserves all SQL exactly and passes 91 chart-data checks
and six browser workflows. See `bundle/` and `bundle-check.sh`.

## Behavior by issue

| Issue | Synthetic implementation | Remaining boundary |
| --- | --- | --- |
| Unstable labels and order | Separate typed dates and naturally sortable period labels | Target installation and visual acceptance |
| Missing periods | Calendar joins for trends and category charts; NULL retained | Definition of complete reporting |
| Incorrect quarter/year measures | Filter original months, then group before hospital/cohort calculations | Clinical agreement on definitions and weighting |
| Partial periods or overall charts lost by outer date filter | Dedicated filter column inside the chosen range | Other runtime versions and dialects |
| Chart/filter references | Native ZIP import preserves UUID relationships with all chart IDs changed | Existing shared-object updates and production promotion |
| Overlapping required selections | SQL guards on hospital and care location | Existing Superset UI still permits Clear all |
| Newest-data card with three hospital selectors | Main selector only; actual observation date | Agreed meaning of latest data across selections |
| PostgreSQL-incompatible selector expression | Numeric hospital identity separates hospital and comparison options | Other data models/dialects |
| Excessive time-unit options | Dedicated instance restricted to Month/Quarter/Year | Per-dashboard allowlist remains separate |

The original clinical calculations and submission-weighted cohort rule remain.
In particular, `prev` and `txrate` divide by `COUNT(*)`, while displayed definitions
name positive urine cultures and ASB cases. Their mismatch appears beside the
ASB definitions in the synthetic dashboard and in the public overview.

The focused three-chart example uses a different proposed pooled rate; the full
21-chart example does not adopt that change. For Q2 hospital comparison in the
fixture, the original weighted rate is `(0.25*18 + 0.125*40) / 58`.

## Development operations

The AWS development host is instance `i-003f97829d735ece2`, named `jamaica-pilot`,
in `us-west-2d`. Systems Manager provides read access. Its Superset app reports
6.1.0. The active metadata database is SQLite at
`/app/superset_home/superset.db`, despite an older handover describing PostgreSQL.
The host also runs unrelated services.

The Superset app health check invokes a missing
`/app/docker/docker-healthcheck.sh` and exits 127. Its website responds despite the
unhealthy container status. Workers, Redis and the metadata-adjacent PostgreSQL
container report healthy status. No development or production service was changed.

The old `superset.openelis-global.org` name points to a different address,
`44.239.158.12`; it is not the CSiM production endpoint or this development host.
It did not match EC2 instances or elastic addresses in the available account's
`us-west-2` inventory. Its service contents remain unknown. No DNS changes apply.

## Catalyst implications

A saved dataset must include its SQL and measure definitions. Widget and dashboard
artifacts need explicit dependencies, display policies and filter coverage.
A turn that changes these artifacts needs review of the affected dashboard result.
The existing Workbench and Library direction can support these requirements;
this standalone Superset demonstration does not implement those product changes.
Metabase and Evidence remain alternative output candidates.

## References

- [September date/filter discussion](https://digi-team-uw.slack.com/archives/C09PMAC93PV/p1788993442778049)
- [Filter-reference repair](https://digi-team-uw.slack.com/archives/C09PMAC93PV/p1788384231145719)
- [September client issues](https://docs.google.com/document/d/1YPqHSzG93kqgNCySb3QfcsUwUgAITtGAERFqGdFlZqo/edit)
- [Deployment handover](https://docs.google.com/document/d/1xRwl4IQwoJ_N17mfwurtP-W5tWQmDEPyMubUABNqDHM/edit)
- [Superset dashboard-specific time-unit proposal](https://github.com/apache/superset/pull/42849) (open September 9)
- [Chart-reference import fix](https://github.com/apache/superset/pull/40140) and [follow-up](https://github.com/apache/superset/pull/38171)

The full comparison charts use sortable date labels because Superset pivots and
re-sorts text axes. The focused single-series lab can use a hidden date-sort metric
with descriptive labels. Preserving that descriptive style in multi-series charts
requires additional Superset support. See [the workflow harness](e2e/README.md)
for browser assertions and screenshot/video evidence.

The treatment numerator is also broader than its displayed definition: the SQL
counts all treated submissions (`tx___1 = 0`), rather than only treated ASB cases.
The synthetic version retains that existing formula and labels the discrepancy.
