# Configuring system prompts and model settings

This guide is the single reference for changing **system prompts** and **model / endpoint
settings** for the two AI surfaces in this harness:

- **(A) Med Agent Hub** — the in-process "Med Agent Team" (ReAct orchestrator + medgemma
  expert + synthesizer). Python, runs in the `med-agent-hub` Docker container.
- **(B) chartsearchai direct** — the OpenMRS `chartsearchai` module that calls an LLM
  directly. Java/`.omod`, configured through OpenMRS global properties.

For every knob you get: **what it controls**, **where it lives** (`file:line` / env var /
global property), **how to change it**, and **how to apply it** (rebuild / restart /
configure) as concrete numbered steps. A [Common tasks](#common-tasks-cheat-sheet)
cheat-sheet at the end maps each frequent change to its exact steps.

> **Two mental models, one per surface.**
> Med Agent Hub knobs are either **Python constants** (need an image rebuild) or
> **environment variables** (set on the host, read by compose, no rebuild).
> chartsearchai knobs are either **Java code constants** (need an `.omod` rebuild) or
> **OpenMRS global properties** (set at runtime via REST/DB, no rebuild) — and for the
> endpoint/model there is additionally a **per-request override** that changes nothing
> globally.

---

## How Med Agent Hub config is wired (read this first)

The container reads **container-side** env names: `LLM_BASE_URL`, `ORCHESTRATOR_MODEL`,
`MED_MODEL`, `LLM_TEMPERATURE` (`targets/med-agent-hub/server/config.py`).

Compose does **not** pass those names through directly. `compose/openmrs-2.8-refapp.yml`
lines 185-188 set each container key from a **host-side** `MED_AGENT_*` name with a default:

```yaml
LLM_BASE_URL:       ${MED_AGENT_LLM_BASE_URL:-http://host.docker.internal:1234}
ORCHESTRATOR_MODEL: ${MED_AGENT_ORCHESTRATOR_MODEL:-google/gemma-4-e4b}
MED_MODEL:          ${MED_AGENT_MED_MODEL:-medgemma-1.5-4b-it}
LLM_TEMPERATURE:    ${MED_AGENT_TEMPERATURE:-0.0}
```

Consequences you must respect:

1. **The host-side knob is `MED_AGENT_*`, not the bare container name.** `export
   ORCHESTRATOR_MODEL=...` does nothing — compose never reads `${ORCHESTRATOR_MODEL}`.
   Use `export MED_AGENT_ORCHESTRATOR_MODEL=...`.
2. **`make med-agent-hub-up` passes no `--env-file`.** Compose auto-loads only the repo-root
   `.env` (which holds unrelated keys). `.env.med-agent-hub` is **not** auto-loaded — you must
   **source** it into your shell so the `MED_AGENT_*` vars are exported before `make`:
   `set -a; . .env.med-agent-hub; set +a`. (See `.env.med-agent-hub.example`, which documents
   exactly this.)
3. **Effective vs. code default for temperature.** The Python fallback is `0.2`
   (`config.py:34`) but it only applies when `LLM_TEMPERATURE` is unset — and compose
   **always** sets it, defaulting to `0.0` (compose:188). So the running default is **0.0**.

The two make targets:

```
make med-agent-hub-build   # docker compose -f compose/openmrs-2.8-refapp.yml build med-agent-hub
make med-agent-hub-up      # docker compose -f compose/openmrs-2.8-refapp.yml up -d med-agent-hub
```

Rule of thumb: **env-var knob → just `up`. Python-constant knob → `build` then `up`.**

---

# (A) Med Agent Hub — system prompts and model/endpoint settings

All paths below are relative to the repo root
(`/Users/pmanko/code/clinical-ai-validation-harness`).

## A.1 System prompts (Python constants — rebuild required)

There is **no** env override for any team prompt; they are multi-line string constants in
`targets/med-agent-hub/server/team.py`. Editing any of them requires
`med-agent-hub-build` then `med-agent-hub-up`.

### A.1.1 Orchestrator prompt — `ORCHESTRATOR_SYSTEM`
- **Controls:** the ReAct loop's behavior — when to call tools vs. stop, and the default
  `kb_search → medical_expert → stop` flow. Key phrases: `DEFAULT pattern:`, `SKIP the tools
  only when:`, and the worked example (team.py:67-80).
- **Where:** `targets/med-agent-hub/server/team.py:44-83` (string after `ORCHESTRATOR_SYSTEM = (`).
- **Change + apply:**
  1. Edit `team.py` lines 44-83.
  2. `make med-agent-hub-build`
  3. `make med-agent-hub-up`

### A.1.2 Clinical-expert prompt — `MEDICAL_EXPERT_SYSTEM`
- **Controls:** how the `medical_expert` tool reasons over the chart + KB snippets, and how
  it cites sources in prose ("State only what the chart supports…", "name its source").
- **Where:** `targets/med-agent-hub/server/team.py:87-100`.
- **Change + apply:**
  1. Edit `team.py` lines 87-100.
  2. `make med-agent-hub-build`
  3. `make med-agent-hub-up`

### A.1.3 Synthesis prompt — `SYNTHESIS_INSTRUCTION`
- **Controls:** final-answer assembly and the citation contract — integer `citations` are
  **chart record indices only**; KB/expert facts are attributed inline in prose with no
  integer. Also the `{answer, citations, blocks}` envelope and the `table`-block rule.
- **Where:** `targets/med-agent-hub/server/team.py:104-132`.
- **Change + apply:**
  1. Edit `team.py` lines 104-132.
  2. `make med-agent-hub-build`
  3. `make med-agent-hub-up`

## A.2 Tool descriptions — the KB flow (Python constants — rebuild required)

The orchestrator decides *whether and in what order* to call tools largely from the tool
**descriptions**. These are the lever for changing the KB-then-expert flow without touching
the prompt prose. Do **not** rename the functions or change their parameters.

### A.2.1 `kb_search` tool description
- **Controls:** the trigger keywords/examples that make the orchestrator call `kb_search`
  FIRST (guideline, drug/dose, threshold, danger sign, schedule, reference range, "is this
  current/recommended").
- **Where:** `targets/med-agent-hub/server/team.py:146-158` (`description` field in
  `_tool_definitions`).
- **Change + apply:** edit the description string → `make med-agent-hub-build` → `make
  med-agent-hub-up`.

### A.2.2 `medical_expert` tool description
- **Controls:** when the orchestrator calls `medical_expert` (AFTER `kb_search`) and the note
  that the expert auto-receives the KB snippets.
- **Where:** `targets/med-agent-hub/server/team.py:175-185` (`description` field).
- **Change + apply:** edit the description string → `make med-agent-hub-build` → `make
  med-agent-hub-up`.

### A.2.3 Loop length — `MAX_TOOL_ITERATIONS`
- **Controls:** max tool-calling iterations per turn (default `3`). Raise for longer chains,
  lower to cut small-model drift.
- **Where:** `targets/med-agent-hub/server/team.py:39`.
- **Change + apply:** edit the integer → `make med-agent-hub-build` → `make med-agent-hub-up`.

## A.3 Model selection (env var — no rebuild)

Set the **host-side** `MED_AGENT_*` var, then `make med-agent-hub-up`. No image rebuild —
the container reads the env at startup.

### A.3.1 Orchestrator + synthesizer model — `MED_AGENT_ORCHESTRATOR_MODEL`
- **Controls:** the model for the orchestrator loop **and** the final synthesis (one model,
  dual role). Container reads `ORCHESTRATOR_MODEL` (`config.py:26`, default `google/gemma-4-e4b`).
- **Where:** host var `MED_AGENT_ORCHESTRATOR_MODEL` → compose:186 → container `ORCHESTRATOR_MODEL`.
- **Change + apply (pick one):**
  - Quick, per-shell:
    1. `export MED_AGENT_ORCHESTRATOR_MODEL='llama-3.1-8b'`
    2. `make med-agent-hub-up`
  - Persistent via env file:
    1. Set `MED_AGENT_ORCHESTRATOR_MODEL=llama-3.1-8b` in `.env.med-agent-hub`
       (copy from `.env.med-agent-hub.example` first if absent).
    2. `set -a; . .env.med-agent-hub; set +a`
    3. `make med-agent-hub-up`
- **Note:** use the official `google/` gemma-4 build — some community GGUFs ship a broken
  jinja tool template that 400s on tool-calling (`config.py:22-24`).

### A.3.2 Medical-expert model — `MED_AGENT_MED_MODEL`
- **Controls:** the model behind the `medical_expert` tool. Container reads `MED_MODEL`
  (`config.py:27`, default `medgemma-1.5-4b-it`).
- **Where:** host var `MED_AGENT_MED_MODEL` → compose:187 → container `MED_MODEL`.
- **Change + apply:** same two options as A.3.1, substituting `MED_AGENT_MED_MODEL`.

## A.4 Endpoint and decoding settings

### A.4.1 LLM endpoint — `MED_AGENT_LLM_BASE_URL` (env var — no rebuild)
- **Controls:** the OpenAI-compatible base URL the team calls (LM Studio or any compat
  server). Container reads `LLM_BASE_URL` (`config.py:19`, default `http://localhost:1234`;
  compose default `http://host.docker.internal:1234`).
- **Change + apply:**
  1. `export MED_AGENT_LLM_BASE_URL='http://192.168.1.100:1234'` (or set in
     `.env.med-agent-hub` and source it).
  2. `make med-agent-hub-up`

### A.4.2 Global temperature (orchestrator + synthesis) — `MED_AGENT_TEMPERATURE` (env var)
- **Controls:** decoding temperature for the orchestrator loop and synthesis. Container reads
  `LLM_TEMPERATURE` (`config.py:34`, code fallback `0.2`); **effective default `0.0`** because
  compose:188 always sets it.
- **Change + apply:**
  1. `export MED_AGENT_TEMPERATURE='0.3'` (or set in `.env.med-agent-hub` and source it).
  2. `make med-agent-hub-up`

### A.4.3 Medical-expert temperature (Python constant — rebuild required)
- **Controls:** temperature for the `medical_expert` tool call only — hardcoded `0.1`,
  **independent** of `LLM_TEMPERATURE`. There is no env override.
- **Where:** `targets/med-agent-hub/server/team.py:276` (`temperature=0.1` in the `_chat`
  call). To inherit the global temperature instead, change it to `temperature=temperature`.
- **Change + apply:**
  1. Edit `team.py:276`.
  2. `make med-agent-hub-build`
  3. `make med-agent-hub-up`

### A.4.4 API key — `LLM_API_KEY` (no host passthrough; rebuild or compose edit)
- **Controls:** optional Bearer token for the LLM endpoint. Container default empty
  (`config.py:20`). **There is no `MED_AGENT_*` passthrough in compose** (only base-url,
  models, temperature are wired at compose:185-188).
- **Change + apply (pick one):**
  - Add a compose passthrough: add `LLM_API_KEY: ${MED_AGENT_LLM_API_KEY:-}` to the
    `med-agent-hub` `environment:` block (compose ~185-188), then
    `export MED_AGENT_LLM_API_KEY=...` and `make med-agent-hub-up`.
  - Or change the code default at `config.py:20`, then `make med-agent-hub-build` and
    `make med-agent-hub-up`.

---

# (B) chartsearchai direct — system prompts and model/endpoint settings

All paths below are under `targets/chartsearchai/`. The decisive distinction:

| Kind | Lives in | Change mechanism | Apply |
|------|----------|------------------|-------|
| **Code constant** (built-in system prompt) | Java (`LlmProvider.java`) | edit source | rebuild `.omod` + redeploy |
| **Global property** (engine, endpoint, model, prompt override, limits) | OpenMRS DB, defined in `config.xml` | REST / `chartsearch-configure.sh` / DB | runtime (some need restart) |
| **Per-request override** (endpoint + model) | thread-local, set from the chat request body | one chat POST | that single request only |

Resolution order for endpoint + model: `RemoteLlmEngine.resolveEndpointUrl()` /
`resolveModelName()` (RemoteLlmEngine.java:213-224) check the **per-request override first**,
then fall back to the **global property**.

## B.1 System prompt — code default vs. global-property override

The built-in prompt is a **Java code constant**. A non-empty global property **overrides**
it at request time; clear the property to fall back to the built-in
(`LlmProvider.getSystemPrompt()`, LlmProvider.java:518-525).

### B.1.1 Built-in default — `DEFAULT_SYSTEM_PROMPT` (code constant — rebuild required)
- **Controls:** the prompt used when the override GP is empty/unset (the default, and what the
  eval suite tests against).
- **Where:** `targets/chartsearchai/api/.../api/impl/LlmProvider.java:41` (`DEFAULT_SYSTEM_PROMPT`).
  It is **not** in `config.xml` — it cannot be changed without a rebuild.
- **Change + apply:**
  1. Edit `LlmProvider.java:41` (the constant).
  2. `make chartsearch-build` (runs `mvn -DskipTests -B package` and copies the fresh
     `.omod` to `artifacts/openmrs/modules/`).
  3. Redeploy the backend so OpenMRS loads the new `.omod` (restart the backend container so
     the module is reloaded).

### B.1.2 Custom override — `chartsearchai.llm.systemPrompt` (global property — runtime)
- **Controls:** replaces the built-in prompt for this deployment. Any non-empty value wins;
  an empty value (or deleted row) reverts to the built-in.
- **Where:** GP `chartsearchai.llm.systemPrompt`
  (`config.xml:83`, default empty; constant `ChartSearchAiConstants.java:286`); read by
  `LlmProvider.getSystemPrompt()`.
- **Change + apply (runtime, no restart):**
  1. `POST /ws/rest/v1/systemsetting/chartsearchai.llm.systemPrompt` with body
     `{"value": "your prompt"}` (admin auth), **or** set the row directly in the
     `global_property` table.
  2. Takes effect on the **next LLM call** — `getSystemPrompt()` reads the GP per request.
  3. To revert: set the value back to empty (or delete the row).
- **Note:** `chartsearch-configure.sh` does **not** set this GP — use REST or DB.

## B.2 Engine, endpoint, model — the config-controlled global defaults

These are the persistent defaults stored in the OpenMRS DB. The harness runs **remote**
(`.env.chartsearch:48` `CHARTSEARCH_LLM_ENGINE=remote`).

### B.2.1 Engine (local vs. remote) — `chartsearchai.llm.engine` (restart required)
- **Controls:** whether chartsearchai runs a bundled local `llama-server` (`local`) or calls
  an OpenAI-compatible API (`remote`). Default `local` in `config.xml`.
- **Where:** GP `chartsearchai.llm.engine` (`config.xml:47`; constant
  `ChartSearchAiConstants.java:264`).
- **Change + apply:**
  1. Set it via `POST /ws/rest/v1/systemsetting/chartsearchai.llm.engine` body
     `{"value": "remote"}` (or `"local"`), **or** `make chartsearch-configure` (reads
     `CHARTSEARCH_LLM_ENGINE` from `.env.chartsearch`), **or** DB.
  2. **Restart the backend** — the activator (`ChartSearchAiModuleActivator`) wires the
     `LocalLlmEngine` / `RemoteLlmEngine` bean at startup from this GP.

### B.2.2 Remote endpoint URL — `chartsearchai.llm.remote.endpointUrl` (runtime)
- **Controls:** the OpenAI-compatible chat-completions URL for the remote engine.
- **Where:** GP `chartsearchai.llm.remote.endpointUrl` (`config.xml:53`; constant
  `ChartSearchAiConstants.java:270`); read by `RemoteLlmEngine.resolveEndpointUrl()`
  (RemoteLlmEngine.java:213-217).
- **Change + apply (runtime, no restart — per-request override checked first):**
  1. `POST /ws/rest/v1/systemsetting/chartsearchai.llm.remote.endpointUrl` body
     `{"value": "http://host:port/v1/chat/completions"}`, **or**
     `make chartsearch-configure` (reads `CHARTSEARCH_REMOTE_ENDPOINT_URL`; idempotent), **or**
     the convenience endpoint in B.4.2, **or** DB.
  2. Effective on the **next LLM call**.

### B.2.3 Remote model name — `chartsearchai.llm.remote.modelName` (runtime)
- **Controls:** the model id sent to the remote endpoint.
- **Where:** GP `chartsearchai.llm.remote.modelName` (`config.xml:59`; constant
  `ChartSearchAiConstants.java:274`); read by `RemoteLlmEngine.resolveModelName()`
  (RemoteLlmEngine.java:220-224).
- **Change + apply (runtime, no restart):**
  1. `POST /ws/rest/v1/systemsetting/chartsearchai.llm.remote.modelName` body
     `{"value": "model-id"}`, **or** `make chartsearch-configure` (reads
     `CHARTSEARCH_REMOTE_MODEL_NAME`; auto-discovers from `/v1/models` if empty), **or** the
     convenience endpoint in B.4.2, **or** DB.
  2. Effective on the **next LLM call**.

### B.2.4 Endpoint registry (picker dropdown) — `chartsearchai.llm.remote.endpoints` (runtime)
- **Controls:** the JSON array of `{label, url}` entries the frontend picker shows. When
  empty, the picker falls back to a single section built from the current `endpointUrl`.
- **Where:** GP `chartsearchai.llm.remote.endpoints` (constant
  `ChartSearchAiConstants.java:284`; example in `.env.chartsearch:39`).
- **Change + apply (runtime, next page load):**
  1. `POST /ws/rest/v1/systemsetting/chartsearchai.llm.remote.endpoints` body
     `{"value": "[{\"label\":\"LM Studio\",\"url\":\"...\"}]"}`, **or**
     `make chartsearch-configure` (reads `CHARTSEARCH_REMOTE_ENDPOINTS`), **or** DB.

## B.3 Per-request endpoint/model override (changes nothing globally)

- **Controls:** pins a specific endpoint + model for **one chat request only**. The
  config-controlled global default is untouched — useful for A/B testing backends or letting
  one session pin a model without affecting other users.
- **Where:** the chat controller reads `endpointUrl` + `modelName` from the request body,
  validates both against the registry, sets a thread-local `RequestLlmOverride`, runs the
  chat, and **clears it in `finally`** (`ChartSearchAiRestController.java:1043-1080`). The
  resolvers check this override before the global (RemoteLlmEngine.java:213-224).
- **Change + apply (request-scoped, no DB/global change):**
  1. `POST /ws/rest/v1/chartsearchai/chat` with body
     `{"patient": "<uuid>", "question": "...", "endpointUrl": "http://...",
     "modelName": "model-id"}`.
  2. Both fields must be present and valid against the endpoint registry, or the request is
     rejected (`400`). The override applies to that response only and is cleared immediately
     after.

## B.4 REST convenience: switch the global default in one call

### B.4.1 Set endpoint + model together — `POST /ws/rest/v1/chartsearchai/endpoint`
- **Controls:** atomically updates **both** global defaults (endpoint URL + model name).
- **Where:** `setEndpoint()` (`ChartSearchAiRestController.java:485-506`); validates against
  the registry, then `modelSwitchService.setEndpointAndModel(url, model)` writes both GPs.
- **Change + apply (runtime, updates the DB globals immediately):**
  1. `POST /ws/rest/v1/chartsearchai/endpoint` body
     `{"endpointUrl": "http://...", "modelName": "model-id"}`.
  2. All subsequent requests use the new endpoint + model unless overridden per-request.

## B.5 Limits and local-engine settings (global properties)

### B.5.1 Rate limit — `chartsearchai.rateLimitPerMinute` (runtime)
- **Controls:** max AI queries per user per minute. Default `10`; `0` disables.
- **Where:** GP `chartsearchai.rateLimitPerMinute` (`config.xml:113`, default `10`; constant
  `ChartSearchAiConstants.java:306`); read by the REST controller's `checkRateLimit()`.
- **Change + apply (runtime):** `POST /ws/rest/v1/systemsetting/chartsearchai.rateLimitPerMinute`
  body `{"value": "30"}` (or DB). Effective on the next request.

### B.5.2 LLM timeout — `chartsearchai.llm.timeoutSeconds` (runtime)
- **Controls:** seconds to wait for an LLM response. Default `300`.
- **Where:** GP (`config.xml:89`, default `300`; constant `ChartSearchAiConstants.java:288`);
  read by `LlmProvider.getTimeoutSeconds()`.
- **Change + apply (runtime):** set the GP via REST or DB; effective on the next LLM call.

### B.5.3 Local context size — `chartsearchai.llm.contextSize` (restart required, local only)
- **Controls:** llama-server context window in tokens. Default `32768`. Only when
  `engine = local`.
- **Where:** GP (`config.xml:107`; constant `ChartSearchAiConstants.java:300`).
- **Change + apply:** set the GP, then **restart the local `llama-server`** (read at subprocess
  start).

### B.5.4 Local server port — `chartsearchai.llm.serverPort` (restart required, local only)
- **Controls:** the embedded llama-server port. Default `18085`. Only when `engine = local`.
- **Where:** GP (`config.xml:101`; constant `ChartSearchAiConstants.java:296`).
- **Change + apply:** set the GP, then **restart** the local engine subprocess.

---

## Common tasks cheat-sheet

Each row = a frequent change → the exact steps. `→` separates ordered steps.

| Task | Steps |
|------|-------|
| **Change the team orchestrator/synthesizer model** | Set host var `MED_AGENT_ORCHESTRATOR_MODEL=<model>` (export, or set in `.env.med-agent-hub` then `set -a; . .env.med-agent-hub; set +a`) → `make med-agent-hub-up`. No rebuild. |
| **Change the team medical-expert model** | Set host var `MED_AGENT_MED_MODEL=<model>` (export or `.env.med-agent-hub` + source) → `make med-agent-hub-up`. No rebuild. |
| **Edit the team orchestrator system prompt** | Edit `targets/med-agent-hub/server/team.py:44-83` (`ORCHESTRATOR_SYSTEM`) → `make med-agent-hub-build` → `make med-agent-hub-up`. |
| **Edit the team clinical (expert) system prompt** | Edit `team.py:87-100` (`MEDICAL_EXPERT_SYSTEM`) → `make med-agent-hub-build` → `make med-agent-hub-up`. |
| **Edit the team synthesis system prompt** | Edit `team.py:104-132` (`SYNTHESIS_INSTRUCTION`) → `make med-agent-hub-build` → `make med-agent-hub-up`. |
| **Change the team's KB flow (when/whether kb_search runs)** | Edit the `kb_search` description `team.py:146-158` and/or `medical_expert` description `team.py:175-185` (keep names/params); optionally adjust `ORCHESTRATOR_SYSTEM` (44-83) and `MAX_TOOL_ITERATIONS` (`team.py:39`) → `make med-agent-hub-build` → `make med-agent-hub-up`. |
| **Point chartsearchai at a different model for ONE request** | `POST /ws/rest/v1/chartsearchai/chat` body `{"patient":"<uuid>","question":"...","endpointUrl":"http://...","modelName":"<id>"}`. Both must validate against the registry. Affects that response only; global default unchanged. |
| **Change chartsearchai's config-default model/endpoint** | `POST /ws/rest/v1/chartsearchai/endpoint` body `{"endpointUrl":"http://...","modelName":"<id>"}` (sets both GPs at once) — OR set `CHARTSEARCH_REMOTE_ENDPOINT_URL` / `CHARTSEARCH_REMOTE_MODEL_NAME` in `.env.chartsearch` → `make chartsearch-configure`. Runtime, next call. |
| **Change chartsearchai's system prompt (override)** | `POST /ws/rest/v1/systemsetting/chartsearchai.llm.systemPrompt` body `{"value":"<prompt>"}`. Runtime, next call. Empty value reverts to built-in. |
| **Change chartsearchai's BUILT-IN system prompt** | Edit `LlmProvider.java:41` (`DEFAULT_SYSTEM_PROMPT`) → `make chartsearch-build` → redeploy/restart the backend so OpenMRS loads the new `.omod`. |
| **Change chartsearchai's rate limit** | `POST /ws/rest/v1/systemsetting/chartsearchai.rateLimitPerMinute` body `{"value":"<N>"}` (`0` disables). Runtime, next request. |
| **Switch chartsearchai local↔remote engine** | Set `chartsearchai.llm.engine` to `local`/`remote` (REST `POST /ws/rest/v1/systemsetting/chartsearchai.llm.engine`, or `CHARTSEARCH_LLM_ENGINE` in `.env.chartsearch` + `make chartsearch-configure`) → **restart the backend** (activator re-wires the engine bean). |

### Reference: file and property index

- Med Agent Hub prompts/tools/loop: `targets/med-agent-hub/server/team.py`
  (39, 44-83, 87-100, 104-132, 146-158, 175-185, 276).
- Med Agent Hub config defaults: `targets/med-agent-hub/server/config.py` (19, 20, 26, 27, 34).
- Med Agent Hub compose wiring: `compose/openmrs-2.8-refapp.yml:185-188`; host env template
  `.env.med-agent-hub.example`; make targets `med-agent-hub-build` / `med-agent-hub-up`.
- chartsearchai constants: `targets/chartsearchai/api/.../ChartSearchAiConstants.java`
  (264, 270, 274, 284, 286, 288, 296, 300, 306).
- chartsearchai GP defaults: `targets/chartsearchai/omod/src/main/resources/config.xml`
  (47, 53, 59, 83, 89, 101, 107, 113).
- chartsearchai resolution/override logic: `RemoteLlmEngine.java` (213-224),
  `LlmProvider.java` (41, 518-525), `ChartSearchAiRestController.java` (485-506, 1043-1080).
- chartsearchai configure script: `scripts/chartsearch-configure.sh`
  (reads `CHARTSEARCH_*`, POSTs to `/ws/rest/v1/systemsetting/<name>`); build: `make chartsearch-build`.
