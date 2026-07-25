# AMIE management-evaluation layer: detailed implementation plan

> **Historical architecture note:** model-provider and ChartSearchAI integration details in this
> research plan predate the hub-profile relay. Its clinical-evaluation research remains background.

> The *why/what* is in `amie-management-axes-brief.md`; the full literature read is in
> `digging-in-research/06-amie-disease-management`. This is the *how, in detail*. Status: planning —
> several design decisions flagged for sign-off (§Decisions) before Phase 1 implementation.

## Framing: coordinates of the target domain — no single headline

This plan is organized by **target-domain coordinate** (see `amie-management-axes-brief.md`):
**A** = WHO-grounded management quality (Phase 1 below); **B** = medication grounding (Phase 3 / RxQA);
**C** = multilingual + localization — the *most novel* candidate (localized chart+question variants and a
raw-global-WHO-vs-localized-WHO-kb grounding ablation, scored on performance **and** in-language safety;
detail to be added once build-scope picks it up); **D** = the on-device/cloud reference (the section
below labelled "Phase 2 — model-scale experiment", now **de-headlined** to a reference coordinate). The
harness *scores* the measurable parts of A–D and *reports* openness + privacy/PHI-egress as run
properties. **There is no single-axis headline**; which coordinates this dissertation builds-and-validates
vs characterizes is the **open build-scope decision**. Phase 1 (Coordinate A) is the unblocker regardless.

## The core design insight (must settle first)

Our scenarios today are **extraction** ("what meds is the patient on?", `am-medications`). AMIE's
management axes score **decisions** ("what's the plan?"). You cannot judge "treatment appropriateness"
on a scenario that never asks for a treatment. So the management layer is **not just new rubric axes —
it is a new scenario *class* + new axes + a new benchmark, plus a shared guideline corpus that grounds
both the model and the judge.** Three coupled pieces:

1. **Management scenarios** (new eval content): prompts that elicit a plan over the HIV/TB cohort —
   "Given this chart, what is your management plan / what should change / what investigations next?"
2. **Management axes + Management Benchmark** (new scoring): AMIE's rater axes, LLM-judged, with a
   co-equal /100 headline beside Answer and In-Depth.
3. **A guideline + formulary corpus** (shared grounding): WHO consolidated HIV guidelines, WHO/national
   TB guidance, and a formulary (WHO Model Formulary, or OpenFDA/BNF as AMIE used). This corpus grounds
   **both** the hub's `kb_search`/`medical_expert` (the model under test) **and the judge** (so
   `guideline_grounding` is scored against the actual guideline, not the judge's parametric memory).

That third point is the load-bearing methodological choice: AMIE used human specialists who *know* the
guidelines; our LLM judge must be *given* the relevant guideline excerpt per cell to score management
honestly. This couples the judge corpus to the `kb` corpus.

---

## Phase 1 — Management scenarios + axes + Benchmark *(the unblocker)*

**1a. Scenario class.** Add `kind: "management"` (or a `management_probe` turn) to
`datasets/validation/scenarios/`. Seed ~8–12 over the three cohort patients (HIV staging + ARV choice,
TB co-treatment + rifampicin interactions, virologic failure → regimen switch, pregnancy + ARV safety,
pediatric dosing). Each carries the WHO-guideline reference span(s) it's graded against.

**1b. Rubric axes** (`.claude/skills/clinical-answer-scoring/rubric.md`): a **Management axes** block,
applied only to management scenarios, mirroring AMIE: `treatment_appropriateness` (0–10),
`investigation_precision` (0–10), `guideline_grounding` (0–10), `followup_quality` (0–10),
`inappropriate_treatment` (`ok`|`flag`). Each band must reference the provided guideline span. Keep
the Answer/In-Depth axes unchanged (separation of concerns, as we already do).

**1c. Judge schema + prep.** Extend the fan-out cell schema with the management block (present only for
management cells). `scripts/judge-prep.py` attaches the guideline span(s) to the cell so the judge
scores `guideline_grounding` against real text.

**1d. Management Benchmark** (`harness/validate/reconcile.py`): `cell_management_benchmark_score` —
same shape as `cell_benchmark_score` / `cell_indepth_benchmark_score`: e.g.
`(treatment·0.35 + investigation·0.25 + guideline·0.25 + followup·0.15)·10 − big penalty if
inappropriate_treatment=flag`, floored 0. Aggregate per arm into a `management` namespace; **red-first
test** in `evals/validate/test_reconcile.py` (hand-computed expecteds, like the In-Depth one).

