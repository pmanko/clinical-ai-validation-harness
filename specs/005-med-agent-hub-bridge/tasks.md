# Tasks: med-agent-hub bridge (005)

Phase letters mirror the approved planning file's phase numbers (`~/.claude/plans/streamed-watching-stream.md`). Cross-reference with the harness task tracker IDs (MAH.*).

## Phase 0 — Feature scaffolding (MAH.0)

- [X] 0.1 — Cut harness branch `005-med-agent-hub-bridge` from `004-chartsearchai-adapter`
- [X] 0.2 — Scaffold `specs/005-med-agent-hub-bridge/{spec,plan,tasks}.md`
- [ ] 0.3 — Cut `harness-integration` branch on `pmanko/med-agent-hub` from `main`; push
- [ ] 0.4 — Initial commit on harness branch with scaffold; push

## Phase 1 — Reboot med-agent-hub fork (MAH.1a–MAH.1e)

### 1A — Delete legacy surface (MAH.1a)

- [ ] 1A.1 — On `pmanko/med-agent-hub:harness-integration`: remove `/generate/orchestrator`, `/generate/medical`, `/generate/clinical`, `/chat` from `server/main.py`
- [ ] 1A.2 — Delete `client/`, `web/`, `Dockerfile.client`, `client-entrypoint.sh`, `nginx.conf`
- [ ] 1A.3 — Delete `server/sdk_agents/administrative_server.py`, `administrative_executor.py`, `agent_configs/administrative.yaml`
- [ ] 1A.4 — Remove the `admin` line from `Procfile.dev`
- [ ] 1A.5 — Update `README.md` to drop legacy-endpoint references
- [ ] 1A.6 — Commit "chore(reboot): drop legacy endpoints + frontends + administrative agent"; push

### 1B — Add OpenAI-compat bridge (MAH.1b)

- [ ] 1B.1 — New `server/openai_compat.py` with `POST /v1/chat/completions` (sync + stream), `GET /v1/models`, `GET /v1/agents`
- [ ] 1B.2 — Pydantic request model mirrors OpenAI shape (`messages[]`, `response_format?`, `tools?`, `temperature?`, `max_tokens?`, `stream?`)
- [ ] 1B.3 — Sync handler: translate request → A2A router invocation; wrap final artifact in `{choices, usage, model:"router"}` shape
- [ ] 1B.4 — Stream handler: emit OpenAI SSE deltas as A2A task events arrive; terminate with `data: [DONE]\n\n`
- [ ] 1B.5 — Mount on the main FastAPI app in `server/main.py`
- [ ] 1B.6 — Tests in `tests/test_openai_compat.py` (sync, stream, schema validation, error paths)
- [ ] 1B.7 — Commit "feat(bridge): OpenAI-compat /v1/chat/completions + /v1/models + /v1/agents"; push

### 1C — Rewrite router for messages[] (MAH.1c)

- [ ] 1C.1 — `server/sdk_agents/router_executor.py`: read `messages[]` from inbound A2A message metadata
- [ ] 1C.2 — Use LAST user-role message content as the routing query (preserves the existing classification prompt)
- [ ] 1C.3 — Forward FULL `messages[]` array to chosen subagent via dispatched A2A message metadata
- [ ] 1C.4 — Test `tests/test_router_messages_passthrough.py` asserting system+chart+priors+current all preserved end-to-end
- [ ] 1C.5 — Commit "feat(router): forward full messages[] to chosen subagent"; push

### 1D — Wire response_format + streaming (MAH.1d)

- [ ] 1D.1 — `server/llm_clients.py`: include `response_format` in outgoing LM Studio body; add `stream=true` generator
- [ ] 1D.2 — `server/sdk_agents/medical_executor.py`: accept `response_format` from inbound metadata; forward to LLMClient
- [ ] 1D.3 — `server/sdk_agents/clinical_executor_v2.py`: same
- [ ] 1D.4 — Test: outgoing LM Studio body includes `response_format` when supplied
- [ ] 1D.5 — Commit "feat(llm): forward response_format + streaming through subagents"; push

### 1E — Logging + green tests (MAH.1e)

