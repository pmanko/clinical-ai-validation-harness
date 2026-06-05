# Answer + In-Depth structure — how to ask for it, and how to validate each (research brief)

**Question this answers.** Our synthesizer is asked for a two-section answer — a direct **Answer**
(patient-specific, chart-cited) and an **In Depth** elaboration (interpretation + external guideline
guidance). We validate the two sections separately. Three things to settle, grounded in research:
(1) is "direct answer + rationale" a sound way to *ask*; (2) is *validating the two separately*
research-backed; (3) how to validate each **given their different scope**.

The short version: separate validation is correct and well-supported — but our current validator
**mis-scopes the In Depth** (it judges the elaboration "against the chart" when the elaboration's job
is to bring in guidance that is *not* in the chart), and the *presence* of a rich In Depth should
**scale with model capability**, not be demanded uniformly.

---

## 1. The two sections have genuinely different epistemic scope

| | **Answer** (direct) | **In Depth** (elaboration) |
|---|---|---|
| Content | patient-specific facts from THIS chart | interpretation of the chart + external guideline/KB guidance |
| Truth condition | **faithful to the chart** (groundedness) | chart-claims → faithful to chart; **guideline-claims → medically correct + correctly attributed, NOT in the chart** |
| Primary rubric axis | accuracy + faithfulness + abstention | completeness + relevance + **KB-utilization** + attribution-faithfulness + harm |
| Characteristic failure | wrong value / date / fabricated trend (**high stakes**) | unsupported interpretation, fabricated guidance/source, over-claim, **KB ignored / mis-applied** |
| Right validation | atomic-claim entailment vs chart (RAGAS-against-chart) | **route by claim type** (ground chart-claims; attribution-check guideline-claims) **+ does the retrieved KB relevantly INFORM the answer** |
| Validation **threshold** | **strict** — error cost is high | **lower / advisory** — error cost is bounded (it can be dropped) |
| Right fallback | **abstain** (never ship a wrong fact) | soften / drop the unsupported claim (try to fix first) — **never abstain the turn for an In-Depth-only miss** |

A claim's truth condition depends on its *type*, not its section. The Answer is (almost) all
chart-facts. The In Depth deliberately **mixes** chart-grounded reasoning with general medical
guidance — which has a *different* truth condition (correctness + attribution, not chart-groundedness).

---

## 2. What the research says

**Validating the answer and the explanation *separately* is correct.**
- **Correctness ≠ Faithfulness in RAG attributions** (Wallat et al., 2025, UvA): answer correctness and
  attribution faithfulness are *independent* — a model can give a correct answer while its supporting
  citations/explanation misrepresent the sources. The recommendation is an explicit **dual evaluation
  protocol**: passing one does not imply the other. This is direct support for our split.
- **Explanations can be plausible but unfaithful** — *Language Models Don't Always Say What They Think*
  (Turpin et al., NeurIPS 2023, arXiv:2305.04388): CoT/rationale can systematically misrepresent the
  real basis of an answer (accuracy swung up to 36% under biasing features the explanation never
  mentions). Implication: **a clean-sounding In Depth must NOT vouch for the Answer, and vice-versa** —
  keep the two gates independent (we already do).
