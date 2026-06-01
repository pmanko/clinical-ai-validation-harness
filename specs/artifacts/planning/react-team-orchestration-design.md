# Med Agent Team — Prompt-Driven ReAct Orchestration (KB → clinical → synthesize)

> Decision-ready implementation spec. Grounds the prompt + minimal code changes that evolve
> `targets/med-agent-hub/server/team.py` so the clinical reasoner (MedGemma) reasons **GIVEN** the
> KB context, while the orchestrator (Gemma-4-E4B) is *strongly suggested* — not hardcoded — to run
> kb_search → medical_expert → synthesize. Keeps the existing guided ReAct loop (plain tool turns,
> then ONE `response_format`-constrained synthesis). Not a fixed pipeline.

## 0. The one decision that ties the spec together

**KB→expert is CODE; ordering is PROMPT.**

- **Code** auto-injects the accumulated `kb_search` observations into the `_run_medical_expert`
  call as a labeled reference block placed at the TOP of the expert's user message (before the
  chart, before the question — lost-in-the-middle, TACL 2024). This is the data dependency the
  research is unanimous a 4-8B orchestrator cannot reliably thread by hand
  (angles 2, 3, 4 — BFCL multi-turn collapse; guardrails up-to-61.8% paraphrase collapse).
- **Prompt** drives only *which/whether* and *ordering* (call kb_search before medical_expert).
  It NEVER tells the model to paste KB facts into the expert's query — the code already did that.

This honors "guided ReAct, not a pipeline" and roadmap decision #3 (KB is a typed tool, not a
deterministic pre-step): we do **not** force kb_search first in code, `tool_choice` stays `"auto"`,
and the model may answer chart-only questions with no tools at all. The only thing that became
deterministic is the *handoff* of an already-retrieved KB block into the expert call — a few lines,
not a backbone. `tool_choice:"required"` first-turn-only is a **measured escalation knob** for the
006 run, never a default.

Consistency rule enforced throughout: because the code auto-injects, the orchestrator exemplar and
tool descriptions say "medical_expert automatically receives what you retrieved" — they do NOT say
"paste the KB into the query." Double-injection would confuse the 4B model.

## 1. Two message contexts (cache-prefix safety)

The loop currently runs under chartsearchai's envelope `DEFAULT_SYSTEM_PROMPT`, which the Llama-3.1
card says degrades small-model tool calling (mixing output-format/conversation rules with tool
defs). We add a loop-phase orchestrator system prompt — but we must NOT break the byte-identical
`[system, user(chart)]` prefix the synthesis call depends on for LM Studio's prompt cache
(roadmap §2). So:

- **Loop context** (its own list): `[orchestrator_system, user(chart), ...prior turns, user(question), ...tool transcript]`.
  Envelope-free, tool-focused. This list does NOT need to hit the cache.
- **Synthesis context** (reconstructed from the ORIGINAL chartsearchai messages): the byte-identical
  `[system(chartsearchai), user(chart), ...prior turns, user(question)]` prefix + ONE collapsed
  "gathered evidence" block (top-K KB snippets first, then expert notes) + the synthesis
  instruction, appended at the end near generation.

The evidence block *replaces* dumping raw `role:tool` messages into the synthesis context — net-
neutral complexity, and it fights lost-in-the-middle by keeping decisive evidence at the end
(angle 5). The loop prefix differing from the synthesis prefix is fine; only the chartsearchai-
facing synthesis call must be cache-stable.

## 2. Prompts (FULL TEXT)

### 2.1 ORCHESTRATOR_SYSTEM (new — loop phase only)

