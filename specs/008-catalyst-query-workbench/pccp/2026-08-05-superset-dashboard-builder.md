# PCCP-style Change Record: Superset-backed Dashboard Builder MVP

**Status:** D1a passed; M3/T186 real-profile multi-widget workflow passed;
M4/T187 release acceptance open

**Date:** 2026-08-05

**Decision:** Extend the accepted Catalyst Query vN workbench through supervised
Dataset, Widget, and Dashboard versions, then publish a deterministic native
bundle to a digest-pinned local Superset 6.1.0 renderer. No Superset REST API,
embedded dashboard, background watcher, Catalyst chart renderer, automatic SQL
execution, or model-generated visualization configuration is authorized.

## Modification and rationale

### Current implementation boundary (2026-08-05)

The current branches implement a Superset import spike: persisted
builder drafts, deterministic native table bundle, pinned Superset runtime,
explicit importer, restart-retained volumes, and verified import receipts. The
historical completed generation path used the then-available deterministic fake
router, so that evidence is structural scaffolding rather than real-model
acceptance. The fake router is no longer part of the product stack. The table exporter is
the only verified native visualization; the designed multi-widget/library UX,
five-family import matrix, complete reset/reimport recovery, accessibility
matrix, and dashboard evidence emitter remain open. This record therefore does
not claim an intermediate MVP or D1 completion until the real-model,
multi-widget, record-reconciled, user-accepted path succeeds.

The current product supports real writer/reviewer query generation, manual SQL
editing and formatting, advisory validation, explicit PostgreSQL execution,
typed results, contextual follow-up, provenance, and refresh restoration. It has
no durable reporting artifact beyond the query/table session. D1 adds a linear,
artifact-first promotion path:

`successful Run → Dataset version → Widget version → Dashboard version → native ZIP → explicit Superset CLI import`

Catalyst remains the desired-configuration and provenance authority. Superset
queries the compiled virtual-dataset SQL with the demo read-only role and is the
only dashboard renderer. Superset-only edits are intentionally replaced by the
next publication and are not represented as synchronized.

### M3 implementation checkpoint (2026-08-06)

The active branches now supersede the table-only runtime boundary above with a
manually testable real-profile flow: Gemma E4B generation, Qwen 14B review,
manual SQL child version, explicit execution, one exact Dataset, table and
time-series Widgets, native bundle/import, live Superset rendering, per-widget
PostgreSQL reconciliation, and restart restoration. Catalyst exposes no second
aggregation choice; Superset's required native metric is deterministically
derived by the exporter without changing Dataset SQL. T187 still owns the
five-family, failure/recovery, repetition/nondeterminism, accessibility,
schema-backed evidence, CI, and explicit user-acceptance gates.

The reconciled design integrates the existing workbench rather than copying the
mock's abbreviated prompt-only flow. Available data remains discoverable before
generation; the latest turn owns the one active SQL editor; a successful Run
creates one Dataset tile whose panel becomes the sole full bounded result
presentation. Earlier turns and review panels are read-only.

## Controlled contracts and invariants

- Exact HTTP, CAS, idempotency, error, pointer, receipt, and status semantics are
  defined in `contracts/dashboard-builder-api.md` and its JSON Schemas.
- A Dataset binds one exact successful execution and its canonical bounded typed
  result identity; it stores no clinical rows. Truncation is explicit and total
  row count remains unknown unless the query itself calculates it.
- Widget compatibility/bindings are deterministic. Table is the fallback;
  proportion is never auto-suggested. The saved Dataset SQL owns report
  aggregation, and Widget review selects only a visualization over that table's
  read-only bindings. Configuration makes no model or database call.
- D1 creates named Dashboards and derives full-width 12-column rows from Widget
  append order. One Dashboard accepts one source/catalog only; cross-source
  placement fails without mutation.
- Bundle identity and Superset UUIDs are deterministic. The archive has the one
  enclosing root required by pinned 6.1.0. Dynamic publication/import IDs and
  times remain outside the ZIP. Layout-only versions reuse unchanged children.