- [ ] 1E.1 — `launch_a2a_agents.py`: drop file-redirect for subprocess stdout/stderr; let it stream to docker stdout
- [ ] 1E.2 — `poetry run pytest` green
- [ ] 1E.3 — `honcho -f Procfile.dev start` launches all four processes (web+router+medical+clinical) cleanly against local LM Studio
- [ ] 1E.4 — Commit "chore(logging): stdout logging for containerized deploy"; push

## Phase 2 — Containerize (MAH.2)

- [ ] 2.1 — Rewrite `Dockerfile.server` → `Dockerfile` (single image, multi-stage poetry install)
- [ ] 2.2 — `CMD ["honcho", "-f", "Procfile.dev", "start"]`; `HEALTHCHECK CMD curl -fsS http://localhost:8080/health`; `EXPOSE 8080`
- [ ] 2.3 — `docker build -t med-agent-hub:dev targets/med-agent-hub/` succeeds; container starts; `/health` returns 200
- [ ] 2.4 — Commit "feat(docker): single-image build with honcho + healthcheck"; push

## Phase 3 — Harness submodule + compose + Makefile + env (MAH.3)

- [ ] 3.1 — `git submodule add -b harness-integration https://github.com/pmanko/med-agent-hub.git targets/med-agent-hub`
- [ ] 3.2 — `compose/openmrs-2.8-refapp.yml`: new `med-agent-hub:` service entry (build context, env, extra_hosts, healthcheck)
- [ ] 3.3 — `.env.med-agent-hub.example` and `.env.med-agent-hub.cloud.example` with sane defaults; `.gitignore` `.env.med-agent-hub`
- [ ] 3.4 — `Makefile` targets: `med-agent-hub-build`, `med-agent-hub-up`, `med-agent-hub-logs`, `med-agent-hub-restart`
- [ ] 3.5 — `scripts/cloud-deploy.sh`: optional `--with-med-agent-hub` flag for image rebuild + restart on VM
- [ ] 3.6 — Commit "feat(harness): med-agent-hub submodule + compose + Makefile + env"; push

## Phase 4 — Local end-to-end smoke (MAH.4)

- [ ] 4.1 — `make med-agent-hub-build` succeeds; `make med-agent-hub-up` health-checks green
- [ ] 4.2 — Direct curl smoke (sync) against `localhost:8080/v1/chat/completions` with chartsearchai-shaped body; assert `{answer, citations, blocks}` parses
- [ ] 4.3 — Stream variant: assert SSE deltas arrive + `data: [DONE]` terminates
- [ ] 4.4 — SQL GP flip on local: `chartsearchai.llm.remote.endpointUrl` → `http://med-agent-hub:8080/v1/chat/completions`; `chartsearchai.llm.remote.modelName` → `router`. No backend restart.
- [ ] 4.5 — 3-turn referential smoke against Zabella: T1 "meds?", T2 "how many did you list?", T3 "and her allergies?". T2 must answer numerically against T1's content.
- [ ] 4.6 — Browser visual pass
- [ ] 4.7 — Capture per-turn latency for the canvas doc

## Phase 5 — Cloud deploy + smoke (MAH.5)

- [ ] 5.1 — `make cloud-deploy --with-med-agent-hub` (image build local + rsync + restart on VM)
- [ ] 5.2 — Verify container healthy on the VM
- [ ] 5.3 — Cloud SQL GP flip (same shape as Phase 4)
- [ ] 5.4 — Cloud 3-turn smoke against `openmrs.openclinai.org`
- [ ] 5.5 — Inspect LM Studio logs on the user's Mac to confirm requests arrive from med-agent-hub with `messages[]` preserved + `response_format` present
- [ ] 5.6 — Verify rollback: SQL revert returns chartsearchai to LM Studio direct in <10s

## Phase 6 — Docs (MAH.6)

- [ ] 6.1 — Write `specs/artifacts/canvases/med-agent-hub-bridge.canvas.tsx`: architecture diagram, subagent assignment, request-response flow, decision matrix, measured per-turn latency, prefix-cache trade-off
- [ ] 6.2 — Update `specs/artifacts/README.md` to list the new canvas
- [ ] 6.3 — Update `specs/roadmap.canvas.tsx` to reflect feature 005 shipping
- [ ] 6.4 — Update this `tasks.md` to mark everything done; finalize `spec.md` + `plan.md` with measured numbers