**1e. Report + index** (`report.py`, `build-reports-index.py`): a **third co-equal benchmark column**
(Answer · In-Depth · Management) + a management-axes table, reusing the In-Depth-block pattern we just
built (sortable, un-hidden, definition-grid legend).

## Phase 2 — A frontier cloud reference arm *(Coordinate D — de-headlined, formerly "the model-scale experiment")*

**2a. Per-backend auth plumbing** (grounded; this is the real new code):
- `harness/validate/models.py`: add `api_key: str | None = None` to `Backend` + `from_dict` (`apiKey`).
- The runner/client path: thread `api_key` into the chartsearchai override request.
- **chartsearchai** (`ModelSwitchService.java`, the submodule): accept a **per-request** `apiKey` in the
  override (today it reads the *global* `chartsearchai.llm.remote.api_key`). This is a small Java change
  in the fork → its own PR.
- `datasets/validation/backends.json`: a `gemini-*` arm → endpoint
  `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`, model `gemini-2.5-flash`
  / `-pro`, `apiKey` from env (never committed).

**2b. The curve.** A comparison set sweeping the scale ladder (Gemini → Gemma 4 12B → smaller Gemmas /
Liquid) **× grounding on/off** (`kb_search` ON/OFF) on the Phase-1 management scenarios → the
management-quality-vs-model-scale curve. Reuse the Q8/Q4 quant-control rig.

**2c. Honest framing in the report**: base Gemini vs base Gemma under *our* scaffolding — a controlled
model-axis test, **not** an AMIE replication; no result asserted in advance.

## Phase 3 — RxQA-analog *(medication reasoning)*

Medication-reasoning scenarios over the ARV/TB cohort (rifampicin × PI/NNRTI interactions, renal/hepatic
dosing, contraindications, pregnancy), graded against the formulary + WHO guideline, run **open-book
(`kb_search` ON) vs closed-book (OFF)** — the cleanest isolation of grounding value, and the most
direct test of whether grounding (not fine-tuning) is the lever.

## Phases 4–6 — build-out
4. **Hub grounding**: load the WHO HIV-TB guideline + formulary into the hub `medical_expert`/`kb_search`;
   measure lift on the Phase-1 axes (pairs with Phase 3's open/closed arms).
5. **Longitudinal**: multi-visit "manage across visits" scenarios over the reconstructed-visit demo data,
   scored on `followup_quality` + plan axes.
6. **Reasoning re-test + adjudication**: re-run `qwen3.6-35b` (and a CoT prompt) on the management
   tasks (where reasoning should matter more than on extraction); re-aim the
   `harness/validate/adjudicate.py` PPI/AC1 human-calibration at the management axes.

---

## Decisions to settle before Phase 1 (your call)

1. **Guideline/formulary source.** WHO Consolidated HIV Guidelines + WHO TB + WHO Model Formulary
   (open, LMIC-aligned, on-thesis) vs AMIE's OpenFDA/BNF (comparable to AMIE but high-income). Recommend
   **WHO-first** (matches the SMART-Guidelines thesis), optionally add BNF/OpenFDA for an AMIE-parallel.
2. **Management probe shape.** A standalone "what's your plan?" turn vs grading the implied plan inside
   the existing answer. Recommend a **dedicated management turn** (clean signal; matches AMIE's design).
3. **Judge grounding.** Provide the guideline span to the judge per cell (rigorous, couples judge↔kb) vs
   rely on the judge's parametric knowledge (cheaper, weaker). Recommend **provide the span**.
4. **Gemini arm now or later.** It needs the chartsearchai Java change + an API key + cloud spend. Do it
   in Phase 2 (after the axes exist) — but the per-backend-`apiKey` plumbing can land early since it's
   independently useful.

## Sequencing
Phase 1 (scenarios + axes + Management Benchmark + report) is the unblocker and the bulk of the
*harness* work. Phase 2's auth plumbing can land in parallel; the curve run waits on Phase 1. Phase 3
(RxQA + open/closed) is the highest-information single experiment once axes exist. Phases 4–6 build on
the same axes and corpus.
