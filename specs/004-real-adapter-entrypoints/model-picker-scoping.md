# Live model picker — scoping

**Status**: design / proposal (2026-05-18). Not yet implemented.

## Goal

Give the user a simple way to switch the LLM model that chartsearchai's chat path uses, without editing a global property by hand or restarting the backend. The first version targets LM Studio (where a developer commonly has multiple models downloaded and wants to A/B them), but the same mechanism works for any OpenAI-compat endpoint that exposes `/v1/models`.

## What we have today

Two global properties drive the remote-engine path:

| GP | Today | Role |
|---|---|---|
| `chartsearchai.llm.engine` | `remote` | Picks `RemoteLlmEngine` vs `LocalLlmEngine` |
| `chartsearchai.llm.remote.endpointUrl` | `http://host.docker.internal:1234/v1/chat/completions` | Where to POST |
| `chartsearchai.llm.remote.modelName` | `medgemma-1.5-4b-it` | `model` field in the request body |

`RemoteLlmEngine.infer()` reads the model name fresh on every call (no instance cache). Changing the GP via REST takes effect on the next request — no backend restart required.

For LM Studio, the doctor script already derives the `/v1/models` URL by stripping `/chat/completions`:

```sh
URL="${CHARTSEARCH_REMOTE_ENDPOINT_URL%/chat/completions}/models"
```

That pattern works for LM Studio, OpenAI, Anthropic, vLLM, Ollama, etc. — all expose `/v1/models`.

## Proposal — simple picker

A POC picker scoped to "list + switch" (no upload, no settings, no per-user preferences):

```
┌──────────────────────────────────────────────────────────┐
│ ✨ AI Chart Search                  [ medgemma-1.5-4b-it ▾ ] [🔄] [✕] │
│                                                          │
│  what meds is she on?                                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Lisinopril 10mg [2], Metformin 500mg [4]            │ │
│  └─────────────────────────────────────────────────────┘ │
```

Dropdown shows the models the configured endpoint reports. Selecting one calls a backend endpoint that updates `chartsearchai.llm.remote.modelName`. Next chat turn routes through the new model.

## Architecture

### Backend additions

Two thin REST endpoints (mirror the existing `/chat` family pattern):

```
GET  /ws/rest/v1/chartsearchai/models
  → 200 OK { current: "medgemma-1.5-4b-it",
            available: ["gemma-4-e2b-it", "medgemma-1.5-4b-it", "meta-llama-3.1-8b-instruct"],
            engine: "remote" }
  → 503 if engine=local (or the endpoint is unreachable — operator action needed)

POST /ws/rest/v1/chartsearchai/model
  body: { modelName: "medgemma-1.5-4b-it" }
  → 200 OK { current: "medgemma-1.5-4b-it" }
  → 400 if modelName is not in the current `available` list (defends against client-typed garbage)
  → 503 if engine=local
```

Implementation sketch (~60 LOC total, one new service class):

```java
// new: api/.../ModelSwitchService.java
public class ModelSwitchService {
  public ModelList listAvailable() {
    String engine = gp(GP_LLM_ENGINE);
    if (!"remote".equalsIgnoreCase(engine)) {
      throw new IllegalStateException("model listing only supported on remote engine");
    }
    String endpoint = gp(GP_LLM_REMOTE_ENDPOINT_URL);
    String modelsUrl = endpoint.replaceAll("/chat/completions$", "/models");
    // call modelsUrl via the same HttpClient as RemoteLlmEngine, with the API key header
    // parse `data[].id` from OpenAI-compat response
    return new ModelList(gp(GP_LLM_REMOTE_MODEL_NAME), ids, engine);
  }

  public String setCurrent(String modelName) {
    // re-fetch listAvailable() and assert modelName ∈ available
    Context.getAdministrationService().setGlobalProperty(GP_LLM_REMOTE_MODEL_NAME, modelName);
    return modelName;
  }
}
```

REST controller is two `@RequestMapping` methods around it.

### Frontend additions

`src/api/chartsearchai.ts`:

```typescript
export interface ModelListResponse {
  current: string;
  available: string[];
  engine: 'remote' | 'local';
}

export async function fetchAvailableModels(): Promise<ModelListResponse> { ... }

export async function setCurrentModel(modelName: string): Promise<{ current: string }> { ... }
```

