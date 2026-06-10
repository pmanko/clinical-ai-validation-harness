# Temporal reasoning in clinical AI — failure taxonomy, research foundations & the fix

> Why our answers get dates and trends wrong, what the research says (incl. time-series-tuned foundation models), and the approach with the strongest foundation. Grounded in the actual run data (Zabella run `1528100e`, judged) + ~50 papers gathered 2026-06-04 across four research strands. Citations are arXiv IDs unless a journal DOI is given. Companion to [eval-methodology-brief.md](eval-methodology-brief.md).

## TL;DR

1. **These are not time-series-forecasting failures, and a time-series foundation model would not fix them — it would make two of them worse.** Our temporal data is sparse and irregular (5 weights over 2 months, a *single* CD4); TS-FMs assume regular, dense sampling and will happily extrapolate a "trend" from one point. *Strongest, most surprising conclusion — and it directly answers the question that motivated this brief.*
2. **The root cause is well-established: transformers derive dates/intervals/trends unreliably in-context, and "reason harder" (CoT, longer context) does not fix it.** Best-in-class models score ~47% on clinical date calculation and ~59% on 3-digit multiplication. *Strong, multi-source.*
3. **The fix with the strongest foundation: compute the temporal facts deterministically server-side, inject them as structured evidence, and have the validator *recompute* (not entail) to check claims.** The same computation serves the answer path and the validator. *Strong; maps onto our existing chart-envelope builder + reconcile layer.*
4. **Cheap, model-agnostic guardrails close the specific failures:** no trend claim with <2 points; clamp every temporal claim to the actual data window; flag any cited date outside it. *Strong on principle; the specific thresholds are our design rules, enforced in the validator.*
5. **Our eval has a temporal blind spot to fix too:** clinical temporal benchmarks show heavy recency bias (questions cluster at the end of the record), so "grab the latest value" looks better than it is. Add a temporal-correctness axis and mid-timeline questions. *Strong.*
6. **Defer per-model fine-tuning.** It has the strongest *causal* proof it works but is not model-agnostic (must be redone across our 4B–35B fleet). Pursue only if 3–4 plateau.

## The grounded problem — failure taxonomy (from the judged run)

Five distinct temporal failure modes, observed in the actual answers. Weak/small lanes (`team-low`, `team-med`) fail most; strong arms (`a4b`, `team-high`) scope correctly — so this is *partly* model capability and *partly* a pipeline gap (the chart envelope hands over raw dated points and lets the model derive trends/windows/dates itself).

| | Failure | Real example (judged) | Research support |
|---|---|---|---|
| **A** | Trend fabricated from a single point | `team-low` CD4: *"consistently around 341 since initial visit"* (one CD4 exists) → acc 3 | By analogy — an insufficient-evidence/over-generalization failure; no benchmark isolates it (handle with a deterministic guard) |
| **B** | Window / scope hallucination | `team-low`/`team-med` weight: *"stable over the past year"* (data spans only Feb–Jun 2006) → acc 2–4 | **Direct**: MenatQA *scope* factor [2310.05157]; models over-rely on the question's stated time frame |
| **C** | Wrong date↔value mapping | `team-med`: *"73 kg on June 6"* (June 6 = 71 kg) | Moderate: event-time binding [TempReason 2306.08952; ChronoSense 2501.03040]; also a retrieval/serialization error |
| **D** | Date typos / fabricated dates | `e2b`: *"2004-04-25"* (should be 2006); `team-low` fabricates *"last tested 2006-03-06 [314]"* (no such obs) | **Direct**: date primitives individually unreliable [PRIMETIME 2504.16155]; memorization over computation [ChronoSense 2501.03040] |
| **E** | End-date drift past last visit | `a4b` orders window ends Aug 6 when last visit is Jun 6 | By analogy — scope (B) + date arithmetic (D) |

## Decision 1 — Time-series foundation models: the wrong tool for these failures

