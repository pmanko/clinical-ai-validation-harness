# Plan: chartsearchai adapter PoC (feature 004)

**Branch**: `004-chartsearchai-adapter`, cut from `main` after PR #10 (feature 002) merged.
**Source of truth**: see also the approved plan file at `~/.claude/plans/streamed-watching-stream.md` from the planning session.

## Architectural decisions

### D1 — Use chartsearchai upstream patterns; minimize harness wrappers

Upstream chartsearchai's install path (per its README's non-Docker section) is: build `.omod` via `mvn package`, drop into `<openmrs-data-directory>/modules/`, configure global properties, restart. The harness already has the modules directory (`artifacts/openmrs/modules/`) mounted into the existing 3.6.0 backend. So the install path is literally upstream's install path with `artifacts/openmrs/modules/` as the target dir.

No Dockerfile variants. No separate compose stack. No Maven build inside Docker.

### D2 — Pin via where `mvn package` runs (not via Dockerfile)

`targets/chartsearchai/` is our submodule. `make chartsearch-build` runs `mvn -DskipTests package` from that directory. The resulting `.omod` carries our submodule SHA's code. That IS the pin — nothing more is needed to honor "build from the submodule."

If we later wanted to build the `.omod` inside Docker (e.g., for reproducible CI builds), we'd need a Dockerfile variant. Not in this PR.

### D3 — Remote LLM engine only (LM Studio / Anthropic / OpenAI / etc.)

`chartsearchai.llm.engine=remote` is the only mode wired in the PoC. Default endpoint in `.env.chartsearch.example` is LM Studio at `http://host.docker.internal:1234/v1/chat/completions`. The bundled `llama-server` (local engine) is never invoked, sidestepping its glibc/libgomp OS coupling.

*Aside*: chartsearchai's bundled local engine has an OS coupling (needs glibc 2.39+ via libgomp) that the upstream Dockerfile.backend "fixes" by rebasing to Ubuntu. The actual fix should be static-linking libgomp or dropping OpenMP. Out of scope for our PoC; file upstream issue if we ever need the local engine.

### D4 — Frontend + gateway: swap published image tag; backend stays at 3.6.0

The chartsearch UI (AI sparkle, chat panel, citations panel) is in the frontend ESM `@openmrs/esm-chartsearchai-app`. Stock RefApp 3.6.0 frontend doesn't include it. The published `openmrs/openmrs-reference-application-3-frontend:nightly-chartsearch` image is the standard RefApp frontend SPA with that ESM baked in.

Our existing compose already supports `OPENMRS_REFAPP_TAG` env var → set to `nightly-chartsearch` and the gateway + frontend pull the chartsearch-flavored images. Backend stays at `:3.6.0` — the chartsearchai `.omod` runs there fine for remote LLM.

Trade: `:nightly-chartsearch` floats. Acceptable for PoC; digest-pin in v2.

### D5 — API key via `OMRS_EXTRA_*` env var; other globals via REST

chartsearchai reads `chartsearchai.llm.remote.apikey` from `openmrs-runtime.properties` (NOT a DB global property) for security. OpenMRS's standard `OMRS_EXTRA_*` env-var mechanism auto-translates `OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY=...` into a `chartsearchai.llm.remote.apikey=...` line in runtime properties at startup.

The other 3 LLM properties (`engine`, `remote.endpointUrl`, `remote.modelName`) are DB-backed global properties. Configure via REST POST after backend health.

### D6 — Querystore is a build-time dep, runtime-deferred to M8 — CORRECTED from earlier draft

**Earlier (wrong) claim**: "Today's chartsearchai works standalone with its own retrieval; no querystore involvement." That was based on our stale submodule SHA `e490782` (2026-05-13), which pre-dates upstream's querystore integration.

**Measured reality** (after `git submodule update --remote targets/chartsearchai` → SHA `ab37133`, 2026-05-16):
- Commit `0215d81` (May 15): chartsearchai added querystore-api as a Maven dep (`scope=provided`) + a `chartsearchai.querystore.enabled` global property to route retrieval through `QueryStoreService`.
- Commits `c091f98` + `0ca730e` + `ab37133` (May 16): chartsearchai integration polish — declares querystore as aware_of_module, registers querystore migration globals in `config.xml`, strips stopwords from querystore queries.
- Default at runtime: `chartsearchai.querystore.enabled=false` — chartsearchai uses its OWN retrieval, querystore is not contacted.
- Graceful degradation: per the commit message of `0215d81`, "chartsearchai still starts if the omod isn't installed (APIException + LinkageError both degrade to an empty chart)."

