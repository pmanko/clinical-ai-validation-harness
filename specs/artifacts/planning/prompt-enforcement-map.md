# Prompt & guardrail enforcement map — chartsearchai-direct vs med-agent-hub

> Purpose: the two answer paths the harness compares are *not* prompt/guardrail-comparable, and where each rule is enforced is convoluted. This traces every system prompt + guardrail to its file:line, for both paths, so we can (a) reason about results and (b) design the "harmonized" variant. All references verified against the code on 2026-06-04.

## The two paths share ONE front door

Both paths enter through chartsearchai's `LlmProvider.search()` — chartsearchai builds the numbered chart + the system prompt and POSTs an OpenAI-style `[{system},{user}]` to whatever `LLM_BASE_URL`/endpoint the run selected. The ONLY difference is the endpoint:

- **chartsearchai-direct** (a4b / e2b / 12b baselines) → endpoint = llama-router `:8077` → the raw model sees chartsearchai's messages verbatim.
- **med-agent-hub team** (med-agent-team-*) → endpoint = hub `:8080` → the hub re-prompts internally, then returns the envelope.

So chartsearchai's prompt is the *baseline contract for both*; the hub adds/replaces layers on top.

## Path A — chartsearchai-direct (single LLM)

```
LlmProvider.search(numberedRecords, focusIndices, question)        LlmProvider.java:137
  systemPrompt = getSystemPrompt()                                 :138   ← CONFIG SEAM
  userMessage  = buildUserMessage(records, focusHint, question)    :139
  getActiveEngine().infer(systemPrompt, userMessage, timeout)      :142  → RemoteLlmEngine → router :8077
  extractResponse(text, …)                                         :145  → {answer, citations, blocks} + resolved references
```

- **System prompt:** `DEFAULT_SYSTEM_PROMPT` (LlmProvider.java:46–109), returned by `getSystemPrompt()` (:138). It is a *method*, so the variant is swappable (Track 2 makes it GP-driven).
- **Guardrails it encodes:** chart-only ("Use only the patient records… Never infer, assume, or add information not in the records" :48–49); **completeness** ("Include ALL relevant records… never omit for brevity" :50); **"Cite EVERY record you reference by its number in brackets"** (:51 — the over-referencing root); strict `{answer,citations,blocks}` JSON (:52–53) enforced HARD by constrained `response_format`; **table rules** (one row per unique item; refs in `cell.refs`, never a citations column :54–72); **plain text only, no markdown** (:73); **abstention demo** ("There are no records of banana deliveries" :107); semantic-invariance to phrasing (:76); a few-shot FORMAT DEMONSTRATION (:78–108).
- **NOT present:** any KB/guideline handling (assumes chart is the only input), explicit false-premise handling, explicit "never invent a guideline/dose/source", an Answer/In-Depth structure.

## Path B — med-agent-hub team (orchestrator → expert → synthesis)

```
chartsearchai → POST :8080 /v1/chat/completions  (messages = [DEFAULT_SYSTEM_PROMPT, chart+question])
  openai_compat._content_for(req)                                  openai_compat.py:87
    level = get_level(req.model)                                   (levels.yaml role+prompt config)
    run_team(messages, …, orchestrator_prompt, synthesizer_prompt, expert_prompt, has_expert)
  team.run_team(...)                                               team.py:307
    ── TOOL LOOP ──  loop_messages = [{system: orchestrator.txt}] + non-system msgs   :344-346  ← REPLACES chartsearchai's system prompt
        up to MAX_TOOL_ITERATIONS, tools = kb_search / medical_expert  :354-357
        kb hits → kb_context ; expert reads (chart + kb) → expert_notes  :376-386
    ── SYNTHESIS ──  synth_messages = list(messages) + [{user: synthesis.txt + gathered_evidence}]  :401-403
        ↑ ORIGINAL messages → INHERITS chartsearchai's DEFAULT_SYSTEM_PROMPT, then layers synthesis.txt
        _chat(synth_model, synth_messages, response_format=…)      :406-411   (HARD envelope schema)
        _normalize_envelope(text)                                  :412 → sweeps EVERY inline [N] into citations  :290
    fallback envelope on empty/exception                            :415-419
```

