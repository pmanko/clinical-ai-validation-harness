# LM Studio API Reference (harness)

This is provider API research from May 2026, not current application setup.
[ChartSearchAI](https://github.com/pmanko/openmrs-module-chartsearchai/blob/main/README.md)
owns bundled local/remote inference and configured Hub integration;
[Hub](https://github.com/pmanko/med-agent-hub/blob/main/README.md) owns its model profiles.

**Last verified**: 2026-05-28 against [lmstudio.ai/docs](https://lmstudio.ai/docs).
**Why this exists**: This records the three LM Studio API surfaces investigated before the hub-relay consolidation.

---

## TL;DR — which surface for which question

| Question | Use this | Notes |
|---|---|---|
| Run chat completion | `POST /v1/chat/completions` (OpenAI-compat) | What chartsearchai's `RemoteLlmEngine` uses today. |
| List "models the chat-completion call can target" (loaded set) | `GET /v1/models` (OpenAI-compat) | Returns the set chartsearchai's `ModelSwitchService` reads today. Loaded set may include downloaded-not-loaded when JIT-load mode is on, but no `state` field to distinguish. |
| **List ALL downloaded models + whether each is loaded** | `GET /api/v1/models` (LM Studio REST v1) | The one the picker should use. Per-entry `loaded_instances` array distinguishes loaded vs not. Available in LM Studio 0.4.0+. |
| Pre-load a model before first chat call | `POST /api/v1/models/load` | Blocks until model is in memory; avoids JIT-load latency on first chat turn. |
| Run chat via Claude/Anthropic-style API | `POST /v1/messages` (Anthropic-compat) | Useful for F008 routing to Anthropic-shaped consumers without modifying chartsearchai. |

---

## Surface 1 — OpenAI-compatible (`/v1/*`)

Default port `1234`. No auth by default; Bearer token optional via LM Studio settings.

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/chat/completions` | Chat completion. Used by chartsearchai's `RemoteLlmEngine.buildRequestBody`. JIT-loads the requested model on first call. |
| POST | `/v1/completions` | Legacy completions. Not used. |
| POST | `/v1/embeddings` | Embeddings. chartsearchai uses in-process ONNX instead. |
| POST | `/v1/responses` | OpenAI Responses API (Codex). Not used. |
| GET | `/v1/models` | Lists models the chat-completion call can target. **Returns the loaded set** by default; with JIT-load enabled, may include downloaded-not-loaded but no `state` to distinguish. |

**Critical limitation**: `GET /v1/models` does NOT distinguish loaded vs not-loaded. If you need that information, use `GET /api/v1/models` instead. See LM Studio bug tracker [#726](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/726).

---

## Surface 2 — LM Studio REST API v1 (`/api/v1/*`)

Launched with LM Studio 0.4.0. **Bearer auth required** via `Authorization: Bearer $LM_API_TOKEN` header.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/models` | All downloaded models. Per-entry: `key`, `type`, `publisher`, `display_name`, `architecture`, `quantization`, `size_bytes`, `params_string`, **`loaded_instances`** (empty array if not loaded), `max_context_length`, `format`, `capabilities`, `description`, `variants`, `selected_variant`. |
| POST | `/api/v1/models/load` | Load a model into memory. Body: `{model, context_length?, eval_batch_size?, flash_attention?, num_experts?, offload_kv_cache_to_gpu?, echo_load_config?}`. Returns `{type, instance_id, load_time_seconds, status: "loaded"}`. Blocks until loaded. |
| POST | `/api/v1/models/unload` | Free VRAM for a loaded model. |
| POST | `/api/v1/models/download` | Pull a model from the LM Studio catalog. |
| GET | `/api/v1/models/download/status` | Check download progress. |
| POST | `/api/v1/chat` | Stateful chat with streaming events. Higher-level than OpenAI's `/v1/chat/completions`. Not used by chartsearchai (which uses the OpenAI-compat path for portability). |

**State semantics**: a model is "loaded" iff `loaded_instances.length > 0`. The agent that surveyed the docs earlier (in PR #19) reported a `state: "loaded" | "not-loaded"` field — that was the v0 shape. v1 uses `loaded_instances` instead.

**Filtering for chat picker**: filter to `type === "llm"`. Embedding models surface in `/api/v1/models` too; selecting one for chat returns a 400 from `/v1/chat/completions`.

**Identifier mapping**: when calling `/v1/chat/completions` with a model name, the value chartsearchai writes to `chartsearchai.llm.remote.modelName` corresponds to the v1 `key` field. Same string used to address the model in load/unload.

---

## Surface 3 — LM Studio REST API v0 (`/api/v0/*`) — DEPRECATED

Earlier REST API, superseded by v1 in LM Studio 0.4.0. Still served for backwards compat. Per-entry includes a `state: "loaded" | "not-loaded"` field directly (cleaner than v1's `loaded_instances` array but the v1 shape carries strictly more information).

**Use only for fallback**: if a `GET /api/v1/models` probe returns 404 or a non-JSON response, the operator's LM Studio is probably < 0.4.0 — fall back to `/api/v0/models`.

---

## Surface 4 — Anthropic-compatible (`/v1/messages`)

Claude Messages API shim. Same port `1234`. **Bearer auth required** (uses the same `LM_API_TOKEN`).

- Supports: `messages[]`, `system`, multi-turn, basic tool use, streaming
- Documentation lookup was thin at time of writing (2026-05-28); the lmstudio.ai/docs sub-page was 404 on the URLs we tried. Update this section once primary docs settle.
- Relevant for F008: when the gateway routes to Anthropic-style consumers, it can choose between Anthropic real API and LM Studio's compat shim. Same wire shape.

---

## References

- LM Studio docs landing: https://lmstudio.ai/docs
- REST API v1 quickstart: https://lmstudio.ai/docs/developer/rest/quickstart
- v1 list models: https://lmstudio.ai/docs/developer/rest/list
- v1 load model: https://lmstudio.ai/docs/developer/rest/load
- v0 (deprecated): https://lmstudio.ai/docs/developer/rest/endpoints
- OpenAI-compat overview: https://lmstudio.ai/docs/developer/openai-compat
- LM Studio bug tracker #726 (`/v1/models` loaded-only): https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/726
- TTL / auto-evict / JIT-load semantics: https://lmstudio.ai/docs/developer/core/ttl-and-auto-evict
