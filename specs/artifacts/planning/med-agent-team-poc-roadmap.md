# Plan: med-agent-hub as the "Med Agent Team" — chartsearchai-selectable agent endpoint + dogfooded KB (POC)

> Review draft (workflow `wab20szmm`, 7 agents). Grounded in live source; cites file:line + primary sources. Not yet committed scope — for critique. Once approved it graduates to a numbered feature spec.

## 1. Situation

med-agent-hub (fork `pmanko/med-agent-hub`, branch `harness-integration` @ `5cac078`, clone at `/Users/pmanko/code/med-agent-hub`) is a reboot stub. It serves only `/`, `/manifest`, `/health` (`server/main.py:46,60,76`); the OpenAI-compat bridge chartsearchai needs is a commented placeholder (`main.py:94-98`). The router is single-dispatch and query-string-only — it extracts one string via `context.get_user_input()` (`router_executor.py:179`), routes on it, forwards one `TextPart` to one subagent, and copies that artifact back verbatim (`router_executor.py:215-242`). `response_format` appears nowhere (grep = 0 hits); `Dockerfile.server:99` runs only `uvicorn server.main:app`, so the image can't even reach the A2A agents (`Procfile.dev` runs four processes). The target: med-agent-hub exposes OpenAI-compat `/v1/chat/completions` + `/v1/models`, forwards the full chartsearchai `messages[]`, runs a coordinated team (orchestrator → KB → medgemma → gemma synthesizer), and returns chartsearchai's strict `{answer, citations, blocks}` envelope — selectable in the model picker as "Med Agent Team." Note: the survey-referenced `specs/005-med-agent-hub-bridge/` dir does **not** exist on this branch; F005 lives in `roadmap.canvas.tsx:303-322`. The wire contract below is pinned from live chartsearchai Java source, the source of truth.

## 2. Target architecture