```
You are the coordinator of a small clinical team answering a clinician's question about ONE
patient's chart. You do not write the final answer yourself — you decide which teammates to
consult, then stop.

You have two tools:
- kb_search: look up EXTERNAL reference guidance (WHO / essential-medicines guidelines, dosing,
  thresholds, danger signs, normal ranges) that is NOT in the patient's chart.
- medical_expert: have a clinical expert interpret THIS patient's chart against the question. The
  expert automatically receives whatever kb_search returned this turn — you do NOT need to copy
  any facts into your question to it.

How to work:
- Before each tool call, state in ONE sentence what you still need and why.
- DEFAULT pattern: if the question involves a guideline, a drug/dose, a threshold, a danger sign,
  an immunization schedule, a normal/reference range, or whether something is current/recommended,
  FIRST call kb_search to pull the relevant reference facts, THEN call medical_expert to interpret
  the chart against them, THEN stop.
- SKIP the tools only when the chart plainly and fully answers the question with no outside
  guidance needed (e.g. "what medications is she on?", "how many did you list?"). Then just say you
  are done.
- Call at most one tool per step. Once you have what you need, stop — do not keep calling tools.

Worked example (a question like the demo's):
Question: "Is this patient's antiretroviral regimen still recommended?"
Step 1 — Thought: I need the current WHO guidance on this regimen, which is not in the chart.
         Action: kb_search({"query": "WHO recommended first-line ART; stavudine d4T phase-out"})
         Observation: reference snippets on preferred dolutegravir-based regimens and the stavudine
         phase-out are returned.
Step 2 — Thought: now interpret the chart's regimen against that guidance.
         Action: medical_expert({"query": "Given the chart's ART regimen, is it still WHO-recommended,
         and if not what is the concern?"})
         Observation: the expert reasons over the chart plus the retrieved guidance.
Step 3 — Thought: I have enough. Done.

Do not invent guideline facts, doses, or chart values. If kb_search returns nothing relevant, say
so rather than guessing.
```

### 2.2 MEDICAL_EXPERT_SYSTEM (replacement — now reasons GIVEN the KB)

```
You are a clinical reasoning assistant. You are given a patient chart excerpt, optionally some
knowledge-base reference snippets (external guideline/dosing/threshold facts, NOT chart data), and
a focused question. Reason using the chart together with any provided reference snippets, and give
concise, clinically-grounded reasoning.

State only what the chart supports plus accepted medical knowledge and the provided reference
snippets. For any guideline, dose, threshold, danger sign, schedule, or "is this current /
recommended" claim, rely on the provided reference snippets; if neither the chart nor the snippets
support an answer, say so explicitly. Do not invent values, doses, or thresholds. When you use a
reference snippet, name its source in prose (e.g. "per WHO IMCI"). Plain text, no preamble.
```

### 2.3 Tool descriptions (FULL TEXT — `_tool_definitions()`)

```
kb_search:
  Search the clinical knowledge base of openly-licensed reference guidance (WHO IMCI danger signs,
  essential medicines, standard dosing and thresholds, antiretroviral guidance) for facts that are
  NOT in the patient's chart. Call this FIRST for any claim about a guideline, a drug or dose, a
  threshold, a danger sign, an immunization schedule, a normal/reference range, or whether a
  treatment is current or recommended. Example: the question asks whether a patient's regimen is
  still recommended -> kb_search({"query": "WHO first-line ART; stavudine d4T phase-out"}). Returns
  reference snippets with provenance — never patient data; cite the source inline as prose, never as
  an integer.
  param query (string): the clinical topic, drug, or guideline term to look up.

medical_expert:
  Consult a clinical expert to interpret THIS patient's chart against the question. Call this AFTER
  kb_search when guideline/dosing/threshold facts matter: the expert AUTOMATICALLY receives the
  snippets kb_search returned this turn, so you do NOT copy any facts into your question — just ask
  what you want interpreted. Use for clinical judgment and interpretation, not for plain chart
  lookup you can answer yourself. Example: after retrieving the guidance ->
  medical_expert({"query": "Given the chart's regimen, is it still WHO-recommended, and what is the
  concern if not?"}).
  param query (string): a focused clinical question for the expert about this chart.
```

### 2.4 SYNTHESIS_INSTRUCTION (replacement — reconciles the upstream conflict)

The upstream `DEFAULT_SYSTEM_PROMPT` (`targets/chartsearchai/.../LlmProvider.java:41-103`) says
"Use only the patient records," "Never infer, assume, or add information not in the records," "Cite
EVERY record by its number," and its three few-shot examples (the apples/oranges/**bananas**
demonstration) all teach *every claim gets an integer; absent info → cite nothing*. On a 4B model
those examples beat plain text. So the synthesis instruction must (a) name the explicit carve-out,
(b) show ONE mixed-citation worked example, (c) extend the integer-exclusion to expert notes and
parametric knowledge, not just KB.

