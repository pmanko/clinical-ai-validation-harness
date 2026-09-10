# Project status hub

[Open the project dashboard](https://pmanko.github.io/clinical-ai-validation-harness/status/) for the visual overview, searchable inventories, report reader, and linked detail panels. The dashboard uses the source files in this directory. [Local preview and maintenance instructions](../../../site/status/README.md).

**Current Catalyst baseline checked 9 September 2026; broader inventory checked 6 September 2026.** Start here to resume ChartSearchAI, Catalyst, and the supporting validation work. This hub joins current work, source changes, requirements, evidence, and public outputs. Product scope and acceptance remain in the existing approved authorities.

Both products have substantial implemented functionality. ChartSearchAI needs upstream reconciliation and final two-provider live acceptance. Catalyst's authoritative roadmap and compatible Spark baseline are now merged. The next active work is specification consolidation, followed by the four usability iterations and a local dual-source owner gate. The fresh model comparison remains separately scheduled.

| Reference | What it contains | Editable input |
|---|---|---|
| [Comprehensive report](reports/2026-09-06.md) | Findings, demonstrated behavior, gaps, chronology, recovery and restart recommendation | Dated narrative snapshot |
| [Merge review](reviews/2026-09-06.md) | Review of all 12 open PRs and both Spark branches, findings, tests and next actions | Dated review; current assessments also live in the inventories |
| [Effort inventory](efforts.md) | 32 efforts with current state, next deliverable, acceptance boundary and sources | [efforts.json](efforts.json) |
| [Pull-request inventory](pull-requests.md) | 145 pull requests grouped by repository, with state, branch, effort and review/check signals | [GitHub snapshot](pull-requests.json) |
| [Roadmap and specification crosswalk](roadmaps.md) | 32 entries distinguishing current authority, partly current plans and superseded material | [roadmaps.json](roadmaps.json) |
| [Artifact inventory](artifacts.md) | 71 authorities, configurations, scenarios, findings, evidence and output references | [artifacts.json](artifacts.json) |
| [Dashboards and publication surfaces](public-surfaces.md) | 21 public, product and operator surfaces, their purpose, status and next update | [public-surfaces.json](public-surfaces.json) |
| [Published report inventory](reports.md) | 19 reports with family, date, method limits and links | [reports.json](reports.json) |
| [Decisions and concrete findings](decisions.md) | 7 open or explicitly deferred items | [decisions.json](decisions.json) |
| [Codex and Claude work](sessions.md) | 6 key working conversations and their handoff significance | [sessions.json](sessions.json) |
| [Maintenance and publication approach](maintenance.md) | How to update this hub and use existing sites without duplicating roadmaps | Editable guide |

The [CSV exports](exports/) provide the same rows for sorting or spreadsheet use. The JSON inputs retain additional detail such as dependencies, exact revisions, check bindings, review markers and provenance. Use `python3 specs/artifacts/project-status/render.py` after editing inputs; `--check` verifies that the generated tables are current.

**What to resume first**

| Priority | Work | Concrete next deliverable |
|---|---|---|
| First | Consolidate Catalyst specifications and planning | Fold the legacy implementation plan and Dashboard delivery goal into the Feature 008 authority set without losing a unique requirement |
| Next | Implement the frozen Catalyst usability design | Deliver the composer, shell, Available data, and result-review iterations, then run the complete local dual-source owner gate |
| First, in parallel | Reconcile the three active OpenMRS integration pull requests | Review current upstream changes, resolve backend/frontend conflicts bottom-up, then rerun paired source checks |
| At the local owner gate | Validate both Spark source databases | OpenELIS and OpenMRS must retain independent catalogs and complete real paths through drafting, browsing, Run, results, and refinement |
| Separately scheduled | Prepare the Catalyst comparison | Use the merged launcher and source isolation, then finish reviewed Spark references and reader-led evidence without the retired database/scoring path |
| Before product closeout | Repeat current-revision ChartSearchAI live proof and record owner review | Both providers, persistence/reload, cancellation, context completeness, evidence and medication-safety states |
| Alongside those changes | Reconcile older pull requests and public status | Preserve useful work; record disposition recommendations and correct deployed/source report-index drift |

**GitHub snapshot**

The full pull-request inventory remains a point-in-time 6 September snapshot. Its current Catalyst delivery records are refreshed here: roadmap #109, Catalyst #79, Hub #24, and harness baseline #100 are merged; superseded harness #108 is closed; dashboard #101 and cloud-safety #105 remain open while their review history is collapsed onto current `main`. Use live GitHub for other changing mergeability and check signals until the next complete collection.

The 12 open upstream contributions include the three active integration pull requests and nine older contributions requiring disposition review. Nine currently conflict with their base; three are mergeable. QueryStore #68 is clean with Java 8, 11, 17 and 21 passing, ESM #23 is clean with its OpenMRS CI build passing, and ChartSearchAI #157 has paired Java 11, 17 and 21 passing at 31a8c162 after upstream main was merged again and the ChartAnswer constructor reconciled. ChartSearchAI's separate advisory QueryStore-HEAD job remains red because upstream main does not yet contain QueryStore #68's API. Old checks and unresolved comment markers are dated evidence, not automatic readiness or defect verdicts.

The merged harness baseline at `2a75bcf` pins Catalyst `47c80d9`, Hub `75d0ff0`, ChartSearchAI `d46f517`, ESM `77f61c8`, and QueryStore `f2fca72`. Final hosted checks passed for the roadmap, Catalyst, Hub, and harness changes; the strict repository-line check passes from merged harness `main`. Fresh browser acceptance remains separate.

**How the evidence and public surfaces fit**

Use [openclinai.org](https://openclinai.org/) for the public explanation and representative demonstration, [the reports site](https://reports.openclinai.org/) for dated research and case evidence, and [the documentation site](https://pmanko.github.io/clinical-ai-validation-harness/) for public architecture/research navigation. Use this hub for active work and links back to their authorities.

The deployed report manifest has 19 entries, while main's manifest has 16. Three Catalyst entries exist only in the deployed manifest, and two omit their family and appear as ChartSearchAI. The older Catalyst comparison still presents the previous numerical thresholds. Preserve that historical evidence and label its method; it does not validate the new Spark path.

All 41 checked public links returned HTTP 200 on September 6. [Availability evidence](evidence/public-surface-checks-2026-09-06.json) records exactly what was checked. No model run, authenticated workflow, reseed, deployment, or owner acceptance was performed for this inventory.

**Updating together**

Update an effort after a meaningful implementation, merge, deployment, validation, publication or acceptance event. Keep one next deliverable and link the actual evidence. Leave unassigned owners explicit. Keep dated reports immutable and update the current inventory instead. Before resuming a task, refresh volatile GitHub and deployment facts and then read the linked product authority.

The [maintenance guide](maintenance.md) provides the proposed workflow and public-summary recommendation. No recurring automation or public-site change is included in this local status-hub change.
