# Quickstart: Validation Run Reporting Platform

**Feature**: 008-reports-frontend · **Date**: 2026-06-25

Lives in `reports-app/` (a sibling to `site/`): `api/` (NestJS), `web/` (Vite + React), `shared/` (DTOs).
The Python harness is unchanged — it produces `artifacts/validate/<run>/`, which the ingest consumes.

## Prerequisites

- Node.js 20 LTS + a package manager (npm/pnpm).
- Harness run artifacts under `artifacts/validate/<run>/` (the ingest source).

## Local development

1. `cd reports-app/api && npm install && npx prisma migrate dev` — creates the SQLite DB + schema.
2. `npm run dev` — the Nest API on `:3001`.
3. `cd reports-app/web && npm install && npm run dev` — the Vite SPA on `:5173` (proxies `/api` → `:3001`).
4. Open `http://localhost:5173` — the catalog (empty until you ingest a run).

## Ingest a completed run

```
cd reports-app/api
npm run ingest -- ../../artifacts/validate/<run_id>
```

Idempotent: re-run safely after a re-judge or a scoring-export change (upserts by unique keys). The
catalog shows the run; open its report.

## Watch a live run

```
npm run ingest -- --watch ../../artifacts/validate/<active_run_id>
```

Tails `results.jsonl`, feeds the SSE; open `/runs/:id/live` to watch cells fill in.

## Publish + curate (no file editing — FR-016)

In the app: publish a run from the catalog, edit its title/summary/takeaway, reorder, feature, or hide —
all in the UI. Scores stay data-derived; only the prose/order/visibility are curation state.

## Human review (FR-017–019)

Open a run's report → review mode → score a cell (accuracy/completeness/relevance, harm, note) as a
reviewer with a tier (owner / domain / clinical). Human scores show alongside the advisory LLM-judge
scores; once a reviewed subset exists, a calibrated headline with its uncertainty appears.

## Deploy (GCE VM)

- Build the SPA: `cd reports-app/web && npm run build` → static bundle served by the Nest API.
- Caddy: change the `reports.openclinai.org` block from `file_server /srv/reports` to
  `reverse_proxy` → the Nest service.
- The SQLite file + the ingest run on the VM; ingest on run completion (publish = a DB row, no rsync).

## Tests (red-first, Constitution V)

- API + ingest: `cd reports-app/api && npm test`.
- Web + shared: `cd reports-app/web && npm test` (Vitest).
- Priority red-first targets: ingest trace-correlation (by `modelName`, not `backendId`), judged-sibling
  lineage, unscored-run rendering, multi-reviewer adjudication (no overwrite), and the calibrated
  headline over a reviewed subset.

## Producer-side note (research Decision 5)

The ingest reads a producer-computed `summary.json` (per-arm aggregates the harness writes at
`judge-finalize`). Until that export lands, the ingest can fall back to a clearly-marked compatibility
shim — but the durable design ingests producer-computed numbers; the platform holds no scoring logic.