```
You are now writing the final answer as the chart-answer JSON object {answer, citations, blocks}.
Use the patient chart above AND the gathered evidence block below (knowledge-base reference snippets
and the clinical expert's notes).

CITATIONS — read carefully:
- The integer indices in `citations` and the `[N]` markers are RECORD INDICES from the numbered
  patient chart ONLY. A claim gets an integer ONLY if you can point to the numbered chart record
  that states it.
- The chart-only rule ("use only the records; never add information not in the records") still
  governs PATIENT facts. Labeled knowledge-base reference snippets are an ALLOWED EXCEPTION: you
  MAY state them as general medical guidance, but attribute them inline in prose (e.g. "per WHO
  IMCI", "per WHO HIV guidelines") and NEVER give them a bracket number or put them in `citations`.
- Knowledge-base facts, the medical expert's notes, and your own medical knowledge are ALL NOT
  chart records — attribute them inline in prose and NEVER place them in `citations`. Only a claim
  verifiable against a numbered chart record gets an integer.
- Never invent a source name, URL, guideline title, dose, threshold, or chart-record index. If no
  chart record and no reference snippet supports the answer, say the information is not available
  rather than guessing.

Worked example (mixed): "She is on a stavudine (d4T)-based regimen [4]. Per WHO HIV guidelines,
stavudine is no longer recommended because of frequent, often irreversible toxicity, and tenofovir
or zidovudine are the preferred nucleoside backbones." -> citations: [4]  (the chart record for the
regimen is cited; the WHO guidance is attributed inline with NO integer).

Emit a `table` block when the answer lists/enumerates multiple items (per the chart-format rules
above); otherwise leave `blocks` empty. Keep the answer concise.
```

## 3. team_py_changes (minimal, keep the guided ReAct loop)

1. **Add `ORCHESTRATOR_SYSTEM` constant** (§2.1) and replace `MEDICAL_EXPERT_SYSTEM` (§2.2) and
   `SYNTHESIS_INSTRUCTION` (§2.4); rewrite the two descriptions in `_tool_definitions()` (§2.3).

2. **Loop context gets its own message list** instead of `working = list(messages)`. Build
   `loop_messages = [{"role":"system","content":ORCHESTRATOR_SYSTEM}] + [m for m in messages if
   m.get("role") != "system"]` so the loop runs under the tool-focused system prompt, envelope-free
   (Llama-card fix). Keep the ORIGINAL `messages` untouched for the synthesis prefix.

3. **Accumulate KB observations and thread them into the expert (the headline fix).** Keep a running
   `kb_context` string; each `kb_search` observation is appended to it. Change the expert signature
   to `_run_medical_expert(client, query, chart_context, kb_context="")` and build its user message
   with the KB block FIRST:
   `f"Reference guidance (NOT chart data; for dosing/threshold/guideline facts use only these or say
   they were not found):\n{kb_context}\n\nPatient chart:\n{chart_context}\n\nQuestion: {query}"`
   (omit the reference block when `kb_context` is empty). At the dispatch site pass
   `kb_context=kb_context`. This is the data dependency; the prompt no longer carries it.

4. **Dedupe tool calls within one assistant message** on `(name, normalized-arguments)` before
   dispatch — documented Gemma+LM Studio bug #1756 emits duplicate identical calls ignoring
   `parallel_tool_calls:false`. No prompt fixes this. Cheap guard; prevents double kb_search /
   wasted expert call / context pollution.

5. **Synthesis builds a collapsed evidence block from the ORIGINAL prefix.** Instead of
   `synth_messages = working + [synthesis_user]`, reconstruct
   `synth_messages = list(messages) + [{"role":"user","content": gathered_evidence + "\n\n" +
   SYNTHESIS_INSTRUCTION}]`, where `gathered_evidence` is the accumulated KB snippets (top-K first)
   followed by the expert notes, under a "Gathered evidence" label. This keeps the byte-identical
   `[system, user(chart)]` prefix for the cache AND puts decisive evidence at the end near
   generation (lost-in-the-middle). The split stays: loop = plain (tools, no `response_format`);
   synthesis = `response_format`, no tools (verified: combining them returns LM Studio's
   "Cannot combine structured output constraints with lazy grammar").

