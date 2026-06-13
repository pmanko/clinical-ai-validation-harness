# Upstream Submodule Sync — 2026-06-13

Combined report for the Chart Search restore + upstream submodule sync. Covers the
two OpenMRS forks rebased onto their upstreams (`chartsearchai`, `chartsearchai-esm`),
the origin-tip bumps for the other targets, and the harness hub-hardening changes.

All work was done in the worktree `harness-wt-chartsearch` on branch
`fix/chartsearch-restore-and-submodule-sync`. Pre-sync tips are preserved as the
tag `backup/pre-sync-2026-06` in each fork's `origin`.

## Summary of pin changes

| Submodule | Old pin | New pin | Action |
|-----------|---------|---------|--------|
| `targets/chartsearchai` | `9af767e` | `b2cb57b` | Rebased `harness-integration` onto `upstream/main` (`8bda8f8`); force-pushed |
| `targets/chartsearchai-esm` | `37427f2` | `34c1949` | Rebased `harness-integration` onto `upstream/main` (`e2b6cd0`); force-pushed |
| `targets/querystore` | `ba1fa2c` | `4ba55f7` | Advanced to `origin/main` tip (+18, origin-only) |
| `targets/med-agent-hub` | `ebdbb43` | `ebdbb43` | Unchanged — already at `origin/main` tip |
| `targets/openmrs_chatbot` | `2e723f8` | `2e723f8` | Unchanged — already at `origin/main` tip |
| `targets/catalyst` | `3c1f1aa` | `3c1f1aa` | Unchanged — already at `origin/main` tip |

Both forks now sit **0 commits behind `upstream/main`** with our feature commits replayed on top.

---

## chartsearchai (Java module)

- **Strategy:** rebase `harness-integration` directly onto `upstream/main`.
- **Result:** 32 upstream commits absorbed; 26 of our commits replayed on top. `mvn -DskipTests -B package` + `mvn -pl api test` green. New pin `b2cb57b`.

### Upstream incoming (highlights of 32 commits, `2c1eb27..8bda8f8`)

The upstream work this cycle centered on **citation grounding**, **reasoning**, and **streaming**:

- **Reasoning field / "thinking" stream** — added a `reasoning` field to the LLM answer schema (`c1a27cb`), streamed as a `thinking` SSE event (`c9a9a2b`), with slice-hardening and a revert of the short-reasoning experiment (`46d07f1`).
- **Citation grounding** — grounding verification for answers (`d90a48b`), config-registered GPs (`452d954`), batched single-call grounding with citations streamed first (`f371619`), clause-scoped grounding (`cad6b83`), lazy Tier-1 (`26c5c26`), and **async grounding** that emits `done` before the Tier-2 tail with verdicts in a trailing `grounded` event (`46ce174`).
- **REST / auth** — authorization-failure status mapping (`021f9e0`), exception-handler tests; reindex-all endpoint added then reverted (`eca3fe1` / `301aa38`).
- **Standalone bundle** — multiple packaging/README changes (not used by the harness path).
- **Slash-citation fix** — `normalizeSlashCitations` no longer mangles slash-separated values (`24bfd51`).

### Conflicts resolved (25 hunks)

Our `harness-integration` carried **multi-turn chat history** and a **structured `blocks[]` table schema**; upstream added **reasoning + grounding + async streaming**. Resolutions merged both:

- **Querystore bridge** (`QueryStoreChartBuilder.java`, `api/pom.xml`) — adopted upstream's **typed `QueryStoreService`** API (`getPatientChart` / `searchByPatient`), dropping our reflective access.
- **LLM engine layer** (`LlmEngine`, `LlmProvider`, `LocalLlmEngine`, `RemoteLlmEngine`) — combined upstream's schema-selectable grounding (`ObjectNode responseFormat`) with our multi-turn `ArrayNode messages` request path.
- **Answer schema** (`ChartAnswerResponseFormat`, `LlmAnswerExtractor`) — reasoning-first schema with our `blocks[]` structured output; required fields = `reasoning, answer, citations, blocks`.
- **`ChartBuildingStrategy`** — removed the upstream-deleted in-memory `chartCache`; `buildChartUnfiltered` calls `chartSerializer.serialize(patient)` directly.
- **`liquibase.xml`** — kept our chat-session/message migration (`chartsearchai-007`) alongside upstream audit-log changesets.
- **Tests** — updated `LlmProviderTest`, `LocalLlmEngineTest`, `RemoteLlmEngineTest` to the merged 4-field schema.

### Implications

