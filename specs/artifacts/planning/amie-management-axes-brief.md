# Applying AMIE's lessons: a management-reasoning evaluation layer for the harness

> Dev brief. The full literature read lives in the dissertation workspace
> (`digging-in-research` → `06-amie-disease-management`). This doc translates it into concrete
> harness work. Status: proposed. Owner: validate lane.

## The gap AMIE exposes

Google's AMIE-for-disease-management (*Nature* 2026) was *non-inferior* to PCPs overall but
*significantly superior* specifically on **plan preciseness, investigation precision, and guideline
grounding** — the *decision* axes — using a general Gemini grounded in guidelines + formularies,
not a medically fine-tuned model.

Our harness today scores **extraction**: `accuracy / completeness / relevance / citation_groundedness
/ harm / temporal` (`.claude/skills/clinical-answer-scoring/rubric.md`) — "did it read the chart
right?". We do **not** score **management** — "is the plan right?". This matters for two reasons:

1. Our headline finding ("multi-agent scaffolding adds little over a strong single model") is measured
   *only on extraction*, where a strong general model already saturates. AMIE shows the signal lives
   in the **management/grounding** layer we don't yet measure — plausibly where the hub's
   `kb_search` + `medical_expert` scaffolding would finally earn its keep.
2. The dissertation's object is **WHO-SMART-Guidelines decision support** (management logic), so a
   management-axis layer is the eval that actually targets the thesis, not a proxy.

## The headline contrast: frontier Gemini vs on-device Gemma 4 (controlled)

AMIE's published number is *Gemini + its own bespoke scaffolding* (dual-agent, self-play,
chain-of-reasoning, guideline retrieval) — the paper cannot separate the model from the machinery. The
dissertation's load-bearing question is the **model-scale** one underneath it: **does AMIE-grade
management reasoning survive the drop from frontier cloud Gemini to an on-device Gemma 4-class model?**

This harness can answer the *controlled* version AMIE cannot: every arm runs through the **same**
chartsearchai flow, grounding, and judge, so a **Gemini arm beside Gemma 4 isolates the base-model
contribution with scaffolding and grounding held fixed.** Framed as a curve, not a point — with the
scale ladder we already run (Gemini → Gemma 4 12B → smaller Gemmas / Liquid) and the quant control from
the Q8/Q4 survey — the deliverable is a **management-quality-vs-model-scale curve, grounding on/off**:
*the smallest model + grounding that approaches AMIE-Gemini-level management reasoning.* That is the
dissertation's empirical core, more than the open/closed or WHO-vs-NICE framing.

**Careful scope (don't overclaim).** This measures **base Gemini vs base Gemma under *our* scaffolding**
— it is **not** a replication of AMIE's number (which bundles AMIE's own scaffolding), and it claims no
result in advance: it is the experiment that *would* size the gap. It depends on the management axes
(item 1) existing first.

## Work items (prioritized, grounded in current files)

### 1. Management axes on the rubric + the judge cell  *(highest value)*
- Add an **Answer-management** axis-set to the rubric, scored on the final answer (and/or a new
  "Plan" probe): `treatment_appropriateness`, `investigation_precision`, `guideline_grounding`,
  `followup_quality`, `inappropriate_treatment` (mirrors AMIE's rater axes).
- Files: `.claude/skills/clinical-answer-scoring/rubric.md` (new axes + scoring bands); the judge
  schema in the fan-out workflow; `harness/validate/reconcile.py` (a **Management Benchmark** /100,
  same shape as `cell_benchmark_score` / `cell_indepth_benchmark_score`); `report.py` + the index
  (a third co-equal benchmark column). Red-first tests in `evals/validate/test_reconcile.py`.
- This is the AMIE "management reasoning" axis made reproducible + LLM-judged.

### 1b. Add a frontier Gemini arm — the headline experiment's to-do  *(depends on item 1)*
- **Mechanics (grounded, not zero-plumbing):** a Gemini arm is a `backends.json` entry whose override
  points chartsearchai at **Gemini's OpenAI-compatible endpoint** (`…/v1beta/openai/chat/completions`,
  model e.g. `gemini-2.5-flash` / `-pro`). chartsearchai already calls a remote LLM with an API key —
  but from a **global** property (`chartsearchai.llm.remote.api_key`), not per-request — and the
  harness `Backend` override (`harness/validate/models.py`) carries `{endpointUrl, modelName}` only. So
  the clean addition is a **per-backend `apiKey`** threaded `backends.json → Backend → the chartsearchai
  override path`, so a Gemini arm can coexist with key-less local arms in one run. Small, real,
  contained.
