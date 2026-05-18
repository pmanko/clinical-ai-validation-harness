# Sitrep — pivot from multi-turn iteration → agent-team + skills + presentation

> Authored 2026-05-18 during a pivot away from continuing single-shot iteration on
> chartsearchai. Primary sources: `pmanko/med-agent-hub`, `pmanko/omrs-ai-playground`,
> plus the already-landed `specs/artifacts/canvases/scout-comparative-analysis.canvas.tsx`.
> Read-only review. Three POC paths laid out with explicit Java-vs-Python boundary calls.

---

## 0. Executive summary

**med-agent-hub** is a working Python A2A v0.3.2+ multi-agent system. Four executors (Router, Medical/MedGemma, Clinical V2, Administrative) run as independent uvicorn processes, each registered as an `AgentExecutor` against an `A2AStarletteApplication` that exposes `/.well-known/agent-card.json`. The Router has two operating modes selected via `message.metadata.orchestrator_mode`: a single-shot LLM classifier (`router_executor.RouterAgentExecutor`) and a tool-calling ReAct loop (`react_router_executor.ReactRouterExecutor`) wired through a `DispatchingExecutor`. Agents are configured by YAML (`server/agent_configs/*.yaml`) and use a real mixture-of-experts: Llama-3.1-8B for the orchestrator, MedGemma-4B for medical synthesis, Gemma-3-4B for clinical SQL/parameter generation. The Clinical V2 executor wires a registry of MCP tools (`SparkPopulationAnalyticsTool`, `SparkPatientLongitudinalTool`, `FHIRSearchTool`, `MedicalSearchTool`) with JSON-Schema-validated input. The web client (`web/src/App.svelte`) is a thin Svelte chat with a mode toggle and an "Answer from: <agent>" label — that's the entire UI sophistication.

