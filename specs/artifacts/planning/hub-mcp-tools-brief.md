# Hub MCP Tools — Source Brief

**Status**: Source brief — QA-locked architecture for lane **L1** (med-agent-hub MCP-ification).
**Roadmap entry**: realizes the real-MCP tool layer F008 anticipates; extends F005.
**Repo**: `pmanko/med-agent-hub` (own repo — feature branch → PR → `hub-ci` green → `main` → harness pin bump).
**Companion dossier**: [`docs/lanes/L1-hub-mcp.md`](../../../docs/lanes/L1-hub-mcp.md).
**Last updated**: 2026-06-14.

This is the authoritative architectural brief for replacing med-agent-hub's hand-rolled tool
layer with a real MCP server. The decisions below are QA-locked — do not revise them without
explicit user direction.

---

## 1. Problem framing

med-agent-hub runs an in-process "team" (orchestrator → tools → synthesis/validation) behind an
OpenAI-compat `/v1/chat/completions`. Its tool surface is **hand-rolled**: `_tool_definitions()`
plus a hardcoded `if name == "kb_search"/"medical_expert"` dispatch switch in `server/team.py`.

Separately, `server/mcp/` is a **homegrown abstraction named "MCP" that is not the Model Context
Protocol** (no `mcp`/`fastmcp` dependency, no transport, just an abstract `MCPTool` base). It
carries A2A-era clinical-data tools (FHIR, Spark population/longitudinal, appointments, a
placeholder medical-search) that are **unwired, return mock data, and were only ever called by the
deleted A2A `clinical_executor`**.

**Goal**: replace the hand-rolled tool layer with a **real, valid MCP server** that is (a) the
standard interface for the team's genuine tool calls, (b) **extensible** so FHIR/Spark/etc. drop in
later, and (c) a **product surface other MCP clients can consume**, not just chartsearchai. Delete
the old fake-MCP / A2A clinical tools.

### Decisions locked (from QA)

- **Only genuine tools get MCP.** `kb_search` → MCP tool. `medical_expert` is an LLM role/sub-agent,
  not a tool → **stays in-process** (A2A territory if it ever becomes its own service; not MCP).
- **Tool surface is hub-global, not level-dependent.** Levels keep choosing only models/prompts/
  validator. No `mcp_servers` field on `Level`.
- **Delete the homegrown `server/mcp/`** + FHIR/Spark/appointment/medical_search, but design the new
  MCP layer to be extended with those later.
