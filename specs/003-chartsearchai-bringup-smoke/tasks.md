# Tasks: ChartSearchAI Bring-Up + Smoke (003)

## Phase A — Artifacts (003.1)

- [X] A.1 — `spec.md` written with FRs + SCs + demo patient anchor
- [X] A.2 — `plan.md` with architectural decisions + risk register
- [X] A.3 — `tasks.md` (this file)

## Phase B — Build chartsearch images (003.2 + 003.3)

- [ ] B.1 — `compose/chartsearchai/Dockerfile.backend` — variant that COPYs from local `targets/chartsearchai/` instead of `git clone`. Wrapper `harness-init.sh` to inject `chartsearchai.llm.remote.apikey` into `openmrs-runtime.properties`.
- [ ] B.2 — `compose/chartsearchai/Dockerfile.frontend` — bake @openmrs/esm-chartsearchai-app into SPA. ESM still `git clone --depth 1` (no submodule).
- [ ] B.3 — `compose/chartsearchai/spa-build-config.json` — copy of upstream
- [ ] B.4 — `compose/chartsearchai/harness-init.sh` — runtime-properties injector
- [ ] B.5 — `docker compose -f compose/openmrs-2.8-chartsearch.yml build` succeeds locally

## Phase C — Compose + env wiring (003.4 + 003.5)

- [ ] C.1 — `compose/openmrs-2.8-chartsearch.yml` — backend/frontend/gateway/db services with chartsearch- prefix; own network
- [ ] C.2 — DB seed via `/docker-entrypoint-initdb.d/01-load-openmrs.sql.gz` mount
- [ ] C.3 — `.env.chartsearch.example` documenting all env vars
- [ ] C.4 — Makefile targets: `chartsearch-build`, `chartsearch-up`, `chartsearch-down`, `chartsearch-logs`, `chartsearch-smoke`

## Phase D — First boot + module verification (003.6)

- [ ] D.1 — `make chartsearch-up` succeeds (image build cached + container start + Liquibase + module init)
- [ ] D.2 — `GET /ws/rest/v1/module` includes `chartsearchai` with `started: true`
- [ ] D.3 — Zabella Halambe reachable: `GET /ws/rest/v1/patient/dd75c020-1691-11df-97a5-7038c432aabf`
- [ ] D.4 — `POST /ws/rest/v1/chartsearchai/search` against a test question returns a structured response (non-empty `answer`, `references[]`)

## Phase E — Playwright workspace (003.7)

- [ ] E.1 — `evals/playwright/package.json` with `@playwright/test`
- [ ] E.2 — `evals/playwright/playwright.config.ts` — Chromium headless, base URL from `CHARTSEARCH_BASE_URL` env
- [ ] E.3 — `evals/playwright/tests/chartsearchai.smoke.spec.ts` — login → search → chart → AI panel → question → assertions
- [ ] E.4 — `evals/playwright/.gitignore` — ignore node_modules + test-results + playwright-report
- [ ] E.5 — `evals/playwright/fixtures/demo-patient.json` — Zabella UUID + name

## Phase F — End-to-end smoke (003.8)

- [ ] F.1 — Set `CHARTSEARCH_REMOTE_API_KEY` (user-provided), boot stack, run `make chartsearch-smoke`
- [ ] F.2 — Smoke passes against remote engine
- [ ] F.3 — Test report committed under `evals/playwright/test-results/last-known-good.json` (single artifact, not full report)

## Phase G — Documentation + PR (003.9)

- [ ] G.1 — Update `specs/003-chartsearchai-bringup-smoke/spec.md` Success Criteria with measured timings + screenshot
- [ ] G.2 — Update `quickstart.md` (root README or specs/002 quickstart) with §10: "Bring up chartsearchai"
- [ ] G.3 — Open PR with title `feat(003): chartsearchai bring-up + Playwright smoke on Zabella Halambe`
- [ ] G.4 — Optional: site canvas `chartsearchai-bringup.canvas.tsx`
