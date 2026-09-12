# Project status hub

[Open the dashboard](https://pmanko.github.io/clinical-ai-validation-harness/status/)
for the visual overview, searchable PR inventory and linked detail panels.

**Core delivery and PR coordination refreshed 12 September 2026.** Other inventory
entries retain their individual evidence dates. This is a maintained snapshot,
not a live GitHub feed. Product requirements and acceptance stay in their existing
specifications.

| Current work | Next checkpoint | Authority |
| --- | --- | --- |
| Catalyst | Visual remediation in #117; runtime release #157 is merged and its owning task is verifying two sources and server evidence. | [Feature 008 plan](../../008-catalyst-query-workbench/plan.md) and [tasks](../../008-catalyst-query-workbench/tasks.md). Closed #151 does not change their sequence. |
| OpenELIS reporting | Defaults approved and v1.3 mock/spec #315 merged; publication verified; finish visual owner review. | [Reporting roadmap](../../openelis-reporting-catalyst-integration.md) links to OpenELIS Section 14; no duplicate checklist here. |
| ChartSearchAI | Reconcile upstream backend #157, retain frontend #23 and QueryStore #68, then complete current-revision provider acceptance. | [Dual-provider roadmap](../planning/openmrs-dual-provider-parity-roadmap.md). |
| PR cleanup | Nine older OpenMRS contributions need content-based disposition. Contributor setup #33 → #148 and the older OpenELIS stacks retain explicit dependency order. | [September 12 PR review](reviews/2026-09-12.md). |

| Reference | Purpose |
| --- | --- |
| [Current PR review](reviews/2026-09-12.md) | Active lanes, overlaps, dependencies and unresolved cleanup. |
| [Pull requests](pull-requests.md) | Current and historical rows, exact heads, available check signals and next actions. [JSON source](pull-requests.json). |
| [Efforts](efforts.md) | One next deliverable and acceptance boundary per effort. [JSON source](efforts.json). |
| [Roadmaps](roadmaps.md) and [artifacts](artifacts.md) | Authority crosswalk and evidence references; inspect each entry's date. |
| [Sites and dashboards](public-surfaces.md) and [reports](reports.md) | Publication surfaces and historical evidence, with claim limits. |
| [Decisions](decisions.md) and [working sessions](sessions.md) | Supporting records; refresh volatile facts before resuming old work. |
| [September 6 report](reports/2026-09-06.md) | Historical comprehensive reconnaissance, not current merge readiness. |
| [Maintenance guide](maintenance.md) | Edit existing JSON, regenerate Markdown/CSV and check the dashboard. |

The PR snapshot includes maintained-repository activity since August 1 and earlier
retained records, current owned OpenMRS contributions, OpenELIS design work, all
13 owned open OpenELIS application PRs, and the two fork companions. The broader
188-PR OpenELIS application list was scanned for overlap, not individually code
reviewed. Missing CI is unknown, not a passing result. Neither mergeability nor
an old green check establishes product acceptance.

Use `scripts/project-status.sh github` for collection guidance and
`scripts/project-status.sh refresh` after editing the inputs. The [CSV exports](exports/)
provide the same rows for sorting. Keep dated reviews immutable; amend current
inventory rows after meaningful implementation, merge, validation, deployment or
acceptance events. Raw screenshots and recordings stay outside Git.

Use [openclinai.org](https://openclinai.org/) for public explanation and
[reports.openclinai.org](https://reports.openclinai.org/) for dated evidence.
Keep this hub linked to the actual product registers rather than copying their
delivery checklists.
