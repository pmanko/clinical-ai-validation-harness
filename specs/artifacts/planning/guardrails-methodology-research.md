# Guardrails + control-flow methodology: deep-research findings (decision input)

> Deep-research workflow (run `wf_942b8fdc-5e8`, 107 agents, 25 sources fetched, 120 claims → 25 verified via 3-vote adversarial check → 21 confirmed / 4 refuted → 6 synthesized findings). Primary sources: Anthropic + OpenAI prompt guides, NVIDIA NeMo Guardrails docs, Meta LlamaFirewall, Swiss-Cheese-for-AI-safety, small-model reliability papers, clinical-LLM safety. Scoped to OUR stack (med-agent-hub clinical chart-QA, 4-8B local models, strict JSON envelope, 006 harness).

## Bottom line

**Your "start soft → measure → harden" instinct is SOUND and matches established practice — with two non-negotiable qualifiers the evidence forces:**

1. **Defense-in-depth means NOT everything starts soft.** The recognized framing is the Swiss Cheese model: every layer has holes, so no single guardrail — least of all a system prompt — is trusted alone. Real systems (NeMo Guardrails, Meta LlamaFirewall) deliberately *stack and mix* enforcement types, and layering empirically beats any single mechanism. So a set of clinical-safety goals must be **HARD from day one**, carved out of "start soft" entirely.

2. **"Measure" must measure CORRECTNESS + GROUNDEDNESS, not just that the JSON is well-formed.** Small models can be "reliably wrong" (consistent, schema-conformant, still incorrect), and single-pass scores collapse on paraphrases. Schema-validity ≠ the guardrail holds.

## Findings (all high-confidence)

1. **Defense-in-depth (Swiss Cheese) is the established framing** — directly justifies stacking soft (prompt) + hard (code) rather than trusting one. "If any single guardrail fails, the associated risks may bypass it" (arXiv 2408.02205); UC Berkeley agentic-defense taxonomy is built on defense-in-depth (arXiv 2603.11088); "model-based detectors are bypassed by adaptive attacks… rule-based detectors require extensive human effort" — neither alone is reliable.

2. **Real systems layer AND mix enforcement types; layering wins.** NeMo Guardrails = 5 staged rail types (input / retrieval / dialog / execution / output) as a code-enforced out-of-model intermediary. Meta LlamaFirewall mixes deterministic detectors + one LLM auditor → cut AgentDojo injection attack-success **17.6% → 1.75% (>90%)** at ~5pp utility cost; neither component sufficed alone (arXiv 2505.03574). → Keep deterministic envelope/citation checks as the hard floor; layer the soft prompt for the rest. No single tool need do everything.

3. **Evidence-based SOFT-layer methodology** (Anthropic + OpenAI, for the orchestrator system prompt):
   - **Clear, explicit, scoped instructions** — models don't infer "above and beyond" or scope from vague prompts.
   - **3-5 diverse XML-tagged few-shot examples** — the most reliable lever for output format/structure (use for the envelope as a *soft* contract atop the hard schema; include an abstention example).
   - **Quote-first grounding** — extract verbatim source quotes into tagged sections *before* answering. Anthropic's own worked example is literally a clinical physician's-assistant chart task ("Find quotes from the patient records… place in `<quotes>` tags. Then…").
   - **Single non-contradictory instruction hierarchy + explicit escape hatch** — contradictory instructions actively degrade reasoning ("if KB search returns nothing relevant, abstain and say so").
   - Prompt structure for the strong-guidance default: role → numbered non-contradictory default path (search KB → consult expert → synthesize → envelope) → tool-use guidance → envelope contract w/ 3-5 worked examples → quote-first grounding → one explicit abstention escape hatch.

4. **The SOFT layer breaks down on 4-8B local models** — the empirical core for hardening safety goals:
   - Prompt *style alone* swings small-model clinical-QA accuracy double digits (roleplay cost Phi-3 Mini **21.5pp** on MedQA; arXiv 2603.00917).
   - Small models can be **"reliably wrong"** — high consistency, schema-conformant, still incorrect (Gemma 2: consistent-yet-wrong on 38.5% of MedQA items). "A dangerous failure mode in clinical AI."
   - Single-pass instruction-following collapses **up to 61.8%** across semantically-equivalent paraphrases on small models (Qwen3-0.6B 58.0%→22.2% vs GPT-5 only −18.3%; arXiv 2512.14754). Reliability is a *second-order* property beyond accuracy.
   - **Small models are poor LLM verifiers** (high false-positive rates) — so a local 4-8B groundedness verifier is unreliable; prefer deterministic citation resolution (code) or escalate the verifier to the cloud model.

5. **Two HARD levers — choose by WHAT must be guaranteed:**
   - **Harden the OUTPUT** (constrained/structured decoding — json_schema response_format / grammar makes violating tokens unproducible) when the guarantee is about *shape/format*. We already do this for the envelope. **Guarantees well-formed, NOT correct or grounded.**
   - **Harden the CONTROL FLOW** (deterministic code / state machine that calls the tool, gates retrieval, forces abstention) when the guarantee is about a *procedure or safety gate a prompt could skip*.

6. **Goal-by-goal map for our POC** (the deliverable):

