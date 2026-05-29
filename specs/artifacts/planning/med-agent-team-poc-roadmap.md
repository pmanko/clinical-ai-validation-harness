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

## 3. Knowledge base — openly-licensed clinical seed + OpenMRS contextualization (demo-grade precursor to F009)

**User decision:** "clinical seed + OpenMRS-contextualized" (over dogfooding our own docs). The demo KB carries **real openly-licensed clinical content**, narrowed to the demo deployment's profile. It is a **demo-grade precursor to F009** (`roadmap.canvas.tsx:347-368`), not F009 itself — no hybrid rerank, no LLM-assisted curation worker, no ≥10pp eval gate yet.

**Content — openly-licensed clinical seed (Tier 1):** a few dozen hand-curated, section-aware snippets from WHO IMCI (danger signs, common-illness management), WHO Essential Medicines List, WHO/national immunization schedules, pediatric dosing, RxNorm drug essentials, and a few MSF Clinical Guideline protocols. All openly licensed (F009 FR-009.7; exact terms verified at acquisition — WHO is CC BY-NC-SA IGO, RxNorm is NLM public domain, MSF guidelines freely published). Each snippet carries `source + version + url + anchor` so it cites to a real fragment. LMIC-relevant by design.

**Contextualization — OpenMRS, demo-grade (Tier 2):** narrow/boost the seed to what the demo deployment actually treats, via a **read-only aggregate query** against the harness OpenMRS 2.8 demo DB (top diagnoses / concepts / formulary by frequency) that filters or boosts the seed — e.g. the HIV demo data surfaces ART content, not warfarin. Optionally tag snippets with **CIEL concept codes** so KB retrieval aligns with the chart's coded data. This is **not** F009's full LLM-assisted curation worker + human-review gate (CUICurate-inspired) — that's deferred; the demo shows the contextualization *idea* with a deterministic, **PHI-free** (aggregates only) filter.

**Search tech (in-container):** SQLite **FTS5 BM25** via stdlib `sqlite3` — zero new deps, explainable, fine for a few-hundred-snippet corpus. Upgrade path only if recall is visibly poor: a `sqlite-vec` table in the same `.db`, vectors from LM Studio `/v1/embeddings` ([LM Studio docs](https://lmstudio.ai/docs/developer/openai-compat/embeddings)), fused via RRF. Avoid FAISS/Chroma.

**Retrieve/inject:** a **deterministic pre-step** (not an orchestrator tool) — predictable, reproducible, honest to demo. Each snippet carries a provenance label ("openly-licensed reference content — not a substitute for clinical judgment") propagated into the synthesizer's system instruction. KB content stays **out of the integer citation array** (inline prose provenance only).

**Index-as-artifact:** **commit `artifacts/kb/corpus.jsonl`** (the curated clinical seed — small, diff-reviewable, license-tagged per snippet). **Gitignore the FTS5 index; rebuild on boot.** `make kb-build` regenerates corpus + index; `make kb-contextualize DEPLOYMENT=demo` runs the aggregate filter.

**Content & index guidance for low-power accuracy** (grounded in `clinical-kb-research.md` §A.3; goal = maximize 4-8B accuracy lift):
- **Prioritize fact-pinning content** — the lift (MedRAG/MIRAGE: up to ~18pp) concentrates on specifics small models fabricate: exact doses, contraindications, interactions, IMCI thresholds, immunization timing. Seed those first.
- **Snippet shape**: atomic, section-aware, ≤~300 tokens; **K=3** at the **top** of the KB block (lost-in-the-middle, TACL 2024); **abstain** below the relevance floor (no KB beats irrelevant KB).
- **Two indexes** (both): (1) retrieval index — FTS5 BM25 for the demo; if recall is weak, add a **cross-encoder reranker** (MS-MARCO MiniLM, ~22M, CPU-cheap — highest-leverage small-model lever) *before* a dense index (`sqlite-vec`+RRF, encoder chosen empirically per "generalist beats biomedical", §A.3). (2) content manifest — `corpus.jsonl` (title+summary+source+version+license+tags+CIEL), doubling as the contextualization input, citation resolver, and transparency surface.
- **Measure the lift, don't assert it**: gate on KB-on vs KB-off A/B via the 006 validation harness (F009's bar is ≥10pp on a MIRAGE-style set). Seed the KB with content that answers the eval scenarios so the lift is observable.

## 4. Roadmap

**P1 — Boot as a chartsearchai-selectable OpenAI-compat endpoint (the bridge).**
Deliverables: `server/openai_compat.py` with `POST /v1/chat/completions` (sync + SSE) and `GET /v1/models`; ChatCompletion schemas in `schemas.py`; full `messages[]` threaded through; `response_format` passthrough; honcho/Procfile single-image `Dockerfile` running web + 3 agent processes; harness submodule `targets/med-agent-hub/`; compose + registry entry.
Exit: `curl /v1/chat/completions` returns a valid `chart_answer` envelope; **`/v1/models` exposes ≥2 ids** (picker hides when `available.length < 2`, `model-picker.component.tsx:148`); let `/api/v1/models` 404 so the hub is tagged `provider:"generic-openai-compat"` (`:514`); a picker selection writes the GP and the id round-trips as the request `model`; per-turn latency captured.

**P2 — Orchestrator + medgemma + gemma-4 synthesizer (no KB).**
Deliverables: thin code orchestrator; medgemma free-text expert call; gemma-4 synthesizer bound to `response_format`; buffer-then-stream-synthesizer path; guaranteed-valid fallback envelope on sub-agent timeout.
Exit: a turn produces a schema-valid envelope from real medgemma→gemma calls; killing medgemma still returns a valid (reduced-confidence) envelope; streamed `delta.content` incrementally forms valid `{"answer":...}` so chartsearchai's `AnswerExtractingConsumer` can parse it.

**P3 — KB agent + clinical seed + OpenMRS contextualization.**
Deliverables: curate the openly-licensed clinical seed → `corpus.jsonl` (section-aware; per-snippet source+version+url+anchor+license); FTS5 index built on boot; a read-only aggregate query against the demo OpenMRS DB → a PHI-free contextualization filter/boost (optional CIEL tags); KB pre-step injecting a labeled block after the question; synthesizer instruction enforcing integer-citations-for-chart-only + inline KB provenance.
Exit: a clinical question whose answer lives in the seed (e.g. IMCI danger signs, metformin dosing) pulls the right cited snippet; the contextualized set is measurably narrower/relevant to the demo deployment's profile (HIV-demo surfaces ART content); KB content never appears as an integer citation; no PHI in the contextualization query/artifact (asserted); frozen prefix byte-identical across turns (`cached_tokens > 0`).

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
