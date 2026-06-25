# Phase 0 Research: Validation Run Reporting Platform

**Feature**: 008-reports-frontend · **Date**: 2026-06-25

The technical direction (NestJS API + Vite/React SPA + a DB) was specified by the requester; this
document records the concrete decisions, their rationale, and the alternatives weighed — including the
one load-bearing architectural seam (Decision 5) that determines whether the refactor actually removes
duplication or merely relocates it. Grounded in the four-part investigation of the current
report/index/dashboard/publish stack and the file-based data model.

## Decision 1 — Backend: NestJS (TypeScript)

- **Decision**: NestJS for the API, organized as one module per domain (`runs`, `results`, `judging`, `traces`, `reviews`, `catalog`, `ingest`).
- **Rationale**: the requester's choice; the modular DI structure *is* the "cleanliness + eventual extensibility" goal — a new surface (cross-run analysis, a new review tier) is a new module, not a rewrite. TypeScript lets the API and the Vite frontend share DTO types.
- **Alternatives**: (a) Python FastAPI — keeps scoring in-language (no Python↔TS boundary) but a weaker frontend story and diverges from the stated stack; (b) thin Fastify/Express — lighter but less structure for the extensibility target. NestJS chosen; the Python↔TS boundary is managed by Decision 5.

## Decision 2 — Frontend: Vite + React 18 (recharts)

- **Decision**: a Vite + React 18 SPA; `recharts` for score charts.
- **Rationale**: matches the existing `site/` docs SPA (React 18 + Vite + Vitest, `recharts`/`dagre` already bundled) — reuse its proven build and prerender conventions. "Simple" = one small shared component set (arm card, confidence treatment, trace, score table, answer tile) rendered once across the catalog / report / live / review routes.
- **Alternatives**: vanilla / Svelte / Vue — lighter but diverge from `site/`'s proven stack and lose the `recharts` reuse. React chosen for consistency with the existing investment.

## Decision 3 — Store: SQLite via Prisma (Postgres-ready)

- **Decision**: SQLite (a file) behind Prisma for v1; Postgres a configuration change later.
- **Rationale**: zero-infra matches "simplicity" and the single-VM deploy; Prisma gives typed models (shared with the API), migrations, and an easy Postgres swap. The schema maps ~1:1 from the data model. The store holds run **metadata + scores + traces + reviews + curated prose** — the constitution's sanctioned harness store — and **references** (does not re-store) clinical chart records.
- **Alternatives**: Postgres from day 1 (more infra than tens–hundreds of runs need); a document store (loses the relational queries — comparison-set membership, judged-sibling lineage, and catalog filtering are relational). SQLite+Prisma chosen for zero-infra plus a clean Postgres path.

## Decision 4 — Ingest: pull from the harness's JSONL artifacts

- **Decision**: a one-way ingest service reads `artifacts/validate/<run>/*.jsonl` (+ the shared `hub-trace/trace.jsonl`) and upserts the DB — **idempotent and re-runnable**. The settled/published path ingests on run completion (a CLI/command); the live path tails the active run's growing `results.jsonl`.
- **Rationale**: keeps the Python harness the SOLE producer (FR-014) — the JSONL is the contract; the platform never reaches into harness internals. Idempotent ingest makes re-ingesting after a re-judge or scoring change safe. Pull (vs push) decouples the two: the harness needs no knowledge of the platform.
- **Alternatives**: (a) the harness POSTs to the API (push) — couples the harness to the platform; (b) the harness writes the DB directly — a Python↔DB coupling that duplicates the schema across two languages. Pull-ingest chosen for decoupling.

## Decision 5 — The scoring seam: the harness computes, the platform ingests numbers (load-bearing)

- **Decision**: score aggregations (the headline benchmark, per-arm `scout_summary`, confidence, citation resolution) are computed ONCE by the harness's reviewed Python (`reconcile.py`) and **exported into the ingestable artifacts**; the platform ingests and serves those numbers and **never re-implements scoring in TypeScript**.
- **Rationale**: this is the boundary that makes the refactor real. Re-implementing `reconcile.py` in TypeScript would RECREATE the duplication the refactor exists to kill (scoring in Python *and* TS, with drift risk) — only in a new pair of languages. Today these aggregates are derived at render time in `report.py`; shift that to a harness export step (`judge-finalize` writes the computed per-arm summary), so the platform is pure presentation/serving. Satisfies Constitution II (accepted behavior lives in reviewed code) and III (numbers trace to the reviewed computation, not a re-derivation).
- **Alternatives**: (a) re-implement scoring in TS — rejected (recreates the duplication + drift); (b) a Python scoring microservice the API calls per request — more moving parts than an export-at-finalize. Export-at-finalize chosen.
- **Producer-side implication**: one small harness change — `judge-finalize` (or a new export step) writes the computed per-arm aggregates into a stable artifact (e.g. `summary.json`) the ingest reads. This is the only producer change; the rest of the harness is untouched, preserving FR-014.

## Decision 6 — Live view: Server-Sent Events over a tailing read

- **Decision**: the live view tails the active run's growing `results.jsonl`/`trace.jsonl` and pushes cell-completion events to the SPA over **Server-Sent Events (SSE)**; the published (settled) path is a normal DB read.
- **Rationale**: SSE is the simplest one-way live channel for "cells appear as they complete," reusing the same components as the static report (FR-013). The live path is P4 — sequenced after the static path proves the data model.
- **Alternatives**: polling (today's 2s dashboard poll — simple but chatty); WebSockets (bidirectional, overkill for a one-way feed). SSE chosen as the simple one-way channel.

## Decision 7 — Deploy: Caddy reverse-proxies the Nest app (replacing `file_server`)

- **Decision**: Caddy reverse-proxies `reports.openclinai.org` to the NestJS service (which serves the API and the built SPA); the SQLite file and the ingest run on the VM. Replaces today's Caddy `file_server` over `/srv/reports` and the whole-directory `rsync`.
- **Rationale**: a running, DB-backed app is the target — no per-report HTML, no whole-dir sync; publish = a DB row. The LLM/agent-readable need that static HTML twins serve today is met by the JSON API plus an `llms.txt` / `runs.json` endpoint (Decision 2 keeps `site/`'s twin pattern available if a static export is later wanted).
- **Alternatives**: static SSG (Vite prerender → files, like `site/`) — keeps the `file_server` model but loses the editable catalog, human review, live feed, and cross-run query the spec requires. A running app chosen.

## Decision 8 — Testing: Vitest + the Nest test runner, red-first

- **Decision**: Vitest for the frontend and shared types; the Nest test runner for the API and ingest; red-first per Constitution V. Priority test targets: the ingest mapping (judged-sibling lineage, trace correlation by served-model identity, partial/unscored runs), the API contracts, the human-review calibration, and the rendering of the spec's edge cases.
- **Rationale**: Constitution V requires tests that fail before implementation and cover scenario diversity, not one fixture. The spec's edge cases become the red-first tests; notably, the current trace-correlation defect (cell matched by `backend_id` while the trace keys on the served model name) becomes an explicit regression test in the ingest's correlation logic.

## Open producer-side note (not a blocker)

The single harness change Decision 5 implies (exporting computed per-arm aggregates at `judge-finalize`) is small and additive; it can land in the harness repo's normal flow. Until it does, the ingest can fall back to reading the raw judge axes and the platform can carry a thin, clearly-marked compatibility shim — but the durable design ingests producer-computed numbers (no scoring logic in the platform).
