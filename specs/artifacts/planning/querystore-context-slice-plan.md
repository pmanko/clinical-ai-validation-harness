# QueryStore Context-Slice Consolidation Plan

Status: Approved execution plan (2026-07-22). Implements roadmap gates **G10 (Context policy)**
and **G11 (Context ceiling)** under the 2026-07-22 shared context-selection amendment recorded in
[`openmrs-dual-provider-parity-roadmap-status.md`](openmrs-dual-provider-parity-roadmap-status.md).
Instrument and measurements: [`engine-parity-instrument.md`](engine-parity-instrument.md).

## Why (measured, 2026-07-22)

The engine-parity instrument proved both providers implement the roadmap §5 `query_scoped`
invariants **partially and divergently**, each holding half the contract:

- bundled `QueryStoreChartBuilder.buildScoped`: typed-complete slices, similarity top-K,
  obs-group/panel completion, 15-record temporal-gated recency anchor — but **no mandatory
  clinical core** (allergies + active conditions absent from every non-scoped slice; fixture
  `context.enumerated-medications-are-complete` pins `mandatory_ids:["patient","allergy-1"]`).
- hub `context_sources._ranked_records`: mandatory core, 32-record always-on clinical-date
  recency core, token budget — but **no panel completion** (a listed `context_policy` invariant),
  and it re-mirrors querystore's `clinicalDate`/`dateKind` semantics client-side.

Measured record-set divergence on identical questions against the same index (system-prompt
format examples excluded): 27v36, 27v41, 36v78, 42v70. Two parallel implementations of one
contracted policy drift structurally; conformance fixtures catch drift after the fact — a single
implementation at the data owner prevents it by construction.

## Decision boundary (what moves, what does not)

QueryStore gains a **tiered record-selection contract** — retrieval, not prompt composition:

```
getContextSlice(patientUuid, question, ContextSliceRequest{types[], temporal})
  -> List<QueryDocument> + tier per record: mandatory | recency_anchor | typed | similarity
```
plus a REST twin (extending `patientrecord`). It implements, once, at the owner of the index,
dates, and group metadata: mandatory clinical core (patient + allergies + active conditions),
always-on clinical-date recency anchor, typed-complete slices for caller-declared types,
similarity union, obs-group/panel family completion, deduplication, deterministic order.

Engines keep: prompt composition, serialization, system prompts, token budgets (trimming over
tiers; `mandatory` is never droppable; overflow fails explicit `insufficient_context`), question
interpretation (intent routing / temporal detection — passed as `types[]`/`temporal` flags in v1),
and all selection for **non-QueryStore sources** (hub stays source-neutral).

Non-goal §12 "No model-context policy inside QueryStore" is re-scoped by the amendment to its
intent: **no prompt composition and no model/token-aware policy** in QueryStore. Record selection
tiers are model-agnostic retrieval semantics.

## Checkpoints (sequential; each red-first, each live-verified via the parity instrument)

### CP0 — Bundled mandatory clinical core (safety hotfix)
The measured safety gap, fixed at today's architecture so it does not wait for the refactor
(and its tests become part of the slice contract's spec).
- `buildScoped` always includes allergies + active conditions alongside the patient record.
- **Red-first:** Java test driving the real `buildScoped` against
  `context.enumerated-medications-are-complete` (mandatory allergy present in a medication
  slice) fails before, passes after. Full chartsearchai suite stays green (G06 preservation).
- **Live:** `parity-engine-probe` + `parity-engine-diff` show allergy/active-condition records
  in BOTH arms' answer-leg prompts for the medication scenario.
- Done when: tests green, live diff shows mandatory records in both slices, committed + pushed.

### CP1 — QueryStore context-slice contract (G10 core)
- `getContextSlice` API + REST mode with tier tags, implementing every §5 `query_scoped`
  selection invariant; `dual-provider-conformance.v1` `context_policy` fixtures become
  red-first querystore tests (typed-complete, recency anchor, mandatory, panel completion,
  stable ordering, trace of included/excluded IDs and reasons).
- Done when: fixture-driven querystore suite green; REST twin serves the slice with tier tags
  live on the harness stack; authorization semantics unchanged from `patientrecord`.

### CP2 — Bundled thin adapter
- `buildScoped` delegates selection to `getContextSlice` (in-process), keeping serialization
  and prompt assembly; `QueryScopeRouter` supplies `types[]`/`temporal`.
- Done when: chartsearchai suite green with the adapter (G06 — no behavior regressions beyond
  the approved selection change); parity instrument re-run shows bundled slice = slice-API
  output; CP0 tests still green (now passing through the shared path).

### CP3 — Hub thin adapter (G11)
- The hub's QueryStore source requests the slice; local ranking policy remains for inline/
  static sources; token budget trims over tiers, never dropping `mandatory`; overflow →
  explicit `insufficient_context` (ceiling-not-target).
- Done when: hub suite green; live hub turn consumes a tier-tagged slice; budget-overflow
  fixture passes; source-neutral paths (inline chart) untouched by construction.

### CP4 — Parity gate tightening (instrument closes the loop)
- Delete `documented_retrieval_divergence` from `engine-parity.v1`; the diff enforces
  record-set equality for querystore-sourced runs again (plus the invariant checks).
- Re-run the scenario sweep (probe + diff ×3) and `make validate-run SET=engine-parity-e4b`.
- Done when: sweep passes with retrieval `identical`; scored run 6/6 good cells; G10/G11
  status rows updated with the live evidence.

## Gate mapping and estimates

| Checkpoint | Gates | Repos | Estimate |
|---|---|---|---|
| CP0 | G10 (partial), G06 | chartsearchai | 0.5 day |
| CP1 | G10, G03 (context fixtures) | querystore | 1 day |
| CP2 | G10, G06 | chartsearchai | 0.5 day |
| CP3 | G11, G09 (source-neutrality preserved) | med-agent-hub | 0.5–1 day |
| CP4 | G10/G11 evidence | harness | 0.25 day |

## Risks / guards

- **Hub source-neutrality (G09):** slice consumption is per-source; inline/static paths keep the
  local policy. The hub must still start and answer without QueryStore.
- **Bundled preservation (G06):** CP2 changes selection only through the shared contract; the
  full suite and the golden bundled behaviors are the regression net.
- **ES full-chart cap:** querystore's 10k-doc `getPatientChart` cap applies inside the slice
  implementation — the slice must surface (not silently absorb) cap truncation, per the
  explicit-overflow invariant.
- **Question interpretation stays caller-side in v1** — intent/temporal drift between engines is
  still possible there; measured by the parity instrument, candidate for a later v2 if it shows.