- **Topology: one FastMCP server mounted into the hub's FastAPI process** (streamable-HTTP at `/mcp`
  for external clients); the team consumes it via an **in-memory client** (no network hop).
  Sidecar/multi-server is a future additive step (e.g. PHI-isolated FHIR), not now. stdio rejected
  (can't serve external clients).

---

## 2. Target architecture

```
            ┌──────────────────── med-agent-hub (one FastAPI process) ────────────────────┐
chartsearchai┤ POST /v1/chat/completions → team.run_team()                                 │
(OpenAI shape)│                               │ in-memory MCP Client(mcp) (list/call_tool) │
            │                                 ▼                                            │
other MCP  ─┤ GET/POST /mcp (streamable-HTTP) ── FastMCP server `mcp` ──tools──▶ kb_search │
clients     │      (external consumers)                                  (+ fhir/spark later)│
            └──────────────────────────────────────────────────────────────────────────────┘
```

Three actors: **(1)** the FastMCP server = the extensible tool catalog; **(2)** the team = one
in-process client that offers a *subset* (`kb_search`) to its orchestrator and keeps `medical_expert`
in-process; **(3)** external clients = other agents/apps hitting `/mcp`.

---

## 3. Implementation

### 3.1 Dependency (`pyproject.toml`)
- Add `fastmcp` (standalone package; bundles the `mcp` SDK). Imports: `from fastmcp import FastMCP`,
  `from fastmcp.client import Client`, `from fastmcp.utilities.lifespan import combine_lifespans`.
- Drop deps that only served the deleted code: `a2a-sdk`, `jsonschema` (old `mcp/base.py`), and the
  `spark`/`duckdb` extras (`PyHive`, `thrift`, `thrift_sasl`, `pure-sasl`, `duckdb`). Keep `PyYAML`,
  `httpx`, `psutil`, etc.

### 3.2 New MCP server (`server/mcp/` rebuilt)
- **Delete** old contents: `base.py`, `fhir_tool.py`, `spark_tools.py`, `appointment_tool.py`,
  `medical_search_tool.py`, `config/spark_profiles/*`.
- `server/mcp/server.py` — define `mcp = FastMCP("med-agent-hub-tools")` and register `kb_search`
  with `@mcp.tool`. Its body is the current `team._run_kb_search` logic (BM25 over `server.kb.search`),
  returning the **same formatted string** that starts with `_KB_BLOCK_HEADER` on a hit / the same
  abstain string on miss — the contract the team relies on. Tool description = the rich one currently
  inline in `_tool_definitions()` (keep the trigger-keyword/ordering/example text — good ACI).
- `server/mcp/tools/` (optional now, recommended for extensibility) — one module per future tool
  domain (`fhir.py`, `spark.py`) registering `@mcp.tool`s on the shared `mcp` instance. Adding a tool
  = add a function; the catalog and external clients pick it up automatically.
- `server/mcp/client.py` — team-facing helpers over an in-memory `Client(mcp)`:
  - `openai_tool_defs(only: list[str]) -> list[dict]`: `await client.list_tools()` → convert MCP tool
    schema → OpenAI `{"type":"function","function":{name,description,parameters}}`, filtered to `only`
    (the team passes `["kb_search"]`). Cache per process (catalog is static).
  - `call(client, name, args) -> str`: `await client.call_tool(name, args)`, extract text content to
    the observation string the loop expects.

### 3.3 Wire the team to MCP (`server/team.py`)
- Replace `_tool_definitions(has_expert)` so it returns **MCP-sourced defs for the team's tool subset
  (`kb_search`) + the in-process `medical_expert` def** (kept verbatim) when `has_expert`.
- In `run_team`, open the in-memory client alongside the existing `httpx.AsyncClient`
  (`async with Client(mcp) as mcp_client:` around the tool loop).
- In the dispatch loop: if the tool name is an **MCP tool** → `observation = await mcp.client.call(
  mcp_client, name, args)`; **elif** `medical_expert` → existing `_run_medical_expert(...)` (unchanged,
  still receives `kb_context` in-code). Preserve **all** existing behavior:
  - `_KB_BLOCK_HEADER` detection → `kb_context` accumulation (the MCP tool returns the same header).
  - dedup of identical calls; `(unknown tool)` branch.
  - the **fallback** deterministic kb_search when nothing was gathered → route through
    `mcp.client.call(... "kb_search" ...)`.
  - **fail-open**: an MCP tool error must yield the "(knowledge base unavailable...)" observation,
    never abort the turn.
  - the **trace step schema** (`{"role":"kb_search",...}` / `{"role":"medical_expert",...}`) unchanged
    — the live dashboard correlates on it; do not rename roles.
- `_run_kb_search` moves into the MCP tool; remove the dead copy (or have the tool import it).

### 3.4 Mount the server (`server/main.py`)
- `from server.mcp.server import mcp`; `mcp_app = mcp.http_app(path="/mcp")`; construct
  `app = FastAPI(..., lifespan=mcp_app.lifespan)` (use `combine_lifespans` if a hub lifespan is ever
  added); `app.mount("/mcp", mcp_app)`. Keep `/`, `/health`, and the OpenAI router. External clients
  reach `http://<hub>:8080/mcp`.

### 3.5 Companion deletion (coupled A2A legacy — can be a separate commit, same PR)
The old `server/mcp/` is imported only by the unwired A2A `sdk_agents`; deleting one wants the other
gone too. Remove: `server/sdk_agents/`, `server/agent_configs/`, `launch_a2a_agents.py`, and the dead
tests `tests/{test_a2a_sdk,test_router_a2a,test_react_orchestrator,test_models_direct,
test_mcp_integration,test_mcp_tools_direct}.py`. Trim the now-unused A2A/Gemini/FHIR/Spark config
blocks in `server/config.py`. (None are imported by the live `main→openai_compat→team` path — verified.)
Also delete `server/llm_clients.py` and `explore_a2a.py` per the legacy sweep.

### 3.6 Tests
- Mirror the existing pytest style (`tests/test_kb.py`). Add `tests/test_mcp_server.py`: with an
  in-memory `Client(mcp)`, assert `list_tools()` contains `kb_search` with the expected input schema;
  `call_tool("kb_search", {...})` returns a `_KB_BLOCK_HEADER` block on a known hit and the abstain
  string on a miss.
- Add/extend a team test proving the orchestrator loop still drives `kb_search` through MCP and threads
  `kb_context` into `medical_expert` (the parity that must not regress).

---

## 4. Verification (red→green, then end-to-end)
1. `poetry install` (picks up `fastmcp`, drops a2a/spark).
2. `poetry run pytest tests/test_mcp_server.py tests/test_kb.py tests/test_team_roles.py -v` — MCP
   server + team tool-loop parity.
3. **In-memory**: a scratch `async with Client(mcp)` → `list_tools()` shows `kb_search`; `call_tool`
   returns the KB block. (Proves valid MCP.)
4. **External HTTP**: `poetry run uvicorn server.main:app --port 8080`; from a separate `fastmcp`
   `Client("http://localhost:8080/mcp")`, `list_tools()` + `call_tool("kb_search", ...)` succeed.
   (Proves the multi-client product surface.)
5. **End-to-end team**: `POST /v1/chat/completions` with `model: med-agent-team-med` and a chart+
   question; confirm the orchestrator calls `kb_search` (now via MCP), synthesis returns a valid
   envelope, and a `trace.jsonl` line with a `kb_search` step is written (dashboard unbroken).
6. **Harness regression**: run one level via the harness against a known question; confirm KB grounding
   parity with pre-change output.

The regression gate throughout: `tests/test_bridge.py` (the `/v1` OpenAI-compat contract that both
chartsearchai and the harness consume) stays green at **every** commit.

---

## 5. Out of scope / future (noted, not built now)
- **FHIR/Spark as real MCP tools** — add `@mcp.tool` modules when a use case lands; likely a **sidecar**
  FastMCP server for PHI isolation, at which point the team's client gains a small **multi-server**
  config (additive — the in-memory local server stays).
- Per-client tool subsets / auth on `/mcp`; publishing the hub port for clients outside the compose
  network (today the harness exposes no host port — internal `med-agent-hub:8080` only).
- Parallelization (explicitly deferred — sequential is fine for now).
- Stale `docs/` tree + `README` project-structure refresh — recommended companion, separate change.
