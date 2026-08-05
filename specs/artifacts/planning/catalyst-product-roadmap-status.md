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
| Selected next milestone | **Superset-backed Dashboard Builder MVP (D1 / feature 008 US7, T137–T143)** |
| Dependency | Accepted query/version/execution/table foundation only |
| Release work kept separate | Harness PR #43 final MS-D acceptance and merge |
| Approved renderer/handoff | Superset 6.1.0; deterministic native ZIP written to a shared outbox and imported by a one-shot CLI service |
| Explicitly deferred from D1 | Superset REST API, embedded viewing, cross-system undo/reconciliation, model-generated visualization specifications, narratives, sharing, scheduling, automatic refresh, and production authorization/deployment |

Dashboard Builder MVP promotes successful executions through immutable Dataset,
Widget, and multi-widget Dashboard drafts. `Publish to Superset` atomically
writes/downloads a deterministic native bundle; stack bootstrap or an explicit
helper imports it. The logical Dashboard UUID stays stable while changed
Dataset/Widget children use version-derived UUIDs, matching Superset 6.1.0's
actual overwrite behavior. Refresh restores Catalyst drafts without model or
database calls; changed source queries mark them stale rather than rebinding.
The prototype's Ask shell integrates the accepted query notebook: all current
generation, SQL editing/versioning, Validate/Run, diagnostic/result, contextual
follow-up, history, refresh, and session behavior remains through **Save
Dataset**, within the new fixed-composer, chronological-thread design. The
schema/data context and executed-result preview move into its Dataset tile/review
presentation.

## Parallel pathways

| Pathway | State | Next gate | Blocks D1? |
| --- | --- | --- | --- |
| Dashboard product (D1) | **Selected next; D1a written plan complete** | D1b stack/export, D1c iterative UI, D1d real Superset/user acceptance | — |
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
| `specs/008-catalyst-query-workbench/roadmap.md` | Detailed evidence history and D1a–D1d checkpoint board |
| `specs/008-catalyst-query-workbench/data-model.md` and `quickstart.md` | Builder-draft/bundle lineage and the D1 live/manual acceptance sequence |
| `specs/008-catalyst-query-workbench/superset-dashboard-research.md` and `superset-load-reload-research.md` | Renderer, bundle, load/reload, UUID, and import-state decisions against pinned Superset behavior |
| `specs/artifacts/planning/catalyst-validation-integration-roadmap-status.md` | PR #43 evaluation-release status only; not the product roadmap |

## Current boundaries

- Query/workbench MVP is accepted; historical evidence remains historical.
- Multi-source implementation presence is not multi-source acceptance.
- PR #43 has green CI and is ready for review, but its final MS-D decision is
  still open and its evidence remains development-labelled until acceptance.
- The design handoff and written plan are aligned; no Dashboard Builder product
  implementation or acceptance is claimed yet.
