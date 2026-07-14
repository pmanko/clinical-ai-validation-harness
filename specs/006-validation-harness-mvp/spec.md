# Feature 006: Validation Harness MVP — scenario × backend comparison with human adjudication

> **PARTIALLY SUPERSEDED:** The scenario, artifact, report, and adjudication model remains current.
> Transport and product-selection text below predates the hub-profile relay. Current product runs send
> a hub product `profile` through ChartSearchAI `/chat`; only explicit low-level experiments call hub
> legs directly. See `specs/artifacts/planning/hub-consolidation-roadmap.md`.

**Roadmap slot**: this IS the validation spine (roadmap M2, slug `006` — the earlier `003` slug was never created); operationalizes it + answer/citation/abstention eval (012) + review/rubric (014) as a minimal, honest MVP.
**Scope of this PR**: an offline, file-first, deterministic-gated eval that runs authored multi-turn scenarios against multiple model backends through chartsearchai's own API, records results onto the existing run_manifest/events.jsonl spine, and presents a standalone TSX report with per-cell human adjudication.
**Status**: shipped validation spine; transport superseded by hub profiles | **Started**: 2026-05-28
**Depends on**: ChartSearchAI's hub relay and med-agent-hub product profiles. The harness drives product comparisons through ChartSearchAI and reserves direct hub legs for labeled low-level experiments.

## Goal

Let an operator (manually or in batch) run the same clinical question(s) against several hub profiles and labeled experimental arms, see the answers side-by-side with deterministic metrics, then adjudicate each with a clinical rubric and record the outcome in a consistent, provenance-linked form. Product comparisons exercise the real ChartSearchAI relay and med-agent-hub profile used by the UI.

This is deliberately **not** a clinician RCT. NASA-TLX, non-inferiority margins, randomized
crossover, and Krippendorff/Gwet inter-rater statistics remain explicit deferrals. Canonical source
resolution and separately attributed Scout judgments are now shipped; deterministic findings remain
distinct from advisory semantic judgments.

## Success criteria

- **SC-006.1**: A scenario is authored as checked-in JSON (`{id, patient_ref, turns[], tags, expectations}`); a comparison set references scenarios + backend configs. Both validate against a documented schema.
- **SC-006.2**: `harness validate run <comparison-set>` replays each scenario's turns in one ChatSearchAI session per product profile and writes one `results.jsonl` line per `(scenario, backend, turn)` under `artifacts/<run_id>/`, alongside a `run_manifest.json` that reuses the existing spine. Explicit low-level arms are labeled as experiments and call med-agent-hub directly.
- **SC-006.3**: Each result carries deterministic, no-LLM metrics. Client-derivable from chartsearchai's `/chat` response alone: `latency_ms`, `json_valid`, `citation_count`, `abstained`. NOT surfaced by chartsearchai's `/chat` response (which returns only `answer`/`disclaimer`/`references`/`blocks`/`session`/`messageId`): `tokens_in/out`, `finish_reasons`, and the OTel GenAI fields (`gen_ai.response.model`, `gen_ai.provider.name`) — mark these `null` in v1 (OTel-deferred; to be back-filled from the OTel span when wired).
- **SC-006.4**: A standalone TSX report (runs locally; built deployable but remote-deploy deferred) renders scenarios down the left, one column per backend, with the answer + citations + table blocks + metric chips, and a per-cell feedback form.
- **SC-006.5**: The feedback form captures the Scout 0–10 rubric (accuracy/completeness/relevance), an abstention outcome, a citation-groundedness judgement, a harm hard-fail, a pass/fail decision, reviewer id, and free text — appending one `feedback` doc per adjudication.
- **SC-006.6**: Persistence goes through one repository interface; the JSONL-file implementation is wired, the MongoDB implementation is a documented stub.
- **SC-006.7**: A candidate comparison set includes the default checked product profile plus a justified quality or topology comparison and 2–3 abstention probes. Direct-model and low-level legs are separate experimental sets.

## Functional requirements

- **FR-006.1**: Product runs MUST send a hub product `profile` through ChartSearchAI's real `/chat` path and replay turns in one persisted session. Low-level leg experiments MAY call med-agent-hub directly, but their configuration and reports MUST identify them as experiments rather than product behavior.
- **FR-006.2**: Scenarios MUST be multi-turn (a `turns[]` sequence replayed in one chat session per backend). Single-turn is just a one-element `turns[]`.
- **FR-006.3**: The runner MUST reuse the existing metadata spine (`harness/metadata.py`: `RunManifest`, `append_event`). A `result` is a projection over the run's events for one `(scenario, backend, turn)` referencing `run_id`; it MUST NOT re-declare provenance fields. Use canonical `gen_ai.provider.name` (the control-plane schema forbids `gen_ai.system`).
- **FR-006.4**: Deterministic metrics MUST be computed without any LLM call. Optional Scout judges
  run afterward as separately attributed actors and cannot override deterministic safety findings.
