# B4 — Endpoint-switching picker (LM Studio + Med Agent Hub as sections)

> Granular plan. The roadmap (§4) only specs the picker minimally for P1 (model round-trip within one endpoint). This is the expansion: the picker switches **endpoints**, each a **section** with its own models. Built on 004; chartsearchai + chartsearchai-esm forks.

## Goal (confirmed with user — scoped down 2026-05-30)

This is **for testing**, and the user needs a **clear connection to the actual running models**. The chat picker shows **one section per configured endpoint** — **LM Studio** and **Med Agent Hub** — and you switch between them (writes both `endpointUrl` and `modelName`, no manual GP flip). The **endpoint list is operator config** (a backend GP registry).

Scope for now (keep it small):
- **LM Studio section** = its real loaded models (as today).
- **Med Agent Hub section** = a **single choice**: the orchestrator **team** (`med-agent-team`), running whatever orchestrator model it's configured with. NOT its raw backends.
- **Clear connection to running models**: each choice surfaces the *real* model behind it — LM Studio entries are the actual model ids; the team entry shows the orchestrator model it's actually running (e.g. "Med Agent Team · google/gemma-4-e4b").
- **Deferred**: dynamically filling the hub section with multiple models / team flavors (later).

Implication: the bridge advertises **just `med-agent-team`** in `/v1/models` for now (single choice), and surfaces the orchestrator model id so the picker can show the connection. Raw backends stay callable via passthrough (for the 006 A/B) — just not advertised in the picker yet.

## Test principle (per user)

Test the **functionality at the right level — not over-mocked**. Concretely:
- **Backend:** exercise the REAL production code (registry parsing, per-endpoint section assembly, validation, GP writes). Seam ONLY the external HTTP boundary (`httpGet` — already a protected test seam) and the GP store. No mocking of ModelSwitchService's own logic. Cover happy + negative (unreachable endpoint, model-not-in-endpoint, registry-unset fallback).
- **ESM:** render the REAL picker component (React Testing Library). Seam ONLY the network/api boundary (`fetchEndpoints`/`setEndpointModel`). Assert behavior a user sees: sections render with their models, current is checkmarked, selecting calls the switch with the right (url, model). No mocking React internals; no tautological assertions.
- Every test must be red-when-broken.

## Backend (chartsearchai) — `ModelSwitchService` + REST + constant

1. **Constant** `GP_LLM_REMOTE_ENDPOINTS = "chartsearchai.llm.remote.endpoints"` — JSON `[{"label":"...","url":"...../v1/chat/completions"}]`.
2. **`listEndpoints()`** → `EndpointSection[]`. Parse the registry GP; for each entry call the existing `fetchAvailable(url)` (reuses the LM-Studio-/v1-probe + OpenAI fallback). Build a section `{label, url, provider, models[], reachable, isCurrent}`. `reachable=false` (not an exception) when a probe throws — one dead endpoint must not blank the picker. Fallback: registry unset/blank → a single section from the current `endpointUrl` GP (so it works with no config).
3. **`setEndpointAndModel(url, modelName)`** → validate `url` is in the registry AND `modelName` is in that endpoint's live `/v1/models` (reuse `fetchAvailable`); then write BOTH `endpointUrl` + `modelName` GPs. Reject (IllegalArgumentException → 400) if invalid; write nothing on reject.
4. **REST** (`ChartSearchAiRestController`): `GET /endpoints` → sections + current; `POST /endpoint` `{endpointUrl, modelName}` → switch both. Same `PRIV_QUERY_PATIENT_DATA` gate as `/models`/`/model`.
5. **Tests** (`ModelSwitchServiceTest`, override `httpGet` + GP seam):
   - `listEndpoints_buildsSectionPerRegisteredEndpoint` (2 endpoints, different models each, current flagged).
   - `listEndpoints_marksUnreachableEndpointWithoutFailing`.
   - `listEndpoints_fallsBackToCurrentEndpointWhenRegistryUnset`.
   - `setEndpointAndModel_writesBothGPsWhenValid`.
   - `setEndpointAndModel_rejectsModelNotServedByEndpoint` (and rejects unknown url) — asserts NO GP write.

## ESM (chartsearchai-esm) — api client + picker

6. **api client** (`api/chartsearchai.ts`): `EndpointSection` type; `fetchEndpoints()` → GET `/endpoints`; `setEndpointModel(url, modelName)` → POST `/endpoint`.
7. **Picker** (`model-picker.component.tsx`): render a **section header per endpoint**, its models beneath; current endpoint+model checkmarked; unreachable section shown disabled with a hint. Selecting a model → `setEndpointModel(url, id)` (optimistic flip + rollback on error, reuse the existing `extractApiError` resource-error handling). Keep the hide rules (showModelPicker, engine!=remote). Generalize the existing LM-Studio header into the per-endpoint section header.
8. **Tests** (`model-picker.test.tsx`, seam the api module): sections+models render; current checkmarked; selecting calls `setEndpointModel(url,id)`; unreachable section disabled; switch-error surfaces.

## Config / seed

9. Seed the registry GP with the two endpoints (LM Studio `:1234`, Med Agent Hub `med-agent-hub:8080`) via `chartsearch-configure.sh` (read from `.env.chartsearch`, e.g. `CHARTSEARCH_REMOTE_ENDPOINTS_JSON`) + document. Default-safe: unset → single-section fallback (#2).

## Increments (commit each)

- B4.1 backend: constant + `listEndpoints` + tests → green.
- B4.2 backend: `setEndpointAndModel` + tests → green.
- B4.3 backend: REST `/endpoints` + `/endpoint`; build `.omod`.
- B4.4 esm: api client + types.
- B4.5 esm: picker sections + tests → green; build bundle.
- B4.6 seed config + e2e in the OpenMRS UI (switch LM Studio ↔ Med Agent Hub by clicking).

## Out of scope (later)

Cloud as a third section (works once added to the registry — no new code); per-endpoint auth keys in the registry; reordering/CRUD of endpoints from the UI.
