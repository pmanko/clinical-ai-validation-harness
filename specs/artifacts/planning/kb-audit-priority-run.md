# KB audit — priority run

**Verdict: the KB is well-aligned for the priority question set; not a bottleneck.** The corpus (`targets/med-agent-hub/server/kb_data/corpus.jsonl`, 24 entries) has strong HIV/ART coverage, which is exactly the patient's domain. Most of the 18 single-turn questions are pure chart-retrieval and do **not** invoke `kb_search`; the few that do are covered, with two minor gaps.

## Corpus inventory (24)
- **HIV/ART (10):** preferred first-line ART (DTG/TLD), second-line, stavudine (d4T) phase-out, treat-all, WHO clinical staging, CD4 role, adherence, TB co-infection, co-trimoxazole, cryptococcal disease.
- **Other clinical:** peds IMCI danger signs / pneumonia thresholds / amoxicillin / ORS+zinc (4), TB first-line (1), malaria ACT + severe (2), metformin T2DM (1), HTN threshold (1), infant EPI immunization schedule (1).
- **OpenMRS/OCL meta (4):** CIEL dictionary, OCL, information model, concept dictionary.

## Coverage vs the 18 single-turn questions
`kb_search` fires only for guideline/threshold/currency/interpretation questions; the rest are chart lookups.

| Question | KB invoked? | Topic → covered? |
|---|---|---|
| medications, allergies, problem-list, recent-activity, last-visit(+detail), contact-info, weight-trend, orders-6mo, last-bmp, upcoming-appointments, age, care-programs | no (chart / demographics / abstain) | n/a |
| vitals | rarely (BP → HTN threshold) | `htn-diagnosis-threshold` ✓ |
| hiv-status (+ last test) | maybe (status/staging) | `hiv-who-staging`, `hiv-cd4-role` ✓ |
| cd4-history | maybe (interpret CD4) | `hiv-cd4-role` ✓ |
| **immunizations** | yes (schedule) | `epi-immunization-schedule` — **infant only → adult gap** ⚠ |
| **hiv-labs** | maybe (CD4 / staging / VL) | `hiv-cd4-role`, `hiv-who-staging` ✓; **no dedicated viral-load-monitoring entry** ⚠ |

Multi-turn: `convo-diagnosis-evidence` richly exercises the HIV KB (ART first-line, d4T phase-out, staging, CD4); `convo-medications-adherence` → `hiv-adherence`; `convo-safety-escalation` → adherence/stopping-ART risk. All covered.

## Recommendations
1. **No KB change is required to run** — the HIV-grounded path is well-covered.
2. **Optional adds**, only if the run shows the team `kb_search`-ing and getting nothing relevant:
   - **HIV viral-load monitoring** (6- and 12-month then annual VL; <1000 copies/mL = suppressed; confirmed >1000 = failure → second-line).
   - **Adult immunization** note (the EPI entry is infant-only; routine adult immunization isn't schedule-tracked the same way).
3. **Post-run check:** scan the run's `kb_search` observations for empty/irrelevant retrievals on `immunizations` and `hiv-labs` to confirm whether the two gaps actually bite.

Corrected the stale `datasets/validation/scenarios/README.md` claim that "the KB seed … does not intersect an HIV patient."
