# Judging review of 2026-08-25 — findings, dispositions, and what a rerun owes

**Status:** All five findings implemented (harness PR #92); persisted from the
working artifact "Catalyst Judge Review" (claude.ai artifact 6446a932). The
measurement changes themselves are frozen in
`specs/008-catalyst-query-workbench/pccp/2026-08-25-catalyst-judge-rank-v1.md`;
this file records the review's findings and their relationship to the
qualification-remediation roadmap.

Grounding: run `9ae123db` — 44 judged queries, 3 teams × 12 scenarios,
catalyst-judge-v1, three same-model passes (claude-fable-5).

## What held up and was kept

Evidence-linked rationales (they caught the stale `baseSql` echo, fixed in
harness #85, and the M2 reference artifact = roadmap Q1); gold precedence
(D7); the frozen contract and pinned rubric.

## Findings and dispositions

| ID | Finding | Evidence on 9ae123db | Disposition |
| --- | --- | --- | --- |
| J1 | Pointwise scores saturate; the scale cannot rank passing work | Every axis median 3; composite median 100; 40/44 ≥ 84 | **Executed:** axes-first summary with ranges; `catalyst-judge-rank-v1` comparative ranking (blinded, tie-honest, refusal-honest). Ranking pass not yet run |
| J2 | Three same-model passes measure stability, not validity | Identity check enforces one model across passes | **Executed:** `judges/<actor>/` layout in finalize; the report states "one judge actor … not whether it scores correctly." Second family not yet run |
| J3 | No human anchor | No adjudication artifact existed anywhere | **Executed:** optional `judge_adjudication.json`; unreviewed runs print "No human adjudication" instead of implying one. Owner adjudication of the named rows not yet done |
| J4 | Magic numbers: the `<80` flag and the 47/29/24 weights | With saturated axes the composite is a step function of the dropped axis | **Executed:** flagging by rubric anchors (any marked-down axis), worst-first, ≤3/team; composite demoted to a labeled convenience |
| J5 | M2 turn 1 judged against the conversation's final reference | Failed by construction for every team; all three judge passes flagged it | **Executed in the runner** (per-turn `goldCheck`; scenario reference scoped to the last turn). The shipped suite v2 belongs to **R2** of the qualification-remediation roadmap (bound to catalog v7, per-turn contracts for every scenario) — this review's minimal v2 draft was withdrawn to avoid preempting it |

## Relationship to program policy

- **Eligibility vs selection:** the 90/80 absolute gates remain the
  eligibility policy (roadmap "Phase 1 qualification and model selection");
  the comparative ranking serves the roadmap's own *relative* selection order
  among eligible teams. The report's abstract carries no gates by design
  (`specs/artifacts/planning/report-surfaces-2026-08-25.md`); the Result
  section prints them with the policy that set them.
- **J5 = Q1.** The remediation roadmap independently identified the same
  defect; R2 is its designated, fuller fix. The runner capability shipped here
  is R2's enabler, not its substitute.

## What still needs a run, not code

1. The ranking pass (and pin `rubric-rank.md`'s hash in its runner).
2. A second judge actor from a different model family.
3. Owner adjudication of the named weakest rows (four on 9ae123db).
4. The R8 qualification batch on R2's suite v2 — which will re-score M2
   honestly and change the published "missed by every team" count from four
   questions to three.