**Foundation: strong, and it's a capability mismatch — not a tuning gap.** Independently confirmed across the survey: the mainstream TS-FMs — **TimesFM** [2310.10688], **Chronos** [2403.07815], **Moirai** [2402.02592], **MOMENT** [2402.03885], **Lag-Llama** [2310.08278], **TimeGPT** [2310.03589], **Timer** [2402.02368], **UniTS** [2403.00131], **Time-LLM** [2310.01728], **GPT4TS/"One Fits All"** [2302.11939], **TEMPO** [2310.04948], **TOTEM** [2402.16412] — all do **forecasting / imputation / anomaly / classification** by mapping an *ordered, regularly-spaced* value sequence to other values. Three things break in our regime:

- **Too few points.** TimesFM's input patch is 32 points; 5 weights is a *fraction of one token*. Chronos scales/quantizes per series by its mean — noise at n≈5. With a single CD4 there is no series.
- **Irregular spacing is an architectural violation.** These models patch/tokenize by *index*, not elapsed time; the real datetime is at most an optional covariate. "3 days, then 41 days, then 6 days" is silently treated as evenly spaced unless you resample — and resampling a sparse outpatient series *fabricates points* (the imputation-as-hallucination trap, i.e. failure A by another route).
- **A trend needs ≥2 points.** Given one point a forecaster still emits an extrapolation — it would *reproduce* failure A, not prevent it.

**Where a TS-FM *would* fit (a different, future feature):** forecasting clinical deterioration from a genuinely **dense, regularly-sampled** stream (inpatient/ICU vitals, CGM glucose, daily home BP/weight). There the assumptions hold; prefer a clinically-pretrained, irregularity-aware model (**MIRA** CT-RoPE/Neural-ODE [2506.07584]) over a grid-based general TS-FM. For *moderately*-sampled irregular series the correct lineage is the irregular-clinical-TS family — **GRU-D** [1606.01865], **Latent ODE** [1907.03907], **SeFT** [1909.12064], **mTAND** [2101.10318], **Raindrop** [2110.05357] — but these are trained task models (classification/interpolation), not chart-Q&A trend readers. **None of these addresses failures A–E.**

## Decision 2 — Why "prompt harder" won't fix it (the case for offloading)

**Foundation: strong, multi-source, including in-domain.** The model's own numeric/temporal primitives are the bottleneck:
- **Clinical date calc tops out ~47%.** MedCalc-Bench [2406.12036]: date-based tasks reach 46.7% even for GPT-4 with a worked example (overall 50.9% one-shot CoT); the authors conclude LLMs "are not yet ready" for clinical calculation. A 2026 audit [2603.02222] argues much of even that is closed-book recall.
- **Arithmetic is unreliable in general.** Faith-and-Fate [2305.18654]: GPT-4 ~59% on 3-digit×3-digit multiplication; transformers reduce computation to "linearized subgraph matching." PRIMETIME [2504.16155]: isolated datetime parsing/arithmetic primitives range from near-zero to perfect — *individually unreliable*, so everything built on them (windows, "most recent", durations) inherits the unreliability.
- **CoT and longer context don't rescue it, in our exact setting.** A longitudinal-clinical study [2501.18724] found CoT did *not* beat direct generation and multi-day context did *not* reliably beat single-day. The robust move is to compute the fact and hand it over.

The offload thesis has direct support: **Program-of-Thoughts** [2211.12588] (~+12% over CoT by separating computation from reasoning), **PAL** [2211.10435] (SOTA on 12/12 reasoning benchmarks; "LLMs make arithmetic mistakes even when decomposition is correct"), **Toolformer** [2302.04761] ("LMs struggle with basic arithmetic where much simpler models excel").

## Decision 3 — The recommended approach (ranked by foundation × fit)

The ranking deliberately resists the headline "tools get 95%" number ([SPAN 2511.09993]: 34.5%→95.31% with a code-gen Time Agent) — that is **GPT-4o**, and our single-model arm is 4B–35B local, where tool-call reliability degrades and a missed call silently falls back to in-context derivation. So:

