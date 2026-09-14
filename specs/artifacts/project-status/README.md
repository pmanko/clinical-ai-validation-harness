# Project status hub

[Open the dashboard](https://pmanko.github.io/clinical-ai-validation-harness/status/)
for the visual overview, searchable PR inventory and linked detail panels.

**Four-pathway reporting refreshed 14 September 2026.** Other inventory
entries retain their individual evidence dates. This is a maintained snapshot,
not a live GitHub feed. Product requirements and acceptance stay in their existing
specifications.

| Current work | Next checkpoint | Authority |
| --- | --- | --- |
| Catalyst | Current release remains in its own register; imported Datasets and ordinary PostgreSQL are approved extensions awaiting design/implementation. | [Catalyst delivery plan](../../008-catalyst-query-workbench/plan.md) and [shared tasks](../../008-catalyst-query-workbench/tasks.md#four-pathway-delivery). Existing AI-design Follow-on A is retained. |
| OpenELIS–Catalyst reporting | Four complementary pathways approved; consolidate specifications and review mock extensions. Native reporting implementation/UAT is already active; mock PR #322 is open. | [Parent reporting roadmap](../../openelis-reporting-catalyst-integration.md), with native reporting and Catalyst task links. No per-lane specification family or duplicate checklist. |
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