- The module now requires the **typed `querystore-api`** at build time (drove the querystore bump below).
- Default prompt/schema is **reasoning-first with structured `blocks[]`** — the validated-hub envelope the harness depends on is preserved.
- Async grounding means the UI must handle a trailing `grounded` event (mirrored in the ESM work below).

---

## chartsearchai-esm (frontend)

- **Strategy:** rebase `harness-integration` onto `upstream/main`.
- **Result:** 5 upstream commits absorbed; 24 of our feature commits replayed + 1 post-rebase integration commit (`34c1949`). `tsc` clean, `eslint --max-warnings 0` clean, `vitest` 181/181 green. New pin `34c1949`.

### Upstream incoming (5 commits, `e66b472..e2b6cd0`)

- `973d9fe` Render citation grounding verdicts in the panel
- `54de651` Render citations before grounding via the early-references SSE event
- `38de980` Use `resourceUuid` (not `resourceId`) for citation highlighting
- `4f2fa53` Apply trailing grounded-event verdicts (async grounding)
- `e2b6cd0` Show the model's live reasoning under the Thinking spinner

These align 1:1 with the Java side's reasoning + grounding + async-grounding work.

### Conflicts resolved

Our branch carried **multi-turn chat**, **structured table blocks**, a **per-endpoint model picker**, **per-request model override / refresh notice / per-response model tag**, and **per-section validator confidence chips**; upstream added SSE callbacks for thinking/early-references/grounding and the `resourceUuid` rename. Resolutions:

- **`useChartSearchAi.ts` / `.test.ts`** — merged upstream's `onThinking` / `onReferences` / `onGrounded` SSE callbacks with our session/history state; dropped the now-unused `useConfig` streaming gate; `ChatMessage` unions `reasoning` (live thinking) + `resolvedModel` + `kind: 'system'`.
- **`api/chartsearchai.ts`** — `chatPatientChartStream` gained the optional `onThinking` / `onReferences` / `onGrounded` callbacks.
- **`ai-chat-content.component.tsx`** — system-notice branch (refresh divider) + `resolvedModel` tag + live-reasoning indicator combined into one render.
- **`ai-response-panel.component.tsx` / `ai-markdown-answer.component.tsx`** — switched to markdown answer rendering (`MarkdownAnswer`) while keeping the references-list grounding badges; removed the now-dead local citation renderer/helpers (moved to `citation-chip.component`).
- **`citation-chip.component.tsx`** — made `CitationChip` **grounding-aware** (ungrounded warning affix + muted styling). Because `MarkdownAnswer` routes all inline citations (prose *and* table cells) through `renderTextWithCitations`, the upstream inline-grounding signal is now preserved everywhere — a net improvement over the pre-rebase behavior.
- **`model-picker.component.tsx` / `.test.tsx`** — purely-ours files (absent upstream); resolved by reproducing each replayed commit's snapshot, so the final tree equals the intended branch tip.

### Post-rebase integration commit (`34c1949`)

A single follow-up commit captures the cross-cutting "adapt to upstream" fixes that no single replayed commit owns:

- Tests updated for the upstream `resourceId -> resourceUuid` rename (string UUIDs).
- `reasoning: ''` on the in-thread system notice (merged `ChatMessage` requires it).
- `CitationChip` inline-grounding port (above).
- Prettier formatting.

### Unmerged upstream feature branches (informational)

`upstream/main` has 11 feature branches not merged to `main`. Several overlap features we already implemented independently; tracked here so future syncs don't double-implement:

| upstream branch | (+ vs main) | overlaps our work? |
|-----------------|-------------|--------------------|
| `feat/chat-history-ui` | +10 | yes — our multi-turn chat history |
| `grounding-badge` | +6 | yes — our grounding-aware citations |
| `feat/model-picker` | +5 | yes — our endpoint/model picker |
| `drug-reference-frontend` | +5 | no — new |
| `chore/migrate-to-vitest` | +3 | partial — we already run vitest |
| `feat/copy-ai-response` | +2 | yes — copy button present |
| `feat/workspace-chat-panel` | +2 | yes — chat panel |
| `early-references-sse` | +1 | merged to main this cycle |
| `fix/clear-chat-on-logout` | +1 | yes — store logout cleanup |
| `chore/chat-launch-mode-validator` | +1 | no — new |
| `simplify-ai-search-button` | +1 | no — new |

No action required now; revisit `drug-reference-frontend` and `chat-launch-mode-validator` if/when they land on `main`.

---

## querystore

