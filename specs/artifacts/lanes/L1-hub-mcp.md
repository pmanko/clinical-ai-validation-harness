# L1 — med-agent-hub MCP-ification

**Status**: Ready — worktree created; `hub-ci` green on hub `main`.
**Repo**: `pmanko/med-agent-hub` — our own repo. Branch model: feature branch → PR → `hub-ci` green → `main` → harness pin bump. (The `harness-integration` buffer was retired 2026-06-11; do NOT recreate it here.)
**Branch / worktree**: `feat/real-mcp-tools` (off hub `origin/main` @ `ebdbb43`) · `~/code/hub-wt-mcp`
**Brief**: [`hub-mcp-tools-brief.md`](hub-mcp-tools-brief.md) (QA-locked architecture) · **Index**: [`dev-roadmap.md`](dev-roadmap.md)

## What & why
Replace the hub's hand-rolled tool dispatch and the homegrown fake-"MCP" layer with **one valid
FastMCP server mounted at `/mcp`**. `kb_search` becomes a real MCP tool; `medical_expert` stays an
in-process role (not a tool); the team consumes the server via an in-memory client (no network hop).
The tool surface is hub-global and extensible (FHIR/Spark drop in later) and becomes a product surface
other MCP clients can consume — not just chartsearchai. See the brief for the full architecture.

## Scope
**In:**
- FastMCP server mounted at `/mcp` (streamable-HTTP for external clients); team consumes it in-memory.
- `kb_search` → real MCP tool; delete the homegrown `server/mcp/` + the unwired A2A clinical tools (FHIR/Spark/appointments/medical_search, all mock).
- Delete legacy modules per the brief's deletion list: `server/sdk_agents/`, `server/agent_configs/`, `server/llm_clients.py`, `explore_a2a.py`, `launch_a2a_agents.py`, and the dead A2A/MCP tests.
- Sweep the 5 pre-reboot hub origin branches (`a2a-updates`, `doc-cleanup-update`, `feature/agenta`, `multiagent`, `rag-augment`): quick triage, **default delete** (tag `archive/<branch>` only if something is genuinely worth keeping). Expected end state: hub origin has `main` only.

**Out:** FHIR/Spark as real MCP tools; per-client tool subsets / `/mcp` auth; parallelization; the stale hub `docs/` tree refresh (all noted in the brief's §5).

## Merge gate (hub-ci)
- `hub-ci` green (unit-and-contract + docker-build).
- `tests/test_bridge.py` (the `/v1` OpenAI-compat contract both chartsearchai and the harness consume) green at **every** commit.

## Pin-bump gate (hub-boundary smoke — runs AFTER the hub PR merges)
Rebuild the container → run the hub README's `/v1/chat/completions` curl with real local models
(`med-agent-team-low`) → a `-validated` level returns the `confidence` block and `trace.jsonl` gains a
line → **then** push the harness pin bump (`.gitmodules` already tracks hub `main`). The integrated
chartsearchai→hub path smoke is deliberately NOT here — it belongs to L4; until then the chat UI is the
manual check.

## Kickoff prompt (verbatim)
> Execute the approved MCP plan in `specs/artifacts/planning/hub-mcp-tools-brief.md` in this worktree
> (med-agent-hub, branch `feat/real-mcp-tools` off `origin/main`). Red-first tests for the new MCP tool
> surface; `tests/test_bridge.py` (/v1 contract) must stay green throughout; delete the legacy A2A/
> fake-MCP modules per the brief's deletion list. First, sweep the 5 legacy origin branches per the
> quick-triage-default-delete rule. PR to hub `main` gated by `hub-ci`; after merge, rebuild the
> container and run the hub-boundary smoke (README /v1 curl with real models + `-validated` confidence
> block + `trace.jsonl` growth) before pushing the harness pin bump.
