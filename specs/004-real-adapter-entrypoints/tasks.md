# Tasks: chartsearchai adapter PoC (004)

## Phase A — Cleanup + spec rewrite (preamble to this commit)

- [X] A.1 — Branch renamed `003-chartsearchai-bringup` → `004-chartsearchai-adapter`
- [X] A.2 — Spec dir renamed `specs/003-chartsearchai-bringup-smoke/` → `specs/004-real-adapter-entrypoints/`
- [X] A.3 — Deleted over-engineered files: `compose/chartsearchai/`, `compose/openmrs-2.8-chartsearch.yml`, `scripts/chartsearch-{up,down}.sh`
- [X] A.4 — spec.md, plan.md, tasks.md (this file) rewritten for PoC scope

## Phase B — Compose + scripts + Makefile

- [ ] B.1 — Add `OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY: ${CHARTSEARCH_REMOTE_API_KEY:-}` to backend `environment:` in `compose/openmrs-2.8-refapp.yml`
- [ ] B.2 — Write `.env.chartsearch.example` with LM Studio default + Anthropic/OpenAI commented examples
- [ ] B.3 — Write `scripts/chartsearch-configure.sh` (3 REST POSTs to set chartsearchai LLM globals)
- [ ] B.4 — Add Makefile targets: `chartsearch-build`, `chartsearch-configure`

## Phase C — Build + bringup + smoke

- [ ] C.1 — Run `make chartsearch-build` → produces `.omod` under `artifacts/openmrs/modules/`
- [ ] C.2 — Set `OPENMRS_REFAPP_TAG=nightly-chartsearch` and recreate `frontend gateway backend` containers
- [ ] C.3 — Verify backend health + `GET /ws/rest/v1/module/chartsearchai` reports `started: true`
- [ ] C.4 — Run `make chartsearch-configure` to set 3 LLM globals
- [ ] C.5 — Manual browser smoke: login → search Zabella → open chart → AI sparkle → ask question → verify streamed answer + ≥1 reference
- [ ] C.6 — Capture screenshot for the spec

## Phase D — Architecture canvas

- [ ] D.1 — Write `specs/artifacts/canvases/chartsearchai-and-querystore.canvas.tsx` per the outline in the approved plan
- [ ] D.2 — Update `specs/artifacts/README.md` to list the new canvas

## Phase E — Final + PR

- [ ] E.1 — Update spec.md with measured timings + observed chartsearchai version + screenshot inline reference
- [ ] E.2 — Commit + push
- [ ] E.3 — Open PR titled `feat(004): M3 PoC — chartsearchai (built from submodule) against the openmrs corpus + architecture canvas`

## Phase F — Multi-turn chat (added 2026-05-18)

Background + 13 design decisions in `spec.md` Phase 2; full execution narrative in `plan.md`. Tasks below mirror the MT.* tracking in the live task list.

- [x] F.1 (MT.1) — Cut multi-turn-chat work branch; scaffold Liquibase chartsearchai-007 + ChatSession/ChatMessage entities/hbm + ChatDAO
- [x] F.2 (MT.2) — `ChatMessages.fromTurns` + red-then-green test (later superseded by F.13)
- [x] F.3 (MT.3) — Service layer + REST `/chat` family + LlmEngine messages-array overloads
- [x] F.4 (MT.4) — Local backend smoke via curl (initial design — surfaced the chart-placement bug)
- [x] F.5 (MT.5) — Fork ESM repo; verify `yarn start --backend=http://localhost:8088` dev loop
- [x] F.6 (MT.6) — Frontend: store + hook + "New chat" button; rewrite `useChartSearchAi.test.ts`
- [x] F.7 (MT.7) — Harness submodule + Makefile + scripts + Caddyfile interception
- [x] F.8 (MT.8) — Local prod-shape Caddy smoke (importmap + bundle served, fall-through for other ESMs)
- [x] F.9 (MT.9) — Local end-to-end (originally failed in browser; reopened, fixed via F.13–F.17)
- [x] F.10 (MT.10) — Cloud deploy; rsync exit-23 FUP.1 fixed; cloud smoke
- [x] F.11 (MT.11) — Open upstream PRs: backend openmrs/openmrs-module-chartsearchai#20, ESM openmrs/openmrs-esm-chartsearchai#9
- [ ] F.12 (MT.12) — Bump submodule pins on harness PR #15; update specs + canvas (this commit)
- [x] F.13 (MT.13) — Restructure messages array: stable system+chart prefix, variable conversation tail
- [x] F.14 (MT.14) — Add `chart_snapshot` / `chart_mappings_json` / `chart_built_at` to chat_session (chartsearchai-008)
- [x] F.15 (MT.15) — Replace `chars/4` heuristic — DECISION: keep POC, file as v2 follow-up (D5)
- [x] F.16 (MT.16) — Disable pre-filter for chat mode (full-chart-per-session via `buildChartUnfiltered`)
- [x] F.17 (MT.17) — `MessagesArrayShapeTest` (7 cases, RED-then-GREEN verified)
- [x] F.18 (MT.18) — Backend curl smoke + LM Studio log inspection; browser visual verification pending user
- [x] F.19 (MT.19) — Switch cloud to `medgemma-1.5-4b-it` (LM Studio needed `--context-length 32768`)

## Phase G — Follow-ups (not blocking M3 close)

- [ ] G.1 — Title generation for `chat_session.title` (small-LLM summarize of first turn)
- [ ] G.2 — Summarization for context overflow (use the reserved `is_summary` column)
- [ ] G.3 — Branching / regenerate-answer UX (use the reserved `parent_message_id` column)
- [ ] G.4 — Cross-user thread sharing (new `chartsearchai_chat_session_acl` table)
- [ ] G.5 — Real tokenizer (jtokkit for OpenAI-compat / llama-server `/tokenize` for local)
- [ ] G.6 — Vercel `consumeStream` pattern for mid-stream client disconnect
- [ ] G.7 — Service-worker cache-buster on importmap interception (so hard-reload isn't required)
- [ ] G.8 — Patient merge / void rebinding for chat sessions (file as upstream issue)
- [ ] G.9 — Playwright multi-turn smoke (was v2.1, retains scope)
- [ ] G.10 — Model picker (scoped separately in `model-picker-scoping.md`)
