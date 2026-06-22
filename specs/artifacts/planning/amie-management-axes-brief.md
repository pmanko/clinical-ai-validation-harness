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
Item 1 unblocks everything (the axes + Management Benchmark). Then item 2 (RxQA-analog + open/closed
ablation) is the highest-information single experiment. Items 3–5 build on the same axes; item 6 is
the calibration backstop and can run alongside.

## What this is NOT
Not a new agent (AMIE is an agent; we're the bench). Not history-taking/empathy (AMIE interviews the
patient; we're handed the chart). We import AMIE's **evaluation framework + grounding thesis**, on an
**open, reproducible, WHO-SMART/OpenMRS, on-device** footing — the niche AMIE does not occupy.