- One global `current.json` selects the most recently published desired
  Dashboard; it is not import truth or recovery state. Prior bundles remain
  content-addressed/downloadable. The importer
  reads the outbox, owns its lock and receipt area, appends immutable attempts,
  atomically replaces a latest-per-digest projection, and advances a separate
  atomic per-Dashboard last-verified projection only after verification.
- Superset stack configuration proves the PostgreSQL driver/network path and
  DB-enforced SELECT-only access. The canonical native fixture owns the
  persisted deterministic analytics Database asset; neither
  `superset_config.py` nor `superset set-database-uri` creates it.
- Catalyst owns the gitignored `runtime/superset/` tree. Importer/state logic is
  standalone Python-3.10-compatible code under `targets/catalyst/scripts/`,
  imports no Catalyst package, and uses only the standard library plus pinned
  Superset-image built-ins. Its tests remain covered by the `catalyst-gateway`
  CI matrix job and `tests/run_tests.sh gateway`, including constrained-
  canonical-JSON parity with `rfc8785` and a pinned-container smoke. The sole
  target-side operator surface is `scripts/mvp-superset.sh
  {status|import|reset}`, routed by the harness; `mvp-up.sh` remains a stack
  lifecycle helper.
- User-visible persisted states are Draft, Bundle ready, Imported, and Import
  failed. Importing may be displayed only from a live digest-specific lock.
- Pointer/bundle/preflight/credential failures and transactionally rolled-back
  Superset CLI failures preserve the previously verified Dashboard. If the CLI succeeds but
  UUID/slug/relationship verification fails, the importer reports Import
  failed, retains the diagnostic, and disables Open/current-success. Recovery
  validates the logical Dashboard's atomic last-verified projection, fully
  resets only the Superset-local metadata database/home volumes, and reimports/
  verifies that exact bundle. Missing/corrupt projection data stops before
  reset. Asset-selective deletion, direct ORM/REST mutation, and automatic
  rollback/retry are prohibited.
- The local Superset connection may carry labelled demo-only credentials but is
  proven SELECT-only. Non-demo bundles require receiver-supplied secrets.

## Validation protocol and checkpoints

### D1a — grounded contracts

Both branches must derive from current `main`; contract schemas must validate;
the Catalyst/harness manifest copies must be byte-identical; the populated Ask
reference must visibly contain one editor and no example prompts; N64–N74 must
own remaining uncertainty; and a SpecKit analysis must report zero unresolved
CRITICAL/HIGH findings before product code.

### D1b — Superset runtime/import

Red tests precede Compose/importer code. Evidence must identify the exact 6.1.0
application/platform and PostgreSQL-driver digests, capture a canonical 6.1.0
export for every supported visualization family, prove the required archive
root and extra JSON-member behavior, and pass clean boot/import, restart,
same-digest no-op, concurrent lock, corrupt/wrong-version input, the scoped
preserving-failure matrix, post-import verification failure with Import failed
and no Open/current-success claim, validated per-Dashboard last-verified
projection, full Superset-local metadata/home reset and verified reimport,
missing/corrupt-projection refusal before reset, recovered-A/failed-desired-B
automatic-bootstrap/retry suppression, write denial, and secret-redaction cases. The
fixture must carry the persisted analytics Database asset; runtime setup proves
only driver/network and DB-enforced read-only access. Fixtures cover the full
renderer-metric behavior and importer tests must be discovered
by Catalyst Gateway CI before the operator wrapper is accepted.

### D1c — builder backend/export

Red storage/route/compiler/export tests precede implementation. Evidence covers
immutable lineage, stale/missing/CAS/idempotency outcomes, deterministic
suggestion/layout/UUIDs, schema-to-native metric mapping, typed parameter escaping, byte-identical ZIPs, atomic
publication/download parity, complete source resolution, changed versus reused
children, all five real fixtures, and zero model/database calls after Run.

### D1d — integrated product UX

Characterize the accepted QueryWorkspace before recomposition. Then prove one
composer/editor/New session action, exact contextual refinement, compact
Available data, one full Dataset result surface, idempotent saves, libraries,
staleness, publish/download/status/open actions, refresh/error recovery, and the
desktop/390×844/320-CSS-pixel/actual-200%-zoom keyboard/focus/status/reduced-
motion matrix. Pause for user UX acceptance.