- It is a **deliberate cloud arm** (cost, off-device) used purely as the frontier *reference point* —
  it does not change the on-device thesis, it sizes the gap to it. Sweep the scale ladder
  (Gemini → Gemma 4 12B → smaller Gemmas/Liquid) × grounding on/off on the item-1 axes to draw the curve.

### 2. RxQA-analog over the HIV/TB cohort  *(reproducible medication-reasoning benchmark)*
- Our demonstrator patients are on **ARV + anti-TB** regimens → build medication-reasoning scenarios
  (interactions e.g. rifampicin × ARVs, dosing, renal/hepatic adjustment, contraindications) under
  `datasets/validation/scenarios/` + a `comparison_sets/` set, graded against a formulary and the
  WHO HIV guideline.
- Run the AMIE **open-book vs closed-book** ablation natively: `med-agent-hub` `kb_search` **ON**
  vs **OFF** — a clean isolation of *grounding value* (and the experiment that would rescue or bury
  the multi-agent value proposition, given MedGemma's fine-tuning already didn't help).

### 3. Guideline + formulary grounding in `med-agent-hub`
- Give the hub's `medical_expert` / `kb_search` an authoritative corpus (WHO HIV-TB guidance, a
  formulary) and measure its lift on the item-1 management axes. Pairs directly with item 2's
  open/closed-book arms. (Aligns with the dissertation's *grounding-over-fine-tuning* thesis.)

### 4. Longitudinal multi-visit scenarios
- The 2.8 demo data is multi-visit (visits were reconstructed). Add "manage-across-visits" scenarios
  (track trajectory → adjust plan → follow-up), scored on item-1's `followup_quality` + plan axes —
  the chronic-HIV shape AMIE evaluated.

### 5. Re-test the reasoning arm where reasoning should matter
- `qwen3.6-35b` was *safe-but-not-top* on extraction. AMIE's deep-thinking management agent suggests
  reasoning matters **more for management**. Re-run it (and a CoT prompt) on the item-1/2 management
  tasks — the clean test of the reasoning payoff our last run only hinted at.

### 6. Point the human-calibration loop at management
- We already calibrate the LLM judge to humans (PPI / Gwet AC1 / clinician-anchored Benchmark via
  `harness/validate/adjudicate.py`). Re-aim that adjudication at the new management axes, where
  automated raters are weakest — mirrors AMIE's blinded-specialist gold standard at our scale.

## Sequencing
Item 1 (axes + Management Benchmark) unblocks the headline experiment and everything else.
**Item 1b — the controlled Gemini-vs-Gemma-4 model-scale curve on the management axes — is the single
experiment that most directly answers the dissertation post-AMIE.** Item 2 (RxQA-analog + open/closed
ablation) is the highest-information grounding ablation and supplies the curve's grounding-on/off axis.
Items 3–5 build on the same axes; item 6 is the calibration backstop and can run alongside.

## What this is NOT
Not a new agent (AMIE is an agent; we're the bench). Not history-taking/empathy (AMIE interviews the
patient; we're handed the chart). We import AMIE's **evaluation framework + grounding thesis**, on an
**open, reproducible, WHO-SMART/OpenMRS, on-device** footing — the niche AMIE does not occupy.
