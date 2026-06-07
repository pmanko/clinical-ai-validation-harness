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

### relevance — on-topic, appropriate, instruction-following?
- **9–10** directly answers, no irrelevant or inappropriate content, follows the question's framing.
- **5–8** mostly on-topic with padding or partial drift.
- **1–4** off-topic, ignores the question, or adds inappropriate content.
- *Note:* this axis conflates commission / instruction-following / context-awareness — judge "did it answer THIS question appropriately."

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
  "note": "Weight decline read correctly but dated 2026 not 2006 (temporal_date_accuracy=wrong); citations resolve but [12] points to the prior visit."
}
```

Omit a temporal_* field when the question has no temporal claim. `note` is 1–3 sentences that
cite specific chart records and justify the lower scores — this is what a human reads to trust the score.
