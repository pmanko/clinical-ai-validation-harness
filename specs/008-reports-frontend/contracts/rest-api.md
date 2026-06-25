# API & Interface Contracts: Validation Run Reporting Platform

**Feature**: 008-reports-frontend · **Date**: 2026-06-25

The platform exposes a JSON REST API (consumed by the SPA and by agents), one SSE stream (live runs),
and an ingest CLI (the harness→DB boundary). Response shapes reference the entities in `data-model.md`.
All read endpoints serve **producer-computed** scores (research Decision 5) — no scoring is computed here.

## Catalog (US1, US2, US5)

- `GET /api/catalog` — published runs for the index. Each item: `{slug, title, summary, takeaway, arms[], nQuestions, date, headline: ArmAggregate[], featured, hidden, sortOrder, hasLive}`. Query filters: `?model=&comparisonSet=&from=&to=&sort=` (FR-002, FR-011). Score filtering is deferred from v1 unless added explicitly to this contract and its tests. Hidden runs excluded unless `?includeHidden=true`.
- `GET /api/catalog/meta` — `{intro, scoringNote}` (CatalogMeta).
- `POST /api/catalog` — publish a run: body `{runId, slug, title?, summary?, takeaway?}` → creates a PublishedReport; does NOT re-render or touch any other run (FR-005). 409 if slug exists.
- `PATCH /api/catalog/:slug` — curate: body any of `{title, summary, takeaway, sortOrder, featured, hidden}` → updates only this entry; scores stay data-derived (FR-006, FR-016).

## Runs & reports (US1)

- `GET /api/runs/:runId` — run header: `{runId, comparisonSet, referenceDate, status, parentRunId?, arms[], nScenarios, gitSha, generatedAt}`.
- `GET /api/runs/:runId/report` — full report payload: `{run, armAggregates[], scenarios[] -> {turns, cells[]}}` where each cell = `{arm, answer, references[], trace?, indepth?, judge?, adjudications[], confidence}` (FR-003). Cells with no `judge` are flagged `scored:false`, never omitted (FR-010).
- `GET /api/runs/:runId/cells/:scenarioId/:armId` — one cell drill-down (answer, references, trace steps, indepth, judge, adjudications) — the report and live views share this shape.
- `GET /api/runs/:runId/export` (alias `/api/runs/:runId.json`) — machine-readable structured data: arms, ArmAggregates, per-cell answers/traces/judge, adjudications — for agents, without HTML (FR-012).

## Human review (US3)

- `GET /api/runs/:runId/reviews` — `{adjudications[], calibrated?: {subset: {label, nCells, tiers[]}, estimate, uncertainty: {method, value?, interval?}}}`. The calibrated block is present only when a reviewed subset exists, is labeled to that subset, and does not claim calibration outside the reviewed cells (FR-019).
- `POST /api/runs/:runId/reviews` — submit an adjudication: body `{scenarioId, armId, reviewerId, axes, harm, note}` → appends an Adjudication; never overwrites another reviewer's (FR-017, FR-018). Returns the stored record + the refreshed calibrated block.

## Live (US4)

- `GET /api/runs/:runId/live` — **SSE**. Events: `cell` (`{scenarioId, armId, turn, status, latencyMs}` as each completes), then `cell:detail` (the drill-down payload), `done`. Backed by the ingest watcher tailing the active run (FR-013). The SPA renders these with the same components as the static report.

## LLM/agent-readable (research Decision 7)

- `GET /llms.txt` — the agent index (catalog + per-run links), replacing today's static HTML twins.
- `GET /api/runs.json` — the full machine-readable run/catalog index.

## Ingest CLI (the harness→DB boundary, FR-014)

- `reports-ingest <run_dir>` — idempotent upsert of a completed run (Result/JudgeRow/ArmAggregate/Trace by unique keys). Trace correlation resolves `resultId` by `levelId == arm.modelName` + time window, NOT `backendId` (FR-008).
- `reports-ingest --watch <run_dir>` — tail an active run; drives the live SSE (US4).
- Reads `artifacts/validate/<run>/{results,judge,events}.jsonl`, the run manifests, `hub-trace/trace.jsonl`, and the required producer-computed `summary.json` (the ArmAggregate export, research Decision 5). It never reaches into harness internals — the artifacts are the contract. Until `summary.json` lands in the producer, tests may use only a documented compatibility fixture that already contains producer-computed aggregate fields; the ingest must not synthesize benchmark/per-arm aggregates from JudgeRows.

## Cross-cutting

- All automated aggregate scores served are ingested producer-computed values (Decision 5); the API holds no benchmark/per-arm scoring logic.
- Errors: 404 unknown run/slug; 409 duplicate slug; 422 invalid adjudication payload; partial/unscored runs are 200 with `scored:false` flags, not errors.