New component `src/components/model-picker.component.tsx`:
- `useSWR` against `fetchAvailableModels()` — 60s stale-while-revalidate
- Renders a Carbon `Dropdown` when `engine === 'remote'` AND the list has ≥2 items
- Hides itself otherwise (so single-model remote setups or local-engine setups don't see a useless dropdown)
- On select: `setCurrentModel` → optimistic UI flip → show Carbon `Notification` toast on success/error

Placement: in the AI panel header, next to the "New chat" button. Floating-mode header: between title and the icons. Workspace mode: in the toolbar row that holds "New chat".

Gated by a new config-schema entry:

```typescript
// src/config-schema.ts
showModelPicker: {
  _type: Type.Boolean,
  _default: false,
  _description:
    'Show the LLM model picker in the AI chat panel header. The picker lists models reported by '
    + "the configured remote endpoint's /v1/models. Useful for developer / demo deployments where "
    + 'switching models live (e.g. between local-LLM variants in LM Studio) is part of the workflow. '
    + 'Defaults off so clinician-facing deployments do not see a control they have no reason to use.',
},
```

## Auth / privilege

POC: gate by the existing `AI Query Patient Data` privilege (same as the chat endpoint). Anyone who can chat can switch the model. Cheap to ship, OK for demo / dev contexts.

**Production**: model switch is a configuration change that affects all users. The clean answer is a new module privilege `chartsearchai.Manage Model` granted only to admins / power users. Out of scope for the picker POC — file as a follow-up.

## Caveats worth flagging in code + spec

1. **Global config — not per-user**. The model GP is global. Switching affects every user's NEXT chat turn, including users mid-conversation in their own sessions. There is no per-session model selection. UX-wise: clinician A switches to medgemma, clinician B's next request also routes through medgemma without warning. For a dev/demo deployment this is fine; for clinician-facing, surface a "this affects everyone" warning above the dropdown OR move the picker to the OpenMRS admin settings page.

2. **Cache invalidation on every switch**. LM Studio's KV cache keys on model. Switching from gemma-4-e2b-it to medgemma → next call pays full prompt processing cost (11K tokens of prompt) on first request. Subsequent calls cache against the new model. Not a correctness issue, just a "first call after switch is slow" UX note.

3. **Context-size mismatch**. The chart-snapshot logic and the `chartsearchai.chat.maxContextTokens` GP both assume a 32K-context model. If the operator switches to a small-context model (4K) without changing the budget GP, the next call returns HTTP 400 from the server. We hit this when first loading medgemma — the model loaded with LM Studio's default 4K window. Two safe behaviors:
   - The picker queries each candidate's `n_ctx` (via the `/v1/models/<id>` detail endpoint when supported, e.g. LM Studio) and warns when below the budget GP.
   - OR document the gotcha and rely on the user catching the HTTP 400 → reload model with larger context. POC takes the second path.

4. **Endpoint reachability**. If the operator's `chartsearchai.llm.remote.endpointUrl` points at an endpoint that's down, the picker shows an empty list (or 503). The error path needs to be clear enough that the user knows to check LM Studio is running. Re-uses the existing `chartsearch-doctor` Makefile target's diagnosis flow.

5. **API-key-protected `/models` endpoints**. OpenAI and Anthropic require auth on `/v1/models`. The implementation must pass the same `Authorization: Bearer <key>` the chat endpoint uses (from `chartsearchai.llm.remote.apikey` runtime property). Already a one-liner in the sketch but easy to forget.

## Sizing

- Backend: ~80 LOC (service + REST controller + tests). Single migration not required — uses existing GP.
- Frontend: ~100 LOC (api helpers + component + config-schema entry + 1–2 vitest cases).
- No schema changes. No new global properties (apart from the frontend config-schema which is a per-deployment SPA setting, not a backend GP).

## Acceptance — picker closes when

1. `GET /chartsearchai/models` returns `{current, available[], engine}` for the LM Studio endpoint
2. `POST /chartsearchai/model` updates the GP and the response reflects the new current
3. Switching a model via the picker → next chat turn uses the new model (verifiable in LM Studio's debug logs: `model: <new>` in the request body)
4. Picker hidden when `engine === 'local'` OR when `available.length < 2`
5. Picker hidden when `showModelPicker === false` in the SPA config
6. Vitest covers: fetch returns expected shape; select calls setCurrentModel; error path shows toast

## Out of scope for POC

- Per-user / per-session model preference
- Admin-level model management (uploads, downloads, deletion)
- Per-model context-size enforcement (item 3 in caveats — relies on operator)
- Model selection auditing (would write an entry to `chartsearchai_audit_log` on each switch)
- A separate `chartsearchai.Manage Model` privilege (POC reuses `AI Query Patient Data`)

## Future enhancements (file separately when warranted)

- Per-session "preferred model" stored on `chat_session.model_name`. Then picker is per-session, not global. Removes caveat #1.
- Auto-detect context size from `/v1/models/<id>` detail endpoint when supported; warn on mismatch with budget GP.
- Show usage stats (prompt_tokens, completion_tokens, prompt cache hit %) per model so the picker doubles as a comparison panel.
- Move to OpenMRS admin settings page (under "Modules → AI Chart Search → Model") for production deployments; keep the in-panel picker as a dev-mode affordance only.

## Open question for the user

Where should the picker live by default?

- **Option A (panel header)** — proposal above. Inline with chat workflow. Easy to switch mid-conversation.
- **Option B (OpenMRS admin settings page)** — slower to access; better for clinician-facing deployments where model selection is rare + admin-only.
- **Option C (both, gated by config)** — `showModelPicker` for the panel header, always available in admin settings. Most flexible.

POC pick: Option A behind `showModelPicker: false`. Operators who want admin-only control just leave the SPA flag off. Option B/C would be added later for production rollout.
