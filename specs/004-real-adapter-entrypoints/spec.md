# Feature 004: Real Adapter Entrypoints — chartsearchai PoC

**Roadmap slot**: M3 (`004-real-adapter-entrypoints`) per `specs/roadmap.canvas.tsx`
**Scope of this PR**: chartsearchai adapter only — proof of concept against the feature-002 corpus (now promoted to `openmrs`; see 2026-05-29 update)
**Status**: in progress | **Started**: 2026-05-16

## Goal

Drop the chartsearchai OpenMRS module (built from our `targets/chartsearchai/` submodule) into the existing harness backend, swap the harness frontend + gateway to the chartsearch-flavored images, point chartsearchai at LM Studio (or any OpenAI-compat endpoint) for remote LLM inference, and verify in a browser that a clinician question against a real demo patient (Zabella Halambe, 303 obs / 39 orders from feature 002) returns a grounded answer with citations.

This is M3 scoped to the chartsearchai adapter. The other M3 adapter targets (querystore, openmrs_chatbot, Catalyst) are explicit deferrals. See `plan.md` for the measured querystore situation justifying why it's not part of this PR.

## Success criteria

- **SC-004.1**: `make chartsearch-build` produces a `.omod` from our submodule SHA and drops it under `artifacts/openmrs/modules/`.
- **SC-004.2**: After restart with `OPENMRS_REFAPP_TAG=nightly-chartsearch` on frontend + gateway (backend stays on `:3.6.0`), `GET /ws/rest/v1/module/chartsearchai` reports `started: true`.
- **SC-004.3**: `make chartsearch-configure` sets the 3 chartsearchai LLM global properties (`engine`, `remote.endpointUrl`, `remote.modelName`) via REST; backend env carries `OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY` so the API key lands in `openmrs-runtime.properties`.
- **SC-004.4**: Browser flow against Zabella Halambe (uuid `dd75c020-1691-11df-97a5-7038c432aabf`) returns a streamed answer with at least one numbered citation when asked "What medications is this patient on?".
- **SC-004.5**: New architecture canvas at `specs/artifacts/canvases/chartsearchai-and-querystore.canvas.tsx` captures today's architecture, future querystore-backed architecture, port map, measured upstream status, and harness integration points.

## Functional requirements

