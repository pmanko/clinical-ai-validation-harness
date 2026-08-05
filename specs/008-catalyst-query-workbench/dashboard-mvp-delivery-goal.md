# D1 Local Dashboard MVP Delivery Goal

**Status:** Active delivery target — local table-dashboard vertical slice is
implemented; real-model acceptance and MVP evidence remain open.

## Goal

Deliver a manually testable local Catalyst workflow in which a user uses the
accepted SQL workbench with the configured real Gemma writer and Qwen reviewer,
manually validates and runs a query, promotes that exact execution to one
Dataset, one verified table Widget, and one named Dashboard, publishes a native
Superset bundle, imports it into pinned local Superset, opens the stable
Superset URL, and reconciles representative displayed values to PostgreSQL.

The local named Docker volumes are the durable development state: `up` resumes
them, `restart` retains them, `seed` explicitly reloads the source pipeline,
and the **stack-level** `reset` is destructive. This is distinct from the
unimplemented D1 Superset last-verified recovery reset. No additional
FHIR-cache registry is part of this goal.

## Definition of done

| ID | Testable acceptance evidence |
| --- | --- |
| MVP-01 | An isolated stack starts with Catalyst UI, Gateway, analytics PostgreSQL, and Superset healthy; `restart` preserves the seeded mart and the Superset metadata volumes without a pipeline reload. |
| MVP-02 | A configured, available Gemma 4 12B writer and different-family Qwen 2.5 14B reviewer complete one question without silent fallback. The record names the actual profile, models, candidate digests, and configuration. |
| MVP-03 | The existing Ask workflow remains intact through explicit Run: one editable SQL editor, manual edit/versioning, advisory validation, explicit execution, typed results, and follow-up all work before Dataset promotion. |
| MVP-04 | One successful current execution creates a Dataset and a table Widget with exact query/execution/source/catalog provenance. Configuration and publication make no model or database call. |
| MVP-05 | A named Dashboard publishes one byte-stable native ZIP to the Catalyst outbox. The downloaded bytes equal the outbox bytes. The explicit importer records an `imported` receipt and verified last-verified projection. |
| MVP-06 | The stable `/superset/dashboard/catalyst-<dashboard-id>/` route opens in local Superset. At least three keyed displayed values reconcile to recorded reproducible PostgreSQL SQL. |
| MVP-07 | One versioned evidence directory records commits/image digest, profile/model configuration, query/execution IDs and SQL, bundle digest, receipt/projection, PostgreSQL reconciliation, and manual visual evidence. It labels any fake-router run as structural scaffolding, never as real-model acceptance. |
| MVP-08 | The user inspects and accepts the deployed local dashboard. |

## Checkpoints

| Checkpoint | Entry | Exit evidence | Decision |
| --- | --- | --- | --- |
| M0 — truthful baseline | Current branches and runtime evidence available | Product/docs/task state distinguishes the implemented table vertical slice from unimplemented D1 hardening; import receipts contain immutable component provenance rather than `worktree`; the `codex/` branch-name limitation of the SpecKit prerequisite is recorded rather than hidden. | Internal |
| M1 — persistent runtime | M0 complete | `up`, `restart`, `seed`, and stack-level `reset` behavior is documented and tested; restart preserves analytics and Superset volumes. This does not claim D1 last-verified recovery reset. | Internal |
| M2 — supervised deployment path | M1 complete | Existing Ask regression remains green; one exact execution produces Dataset → table Widget → named Dashboard → byte-matching bundle → verified import. | Internal |
| M3 — real-model evidence | M2 complete and models are available | MVP-02 through MVP-07 are demonstrated with no model substitution and record-level PostgreSQL reconciliation. | User review |
| M4 — local MVP acceptance | M3 complete | User opens and accepts the deployed Superset dashboard. | User acceptance |

## Explicitly deferred to D1 hardening

The fuller D1 program remains real work, but does not redefine the local MVP:
five clean-imported visualization families, multi-widget/library UX, a complete
reset/reimport recovery implementation, full accessibility matrix, changed and
layout-only child-version behavior, and the schema-backed dashboard event and
acceptance emitter. These remain in T139–T182 and must not be marked complete
from table-MVP evidence.