**Implication for this PoC**:
- **Build**: chartsearchai requires querystore-api on the local Maven classpath. The harness's `make chartsearch-build` target installs `querystore-api:1.0.0-SNAPSHOT` from our `targets/querystore/` submodule first, then builds chartsearchai.
- **Runtime**: querystore is NOT deployed in the running stack. Only chartsearchai's `.omod` is installed. `chartsearchai.querystore.enabled` stays at its default (false). chartsearchai uses its in-process retrieval, the same way it always has.
- Future M8 (`009-querystore-parity-testbed`): we'd flip `chartsearchai.querystore.enabled=true` and deploy the querystore .omod. That requires querystore to reach alpha-usable state (5 critical runtime bugs blocking).

## Querystore situation (measured 2026-05-16)

| Upstream | HEAD | Status |
|---|---|---|
| `openmrs/openmrs-module-chartsearchai` | `e490782` (2026-05-13) | mature; 12 merged PRs; active dev |
| `openmrs/openmrs-module-querystore` | `ab37133` (2026-05-16) | pre-alpha; 1 merged PR (scaffold); single-author hot iteration |

**Querystore open runtime bugs** (any blocks startup):
- #9 `MysqlBackendStore` no `dataSource` bean — MySQL tier won't start
- #10 `BackendStoreSelector` Spring init deadlock — module init hangs
- #11 schema manager picks up `querystore_bootstrap_progress` → BM25/kNN fail
- #12 `BootstrapService` not registered with `ServiceContext` — every cold-patient search fails
- #13 Lucene tier collides with core Hibernate Search Lucene 8.7 codec

