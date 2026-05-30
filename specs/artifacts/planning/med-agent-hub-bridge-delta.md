# med-agent-hub bridge — survey + delta note (MAH.A1)

Grounded in the actual code: med-agent-hub `harness-integration` (server/) + chartsearchai backend (RemoteLlmEngine, ChartAnswerResponseFormat) + advisor review.

## What exists in med-agent-hub today (post-reboot @5cac078)

- **`main.py`** — slim FastAPI facade: `/`, `/manifest`, `/health`. The OpenAI-compat bridge is **NOT built yet** — only a placeholder comment ("mount `server/openai_compat.py`"). So the bridge endpoint is net-new.
- **`sdk_agents/react_router_executor.py`** (345 LoC) — the ReAct loop, but bound to the **A2A runtime**: subclasses `AgentExecutor`, uses `EventQueue`/`TaskUpdater`, discovers subagents via **A2A agent-cards** over HTTP, and dispatches to them as **separate A2A server processes** (`medical_server` :9101, `clinical_server` :9102). Also carries **demo cruft** (hardcoded `heatstroke`/`cities` multi-intent heuristics) and **process-comments** (`feature 005 phase 1B`).
- **`Procfile.dev`** — runs **4 uvicorn processes** (web + router + medical + clinical) = the in-process A2A mesh the research says to collapse.
- **`llm_clients.py`** — `LLMClient.generate_chat()` posts OpenAI-compat; **no `response_format`, no streaming** (returns first-choice content only). `GeminiClient` + `OrchestratorClient` give a provider switch (local ↔ gemini) = the model-swap substrate (knob B) partly exists.
- **`mcp/`** — a hand-rolled MCP-ish tool abstraction (`MCPTool` ABC, registry, jsonschema). `medical_search_tool.py` is a **MOCK** (returns fake PMIDs). No real KB. (Also Spark/FHIR/appointment tools = heavier, not needed for v1.)
- **`schemas.py`** — legacy `ChatRequest{prompt, orchestrator_mode: simple|react}` — not OpenAI-compat; net-new schemas needed.

## Verified envelope contract (from chartsearchai's real code — NOT memory)

- **chartsearchai SENDS `response_format: json_schema` itself** (`RemoteLlmEngine.java:189`), strict mode, schema `{answer:string, citations:int[], blocks:Block[]}` — all three **required**, `additionalProperties:false`. `blocks` = table blocks (`kind:"table"`, columns, rows of cells `{text, refs:int[]}`).
- In the same body it sets `temperature:0.0` (or `top_k:1` for claude-opus-4-7), **`max_tokens:4096`**, `stream:true|false` (+ `stream_options.include_usage` when streaming).
- **The chat path uses BOTH** `infer` (non-stream) and `inferStreaming` (`LlmProvider.java:125/151/340/364`; `ChatServiceImpl.chatStreaming`). The envelope is parsed **whole** (accumulating parser).

→ **Implication:** the bridge mostly **FORWARDS** chartsearchai's `response_format`/`temperature`/`max_tokens`/`stream` to LM Studio; constrained decoding does the envelope enforcement. This deletes most of the old plan's envelope/streaming complexity.

## Proposed v1 delta (advisor-reviewed) — **for user's read before coding**

1. **Reuse the ReAct *pattern*, shed the A2A *wrapper*.** Extract the loop (iterate: LLM-with-tools → run tool → observe → loop → finalize; keep `MAX_ITERATIONS`, `_extract_json`) into a plain in-process async orchestrator the bridge calls with `messages[]`. **Drop:** the `AgentExecutor` base, the `_call_agent` A2A dispatch, the subagent server processes (collapse Procfile to one), the heatstroke/cities heuristics, the process-comments. Keep it iterative + multi-tool (NOT a fixed pipeline).
2. **Envelope on the FINAL synthesis call only.** Run the tool loop **plain** (tools, no `response_format`) — constrained-JSON + tool-calling in the same turn is unreliable on 4-8B. When the model stops calling tools, do **one** final synthesis call **with** `response_format`=the forwarded envelope and no tools. (Bonus: this is exactly the single constrained call the guardrails research wants.)
3. **Forward, don't hardcode.** Thread chartsearchai's `response_format`/`temperature`/`max_tokens`/`stream` through to LM Studio. (`_call_llm` currently hardcodes `max_tokens:1000` → would truncate a 4096 multi-block envelope. Fix.)
4. **Streaming: support `stream:true` via buffer-then-emit SSE.** The chat path can send `stream:true`, so the bridge must return valid SSE — but it can run the loop, build the whole envelope, then emit it as a final SSE chunk + `[DONE]`. No true token-streaming from the loop. (Simplification, not full deferral.)

## Phase sequencing (roadmap §4, P1–P4 — confirmed with user 2026-05-29)

The team + KB scope are **settled in the roadmap §2–§3**; this delta applies the recalibration (in-process ReAct over typed tools; A2A/MCP-protocol deferred) to them. **Merged P1+P2 (user 2026-05-29):** the bridge stands up the real in-process team from the start — no single-model proxy step — because the existing team is A2A-welded (can't be routed through a plain endpoint without the in-process refactor anyway), and starting with the ReAct structure matches the recalibration. Build order:

- **P1 — Bridge + in-process team (no KB).** The OpenAI-compat endpoint calls the refactored **in-process ReAct loop** from the start: `messages[]` + `response_format`/`temperature`/`max_tokens` forwarded; loop = gemma-4 (swappable / llama-3.1-8b fallback) **+ medgemma-1.5-4b expert tool + gemma-4 synthesizer** (envelope on the **final** call) **+ guaranteed-valid fallback envelope** on sub-agent timeout; valid `chart_answer` envelope; `/v1/models`≥2 ids; picker round-trips; runs in the harness (container + submodule + compose). De-risk by **curling the loop directly** before wiring picker/compose/cloud. (Probe gemma-4 tool-calling reliability early; fall back to llama-3.1-8b if poor.)
- **P3 — KB.** The settled §3 scope: openly-licensed clinical seed + OpenMRS contextualization (PHI-free aggregate), FTS5 BM25, `corpus.jsonl` committed, fact-pinning/K=3/abstain, integer-citations-chart-only + inline KB provenance. **KB engagement (typed tool the loop may call vs always-on pre-step) decided at P3** — measure both with the 006 harness.
- **P4 — Validate.** Register the team in the 006 harness; **KB-on/off A/B** + abstention/Scout rubric; latency/cost per turn.

## Team (settled, §2) — not re-litigated
gemma-4 e4b **orchestrator + synthesizer** (dual role, swappable, llama-3.1-8b fallback) · medgemma-1.5-4b medical expert · KB lookup (FTS5 BM25). The separate `clinical/generalist` A2A subagent in the current code is old demo scaffolding — dropped. KB & expert are **typed tools** (recalibration), not A2A agents. Probe gemma-4 tool-calling reliability before committing.

## Out of scope for v1 (deferred seams, unchanged)
MCP protocol, A2A agent-cards/executors, real KB (F009), Spark/FHIR tools, `/v1/agents` skill surface, deterministic control-flow hardening, output safety-guards (citation-resolution/abstention) — all measurement-driven or boundary-triggered per the synced planning docs.
