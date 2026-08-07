# D1 Dashboard Builder MVP Delivery Goal

**Status:** Active — M3 was accepted on 2026-08-06 after the binding 4c product,
real notebook-to-Superset path, deterministic D1d browser flow, durable visual
evidence, and user checkpoint passed. M4 release hardening and deployed
acceptance are in progress. Actual 200% browser zoom is deferred polish.

## Goal

Deliver a manually testable local Catalyst workflow in which a user asks a
question through the Hub-owned `catalyst-query-e4b-qwen14b` profile, edits,
validates, and runs the generated SQL, promotes the exact successful execution
into the designed multi-widget Dashboard Builder, publishes a native Superset
bundle, imports it into pinned local Superset, reconciles displayed values to
PostgreSQL, and explicitly accepts the experience.

The original table-only Dataset → Widget → Dashboard bundle/import path was a
**Superset import spike**. It proves useful mechanics, but it is not a separate
or smaller MVP tier and cannot close this goal by itself.

The local named Docker volumes are the durable development state: `up` resumes
them, `restart` retains them, `seed` explicitly reloads the source pipeline,
and the **stack-level** `reset` is destructive. This is distinct from the
unimplemented D1 Superset last-verified recovery reset. No additional
FHIR-cache registry is part of this goal.

## Definition of done

| ID | Testable acceptance evidence |
| --- | --- |
| MVP-01 | The isolated persistent stack starts without reseeding with Catalyst UI, Gateway, analytics PostgreSQL, Med-Agent Hub, and Superset healthy. No fake or bundled model-router service exists. |
| MVP-02 | Hub discovery exposes only the available `catalyst-query-e4b-qwen14b` profile with exact `google/gemma-4-e4b` writer and `qwen2.5-14b-instruct-mlx` reviewer roles, prompts, knobs, and digests. Missing aliases fail startup clearly. |
| MVP-03 | The existing Ask workflow remains intact through explicit Run: one editable SQL editor, manual edit/versioning, advisory validation, explicit execution, typed results, and follow-up all work before Dataset promotion. |
| MVP-04 | A successful current execution creates a Dataset and supports the actual multi-widget builder experience and required native Superset visualization mappings without a second SQL editor or automatic execution. |
| MVP-05 | A named Dashboard publishes one byte-stable native bundle to the Catalyst outbox. The downloaded bytes equal the outbox bytes. The explicit importer records an `imported` receipt and verified last-verified projection. |
| MVP-06 | The stable `/superset/dashboard/catalyst-<dashboard-id>/` route opens in local Superset. Representative values for every accepted widget reconcile to recorded reproducible PostgreSQL SQL. |
| MVP-07 | One versioned evidence directory records exact commits/image digests, profile/model configuration, query/execution IDs and SQL, bundle/receipt/projection digests, PostgreSQL reconciliation, repetition/nondeterminism, accessibility checks, and screenshots/video. |
| MVP-08 | The user inspects and accepts the deployed local dashboard workflow. |

## Checkpoints

| Checkpoint | Entry | Exit evidence | Decision |
| --- | --- | --- | --- |
| M0 — truthful baseline | Current branches and runtime evidence available | Product/docs/task state identifies the implemented table exporter/importer as a Superset import spike and keeps the Dashboard MVP open. | Passed 2026-08-05 |
| M1 — real profile/runtime foundation | M0 complete | Hub/Catalyst/harness pins contain one shared workflow-typed profile schema, no duplicate Gateway model configuration, no fake-router path, and external-only startup with exact alias checks. | Passed 2026-08-05 |
| M2 — real query-workbench proof | M1 complete and models are available | Persistent isolated stack starts without seed; Gemma → Qwen generation, manual edit, Validate/Run, result inspection, and exact trace evidence pass. Pause before dashboard implementation resumes. | Accepted 2026-08-05 |
| M3 — Dashboard MVP integration | M2 accepted | The preserved Workbench is recomposed into the binding 4c shell with one editor/composer, chronological turns, Dataset/Widget/Dashboard review and libraries, and publication controls; the real happy path imports into Superset and reconciles to PostgreSQL. | **Accepted 2026-08-06** — T150–T154 and T174–T179 are closed from focused automated/live evidence, durable visual artifacts, and explicit user acceptance. Actual 200% browser zoom was explicitly deferred to polish; 320/390/640-CSS-pixel reflow remains required. |
| M4 — release acceptance | M3 complete and explicitly accepted by the user | Required repetition, nondeterminism, failure/recovery, keyboard/reflow/accessibility, evidence emission, CI, and video evidence pass; the user accepts the deployed workflow. | **In progress** — D1b runtime/lifecycle T139/T140/T160–T162, canonical five-family fixture T141, and standalone importer T142/T143 pass. T163–T165 recovery/state closure is next, followed by the remaining D1b → D1c → D1e tasks. |

## Required D1 completion work

The active implementation slice is M4 release hardening without widening scope.
T150–T154 and T174–T179 are complete from their own characterization,
component/API/browser, durable visual, and user-acceptance evidence. Actual 200%
browser zoom is deferred polish and is not an M4 gate; deterministic desktop and
320/390/640-CSS-pixel reflow remains required. D1b runtime identity,
permissions, mounts, secret-free evidence, and non-destructive restart now pass
at T139/T140/T160–T162, and the canonical five-family clean-import fixture passes
at T141, and the standalone Python 3.10 importer boundary passes at T142/T143.
The remaining D1 hardening—complete reset/reimport recovery,
changed/layout-only child behavior, schema-backed evidence emission, repetition,
CI, and release evidence—remains individually tracked in the still-open D1 tasks. No bridge
task may close those tasks or substitute backend evidence for product UX.

Superset REST publication, embedded Superset, bidirectional reconciliation,
sharing/scheduling, automatic refresh, production authentication and
authorization, and model-generated visualization specifications remain outside
this local MVP.