6. **Keep everything else.** `MAX_TOOL_ITERATIONS = 3`, `tool_choice:"auto"`, the per-tool
   try/except (a failed tool is skipped, the turn still synthesizes), the empty-content guard, and
   the always-valid `_fallback_envelope`. These are load-bearing on a sub-7B stack, not cruft.

NOT in the minimal set (listed as risk-mitigation options, not built): a deterministic post-
synthesis citation validator (006 is human-adjudicated — FR-006.4 forbids an LLM judge and
groundedness is a reviewer field, SC-006.5); `tool_choice:"required"` as a default; promoting
kb_search-first into code. Each is a 006-gated escalation, not a v1 edit.

## 4. Rationale (cited to the research angles)

- **KB→expert as code (angles 2, 3, 4).** The headline gap: `_run_medical_expert` never receives
  the kb_search output today, so MedGemma reasons WITHOUT the KB and the "reason GIVEN KB context"
  flow is unrealized. Every clinical-RAG result conditions generation on the retrieved context in
  the SAME prompt (MedRAG/MIRAGE, up to ~18pp lift). No prompt reliably makes a 4-8B orchestrator
  hand-thread retrieved facts into a sibling tool's free-text argument (BFCL multi-turn collapse;
  guardrails up-to-61.8% paraphrase collapse). So the handoff is code; the ordering stays prompt.
