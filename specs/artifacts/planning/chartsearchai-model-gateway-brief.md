# chartsearchai Model Gateway — Source Brief

**Status**: Source brief — feeds `/speckit-specify` for feature 008.
**Roadmap entry**: M3/M4 follow-on — `008-chartsearchai-model-gateway` (lane `foundation`; first consumer is chartsearchai).
**Recommended spec number**: **008**. 006 and 007 are reserved by 005's explicit deferrals (frontend "Answered by" pill; MCP/Spark/FHIR tooling). 003 is a numbering gap that is deliberately not backfilled (the chartsearchai lineage is sequential on disk: 004 → 005 → 006 → 007 → 008).
**Last updated**: 2026-05-20.
**Paired canvas (to be created during `/speckit-plan`)**: `specs/artifacts/canvases/chartsearchai-model-gateway.canvas.tsx`.

This document is the authoritative architectural brief for the chartsearchai model gateway. It is the **input** to Spec Kit commands (`/speckit-specify`, `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`). Spec Kit-generated artifacts live under `specs/008-chartsearchai-model-gateway/` after Phase 2. Do not edit the generated artifacts; update this brief instead.

---

## 1. Goal

The chartsearchai backend currently treats "the LLM provider" as a single OpenAI-compatible URL plus a model name, both stored as OpenMRS global properties (`chartsearchai.llm.remote.endpointUrl`, `chartsearchai.llm.remote.modelName`). The picker in the ESM frontend fetches `/v1/models` from whichever endpoint is currently configured and renders a flat list of raw model IDs. Switching providers today means a SQL `UPDATE` against `global_property` and re-fetching the model list from the new endpoint. There is no notion of "which provider this model came from", no way to surface multiple providers in one picker, and no place to keep provider-class metadata (capability tier, auth requirement, cost class, locality).

Feature 005 (med-agent-hub bridge) hardened this single-endpoint pattern by making med-agent-hub the lone gateway chartsearchai talks to, with routing happening internally to that one URL. That posture is correct for 005 but does not generalize: the user wants to **simultaneously** offer LM Studio, Ollama, vLLM, cloud APIs (OpenAI / Anthropic / Gemini / Azure), and agentic providers (med-agent-hub, future Catalyst-as-LLM) in the same picker, with the picker organized by **class of connection**, and with one chartsearchai-facing entrypoint that mediates the actual provider calls.