**Querystore open enhancement gaps** (#2-#6): whole-patient document listing, patient merge handling, index-change events, on-demand bootstrap, service-layer filters.

**Migration blockers** (per `targets/querystore/docs/migration-chartsearchai.md`): 4 ADR open questions (patient merge, initial backfill, long-text chunking, sync reliability + reconciliation) PLUS the 5 runtime bugs above. None of the port-map items in `targets/querystore/docs/chartsearchai-port-map.md` have landed (8 serializers + embedding provider + tokenizer + indexer + RRF + ES query DSL all still in chartsearchai).

**Chartsearchai-side integration progress** (post-2026-05-15, measured from submodule HEAD `ab37133`):
- `chartsearchai.querystore.enabled` global property added (default false)
- `QueryStoreChartBuilder` added to call `QueryStoreService.searchByPatient(uuid, query, topK)` when flag is on
- AOP indexing advice + `EmbeddingIndexTask` become no-ops when querystore is enabled (to avoid double indexing)
- querystore-api added as `<scope>provided</scope>` Maven dep — required at build time, not at runtime

So the chartsearchai side of the migration has its scaffolding in place (off by default). The querystore side has 5 runtime bugs that block actually flipping the switch.

**Implication**: PoC validates today's chartsearchai (querystore-disabled). When we want querystore-backed retrieval (future M8), the chartsearchai side is ready to flip; the work is on the querystore side.

## Files

### Add
| File | Lines | Role |
|---|---|---|
| `.env.chartsearch.example` | ~30 | Operator template — LLM endpoint, model, API key |
| `scripts/chartsearch-configure.sh` | ~30 | 3 REST POSTs for LLM global properties |
| `specs/artifacts/canvases/chartsearchai-and-querystore.canvas.tsx` | ~500 | Architecture canvas |
| `specs/004-real-adapter-entrypoints/{spec,plan,tasks}.md` | (this dir) | Spec docs |

### Modify
| File | Change |
|---|---|
| `compose/openmrs-2.8-refapp.yml` | Add `OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY: ${CHARTSEARCH_REMOTE_API_KEY:-}` under backend `environment:` (1 line) |
| `Makefile` | Add `chartsearch-build` (mvn + cp), `chartsearch-configure` (delegates to script) targets |
| `.gitignore` | Add `!.env.*.example` exception (carried forward from earlier branch work) |

### Delete (over-engineered from earlier iterations on this branch — already done in preamble)
`compose/chartsearchai/`, `compose/openmrs-2.8-chartsearch.yml`, `scripts/chartsearch-up.sh`, `scripts/chartsearch-down.sh`.

## Sequencing

1. Branch + spec-dir rename, delete over-engineered files (done)
2. Spec/plan/tasks rewrite (this commit)
3. Compose env-var addition + Makefile + .env.example + configure script (next commit)
4. `make chartsearch-build` produces `.omod` (`.omod` itself stays in `artifacts/**` which is gitignored)
5. Restart frontend + gateway + backend; configure LLM globals; verify in browser
6. Write the architecture canvas
7. Final spec update with measured signals + screenshot
8. PR

## Risks

- **R1 — `:nightly-chartsearch` image drift**: pinned by tag, floats. Mitigation: record SHA at PoC time; digest-pin as v2 follow-up.
- **R2 — admin lacks `AI Query Patient Data` privilege**: chartsearchai module activator registers it on first install; admin's `*` role wildcard covers it. Verify post-boot; single REST grant if not.
- **R3 — `:nightly-chartsearch` frontend ESM expects backend REST API newer than `:3.6.0`**: possible compat mismatch. Mitigation: if breakage surfaces, swap backend to `:nightly-chartsearch` too.
- **R4 — LM Studio not reachable**: `host.docker.internal` resolves to host on Docker Desktop (Mac/Win); Linux native may need `--add-host=host.docker.internal:host-gateway`. Document.
- **R5 — chartsearchai PR #17 UUID migration (2026-05-14)**: resource identifiers migrated Integer → UUID. May affect dumps produced before that date. Verify in PoC; if conflicts, rebuild dump or pin chartsearchai to a pre-#17 SHA.
- **R6 — Fork-branch drift vs upstream**: `targets/chartsearchai` and `targets/chartsearchai-esm` both pin to `pmanko/*` fork `harness-integration` branches. Drift measured 2026-05-28: chartsearchai 5 ahead / 35 behind upstream `openmrs/main`; chartsearchai-esm similar. Two open upstream PRs (#18 HTTP/1.1 pin, #19 querystore reflection) carry the ahead-commits. Mitigation: see Maintenance section below.

## Maintenance — fork branch rebase cadence

Both `targets/chartsearchai` and `targets/chartsearchai-esm` pin to fork branches we maintain. Without an explicit cadence, fork drift compounds — every upstream merge widens the diff we'd need to rebase.

**Cadence**: monthly checkpoint. On the first business day of each month:

1. For each submodule (`chartsearchai`, `chartsearchai-esm`):
   - Fetch upstream `origin/main`
   - Rebase `fork/harness-integration` on upstream main
   - Drop any commits that landed upstream in the interim (e.g. when upstream PR #18/#19/#20 merges, drop the corresponding fork commits)
   - Force-push `fork/harness-integration`
2. Bump the harness `targets/<submodule>` SHA in a maintenance commit on the next active feature branch (or directly on main if no active feature branch)
3. Run the existing smoke tests (Playwright + `make chartsearch-up` browser pass) before pushing
4. Update the "measured as of" date in `specs/artifacts/canvases/chartsearchai-and-querystore.canvas.tsx`

**Cost**: ~30 minutes per submodule per month when upstream is calm; up to ~2 hours when upstream merges touch files we've also modified.

**When to deviate from monthly**:
- Skip the month if drift is <5 commits behind (cheap to defer)
- Bump immediately when an upstream-merged change unblocks a harness feature (e.g. if upstream merges a `/v1/models` schema change we depend on)

**Owner**: harness maintainer. Failure mode if neglected: rebase becomes >1 day of work; harness-integration branch becomes "dead" (operators avoid bumping submodule SHAs because the rebase is scary). Avoid this by enforcing the monthly checkpoint even when no upstream changes touch our files.

## Acceptance — PoC closes when

1. `make chartsearch-build` succeeds and lands a `.omod` under `artifacts/openmrs/modules/`
2. `GET /ws/rest/v1/module/chartsearchai` reports `started: true`
3. `make chartsearch-configure` succeeds; the 3 LLM globals are set; apikey is in runtime properties
4. Browser flow against Zabella returns a streamed answer with ≥1 reference
5. Architecture canvas shipped
6. Spec/plan/tasks updated with measured signals (timings, observed module version, screenshot)
7. PR opens against `main`, GitGuardian green

---

# Phase 2 plan — Multi-turn chat (added 2026-05-18)

Background and 13 design decisions in `spec.md` Phase 2 section. This is the execution plan.

## Sequencing actually followed

1. Discovery — read backend Java code paths, frontend ESM source, primary docs (Anthropic / OpenAI / llama.cpp prompt-caching). Identified the chart-in-current-user shape as cache-hostile.
2. **First attempt (rejected)** — simple `ChatMessages.fromTurns` with chart still in current user, budget trim around it. Symptom: LM Studio still saw `"conversation with 2 messages"` on every turn. The budget trim dropped every prior because chart-alone exceeded the budget. Root cause: chart placement, not budget arithmetic.
3. Research dive — 8 numbered design questions answered against primary sources (saved as `streamed-watching-stream-agent-*.md`). Conclusion: chart MUST live in a stable prefix; D2 (freeze per session) follows directly.
4. 13-question Q&A pass with the user to lock decisions (D1–D13).
5. Implementation in order:
   - `ChartBuildingStrategy.buildChartUnfiltered` sibling method (advisor pre-check: smaller diff than adding a conditional)
   - Liquibase `chartsearchai-008` adds `chart_snapshot` / `chart_mappings_json` / `chart_built_at`
   - `ChatSession` entity + hbm.xml extended
   - `ChatMessages.assembleChat` — new builder; old `fromTurns` deleted as dead code
   - `LlmProvider.chat` / `chatStreaming` switch to `assembleChat`
   - `LlmInferenceService.chat` / `chatStreaming` signatures take chart envelope + mappings
   - `ChatServiceImpl` builds + persists snapshot on session create; deserializes mappings on every chat
   - `MessagesArrayShapeTest` (7 cases) — RED verified by stubbing `assembleChat` to single-shot, 7/7 fail including the byte-identity test
6. Local curl smoke — turn 3 referential test passes (LLM correctly recalls "11 medications" from turn 1)
7. Cloud deploy via `make cloud-deploy` (FUP.1 rsync fix held)
8. Cloud curl smoke — same pass
9. Slice-branch the work into clean upstream PRs (squash dd28cf6+9e56b3a+1374669 into one commit)
10. Open backend PR #20 + ESM PR #9 (both against `main` of openmrs/openmrs-*)
11. Switch cloud to medgemma — required reloading medgemma in LM Studio with `--context-length 32768`
12. Spec/plan/tasks/canvas updates (this commit)

## Risks specific to Phase 2

- **R6 — Chart freshness mid-session**: see spec trade-off. Clinician must click "New chat" to refresh.
- **R7 — Switching models invalidates cache**: GP change → next call hits with new model → first call after switch pays full prompt cost. Acceptable but worth knowing.
- **R8 — Service-worker caches the baked importmap**: addressed by hard-reload on first browser visit. Cache-buster query string could be added in v2.
- **R9 — Importmap drift across `:nightly-chartsearch` rebuilds**: our custom importmap is regenerated from the running container's baked importmap each deploy, so unrelated module versions stay in sync.
- **R10 — Trim path uses `chars/4`**: vestigial under the new design (chart lives in reserved prefix, conversation tail is small). Accurate tokenizer is a v2 follow-up.

## Acceptance — Phase 2 closes when

1. `MessagesArrayShapeTest` green (7/7); RED verified by stubbing
2. Backend smoke: turn 3 referential test passes both local + cloud (turn-1's "11 medications" recalled correctly)
3. `chart_chars` byte-stable in backend logs across all turns of one session
4. ESM build clean; 118/118 frontend tests green
5. Caddy interception verified: importmap + chartsearchai bundle served from `/srv/spa-custom`, other ESMs flow through
6. Upstream PRs opened: backend #20, ESM #9
7. Harness PR #15 bumps both submodule pins
8. Specs + canvas extended (this commit)
9. Browser visual pass: user verifies multi-turn UX end-to-end