- Rationale evaluation itself has **two distinct axes** — *human-alignment* (matches a human's
  rationale) vs *faithfulness* (reflects the model's actual process) (arXiv:2407.00219). For our
  purpose the operative axis is **groundedness/correctness of the stated claims**, not whether the prose
  reads well.

**"Direct answer + rationale," and bounded completeness, are sound for clinical QA.**
- Structured clinical-reasoning prompts (answer + an interpretable rationale) improve diagnostic quality
  and let a clinician judge trustworthiness (Diagnosis-Please study, medRxiv 2024; LLM-MedQA 2501.05464).
- **Completeness is a *distinct* axis from accuracy** — a model can be ~90% accurate yet omit clinically
  important information in ~47% of summaries (npj Digit. Med. 2025; in our `eval-methodology-brief.md`).
  So a *correct Answer alone* is not sufficient — the In Depth carries completeness — **but** completeness
  must be **bounded by the question** (the "relevance" axis: don't demand elaboration beyond what's asked).

**The In Depth should scale with capability — for weak models, elaboration can HURT.**
- *To Reason or Not to: Selective Chain-of-Thought in Medical QA* (arXiv:2602.20130): explicit reasoning
  does **not** uniformly help; for **smaller models** generating reasoning can **reduce accuracy /
  introduce errors**. They invoke reasoning *selectively* (by difficulty/confidence), not always.
- Elaboration is a **fabrication surface**: in a clinical decision-support assurance study models
  **elaborated on planted fabricated details in up to 83% of cases** (Communications Medicine 2025);
  longer responses hallucinate more (arXiv:2510.20229). Our own run shows it: the weak LOW synth's
  In Depth produced "improved due to ART," "falls within the normal range," "9.2 vs 9.1 g/dL" — i.e. the
  In Depth, not the Answer, is where it invents.

**Abstaining on *part* of an answer is research-backed — but section-drop is a blunt version.**
- Selective generation (abstain when unsure) **does not scale to long-form**, where one response holds
  many claims of varying confidence (Google Research, "sufficient context"; survey *Know Your Limits*).
  The principled unit is the **claim**, not the section: keep the confident claims, drop/soften the
  uncertain ones — "uncertain about the exact date but confident about the year" (I-CALM 2604.03904;
  fine-grained semantic-confidence abstention 2510.24020; AbstentionBench 2506.09038). Our current
  whole-**In-Depth** drop is the pragmatic interim; **claim-level** is the research target.

**Grounded vs parametric is a known RAG distinction.**
- A correct answer may come from the model's parametric knowledge rather than the retrieved context
  (RAG-X 2603.03541; FaithfulRAG 2506.08938) — a "Grounding Score" measures reliance on retrieved
  evidence vs memorized knowledge. For us: the In Depth's *guideline* claims are legitimately parametric/
  external and must be judged for **correctness + attribution**, while its *patient* claims must be
  judged for **chart-groundedness** — two different tests in one section. (AttrScore's
  **Extrapolatory vs Contradictory** split, 2305.06311: "the chart doesn't mention this" ≠ "the chart
  contradicts this" — clinically very different verdicts.)

### 2a. The In Depth's *real* test: does the KB properly inform the answer?

The In Depth is the place where the team's retrieval earns its keep. So its core criterion is not
"is every sentence in the chart" — it is **does the retrieved KB/guideline guidance relevantly and
correctly inform this patient's answer**. That is **context-utilization**, a separate axis from
chart-faithfulness:
- **RAGAS** decomposes RAG quality into *faithfulness* (claims inferable from the retrieved context),
  *context-relevance* (was the right context retrieved), and *answer-relevance* (does the answer use it
  on-topic) (arXiv:2309.15217) — the In Depth is exactly where context-relevance + utilization live.
- A "**Grounding Score**" / context-utilization measures reliance on retrieved evidence vs memorized
  parametric knowledge (RAG-X 2603.03541; FaithfulRAG 2506.08938). For the In Depth, *good* = the KB
  guidance is real, correctly attributed, and **actually applied** to the chart findings — not boilerplate
  ("consult a doctor") and not ignored.

This is also a **signal of whether orchestration earned its cost**: if the In Depth shows the KB correctly
contextualizing the answer, the kb_search + expert hops added value; if the In Depth ignores or fabricates
guidance, they did not.

**Different threshold, not just a different rubric.** Stakes-calibrated abstention is standard in selective
prediction — set the bar by the cost of an error (Kamath 2006.09462; graded severity 2410.12222). The two
sections have very different error costs:
- **Answer** — a wrong patient fact is high-harm and hard to detect downstream → **strict** threshold,
  **abstain** on failure.
- **In Depth** — an imperfect elaboration is recoverable (it can be softened or dropped) → a **lower,
  advisory** threshold, **drop/soften** on failure, **never abstain the whole turn** for an In-Depth-only
  miss. Holding the In Depth to the Answer's strict bar is precisely what produced our over-abstention.

---

## 3. The concrete bug this surfaces

Our validator prompt tells the model to judge the In Depth as "VALID and useful: **grounded only in the
patient chart**." That is a **category error** for the guideline half of the In Depth — it penalizes the
elaboration for doing its job. Live evidence from this run's verdict logs: the e4b validator flagged an
In Depth because it **"introduces external knowledge (OpenMRS guidelines)"** — exactly the content the
synthesis prompt *asks* for. The fix is **claim-type routing in the validator**, not a stricter chart check.

---

## 4. Design implications (for discussion — not yet built)

1. **Validate by claim type, not by section-as-monolith.**
   - *Answer*: every claim must be chart-grounded (atomic-claim/numeric/temporal entailment vs chart).
     Fallback = **abstain**.
   - *In Depth*: split claims — **patient-claims** grounded vs chart; **guideline-claims** judged for
     *not-fabricated source* + *correct attribution* + *medical plausibility* (NOT chart-groundedness).
     Fallback = soften/drop the specific unsupported claim.
2. **Keep the gates independent** (Turpin) — a good In Depth never excuses the Answer, and vice-versa.
3. **Scale In-Depth *presence* to tier** (Selective CoT). Weak tiers may do better with a **lean** output
   (Answer + the structured `blocks` evidence table, minimal free-text interpretation); rich interpretive
   In Depth is for tiers strong enough not to fabricate it. Measure before fixing this.
4. **Section-drop now, claim-level later.** Whole-In-Depth drop is the pragmatic interim; the research
   target is keep-confident-claims / drop-uncertain-claims within the In Depth.
5. **Try before conceding (goal-framing).** When a section is flagged, attempt to satisfy its goal
   (re-synthesis with targeted feedback) and drop/abstain only if that fails — symmetric for both
   sections, with keep-best protecting whichever section was already good.

## Open decisions to settle before building
- **D1 — granularity:** section-level (drop the whole In Depth) vs claim-level (drop only unsupported
  claims) handling. Claim-level is the research ideal; section-level is cheaper and simpler.
- **D2 — tier-scaled elaboration:** should weak tiers emit a rich In Depth at all, or Answer + `blocks`
  evidence only? (Needs a measured A/B, per Selective CoT.)
- **D3 — validator scope fix:** route the In Depth audit by claim type (chart-fact vs guideline) — the
  fix for the mis-scoping bug. (This one looks unambiguously correct.)
- **D4 — In-Depth fix mechanism:** one full re-synth + keep-best, vs a targeted In-Depth-only
  regeneration that freezes the validated Answer.

## Sources
Wallat et al. 2025 *Correctness is not Faithfulness in RAG Attributions* (UvA);
Turpin et al. 2023 arXiv:2305.04388; *Selective CoT in Medical QA* arXiv:2602.20130;
rationale human-alignment vs faithfulness arXiv:2407.00219; RAG-X arXiv:2603.03541;
FaithfulRAG arXiv:2506.08938; AttrScore arXiv:2305.06311; I-CALM arXiv:2604.03904;
fine-grained semantic-confidence abstention arXiv:2510.24020; AbstentionBench arXiv:2506.09038;
long-response hallucination arXiv:2510.20229; adversarial clinical hallucination (Communications
Medicine 2025); structured clinical-reasoning prompt (medRxiv 2024); LLM-MedQA arXiv:2501.05464.
Faithfulness/citation backbone (FActScore 2305.14251, RAGAS 2309.15217, SAFE 2403.18802,
ALCE 2305.14627, AIS 2112.12870) and the clinical rubric/completeness sources are catalogued in
`eval-methodology-brief.md`.
