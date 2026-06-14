# Feature 006: Validation Harness MVP — scenario × backend comparison with human adjudication

**Roadmap slot**: this IS the validation spine (roadmap M2, slug `006` — the earlier `003` slug was never created); operationalizes it + answer/citation/abstention eval (012) + review/rubric (014) as a minimal, honest MVP.
**Scope of this PR**: an offline, file-first, deterministic-gated eval that runs authored multi-turn scenarios against multiple model backends through chartsearchai's own API, records results onto the existing run_manifest/events.jsonl spine, and presents a standalone TSX report with per-cell human adjudication.
**Status**: in progress (core runner/client/report + feedback form shipped and live-run validated) | **Started**: 2026-05-28
**Depends on**: the med-agent-hub bridge + endpoint-registry picker (shipped on branch `004`; see `specs/005-med-agent-hub-bridge/spec.md` and `specs/artifacts/planning/archive/med-agent-team-poc-roadmap.md`) — the harness drives backends through chartsearchai's REST API and compares the `med-agent-team` endpoint that bridge stands up.

## Goal

Let an operator (manually or in batch) run the same clinical question(s) against several model backends — a small Gemma, MedGemma, and the med-agent-team router by default — and see the answers side-by-side with deterministic metrics, then adjudicate each with a clinical rubric and record the outcome in a consistent, provenance-linked form. The harness exercises chartsearchai's *real* pipeline (chart build → prompt → structured `{answer, references, blocks}` → citation extraction), not raw model output, by driving the exact REST API the chat UI drives.

This is deliberately **not** a clinician RCT. NASA-TLX, non-inferiority margins, randomized crossover, an automated citation resolver, an LLM-as-judge subsystem, and Krippendorff/Gwet inter-rater statistics are explicit deferrals.

## Success criteria

- **SC-006.1**: A scenario is authored as checked-in JSON (`{id, patient_ref, turns[], tags, expectations}`); a comparison set references scenarios + backend configs. Both validate against a documented schema.
- **SC-006.2**: `harness validate run <comparison-set>` replays each scenario's turns in one chat session per backend — selecting the backend **per request**: `{endpointUrl, modelName}` are sent in each `POST /chat` body as a per-request override (chartsearchai uses that backend for that request only, leaving its config-controlled global default untouched) — and writes one `results.jsonl` line per `(scenario, backend, turn)` under `artifacts/<run_id>/`, alongside a `run_manifest.json` that reuses the existing spine.
- **SC-006.3**: Each result carries deterministic, no-LLM metrics. Client-derivable from chartsearchai's `/chat` response alone: `latency_ms`, `json_valid`, `citation_count`, `abstained`. NOT surfaced by chartsearchai's `/chat` response (which returns only `answer`/`disclaimer`/`references`/`blocks`/`session`/`messageId`): `tokens_in/out`, `finish_reasons`, and the OTel GenAI fields (`gen_ai.response.model`, `gen_ai.provider.name`) — mark these `null` in v1 (OTel-deferred; to be back-filled from the OTel span when wired).
- **SC-006.4**: A standalone TSX report (runs locally; built deployable but remote-deploy deferred) renders scenarios down the left, one column per backend, with the answer + citations + table blocks + metric chips, and a per-cell feedback form.
- **SC-006.5**: The feedback form captures the Scout 0–10 rubric (accuracy/completeness/relevance), an abstention outcome, a citation-groundedness judgement, a harm hard-fail, a pass/fail decision, reviewer id, and free text — appending one `feedback` doc per adjudication.
- **SC-006.6**: Persistence goes through one repository interface; the JSONL-file implementation is wired, the MongoDB implementation is a documented stub.
- **SC-006.7**: The default comparison set includes a Gemma single-model backend, a MedGemma single-model backend, and the med-agent-team router, plus 2–3 abstention-probe scenarios (out-of-chart / leading / dangerous-action).

## Functional requirements

- **FR-006.1**: The runner MUST drive backends via chartsearchai's real REST API — selecting the backend **per request**: `{endpointUrl, modelName}` are carried IN each `POST /chat` body as a per-request override (chartsearchai's request-scoped `RequestLlmOverride`, validated against the endpoint registry; that backend is used for that request only and the config-controlled global default is NOT mutated), replaying the scenario's turns in one chat session. No bypassing chartsearchai to call the LLM endpoints directly. (The config-only `POST /endpoint` global switch is for the picker's "set as default", not the runner.)
- **FR-006.2**: Scenarios MUST be multi-turn (a `turns[]` sequence replayed in one chat session per backend). Single-turn is just a one-element `turns[]`.
- **FR-006.3**: The runner MUST reuse the existing metadata spine (`harness/metadata.py`: `RunManifest`, `append_event`). A `result` is a projection over the run's events for one `(scenario, backend, turn)` referencing `run_id`; it MUST NOT re-declare provenance fields. Use canonical `gen_ai.provider.name` (the control-plane schema forbids `gen_ai.system`).
- **FR-006.4**: Deterministic metrics MUST be computed without any LLM call. No LLM-as-judge in v1. The pass/fail and safe/unsafe decision is human-only.
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
  "backend_ids": ["gemma-local","medgemma-local","med-agent-team"] }  // each backend_id resolves (via the checked-in backends.json registry) to a concrete {endpointUrl, modelName} included in each POST /chat request body as the per-request override

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
- LLM-as-judge (advisory or gating) — schema leaves room; ship later behind a flag, advisory-only.
- Automated `citations_resolve` (do `resourceId`s resolve against the patient's real records) → v2; v1 uses `citation_count` + human groundedness.
- NASA-TLX, non-inferiority margins, randomized crossover, blind pairwise comparison, Krippendorff α / Gwet AC2.
- Persisting a per-session/per-user *default* backend server-side. (The picker and harness already select per request: the picker holds a per-browser-session choice and the harness sends `{endpointUrl, modelName}` in each `POST /chat` — a request-scoped override that never mutates the config-controlled global default. Only persisting that choice as a per-user default is deferred.)

## Verification

1. Author the demo comparison set; `harness validate run demo` with the full local stack up (backend + DB + LM Studio + med-agent-hub) writes `run_manifest.json` + `results.jsonl` with the three backends.
2. Deterministic metrics present + correct on a hand-checked run (latency/tokens non-zero, `json_valid` true, `citation_count` matches the answer).
3. Standalone report renders the comparison grid; submitting the feedback form appends a well-formed `feedback` doc.
4. Repository interface: same `find("results", …)` returns identical data from the file impl; Mongo impl raises a clear "not implemented" stub.
5. Multi-reviewer: two feedback docs on one cell → report shows raw % agreement.