**omrs-ai-playground** is an Instant OpenHIE v2 composition harness that wraps med-agent-hub plus several siblings as packages and projects. The two interesting code units are `projects/omrs-appo-service` (a finite-state-machine WhatsApp triage assistant on FastAPI + Redis + MedGemma; very different shape from med-agent-hub) and `packages/analytics-ohs-data-pipes` (Parquet-on-FHIR via Spark Thrift, the data plane behind med-agent-hub's population analytics MCP tool). The platform composes via docker-compose overrides and `package-metadata.json` env-var contracts.

**Improvement paths, one-line answers:**

1. **Agent-team**: Adopt **Shape C (LLM-tool-calling subagents inside one Java orchestrator)** — port med-agent-hub's `clinical_executor_v2._route_to_skill` + `_execute_skill` pattern into Java, not its multi-process A2A topology. The Java/Python boundary makes Shape B too heavy for POC; Shape C captures 80% of the architectural win.
2. **Skills**: Steal the **A2A agent-card skill JSON shape verbatim** (`{id, name, description, tags, examples}`) and surface `examples` as clickable chips. The discovery mechanism in `router_executor._discover_agents` is the *exact* pattern, just collapsed to a static registry the Java backend serves at `/ws/rest/v1/chartsearchai/skills`.
3. **Presentation**: Extend the answer envelope from `{answer, citations[]}` to `{answer, citations[], key_findings[], suggested_followups[], confidence}` and render each as a typed Carbon component. Borrow Scout's evidence-card pattern (already analyzed in `scout-comparative-analysis.canvas.tsx`); the chartsearchai citation pill panel is the 80% prototype.

**Footguns:**
- **Don't import the A2A SDK into chartsearchai.** chartsearchai is Java/Spring/Hibernate in an OpenMRS .omod. A2A SDK 0.3.2+ is Python, `a2a.server.apps.A2AStarletteApplication` is Starlette-on-Python. Cross-process is the wrong default for a single-tenant chart QA panel.
- **Don't replicate the multi-uvicorn Procfile.dev topology.** med-agent-hub runs five uvicorn processes (web + router + medical + clinical + admin) on five ports. That makes sense for an OpenHIE composition; it's pure overhead for an OpenMRS module that already lives inside one JVM.
- **Don't adopt the appo-service Redis state machine.** chartsearchai already has chat sessions in MySQL via the recent multi-turn work (`chat_session.chart_snapshot`, `ChatMessages.fromTurns`). The appo-service pattern is for fundamentally different ergonomics (asynchronous WhatsApp, no UI re-render); chartsearchai's frontend has direct DOM control over state.

---

## 1. med-agent-hub: what's actually there

### Architecture and process topology

`Procfile.dev` (full content, 5 lines) is the architectural source of truth:

```
web:      uvicorn server.main:app                      :8080
router:   uvicorn server.sdk_agents.router_server:app  :9100
medical:  uvicorn server.sdk_agents.medical_server:app :9101
clinical: uvicorn server.sdk_agents.clinical_server:app:9102
admin:    uvicorn server.sdk_agents.administrative_server:app :9103
```

Five processes. The `web` process is a FastAPI shim with `/generate/{model}` direct endpoints and a `/chat` endpoint that proxies to the router. Each agent process builds an `A2AStarletteApplication` whose `DefaultRequestHandler` wraps that agent's `AgentExecutor` and an `InMemoryTaskStore`. Discovery is decentralized: each agent serves its own `/.well-known/agent-card.json`.

### The four executors

`server/sdk_agents/`:

| File | Class | Role | Lines |
|---|---|---|---|
| `router_executor.py` | `RouterAgentExecutor` | Single-shot LLM router | 207 |
| `react_router_executor.py` | `ReactRouterExecutor` | Tool-calling ReAct loop, `MAX_ITERATIONS = 5` | 280 |
| `dispatch_executor.py` | `DispatchingExecutor` | Reads `message.metadata.orchestrator_mode` and picks one | 34 |
| `medical_executor.py` | `MedicalExecutor` | Plain LLM passthrough, MedGemma, hardcoded disclaimer | 130 |
| `clinical_executor_v2.py` | `ClinicalExecutorV2` | Skill-routed + MCP-tool-using | 540 |
| `administrative_executor.py` | `AdministrativeExecutor` | Two skills (review/schedule), single MCP tool | 360 |

### The router pattern (load-bearing for improvements #1 and #2)

`router_executor.RouterAgentExecutor._discover_agents()` (lines 60–98) is the heart. At startup it reads `ACTIVE_AGENTS` env, maps each name to a port, and `GET`s `/.well-known/agent-card.json` synchronously. The resulting `self.agents` dict records each agent's `url`, `name`, and a flat list of skill IDs.

`_route_query()` (lines 108–148) then formats those into the routing prompt:

```python
agents_info = "\n".join([
    f"- {name}: {info['name']} (skills: {', '.join(info['skills'])})"
    for name, info in self.agents.items()
])
system_prompt = self.system_prompt_template.format(agents_info=agents_info)
```

The template (from `router.yaml`):

```yaml
system_prompt_template: |
  You are a query router for a medical multi-agent system.
  Available agents:
  {agents_info}
  Respond with JSON: {{"agent": "agent_name", "reasoning": "why this agent"}}
```

LLM call → JSON parse → fallback to `"medical"` on parse error. Then `ClientFactory(client_config).create(agent_card)` constructs an A2A client and `client.send_message(message)` streams events back. Final artifact gets forwarded to the parent task.

### The ReAct router (alternative orchestration mode)

`react_router_executor.py` builds OpenAI-style `tools` definitions from agent cards (lines 60–88) and uses `tool_choice: "auto"` against the orchestrator LLM. Each tool call produces an "observation" appended to history; loop terminates when the LLM returns content with no tool_calls. Notably it includes a heuristic multi-intent gate (lines 209–217) — if the query has both "medical" and "general" intent and only one tool has been called, it injects a synthetic `user` message demanding the missing one. Useful pattern; ugly implementation.

### MCP tool wiring

`server/mcp/base.py` defines `MCPTool` (abstract) + `MCPToolRegistry`. Each tool exposes a `schema` property with JSON-Schema `input_schema`, and `safe_invoke()` validates input before calling `invoke()`. The clinical executor registers tools conditionally on env presence:

```python
# clinical_executor_v2.py:127-148
if spark_config['host']:
    self.tool_registry.register(SparkPopulationAnalyticsTool(spark_config))
    self.tool_registry.register(SparkPatientLongitudinalTool(spark_config))
if fhir_config['base_url']:
    self.tool_registry.register(FHIRSearchTool(fhir_config))
self.tool_registry.register(MedicalSearchTool())  # always
```

`SparkPopulationAnalyticsTool.schema` (in `spark_tools.py`) declares `analysis_type ∈ {prevalence, trends, demographics, comorbidities, custom}`, plus `condition`, `timeframe`, `filters`, `custom_sql`. The two-step internal flow is: (1) LLM generates parameters from query using `skill_prompts.population_analytics` template, (2) tool builds SQL via `_build_query()` and runs it through PyHive. Step (3) is a *separate* synthesis LLM call that reframes raw rows as clinical interpretation (`clinical_executor_v2.py:_execute_skill` lines 318–344).

The `SparkProfile` (`base.py` lines 38–104) is a logical-to-physical column mapping loaded from YAML, with introspection that asks `DESCRIBE <table>` and gates feature availability on column presence. This is over-engineered for chartsearchai but worth flagging as the right pattern for the analytics use case.

### Mixture of experts (model assignment)

From `server/config.py:23-26` and `agent_configs/*.yaml`:

| Agent | Model | Role |
|---|---|---|
| router (orchestrator) | `meta-llama-3.1-8b-instruct` | Cheap classifier, JSON-only output |
| medical | `medgemma-4b-it` | Clinical synthesis with disclaimer |
| clinical | `gemma-3-4b-it` | SQL/parameter generation, then synthesis |
| administrative | `meta-llama-3.1-8b-instruct` | Routing + parameter extraction |

Temperatures: orchestrator 0.3, medical 0.1, clinical 0.3. All routed through one LM Studio at `LLM_BASE_URL` — same posture as chartsearchai's LM Link to LM Studio. There's an optional Gemini orchestrator path (`ORCHESTRATOR_PROVIDER=gemini`, `config.py:64-71`) but it's not the default.

### Client / web frontend

Two surfaces:
- `client/` — vanilla JS + Pico.css, 15KB `script.js`. Has a mode dropdown (Direct vs Agents-A2A), system-prompt presets, conversation history capped at 20 messages, custom-prompt editor. Renders markdown via `marked`. The `addMessage()` function (lines 175–195) is the *entire* renderer — plain text or `marked.parse(content)`.
- `web/` — Svelte + Vite, 8KB `App.svelte`. Same model. The only structured-output handling is `data.responding_agent` → `<small class="agent-label">Answer from: {m.agent}</small>` (lines 73–76, 156–160). Markdown again via `marked`.

The presentation layer is intentionally minimal. There is no structured-output renderer, no evidence card, no skill chip surface. Skills exist in the agent cards but the UI never advertises them — the user types free text.

### Tests

`tests/test_a2a_sdk.py` (15.5KB), `test_react_orchestrator.py`, `test_mcp_integration.py`, `test_router_a2a.py`. They exercise the SDK against a running cluster — not unit tests in the chartsearchai sense.

---

## 2. omrs-ai-playground: what's actually there

### Instant OpenHIE composition pattern

Top-level layout pulls med-agent-hub, fhir-data-pipes, a2a-samples, appoint-ready as **submodule files** (those are submodule pointer files, hence `type: file` size~85 each). The platform's own first-class units are:

- **Packages** (`packages/*`) — Docker Compose units with `package-metadata.json` declaring env-var contracts. `packages/med-agent-hub/docker-compose.yml` shows how med-agent-hub gets wrapped: external networks `multiagent`, `openmrs`, `open-health-stack` so it can dial OpenMRS by hostname; env-var passthrough for `LLM_BASE_URL`, `OPENMRS_FHIR_BASE_URL`, `SPARK_THRIFT_HOST`; a healthcheck on `/health`.
- **Projects** (`projects/*`) — first-party application code. `omrs-appo-service`, `synthetic-data-uploader`, and the `omrs-appo` legacy dir.

`packages/med-agent-hub/package-metadata.json` is the cleanest illustration of the pattern: it declares **27 env vars** with defaults, mapping the entire med-agent-hub configuration surface (LLM endpoints, A2A URLs, FHIR creds, Spark coordinates, agent ports) so the package can be `init`-ed via `./instant package init -n med-agent-hub -d`.

**Transferable insight:** Instant OpenHIE's *composition contract* is a clean env-var manifest with defaults. chartsearchai already has this implicitly via `.env.chartsearch.cloud`; nothing new to import.

### omrs-appo-service: the agent-of-different-shape

A FastAPI service that *is not* an A2A agent. It's a stateful workflow orchestrator over WhatsApp. Architectural shape (from `ARCHITECTURE.md` and `src/services/conversation_manager.py`):

**State machine**: `INITIAL → COLLECTING_SYMPTOMS → TRIAGE_ASSESSMENT → SCHEDULING_APPOINTMENT → CONFIRMING_DETAILS → COMPLETED | CANCELLED`. Each state has a handler (`conversation_manager.py:21-30`):

```python
self.state_handlers = {
    ConversationState.INITIAL: self._handle_initial_state,
    ConversationState.COLLECTING_SYMPTOMS: self._handle_collecting_symptoms,
    ConversationState.TRIAGE_ASSESSMENT: self._handle_triage_assessment,
    ...
}
```

**Session persistence**: Redis with 24h TTL. `session_manager.py:18-20`: `self.session_ttl = timedelta(hours=24)`. Keys are `whatsapp_session:{phone_number}`. The whole `ConversationSession` Pydantic object (state + patient profile + triage data + history) is JSON-serialized into one Redis key.

**MedGemma client** (`medgemma_client.py`) is Google's hosted MedGemma via `google.generativeai.GenerativeModel`, *not* the same MedGemma path med-agent-hub uses (LM Studio + GGUF). It has three semantic-distinct call surfaces: `generate_response()` (conversational), `analyze_triage_data()` (structured JSON extraction with severity 1-5), `generate_summary()` (free-text medical summary).

**Key clinical content** (`medgemma_client.py:62-78`) — the system prompt enumerates triage responsibilities:
```
1. Gather information about the patient's symptoms and concerns
2. Ask relevant follow-up questions for triage
3. Assess urgency level (1-5, where 5 is most urgent)
4. Help schedule appointments based on the assessment
5. Be empathetic and professional
```

**What's transferable to chartsearchai:**
- The state-machine pattern is **not** transferable. chartsearchai's workflow is interactive Q&A, not multi-turn data-collection.
- The split into 3 *named LLM call surfaces with distinct prompts* is transferable — it's the same idea as med-agent-hub's "skills", just inside one process. Maps directly to Improvement #1 Shape C.
- The MedGemma-via-Vertex path is **not** transferable; chartsearchai already runs MedGemma locally via LM Link / LM Studio.

### synthetic-data-uploader

Synthea CLI wrapper. Generates synthetic patients in HIV/TB care domains, validates FHIR resources, uploads to OpenMRS via FHIR API. Not load-bearing for the pivot. (The output data shape is what backs the Spark Parquet tables that the clinical agent queries.)

### packages/analytics-ohs-data-pipes

Wraps FHIR Data Pipes (Google's OHS project) — runs the controller pod that crawls OpenMRS FHIR and emits Parquet, with a Spark Thrift server (`ANALYTICS_SPARK_THRIFT_PORT=10001`) for SQL access. `package-metadata.json` declares image `us-docker.pkg.dev/cloud-build-fhir/fhir-analytics/main:latest`. This is the back-end that lights up `SparkPopulationAnalyticsTool` in med-agent-hub.

**Insight for #2:** the *canonical analytics queries* in `spark_tools._build_query` (prevalence / trends / demographics / comorbidities) are basically population-level skills. chartsearchai's per-patient context narrows this dramatically — patient-level skills, not population-level.

---

## 3. Cross-walk to chartsearchai

| Pattern from prior repo | Repo, file | Direct apply? | Why / why not | If modify: how |
|---|---|---|---|---|
| A2A SDK adoption (uvicorn + AgentExecutor) | med-agent-hub `server/sdk_agents/*_server.py` | **No** | chartsearchai is Java/Spring/Hibernate inside an .omod. SDK is Python. Cross-process is wrong default for single-JVM module. | Steal the conceptual contract (agent card + skill list + structured input schemas) but implement in Java, not via the SDK. |
| Agent card JSON shape (`{id, name, description, tags, examples}`) | med-agent-hub `agent_configs/*.yaml` `card.skills[]` | **Yes** | Pure data contract, language-neutral. The `examples[]` array is exactly the seed list for empty-state chips. | Serialize statically into the .omod, expose via `/ws/rest/v1/chartsearchai/skills`. |
| Router semantic routing (LLM classifier) | `router_executor._route_query` | **Modify** | The routing prompt + JSON-only response works. But for chartsearchai there's typically one "agent" (the chart) plus auxiliaries (summarizer, citation-extractor, follow-up-generator). | Move the LLM classification *inside* a Java orchestrator; output a small enum of subagent names. |
| ReAct tool-calling loop | `react_router_executor` | **Modify (smaller form)** | Full ReAct with 5 iterations is overkill for single-shot chart QA. But the structured-output schema with named tool calls is the right primitive. | Use OpenAI tool-calling against the medgemma-1.5-4b model with a fixed shortlist of tools: `extract_meds`, `extract_allergies`, `summarize_encounters`, etc. Cap at 2 hops. |
| MCP tool interface (JSON-Schema-validated `safe_invoke`) | `server/mcp/base.py:MCPTool` | **Modify** | Excellent contract. But the JVM equivalent is much simpler — a Java interface with a Jackson-validated payload. | Define `ChartTool` interface with `name()`, `schema()`, `invoke(JsonNode)`. Already partially present in `LlmInferenceService`. |
| Mixture-of-experts model routing (Llama for class, MedGemma for synth) | `config.py:25-26` + `medical.yaml` model | **Yes** | chartsearchai already runs medgemma-1.5-4b-it (per MT.19). Adding a cheap classifier model is straightforward via LM Link. | Configure two model handles in `LlmProvider`: a classifier (e.g. `llama-3.2-3b`) and a synthesizer (`medgemma-1.5-4b-it`). Route by call site. |
| ReAct orchestration with synthetic-intent gating | `react_router_executor.py:209-217` | **No** | The "multi-intent heuristic" is bespoke + hacky. ReAct in chartsearchai's domain isn't worth the prompt-engineering tax for POC. | Skip. |
| appo-service triage state machine | `conversation_manager.py:21-30` | **No** | chartsearchai isn't a workflow; it's free-text QA. Forcing states would degrade UX. | Skip. |
| Redis session storage with TTL | `session_manager.py` | **No** | chartsearchai already persists multi-turn chat in MySQL via Liquibase (`chat_session`, `chat_message`). | Already done; nothing to import. |
| Two-step LLM-then-tool-then-LLM synthesis | `clinical_executor_v2._execute_skill` lines 247-344 | **Yes (POC)** | This is *the* pattern for improvement #1 Shape C: small LLM call extracts structured params → deterministic tool runs → big LLM synthesizes for the user. Maps cleanly to "extract meds from chart" → "format meds table" → "render". | Implement in Java as `LlmInferenceService.runSkill(skillName, query, chart)`. |
| A2A client/web UI (Svelte chat) | `web/src/App.svelte` | **No** | chartsearchai's frontend is OpenMRS O3 ESM (Carbon Design System); med-agent-hub's web is Pico-CSS Svelte. Different design system, different host. | None — the only borrowable element is the "Answer from: <agent>" label, which becomes "Answered by: <skill>" in chartsearchai. |
| Parquet-on-FHIR analytics skill pattern | `spark_tools.py:_build_query` | **No (for chartsearchai)** | Population queries (`prevalence`, `trends`) are out-of-scope for a per-patient chart panel. | Save for a separate analytics surface — not chartsearchai. |
| Skill discovery via `.well-known/agent-card.json` | `router_executor._discover_agents:60-98` | **Modify** | The HTTP-card-fetching mechanism is wrong for in-JVM. But the data contract — agents publish skills, router enumerates them — is the right model. | Java side: `ChartSearchAiActivator` registers skills into a `SkillRegistry` bean at startup; REST endpoint surfaces them. |

---

## 4. Improvement path #1: Agent-team-based processing

### Feasibility — three shapes

**Shape A — in-process Java orchestrator (sequential composition)**
- chartsearchai gets a new `ChartOrchestratorService` that issues *multiple sequential* LLM calls per user turn against `LlmProvider`. Examples: call 1 = classify intent ("meds question" / "allergies question" / "encounter summary" / "general"); call 2 = generate the focused answer with a skill-specific prompt; call 3 = generate suggested follow-ups.
- Pros: zero new infra, zero new process boundaries, fits the existing `ChatServiceImpl → LlmInferenceService → LlmProvider` chain. Easiest to ship. Already works behind the existing REST API.
- Cons: slowest at runtime (sequential calls); no parallelism; loses the elegance of A2A discoverability.

**Shape B — external Python A2A sidecar (full med-agent-hub adoption)**
- Add a Python A2A service alongside the JVM. The Java module sends queries to the router URL via HTTP. The sidecar runs four uvicorn agents per the existing `Procfile.dev`.
- Pros: inherits med-agent-hub directly. Each agent can use a different model. Future-proof for multi-tenant.
- Cons: heaviest infra. Forces .omod build + Python service ship in lockstep. PHI now crosses a process boundary. LM Link routing complicates. Way too heavy for POC.

**Shape C — LLM tool-calling subagents (recommended)**
- Single LLM call uses **OpenAI-style `tools` + `tool_choice: "auto"`** against the medgemma model, with **named subagents as the tool surface**. The Java orchestrator handles dispatch deterministically when the model emits a tool call. Each "subagent" is a Java function that builds a focused prompt and runs a second LLM call.
- Pros: one network hop (Java→LM Link→LM Studio). Subagents are just Java methods. Model picks which subagents to fire. Falls back to single-shot if no tool selected. Compatible with current model (medgemma-1.5-4b-it supports tool calling).
- Cons: tool-calling quality varies by model; needs eval. Mid-weight; less elegant than Shape A's pure sequential chain.

**Recommendation: Shape C.** It maps the *architectural* win of med-agent-hub (specialized subagents with structured I/O) without paying for the *operational* weight (Python A2A sidecar). It also keeps chartsearchai trivially deployable as a single .omod.

### Shape C data flow

```
┌─────────────────────────────────────────────────────────────────┐
│ ESM frontend: user types query in AI panel                      │
└────────────────────────────┬────────────────────────────────────┘
                             │ POST /ws/rest/v1/chartsearchai/chat
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ ChatResource → ChatServiceImpl.processChatTurn()                │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ ChartOrchestratorService.orchestrate(turn, chartSnapshot)       │
│  ─ builds messages array (existing prefix+tail pattern)         │
│  ─ adds `tools: [...]` with named subagents                     │
│  ─ calls LlmProvider.completeWithTools()                        │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ medgemma decides     │
                  │ tool_calls vs answer │
                  └──┬──────────────────┬┘
                     │                  │
            no tools │                  │ tool_calls
                     │                  ▼
                     │     ┌──────────────────────────────┐
                     │     │ ChartSubagentDispatcher      │
                     │     │  ─ extract_meds(chart)       │
                     │     │  ─ extract_allergies(chart)  │
                     │     │  ─ summarize_encounters(...) │
                     │     │  ─ propose_followups(answer) │
                     │     └────────┬─────────────────────┘
                     │              │ structured results
                     │              ▼
                     │     ┌──────────────────────────────┐
                     │     │ Synthesis LLM call           │
                     │     │  (medgemma w/ structured     │
                     │     │   output schema)             │
                     │     └──────────────┬───────────────┘
                     │                    │
                     ▼                    ▼
              ┌──────────────────────────────────┐
              │ Envelope:                        │
              │  {answer, citations[],           │
              │   key_findings[],                │
              │   suggested_followups[],         │
              │   confidence}                    │
              └──────────────────────────────────┘
```

### Code changes (POC)

| File | Change |
|---|---|
| `api/src/main/java/.../impl/LlmProvider.java` | Add `completeWithTools(messages, tools)` overload. Existing single-shot path remains as fallback. |
| `api/src/main/java/.../impl/LlmInferenceService.java` | Currently does one call. Add a `runSubagent(name, prompt, chart)` method that wraps a focused LLM call with skill-specific system prompt. |
| `api/src/main/java/.../impl/ChartOrchestratorService.java` (new) | Coordinator. Calls `LlmProvider.completeWithTools`, dispatches tool calls into `runSubagent`, runs final synthesis. |
| `api/src/main/java/.../impl/ChartSubagentDispatcher.java` (new) | Maps tool name → Java method. Four methods to start: `extractMeds`, `extractAllergies`, `summarizeRecentEncounters`, `proposeFollowups`. |
| `api/src/main/java/.../api/impl/ChatServiceImpl.java` | Swap the call from `LlmInferenceService.completeChat()` to `ChartOrchestratorService.orchestrate()`. |
| `api/src/main/java/.../impl/ChartAnswerResponseFormat.java` | Extend JSON schema with `key_findings`, `suggested_followups`, `confidence`. |

The new files don't touch existing tests; `ChatMessagesFromTurnsTest` and `MessagesArrayShapeTest` still apply. New tests: `ChartSubagentDispatcherTest` (each subagent in isolation), `ChartOrchestratorServiceTest` (full flow with mocked `LlmProvider`).

---

## 5. Improvement path #2: Context-suggested / standard queries / skills (POC)

### Phase 1 — static seeded skills

The **A2A agent-card JSON skill shape** is the contract. From `medical.yaml`:

```yaml
skills:
  - id: "answer_medical_question"
    name: "Answer Medical Questions"
    description: "Provide evidence-based answers to general medical questions"
    tags: ["medical", "health", "q&a"]
    examples:
      - "What are the symptoms of diabetes?"
      - "Explain how vaccines work"
```

For chartsearchai, declare 6–10 patient-context skills:

```yaml
skills:
  - id: "list_active_meds"
    name: "List Active Medications"
    examples: ["What meds is this patient on?", "Show current prescriptions"]
  - id: "drug_allergies"
    examples: ["Any drug allergies?", "Allergy list"]
  - id: "recent_encounters"
    examples: ["Summarize the last 30 days", "Recent visits"]
  - id: "lab_trends"
    examples: ["Trend HbA1c", "Show recent lab values"]
  - id: "problem_list"
    examples: ["Active conditions", "What is this patient being treated for?"]
  - id: "vital_trends"
    examples: ["Recent vitals", "BP trend"]
```

Surface as REST: `GET /ws/rest/v1/chartsearchai/skills` returns the list. ESM frontend fetches once per panel open.

### Phase 2 — two UI surfaces

1. **Empty-state chips** in `ai-search-panel.component.tsx` — when no messages, render the `examples` from each skill as Carbon `Tag` components (clickable). Click → prefill input + submit.
2. **"Continue with..." chips** under each assistant response — render `response.suggested_followups[]` (from the extended envelope) as the same chip component. Click → submit as new turn.

### Phase 3 — dynamic suggestions

Three sources, in order of POC effort:

1. **LLM-generated, inside structured output**: the synthesis schema gets `suggested_followups: string[]` (3-5 items). The medgemma call already runs; cost is a slightly longer output. **Best ROI for POC.**
2. **Heuristic**: if chart contains an Observation of HbA1c → inject "Trend HbA1c over time" as a chip. Java-side: scan the chart snapshot for resource types, look up matching skills via a tag map. Mid-weight.
3. **Skill-discovery from a sidecar** (Shape B from #4): only when Shape B exists. Skip for POC.

### Mapping to med-agent-hub's mechanism

med-agent-hub does this via `_discover_agents()` HTTP-fetching `/.well-known/agent-card.json`. chartsearchai short-circuits the discovery: skills are statically packaged with the .omod, served from a single REST endpoint, exposed to the frontend on panel mount. Same data model; collapsed transport.

---

## 6. Improvement path #3: Presentation-side improvements (POC)

The most under-developed pillar today.

### Renderer pluralism

Current state: `ai-chat-content.component.tsx` renders the answer as a single text blob, citation pills `[1]` open a side panel listing source records. Extend the envelope:

```ts
type ChartSearchAiResponse = {
  answer: string;
  citations: number[];
  key_findings?: { label: string; value: string; citation?: number }[];
  suggested_followups?: string[];
  confidence?: 'high' | 'medium' | 'low' | 'cannot_answer';
};
```

Renderer dispatches each block to a Carbon primitive:

| Envelope field | Carbon component | Lives in |
|---|---|---|
| `answer` | existing markdown renderer | `ai-chat-content.component.tsx` |
| `key_findings[]` | `StructuredListWrapper` with `StructuredListCell` per row | new `key-findings.component.tsx` |
| `citations[]` | existing pill row + side panel | `ai-response-panel.component.tsx` |
| `suggested_followups[]` | row of `Tag` (clickable) | new `followup-chips.component.tsx` |
| `confidence` | `InlineNotification` (success/info/warning/error) | inline in chat content |

For medication lists or labs (when a subagent like `extract_meds` runs), add a `medications[]` block in the envelope and a small `<DataTable>` renderer.

### Evidence cards (Scout pattern)

Current citation pill opens a side panel listing the record IDs. Extend to render *evidence cards* per the Scout analysis already in `specs/artifacts/canvases/scout-comparative-analysis.canvas.tsx`:

- Card header: resource type + date (e.g. "Observation · 2024-09-12")
- Card body: human-readable content (concept name + value + units for Observation; med name + dose for MedicationRequest)
- Card footer: small "Open in chart" affordance

Lives in `ai-response-panel.component.tsx`. The data is already retrieved by the existing record-index → record-uuid table; this is a pure-frontend rendering change.

### Confidence + abstain

Add `confidence` to the schema (`ChartAnswerResponseFormat.java`). Prompt the model to set `cannot_answer` when nothing in the chart answers the question. ESM renders:

- `cannot_answer` → red `InlineNotification` above the answer, with a copy of the user's question and a single "Re-ask with more context" affordance.
- `low` → orange caution.
- `high`/`medium` → no banner.

### Visual primitives shopping list (Carbon, already available in O3)

- `Tag` — skill chips, followup chips
- `StructuredListWrapper` / `StructuredListCell` — key findings
- `DataTable` — meds list, labs list
- `InlineNotification` — confidence / abstain
- `Tile` — evidence card body
- `SparklineChart` (`@carbon/charts-react`) — lab trend mini-chart (the only new dep)

### Where each change lands

| Change | File(s) |
|---|---|
| Schema extension | `targets/chartsearchai/api/.../ChartAnswerResponseFormat.java` + ESM `src/types.ts` |
| Envelope parsing | `targets/chartsearchai-esm/src/api/chartsearchai.ts` |
| Block renderer dispatch | `targets/chartsearchai-esm/src/components/ai-chat-content.component.tsx` |
| Key-findings | new `key-findings.component.tsx` |
| Followup chips | new `followup-chips.component.tsx` |
| Evidence cards | extend `ai-response-panel.component.tsx` |
| Confidence banner | inline in `ai-chat-content.component.tsx` |

---

## 7. Sequencing recommendation

A 3-week / 3-milestone POC arc, interleaving the three improvements so each milestone produces something demoable end-to-end.

### M1 (Week 1) — Envelope extension + static skills + chip surfaces

**Backend**:
- Extend `ChartAnswerResponseFormat` schema with `key_findings`, `suggested_followups`, `confidence`. Update `LlmProvider` system prompt to require them.
- Add `GET /ws/rest/v1/chartsearchai/skills` returning a static seeded list (6 skills, with `examples[]`).

**Frontend**:
- Fetch skills on panel mount.
- Render empty-state chips from `skill.examples[]`.
- Render followup chips from `response.suggested_followups[]`.
- Render `InlineNotification` for `confidence: cannot_answer`.

**Outcome demoable**: clinician opens panel, sees 6 clickable chips; types or clicks; gets answer + 3 followup chips + (sometimes) abstain banner.

### M2 (Week 2) — Subagent orchestration (Shape C)

**Backend**:
- New `ChartOrchestratorService` + `ChartSubagentDispatcher` (two subagents: `extract_meds`, `extract_allergies`).
- `LlmProvider.completeWithTools()` overload.
- `ChatServiceImpl` swaps in the new orchestrator behind a feature flag (`chartsearchai.orchestrator.mode = legacy | subagent`).

**Frontend**:
- Renderer for `medications[]` block (Carbon `DataTable`).
- Renderer for `allergies[]` block (Carbon `Tag` row).

**Outcome demoable**: "What meds is this patient on?" returns a structured table instead of free text. "Any allergies?" returns chips. Legacy mode still works behind the flag.

### M3 (Week 3) — Evidence cards + rubric eval

**Backend**:
- Add 2 more subagents: `summarize_encounters`, `propose_followups` (which replaces the inline schema field on the orchestrator path).

**Frontend**:
- Evidence cards in `ai-response-panel`: each citation pill expands to a Carbon `Tile` with resource-type header, date, and human-readable body.
- Optional: lab sparkline for HbA1c when `lab_trends` skill fires.

**Eval**:
- Run the same OpenMRS 18-question set used during multi-turn work against both `legacy` and `subagent` modes.
- Score on the existing or a chartsearchai-native rubric (see Q3 in §8).
- Capture latency, token counts, citation accuracy.

**Outcome**: side-by-side eval shows whether Shape C is worth the complexity for the canonical question set.

---

## 8. Open questions for the user (max 6)

1. **Shape choice**: Confirm Shape C (Java in-JVM tool-calling subagents) over Shape A (sequential composition) or Shape B (Python A2A sidecar)? Shape C is recommended but locks in tool-calling support on the model side, which may bias model selection.
2. **Tool-calling on medgemma**: medgemma-1.5-4b-it claims tool-calling support; have you confirmed this works through LM Studio + LM Link, or should the POC default to a Llama-3.2-3B classifier for the routing step and reserve medgemma for synthesis?
3. **Eval rubric**: Run POC against the 11-pt Scout rubric (from the existing canvas analysis), or define a chartsearchai-native rubric first? The Scout rubric has the advantage of comparability; a native rubric better captures structured-output quality.
4. **Charting library**: Carbon-only renderers, or introduce `@carbon/charts-react` (an extra dep) for the lab sparkline? Carbon-only is lighter; charts unlock a real "lab trend over time" affordance.
5. **Skill source-of-truth**: Should the static skill list live in the Java module (compiled into the .omod) or in the ESM frontend (TypeScript constant)? Java-side is more A2A-faithful and lets the backend gate skills by chart contents; frontend-side is simpler for POC.
6. **Cloud-vs-local LM target**: continue running the orchestrator + synthesis against the same cloud-LM-Link → LM Studio path, or split (classifier local-embedded llama-server fallback, synthesis cloud)? Affects M2 latency budget.

---

## Bottom line

The two prior repos provide a clear blueprint — agent cards + skill JSON, mixture-of-experts, structured-output schemas, two-step extract-then-synthesize — but the *transport* (A2A SDK, multi-uvicorn, Redis state machine) is wrong for chartsearchai's single-JVM .omod posture. **The POC pitch is to import the data contracts, not the topology.**