- **Strategy:** advance the pin to `origin/main` tip (origin = `openmrs/openmrs-module-querystore`; origin-only, no fork). `ba1fa2c -> 4ba55f7` (+18 commits).
- **What's in the 18 commits:** querystore REST API (indexing-status, per-patient + global `/reindex`), `@Authorized` enforcement via an authorization proxy, drift detection (core vs index counts), bootstrap robustness (poison-page recovery, dump-orphaned-FK guards, batched writes), and docs/tests.
- **Compatibility with chartsearchai:** the two methods chartsearchai calls — `getPatientChart(String)` and `searchByPatient(String, String, int)` — are unchanged in signature. Both now carry `@Authorized(PrivilegeConstants.GET_PATIENTS)`; satisfied by the normal authenticated chart-search context (and the daemon context for warmup/indexing). Verified against `upstream/main`'s `QueryStoreService` interface.
- **Implication:** confirm chart search still resolves after the `.omod` rebuild (Phase 6); the only runtime delta is the `GET_PATIENTS` privilege check on read methods.

## med-agent-hub / openmrs_chatbot / catalyst

Already at their respective `origin/main` tips; no change this cycle.

---

## Harness hub hardening

Changes in the harness repo (this PR), making the canonical LLM path explicit and guarding the common failure modes seen during the restore:

- **`make llama-router-up` / `make llama-router-models`** — bring up the canonical llama.cpp Router Mode backend on `:8077` with the tier GGUFs (`LLAMA_ROUTER_TIER=low|med|high` -> models-max 4/4/1) and probe what it serves. Guards a missing `llama-server` binary.
- **`med-agent-hub-up` preflight** — hard-fails if `targets/med-agent-hub/server/levels.yaml` is missing (the read-only bind mount that, when absent, made the hub 500 on every request), and soft-warns when `:8077` is unreachable.
- **`.env.chartsearch.example`** — canonical path is now chartsearchai -> Med Agent Hub (`med-agent-team-med-validated`) -> llama-router (`:8077`); LM Studio (`:1234`) documented as a configurable alternative. Endpoint registry default exposes all three picker sections.
- **`README.md`** — ChartSearch operations section states the canonical path and adds the llama-router targets.

The running backend matches this canonical config (`chartsearchai.llm.remote.endpointUrl = http://med-agent-hub:8080/v1/chat/completions`, `modelName = med-agent-team-med-validated`).

---

## PCCP-style Change Record

### 1) Modification Description

- **Change id:** upstream-sync-2026-06-13
- **Date:** 2026-06-13
- **Owner:** harness maintainer (pmanko)
- **Component:** chartsearchai (Java + ESM forks), querystore pin, harness hub config
- **Why change is needed:** restore the broken Chart Search runtime (canonical llama-router path) and realign the OpenMRS forks with upstream so the harness validates against current production behavior (reasoning + citation grounding + async streaming), not a stale fork.
- **What changed:** both forks rebased onto `upstream/main` (grounding/reasoning/streaming merged with our multi-turn chat + structured blocks + picker + confidence chips); querystore advanced to its REST/auth/drift tip; harness Makefile/env/docs hardened to make llama-router canonical.

### 2) Modification Protocol

- **Preconditions:** worktree off `main`; submodules fetched (origin + upstream); pre-sync tips tagged `backup/pre-sync-2026-06` and pushed.
- **Validation plan:** per-fork build/test (chartsearchai `mvn package` + `mvn -pl api test`; esm `tsc` + `eslint` + `vitest`); harness `chartsearch-build` rebuild of the `.omod`, then `load-test` + `import-smoke` + `smoke`; chart-search smoke + UI Patient Summary with citations resolving (Phase 6).
- **Datasets used:** feature-002 transformed 5,284-patient corpus in the `openmrs` schema.
- **Expected risk controls:** force-push only after green build/test and `--force-with-lease` against the recorded pre-sync tip; backup tags allow exact rollback.
- **Rollback plan:** reset each fork's `harness-integration` to `backup/pre-sync-2026-06` and re-pin the submodule gitlinks to the old SHAs in the table above.

### 3) Impact Assessment

- **Retrieval impact:** querystore read methods now `@Authorized(GET_PATIENTS)`; typed bridge replaces reflective access. To be confirmed green by the Phase 6 chart-search smoke.
- **Answer/citation impact:** reasoning-first schema + async grounding; inline citations are grounding-aware in prose and tables; per-section confidence chips retained.
- **Safety impact:** grounding verdicts surfaced inline and in the references list (ungrounded marked, never shown as verified); advisory framing unchanged.
- **Clinician review outcome:** N/A (infrastructure/sync change).
- **Residual risk:** intermediate rebased commits in the ESM history are not each independently green (cross-cutting fixups land in `34c1949`); final tree is fully validated. Upstream feature branches not yet on `main` may need a follow-up sync.
- **Decision:** proceed to Phase 6 validation, then merge the single harness PR.
