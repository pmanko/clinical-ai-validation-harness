# Dashboard Builder delivery goal

**Status:** The binding design and query-notebook browser behavior are accepted. Final
Phase 3 implementation and browser-visible acceptance remain open.

Phase 1 requires one Dataset-to-Superset regression smoke through the generic
connection. That smoke does not complete or reduce this goal. Phase 2 is defined
after the Phase 1 report; Dashboard Builder completion follows as Phase 3.

## Goal

Deliver a manually testable Catalyst workflow in which a person:

1. asks a question through the configured model profile;
2. reviews, edits, formats, and runs the exact SQL;
3. saves a successful execution as an immutable Dataset;
4. creates and reviews multiple Widgets;
5. arranges a Dashboard;
6. publishes a deterministic native Superset bundle;
7. imports it and opens the stable URL; and
8. inspects the rendered dashboard.

The binding interaction and visual contract is
`targets/catalyst/docs/dashboard-builder-mvp-design.md` and its populated
binding 4c page. Current product requirements and tasks live in
[spec.md](spec.md) and [tasks.md](tasks.md).

## Phase 1 regression smoke

Phase 1 covers one narrow Dashboard path:

- a successful exact query is saved and restored after refresh;
- its Dataset is published and imported through the accepted Spark connection;
- Superset renders it;
- one displayed value is inspected against the originating Catalyst result
  without a second database query; and
- the chosen Spark query path cannot mutate source data.

This proves the generic connection reaches Superset. It is not final
Dashboard Builder acceptance.

## Phase 3 definition of done

### Workbench and thread

- The live product is compared side by side with the binding design.
- Profile and model selection, one active SQL editor, fixed composer,
  chronological thread, New session, Format, explicit Run, advisory findings,
  typed parameters, generation and failure evidence, database errors,
  Clear/Restore, query versions, stale-result behavior, and refresh restoration
  remain present.
- Available data exposes every readable relation and column through the compact
  disclosure and full searchable, filterable, paginated view, including empty
  and failure states.
- Earlier turns are readable summaries and only the latest turn owns the editor.

### Dataset, Widget, and Dashboard

- Only a successful execution for the exact current query creates or refreshes a
  Dataset draft.
- The Dataset review panel owns the full bounded typed result table.
- Dataset saves are immutable and idempotent and retain source, dialect,
  readable-schema snapshot, query, and execution identity.
- Visualization compatibility and the initial suggestion are deterministic from
  the typed result shape; the person reviews or chooses another compatible type.
- Widget and Dashboard libraries show saved immutable versions.
- A Dashboard arranges multiple same-source Widgets and preserves the accepted
  layout behavior.

### Publication and Superset

- Publish creates a deterministic native Superset bundle in the outbox and
  exposes the same bytes for download.
- Status follows explicit importer receipts. A file's existence alone is not
  shown as imported.
- Failures remain actionable and do not expose a false success or Open action.
- The stable Dashboard URL opens only after successful import.
- Superset renders the originating saved Datasets through the configured
  connection.
- One displayed value is inspected against its originating Catalyst result;
  there is no separate database reconciliation path.

### Accessibility and owner acceptance

- Focus order, visible focus, Escape/return behavior, announcements, reduced
  motion, desktop, and the accepted narrow-layout checks pass.
- The owner walks the live Workbench, Dataset review/library, Widget
  review/library, Dashboard library/arrangement, and every publish/import state
  side by side with the binding design and accepts the result.

## Focused implementation work

- Add public route coverage for Dataset, Widget, Dashboard, and publication
  actions.
- Finish lossless typed execution-to-Dataset conversion for the active dialect.
- Finish deterministic visualization compatibility, bundle generation, and
  receipt-based publication status.
- Run the real model-assisted browser workflow through Spark.
- Capture only the source, dialect, readable schema, model setup, query and
  execution, asset and receipt, screenshots, and accessibility results needed to
  understand the visible flow and diagnose a failure.

## Not required

This goal does not require repeated model runs, restart/reset matrices,
environment parity, direct database reconciliation, exhaustive infrastructure
failure simulation, Superset application programming interface publication,
embedded Superset, bidirectional synchronization, sharing, scheduling,
automatic refresh, production access control, or model-generated visualization
specifications.
