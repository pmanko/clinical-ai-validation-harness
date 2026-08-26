# Phase 1 planning discussion — closed decision record

**Status:** Workshop completed 2026-08-23. This file explains the evidence and
the choices made. `specs/catalyst-program-roadmap.md` owns product decisions;
`specs/catalyst-phase1-qualification-remediation-roadmap.md` owns the active
repair sequence. This historical brief is not a current plan. On 2026-08-25,
the owner corrected the data-boundary entry below: the number 13 described the
then-current fixture and was never intended as a product allowlist. On the same
date, the owner removed the brief's collection-count policy, numerical gates,
infrastructure-failure budget, context caps, ranking formula, and validator
execution gate. The owner then clarified that the report is evidence for the
reader rather than a team-selection gate, and that explicit guidance or a Pin
interface must remain an open research question beside ordinary conversation
history. The tables below preserve the workshop state and are not current
requirements. The active roadmaps contain the simpler direction.

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
5. Identical requests at temperature zero produced different terminal
   findings. The evidence must show that output variability honestly.
6. The field evidence supports six practices: described data meaning,
   itemized retained guidance, verified examples, failure feedback, honest
   clarification, and bounded context with explicit omissions.

## Workshop decisions at close — historical

| Question | Decision recorded at workshop close |
| --- | --- |
| Data boundary | The writer, editor, validator, and executor use every relation the configured read-only database role can read. Reviewed metadata guides use but does not hide readable relations. |
| Writer outcomes | `ready`, `needs_clarification`, and `unsupported`; Gateway-owned `rejected` remains separate. |
| Conversation state | Supply relevant retained instructions, person-pinned guidance, useful failure information, and prior verified examples within the configured model's capacity. Record what was supplied and every omission; do not lock counts, physical order, or ranking here. |
| Guidance | Free text with provenance; composer pin and explicit pin-from-failure; no pin-from-success. Unpin and replacement are append-only events. |
| Measurement | Qualify the completed Phase 1 system. Do not publish an old-system baseline or individual on/off comparisons. |
| Model comparison | Gemma writer only; Gemma writer checked by Gemma; Gemma writer checked by Qwen. Treat them as complete product setups. |
| Environments | Run the full comparison locally on the owner's GPU. Run three real browser journeys on the deployed server. |
| Report | One consolidated report with separate model and infrastructure outcomes, database answers, context, token and timing evidence, and the documented owner-reviewed decision. No causal claim is made about an individual context practice. |

## Recommendations explicitly superseded

The workshop rejected these recommendations from the original discussion
pack. They must not reappear as open choices:

- Keep a smaller generation-only catalog. The owner chose the same complete
  role-readable catalog for model and human paths; the current relation count
  is not a limit.
- Measure an old system and then remove or add each context practice in turn.
  The integrated system, not individual levers, is the subject of the
  comparison.
- Allow only ready or clarification. The owner added an honest unsupported
  outcome while retaining Gateway rejection.

The current roadmap further clarifies that the final report presents evidence
for the reader. It does not automatically select a team, attribute a result to
one context practice, or claim local and server model performance are equal.

## Historical implementation-readiness record

At workshop close, no product-decision or repository blocker remained. The
three readiness tasks below were complete. Later implementation and the first
development comparison exposed evidence and reporting defects now governed by
`specs/catalyst-phase1-qualification-remediation-roadmap.md`.

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

The interfaces, scenario set, model profiles, comparison method, implementation
order, deployed browser checks, and unchanged Phase 3 gates are defined in the
program roadmap.

## Evidence pointers

- `specs/catalyst-program-roadmap.md` — current decisions and acceptance.
- `specs/catalyst-phase1-qualification-remediation-roadmap.md` — active
  execution sequence.
- `specs/artifacts/planning/what-the-writer-sees.html` sections 01–02 — writer
  context reconstruction and the six evidence-backed practices.
- `specs/008-catalyst-query-workbench/remediation-roadmap.md` — completed
  WS1–WS7 history.
- `specs/008-catalyst-query-workbench/tasks.md` — the 15 unchanged Phase 3
  Dashboard Builder gates.
- `harness/catalyst/notebook_validation.py` — existing validation runner to
  extend rather than replace.
