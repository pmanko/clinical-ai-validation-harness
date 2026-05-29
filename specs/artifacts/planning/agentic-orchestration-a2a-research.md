# Agentic orchestration + A2A: deep-research findings (decision input)

> Deep-research workflow `whwfxdsiy` (103 agents, 21 sources fetched, 94 claims → 25 verified via 3-vote adversarial check → 22 confirmed / 3 refuted → 6 synthesized findings). Primary sources: A2A spec, Anthropic "Building Effective Agents", Linux Foundation, Google, Berkeley BFCL, arXiv. **This contradicts the round-2 roadmap decision (keep A2A + ReAct loop) — see "Conflict" below.**

## Bottom line

**REPLACE A2A as the foundation for the in-house med-agent-hub team. Standardize on MCP-for-tools + a light DETERMINISTIC workflow. Keep A2A only as a deferred future seam (adopt the day an agent becomes remote / cross-vendor / independently lifecycle-managed).**

## Findings (all high-confidence unless noted)

1. **A2A is mismatched in-house.** A2A is purpose-built for cross-vendor/cross-org collaboration between **opaque, independently-owned agents that deliberately do NOT share memory, tools, or context** over network boundaries ("internal workings, memory, or tools are not exposed", A2A key-concepts; "to preserve data privacy and IP", IBM). That's the *opposite* of an in-house team of local models inside one service the orchestrator owns and wants to observe. Vendor guidance is explicit: *"In-process composition works well when all agents live in the same application, share the same runtime, and are maintained by the same team. A2A is designed for when agents need to cross boundaries"* (Microsoft Learn); for in-process sub-agents *"A2A's network overhead and serialization would be counterproductive"* (Google ADK). → Don't model the KB or the medical-expert as A2A peers.

2. **MCP is the load-bearing standard here.** The de-facto mid-2026 split: **MCP = vertical (agent→tools/data), A2A = horizontal (agent→peer agents)** — "complements, not alternatives" (Google, LF, IBM, A2A spec). The KB FTS5/BM25 lookup is a textbook MCP tool; the single-call, stateless medical-expert is also tool-like ("A2A is about agents *partnering*; MCP is about agents *using capabilities*", a2a spec). For a few agents + a KB tool, **MCP + light orchestration is sufficient.**

3. **Use a deterministic WORKFLOW, not an autonomous ReAct loop.** Anthropic: workflows (predefined code paths) for well-defined tasks with predictable steps; autonomous agents for open-ended problems where steps can't be predicted. Our pipeline (orchestrator → medical-expert + KB → synthesize → strict JSON envelope) has **predictable, fixed subtasks** → a fixed workflow beats a dynamic agentic loop. "Find the simplest solution; add complexity only when it demonstrably improves outcomes; reduce abstraction layers; build with basic components."

4. **Small-model tool-calling: minimize hops, invest in tool design, lean on the JSON envelope.** Berkeley BFCL (V4, Apr 2026) + FunReason-MT: single-turn calls are reliable, but **multi-step agentic chaining materially degrades — worse for 4-8B models** (error compounds across turns). Mitigation (grounded): **strict JSON-schema / constrained decoding closes much of the small-model gap** — which med-agent-hub already uses (the `chart_answer` envelope). → argues against a deep ReAct loop with many small-model tool decisions. (The specific "ReAct chaining is risky" claim passed 2-1: elevated but addressable, not fatal.)

5. **Simple-but-expandable: commit to two seams now, defer A2A.** Commit NOW to (a) the **OpenAI-compat `/v1/chat/completions` + strict JSON envelope** (the chartsearchai consumer contract) and (b) an **MCP tool interface** for the KB (and future tools). **Defer A2A agent cards/executors** until an agent crosses a boundary — they compose cleanly later (an A2A agent can internally use MCP). Smallest sound foundation: one deterministic orchestrator → a medical-expert model call + an MCP KB tool → synthesize to the envelope.

6. **Ecosystem momentum (medium confidence):** both MCP and A2A are now Linux Foundation projects (durability signal); A2A passed 150+ orgs in year one. Bet on MCP-for-tools now; treat A2A as the future cross-boundary standard. BFCL V4 is the yardstick to track small-model tool-calling.

## Caveats (honest)

