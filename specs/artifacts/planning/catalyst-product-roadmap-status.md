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
| Selected next milestone | **Superset-backed Dashboard Builder MVP (D1 / feature 008 US7, T137–T182)** |
| Dependency | Accepted query/version/execution/table foundation only |
| Release work kept separate | Harness PR #43 merged green at `136067a`; optional session-export/comparative expansion remains parallel |
| Approved renderer/handoff | Superset 6.1.0; deterministic native ZIP written to a shared outbox and imported by a one-shot CLI service |
| Explicitly deferred from D1 | Superset REST API, embedded viewing, cross-system undo/reconciliation, model-generated visualization specifications, narratives, sharing, scheduling, automatic refresh, and production authorization/deployment |

Dashboard Builder MVP promotes successful executions through immutable Dataset,
Widget, and multi-widget Dashboard drafts. `Publish to Superset` atomically
writes/downloads a deterministic native bundle; stack bootstrap imports only an
eligible desired digest and an explicit helper owns retries. The logical Catalyst Dashboard ID, derived Superset Dashboard
UUID, and slug stay stable while changed Dataset/Widget children use version-
derived UUIDs, matching Superset 6.1.0's actual overwrite behavior. Refresh
restores Catalyst drafts without model or
database calls; changed source queries mark them stale rather than rebinding.
Each D1 Dashboard locks one exact `dataSourceId` plus `catalogVersion`; a catalog
refresh requires a new Dashboard. The stable Superset slug is
`catalyst-<lowercase-dashboard-id>`, derived from the logical Catalyst Dashboard
ID rather than its separate Superset asset UUID; import evidence must verify the UUID,
slug, and route before Open Superset is enabled. Dataset promotion normalizes the
accepted execution table wire payload into one canonical RFC 8785 digest object
with ordered stable warning codes; no current logical type is silently dropped.
The runtime proves the PostgreSQL driver/network path and DB-enforced read-only
access, while the canonical native Superset fixture owns the persisted
analytics Database asset. Pointer/bundle/preflight/credential failures and
transactionally rolled-back Superset CLI failures preserve the previously verified Dashboard. A later
UUID/slug/relationship verification failure instead reports `Import failed`,
retains its diagnostic, and disables Open/current-success; recovery is an
explicit full reset of only the Superset-local metadata database/home volumes
plus verified reimport from the atomic per-Dashboard last-verified projection.
Missing/corrupt projection data stops before reset. If verified A is recovered
while failed desired B remains in `current.json`, B stays `import_failed` and
automatic bootstrap/retry is suppressed until explicit retry or new publication.
Asset-selective deletion, direct ORM/REST mutation, and automatic rollback are
not used.
The prototype's Ask shell integrates the accepted query notebook: all current
generation, SQL editing/versioning, Validate/Run, diagnostic/result, contextual
follow-up, history, refresh, and session behavior remains through **Save
Dataset**, within the new fixed-composer, chronological-thread design. The
schema/data context and executed-result preview move into its Dataset tile/review
presentation.

## Parallel pathways

| Pathway | State | Next gate | Blocks D1? |
| --- | --- | --- | --- |
| Dashboard product (D1) | **Superset import spike plus accepted-workbench real-model proof; full D1 open** | User M2 review, then multi-widget M3 and release M4 (T139–T182) | — |
| Data foundation (G2.10) | Candidate implementation; evidence open | T117–T122 internal and two-source/lossless acceptance | No |
| Query assistance (W2) | Planned, not selected | G4 scope revalidation before T028–T034 | No |
| Evaluation (W3/CVR) | Runner/report parity merged in PR #43; session-export/comparative expansion remains | Separately select T036–T038 or later experiments | No |
| Narrative reporting (R4) | Not started | Evidence adapter and honest grounding-state contract | No |
| Productionization (R5) | Future | Separate security, authorization, data-scope, audit, and deployment plan | No |

## Artifact alignment

| Artifact | Role |
| --- | --- |
| `targets/catalyst/docs/specification.md` | Canonical product goal, Dashboard MVP requirements, acceptance, and deferrals |
| `targets/catalyst/docs/roadmap.md` | Parallel pathway map, D1 slices, dependencies, and exits |
| `specs/008-catalyst-query-workbench/spec.md` | Accepted workbench foundation plus Dashboard MVP user story/requirements |
| `specs/008-catalyst-query-workbench/plan.md` | Technical pathway boundaries, Dashboard MVP design boundary, and selected-milestone scope |
| `specs/008-catalyst-query-workbench/tasks.md` | Historical work plus executable test-first D1 tasks T137–T182, retaining T144/T149/T154/T157 as checkpoint gates |
| `specs/008-catalyst-query-workbench/roadmap.md` | Detailed evidence history and D1a–D1e checkpoint board |
| `specs/008-catalyst-query-workbench/data-model.md` and `quickstart.md` | Builder-draft/bundle lineage and the D1 live/manual acceptance sequence |
| `specs/008-catalyst-query-workbench/superset-dashboard-research.md` and `superset-load-reload-research.md` | Renderer, bundle, load/reload, UUID, and import-state decisions against pinned Superset behavior |
| `specs/artifacts/planning/catalyst-validation-integration-roadmap-status.md` | PR #43 evaluation-release status only; not the product roadmap |

## Current boundaries

- Query/workbench MVP is accepted; historical evidence remains historical.
- Multi-source implementation presence is not multi-source acceptance.
- PR #43 merged with green CI at `136067a`; any future evaluation expansion is
  separate from Dashboard MVP.
- The second groundedness audit reopened D1a after finding stale branch ancestry,
  missing API/receipt contracts, oversized tasks, and insufficient evidence
  gates. Remediation is now technically complete: both feature branches are based
  on current `main`, eight Dashboard Builder contract mirrors are byte-identical,
  seven JSON Schemas and their positive/negative fixtures validate, all 182 task
  IDs are unique, and the final Spec Kit pass has zero unresolved CRITICAL/HIGH
  findings. The user accepted D1a on 2026-08-05 and authorized implementation
  through a working local MVP. The task graph is split into path-specific red→green steps, and evidence schema/
  emitter validation precedes the real D1e run. Catalyst owns and gitignores
  `runtime/superset/`. Importer/state implementations are standalone Python 3.10
  scripts under `targets/catalyst/scripts/` with no Catalyst package dependency;
  their canonical-JSON and pinned-container tests live under the Gateway test
  tree and run in Catalyst's Gateway CI job. Runtime commands use one dedicated
  `mvp-superset.sh` boundary routed from the harness.

  **Current correction (2026-08-05):** the former statement that no Dashboard
  Builder implementation was claimed is obsolete. The active feature branches
  contain a working local table-dashboard vertical slice: persisted builder
  drafts, deterministic native bundle, pinned Superset stack, explicit importer,
  and verified local import receipt. It is not full D1 acceptance: the exporter
  is table-only; the multi-widget library shell, five clean-imported
  visualization families, full reset/reimport recovery, comprehensive
  accessibility evidence, builder-integrated real-model D1e evidence, and
  schema-backed dashboard acceptance emission remain open. The standalone M2
  real-profile workbench proof passed technically on exact Gemma E4B/Qwen 14B
  aliases and is awaiting user acceptance. The authoritative M0–M4
  local-MVP target is
  `specs/008-catalyst-query-workbench/dashboard-mvp-delivery-goal.md`.
