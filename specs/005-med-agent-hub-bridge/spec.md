# Feature 005: med-agent-hub bridge — chartsearchai routes through an A2A team

**Roadmap slot**: M4 follow-on to 004 — agent-team backend introduction
**Scope of this PR**: integrate `pmanko/med-agent-hub` as a new harness submodule that serves chartsearchai over OpenAI-compat, with the LLM-classifier router always engaged.
**Status**: in progress | **Started**: 2026-05-18

## Goal

Stand up `med-agent-hub` as a peer service inside the harness compose stack, exposing a single `POST /v1/chat/completions` endpoint that internally dispatches to a small agent team (router → medical | clinical). chartsearchai's existing OpenAI-compat call path is unchanged on the wire; the only chartsearchai change is two global-property flips. End state: a clinician question against a real patient at `openmrs.openclinai.org` flows chartsearchai → med-agent-hub → LM Studio (via LM Link), returning the same `{answer, citations, blocks}` envelope as today, with the answer now produced by a routed subagent rather than a single direct LLM call.

This feature does not change chartsearchai code, does not introduce a frontend "which agent answered" affordance, and does not exercise med-agent-hub's MCP/Spark/FHIR tooling. Those are explicit deferrals to feature 006+.

## Success criteria

- **SC-005.1**: `make med-agent-hub-build` produces a `med-agent-hub:dev` Docker image from the `targets/med-agent-hub/` submodule SHA.
- **SC-005.2**: `make med-agent-hub-up` starts the container; `docker inspect` reports healthy after ≤90s.
- **SC-005.3**: Direct curl smoke against `http://localhost:8080/v1/chat/completions` with a chartsearchai-shaped body (system + chart-user + question; `response_format: {json_schema}`) returns valid `{answer, citations, blocks}` JSON. Stream variant emits OpenAI-shape SSE deltas and terminates with `data: [DONE]`.
- **SC-005.4**: After a SQL `UPDATE global_property` flips `chartsearchai.llm.remote.endpointUrl` to `http://med-agent-hub:8080/v1/chat/completions` and `chartsearchai.llm.remote.modelName` to `router` (no backend restart), a 3-turn referential chat against Zabella Halambe answers turn 2's "how many medications did you list?" with a number derived from turn 1's response. Proves priors flow through the router → subagent → LM Studio path.
- **SC-005.5**: `make cloud-deploy --with-med-agent-hub` deploys to the GCE VM; the same 3-turn smoke passes against `openmrs.openclinai.org`.
- **SC-005.6**: Rollback to direct-LM-Studio is a single SQL UPDATE (verified).
- **SC-005.7**: New architecture canvas at `specs/artifacts/canvases/med-agent-hub-bridge.canvas.tsx` captures the new path, subagent assignment, and the loss-of-prefix-cache trade-off documented honestly.

## Functional requirements

- **FR-005.1**: med-agent-hub MUST expose `POST /v1/chat/completions` with OpenAI-compat semantics: accepts `messages[]`, `response_format`, `tools`, `temperature`, `max_tokens`, `stream`. Returns `{choices:[{message:{role:"assistant",content}}], usage:{prompt_tokens,completion_tokens}, model:<chosen subagent>}`.
- **FR-005.2**: Every `/v1/chat/completions` request MUST engage the router agent (LLM classifier). No "skip routing" code path. Rationale: pointing chartsearchai at med-agent-hub for non-routed inference duplicates the LM Studio direct path with no added value.
- **FR-005.3**: The router MUST forward the FULL `messages[]` array to the chosen subagent (system message + chart prefix + prior turns + current user message). Today the router consumes a single `query` string; this MUST be rewritten.
- **FR-005.4**: The subagent's outgoing LM Studio request MUST include `response_format` when chartsearchai supplied one. Today `LLMClient.generate_chat` omits this field; this MUST be fixed.
- **FR-005.5**: Streaming MUST translate A2A's task-event stream into OpenAI-shape SSE deltas: `data: {"choices":[{"delta":{"content":"..."}}]}\n\n`. Terminate with `data: [DONE]\n\n`.
- **FR-005.6**: All legacy med-agent-hub endpoints (`/generate/orchestrator`, `/generate/medical`, `/generate/clinical`, `/chat`) MUST be deleted. Bundled `client/` and `web/` frontends MUST be deleted. Administrative agent MUST be removed. Keep `/`, `/health`, `/manifest`, `/v1/chat/completions`, `/v1/models`, `/v1/agents`.
- **FR-005.7**: chartsearchai MUST remain untouched code-wise. The only chartsearchai change is the two global-property values via SQL UPDATE.
- **FR-005.8**: med-agent-hub MUST be integrated as a git submodule at `targets/med-agent-hub/`, tracking the `harness-integration` branch of `pmanko/med-agent-hub`, following the same pattern as `targets/chartsearchai/` and `targets/chartsearchai-esm/`.
- **FR-005.9**: The container MUST log to stdout (not files) so `docker logs med-agent-hub` works.
- **FR-005.10**: med-agent-hub MUST reach LM Studio via the same `extra_hosts: host.docker.internal:host-gateway` pattern the OpenMRS backend uses — no separate tunnel, no double-routing.

## Demo patient anchor

Same as feature 004: Zabella Halambe (`dd75c020-1691-11df-97a5-7038c432aabf`), the 303-obs / 39-orders test patient from feature 002.

**3-turn referential smoke** (load-bearing for SC-005.4):
1. "What medications is this patient on?"
2. "How many medications did you list?"
3. "And what about her allergies?"

Turn 2 must answer with a number derived from turn 1's response (cannot be answered from the chart alone). Turn 3 must answer with the patient's allergy data (referential "her").

## Out of scope (explicit deferrals)

- Frontend "Answered by: <agent>" pill or any chartsearchai-esm change → feature 006.
- MCP tooling (Spark Parquet-on-FHIR analytics, FHIR search, medical literature search) feature-gated off in this POC; `SPARK_THRIFT_HOST` and `OPENMRS_FHIR_BASE_URL` are deliberately unset → feature 007.
- Skill discovery surface (`GET /v1/agents`) is declared as a stub returning the agent-card skill list, but no frontend consumes it in this feature → feature 006.
- Sticky session routing to recover the LM Studio prompt-cache hits chartsearchai relies on today → measured trade-off captured in the canvas; mitigation in a future feature.
- Administrative agent (appointment scheduling) → never; out of POC scope.
- Authentication on the med-agent-hub endpoint → med-agent-hub is internal-only on the compose bridge network, not Caddy-exposed.
- Upstream PR against any community med-agent-hub fork — there is no upstream; med-agent-hub is user-owned.

## Demo path that proves success

1. Local: `make med-agent-hub-build && make med-agent-hub-up`; container healthy; bridge curl smoke green; SQL GP flip; multi-turn referential chat passes in the harness backend; browser pass.
2. Cloud: `make cloud-deploy --with-med-agent-hub`; same smoke against `openmrs.openclinai.org`; LM Studio logs on the user's Mac show requests arriving with `messages[]` preserved and `response_format` present.
3. Rollback: SQL revert returns chartsearchai to LM Studio direct in <10s with no .omod rebuild.
