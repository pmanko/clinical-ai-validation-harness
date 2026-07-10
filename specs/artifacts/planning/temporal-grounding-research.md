# Temporal grounding for clinical LLMs — evidence synthesis + grounded design

Purpose: replace the ad-hoc "anchor on a single most-recent date" temporal scaffold with an
evidence-founded representation. Triggered by `am-last-visit` reporting a TB **Program enrollment**
(2026-05-20) as the "last visit" when the last clinical **Visit** was 2026-01-07 — see
[[project_temporal_last_visit_record_type_confound]].

## Verdict
The candidate design is **well-founded**: (a) an explicit `Current date` for relative/future
questions, (b) a deterministic **typed + dated + chronological event timeline** the model reports
from, (c) precomputed numeric series for trends — plus one strongly-supported refinement:
(d) a **consistency/reflection check against the timeline**.

## Evidence (primary sources)
- **Typed dated event timeline is the standard + highest-yield scaffold.** EHRSHOT (NeurIPS 2023 D&B,
  arXiv:2307.02028) and Next-Event-Prediction (arXiv:2509.25591) represent a patient as ordered typed
  events `(type, value, timestamp)`. TISER (arXiv:2504.05258) — build an ordered timeline then reflect
  — took a 7B model **40.1%→91.5%** on TempReason-L3; its *reflection* stage was the most important
  component (ablation 91%→70%). TIMER (npj Dig Med 2025, arXiv:2503.04176) — XML longitudinal records
  with per-answer "Time Evidence Sets"; time-aware tuning +6.6% completeness, +9.2% temporal reasoning.
- **Small models NEED pre-structured input (our low-resource target).** Serialisation Strategy Matters
  (arXiv:2604.21076): chronological/narrative serialization lifted Mistral-7B medication-recon F1
  0.72→0.91 (+19) vs raw JSON; ≥70B models were ~tied on raw JSON. Structure is the lever for small
  open models specifically.
- **Don't do date math in-head — precompute / use tools.** SPAN (arXiv:2511.09993): tool/code-computed
  dates ~50%→95.31%. FHIR-AgentBench (arXiv:2509.19319): retriever-only 22-25% → +code 33% → multi-turn
  +retriever+code 50%; "code generation is essential for parsing complex FHIR data." Raw full-record
  dumps / long-context-alone fail (FHIR-AgentBench; Kruse/Gao EMNLP 2025, DOI 10.18653/v1/2025.findings-emnlp.1128).
- **Explicit dates rescue temporal reasoning** but future/relative dates are the worst case (SPAN;
  clinical AF/HF cohort study, Domingo-Aldama 2026, DOI 10.1007/s13755-025-00415-w).
- **AMIE is weak support for our setting.** "Towards Conversational AI for Disease Management" (Nature
  2026, DOI 10.1038/s41586-026-10764-5; arXiv:2503.06074) uses a running "Agent State" summary + a
  *visit-number counter* + Gemini long-context — NOT a dated timeline. But it never validates real
  calendar-date EHR reasoning (simulated visits 1-2 days apart), and temporal management reasoning was
  its weakest axis (§5.2.3, §2.2.2). Do NOT down-spec our real-dated design to AMIE's running-summary.

## Documented failure modes → mitigations
Temporal boundary violations (out-of-window data); chronological confusion (ordering — hardest category
even for GPT-4, TRAM arXiv:2310.00835); date arithmetic ("no internal today"; 23-35% drop on relative
dates; sharp drop on *future* dates, SPAN); **conflating heterogeneous resource/record types**
(FHIR-AgentBench). Mitigations with evidence: explicit ordered timeline (TISER); precompute / tool the
date math (SPAN); provide today's date; typed events.

## Literature gaps = our citable contributions (deterministic-guardrail axis)
1. **No paper tests conflating an administrative record (program enrollment) with a clinical visit** —
   the typed-event fix is evidence-aligned (event-typing is the foundation-model standard) but not
   demonstrated. Our harness can A/B it.
2. **No clinical A/B of precomputed-series vs in-context model-computed trends.** Fillable.
3. **Small-model serialization for temporal QA** specifically (our domain) is thinly covered.

## Grounded design + implementation path
- `Current date: <reference_date>` — always (cheap; future/relative dates fail worst). From the run
  reference_date (the judge's "now"), not the data — supersedes the latest-record anchor that caused
  the muddle.
- **Typed dated chronological event timeline** — group records by date, carry the event TYPE
  (Visit/Encounter vs Program-enrollment vs lab/Obs vs MedicationRequest vs Condition); a Program is
  labeled administrative, never "the latest visit."
  - **Now:** build from the chart text the hub already receives (records are already typed:
    `Finding`/`Test`/`Assessment`/`Drug order`/`Program`). Self-contained, fixes the bug.
  - **P2 (planned):** when the hub owns querystore retrieval, upgrade the source to the precise
    `querystore_visit`/`_encounter`/`_program` typed records. Same design, better source.
- **Precomputed numeric series** — keep; extend the "don't compute dates in-head" discipline to all
  date arithmetic (intervals, "N days ago", windowing).
- **Timeline-consistency check** (TISER's highest-yield single addition) — a verifier re-derives the
  answer from the typed timeline. Next increment, not the immediate fix.

Replaces the misleading `temporal.py` "Most recent record: max(all dates) — treat as latest visit"
line. Evaluation: score answers against a dated event set (TIMER-style time-evidence grounding), not
free-text plausibility.
