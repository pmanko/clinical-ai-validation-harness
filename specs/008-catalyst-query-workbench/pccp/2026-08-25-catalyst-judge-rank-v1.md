# PCCP-style Change Record: Catalyst Judge measurement changes (rank v1, anchors-based flagging, stated limits)

**Status:** Implemented and live on the published report; ranking pass not yet
run; owner acceptance of this record pending

**Date:** 2026-08-25
**Reviewer decision:** The owner directed "execute the suggestions of the
report" against the judging review of 2026-08-25 (five findings, all grounded
in run `9ae123db`). This record freezes what changed and why, in the same
governance stream as `2026-07-21-catalyst-judge-v1.md`.

## What run 9ae123db showed about catalyst-judge-v1

The pointwise rubric performed its advisory role but could not perform a
comparative one: every axis median was 3 for every team, the composite median
was 100, and 40 of 44 composites landed at or above 84. All discriminating
signal lived in four rows. Three same-model passes measured scoring stability,
not validity; no human had ever confirmed or overruled a judged call; and the
`<80` flag line plus the 47/29/24 weights carried no recorded justification.
Separately, the judge's rationales caught two real harness defects (the stale
`baseSql` echo fixed in #85, and the M2 final-reference-on-intermediate-turn
artifact, Q1 in the qualification-remediation roadmap) — the rationales are
the layer's proven value and are unchanged by this record.

## Modifications

### 1. `catalyst-judge-rank-v1` — comparative ranking (new, companion rubric)

Rubric: `.claude/skills/catalyst-sql-scoring/rubric-rank.md`.
Mechanics: `harness/catalyst/judge_ranking.py`.

- One comparison per (scenario, turn) that more than one team answered: the
  same instruction, every team's answer with SQL, parameters, and evidence.
- Team identities are blinded behind labels shuffled per comparison. The
  shuffle is content-derived (SHA-256 of scenario/turn/team), so the worklist
  is replayable evidence while a judge cannot learn that one label is one team.
- The judge orders answers best-first with one checkable sentence each,
  priority intent > catalog discipline > construction. Ties are recorded as
  ties (competition-style ranks). A comparison the judge cannot meaningfully
  order is returned `comparable: false` with a reason — never forced.
- Aggregation: mean rank leads (survives ties, cannot saturate); wins are
  reported alongside; a standing where every team shares one mean rank states
  that it does not separate them.
- Posture: advisory, identical to pointwise. Gold execution-match remains
  authoritative. Rankings never change whether a query passed.
- Report: `report.html` renders a "Comparative standing" section only when a
  `judge_rank.jsonl` exists; absence renders nothing, because an empty section
  would imply the comparison was made and came out even.

Relationship to program policy: the absolute 90/80 gates decide
**eligibility**; the ranking is a **selection** instrument among eligible
teams, aligned with the roadmap's own relative tie-break order
(complete-scenario rate, worst scenario rate, …). It does not replace gates.

### 2. Flagging by rubric anchors, not a composite cutoff

The `<80` flag line is removed everywhere. A query is named in the judge
summary when the judge marked it down on **any axis** (below the axis's top
anchor), ordered worst-composite-first, capped at three per team. Purely
relative flagging (each team's below-its-own-best) was tried and rejected: a
team whose queries all scored alike and badly would name nothing.

### 3. Axes-first reporting

The judge summary leads with the four axes; each cell shows the median and,
where scores differ, the min–max range. The composite is demoted to a trailing
convenience column carrying the team floor. The weights (47/29/24 and
40/25/20/15) are unchanged but explicitly documented as a convenience: with
saturated axes the composite is nearly a step function of whichever axis
dropped, and no decision may rest on it alone.

### 4. Stated limits: actors and adjudication

`harness/catalyst/judge_consensus.py`:

- **Actors.** Judge rows group by provider/model/model_version. A single-actor
  run prints, beside its scores: "One judge actor … three passes finalized by
  median. That measures how stably this model scores, not whether it scores
  correctly." A multi-actor run prints how many cells all actors scored and
  their widest per-axis disagreement. `catalyst-judge-finalize` gained
  `actor_dirs()`: `judges/<actor>/` holds one pass set each; the flat run root
  remains the single-actor layout every existing run uses.
- **Human adjudication.** An optional `judge_adjudication.json`
  (`{"verdicts": {"<scenario>:<turn>:<version>": {"agree": bool, "note":
  str}}}`) written by a person. An unreviewed run yields no agreement rate —
  the report prints "No human adjudication" rather than implying an anchor.

### 5. Per-turn gold references in the runner (Q1 enabler)

`NotebookTurn` accepts `goldCheck`; the scenario-level `successorGoldCheck`
applies to the final turn only. This is runner capability for the
qualification-remediation roadmap's **R2**; the shipped suite v2 (bound to
catalog v7, per-turn contracts for every scenario) is R2's to create. Suite v1
remains byte-immutable; no successor suite file ships before R2.

## What this record does not change

Axis definitions, the 0–3 anchors, three-pass finalization, gold precedence
(D7), "when unsure pick the lower", the row schema
(`catalyst-judge-v1.schema.json`), and the pointwise rubric bytes
(`rubric.md`, sha256 `5dc94bbd…`) are all untouched.

## Outstanding before this layer informs a decision

1. Run the ranking pass over run 9ae123db (or its R8 successor batch).
2. Run a second judge actor from a different model family.
3. Owner adjudication of the named weakest rows (four on run 9ae123db).
4. Rubric hash for `rubric-rank.md` to be pinned by the ranking runner the
   same way the pointwise pass pins `rubric.md`.