**Topology resolution (the central ambiguity): gemma-4 is BOTH orchestrator and synthesizer; sequencing is a thin deterministic code orchestrator, not an LLM router.** Justification is structural: F005's router (`roadmap.canvas.tsx:309`, llama-3.1-8b classifier) exists to **pick one** subagent. The team topology **runs every agent every turn** in a fixed pipeline (KB → medgemma → gemma) — so there's nothing left to classify. The pick-one job disappears; an LLM router call would be pure serial latency for zero routing decision. This is an *evolution* of F005's intent (its router was for backend selection, which the fixed roster makes moot), surfaced as Open Decision #1 so the F005 author can veto. The chain is sequential + dependent, so latencies **add** — Anthropic's "90% time cut" is *parallel* subagents and does not apply ([Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)). So minimize N to ~2 LLM calls/turn (medgemma expert → gemma synthesizer); the KB step is non-LLM ([MDAgents adaptive routing, arXiv 2404.15155](https://arxiv.org/html/2404.15155v1)).

**Message flow for one chartsearchai turn.** chartsearchai sends `[system, user(chartEnvelope), ...prior turns (no chart bytes), user(question)]` with strict json_schema `chart_answer` and (on stream) `stream_options.include_usage` (`RemoteLlmEngine.java:172-198`, `ChatMessages.java:33-104`):

1. **Bridge** (`/v1/chat/completions`) receives the full `messages[]` + `response_format`. Routes on `model` id, validates, hands the array to the orchestrator.
2. **Orchestrator** (thin Python, no LLM) sequences the pipeline and owns graceful degradation (per-call timeout; on KB/expert failure, proceed and still return a valid envelope).
3. **KB agent** (deterministic, non-LLM) extracts the current question, retrieves top-k=3-5 chunks, builds one **labeled context block appended AFTER the question** — never into the system/chart prefix.
4. **medgemma medical-expert** receives `[system', chart, priors, question, kb-block]` as free text, returns clinical reasoning (no schema binding).
5. **gemma-4 synthesizer** receives chart + question + KB block + medgemma's reasoning, is bound to chartsearchai's `response_format` (passed through verbatim to LM Studio), and emits the single `{answer, citations, blocks}` envelope.
6. **Bridge** returns it as `choices[0].message.content` (a stringified JSON envelope, per `LlmResponseParser.java:58-86`).

**Model assignment.**

| Role | Model | Call type | Schema-bound | Notes |
|------|-------|-----------|--------------|-------|
| Orchestrator | none (Python) | — | — | sequences + degrades gracefully; replaces F005 LLM router |
| KB agent | none (BM25/FTS5) | retrieval | — | non-LLM pre-step; injects after question |
| Medical expert | medgemma (1.5) | OpenAI-compat → LM Studio | no (free text) | clinical reasoning enrichment |
| Synthesizer | gemma-4 | OpenAI-compat → LM Studio | **yes** (`chart_answer`) | composes envelope; the streaming endpoint |

**KB citations vs patient-chart citations — the type system enforces it.** `citations[]` items are `type:integer` (chart-record indices) and block-cell `refs` are `type:integer` too (`ChartAnswerResponseFormat.java:56-60, 95-97`). There is no string citation channel, so a `kb:roadmap#kb-agent` string-prefix namespace is **unrepresentable** — and that's a feature: KB content can never become a chart-record integer. Mechanism: synthesizer emits integer `[N]` citations **only** for chart-derived claims, **never** attaches an integer to a KB-derived claim, and surfaces KB provenance as inline labeled prose ("per internal project documentation…"). A cited hallucination (KB content presented as "the chart says") is structurally impossible via the citation array.

**Prefix-cache tradeoff + mitigation.** chartsearchai pins `[system, user(chart)]` byte-identical across turns so LM Studio's prompt cache skips re-prefilling the chart (`ChatMessages.java:36-48`). med-agent-hub now owns that upstream call, so two rules: (a) the synthesizer's LM Studio call keeps `[system, user(chart)]` byte-identical and appends KB/expert context only after the question; (b) pin **one** synthesizer model (gemma-4) so the chart prefix stays cache-stable — a per-turn model switch re-prefills the whole chart (cache is per-model). Internal medgemma calls use their own prompts and don't benefit from chartsearchai's cache; fine.

**Streaming + json_schema tension.** `response_format` is sent on the stream path too (`RemoteLlmEngine.java:110,183-189`), and the sync-path `.timeout()` wraps the *whole* pipeline → `HttpTimeoutException` if the team is slow. Posture: **buffer the chain, then stream only the synthesizer's structured output** once its call begins. Pre-synthesis work (KB + medgemma) raises time-to-first-token; measure it.

## 3. Knowledge base (POC mechanism, NOT roadmap F009)

Dogfoods *our own design docs* to demonstrate the KB-agent *mechanism*. Explicitly **not** F009 (`roadmap.canvas.tsx:347-368`), the real clinical KB (WHO IMCI/EML, RxNorm, hybrid BM25+RRF+cross-encoder, ≥10pp accuracy-lift gate). Label as mechanism POC so "FTS5-only / our-docs corpus" is never mistaken for F009.

**Corpus (high-value seeds):** `roadmap.canvas.tsx`; `specs/006-validation-harness-mvp/spec.md` (envelope + abstention rubric); `specs/007-llm-config-overrides/`; `specs/artifacts/canvases/{chartsearchai-and-querystore, clinical-ai-research-guidance, scout-comparative-analysis, validation-research}.canvas.tsx`; `specs/artifacts/sibling-context/*`; `specs/artifacts/planning/clinical-kb-{brief,research}.md`; `specs/artifacts/handoffs/session-handoff-2026-05-12.md`.

**Ingestion — mixed corpus, two parsers.** Richest sources are `.canvas.tsx`, not markdown. `.md`: split on `##`/`###`, prepend full header path ([Weaviate chunking](https://weaviate.io/blog/chunking-strategies-for-rag)), 256-512 tokens. `.tsx` canvases: **targeted field extraction** (pull `title/purpose/scope[]/evidence[]/note/detail` from node objects; skip SVG/layout). Without the canvas parser the corpus collapses to a handful of specs.

**Search tech (concrete, in-container):** SQLite **FTS5 BM25** via stdlib `sqlite3` — zero new deps, explainable, fine for a few-hundred-chunk corpus reusing our own vocabulary. Upgrade path only if recall is visibly poor: a `sqlite-vec` table in the same `.db`, vectors from LM Studio `/v1/embeddings` ([LM Studio docs](https://lmstudio.ai/docs/developer/openai-compat/embeddings)), fused via RRF. Avoid FAISS/Chroma.

**Retrieve/inject:** a **deterministic pre-step**, not an orchestrator tool — predictable, reproducible, honest to demo. Each snippet carries a provenance label ("Source: internal project documentation — not clinical guidance") propagated into the synthesizer's system instruction.

**Index-as-artifact:** **commit `artifacts/kb/corpus.jsonl`** (small, diff-reviewable). **Gitignore the index; rebuild on boot.** A `make kb-build` regenerates corpus + index from `specs/`.

## 4. Roadmap

**P1 — Boot as a chartsearchai-selectable OpenAI-compat endpoint (the bridge).**
Deliverables: `server/openai_compat.py` with `POST /v1/chat/completions` (sync + SSE) and `GET /v1/models`; ChatCompletion schemas in `schemas.py`; full `messages[]` threaded through; `response_format` passthrough; honcho/Procfile single-image `Dockerfile` running web + 3 agent processes; harness submodule `targets/med-agent-hub/`; compose + registry entry.
Exit: `curl /v1/chat/completions` returns a valid `chart_answer` envelope; **`/v1/models` exposes ≥2 ids** (picker hides when `available.length < 2`, `model-picker.component.tsx:148`); let `/api/v1/models` 404 so the hub is tagged `provider:"generic-openai-compat"` (`:514`); a picker selection writes the GP and the id round-trips as the request `model`; per-turn latency captured.

**P2 — Orchestrator + medgemma + gemma-4 synthesizer (no KB).**
Deliverables: thin code orchestrator; medgemma free-text expert call; gemma-4 synthesizer bound to `response_format`; buffer-then-stream-synthesizer path; guaranteed-valid fallback envelope on sub-agent timeout.
Exit: a turn produces a schema-valid envelope from real medgemma→gemma calls; killing medgemma still returns a valid (reduced-confidence) envelope; streamed `delta.content` incrementally forms valid `{"answer":...}` so chartsearchai's `AnswerExtractingConsumer` can parse it.

**P3 — KB agent + searchable KB.**
Deliverables: ingestion (md + canvas parsers) → `corpus.jsonl`; FTS5 index built on boot; KB pre-step injecting a labeled block after the question; synthesizer instruction enforcing integer-citations-for-chart-only + inline KB provenance.
Exit: a question whose answer lives in our docs visibly pulls the right snippet; KB content never appears as an integer citation; frozen prefix byte-identical across turns (`cached_tokens > 0`).

**P4 — Wire into validation harness (006).**
Deliverables: team registered as a harness endpoint; scenario eval over 006's abstention + Scout rubric.
Exit: team scored on ≥1 scenario set; KB-on vs KB-off A/B captured; latency/cost per turn reported.

## 5. Open decisions (defaults proposed)

1. **Orchestrator topology** — fold routing into gemma-4 + thin code orchestrator, OR keep F005's LLM-classifier router? *Default: fold* — a fixed run-every-agent pipeline has nothing to classify. (F005 author veto point.)
2. **KB search tech** — FTS5 BM25 only, OR hybrid (BM25+sqlite-vec+RRF) now? *Default: BM25 only* — zero deps; few-hundred-chunk corpus; clean upgrade path.
3. **KB agent** — deterministic pre-step, OR a tool the orchestrator may call? *Default: pre-step* — predictable, reproducible, cheaper, honest to demo.
4. **Internal agent transport** — keep A2A multi-process, OR in-process Python team? *Default: keep A2A* — current code is A2A executors; preserves F005 posture. (In-process would cut latency/complexity.)
5. **Bridge scope this milestone** — minimal bridge for the team only, OR finish F005's full cleanup/upstream first? *Default: minimal* — unblocks the demo fastest; F008 gateway generalizes later.
6. **Demo `/v1/models` second id** — expose underlying medgemma/gemma as real selectable backends, OR a synthetic A/B sibling? *Default: real underlying models* — satisfies the ≥2-id picker constraint *and* gives genuine team-vs-raw A/B demo value.
