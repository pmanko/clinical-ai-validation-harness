# Catalyst Product Roadmap Status

Portfolio status for Catalyst product, data, assistance, evaluation, narrative,
and production work. The canonical product contract and pathway definitions live
in `targets/catalyst/docs/specification.md` and
`targets/catalyst/docs/roadmap.md`; feature 008 retains the detailed workbench
history and implementation tasks.

## Current decision

| Field | Value |
| --- | --- |
| Accepted foundation | Query-to-table workbench and iterative Query vN notebook |
| Selected next milestone | **Supervised Dashboard MVP (D1 / feature 008 US7, T137–T143)** |
| Dependency | Accepted query/version/execution/table foundation only |
| Release work kept separate | Harness PR #43 final MS-D acceptance and merge |
| Explicitly deferred from D1 | Multi-widget layouts, model-generated visualization specifications, narratives, sharing, scheduling, automatic refresh, publication/export, and production authorization/deployment |

Dashboard MVP promotes one successful execution into one manually configured
table, bar chart, or line chart. Explicit saves append immutable dashboard
versions; refresh restores them without model or database calls; a changed
source query leaves the artifact visible and marks it stale rather than silently
rebinding it.

## Parallel pathways

| Pathway | State | Next gate | Blocks D1? |
| --- | --- | --- | --- |
| Dashboard product (D1) | **Selected next; not started** | D1a contract/persistence tests, D1b supervised UI, D1c real-path user acceptance | — |
| Data foundation (G2.10) | Candidate implementation; evidence open | T117–T122 internal and two-source/lossless acceptance | No |
| Query assistance (W2) | Planned, not selected | G4 scope revalidation before T028–T034 | No |
| Evaluation (W3/CVR) | Runner/report parity implemented; PR #43 MS-D and session-export/comparative expansion remain | Final MS-D for PR #43; separately select T036–T038 or later experiments | No |
| Narrative reporting (R4) | Not started | Evidence adapter and honest grounding-state contract | No |
| Productionization (R5) | Future | Separate security, authorization, data-scope, audit, and deployment plan | No |

## Artifact alignment

| Artifact | Role |
| --- | --- |
| `targets/catalyst/docs/specification.md` | Canonical product goal, Dashboard MVP requirements, acceptance, and deferrals |
| `targets/catalyst/docs/roadmap.md` | Parallel pathway map, D1 slices, dependencies, and exits |
| `specs/008-catalyst-query-workbench/spec.md` | Accepted workbench foundation plus Dashboard MVP user story/requirements |
| `specs/008-catalyst-query-workbench/plan.md` | Technical pathway boundaries, Dashboard MVP design boundary, and selected-milestone scope |
| `specs/008-catalyst-query-workbench/tasks.md` | Historical work plus executable D1 tasks T137–T143 |
| `specs/008-catalyst-query-workbench/roadmap.md` | Detailed evidence history and D1a–D1c checkpoint board |
| `specs/008-catalyst-query-workbench/data-model.md` and `quickstart.md` | Dashboard artifact/version lineage and the D1 live/manual acceptance sequence |
| `specs/artifacts/planning/catalyst-validation-integration-roadmap-status.md` | PR #43 evaluation-release status only; not the product roadmap |

## Current boundaries

- Query/workbench MVP is accepted; historical evidence remains historical.
- Multi-source implementation presence is not multi-source acceptance.
- PR #43 has green CI and is ready for review, but its final MS-D decision is
  still open and its evidence remains development-labelled until acceptance.
- No Dashboard MVP implementation or acceptance is claimed by this alignment.