| Goal | Layer at POC | Mechanism |
|---|---|---|
| JSON envelope shape | **HARD now** | constrained decoding (json_schema) — keep as-is |
| Citation groundedness (no fabricated indices) | **HARD now** | code validates every integer citation index resolves to a real chart record + quote-first prompting |
| Abstention on insufficient evidence | **HARD now** | retrieval-gating: if KB search returns nothing relevant, **code** forces abstention (don't trust the prompt) |
| Scope / PHI limits | **HARD now** | code-enforced |
| Default-path adherence (search→expert→synthesize) | **SOFT now** | strong system-prompt guidance; promote to hard control-flow code on measured failure |
| Completeness / thoroughness | SOFT | prompt |
| Tone | SOFT | prompt |
| Citation *selection* quality | SOFT | prompt + harness groundedness scoring |

**Promotion criterion:** promote a soft goal → hard control-flow when the 006 harness shows the small model failing it on **correctness / groundedness / abstention-outcome** across paraphrase or adversarial probes — not on a single pass, and not on schema-validity.

## Framework recommendation

**Hand-roll deterministic validators now.** We already hand-roll the envelope guardrail; NeMo is a heavyweight out-of-model intermediary; LLM-based verifier guardrails degrade sharply on small models. Keep the architecture expandable. (Caveat: Guardrails AI / OpenAI Agents SDK tripwires were NOT covered by surviving evidence — this is grounded inference, not a head-to-head. Revisit if/when validators multiply.)

## Caveats (honest)

- **TERMINOLOGY TRAP (most important):** the academic "hard vs soft guardrails" (hard = rigid for legal/ethical/safety; soft = context-*adjustable*/flexible) is a DIFFERENT axis from our "soft = prompt-level/always-violable" vs "hard = code/constrained-decoding/non-negotiable." The claim that the academic taxonomy maps onto ours was **refuted 0-3**. What the literature licenses is the *defense-in-depth/layering* principle and *mixing enforcement types* — the prompt-vs-code labeling is our own operational framing. Treat SOFT/HARD here as our definitions.
- **Vendor prompt docs target FRONTIER models** (Claude Opus 4.x, GPT-5). They establish the right *method* for the soft layer but do NOT establish prompts steer reliably enough on 4-8B to skip hard enforcement — the small-model findings cut the other way. OpenAI's `reasoning_effort` knob has no gemma/medgemma analog on LM Studio.
- **4-8B band is extrapolated** — reliability-collapse measurements bracket it (≤3B and ≥70B); direction (smaller → more brittle) well-supported, exact in-band magnitude inferred.
- **Framework coverage incomplete** (NeMo + LlamaFirewall have primary sources; Guardrails AI / OpenAI Agents SDK do not).
- **Security ≠ clinical metrics:** the AgentDojo injection numbers motivate *layering as a principle*; they're not predictions of clinical-QA groundedness performance.
- **Refuted (do NOT cite):** academic hard/soft = our axis (0-3); GPT-5 persistence-instruction reliability (0-3); Meditron-7B 99% UNKNOWN near-complete instruction-failure (0-3); input rule-vs-model = our axis (1-2).

## Open questions

1. Can a groundedness/abstention *verifier* run acceptably on the local 4-8B stack at all (high FPR), or must citation-groundedness be pure-code citation-resolution / escalate to the cloud model? Decides whether 006's deferred automated `citations_resolve` can be pure code.
2. Concrete NUMERIC promotion threshold on THIS harness's metrics (Scout accuracy/completeness, failed-to-abstain rate, unsupported-citation rate) to trigger soft→hard. Must be set empirically against the default comparison set.
3. Are Guardrails AI / OpenAI Agents SDK tripwires worth adopting over hand-rolled validators for our local + OpenAI-compat + small-model + observability needs?
4. Within 4-8B (gemma-4-e4b vs medgemma-1.5-4b), does the accuracy-vs-reliability decoupling hold — i.e. select the default engine by measured *reliability on the guided path*, not benchmark accuracy?

## Reconciliation with the settled orchestrator design

This **refines** the settled design (one agentic loop, two knobs, typed tool interface) — it does not reverse it. One meaningful update:

- Earlier we said hard control-flow code is a **deferred promotion**, triggered only if measurement shows the small model can't hold the guided path. The research confirms that for **path adherence / completeness / tone** — but **carves out clinical-safety goals** (citation-index resolution, retrieval-gated abstention, scope/PHI) which must be **HARD from day one**, not deferred. The "defer" applies to the *path*, not to *safety gates*.
- Everything else lands cleanly: the existing hard JSON envelope stays; the strong-guidance default lives in the system prompt with the documented structure; the 006 harness (which already measures correctness/groundedness/abstention) is exactly the "measure" step; promotion is measurement-driven.

## Key sources

- Swiss-Cheese AI safety: https://arxiv.org/html/2408.02205v3 · Agentic defense taxonomy: https://arxiv.org/html/2603.11088v1
- NeMo Guardrails: https://docs.nvidia.com/nemo/guardrails/latest/user-guides/guardrails-process.html · LlamaFirewall: https://arxiv.org/pdf/2505.03574
- Anthropic prompting: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices · OpenAI GPT-5 guide: https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide
- Small-model clinical reliability (LMIC): https://arxiv.org/abs/2603.00917 · Reliability vs accuracy: https://arxiv.org/html/2512.14754v1
