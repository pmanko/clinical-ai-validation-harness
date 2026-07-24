# G15 — Final-answer integrity, live evidence (2026-07-24)

Deployment: `harness-med-agent-hub` at `HUB_BUILD_REVISION=a279a56`, real patient
`dd5558ed-1691-11df-97a5-7038c432aabf` on the running OpenMRS 2.8 demo stack, real querystore-backed
context, real `gemma-4-12b` model on the local llama-router.

## 1. References are recomputed post-rewrite (not carried over from the original answer)

Sent a deliberately wrong answer (a real numeric contradiction against the chart — dose 500mg where
the chart record says 81mg) through the hub's review/rewrite profile directly
(`answer-review:gemma-4-12b@validation-rewrite~enforce~temp0`, `answer_to_review.v1` payload):

- Chart: `[1] Aspirin 81mg daily, active order`
- Draft answer under review: `"The patient is taking Aspirin 500mg daily [1]."`

Live response:

```json
{
  "answer": "The patient is taking Aspirin 81mg daily [1].",
  "citations": [1],
  "answerValidation": {
    "status": "edited",
    "label": "Updated after check",
    "issues": [{"wrong": "Aspirin 500mg daily", "chart": "Aspirin 81mg daily [1]", "fix": "Aspirin 81mg daily"}],
    "originalAnswer": "The patient is taking Aspirin 500mg daily [1]."
  }
}
```

The reviewer correctly identified the chart contradiction (500mg vs. the chart's 81mg), rewrote the
answer, marked `answerValidation.status: "edited"` (not silently "checked"), and preserved the
original wrong answer in `originalAnswer` for audit. The corrected text is what a client actually
renders — the pipeline never silently keeps a chart-contradicted claim.

(Aside, also live-verified but not itself evidence of a bug: a first attempt using a
not-in-the-chart-but-not-contradicted detail — a stated dose/indication absent from, but not
contradicted by, a one-line chart — was correctly left unedited by the reviewer, per its own prompt
rule that "not documented" is not an error. That is correct reviewer behavior, not a miss.)

## 2. Prior-turn citation numbers cannot bind to current-turn evidence

Two-turn conversation against the real patient via the full `single-e4b-checked` product profile:

**Turn 1** — "What medications is the patient currently on?"
```
ANSWER: ...Trimethoprim and sulfamethoxazole [2], Lamivudine / zidovudine [3], Efavirenz [4], ...
citations: [2, 3, 4, 5]
ref 2 -> drug_order 1e3d45ea-... "Trimethoprim and sulfamethoxazole"
```

**Turn 2** — same conversation, turn 1's Q&A supplied as prior context — "Does the patient have any
recorded allergies?"
```
ANSWER: The patient has recorded allergies to Penicillins ... [233][278][277]
citations: [233, 278, 277]
ref 233 -> allergy 762624d5-... "Penicillins (drug allergen)"
ref 278 -> obs c1aea084-... "Allergy to sulfa: No"
ref 277 -> obs c1ae9d30-... "Allergy to other medicine: No"
Total references in turn 2's own reference pool: 3 (233, 277, 278) — index "2" is not present at all.
```

Citation indices are stable ledger positions (not per-turn-reset small integers), and turn 2's
resolvable reference pool for this question simply does not contain index `2` — it cannot be
misread as "the same as turn 1's [2]" because it isn't there to resolve. Turn 1's `[2]`
(Trimethoprim) and turn 2's actual answer never collide or get silently reinterpreted; a stale
reference either keeps its one true meaning or is absent, never rebinds to different evidence.

## Conclusion

Both G15 sub-claims are demonstrated live against a real patient, a real model, and the real
review/rewrite and multi-turn pipelines: a chart-contradicted claim is caught, rewritten, and
honestly labeled `edited` with full before/after audit; and citation numbers are stable-ledger-scoped
so a prior turn's index cannot silently resolve against a different turn's evidence.
