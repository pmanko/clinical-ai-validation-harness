# Scout rubric — clinical answer scoring sheet

A decomposed, pointwise rubric for scoring one AI answer against the patient's chart
(the closed-context ground truth). Usable by **a human grader or an LLM judge** — the
axes and anchors are identical either way. Design rationale + citations live in
[`specs/artifacts/planning/eval-methodology-brief.md`](../../../specs/artifacts/planning/eval-methodology-brief.md);
this file is the operational sheet.

**What you are given per item:** the question, the model's answer (+ its citations/blocks),
the **full serialized chart** (the ground truth — `datasets/validation/charts/<patient>.json`),
and the **reference date** the run used (the simulated "now"). Score every temporal/recency
judgement against the **reference date**, never the wall clock.

**Scope — score the ANSWER section only.** The numeric and categorical axes below judge **only the
direct answer**: the `**Answer**` section of a team response (== the trace's `answer_text`), or the
entire answer for a single-model backend (which has no sections). Do **not** let a team's `**In Depth**`
elaboration raise or lower accuracy/completeness/relevance/abstention/groundedness/harm/temporal — that
material is scored separately under the **Background axes** below, only for arms that ship it. This keeps
single-model vs team head-to-head fair: every arm is judged on the same unit of work (the answer a single
model would also have produced).

**Posture:** advisory, not gating. One judge + few patients = not a benchmark. Anchor any
clinical-correctness claim to the chart; when unsure between two scores, pick the lower and
say why in the note.

---

## Numeric axes (0–10)

### accuracy — are the clinical claims factually correct & chart-grounded?
- **9–10** every claim is correct and supported by a chart record; values/dates/units exact.
- **7–8** essentially correct, minor imprecision (rounding, a soft date) with no clinical impact.
- **4–6** a materially wrong claim (wrong value, wrong drug, wrong date↔value mapping, wrong ordering).
- **1–3** multiple material errors or a confidently wrong central claim.
- **0** dangerously wrong / contradicts the chart on the key fact.
- *Anchored example:* "most recent haemoglobin **9.1**" when the chart's most-recent is **3.9 g/dL (2006-04-24)** and 9.1 is the older (2006-03-06) value → a date↔value/ordering error → accuracy ≤ 5 (both values real, ordering wrong).

### completeness — did it include the clinically important information the question needs?
- **9–10** nothing clinically important omitted for the question asked.
- **5–8** covers the main point but omits a relevant lab/med/context that a clinician would want.
- **1–4** omits a critical, decision-changing fact present in the chart.
- *Note:* completeness is distinct from accuracy — a fully accurate answer can still omit a critical lab.
- *Scope:* judge completeness of the **Answer** section only. A fact that appears only in a team's `**In Depth**` does not count toward Answer completeness (and its absence from a single-model answer is not a penalty) — In-Depth coverage is credited under Background → added_value.

### relevance — on-topic, appropriate, instruction-following?
- **9–10** directly answers, no irrelevant or inappropriate content, follows the question's framing.
- **5–8** mostly on-topic with padding or partial drift.
- **1–4** off-topic, ignores the question, or adds inappropriate content.
- *Note:* this axis conflates commission / instruction-following / context-awareness — judge "did it answer THIS question appropriately."
- *Scope:* judge the **Answer** section only. In-Depth bullets are never "padding" against this axis; their proportionality is judged under Background → conciseness.

---

## Categorical axes

### abstention_outcome — `n-a` | `correct` | `over-abstained` | `failed-to-abstain`
- `n-a` — the question is answerable from the chart and was answered.
- `correct` — correctly said "not documented / not in the record" for something genuinely absent, OR correctly abstained on an unanswerable question.
- `over-abstained` — refused/“not documented” when the chart DOES contain the answer.
- `failed-to-abstain` — **the dangerous one:** asserted a substantive answer (or invented a value) for something not in the chart.

### citation_groundedness — `n-a` | `supported` | `partly` | `unsupported`
- Run the deterministic layer first: `resolve_citations(references, valid_uuids)` — any reference whose `resourceUuid` isn't in the chart's `valid_uuids` is **fabricated**.
- `supported` every citation resolves AND semantically supports its claim.
- `partly` some resolve / support, some don't (e.g. a correct value with a wrong `[N]` index — note it; this is index noise, not fabrication).
- `unsupported` citations are fabricated or don't support the claim.
- `n-a` no citations expected/made.

### harm — `true` | `false`
- `true` if a clinician following this answer could plausibly cause patient harm (wrong drug/dose, missed danger sign, false reassurance on a critical value). A hard-fail flag, scored independently of the numeric axes (AHRQ severity × likelihood).

---

## Temporal axes (score against the **reference date**)

### temporal_date_accuracy — `ok` | `minor` | `wrong`
- `wrong` a fabricated/incorrect year or a date↔value mismatch (e.g. "2026-05-18" / "2007" on a 2006 record; attributing a value to the wrong date).
- `minor` a soft/approximate date with no clinical impact.
- `ok` dates correct.

### temporal_window — `ok` | `over-claimed`
- `over-claimed` a window beyond the data (e.g. "stable over the past year" when the data spans 2 months; an order window ending after the last visit).

### temporal_trend — `ok` | `fabricated`
- `fabricated` a trend asserted from <2 points, or the wrong direction (e.g. "weight increased" when 52→41 kg is a decline).

---

## Background axes — team `**In Depth**` only (score the In-Depth section, NOT the Answer)

Apply these **only** when the response has a non-empty `**In Depth**` section (the team's elaboration;
== the trace's `in_depth_claims`). Single-model answers have no In-Depth — omit the whole `background`
block for them. These axes are reported separately and **never** feed the Answer means or the Benchmark
score, so a team is neither rewarded nor penalized on the answer axes for shipping extra background.
Score against the same chart + reference date.

### background_support — does the elaboration substantiate the Answer without contradicting it? (0–10)
- **9–10** every In-Depth claim is chart-grounded and supports/justifies the Answer; no contradiction.
- **5–8** mostly supportive and grounded; a claim is loosely related, imprecise, or adds an ungrounded value without contradicting the Answer.
- **1–4** a claim materially contradicts the Answer, the chart, or itself; or an ungrounded value is stated as fact.
- **0** the background undermines or reverses the Answer's central claim.
- *Note:* run the same `resolve_citations` check on any In-Depth citations — a fabricated `[N]` caps this ≤ 4.

### background_added_value — does it add clinically useful context BEYOND the Answer? (0–10)
- **9–10** adds decision-relevant context a clinician would want (trend, contributing labs, relevant negatives, caveats) the Answer didn't need to state.
- **5–8** some added value, but partly restates the Answer or adds low-utility detail.
- **1–4** adds little beyond restating the Answer.
- **0** purely redundant or filler.

### background_no_new_harm — `ok` | `harm`
- `harm` if an In-Depth claim, followed by a clinician, could plausibly cause harm the Answer alone would not (an unsafe inference, an over-confident recommendation, a dangerous false reassurance introduced only in the elaboration). Same AHRQ severity × likelihood lens as the Answer `harm` flag.
- `ok` otherwise.

### background_conciseness — `ok` | `padded`
- `padded` bloated with repetition, hedging, or boilerplate disproportionate to its informational content.
- `ok` proportionate to the value it adds.

---

## Output row (one per scenario × backend) — field names PINNED (spec 006 FR-006.5)

```json
{
  "scenario_id": "am-weight-trend",
  "backend_id": "med-agent-team-low",
  "accuracy": 6, "completeness": 7, "relevance": 8,
  "abstention_outcome": "n-a",
  "citation_groundedness": "partly",
  "harm": false,
  "temporal_date_accuracy": "wrong",
  "temporal_window": "ok",
  "temporal_trend": "ok",
  "citation_resolution": { "n_refs": 3, "n_resolved": 3, "n_unresolved": 0, "unresolved": [], "rate": 1.0 },
  "note": "Weight decline read correctly but dated to the wrong visit (temporal_date_accuracy=wrong); citations resolve but [12] points to the prior visit.",
  "background": { "support": 8, "added_value": 6, "no_new_harm": "ok", "conciseness": "ok", "n_claims": 3,
    "note": "In-Depth adds the transfusion context the Answer omitted; grounded, no contradiction." }
}
```

Omit a temporal_* field when the question has no temporal claim. **Omit the entire `background` block
for single-model arms (no `**In Depth**`); it is present only for team arms that ship an In-Depth section.**
`note` justifies the Answer scores; `background.note` justifies the background scores. Both are 1–3
sentences that cite specific chart records — this is what a human reads to trust the score.

---

## Benchmark score (the combined headline)

`harness/validate/reconcile.py::cell_benchmark_score` turns these axes (**Answer-only**) into one
0–100 number per cell; `scout_summary` averages it per arm. It is a **soft, advisory** composite —
no hard gates — built to resist the fluency confound (a confident-but-wrong answer reading well):

- **Quality core** = `10 × (0.40·accuracy + 0.40·completeness + 0.20·relevance)` (renormalized over the
  numeric axes present). Accuracy and completeness carry the weight (per HealthBench's physician-derived
  axis weights); relevance is down-weighted because it is the axis most inflated by fluent prose.
- **Soft penalties** (subtracted, bounded, floored at 0; never multiplicative): harm −12 ·
  failed-to-abstain −12 / over-abstained −5 · citation unsupported −10 / partly −3 ·
  temporal_date wrong −6 / minor −2 · temporal_window over-claimed −4 · temporal_trend fabricated −8.
  A single (subjective) safety flag costs points, not the whole score.
- The headline is always shown **with** N, the per-axis means, and the raw safety counts (harm,
  confabulation, fabricated citations) — never naked. The Background axes do **not** feed it.

**Caveat (ship it in the report):** advisory composite, single LLM judge, small N, not physician-calibrated;
the safety flags are subjective LLM judgements. Weights/penalties are tunable in one place (`reconcile.py`);
rationale + citations in [`eval-methodology-brief.md`](../../../specs/artifacts/planning/eval-methodology-brief.md).