- **FR-004.1**: The chartsearchai `.omod` MUST be built from the harness's `targets/chartsearchai/` submodule via `mvn -DskipTests package`. The submodule SHA is the pin.
- **FR-004.2**: The PoC MUST use chartsearchai's **remote** LLM engine (OpenAI-compatible). The bundled local llama-server is out of scope.
- **FR-004.3**: The harness MUST minimize customization vs upstream: no Dockerfile variants, no separate compose stack, no Maven build inside Docker. Only an env-var addition to the existing compose, an env-file template, a Makefile target wrapping `mvn package + cp`, and a small `chartsearch-configure.sh` wrapping 3 REST POSTs.
- **FR-004.4**: The PoC MUST NOT deploy querystore at runtime. (Correction from earlier draft: recent chartsearchai *does* declare a build-time dep on `querystore-api` with `scope=provided`. We install querystore-api locally from our submodule so chartsearchai builds; at runtime `chartsearchai.querystore.enabled=false` keeps chartsearchai on its in-process retrieval. Deploying querystore is M8 (`009-querystore-parity-testbed`) and is blocked by querystore's 5 open critical runtime bugs.)
- **FR-004.5**: The architecture canvas MUST capture both the current standalone-chartsearchai shape and the future querystore-backed shape, with the migration gap and open-bug count from upstream so future planning has measured context.

## Demo patient anchor

| Field | Value |
|---|---|
| `patient_id` | 2429 |
| `uuid` | `dd75c020-1691-11df-97a5-7038c432aabf` |
| Given name | Zabella |
| Family name | Halambe |
| Gender | F |
| Birthdate | 1978-10-08 |
| Obs count | 303 |
| Encounter count | 11 |
| Order count | 39 |
| Condition count | 0 |
| Allergy count | 0 |

Richest chart in `openmrs`. Anchors the smoke on a known-populated medication history (39 orders).

**Smoke question**: *"What medications is this patient on?"*

**Assertions** (manual): (a) streamed answer text non-empty within ~60s, (b) References panel renders with ≥1 numbered citation, (c) citation links resolve to a chart tab.

NOT asserted: specific drug names. Brittle vs LLM phrasing; smoke is about wiring.

## Out of scope

- Local LLM engine (bundled `llama-server` + GGUF model) — `chartsearchai.llm.engine=remote` only
- Playwright automation — v2 follow-up
- chartsearchai's embedding/Lucene/hybrid/elasticsearch retrieval pipelines — default `preFilter=false` (full-chart mode) is the simplest path
- querystore module bringup — pre-alpha upstream, blocked by 5 critical runtime bugs + 4 open ADR questions (see `plan.md`)
- openmrs_chatbot + Catalyst adapters — future M3 iterations
- Digest-pinning the `:nightly-chartsearch` published image — v2 follow-up

## Non-functional notes

- **`:nightly-chartsearch` floats**: published image rebuilt nightly from upstream main. Acceptable for PoC; pin to digest in v2.
- **Backend image**: the original PoC ran on stock `:3.6.0` (Amazon Linux 2), valid while remote-engine mode never invoked the bundled `llama-server`. The harness now rebases that dist onto temurin (`compose/Dockerfile.backend`) — required once querystore was enabled, because its onnxruntime embedder needs glibc ≥ 2.27 and AL2 ships 2.26. See the 2026-05-29 update.
- **LM Studio**: default endpoint URL in `.env.chartsearch.example` is `http://host.docker.internal:1234/v1/chat/completions`. Anthropic/OpenAI shown as commented alternatives.

---

# Phase 2 — Multi-turn chat history continuity (added 2026-05-18)

The PoC shipped above demos a single-shot AI sparkle: ask a question, get an answer. Every question is independent at the LLM layer. Phase 2 adds **multi-turn chat continuity** so referential follow-ups ("and her allergies?", "what would you do?") resolve against prior turns.

## Problem

The original `/chartsearchai/search` endpoint built `[system, user(chart+question)]` on every call. The chat panel UI displayed a history list, but each submit hit the single-shot endpoint independently — the LLM never saw prior turns. Symptom: open Zabella's chart, ask "what meds is she on?", then "and her allergies?" — the LLM responded with a generic chart dump because "her" couldn't resolve.

## Root-cause analysis (LM Studio debug logs)

LM Studio's request body shows every call arriving as `"messages": [{role: system, ...}, {role: user, "Patient records... Clinician's query: ..."}]` — two messages. No prior assistant turns. The chart sits in the **variable tail** of the prompt, so even with a multi-turn array the cache hash changes every turn AND the chart bytes would be duplicated across user turns. The original design that landed both ends of the prefix wrong is documented in the deleted `ChatMessages.fromTurns` history.

## Design (primary-source convergence)

Anthropic, OpenAI, and llama.cpp prompt-caching docs all say the same thing: **static content at the top of the prompt, variable content at the end.** Patient chart is the large per-session static block — it belongs in a stable prefix, not the variable tail.

```
[ system,
  user(chart envelope — frozen on session create),
  ...prior user/assistant pairs (no chart in any of them)...,
  user(current question) ]
```

The first two messages are byte-identical across every turn of a session. `llama-server`'s `cache_prompt=true` hits this prefix on follow-ups — only the new question + response need fresh prompt-processing.

## 13 locked decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Chart placement | First user message, byte-stable |
| D2 | Chart freshness | Frozen on session open; "New chat" refreshes |
| D3 | Pre-filter in chat | Always full chart (chat bypasses `chartsearchai.embedding.preFilter`) |
| D4 | Chart persistence | Snapshot on `chat_session.chart_snapshot` + `chart_mappings_json` |
| D5 | Tokenizer | Keep `chars/4` with bumped budget (POC; trim rarely fires) |
| D6 | `/search` vs `/chat` | Keep both; AI panel uses `/chat` only |
| D7 | Stream disconnect | Status quo (persist partial w/ `finish_reason='aborted'`) |
| D8 | Chat retention | 90 days (clinical-utility, separate from audit log's 6yr) |
| D9 | System prompt stability | Live GP, accept cache-invalidation on edit |
| D11 | Session uuid persistence | Server-side via `openOrLoadActiveSession`; no localStorage |
| D12 | Session boundary | Per (patient, user) |
| D13 | Sequencing | Ship redesign + browser-verify before opening upstream PRs |

D10 ("New chat" UI placement) was settled by implementation: floating-panel header icon + workspace-mode toolbar with icon+label.

## Schema (two Liquibase changesets)

- `chartsearchai-007`: `chartsearchai_chat_session` (header) + `chartsearchai_chat_message` (turns with `ordinal`, `parent_message_id` reserved for branching, `is_summary` reserved for summarization, `audit_log_id` FK back to existing `chartsearchai_audit_log`).
- `chartsearchai-008`: `chart_snapshot MEDIUMTEXT`, `chart_mappings_json MEDIUMTEXT`, `chart_built_at DATETIME` columns on `chat_session`. Kept as a separate changeset so already-deployed instances run a clean upgrade.

## REST surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/ws/rest/v1/chartsearchai/chat` | Single-call, returns `{answer, references, session, messageId}` |
| POST | `/ws/rest/v1/chartsearchai/chat/stream` | SSE; surfaces session uuid via `X-ChartSearchAi-Session` header |
| POST | `/ws/rest/v1/chartsearchai/chat/new` | Close current + open fresh session |
| GET  | `/ws/rest/v1/chartsearchai/chat?patient=` | Hydrate the SPA panel on mount |

## Three-repo paired-PR strategy

| Repo | Upstream PR | Status |
|---|---|---|
| `openmrs/openmrs-module-chartsearchai` | #20 — multi-turn chat with frozen-session chart in stable prefix | Open from `pmanko:multi-turn-chat` |
| `openmrs/openmrs-esm-chartsearchai` | #9 — multi-turn chat history continuity | Open from `pmanko:multi-turn-chat` |
| `pmanko/clinical-ai-validation-harness` (this) | #15 — paired submodule pin bumps + Caddy interception | Open from `004-chartsearchai-adapter` |

All three opened from clean slice branches; the consolidated fork branches (`harness-integration`) keep both the multi-turn slice and the earlier already-PR'd commits (chartsearchai #18 HTTP/1.1 pin, #19 querystore reflection) so the harness submodule pin tracks one consolidated ref instead of N branches.

## Verification (Zabella, gemma-4-e2b-it via LM Studio, both local + cloud)

| Turn | Question | Answer | Backend log |
|---|---|---|---|
| 1 | "What medications is this patient on?" | 11-medication list | `priors=0, included=0, chart_chars=26491` |
| 2 | "And what about her allergies?" | "Allergy to spiders [57]" | `priors=2, included=2, chart_chars=26491` |
| 3 | "How many medications did you list?" | **"11 medications were listed."** | `priors=4, included=4, chart_chars=26491` |

Turn 3 is the load-bearing proof: the number "11" comes only from turn 1's assistant message — not derivable from the chart alone. `chart_chars=26491` byte-stable across all turns confirms prefix-cache eligibility.

Switched cloud to `medgemma-1.5-4b-it` after baseline verification (D6 pre-condition: model is GP-driven, no backend restart needed). Required reloading medgemma in LM Studio with `--context-length 32768` because LM Studio defaults to 4K context and a real patient chart is ~11K tokens.

## Trade-off (documented in code)

Chat sessions don't pick up new lab results mid-session — the chart snapshot is frozen until "New chat" rebuilds it. Deliberate cost of cache-eligibility; matches the user-facing model ("opening a new chat = a fresh context view").

## Out of scope for Phase 2

- Title generation (`chat_session.title` reserved; LLM-summarize first turn later)
- Summarization for context overflow (`is_summary` column reserved)
- Branching / regenerate-answer UX (`parent_message_id` reserved)
- Cross-user thread sharing (would add a session ACL table later; today's `user_id` scope suffices)
- Real tokenizer (jtokkit / llama-server `/tokenize`) — POC keeps `chars/4`
- Vercel `consumeStream` pattern for mid-stream disconnect — POC keeps status quo
- Picker for live model-switch (scoped in `model-picker-scoping.md`)

---

# Update — querystore enabled + backend rebased (2026-05-29)

The PoC above deliberately ran chartsearchai standalone (`querystore.enabled=false`) on the stock Amazon Linux 2 backend. That posture has changed; this update governs where it conflicts with the original text — specifically **FR-004.4**'s querystore deferral, the **"5 critical runtime bugs"** framing (FR-004.4, out-of-scope list), and the original "glibc is moot" note.

- **DB schema**: `openmrs` is canonical — the full 5,284-patient corpus (feature 002's transform, promoted). The iteration/staging schemas (`openmrs_test`, `openmrs_*_dlt`, `*_staging`) are dropped; the backend connects to `openmrs` only.
- **querystore: ON and serving.** `chartsearchai.querystore.enabled=true`. The earlier "5 critical runtime bugs block any backend tier from starting" assessment was stale (fixed/unreproducible upstream). querystore starts clean, lazily indexes a patient on first access (`BootstrapService.ensureIndexed`), and serves kNN-retrieved charts — verified end-to-end against Zabella (real medications + 15 citations from a populated `querystore_drug_order` Lucene index).
- **Backend rebased to temurin.** querystore bundles onnxruntime 1.24.3, whose native lib needs glibc ≥ 2.27; the RefApp backend is Amazon Linux 2 (glibc 2.26), so the embedder died at load with `GLIBC_2.27 not found`. `compose/Dockerfile.backend` copies the stock `:3.6.0` dist onto `eclipse-temurin:21-jre` (glibc 2.39) and bakes **no** module, so the bind-mounted omods stay authoritative. Same rebase chartsearchai's own `Dockerfile.backend` uses; the "glibc is moot" note held only while querystore was off.
- **Chat LLM remote; embedded LLM off.** `chartsearchai.llm.engine=remote` (LM Studio). The bundled local engine stays off in local and cloud; its GP toggle is sufficient and the model picker stays at **F008 Phase 0** (no gating work) — consistent with the roadmap's "wait for F005 cloud-smoke green before F008 implementation."
- **Applies to local + cloud** (`openclinai.org`): the target running state is identical in both.

---

# Update — querystore backend tiers + reproducible cloud (2026-05-29)

querystore's storage backend is pluggable (querystore ADR Decision 3):
`querystore.backend=mysql|lucene|elasticsearch` — three reference tiers for three
deployment scales. A validation harness exists to exercise the *real* ones, so it
now runs all three, with **Elasticsearch** as the headline: the real CQRS read
store, a separate service *off* the clinical MariaDB (native HNSW + RRF). The
earlier update's "lucene" wording is just one tier; the canonical default is now
explicit below.

- **Backend tiers.** `mysql` (module default; vectors live in core's DB — the
  convenient case, but the read store is still *inside* the clinical OLTP DB, so
  not real CQRS separation), `lucene` (on-disk FSDirectory; better BM25), and
  `elasticsearch` (separate cluster — the production/scale path). For
  patient-scoped chart search all three serve identically; the cross-patient kNN
  O(N) limit of mysql/lucene doesn't bite us. All three validated end-to-end
  against Zabella (real meds + `drug_order` citations).
- **Elasticsearch service.** `compose/openmrs-2.8-refapp.yml` gains an
  `elasticsearch` service (ES 8.13.4, matching querystore's client) behind an
  `elasticsearch` compose profile. The backend reaches it via
  `querystore.elasticsearch.uri` (runtime property, wired by
  `OMRS_EXTRA_QUERYSTORE_ELASTICSEARCH_URI`). `querystore.backend` is wired at
  module startup, so switching tiers = set the GP + (re)start the backend.
- **`make chartsearch-backend BACKEND=mysql|lucene|elasticsearch`** flips the
  tier locally in one command (set GP → start ES if needed → recreate → configure).
- **Single-step deploy via `backend-init.sh`.** The temurin image
  (`compose/Dockerfile.backend`) now uses chartsearchai's own `backend-init.sh`
  entrypoint: it heals the data-volume ownership, downloads the all-MiniLM ONNX
  embedding model + vocab if absent (read by both querystore and chartsearchai),
  then drops to uid 1001. `chartsearch-configure` sets the querystore embedding
  GPs alongside the LLM GPs. This removed the manual model copy / volume heal /
  GP-setting that the first cloud bring-up needed.
- **Reproducible cloud.** `make cloud-up` brings up querystore-on-Elasticsearch
  hands-off (`CHARTSEARCH_QUERYSTORE_BACKEND`, default elasticsearch): starts ES,
  pre-sets the backend GP, `--build`s the image, waits for the REST API to answer
  (not just the Tomcat healthcheck), and runs configure *inside* the backend
  container (`CHARTSEARCH_EXEC` — on the cloud the host only reaches the backend
  through Caddy's domain on :443, so host curls get 308/reset). Verified:
  `cloud-up` → "Stack up", cloud ES cluster populated (`querystore_drug_order`=39).