- **FR-006.5**: The rubric MUST be Scout's three axes at native 0–10 (accuracy, completeness, relevance) + categorical abstention outcome (`correct`/`over-abstained`/`failed-to-abstain`/`n-a`) + a single citation-groundedness judgement for the answer (`supported`/`partly`/`unsupported`, or `n-a`) + a harm hard-fail flag. *(v1 ships one scalar `citation_groundedness`; per-citation groundedness keyed by citation index is v2 — see the data model below.)*
- **FR-006.6**: Persistence MUST sit behind a `save(collection, doc)` / `find(collection, query)` repository interface. Collections: `scenarios`, `comparison_sets`, `results`, `feedback`. The file implementation maps each to JSONL (results/feedback under `artifacts/<run_id>/`; scenarios/comparison_sets as checked-in JSON). The Mongo implementation is a stub with the same interface.
- **FR-006.7**: The report MUST be a standalone TSX app reading run artifacts (not an in-ESM page) and MUST reimplement the citation display format (`[index] resourceType — date`) rather than importing the ESM renderer (which hard-depends on chart-nav DOM).
- **FR-006.8**: The harness MUST support multiple reviewers; when ≥2 feedback docs exist for a cell, report raw % agreement (and Cohen's κ if exactly 2). It MUST NOT block a run on agreement.
- **FR-006.9**: The harness MUST distinguish its evaluator `feedback` doc from chartsearchai's existing end-user thumbs feedback (`AiFeedback`); they are separate surfaces.

## Demo anchor

Zabella Halambe (`dd75c020-1691-11df-97a5-7038c432aabf`, 303 obs / 39 orders) is the first scenario's `patient_ref`. The default comparison set's first scenario is the multi-turn medication thread already used as the smoke for the multi-turn work:
1. "What medications is this patient on?"
2. "How many did you list?"
3. "And what about her allergies?"

Plus 2–3 abstention probes (e.g. a question about data not in the chart — abstention is the correct behavior).

## Data model (copy-pasteable shapes)

```jsonc
// scenarios/<id>.json            (collection: scenarios) — checked in
{ "id": "meds-zabella",
  "patient_ref": "dd75c020-1691-11df-97a5-7038c432aabf",
  "turns": [ {"n":1,"question":"What medications is this patient on?"},
             {"n":2,"question":"How many did you list?"},
             {"n":3,"question":"And what about her allergies?"} ],
  "tags": ["medications","multi-turn","smoke"],
  "expectations": { "should_cite_resource_types": ["MedicationRequest","Observation"],
                    "should_abstain": false } }

// comparison_sets/<id>.json      (collection: comparison_sets) — checked in
{ "id": "demo",
  "scenario_ids": ["meds-zabella","abstain-out-of-chart"],
  "backend_ids": ["single-12b-checked"] }  // product backend ids are authoritative hub profile ids; direct/leg experiments live in separate sets

// artifacts/<run_id>/results.jsonl   (collection: results) — one line per (scenario,backend,turn)
{ "run_id":"dev-...","scenario_id":"meds-zabella","turn":1,"backend_id":"gemma-local",
  "request": {...}, "response": {"answer":"...[1]...","references":[...],"blocks":[]},
  "metrics": {"latency_ms":8421,"tokens_in":5120,"tokens_out":240,"json_valid":true,
              "citation_count":1,"abstained":false,
              "gen_ai.response.model":"gemma-4-e2b-it","gen_ai.response.finish_reasons":["stop"]},
  "started_at":"...","ended_at":"..." }

// artifacts/<run_id>/feedback.jsonl  (collection: feedback) — human gate
{ "run_id":"dev-...","scenario_id":"meds-zabella","turn":1,"backend_id":"gemma-local",
  "reviewer":"pmanko@uw.edu",
  "scores": {"accuracy":8,"completeness":6,"relevance":9},
  "abstention_outcome":"n-a",
  "citation_groundedness":"supported",   // v1: one scalar judgement; per-citation citation_checks[{index,groundedness}] is v2
  "harm_fail":false,"decision":"pass","free_text":"missed the insulin order","created_at":"..." }
```

`run_manifest.json` is unchanged and owns provenance/OTel; results + feedback reference its `run_id`.

## Out of scope (deferred, not MVP)

- MongoDB implementation wiring + container; remote deployment of the report (compose service + Caddy). Build deployable, run local-only.
- Clinician-outcome validation and automated adjudication of judge disagreement.
- Automated `citations_resolve` (do `resourceId`s resolve against the patient's real records) → v2; v1 uses `citation_count` + human groundedness.
- NASA-TLX, non-inferiority margins, randomized crossover, blind pairwise comparison, Krippendorff α / Gwet AC2.
- Persisting a per-user profile preference. The hub advertises the available effective default; the picker retains only a valid advertised selection.

## Verification

1. Author the demo comparison set; `harness validate run demo` with the full local stack writes `run_manifest.json` + `results.jsonl` for the selected hub product profiles.
2. Deterministic metrics present + correct on a hand-checked run (latency/tokens non-zero, `json_valid` true, `citation_count` matches the answer).
3. Standalone report renders the comparison grid; submitting the feedback form appends a well-formed `feedback` doc.
4. Repository interface: same `find("results", …)` returns identical data from the file impl; Mongo impl raises a clear "not implemented" stub.
5. Multi-reviewer: two feedback docs on one cell → report shows raw % agreement.