**R1 (build first) — Inject computed temporal evidence into the chart envelope.** Server-side, per observation series, compute and serialize as an aligned table (ISO dates, units, `resourceUuid` per row): most-recent value+date, min/max+dates, deltas, slope/trend direction, inter-observation intervals, patient age, and the **data-window bounds (earliest, latest, span)**. The model *reports* facts instead of *deriving* them. Lowest cost (the envelope is already built), unconditional (no reliance on a small model choosing a tool), and the computation is reused by R4. *Foundation: strong* — Faith-and-Fate, PoT, PAL, and in-domain 2501.18724. Serialization is a real lever, not cosmetic — aligned tables + explicit ISO dates + careful digit handling materially affect reading accuracy [Table-meets-LLM 2305.13062; LLMTime tokenization insight 2310.07820].

**R2 (next, for the team / larger arm) — Tool calls for date math + series stats.** Add typed `date_diff` / `most_recent` / `compute_trend` / `window_bounds` into med-agent-hub's existing ReAct tool loop. *Foundation: strong but conditional* — ReAct [2210.03629] reduces hallucination by grounding; SPAN/Time-Agent shows the ceiling; but deploy where invocation is reliable (orchestrator/larger or cloud arm), with R1's injected block as the floor. TReMu [2502.01630] (29.83→77.67 by generating Python for temporal calc + a timeline memory) shows the size of the prize when arithmetic is externalized.

**R3 (cheap, in parallel) — Temporal abstention / clamping guardrails.** Prompt rules + validator enforcement: no trend with <2 points (kills A); clamp every claim to the data window so "past year" over 2 months and end-date drift are impossible (kills B, E); flag any cited date outside the window (catches D). *Foundation: strong on principle* [R-Tuning 2311.09677; Mallen 2212.10511 — abstain when support is thin]; **honesty label: the specific thresholds (N≥2, clamp-to-window) are our design rules, not cited values.** Soft on the answer path (small models follow inconsistently) → the teeth live in R4.

