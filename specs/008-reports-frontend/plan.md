# Implementation Plan: Validation Run Reporting Platform

**Branch**: `008-reports-frontend` | **Date**: 2026-06-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-reports-frontend/spec.md`

## Summary

Replace the three hand-generated HTML surfaces (run catalog, per-run report, live dashboard) and the
full-HTML republish / whole-directory-rsync model with one DB-backed application: a queryable store of
runs/artifacts/data and a single shared presentation. Per the scope decision, the unified app also owns
catalog curation (was `feat/editable-reports-homepage`) and human review/adjudication (was
`feat/report-human-feedback`). Stack: a NestJS API + a Vite/React SPA over SQLite-via-Prisma. The Python
harness stays the sole producer of run artifacts; a one-way **idempotent ingest** loads its JSONL plus the
additive producer-computed `summary.json` aggregate export into the store. The load-bearing boundary
(research Decision 5): **scoring stays in the harness — the platform ingests producer-computed numbers and
never re-implements scoring in TypeScript**, so the refactor removes the current Python/JS presentation
duplication rather than relocating it.

## Technical Context

**Language/Version**: TypeScript on Node.js 20 LTS (API, ingest, frontend). The existing harness remains
Python 3.11 — the unchanged producer of run artifacts.

**Primary Dependencies**: NestJS (HTTP API + modular DI), SQLite runtime persistence, Prisma schema +
migrations for the normalized target model, Vite + React 18 (SPA), `recharts` (score charts — already
proven in `site/`).

**Storage**: SQLite (file) for v1. The shipped runtime persists the report store to SQLite and includes a
Prisma schema/migration for the normalized target model; fully normalized Prisma repositories remain the
next persistence-hardening step before a Postgres swap. The store holds run **metadata + scores + traces +
human reviews + curated prose**; it **references** (never re-stores) clinical chart records.

**Testing**: Vitest (frontend + shared types), the Nest test runner (API + ingest), red-first per
Constitution V; optional Playwright for one end-to-end smoke. Priority targets: ingest mapping
(judged-sibling lineage, trace correlation by served-model identity, partial/unscored runs), API
contracts, human-review calibration, edge-case rendering. Final merge/release readiness includes a
`DIGI-UW/code-qa` polishing and validation gate for spec-code alignment, meaningful test coverage,
simplicity review, evidence bundling, and commit/PR hygiene.

**Target Platform**: a Node service (NestJS serving the API + the built SPA) behind Caddy on the GCE VM
(reverse-proxy `reports.openclinai.org`, replacing the `file_server` over `/srv/reports`); local dev via
the Vite dev server + the Nest dev server.

**Project Type**: web application — backend API + frontend SPA — plus a one-way ingest from the Python
harness's file artifacts.

**Performance Goals**: catalog and per-run report load in <1s for a typical run; a reader can locate a
run by model/arm, comparison set, or date and open its report in <30s without knowing run identifiers;
publish/curate is O(1) (no whole-index rebuild, no whole-directory sync); ingest of a completed run in a
few seconds; per-report payloads are materially smaller than today's 1–2 MB self-contained HTML.

**Constraints**: the Python harness remains the SOLE producer of run artifacts AND the owner of
scoring/aggregation — the platform ingests computed values from the producer `summary.json` aggregate
export and never re-implements scoring (the seam); any temporary ingest compatibility path may only load
already-computed producer fields and must not derive benchmark/per-arm scoring semantics; clinical chart
records are referenced, not re-stored; the LLM/agent-readable need is met by the JSON API (no separate
static HTML twin required).

**Scale/Scope**: tens to low-hundreds of published runs; ~hundreds of cells per run; a handful of
reviewers; four surfaces (catalog, report, live, review) rendered from one shared component set.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Real production paths**: **PASS** — the platform ingests and displays the REAL harness artifacts
  (`results.jsonl`, `judge.jsonl`, `trace.jsonl`, manifests). It does not simulate validation; it
  presents the harness's real outputs. Sample runs used in tests are labeled fixtures/scaffolding, not
  release evidence.
- **Deterministic reviewed transforms**: **PASS** — the ingest (artifact JSONL → DB) is deterministic,
  reviewed code, repeatable from a clean DB; the scoring/aggregation stays in the harness's reviewed
  Python (the platform ingests computed values, not re-derived ones — research Decision 5).
- **Record-level evidence**: **PASS** — the platform preserves and *surfaces* record-level evidence
  (per-cell citations, judge notes, reasoning traces, human-review rationale) and the chain from an
  answer to its supporting records; it strengthens rather than hides that chain (FR-015, FR-018).
- **Metadata and provenance**: **PASS** — the harness remains the emitter of `run_manifest.json` /
  `events.jsonl` / provenance; this platform is a faithful CONSUMER that preserves the provenance chain
  in its store for query and display, never altering it. (No new run evidence is *produced* here.)
- **Tests define behavior**: **PASS** — red-first tests for the ingest mapping (judged-sibling lineage,
  trace correlation, partial/unscored runs), the API contracts, the review calibration, and edge-case
  rendering; tests cover scenario diversity (the spec's edge cases), not one fixture.
- **Data boundaries and governance**: **PASS** — the store holds run metadata + scores + traces + review
  records + reports (the constitution's sanctioned harness store) and references clinical chart records;
  the LLM-advisory vs human-review-reference boundary is preserved (FR-018). This feature changes no
  model/prompt/retrieval behavior, so no PCCP record is required for it; the one producer-side scoring
  export (Decision 5) carries its review context in the harness repo.
- **Why this is sufficient**: the platform is a presentation/query layer over the harness's real
  validation evidence. It preserves provenance, record-level evidence, and decision rationale; keeps the
  clinical-data and advisory/reference boundaries; leaves scoring with the reviewed producer; and is
  covered by red-first tests over diverse scenarios. It therefore strengthens, not weakens, the evidence
  chain the harness produces.

## Project Structure

### Documentation (this feature)

```text
specs/008-reports-frontend/
├── plan.md              # This file
├── research.md          # Phase 0 output (8 decisions, incl. the scoring seam)
├── data-model.md        # Phase 1 output (entities → schema)
├── quickstart.md        # Phase 1 output (dev/run/ingest walkthrough)
├── contracts/           # Phase 1 output (REST API + ingest + SSE contracts)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
reports-app/                     # the unified reporting platform (NEW top-level, sibling to site/)
├── api/                         # NestJS backend
│   ├── src/
│   │   ├── runs/                # runs + lineage (read)
│   │   ├── results/             # cells/results + references (read)
│   │   ├── judging/             # judge rows + producer-computed aggregates (read)
│   │   ├── traces/              # reasoning traces (read)
│   │   ├── reviews/             # human adjudication + calibration (read + write)
│   │   ├── catalog/             # published reports + curation: prose/order/feature/hide (read + write)
│   │   ├── ingest/              # JSONL artifact → DB ingest; live tail + SSE
│   │   └── prisma/              # schema.prisma + migrations
│   └── test/
├── web/                         # Vite + React 18 SPA
│   ├── src/
│   │   ├── components/          # the ONE shared set: ArmCard, ConfidenceSection, TraceSteps,
│   │   │                        #   ScoreTable, AnswerTile, RefList
│   │   ├── routes/              # catalog · report · live · review
│   │   └── api/                 # typed client (consumes shared DTOs)
│   └── test/
└── shared/                      # DTO/types shared by api + web

# Unchanged — the producer + the ingest source:
harness/                         # Python harness — still produces results/judge/trace/manifest
artifacts/validate/<run>/        # ingest source (unchanged)
compose/Caddyfile                # reports.openclinai.org: file_server → reverse_proxy → reports-app/api
```

**Structure Decision**: a new top-level `reports-app/` (sibling to `site/`), a small monorepo of
`api/` (NestJS), `web/` (Vite + React), and `shared/` (DTOs). The Python harness and `artifacts/` remain
the producers; the required producer-side touch is the additive `judge-finalize` aggregate export
(`summary.json`, research Decision 5), which lands in the harness repo's own flow before durable ingest
validation. The Caddy `reports` site block flips from `file_server` to `reverse_proxy`.

## Complexity Tracking

No constitution gate failed; no violations to justify. (The one cross-language boundary — Python
producer / TypeScript platform — is deliberately contained by research Decision 5: the platform ingests
producer-computed numbers and holds no scoring logic, so it adds no duplication.)
