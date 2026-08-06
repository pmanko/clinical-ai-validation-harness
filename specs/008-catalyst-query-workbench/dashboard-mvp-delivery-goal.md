# D1 Dashboard Builder MVP Delivery Goal

**Status:** Active — the binding 4c product implementation is live and the real
notebook-to-Superset path plus deterministic D1d browser flow pass. M3 remains
in progress pending the remaining Dataset/Widget/publication checks, actual
200% browser zoom, and explicit user acceptance; M4 has not started.

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
| M3 — Dashboard MVP integration | M2 accepted | The preserved Workbench is recomposed into the binding 4c shell with one editor/composer, chronological turns, Dataset/Widget/Dashboard review and libraries, and publication controls; the real happy path imports into Superset and reconciles to PostgreSQL. | **In progress** — T150/T174/T151 and the 4c shell are complete; one real Gemma/Qwen notebook-to-Superset path and the deterministic D1d browser flow are live, including refresh-hydrated `Imported`/verified Open state. T175/T152, T176/T177, T178/T153, T179/T154, actual 200% browser zoom, and explicit user acceptance remain open. |
| M4 — release acceptance | M3 complete and explicitly accepted by the user | Required repetition, nondeterminism, failure/recovery, keyboard/reflow/accessibility, evidence emission, CI, and video evidence pass; the user accepts the deployed workflow. | **Not started** — partial technical evidence already recorded remains supporting evidence only. |

## Required D1 completion work

The active implementation slice is to finish the product surface without
widening scope. T150/T174/T151 are complete from their own characterization,
shell, and browser evidence. Close T175/T152, T176/T177, T178/T153, and
T179/T154 only from their own evidence, then pause for user acceptance of the
live 4c experience before beginning M4. The remaining D1
hardening—five-family clean-import coverage, complete reset/reimport recovery,
changed/layout-only child behavior, schema-backed evidence emission, repetition,
CI, and release evidence—remains individually tracked in T139–T182. No bridge
task may close those tasks or substitute backend evidence for product UX.

Superset REST publication, embedded Superset, bidirectional reconciliation,
sharing/scheduling, automatic refresh, production authentication and
authorization, and model-generated visualization specifications remain outside
this local MVP.
