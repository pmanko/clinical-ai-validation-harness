# Agent collaboration playbook — long, exploratory, iteration-driven threads

For working with a coding agent on **exploratory, innovative work that builds step-on-step** — the
opposite of pre-decomposed tickets. Rooted in the sources at the bottom, and in a concrete failure
(see "Worked example").

## The one law
**The code (and the running system) is the only ground truth.** Everything the agent carries —
conversation, summaries, this doc, memory, task lists, prior demo videos — is *narrative* or a
*downstream effect* of the code. An LLM has no world-model to weight these by, so a stale sentence
("the frontend is finished") gets the same credence as freshly-read code unless grounding is enforced.
So: **verify claims against code; never trust narrative over it.**

## 1. Keep the long thread — the problem is never "too much context," it's *ungrounded* context
- Long exploratory threads that accumulate context are good and worth preserving. Do **not** clear/compact
  as a strategy — compaction is **lossy** ("loss of subtle but critical context whose importance only
  becomes apparent later"), and clearing forces re-stating everything, which kills the build-on-last-step value.
- The real fix for drift is **grounding at boundaries**: the moment work crosses into a file/module the
  agent hasn't actually read *in this thread*, it reads that code before acting. Everywhere else, build
  freely on the accumulated context.

## 2. Offload durable state to artifacts — don't rely on the window to "remember"
- Shift from *remember everything* → *know where to find it*. Persist decisions, the current map, open
  questions to **files the agent re-reads** (a living handoff/notes doc, `CLAUDE.md`, the memory dir),
  and reference code by **path + symbol** (just-in-time retrieval), not by re-pasting.
- This is what makes a long effort survive compaction/new sessions: the truth lives in artifacts, so the
  conversation can be lossy without the *work* losing state.

## 3. Exploratory work: spikes + tight feedback loops, not upfront decomposition
- You can't (and shouldn't) pre-plan innovative work. Use **spikes** (small investigative probes) and a
  **tight loop**: one grounded change → verify → record what was learned → next. Structure emerges.
- Still define **"done" as a verifiable acceptance test**, even when the path is unknown ("the demo shows
  X and the assertion passes"). A demo/recording/proof **is** the acceptance test — build the capability;
  the artifact verifies it. If the proof won't run cleanly, the feature isn't done. **Never game the proof.**

## 4. Make the loop tight by building observability
- A loop is only as good as its feedback. Backend work is smooth because state is explicit and probeable
  (tests, API, logs). Frontend/UX stumbles because state is *implicit and unobservable* — so **expose it**
  (e.g. `data-*` state attributes) so "is it right?" is a cheap, grounded check, not a slow demo guess.
- Prefer objective signals (a test, a DOM attribute, a log line, an API response) over the agent's confidence.

## 5. Catch loops early; isolate big reads
- Same obstacle recurs ~twice → **stop and re-derive the goal** from ground truth; don't patch the symptom again.
- For large explorations, use a **sub-agent** that reads extensively and returns a distilled summary — keeps
  the main thread's context clean without losing the finding.

## Worked example (this project)
Backend answer-quality work went smoothly (explicit state, tests, live probes). The frontend staged-UX work
stumbled repeatedly because: (a) its state was **implicit/unobservable**; (b) after a compaction the agent
inherited a **stale "feature finished"** claim and never re-read the frontend; (c) it treated a demo video as
an artifact to produce and **patched the recording symptom-by-symptom** instead of building the capability.
Root cause: optimizing the narrative's next step instead of reading the one source of reality.

## Do / Don't
| Do | Don't |
|---|---|
| Read the code first, esp. after any compaction | Trust a summary/manifest/"it's done" over code |
| Keep the long thread; ground at boundaries | Clear/compact as your context strategy |
| Offload durable state to files the agent re-reads | Rely on the window to "remember" across sessions |
| Spikes + tight loops; let structure emerge | Pre-decompose exploratory work into fixed tickets |
| Define done as an acceptance test; build the capability | Hack the demo/test to pass |
| Expose state so verification is cheap | Verify by slow, subjective demo guessing |

## Sources
- [Effective context engineering for AI agents — Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (structured note-taking, sub-agents, compaction tradeoffs, just-in-time context)
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices) · [How Claude Code is used in practice — Anthropic](https://www.anthropic.com/research/claude-code-expertise)
- [Fighting Context Rot](https://inkeep.com/blog/fighting-context-rot) · [Agent Context Engineering 2026: memory offloading](https://agentmarketcap.ai/blog/2026/04/11/agent-context-engineering-sliding-windows-memory-2026)
- [Addy Osmani — My LLM coding workflow](https://addyosmani.com/blog/ai-coding-workflow/) · [DECODE — using AI coding agents effectively](https://decode.agency/article/how-to-use-ai-coding-agents/)
