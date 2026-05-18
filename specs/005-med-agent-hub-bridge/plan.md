# Plan: med-agent-hub bridge (feature 005)

**Branch**: `005-med-agent-hub-bridge`, cut from `004-chartsearchai-adapter`.
**Source of truth**: see also the approved planning file at `~/.claude/plans/streamed-watching-stream.md` from the planning session. The plan there is authoritative; this file captures durable architectural decisions for the spec record.

## Architectural decisions

### D1 — med-agent-hub is the OpenAI-compat peer of LM Studio

chartsearchai's `RemoteLlmEngine` reads `chartsearchai.llm.remote.endpointUrl` at every inference call (call-time, not boot-time), so any OpenAI-compat backend is a peer of LM Studio. med-agent-hub slots into that peer position: chartsearchai treats it as just-another-LLM, and med-agent-hub does the agent-team routing internally before reaching LM Studio.

```
chartsearchai (Java, .omod)
   │  POST /v1/chat/completions   (unchanged wire shape)
   ▼
med-agent-hub:8080  (new harness submodule, Python FastAPI)
   │  ── always engages the LLM-classifier router
   │  ── router picks {medical, clinical}
   │  ── subagent receives full messages[] (chart prefix + conversation tail)
   │  POST /v1/chat/completions
   ▼
LM Studio  (same path med-agent-hub and chartsearchai both use)
```

### D2 — Always route. No "skip routing" path.

Every request to med-agent-hub's `/v1/chat/completions` engages the router agent (LLM classifier). The rationale: pointing chartsearchai at med-agent-hub *for non-routing inference* duplicates the LM Studio direct path with no added value. If a clinician question doesn't benefit from team routing, the right answer is to flip chartsearchai's GP back to LM Studio direct — not to add a bypass in med-agent-hub.

### D3 — Subagent dispatch preserves the full `messages[]` array

chartsearchai sends `system + chart-snapshot-user + prior turns + current-user`. The router agent classifies on the LAST user-role message content, but forwards the entire `messages[]` array to the chosen subagent. The subagent's LM Studio request is structurally identical to what chartsearchai would send directly — just from a different origin.

Today's `router_executor.RouterAgentExecutor.execute()` extracts a single `query` string (router_executor.py:138) and the subagent dispatch passes only that string forward. This is the load-bearing rewrite on the med-agent-hub side.

### D4 — `response_format` and `stream` forward through end-to-end

chartsearchai sends a `response_format: {type: json_schema, schema: {answer, citations, blocks}}` envelope. The bridge MUST forward this through the router → subagent → LM Studio path, and the subagent's outgoing LM Studio request body MUST include the field. Today `LLMClient.generate_chat` omits `response_format`; this MUST be fixed.

Streaming: the bridge implements SSE on `/v1/chat/completions`, emitting OpenAI-shape `data: {"choices":[{"delta":{"content":"..."}}]}\n\n` chunks as the subagent's LM Studio stream produces tokens, terminating with `data: [DONE]\n\n`.

### D5 — Subagent scope: web + router + medical + clinical only