**R4 (with R1 — same code, reused as a check) — Validator that recomputes, not entails.** In `reconcile`, for each temporal/numeric claim: parse the asserted trend/window/date↔value, **recompute** from the series, compare deterministically; reserve LLM/NLI for fuzzy prose only. *Foundation: strong* — EQUATE [1901.03735]: NLI on quantitative claims ≈ majority baseline while a symbolic checker gains +24.2%; temporal NLI is also weak off-the-shelf [Vashishtha, ACL-Findings-EMNLP 2020]. This **resolves the open gap our eval brief flagged** (trends don't survive atomic-claim decomposition; plain NLI under-catches numeric fabrication). Prose claims still use the existing faithfulness stack [FActScore 2305.14251; RAGAS 2309.15217; ALCE 2305.14627].

**Structural complement (both arms):** build the timeline/ordering **deterministically** and give it to the model rather than asking it to construct it — timeline/graph intermediates raise temporal accuracy and let smaller open models beat larger closed ones [TG-LLM 2401.06853; TISER 2504.05258]. For the prompt-only smallest-model path, Narrative-of-Thought [2410.05558] is the one temporal-CoT method validated *specifically* for <10B models (training-free). Don't re-serialize the whole chart each turn — a maintained, dated patient-state beats re-reading raw history over long horizons [Vital Trace 2602.12833].

## Decision 4 — What clinical NLP already settled (reinforces R1/R3/R4)

**Foundation: strong.** Every robust EHR model encodes time *explicitly* rather than leaving it to token order: age embeddings (BEHRT, *Sci Rep* 2020), discretized inter-event interval tokens (**CEHR-BERT** ATT buckets [2111.08585]; **ETHOS** [2407.21124]), or time-as-target (**MOTOR** [2301.03150]). Clinical temporal extraction shows the hard parts are exactly ours: i2b2-2012 [*JAMIA* 2013] had EVENT F1 0.92 but TIMEX3 ~0.66 / TLINK ~0.69, with **relative dates and reference-time anchoring** the dominant failures; Clinical TempEval relations sit ~0.40 and **drop ~20 pts cross-domain** — so don't trust model-derived ordering; normalize to ISO 8601 against an explicit anchor (HeidelTime/SUTime) and order by computed timestamps.

## Decision 5 — Fix the eval's temporal blind spot

**Foundation: strong.** TIMER [2503.04176] shows clinical temporal benchmarks are recency-biased — 55.3% of MedAlign instructions fall in the last quarter of a ~10.7-year record — so "anchor to the latest value" scores well while mid-timeline reasoning fails. Two changes: (1) add a **temporal-correctness axis** to the Scout rubric (date accuracy, window scoping, trend-justified-by-points, no fabricated dates) — it currently rides inside "accuracy"; (2) add **mid-timeline and "as of date X" / "between A and B"** scenarios, not just "latest"/"most recent". TIMER-Instruct's +7.3/+9.2 gains confirm temporal competence is measurable and improvable.

## How this maps to the implementation (and the existing plan)

- **R1** = extend the chart-envelope builder (chartsearchai-side / hub-side) to emit a deterministic temporal-evidence block. Reuses the dated records we already assemble.
- **R4** = a temporal check inside the shared `reconcile` module, consumed by both the offline judge (Track 5) and the runtime **validator (Track 4)** — recompute-then-diff, the same code as R1.
- **R3** = guardrail lines in the harmonized prompts (Track 2/6) + enforced in the validator.
- **R2** = new typed tools in the hub's tool loop (team/larger arm).
- **Eval** = a temporal axis in the Scout rubric + mid-timeline scenarios (Track 5).
- The judge stays advisory + human-calibrated; deterministic temporal checks are the cheap, sound floor that should run on every answer.

## Key sources

LLM temporal reasoning: Test of Time [2406.09170], TempReason [2306.08952], TimeBench [2311.17667], TRAM [2310.00835], MenatQA [2310.05157], TimeQA [2108.06314], TempLAMA [2106.15110], TIMEDIAL [2106.04571], ChronoSense [2501.03040], PRIMETIME [2504.16155]. Time-series FMs: TimesFM [2310.10688], Chronos [2403.07815], Moirai [2402.02592], MOMENT [2402.03885], Lag-Llama [2310.08278], TimeGPT [2310.03589], Timer [2402.02368], UniTS [2403.00131], Time-LLM [2310.01728], GPT4TS [2302.11939], TEMPO [2310.04948], TOTEM [2402.16412]; irregular-clinical: GRU-D [1606.01865], Latent ODE [1907.03907], SeFT [1909.12064], mTAND [2101.10318], Raindrop [2110.05357]; MIRA [2506.07584]. Clinical/EHR temporal: CEHR-BERT [2111.08585], MOTOR [2301.03150], ETHOS [2407.21124], EHRSHOT [2307.02028], i2b2-2012 [*JAMIA* 2013], Clinical TempEval [SemEval-2017 Task 12], MedCalc-Bench [2406.12036] (+audit [2603.02222]), TIMER [2503.04176], Vital Trace [2602.12833]. Integration/offload: Faith-and-Fate [2305.18654], PoT [2211.12588], PAL [2211.10435], Toolformer [2302.04761], ReAct [2210.03629], SPAN [2511.09993], TReMu [2502.01630], TG-LLM [2401.06853], TISER [2504.05258], Narrative-of-Thought [2410.05558], LLMTime [2310.07820], Table-meets-LLM [2305.13062], "Are LMs useful for TS forecasting?" [2406.16964], EQUATE [1901.03735], temporal-NLI Vashishtha [ACL-Findings-EMNLP 2020], R-Tuning [2311.09677], Mallen [2212.10511], longitudinal-clinical CoT study [2501.18724].