- **Ordering as strong-suggestion-with-escape-hatch (angle 1).** Gemma is documented as NOT trained
  on multi-step chaining or multi-turn state aggregation — exactly this retrieve→reason→synthesize
  flow. The highest-leverage mitigations are (a) enriched tool descriptions with trigger keywords +
  ordering + a usage example (Google's #1 lever; Anthropic "junior-dev docstring"), and (b) ONE
  worked exemplar resembling the actual question domain (Brittle-ReAct: exemplar-query *similarity*
  drives behavior, not abstract rules). The exemplar is HIV/ART-flavored because the demo anchor is
  Zabella (HIV) and the KB is HIV-heavy. "Not mandatory" is encoded as an explicit skip condition,
  not silence (silence reads as "ignore" to a small model).
- **Two contexts + cache (angles 1, 3, 5).** A loop-phase orchestrator prompt without the envelope
  (Llama card: mixing format rules with tool defs degrades tool calling), while the synthesis call
  preserves the byte-identical chartsearchai prefix the roadmap pins for LM Studio's prompt cache.
- **Synthesis carve-out + mixed example (angles 4, 5).** The single biggest risk to the KB feature
  lives in the running prompt stack: chartsearchai's three few-shot examples teach "every claim →
  integer," which on a 4B model will either suppress KB content or attach an integer to a KB fact.
  Naming the carve-out, showing one mixed-citation example, and extending the integer-exclusion to
  expert notes + parametric knowledge closes it. The schema backstops it: `citations` is
  `integer[]` with no string channel, so KB content is structurally unrepresentable there.
- **Loop/synthesis split (angle 3, 5).** Verified live: tools + `response_format` in one call →
  LM Studio error; format restriction degrades reasoning (EMNLP 2024 "Let Me Speak Freely"). Keep
  the free-text tool phase as the reasoning-preservation step; constrain only the final call.
- **Dedupe + short loop (angle 1, 2, 3).** Gemma+LM Studio duplicate-tool-call bug needs a code
  guard; multi-turn unreliability rises ~112% so `MAX_TOOL_ITERATIONS` stays low and prefer one
  round.

## 5. Risks (small-model adherence — what to watch)

- **The documented ceiling.** Gemma is not trained on multi-step chaining / state aggregation —
  the exact flow. Prompt-suggested ordering RAISES the hit-rate of kb_search→expert; it does not
  GUARANTEE it on a 4B model. The code fallback (skip a failed/slow tool, still synthesize) is
  load-bearing, not a safety net we hope never fires. Demotion to a code-enforced chain is the
  006-gated next rung if the measured order-firing rate is too low.
- **Under-calling kb_search.** Gemma may answer a guideline question from parametric memory with no
  retrieval. Mitigation knob (measured, not default): `tool_choice:"required"` on the FIRST loop
  turn only, then revert to `"auto"` so it can stop.
- **The parallel trap.** Gemma's strength is parallel calls, but our flow is inherently sequential
  (the expert must consume kb_search output). A future refactor must NOT parallelize these two.
- **Upstream few-shot dominance.** Even with the carve-out, the bananas example may pull the model
  toward suppressing KB or integer-citing it. Watch citation-channel purity in the 006 run; if it
  leaks, the post-synthesis validator (deferred) becomes the backstop.
- **Empty tool_calls despite need.** Some LM Studio parsers drop Gemma's escaped tool-call markers,
  so a real call looks like "the model chose not to call." Don't fix with louder prompts — verify
  the template/parser on the specific Gemma build.
- **Sub-7B structured-output reliability.** gemma-4-e4b and medgemma-1.5-4b sit below LM Studio's
  ~7B structured-output comfort line; keep the empty-content guard and the always-valid fallback.
- **Latency.** kb_search + a KB-grounded expert call before synthesis raises time-to-first-token;
  the buffer-then-stream-synthesizer posture and the 3-iteration cap bound it. Report it in 006.

## 6. How to measure (the 006 run)

The point: does the team now *pull KB* and produce *richer grounded* answers than the bare Gemma
model? The demo anchor makes this concrete and is **grounded, not asserted**: Zabella Halambe
(`dd75c020-1691-11df-97a5-7038c432aabf`) is on a d4T/3TC/NVP/EFV (stavudine-based) regimen — stated
in `datasets/validation/scenarios/convo-abstention-honesty.json` (T4 note) — and the KB carries the
`hiv-d4t-phaseout` snippet ("Stavudine (d4T)-based regimens are no longer recommended …"). So a
scenario asking "Is this patient's ART regimen still recommended?" should make the team:
1. call kb_search → pull the stavudine-phaseout snippet,
2. pass it into medical_expert → which reasons the chart's d4T regimen is outdated per WHO,
3. synthesize an answer that cites the chart regimen record by integer AND attributes the
   phase-out guidance inline ("per WHO HIV guidelines"), with the guidance NOT in `citations`.

The **bare Gemma single-model backend** (006 default) has no KB and is told to use only the chart,
so it will at best restate the regimen; it cannot flag it as outdated with sourced guidance. That
delta is the demo.

Run via the 006 harness (MAH.C2 / task #138) through chartsearchai's real REST API, KB-on vs
KB-off and team vs gemma-local / medgemma-local (SC-006.7):

- **Deterministic, no-LLM metrics (SC-006.3):** `json_valid`, `citation_count`, `abstained`,
  `latency_ms` per `(scenario, backend, turn)`.
- **Chain-adherence instrumentation (the promotion trigger — angle 2):** log per turn (a) did
  kb_search fire before the synthesis call on guideline-type questions; (b) did the medical_expert
  user message actually contain a KB block (it now does, by construction — assert it); (c)
  citation-channel purity (no KB/expert fact carrying an integer); (d) hops + variance across N
  repeats (multi-turn unreliability, not just mean).
- **Human adjudication (SC-006.5):** Scout 0-10 accuracy/completeness/relevance, per-citation
  groundedness (`supported`/`unsupported`/`unverifiable`), abstention outcome, harm hard-fail.
  Expect the team to score higher on completeness/accuracy on guideline-flavored scenarios and to
  show *supported* inline KB attributions the bare model lacks.

Promotion gate (Anthropic/OpenAI/Microsoft: escalation is evidence-triggered): if 006 shows the
loop under-calls kb_search or citation purity leaks, escalate — `tool_choice:"required"` first turn,
then a coded retrieve-before-synthesize step, then the post-synthesis validator — in that order.
Measure first.
```