### D1e — deployed MVP

Use the configured real Gemma 4 12B writer and different-family Qwen 2.5 14B
reviewer when available, with no silent substitution. Generate/edit/validate/run
and follow up; save two exact Dataset versions and heterogeneous Widgets; create,
publish, and import one Dashboard; open its real Superset URL; and reconcile
rendered keyed IDs/values to reproducible PostgreSQL queries. Repeat same digest,
changed child, layout-only reuse, restart, scoped preserving failures, a
post-verification failure plus explicit full-reset/reimport-last-verified recovery,
read-only denial, and all-family clean imports. Record model candidate/digest
variance. Acceptance/event schemas are finalized in D1a/T159; D1e/T181 only
implements their serializer/emitter.

## Evidence contract

The definitive run writes `artifacts/catalyst-dashboard/<run-id>/` with a
versioned `run_manifest.json`, `events.jsonl`, `acceptance.json`, bundle/pointer/
receipt/last-verified-projection copies, PostgreSQL reconciliation, and visual evidence. The acceptance
receipt resolves harness/Catalyst/Hub/Superset/image revisions; profile/model/
configuration and candidate digests; session/turn/query/execution/Dataset/
Widget/Dashboard IDs; bundle/current/receipt digests; the stable Superset URL;
inspected record identifiers/values; reviewer rationale; timing; accessibility;
scoped failure classification; and explicit full-reset/reimport recovery.
`events.jsonl` includes structured `query_turn`, `query_version`, and
`query_execution` D1 projections, and `acceptance.json` carries the fixed
six-step `orderedWorkflow` through Dataset v2 save. Evidence
must distinguish preservation supported before/within a failed CLI transaction
from the no-rollback post-verification boundary. Aggregate counts, health alone,
screenshots alone, or a generated ZIP do not close D1.

## Impact, rollback, and residual risk

The accepted Ask/workbench routes and exact Run behavior remain compatible.
Rollback hides/disables Dashboard Builder routes and UI, stops Superset services,
and restores the prior QueryWorkspace presentation while retaining append-only
Catalyst evidence and content-addressed bundles. That product-feature rollback
is separate from import recovery. Before recovery, the operator validates
`receipts/last-verified/<logicalDashboardId>.json`, its immutable receipt, bundle,
and digests; missing/corrupt evidence stops before reset. The local-only full
reset removes the complete Superset-local metadata database/home volumes,
retains outbox and immutable import attempts, then initializes and explicitly
reimports/verifies the projected bundle. It never selectively deletes assets or
writes through Superset ORM/REST, and is never triggered automatically. If A is
recovered while failed desired B remains in `current.json`, B remains
`import_failed` and automatic bootstrap/retry stays suppressed until explicit
retry or a new publication. Normal startup and publication never reset metadata.
A post-import verification failure may follow partial
Superset mutation, so the system makes no prior-dashboard usability or automatic
rollback claim; it reports Import failed, disables Open/current-success, and
retains the diagnostic until explicit recovery succeeds.

No clinical result rows enter Dashboard Builder storage or the bundle. Original
parameterized SQL and ordered typed values are portable provenance and may
contain demo identifiers; access remains local-demo scoped. Credentials, DSNs,
raw traces, hidden reasoning, and result rows are forbidden from manifests,
receipts, diagnostics, and run metadata.

Residual risks are Superset release-coupled YAML/`params`, container/driver
availability by architecture, host/container file ownership, semantic limits of
deterministic chart suggestions, full-query results differing from a bounded
preview, model variance, orphaned immutable Superset children, and ephemeral
Superset-only edits. Post-import verification after a successful CLI can expose
partial Superset mutation until explicit full-reset/reimport recovery. N64–N74 assign
each risk to a checkpoint. A failed gate is reported and reviewed; tests or
evidence are not weakened to claim completion.

## Approval and completion

The user selected the Superset-backed Dashboard Builder direction and requested
this groundedness revalidation plus implementation through a real deployed MVP.
D1 nevertheless remains open until D1d UX review and D1e deployed-dashboard
evidence receive explicit user acceptance.