So the team enforces guardrails in **three different places**:

1. **Tool loop** runs under `orchestrator.txt` (orchestrator.txt:1–26), which **replaces** chartsearchai's system prompt (team.py:344). Guardrails: ALWAYS call kb_search + medical_expert, never answer from chart alone (:7); a fixed 3-step path (:9–11); no "chart answers it by itself" shortcut (:13); "Do not invent guideline facts, doses, or chart values" (:25). **The direct path never sees any of this.**
2. **Medical expert** runs under `medical_expert.txt`: evidence-only ("State only what the chart supports plus accepted medical knowledge and the provided reference snippets"), name KB sources in prose, "Do not invent values, doses, or thresholds".
3. **Synthesis** runs on chartsearchai's ORIGINAL messages (so it **inherits `DEFAULT_SYSTEM_PROMPT`**) **+** `synthesis.txt` appended as a user turn (team.py:402–403). `synthesis.txt` adds: an **Answer/In-Depth** structure (:3–13); "Cite chart records inline with `[N]`" (:4, compounding chartsearchai's cite-EVERY-record); a **KB carve-out** — KB/guideline facts in prose, NEVER bracketed, `[...]` reserved for chart-record integers (:26–30); **false-premise** handling (:20); **never-invent** a source/dose/index (:30); tables in `blocks` (:42–43).

## Guardrail-delta table (the confound)

| Guardrail | chartsearchai-direct | hub team | Where |
|---|---|---|---|
| Chart-only / never-infer | ✅ | ✅ (inherited at synthesis) | LlmProvider:48 |
| Completeness ("include ALL relevant") | ✅ | ✅ (inherited) | LlmProvider:50 |
| "Cite EVERY record" | ✅ | ✅ + "cite inline [N]" (compounded) | LlmProvider:51 / synthesis.txt:4 |
| Strict envelope (constrained decode) | ✅ | ✅ | RemoteLlmEngine response_format / team.py:408 |
| Table rules | ✅ (detailed) | ✅ (lighter) | LlmProvider:54–72 / synthesis.txt:42 |
| **KB/guideline retrieval + carve-out** | ❌ none | ✅ (kb_search tool + carve-out) | orchestrator.txt:4 / synthesis.txt:26–30 |
| **Separate clinical-expert reasoning** | ❌ one-shot | ✅ medical_expert role | team.py:376 |
| **Mandated KB→expert→synth path** | ❌ | ✅ | orchestrator.txt:7–11 |
| **False-premise handling** | ❌ | ✅ | synthesis.txt:20 |
| **Explicit "never invent guideline/dose/source"** | ⚠️ implicit only | ✅ explicit | synthesis.txt:30 |
| **Answer / In-Depth structure** | ❌ (plain text) | ✅ | synthesis.txt:3–13 |

**Conclusion:** the current comparison confounds *orchestration* (KB + expert) with *a different, stricter final-answer prompt*. The team could be "winning" on prompt, not on orchestration. Harmonizing the final-answer guardrails isolates the orchestration effect.

## Implications for the plan

- **Harmonized set (Track 2):** one citation contract (clean prose + structured citations + cap + never-bracket-non-chart) + abstention/honest-absence + never-invent + false-premise — applied to BOTH `getSystemPrompt()` (direct) and the hub synthesis prompt. A `med-agent-team-harmonized` lane (Track 3) = team synthesis under the harmonized prompt, so its only delta vs harmonized-direct is the KB+expert evidence.
- **Reference pollution (Track 6):** driven by `DEFAULT_SYSTEM_PROMPT:51` ("cite EVERY record") **and** `synthesis.txt:4` ("cite inline [N]"), then amplified by `_normalize_envelope` (team.py:290) sweeping every `[N]` with no cap/dedup. Fix in both prompts + the normalizer.
- **Validator (Track 4):** the synthesis seam is team.py:412 — after `_normalize_envelope`, before return.
- **`hublike` direct variant:** give the direct path synthesis.txt-style guardrails (minus the KB tool) to test whether the hub's lift is prompt or orchestration.
