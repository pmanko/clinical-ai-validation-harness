# Catalyst comparative ranking rubric (`catalyst-judge-rank-v1`)

Companion to the pointwise `catalyst-judge-v1` rubric. Pointwise scores
saturate: on run 9ae123db every axis median was 3 and 40 of 44 composites
landed at or above 84, so the scale could describe failures but could not
rank teams that all passed. A ranking cannot saturate — asked which of
three answers to the same question is best, a judge must choose.

**What you are given per comparison:** one scenario instruction (initial
question or follow-up), and every team's answer to *that same* instruction
— each with its generated SQL, parameters, execution evidence, and gold
verdict when present. Team identities are replaced by opaque labels
(`A`, `B`, `C`) in a fixed random order per comparison, so a ranking cannot
be anchored to a model name.

**Posture:** advisory, exactly like the pointwise rubric. Gold
execution-match remains authoritative. A ranking never changes whether a
query passed.

---

## The task

Order the answers best-first. Then, for each, one sentence saying what put
it where it is — in terms a reader can check against the evidence.

Judge on the same three concerns the pointwise rubric names, in this
priority order when they conflict:

1. **Answers the instruction.** Predicates, projections, and grain match
   what was asked. This dominates: a beautifully written query that answers
   a different question ranks below a plain one that answers this one.
2. **Stays inside the catalog contract.** Catalogued tables and columns,
   correct types, parameters bound.
3. **Construction.** Clear joins and aggregation, no dead branches, nothing
   a maintainer would have to untangle.

## Ties are real — record them

Two answers that differ only cosmetically are **tied**, and a forced
ordering between them would be noise presented as signal. Give tied answers
the same rank and say why they tie. Ranks are competition-style: a tie for
first is `1, 1, 3`.

## When a comparison is not comparable

If the teams' answers cannot be meaningfully ordered — every one failed for
the same structural reason, or the scenario's own reference is at fault —
say so with `comparable: false` and a reason, and give no ranks. A refusal
that names the obstacle is worth more than an invented ordering. (On run
9ae123db, M2 turn 1 was exactly this case: the suite checked an
intermediate turn against the conversation's final reference.)