This feature introduces a new service — the **chartsearchai model gateway** — that sits between chartsearchai and the real LLM providers. The gateway exposes a single OpenAI-compat surface to chartsearchai (preserving 005's wire-shape contract verbatim), maintains a connection registry of available providers grouped by class, normalizes per-provider `/v1/models` responses into a uniform shape with class and capability metadata, and forwards chartsearchai's full request payload (including `response_format`, `stream`, `stream_options`, `top_k`, `temperature`, `max_tokens`, `tools`) to the chosen provider. The picker UX is generalized from a flat dropdown of model IDs to a grouped/two-level view that surfaces the connection class alongside the model ID.

The gateway is **separate and specific to chartsearchai**. med-agent-hub is **one provider** the gateway can route to — not the gateway itself. Catalyst-as-LLM, Ollama models, LM Studio models, and cloud APIs are peers of med-agent-hub in the gateway's connection registry. The picker generalizes; chartsearchai's `RemoteLlmEngine` continues to read one endpoint URL at call-time (the gateway's URL); chartsearchai itself stays code-untouched except for the picker UX changes in the ESM submodule and the `/v1/models` response shape evolution in the REST controller.

---

## 2. Target architecture

```
chartsearchai (Java .omod, unchanged on the LLM wire)
   │  GET  /ws/rest/v1/chartsearchai/models          (REST surface — shape evolves to carry class metadata)
   │  POST /ws/rest/v1/chartsearchai/model           (REST surface — body accepts {connectionId, modelId})
   │  POST <gateway-url>/v1/chat/completions         (wire-identical to today; gateway is just an endpoint)
   ▼
chartsearchai-model-gateway   (NEW — Python FastAPI, sibling of med-agent-hub)
   │  ── reads connection registry (file | DB | gateway-internal — see Open Q2)
   │  ── normalizes /v1/models across providers
   │  ── enforces auth boundary: holds provider API keys, never returns them
   │  ── preserves response_format / stream / stream_options / top_k / temperature / max_tokens / tools verbatim
   │  ── translates streaming SSE shape per-provider (already a 005 precedent for med-agent-hub)
   │
   ├──►  LM Studio                  (host.docker.internal:1234, OpenAI-compat)        [class: local-runtime / lm-studio]
   ├──►  Ollama                     (host.docker.internal:11434, OpenAI-compat)       [class: local-runtime / ollama]
   ├──►  vLLM / TGI / llama.cpp     (any OpenAI-compat HTTP runtime)                  [class: local-runtime / generic-openai]
   ├──►  OpenAI                     (api.openai.com)                                  [class: cloud-api / openai]
   ├──►  Anthropic Claude           (api.anthropic.com, /v1/messages adapter inside gateway) [class: cloud-api / anthropic]
   ├──►  Google Gemini              (generativelanguage.googleapis.com)               [class: cloud-api / gemini]
   ├──►  Azure OpenAI               (per-deployment endpoint)                         [class: cloud-api / azure]
   └──►  med-agent-hub:8080         (from 005, OpenAI-compat with internal routing)   [class: agentic / med-agent-hub]
```

Key architectural posture:

1. **chartsearchai's `RemoteLlmEngine` reads `chartsearchai.llm.remote.endpointUrl` at every inference call** (RemoteLlmEngine.java:56 / :106). The gateway URL becomes the value of that GP. From chartsearchai's perspective, the gateway is "just another OpenAI-compat endpoint" — identical posture to how 005 slotted med-agent-hub in. Rollback to direct-LM-Studio remains a single SQL UPDATE on one row.
2. **The model name GP (`chartsearchai.llm.remote.modelName`) carries a gateway-resolvable identifier**, not a raw provider model ID. Format is part of Open Q1/Q7 — proposals: `<connectionId>:<modelId>` (e.g. `lm-studio:gemma-3-4b`, `anthropic:claude-opus-4-7`, `med-agent-hub:router`) or `<modelId>` with the gateway choosing the connection based on disambiguation rules.
3. **The gateway is a new compose service**, sibling of med-agent-hub. Same shared-bridge-network pattern. Same submodule pattern (`targets/chartsearchai-model-gateway/`). Same `extra_hosts` to reach `host.docker.internal` for local-runtime providers.
4. **Provider credentials live in the gateway's env scope**, never in chartsearchai's env or DB. chartsearchai sends no `Authorization` header to the gateway by default; the gateway attaches the per-provider `Authorization: Bearer <key>` outbound. Optional: chartsearchai's existing `RP_LLM_REMOTE_API_KEY` runtime property can be repurposed as a gateway-level shared secret if gateway↔chartsearchai auth is needed.

---

## 3. Relationship to other specs

| Spec | Title | Status | Relationship | Blocks 008? | Unblocked by 008? |
|---|---|---|---|---|---|
| 001 | Harness control plane foundation | done | Defines compose overlay strategy + adapter contract shape the gateway must conform to. | No (pure dependency) | n/a |
| 002 | OpenMRS demo data 2.8 remap | in progress | Provides Zabella Halambe and the populated test patients used in 008's demo path. | No | n/a |
| 003 | (numbering gap, not backfilled) | n/a | Lineage stays sequential on disk. | n/a | n/a |
| 004 | Real adapter entrypoints — chartsearchai PoC | in progress | Establishes the chartsearchai REST + ESM picker baseline that 008 evolves. Defines today's two-GP contract. | **Yes — 008 cannot ship before 004 lands** because 008 assumes the chartsearchai `.omod` + ESM picker baseline. | n/a |
| 005 | med-agent-hub bridge | in progress | Establishes med-agent-hub as a gateway-compatible provider. 008 absorbs med-agent-hub as **one provider class** in the registry; the user's chartsearchai-side GP flip in 005 (point at med-agent-hub directly) becomes "point at the gateway, register med-agent-hub as a connection". | **Soft block — recommended**: 005 should land first so the gateway has a real agentic provider to register on day one, validating the architecture against a non-trivial class. Hard-block only if 008's design depends on shape decisions still open in 005. | Yes — 005's wire-contract decisions (response_format passthrough, SSE translation) become reusable inside the gateway. |
| 006 | Frontend "Answered by: <agent>" pill | deferred from 005 | Surfaces which subagent inside med-agent-hub answered a turn. 008's picker introduces a closely related affordance ("Connected via: <class> / <provider>"). | No | **Yes — 008 can fold or coordinate** with 006: if 008 picker shows class/provider per chat turn, 006's pill becomes a sub-affordance for agentic providers (which subagent of med-agent-hub answered). Recommend 008 explicitly defines the data shape so 006 just consumes it. |
| 007 | MCP / Spark / FHIR tooling in med-agent-hub | deferred from 005 | Tool-use endpoint inside med-agent-hub. Orthogonal to 008. | No | **Parallel-safe.** 008 doesn't touch med-agent-hub's tool plumbing; 007 doesn't touch chartsearchai's picker. They can ship in either order. |
| 009 | Clinical knowledge base | planned | KB has its own integration paths (chartsearchai `LlmProvider.search` is the simplest; gateway is a likely second consumer). 008 is **not** a hard prerequisite for 009. | No | Yes — once 008 ships, the KB can register as a `kb-augmented` provider class, transparent to consumers that already speak the gateway. |
| 010 (M5) | Answer/citation/abstention eval | not started | Different concern (eval methodology). | No | Yes — gateway enables per-provider eval runs by class. |
| 013 (M8) | Querystore parity testbed | not started | Different concern (retrieval pipeline parity). | No | No — parallel. |
| 014 (M9) | Cross-project validation expansion | not started | Different scope. | No | Possibly — if openmrs_chatbot wants to share a model picker, the gateway becomes a reusable surface. Out of scope for 008. |
| 011 (M10) | Catalyst FHIR sidecar POC | planning | Catalyst exposes its own LLM-as-tool surface; could become a future gateway provider class (`catalyst-fhir`). Not in 008 scope. | No | Yes — gateway architecture leaves a clean slot for Catalyst as a provider. |

**Recommended ordering**: 004 → 005 → 008, with 006 and 007 sequencing flexible after 008. Rationale:
- 004 establishes the chartsearchai baseline (REST + ESM picker) that 008 evolves.
- 005 establishes the agentic-provider precedent (wire-shape preservation, SSE translation) that 008 absorbs as a provider class.
- 008 generalizes the picker and introduces the gateway as the new chartsearchai-side endpoint, with med-agent-hub registered as one of several providers.
- 006 layers on the per-turn "answered by" affordance once 008 has the class/provider metadata flowing.
- 007 adds tool-use inside med-agent-hub, transparent to 008.

**Why a new spec, not a 005 amendment**: 005 deliberately scoped down to "med-agent-hub is the single endpoint chartsearchai talks to" with no picker generalization. The picker generalization + multi-provider registry + auth boundary work is a meaningfully larger surface (new service, new submodule, new compose entry, new credential plane) that warrants its own spec record.

---

## 4. Success criteria

- **SC-008.1**: `make chartsearchai-model-gateway-build` produces a `chartsearchai-model-gateway:dev` Docker image from the `targets/chartsearchai-model-gateway/` submodule SHA.
- **SC-008.2**: `make chartsearchai-model-gateway-up` starts the container; `docker inspect` reports healthy after ≤90s. `GET /health` returns `200` with `{providers: [{id, class, ok}], ok: <bool>}`.
- **SC-008.3**: `GET <gateway>/v1/models` (called by chartsearchai's `ModelSwitchService`) returns a list whose entries include at minimum `{id, class, providerId, displayName, capabilities?}`. The list is the **union** of models exposed by all configured connections, normalized across provider-specific `/v1/models` shapes (LM Studio, Ollama, OpenAI, Anthropic, Gemini, Azure, med-agent-hub).
- **SC-008.4**: A single SQL `UPDATE` to `chartsearchai.llm.remote.endpointUrl` (point at the gateway) plus a model-name flip (gateway-resolvable identifier) makes the ESM picker render a **grouped or two-level** view that lets the operator pick a model from a different class (e.g. switch from `lm-studio:gemma-3-4b` to `anthropic:claude-opus-4-7`) without a backend restart and without an `.omod` rebuild. Verified in the ESM Playwright spec.
- **SC-008.5**: After switching to a new class via the picker, a 3-turn referential chat against Zabella Halambe (same anchor as 004 / 005) returns coherent answers from the newly-selected provider with citations preserved. Verifies the gateway forwards `response_format` and prior turns through every provider class on the critical path (load-bearing for at least: one local-runtime class + one cloud-api class + the agentic class).
- **SC-008.6**: Provider API keys (OpenAI, Anthropic, Gemini, Azure) are **never** present in chartsearchai's `openmrs-runtime.properties`, OpenMRS DB, OpenMRS logs, or wire traffic from chartsearchai to the gateway. Verified by grep against captured run artifacts plus a wire capture (e.g. mitmproxy) of one chartsearchai → gateway request showing no `Authorization` header.
- **SC-008.7**: Streaming SSE works through every provider class on the critical path. The chartsearchai SSE consumer (which is unforgiving of malformed `data:` lines per the 005 R2 precedent) accepts the gateway's translated stream without modification. Verified via `/ws/rest/v1/chartsearchai/chat/stream` browser test for at least one provider per class.
- **SC-008.8**: Rollback to "no gateway" (chartsearchai talking direct to LM Studio as in 004) is a single SQL UPDATE on `chartsearchai.llm.remote.endpointUrl`. No `.omod` rebuild, no module restart. Verified.

---

## 5. Functional requirements

- **FR-008.1**: The gateway MUST expose `POST /v1/chat/completions` with OpenAI-compat semantics. Request body fields MUST be preserved verbatim when forwarded to the chosen provider: `messages[]`, `model`, `response_format`, `stream`, `stream_options.include_usage`, `temperature`, `top_k`, `max_tokens`, `tools`, `tool_choice`. (Wire-shape parity with the 005 precedent. See `RemoteLlmEngine.buildRequestBody`.)
- **FR-008.2**: The gateway MUST expose `GET /v1/models` returning the **union** of models across all registered connections, with each entry carrying at minimum `{id, class, providerId, displayName, capabilities?}`. Per-provider `/v1/models` response shapes (OpenAI vs Anthropic's `/v1/models` vs LM Studio's `/v1/models` vs Ollama's `/v1/tags` vs med-agent-hub's `/v1/models`) MUST be normalized into this unified shape inside the gateway.
- **FR-008.3**: The gateway MUST maintain a **connection registry** of providers it can route to. Each registry entry MUST carry: stable id, human display name, class assignment, base URL, auth config reference (not the secret itself), and per-class capability metadata. Registry source is an open design question (Q2).
- **FR-008.4**: The gateway MUST hold all provider API keys in its own env / secret store. chartsearchai MUST NOT receive, store, log, or transmit provider API keys. The gateway MUST attach the appropriate `Authorization` header outbound per-provider; chartsearchai-to-gateway requests MUST work without any auth (or with an optional gateway-level shared secret carried in chartsearchai's existing `RP_LLM_REMOTE_API_KEY` runtime property — Open Q3).
- **FR-008.5**: The gateway MUST preserve chartsearchai's exact `response_format: {type: json_schema, schema: ...}` envelope when forwarding to providers that support structured output natively (OpenAI, Anthropic via tool-use shim, vLLM with grammars, LM Studio with JSON schema, med-agent-hub per 005). For providers without native structured output, the gateway MAY either reject the request (`400` with explicit reason) or inject a prompt-level instruction; the choice is per-provider and declared in the registry entry's `capabilities`.
- **FR-008.6**: The gateway MUST preserve the `claude-opus-4-7` quirk from `RemoteLlmEngine.buildRequestBody` (lines 175-180): when the chosen model id starts with `claude-opus-4-7`, the gateway MUST NOT inject `temperature`/`top_p` and MUST honor `top_k=1`. Equivalent provider-specific quirks for other cloud APIs (e.g. Azure deployment naming, Gemini `safety_settings`) MUST be encoded in the gateway, not in chartsearchai.
- **FR-008.7**: The gateway MUST translate provider-specific streaming SSE into the OpenAI-shape `data: {"choices":[{"delta":{"content":"..."}}]}\n\n` chunks chartsearchai expects, terminating with `data: [DONE]\n\n`. This includes Anthropic's `event: content_block_delta` shape, Ollama's NDJSON shape, and any non-OpenAI provider added to the registry.
- **FR-008.8**: The gateway MUST be reachable from chartsearchai's OpenMRS backend container by service name on the shared compose bridge network (e.g. `http://chartsearchai-model-gateway:8080/v1/chat/completions`). The gateway MUST use `extra_hosts: host.docker.internal:host-gateway` to reach local-runtime providers on the host (mirrors med-agent-hub's pattern from 005 FR-005.10).
- **FR-008.9**: The gateway MUST log to stdout (not files) so `docker logs chartsearchai-model-gateway` works. Logs MUST NOT dump full `messages[]` bodies at INFO level — chart-snapshot user messages contain PHI. Bodies appear only at DEBUG and MUST be scrubbed before any cloud deploy (mirrors 005 trade-off #4).
- **FR-008.10**: The gateway MUST be integrated as a git submodule at `targets/chartsearchai-model-gateway/`, tracking the harness-integration branch of its upstream repo, following the same pattern as `targets/med-agent-hub/`, `targets/chartsearchai/`, and `targets/chartsearchai-esm/`.
- **FR-008.11**: chartsearchai's `ModelSwitchService` MUST accept the gateway's unified `/v1/models` shape. The response from `GET /ws/rest/v1/chartsearchai/models` MUST carry per-entry class metadata so the ESM picker can render a grouped/two-level view. (This is a chartsearchai REST shape change — the only chartsearchai-side code change in this feature.)
- **FR-008.12**: `POST /ws/rest/v1/chartsearchai/model` MUST accept a gateway-resolvable model identifier (form decided in Open Q7). The existing validation contract (only persist names present in the live `/v1/models` list) MUST hold against the unified list returned by the gateway.
- **FR-008.13**: The ESM `model-picker.component.tsx` MUST surface the connection class alongside the model id. The exact affordance (grouped dropdown, two-level menu, inline cards) is Open Q4; the data contract is fixed: each picker entry shows at minimum `{class, providerName, modelId}`.
- **FR-008.14**: The gateway MUST be backwards-compatible with the **no-gateway** posture: chartsearchai pointing direct at LM Studio (as in 004) or direct at med-agent-hub (as in 005) MUST continue to work. The gateway is opt-in per environment via the `chartsearchai.llm.remote.endpointUrl` GP value. (Open Q5 covers migration mechanics.)
- **FR-008.15**: The gateway MUST expose a per-connection health probe (`GET /v1/connections/<id>/health` or equivalent) so the picker can hide unreachable connections and the operator can debug provider outages without reading container logs.

---

## 6. Open design questions for `/speckit-clarify`

These must be resolved before Phase 2 spec artifacts are authored. Each question lists **2-3 options with trade-offs**; the user picks during clarification.

### Q1 — Semantics of "classes of connections"

The picker needs to organize providers by some axis. Three candidate framings:

| Option | Axis(es) | Example classes | Pros | Cons |
|---|---|---|---|---|
| **A. Provider family** (single axis) | Who runs the runtime / who owns the model serving | `lm-studio`, `ollama`, `vllm`, `generic-openai`, `openai`, `anthropic`, `gemini`, `azure-openai`, `med-agent-hub` | Maps 1:1 onto how operators think about credentials and deployment. Easy to render. Matches gateway plumbing. | Doesn't surface capability tier — operator can't tell at a glance "small fast local" vs "large slow cloud". |
| **B. Capability tier** (single axis) | What the model is good for | `small-local`, `medium-local`, `large-cloud-general`, `large-cloud-frontier`, `agentic`, `specialty-medical` | User-friendly framing matches clinical workflow ("I want a fast model for this triage Q"). | Capability assignments are subjective and drift over time. Hard to assign new models automatically. Hides provider identity which the operator may need for cost/compliance reasons. |
| **C. Both as orthogonal axes** | Provider family (grouping) × capability tier (badge/sort) | Grouped by family, with per-entry capability badges | Most informative. Survives evolution: new providers slot into existing classes; new capability tiers don't require regrouping. | More UI surface (groups + badges); registry entries carry two fields; more clarification needed at registration time. |

**Recommendation surfaced for `/speckit-clarify`**: Lean Option C, fall back to Option A if the picker UX (Q4) gets too dense. Whichever is picked, the registry schema MUST carry both fields so the other framing is recoverable in a follow-up without a wire change.

### Q2 — Connection registry source

Where does the gateway read its connection list from? Three candidate sources:

| Option | Mechanism | Pros | Cons |
|---|---|---|---|
| **A. File-based (YAML/JSON in the gateway image or mounted volume)** | `connections.yaml` baked at image build OR mounted at runtime; reload-on-SIGHUP | Simplest. Versionable in git. Matches catalyst/med-agent-hub config patterns. Works with `.env.chartsearchai-model-gateway` for secret refs. | Operators must restart or signal the gateway to add a new connection. No multi-tenant story. |
| **B. DB-backed via OpenMRS global properties** | Each connection a GP row, gateway reads via REST callback on the chartsearchai OpenMRS backend | Operators manage providers in the same admin UI as everything else. No restart needed. | Couples gateway lifecycle to chartsearchai availability. Pushes provider config (including non-PHI display strings) through the OpenMRS DB. Cyclic dependency at startup. |
| **C. Gateway-internal config served via its own admin API** | `POST /v1/admin/connections`; persisted to gateway-owned sqlite or postgres | Cleanest separation; gateway owns its own state. Multi-tenant ready. | New service surface to secure. New persistence dep. Heaviest implementation. |

**Recommendation surfaced for `/speckit-clarify`**: Option A for the POC (matches the harness's "real production paths, deterministic transforms" stance). Defer Option C to a v2 if multi-tenancy emerges.

### Q3 — Auth model boundaries

Three orthogonal sub-questions:

3a. **chartsearchai → gateway**: (i) unauthenticated on the compose bridge network (matches med-agent-hub from 005, which is internal-only); (ii) shared secret via chartsearchai's existing `RP_LLM_REMOTE_API_KEY` runtime property; (iii) per-user OpenMRS session forwarded as a header for audit/RBAC.

3b. **Gateway → provider**: gateway holds the credential, attaches the appropriate auth header per-provider (Bearer for OpenAI/Anthropic/Gemini; `api-key` for Azure; none for local runtimes). Not really open — this is the FR-008.4 invariant.

3c. **User identity propagation**: does the gateway need to know which OpenMRS user made the request (for cost attribution, rate limiting, audit)? (i) No — gateway is fully anonymous; (ii) Yes, propagate as a header from chartsearchai; (iii) Yes, propagate AND let the registry encode per-class rate limits.

**Recommendation surfaced for `/speckit-clarify`**: 3a-i for the POC (internal-only, mirrors 005). 3c-i for the POC; revisit when cloud-API spend becomes material. The user MUST decide if any cloud-API spend visibility is needed before shipping cloud-API support — that decides 3c.

### Q4 — Picker UX affordance

Three candidate affordances:

| Option | Visual | Pros | Cons |
|---|---|---|---|
| **A. Grouped dropdown** | Single popover; entries grouped by class header (`LM Studio`, `Anthropic`, `med-agent-hub`); each row shows model id | Smallest UI change from today's flat popover. Carbon-friendly. | Long list with many providers; no visible capability hint. |
| **B. Two-level (class first, then model)** | Click trigger → pick class → pick model within class | Cleanest mental model. Scales to many providers per class. | Two clicks instead of one. Requires a back-affordance. |
| **C. Inline cards** | Trigger expands a card grid; each card shows class badge, provider name, model id, capability hint | Most informative. Best for showcasing the new "classes" framing. | Heaviest UI. Larger bundle weight (matters per `model-picker.component.tsx` comment about bundle weight). |

**Recommendation surfaced for `/speckit-clarify`**: Option A for the POC (minimal departure from today's affordance, preserves bundle-weight discipline). Option B is the v2 if the model list crosses ~20 entries. Option C is appropriate for a dedicated "model browser" surface, not the inline picker. The data contract (FR-008.13) is the same across all three; the affordance is purely a UX call.

### Q5 — Backwards compatibility & migration

Three migration paths:

| Option | Mechanism | Pros | Cons |
|---|---|---|---|
| **A. Per-environment opt-in via GP value** | `chartsearchai.llm.remote.endpointUrl` either points at the gateway (new) or direct at LM Studio (old); no flag needed | Cleanest — uses existing GP semantics. Zero new state. Rollback is one SQL UPDATE. | Operators have to know to flip; no automatic migration. |
| **B. Third engine value (`chartsearchai.llm.engine=gateway`)** | New value alongside `local` / `remote`; engine selection logic in `LlmProvider.getActiveEngine()` adds a third branch | Explicit posture; easier to grep logs for. | Requires chartsearchai code change (touches `LlmProvider`, breaks the "code untouched" posture FR-005.7 established). |
| **C. Auto-detect from endpoint URL shape** | Gateway URL has a known prefix or trailing path the engine sniffs | No operator action needed once URL is set. | Magic; brittle. Doesn't survive URL rewrites. |

**Recommendation surfaced for `/speckit-clarify`**: Option A. Preserves the 005 FR-005.7 "chartsearchai code untouched" posture for the engine selection path. The only chartsearchai code changes in 008 are the `ModelSwitchService` response shape (FR-008.11) and the ESM picker UX (FR-008.13) — neither touches the engine branch.

### Q6 — Engine GP semantics for the gateway case

Closely related to Q5 but distinct. Today: `chartsearchai.llm.engine ∈ {local, remote}`. With the gateway, what's the value?

- **Option A**: Keep `remote`. Gateway is "just another remote endpoint" (the 005 posture). Zero code change.
- **Option B**: Introduce `gateway` as a third value. Makes the posture explicit, lets `ModelSwitchService.listAvailable()` skip the engine check or route differently.
- **Option C**: Keep `remote` but add a sibling GP `chartsearchai.llm.remote.endpointType ∈ {direct, gateway}` for explicit signalling without breaking the engine enum.

**Recommendation**: Option A for the POC. Revisit if the gateway grows admin endpoints chartsearchai needs to call separately.

### Q7 — Model identifier format on the wire

What does `chartsearchai.llm.remote.modelName` hold when the gateway is active?

- **Option A**: `<connectionId>:<modelId>` (e.g. `lm-studio:gemma-3-4b`, `anthropic:claude-opus-4-7`). Gateway parses, routes, strips prefix before forwarding the original `modelId` to the provider. Picker writes this composite key. Round-trip stable.
- **Option B**: Raw `<modelId>` (e.g. `gemma-3-4b`). Gateway picks the connection based on disambiguation rules (first-match, capability hint, recently-used). Ambiguous when two providers serve the same model name.
- **Option C**: Opaque opaque-id assigned by the gateway at registry-load time (e.g. `m_abc123`). Gateway resolves the id internally. Most flexible but unfriendly to log scraping / debugging.

**Recommendation surfaced for `/speckit-clarify`**: Option A. Survives same-name collisions, debuggable, no registry-side state needed for resolution. Matches `ModelSwitchService.setCurrent`'s existing "validate against live list" contract trivially (composite key validated as one string).

### Q8 — Gateway's `/v1/models` shape: where does normalization happen?

`ModelSwitchService.deriveModelsUrl` today strips `/chat/completions` and appends `/models` (lines 171-180). If the gateway returns OpenAI-shape `{data: [{id, ...}]}`, this convention keeps working with zero chartsearchai change. But the brief requires per-entry class/provider/capability metadata. Two options:

- **Option A**: Extend OpenAI shape — `{data: [{id, class, providerId, displayName, capabilities, ...}]}`. chartsearchai's `ModelSwitchService.parseModelIds` currently reads only `id` (line 220) and ignores extras; safe to extend.
- **Option B**: New shape under a different path (e.g. `/v1/connections` returning `{connections: [{id, class, models: [...]}]}`). Cleaner separation; requires chartsearchai REST shape change.

**Recommendation**: Option A. Backwards-compatible by construction. The chartsearchai REST shape change (FR-008.11) is the layer that surfaces the extra fields up to the SPA — the gateway-to-chartsearchai wire stays OpenAI-shaped.

### Q9 — Where the gateway runs (deployment shape)

- **Option A**: New compose service alongside med-agent-hub. New submodule under `targets/chartsearchai-model-gateway/`. Python FastAPI (consistent with med-agent-hub, openmrs_chatbot, catalyst). Recommended.
- **Option B**: Same repo as med-agent-hub, run as a sidecar in the same container. Wrong shape — couples lifecycles, violates the "med-agent-hub is one provider" framing.
- **Option C**: **Adopt an existing OSS LLM gateway** (LiteLLM, OpenLLM, Portkey) and harness-wrap it instead of building. The user's design space did not surface this; recommend it as the **pre-spec research item** (see Section 10). If chosen, the FRs around wire-shape preservation, class metadata, and SSE translation all still apply but become "verify the OSS gateway honors them" rather than "build them".

**Recommendation surfaced for `/speckit-clarify`**: Option C deserves a research spike before Option A is locked in. Adopting an existing gateway saves substantial implementation work; the question is whether any OSS gateway preserves the chartsearchai wire-shape quirks (json_schema response_format, top_k=1 for claude-opus, SSE translation across providers) verbatim. If yes, adopt. If no, build (Option A).

---

## 7. Out of scope (deferrals)

- **Per-user cost attribution / spend visibility** — gateway is anonymous to the user level in the POC. Cost tracking is a v2 once cloud-API spend becomes material.
- **Per-user / per-class rate limiting** — chartsearchai's existing audit-log-based rate limit (`ChartSearchAiRestController.checkRateLimit`) continues to apply at the chartsearchai layer. Gateway-level rate limits are deferred.
- **Multi-tenancy in the gateway** — single-tenant POC. Multi-tenant registry deferred to v2.
- **Caching layer in the gateway** — gateway is a pure forwarder. Response caching (semantic cache, exact-match cache) is deferred. chartsearchai's prefix-cache benefits (from feature 004 Phase 2) remain at the chosen provider's layer (LM Studio cache_prompt, Anthropic prompt caching).
- **Frontend "Answered by: <agent>" pill for routing inside med-agent-hub** — deferred to feature 006. 008's picker shows the chosen class/provider; the intra-agentic-provider routing (router → medical | clinical inside med-agent-hub) is 006's surface.
- **Tool-use endpoint inside med-agent-hub / Spark / FHIR** — deferred to feature 007. Orthogonal to gateway architecture.
- **Sticky-session routing for prompt-cache preservation across turns** — same trade-off 005 documented; gateway adds another layer where session affinity could be enforced, but POC accepts the cache loss.
- **Admin UI for gateway config** — registry is operator-managed via file/GP/API depending on Q2 choice. No web UI in 008.
- **`/v1/embeddings` passthrough** — chartsearchai's embedding pipeline uses an in-process ONNX model (the `LocalLlmEngine`'s warmup path is for chat, not embeddings). Out of scope.
- **Self-signed cert / mTLS between chartsearchai and gateway** — deferred. Internal-only on bridge network per FR-008.4 / 005 precedent.
- **Adding the gateway as a provider class to OTHER harness targets** (openmrs_chatbot, catalyst, querystore) — out of scope. 008 is chartsearchai-specific per user. Reusing the gateway across targets is a future expansion (potentially feature 014 / M9).

---

## 8. Demo path that proves success

**Local**: operator runs `make chartsearchai-model-gateway-build && make chartsearchai-model-gateway-up`; gateway container reports healthy; `curl <gateway>/health` shows at least two configured providers green (LM Studio + Anthropic). Operator SQL-updates `chartsearchai.llm.remote.endpointUrl` to the gateway URL and `chartsearchai.llm.remote.modelName` to `lm-studio:gemma-3-4b`. Opens Zabella Halambe's chart in the browser, asks "What medications is this patient on?" — streamed answer returns with citations from LM Studio. Opens the picker (now grouped by class), selects `anthropic:claude-opus-4-7` from the **Anthropic** group. Same question — streamed answer returns from Claude (no `.omod` rebuild, no module restart, picker reflects the new selection immediately). Selects `med-agent-hub:router` from the **med-agent-hub (agentic)** group; runs the 005 3-turn referential smoke (Q1: "What medications?"; Q2: "How many did you list?"; Q3: "And what about her allergies?"); turn 2 answers with a number derived from turn 1 (proves priors flow through gateway → med-agent-hub → subagent → LM Studio). Greps captured backend logs and OpenMRS DB: zero Anthropic API key occurrences. Greps gateway logs at INFO: zero `messages[]` body content. Reverts `endpointUrl` GP to direct-LM-Studio; chat still works (proves rollback).

**Cloud (follow-on validation, not load-bearing for 008 closure)**: `make cloud-deploy --with-chartsearchai-model-gateway`; same smoke against `openmrs.openclinai.org`. Gateway reaches LM Studio via the LM Link tunnel, reaches Anthropic via direct HTTPS. Per-class wire capture confirms the auth-boundary invariant in the cloud profile.

---

## 9. Risks

| # | Risk | Mitigation |
|---|---|---|
| **R1** | Existing OSS LLM gateways (LiteLLM, Portkey, OpenLLM) already solve this problem; building from scratch duplicates work. | **Pre-spec research item** — see Section 10. Spike LiteLLM compatibility against chartsearchai's wire quirks (json_schema response_format, top_k=1 for claude-opus, SSE translation, streaming with `stream_options.include_usage`) before `/speckit-plan` locks the build-vs-adopt decision. |
| **R2** | Provider-specific quirks (Anthropic's `/v1/messages` vs `/v1/chat/completions`, Gemini's safety_settings, Azure's deployment naming) leak through the abstraction and break chartsearchai's response parser (`LlmResponseParser`). | Phase 1 acceptance test: chartsearchai talking through the gateway must produce byte-identical `{answer, citations, blocks}` envelopes as chartsearchai talking direct to LM Studio (for the same canonical question against the same patient and same model class). Gates merge. |
| **R3** | Streaming SSE translation across N providers becomes a maintenance burden — same R2 from 005 multiplied by the number of provider classes. | Adopt the 005 test-discipline: every provider class gets a dedicated SSE-translation test that asserts `data: [DONE]` termination and well-formed delta chunks. New provider classes ship only when their SSE test is green. |
| **R4** | PHI leakage in gateway container logs — chart-snapshot user messages contain PHI per the 005 trade-off #4. The gateway adds another logging surface. | Audit log statements during Phase 1; assert no INFO-level message body logging; scrub at DEBUG before any cloud deploy. Same posture as 005. |
| **R5** | Picker UX regression — users who were happy with today's flat list find the grouped/two-level affordance worse for "I have one provider, one model" deployments. | The picker MUST gracefully degrade: when only one connection has more than one model and no other connections are healthy, render today's flat list (no class headers). FR-008.13 + a hide-class-headers-when-single-class rule in the ESM picker. |

---

## 10. Pre-spec research items the user should consider commissioning

1. **OSS LLM gateway compatibility spike** (load-bearing for Q9 / R1). Spend 1-2 days standing up LiteLLM (or Portkey or OpenLLM) in front of LM Studio + Anthropic + med-agent-hub. Drive it from a curl harness that mimics `RemoteLlmEngine.buildRequestBody` exactly (json_schema response_format, top_k=1 for claude-opus, stream_options.include_usage). Pass criterion: the OSS gateway returns chartsearchai-parseable JSON for every provider class and emits chartsearchai-parseable SSE for every streaming provider. Failure criterion: any wire-shape divergence requires gateway-side patching. Outcome determines build-vs-adopt for `/speckit-plan`.
2. **Anthropic `/v1/messages` ↔ OpenAI `/v1/chat/completions` adapter audit**. Anthropic's native API does not implement `/v1/chat/completions`. Either rely on Anthropic's OpenAI-compat shim (which has known limitations — the `claude-opus-4-7` `top_k=1` quirk in `RemoteLlmEngine` exists because of one such limitation) or adapt inside the gateway. Audit which Anthropic features chartsearchai needs (prompt caching for the chart-prefix; json_schema response_format) and which the shim covers.
3. **Provider `/v1/models` shape inventory**. Capture a real response from each provider on the target list (LM Studio, Ollama, OpenAI, Anthropic, Gemini, Azure, med-agent-hub) and produce a normalization matrix. This is fast and de-risks FR-008.2 / Q8. Should happen before `/speckit-plan` so the normalization design is concrete, not speculative.

---

## 11. References

**chartsearchai files**:
- `targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/RemoteLlmEngine.java` (lines 50-198: `infer` / `buildRequestBody` — the wire-shape contract the gateway preserves; lines 175-180: the `claude-opus-4-7` quirk)
- `targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/ModelSwitchService.java` (lines 112-164: `listAvailable` / `setCurrent`; lines 171-180: `deriveModelsUrl` URL convention; lines 212-233: `parseModelIds` extension surface)
- `targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/LlmProvider.java` (lines 545-553: `getActiveEngine` — the engine selection branch FR-005.7 / Open Q6 protects)
- `targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/ChartSearchAiConstants.java` (lines 264-268: `GP_LLM_ENGINE`, `LLM_ENGINE_LOCAL`, `LLM_ENGINE_REMOTE` — engine enum values for Q6)
- `targets/chartsearchai/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java` (lines 318-376: `/models` and `/model` REST surface — FR-008.11 / FR-008.12 evolution point)
- `targets/chartsearchai-esm/src/components/model-picker.component.tsx` (full file — FR-008.13 picker UX change point; lines 19-26: hide-conditions that must continue to work)
- `targets/chartsearchai-esm/tests/e2e/specs/model-picker.spec.ts` (Playwright spec to extend per SC-008.4)

**Related specs**:
- `specs/004-real-adapter-entrypoints/{spec,plan,tasks}.md` — chartsearchai PoC baseline 008 extends
- `specs/005-med-agent-hub-bridge/{spec,plan,tasks}.md` — agentic-provider precedent 008 absorbs; D1 (peer-of-LM-Studio posture), D4 (response_format end-to-end), FR-005.3 / FR-005.4 (the wire-shape invariants 008 generalizes)
- `specs/001-harness-control-plane-foundation/{spec,plan,tasks}.md` — compose overlay and adapter contract shape

**Reference brief whose shape this mirrors**:
- `specs/artifacts/planning/catalyst-fhir-sidecar-brief.md`

**Paired research/planning**:
- `specs/artifacts/planning/clinical-kb-research.md` — companion KB research (parallel feature 009).
- `specs/artifacts/planning/clinical-kb-brief.md` — companion KB brief (parallel feature 009).
