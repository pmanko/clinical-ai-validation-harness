# Phase 1 planning discussion — closed decision record

**Status:** Workshop completed 2026-08-23. This file explains the evidence and
the choices made. `specs/catalyst-program-roadmap.md` is the only current plan.

## What the research established

Read `what-the-writer-sees.html` sections 01–02 for the full evidence. The
important findings were:

1. The writer receives the catalog, policy, editor state, recent instructions,
   and current validation details.
2. Session guidance, the relevant prior failure, and verified successful
   examples are recorded or derivable but do not reach the next request.
3. The writer was intentionally limited to four approved views while a human
   could use 13 readable relations. The narrow list was deliberate; the
   resulting patient-name gap was not.
4. The prompt says to ask when information is missing, but the writer's output
   contract permits only a ready query.
5. Repeating the same request at temperature zero produced different terminal
   findings. A single live run cannot qualify a model setup.
6. The field evidence supports six practices: described data meaning,
   itemized retained guidance, verified examples, failure feedback, honest
   clarification, and bounded context with explicit omissions.

## Owner decisions

| Question | Locked answer |
| --- | --- |
| Data boundary | One reviewed list of all 13 currently readable relations for the writer, editor, validator, and executor. Database permissions do not auto-expand it. |
| Writer outcomes | `ready`, `needs_clarification`, and `unsupported`; Gateway-owned `rejected` remains separate. |
| Conversation state | Keep the initial instruction and five latest follow-ups, then add at most 20 verbatim guidance entries, one relevant failure, and three verified examples. |
| Guidance | Free text with provenance; composer pin and explicit pin-from-failure; no pin-from-success. Unpin and replacement are append-only events. |
| Measurement | Qualify the completed Phase 1 system. Do not publish an old-system baseline or individual on/off comparisons. |
| Model comparison | Gemma writer only; Gemma writer checked by Gemma; Gemma writer checked by Qwen. Treat them as complete product setups. |
| Repetitions | Start with three per model/scenario pair and extend unstable or effectively tied pairs to five; never extend beyond five. |
| Environments | Run the full comparison locally on the owner's GPU. Run three real browser journeys on the deployed server. |
| Report | One consolidated report with absolute qualification gates, separate failure counts, database answers, token and timing evidence, and no causal claim about an individual context practice. |

## Recommendations explicitly superseded

The workshop rejected these recommendations from the original discussion
pack. They must not reappear as open choices:

- Keep a smaller generation-only catalog. The owner chose the shared reviewed
  13-relation list.
- Measure an old system and then remove or add each context practice in turn.
  The owner chose one final integrated qualification.
- Run the complete repeated matrix both locally and on the demo server. The
  owner chose local GPU measurement plus limited deployed browser checks.
- Run five repetitions for every pair by default. The owner chose three,
  extending only unstable or tied pairs to five.
- Allow only ready or clarification. The owner added an honest unsupported
  outcome while retaining Gateway rejection.

These choices mean the final report can compare model teams and determine
whether the finished product meets its bar. It cannot attribute a result to
one context practice or claim local and server model performance are equal.

## Implementation readiness

No product decision or repository blocker remains. The three readiness tasks
are complete:

1. The authoritative roadmap replaces stale PR #59, which is closed as
   superseded.
2. Harness PR #61 repaired issue #58. Catalog v5 and the exact native codes and
   displays reconcile locally and on the demo host. The HIV correction was
   applied in place without reingesting or reseeding that source. A separate
   supported synthetic OpenELIS seed later restored the local MVP validation
   baseline.
3. Catalyst PR #65 fixed the isolated seed command's false Superset-port
   failure, and the harness pins its merged commit. The full local health and
   provenance gate passes.

The exact interfaces, scenario set, model profiles, thresholds, implementation
order, deployed browser checks, and unchanged Phase 3 gates are defined in the
program roadmap.

## Evidence pointers

- `specs/catalyst-program-roadmap.md` — current decisions and acceptance.
- `specs/artifacts/planning/what-the-writer-sees.html` sections 01–02 — writer
  context reconstruction and the six evidence-backed practices.
- `specs/008-catalyst-query-workbench/remediation-roadmap.md` — completed
  WS1–WS7 history.
- `specs/008-catalyst-query-workbench/tasks.md` — the 15 unchanged Phase 3
  Dashboard Builder gates.
- `harness/catalyst/notebook_validation.py` — existing validation runner to
  extend rather than replace.
