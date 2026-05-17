# Plan: ChartSearchAI Bring-Up + Smoke (003)

**Predecessor**: 002 delivered `openmrs_test` with 5,284 legacy patients + portable dump.
**Branch**: `003-chartsearchai-bringup` cut from `main` after PR #10 merge.

## Architectural decisions

### D-003.1 — Isolated stack, own DB seeded from dump

The chartsearchai backend will run alongside (not replace) the harness's existing 3.6.0 RefApp backend. To avoid Liquibase races (3.6.0 backend and `:nightly-chartsearch` backend both managing the same schema), the chartsearch stack owns its own MariaDB and seeds it on first boot from feature 002's `refapp_28_demo.sql.gz` dump.

- Base stack (`compose/openmrs-2.8-refapp.yml`): unchanged. Stays at port `${HARNESS_PROXY_HTTP_PORT:-8088}` against `harness-openmrs-db.openmrs_test`.
- Chartsearch stack (`compose/openmrs-2.8-chartsearch.yml`): new. Port `${CHARTSEARCH_PROXY_HTTP_PORT:-8089}` against `chartsearch-db.openmrs`.

### D-003.2 — Build locally, pin to submodule

Harness-owned `compose/chartsearchai/Dockerfile.backend` mirrors the upstream multi-stage shape (Java 11 builder → Ubuntu Java 21 runtime) but replaces the `git clone --depth 1 https://github.com/openmrs/openmrs-module-chartsearchai.git /build` with a `COPY` from `targets/chartsearchai/` (the harness's submodule checkout). The submodule SHA is the pin.

Frontend (`compose/chartsearchai/Dockerfile.frontend`) keeps the upstream `git clone --depth 1` for `openmrs-esm-chartsearchai` since we don't have it as a submodule. Acceptable drift on the frontend ESM for now; promote to a submodule if drift becomes a problem.

### D-003.3 — LLM engine config: env-driven, default remote, both supported

| Env var | Default | Purpose |
|---|---|---|
| `CHARTSEARCH_LLM_ENGINE` | `remote` | `remote` (OpenAI-compat) or `local` (bundled llama-server) |
| `CHARTSEARCH_REMOTE_ENDPOINT_URL` | `https://api.anthropic.com/v1/chat/completions` | OpenAI-compat endpoint |
| `CHARTSEARCH_REMOTE_MODEL_NAME` | `claude-haiku-4-5` | Model identifier |
| `CHARTSEARCH_REMOTE_API_KEY` | *(required for remote)* | Bearer token, injected into `openmrs-runtime.properties` at start |

The API-key injection is the trickiest piece — chartsearchai reads `chartsearchai.llm.remote.apikey` from runtime properties, NOT env vars, for security. A small `harness-init.sh` wrapper appends the key to `/openmrs/data/openmrs-runtime.properties` before exec'ing the upstream `backend-init.sh`. Runtime properties already exist on container start because the openmrs distro auto-generates them from `OMRS_CONFIG_*` env vars.

For `CHARTSEARCH_LLM_ENGINE=local`: backend-init.sh handles the Gemma GGUF + ONNX downloads; no remote key needed; we set the global property `chartsearchai.llm.engine=local` via the admin REST after startup (or via SQL preload on the DB seed step).

### D-003.4 — DB seed via init script

The chartsearchai compose mounts feature 002's dump file (e.g., `artifacts/<run>/transform/refapp_28_demo.sql.gz`) into `/docker-entrypoint-initdb.d/01-load-openmrs.sql.gz`. MariaDB's standard init mechanism auto-loads `*.sql.gz` on first boot. Note this only fires when the named volume is empty (first init); subsequent restarts re-use the seeded data.

The dump's first line is `USE openmrs;` (or we wrap with a small `.sh` script to ensure the right DB context). The dump also contains `mysql.openmrs` user/role rows from the original snapshot — we strip any superuser-grant statements at dump time and rely on MariaDB env-var-driven user creation.

### D-003.5 — Playwright in a dedicated workspace

`evals/playwright/` — new Node workspace with `@playwright/test`, its own `package.json` + `tsconfig.json`. Not part of the existing `site/` workspace (which is Vite/React canvas viewer with different deps). Test files end in `.smoke.spec.ts` for the first iteration; later eval-style tests would use `.eval.spec.ts`.

Tests target `http://localhost:${CHARTSEARCH_PROXY_HTTP_PORT:-8089}/openmrs/spa/login`. Browser: Chromium headless by default; flip to headed via `PWDEBUG=1`.

### D-003.6 — Granting "AI Query Patient Data" privilege

The seeded dump's `admin` user inherits role `System Developer` which has the `*` privilege (all) — so it already has `AI Query Patient Data` even though the privilege didn't exist when the dump was created (the chartsearchai module registers the privilege at install time, and `*` automatically covers it). If that turns out wrong in practice (need to verify), the alternative is a small SQL post-step that grants the privilege explicitly to a test role.

Verification step: post-boot, `curl -u admin:Admin123 .../ws/rest/v1/privilege?q=AI Query` should return the privilege; then check `role_privilege` for admin's role.

## Compose structure

```
compose/
├── openmrs-2.8-refapp.yml        (unchanged from 002)
├── openmrs-2.8-chartsearch.yml   (NEW)
├── Caddyfile                      (unchanged — base stack only)
└── chartsearchai/                 (NEW)
    ├── Dockerfile.backend
    ├── Dockerfile.frontend
    ├── spa-build-config.json     (copy of upstream)
    └── harness-init.sh
```

Service names in chartsearch compose are prefixed `chartsearch-` to avoid collisions with the base stack (`chartsearch-backend`, `chartsearch-frontend`, `chartsearch-gateway`, `chartsearch-db`). No shared `proxy` — the chartsearch gateway is its own nginx, exposed on host port directly.

## Playwright test outline

```
evals/playwright/
├── package.json
├── playwright.config.ts
├── .gitignore
├── tests/
│   └── chartsearchai.smoke.spec.ts
└── fixtures/
    └── demo-patient.json    # Zabella's UUID + name + expected order count
```

`chartsearchai.smoke.spec.ts` pseudo-flow:
1. `await page.goto('/openmrs/spa/login')`
2. `await page.fill('[name="username"]', 'admin'); await page.fill('[name="password"]', 'Admin123'); await page.click('button[type="submit"]')`
3. Wait for home, navigate to `/openmrs/spa/home`
4. Click magnifier; type "Zabella"; click the resolved patient
5. Wait for chart load; click the "Ask AI about this patient" sparkle (`role=button[name="Ask AI"]` or `data-testid="chartsearchai-launch"`)
6. Wait for chat panel; type the question; click Send
7. Assert `[role="article"]` (the answer bubble) becomes non-empty within 60s
8. Assert References section has ≥1 entry: `await expect(page.locator('[data-testid="chartsearchai-reference"]')).toHaveCount.gte(1)`

Real selectors will be discovered during 003.7. If the upstream ESM uses different test IDs, we capture them in `fixtures/demo-patient.json` or `tests/selectors.ts`.

## Risk register

- **R1 — Image build flakiness**: `mvn package` inside Dockerfile.backend takes ~3-5 min and is sensitive to Maven Central availability. Mitigation: pin `maven:3.9-eclipse-temurin-11` digest; commit a slim `.mvn/settings.xml` that prefers Maven Central directly. Not addressed in this PR; treat as known follow-up.
- **R2 — :nightly base drift**: Dockerfile.backend uses `openmrs/openmrs-reference-application-3-backend:nightly` as the base. Nightly is a moving target. Mitigation later: pin to a specific digest sha256. Out of scope for the first smoke.
- **R3 — `:nightly` Liquibase migrations vs 3.6.0 dump**: nightly may include schema migrations not yet in 3.6.0. Liquibase will run them on first boot against the seeded dump. Expected to succeed (it's the same OpenMRS Platform 2.8 line) but could surface compatibility issues. Mitigation: keep RefApp 3.6.0-backed `:nightly` close; switch to a tagged release if drift breaks things.
- **R4 — Apple Silicon emulation**: backend boot ~3-5 min cold under linux/amd64 emulation. Acceptable for dev/smoke; flag in README. Production deploy would target x86_64 hosts.
- **R5 — Remote LLM provider rate limits**: first smoke run + iteration may hit rate limits depending on provider. Mitigation: documented in `.env.chartsearch.example`; ensure smoke test has clear retry semantics.
- **R6 — `AI Query Patient Data` privilege**: assumed granted via `*` wildcard on admin's role from the dump. If not, post-boot SQL grants needed. Mitigation: 003.6 verifies as part of acceptance.

## Acceptance — 003 closes when

- `make chartsearch-up` boots; `make chartsearch-smoke` exits 0.
- `GET /ws/rest/v1/module` lists chartsearchai started.
- Playwright produces an HTML report at `evals/playwright/playwright-report/` confirming 1 passed test.
- Smoke test against Zabella Halambe returns a non-empty answer with ≥1 reference.
- Spec + plan + tasks updated with measured signals (timings, image sizes, screenshot of result).
- PR opened against main, GitGuardian green.

## Deferred (post-003)

- Local LLM smoke (Gemma 4 E4B GGUF, ~5GB) — wired but not in smoke matrix.
- chartsearchai indexing / embedding pipeline (`preFilter=true`) — out of scope for the smoke.
- querystore module bring-up — separate feature.
- Multi-question matrix + content assertions — incremental feature after the smoke greens out.
- chartsearchai eval harness in CI — upstream's concern.
