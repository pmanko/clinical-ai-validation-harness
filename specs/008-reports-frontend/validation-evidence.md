# Validation Evidence: Reports Frontend

Generated during `/speckit-implement` after implementation of the DB-backed reports platform.

## Spec-Code Alignment

- `reports-app/` implements the planned API, SPA, shared DTOs, ingest CLI, live SSE, review, catalog,
  and export surfaces.
- The runtime is SQLite-backed through `SqliteReportStore`; Prisma schema/migrations under
  `reports-app/api/src/prisma/` define the normalized persistence target and were aligned in the plan and
  data model after implementation.
- The producer scoring boundary is implemented in Python via
  `harness.validate.report.write_summary_export()`, which writes `summary.json` from
  `scout_summary()`. The TypeScript platform ingests aggregate rows and does not derive benchmark or
  per-arm Scout scores.

## Meaningful Test Coverage

The suite includes right-level guards for the main failure modes:

- API/integration: ingest trace correlation, judged-sibling lineage, idempotency, unscored cells,
  no TypeScript aggregate synthesis, catalog/report contracts, curation O(1), reviews, live SSE,
  query/export, payload/perf, and SQLite persistence.
- Web/component: report route renders team-arm trace evidence and answered-but-not-scored cells through
  shared components.
- Producer/unit: `write_summary_export()` writes producer-owned `summary.json` from the reviewed Python
  aggregation path.

## Simplicity Review

- Kept one shared React component set (`ArmCard`, `ConfidenceSection`, `TraceSteps`, `ScoreTable`,
  `AnswerTile`, `RefList`) and reused it across report/live/catalog paths.
- Avoided a second TypeScript scoring layer; aggregate scoring remains producer-owned.
- Deferred full normalized Prisma repositories to a future persistence-hardening step rather than adding
  a large async repository refactor during this implementation.

## Evidence Commands

```bash
npm --prefix reports-app run lint --workspaces --if-present
npm --prefix reports-app test --workspaces --if-present
npm --prefix reports-app run build
uv run --extra dev pytest tests/test_summary_export.py
```

Observed result:

- API: 8 files, 10 tests passed.
- Web: 1 file, 1 test passed.
- Shared: 1 file, 1 test passed.
- Python producer summary export: 1 test passed.
- Reports app build passed.

## Residual Risk

`npm audit` reports unresolved transitive advisories in current Prisma/Nest dependency chains. A
non-breaking `npm audit fix` did not resolve them; `npm audit fix --force` proposes breaking dependency
changes, so it was not applied automatically.