- **Framework comparison is UNANSWERED.** Zero surviving claims evaluated LangGraph / Google ADK / AutoGen-AG2 / OpenAI Agents SDK / CrewAI / Pydantic-AI / LlamaIndex. Only Anthropic's "start simple, hand-roll, reduce abstraction" survived — which *directionally* favors hand-rolling on MCP now over a heavyweight framework, but is **not** a framework comparison. A dedicated follow-up is needed before betting on a framework.
- **Boundary blur:** the MCP/A2A split is the convention, but A2A's spec admits an A2A agent can expose MCP-compatible resources and a stateful MCP server can act agent-like. Refines, doesn't overturn, the in-house recommendation.
- **Time-sensitive:** fast-moving field; framework momentum especially will churn — revisit before a larger build-out.

## Open questions

1. Which framework (if any) vs hand-roll on MCP? Needs a dedicated evaluation.
2. What is gemma-4 / medgemma-1.5-4b's *actual measured* tool-calling reliability on our exact MCP KB-lookup surface (single-turn, constrained decoding)? Probe needed.
3. Will mid/late-2026 convergence shift build-vs-buy before we scale?
4. Concrete migration path from in-house MCP/workflow → A2A agent cards when an agent first crosses a boundary.

## Reconciled decision (with user, 2026-05-28)

The research recommended deterministic-only orchestration + MCP-for-tools. The user refined it on two axes; the settled decision is:

1. **Orchestrator = a PLUGGABLE strategy behind the OpenAI-compat boundary**, selected per-request via the `model` id and **compared empirically in the 006 validation harness**:
   - `team-deterministic` — **the documented default** (fixed: KB lookup? → medical-expert → gemma-4 synthesize → envelope). Lowest latency, lowest small-model tool-calling risk.
   - `team-react` — gemma-4 ReAct loop, **kept as an option** for open-ended / multi-hop clinical questions (the research's "predictable pipeline" assumption does not always hold — clinical questions can be open-ended).
   - `team-cloud` — orchestration delegated to a frontier cloud agent (Claude/GPT) over the **same** tool interface; the top-shelf comparison baseline.
   - "Strong guidance on the default" = deterministic by default, with the harness measuring the tradeoff per question-type rather than asserting it.

2. **Tool layer = a clean typed tool INTERFACE now, NOT the MCP protocol yet.** The KB is a plain `kb.search(query) -> snippets` function (a direct API/CLI/SQL call); the medical-expert is just an OpenAI-compat call. Grounded by Anthropic "Code execution with MCP" (tool-def + intermediate-result bloat; 150k→2k tokens / 98.7% via code-over-tools; "direct tool calls remain appropriate for simpler scenarios") and Cloudflare "Code Mode" ("LLMs are better at writing code to call MCP than calling MCP directly"; MCP earns its keep at scale + uniformity). We have neither the scale nor the chaining pain points, so the **protocol is deferred**; MCP / code-mode is the seam we adopt when tools multiply or are consumed by external agents.

3. **A2A deferred** (unchanged from the research) — adopt only when an agent crosses a boundary (remote / cross-vendor / independently lifecycle-managed).

The two durable seams to commit to now: the **OpenAI-compat `/v1/chat/completions` + strict JSON envelope** (consumer + orchestrator-strategy selector) and the **typed tool interface** (KB + future tools). Everything else (MCP protocol, A2A cards, framework choice) is a deferred seam.

Supersedes the round-2 roadmap §2 ("keep A2A + ReAct loop + KB as A2A agent"). §2 to be rewritten to this.

## Key sources

- A2A↔MCP: https://a2a-protocol.org/latest/topics/a2a-and-mcp/ · https://a2a-protocol.org/latest/topics/key-concepts/
- Anthropic, Building Effective Agents: https://www.anthropic.com/research/building-effective-agents
- LF A2A press: https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-...
- Google A2A launch: https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- Berkeley BFCL: https://gorilla.cs.berkeley.edu/leaderboard.html · PMLR v267 patil25a
- FunReason-MT: https://arxiv.org/pdf/2510.24645 · ACI/SWE-agent: arXiv 2405.15793
- MCP criticism (tool layer): Anthropic "Code execution with MCP" https://www.anthropic.com/engineering/code-execution-with-mcp · Cloudflare "Code Mode" https://blog.cloudflare.com/code-mode/