POC drops the administrative agent (appointment scheduling, needs OpenMRS REST tokens, not load-bearing for chart QA). Drops the bundled `client/` and `web/` Svelte/JS frontends (they consumed the legacy `/chat` endpoint we're removing). Result: one container running web (FastAPI on 8080) + router (uvicorn 9100) + medical (uvicorn 9101) + clinical (uvicorn 9102) via honcho.

### D6 — Single Docker image, honcho inside, stdout logs

Container packaging is one image with `CMD ["honcho", "-f", "Procfile.dev", "start"]`. Only port 8080 is exposed externally; internal ports 9100-9102 stay inside the container. `launch_a2a_agents.py`'s file-based logging is dropped in favor of stdout so `docker logs med-agent-hub` works.

### D7 — Internal-only networking; no Caddy route

The OpenMRS backend container reaches med-agent-hub by service name on the shared compose bridge network: `http://med-agent-hub:8080/v1/chat/completions`. No Caddy upstream needed; med-agent-hub is private to the stack. If we ever expose it externally (for an agent-test tool), add a Caddy route then.

### D8 — LM Studio access mirrors chartsearchai backend's pattern

med-agent-hub container gets `extra_hosts: host.docker.internal:host-gateway` (mirrors `compose/openmrs-2.8-refapp.yml:131-136`). Its `LLM_BASE_URL` env defaults to `http://host.docker.internal:1234/v1` on local; on cloud, the LM Link tunnel resolves the same address. Single LM Studio instance, no double-tunnel.

### D9 — Environment scoping: separate `.env.med-agent-hub`

Keeps med-agent-hub's 12-15 env vars out of `.env.chartsearch`. Loaded by compose for the `med-agent-hub:` service only. `chartsearchai.llm.remote.endpointUrl` becomes the *only* coupling between the two modules — no shared env.

### D10 — chartsearchai code untouched; runtime config only

Two SQL `UPDATE global_property` statements (endpoint URL + model name) flip chartsearchai onto the new path. No `.omod` rebuild, no module restart, no schema migration. Rollback is the same two UPDATEs in reverse. Verified by RemoteLlmEngine.java:56 reading the endpoint URL at call time.

### D11 — Submodule pattern mirrors chartsearchai / chartsearchai-esm

`targets/med-agent-hub/` is a git submodule tracking `pmanko/med-agent-hub` branch `harness-integration`. Same pinning principle as the other two submodules: fork branches consolidate every pending change so the harness pin is one ref. There is no upstream community to PR back to; med-agent-hub is user-owned.

## Trade-offs accepted (will document in the canvas)

1. **Prefix-cache loss**: The router can route different turns of the same chat session to different subagents (different LMs). The chart-snapshot prefix won't cache on the LM Studio side across turns. POC accepts this cost; sticky-session routing is a future feature.
2. **Cold-start latency**: med-agent-hub adds one LLM hop (router classification) per turn. Adds 1-2s. Instrument timing in Phase 4 to know the cost.
3. **Two LM Studio model loads**: med-agent-hub wants llama-3.1-8b (orchestrator) + medgemma-1.5-4b (medical) + gemma-3-4b (clinical) loaded simultaneously. User's M5 Pro likely fits all three at 32K context; verify before cloud deploy.
4. **PHI in med-agent-hub logs**: chart-snapshot user message contains PHI. Ensure logging doesn't dump full `messages[]` bodies at INFO level; drop to DEBUG or scrub before Phase 5 cloud deploy.

## Out-of-scope rationale (one-liners)

- Frontend "Answered by: <agent>" pill — adding it now couples this feature to ESM submodule changes and slows the agent-team-on-the-backend smoke. Feature 006.
- MCP / Spark / FHIR tool integration — orthogonal to the routing contract; feature-gated off (env vars unset) so the agents run as pure LLM passthroughs in POC. Feature 007.
- Sticky session routing — needs router-side session state, which requires either a Redis dep or in-memory state with non-trivial lifecycle. Defer until measured prefix-cache loss is shown to actually hurt UX.
- Upstream PR against med-agent-hub — no upstream community exists.

## Risks identified during planning

| # | Risk | Mitigation |
|---|---|---|
| R1 | A2A SDK doesn't cleanly expose a message-metadata channel to attach `messages[]` + `response_format` | Phase 1 decision; fallback is encoding the full payload as JSON inside the A2A message body |
| R2 | SSE delta translation: A2A task events ↔ OpenAI SSE chunks | Phase 1 — extra care; chartsearchai's SSE consumer is unforgiving of malformed `data:` lines |
| R3 | Routing latency on simple "what meds is this patient on?" queries | Phase 4 instrumentation captures per-turn timing; documented in the canvas |
| R4 | LM Studio model-load capacity on the user's Mac when 3 models needed simultaneously | Verify in Phase 5 before cloud deploy; fallback is sharing models across subagents (medgemma for both medical and clinical) |
| R5 | PHI leakage in container logs | Audit log statements during Phase 1; assert at DEBUG only before Phase 5 cloud |
| R6 | Prefix-cache loss makes follow-up latency worse than today's direct path | Instrument in Phase 4; if material, consider exposing sticky-session as an env-gated alpha feature in a follow-up |
