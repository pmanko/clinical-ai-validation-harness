# Validation Reports App

DB-backed reporting platform for validation runs. The app has three workspaces:

- `api/`: NestJS API, ingest CLI, SQLite-backed report store, Prisma schema, and contract tests.
- `web/`: Vite/React SPA for catalog, report, live, and review surfaces.
- `shared/`: DTOs shared by API and web.

## Local Development

```bash
npm install
DATABASE_URL="file:./reports.db" npm run dev -w @reports/api
npm run dev -w @reports/web
```

The web app runs on `http://127.0.0.1:5173` and proxies `/api` to the API on port `3001`.
The Prisma schema/migrations in `api/src/prisma/` define the normalized persistence target; the current
runtime persists the report store snapshot to the SQLite database configured by `DATABASE_URL`.

## Ingest

```bash
npm run ingest -w @reports/api -- ../../artifacts/validate/<run_id>
```

The ingest reads `results.jsonl`, `judge.jsonl`, `events.jsonl`, `run_manifest.json`,
`hub-trace/trace.jsonl`, and the producer-computed `summary.json`. The app must not derive
benchmark or per-arm aggregate scoring in TypeScript.

## Validation

```bash
npm test --workspaces --if-present
npm run build
```

Before merge/release, run the `DIGI-UW/code-qa` validation gate from the feature task list:
spec-code alignment, meaningful-test-coverage, simplicity-review, evidence-bundle, and
commit-pr-hygiene.
