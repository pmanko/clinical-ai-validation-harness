# Scoring the low-resource target domain: harness extension plan

> Dev brief. The framing + literature read live in the dissertation workspace
> (`digging-in-research` → `06-amie-disease-management`; §3.0 of `01-research-foundation`). This
> translates it into concrete harness work. Status: proposed; **build-scope under discussion**.
> Owner: validate lane.

## The framing: the harness scores the target domain's coordinates

The design unit is the **low-resource clinical target domain** — a *constellation* of coordinates
(task-shifted workforce, on-device/low-infra, data sovereignty, WHO clinical logic, multilingual care,
localized knowledge), **not a single axis**. The harness's job is to **score what is measurable about
serving that target, and report the rest as run properties**:

- **Scored** (judged per cell): WHO-grounded **management/decision quality** (the AMIE-derived axes);
  **medication reasoning** grounded in the local formulary; **multilingual performance AND safety**;
  on-device/quantization cost; latency/cost.
- **Reported as run properties** (not per-answer scores): openness/license; privacy/PHI-egress.

That split is the empirical-contribution map. AMIE's blinded management evaluation is the *template* for
the first scored coordinate — we apply it on **WHO logic for the HIV/TB cohort**, not NICE/BMJ. A
**frontier cloud arm (e.g. Gemini)** belongs in the harness, but as a **de-headlined reference** that
sizes the gap to the on-device target on each coordinate — not as the thesis.

## Why this layer at all (what's missing today)

Our harness scores **extraction** (`accuracy / completeness / relevance / citation_groundedness / harm
/ temporal`) — "did it read the chart right?". It does **not** score **management** ("is the plan
right?"), **medication reasoning**, or **multilingual safety** — the coordinates that actually
characterize serving the target. Two consequences: (a) our "scaffolding adds little over a single model"
finding is measured *only on extraction*, where a strong model already saturates — the
management/grounding/multilingual layer is where scaffolding + grounding might finally earn their keep;
(b) the dissertation's object (WHO-grounded, multilingual, low-infra decision support) needs these
coordinates measured directly, not proxied.

## Work items (grouped by coordinate; grounded in current files)

### Coordinate A — WHO-grounded management / decision quality  *(the unblocker; AMIE template)*
1. **Management axes + Benchmark.** AMIE-style axes — `treatment_appropriateness`,
   `investigation_precision`, `guideline_grounding`, `followup_quality`, `inappropriate_treatment` —
   scored on a management probe, **graded against WHO HIV/TB logic**. Files:
   `.claude/skills/clinical-answer-scoring/rubric.md`; the judge schema; `harness/validate/reconcile.py`
   (a **Management Benchmark** /100, same shape as the Answer/In-Depth Benchmarks); `report.py` + index
   (a co-equal column). Red-first tests in `evals/validate/test_reconcile.py`.
2. **Management scenario class.** A `kind: management` class over the HIV/TB cohort (staging/ARV choice,
   TB co-treatment, virologic failure → switch, pregnancy, pediatric), each carrying the WHO guideline
   span it's graded against.
3. **Longitudinal.** Multi-visit "manage across visits" scenarios — the chronic-HIV shape.

### Coordinate B — medication reasoning + grounding (the RxQA-analog)
4. **RxQA-analog** over ARV/TB regimens (rifampicin × ARVs, dosing, renal/hepatic, contraindications,
   pregnancy), graded against the **WHO/localized formulary**, run **open-book (`kb_search` ON) vs
   closed-book (OFF)** — the clean grounding ablation (and the test of whether grounding, not
   fine-tuning, is the lever).
5. **Hub grounding.** Load the WHO HIV-TB guideline + formulary into `med-agent-hub`
   `medical_expert`/`kb_search`; measure lift on the Coordinate-A axes.

### Coordinate C — multilingual performance + safety  *(highest-value novel axis; the PI's localization thrust)*
6. **Multilingual scenarios.** Localized variants (chart + question in-language; start **Polish**
   [PI-fluent] + **French** [examples]), scored on **both performance and the harm/safety axis**
   in-language. Published evidence: performance drops 10–35 pts and **safety collapses** in low-resource
   languages — *worst for the small open on-device models* we deploy; AMIE reports zero non-English eval.
7. **Localization ablation (the deeper contribution).** Grade a model grounded in the **raw global WHO**
   corpus vs a **localized WHO kb** (language + jargon + clinical reality: formulary, epidemiology):
   does localization improve grounded, *safe* management? This is the *localization mile* (L1→L2 DAK),
   evaluable as a grounding ablation.

### Coordinate D — on-device / resource (the model-scale reference)
8. **A frontier cloud reference arm (e.g. Gemini).** A `backends.json` entry → Gemini's OpenAI-compat
   endpoint. Mechanics (grounded): chartsearchai's remote api key is a **global** property and the
   harness `Backend` override (`harness/validate/models.py`) carries `{endpointUrl, modelName}` only — so
   the clean addition is a **per-backend `apiKey`** threaded `backends.json → Backend → override`. Tag it
   with its **violated** properties (cloud · closed · PHI-egress) so the leaderboard shows the *trade*,
   not just the number. Sweep the ladder (cloud → Gemma 12B → smaller) × grounding on/off to size the
   on-device gap on each scored coordinate — a *reference reading*, not the headline.

### Cross-cutting — human calibration
9. **Point the adjudication loop at the new axes.** We calibrate the LLM judge to humans (PPI / Gwet
   AC1 via `harness/validate/adjudicate.py`); re-aim it at management + multilingual-safety, where
   automated raters are weakest — AMIE's blinded-specialist gold standard, at our scale.

## Build-scope (the open decision — in discussion)
Coordinate A (management axes + Benchmark) is the unblocker and the cleanest AMIE template. Beyond that,
**which coordinates this dissertation actually *builds + validates* vs *characterizes as landscape* is
the open decision** — not every coordinate ships in one study. The most novel / highest-information
candidates are **Coordinate C (multilingual + localization)** and **Coordinate B (medication grounding
ablation)**; Coordinate D (cloud reference) is cheap to add as context. This is what we're deciding now.

## What this is NOT
Not a new agent (AMIE is an agent; we're the bench). Not history-taking/empathy (we're handed the
chart). And **not a single-axis / model-scale headline** — the contribution is serving the target domain
across its coordinates, scoring what's measurable and reporting the rest. We import AMIE's **evaluation
framework + grounding thesis** on an **open, reproducible, WHO/OpenMRS, on-device, multilingual** footing
— the target AMIE does not occupy.
