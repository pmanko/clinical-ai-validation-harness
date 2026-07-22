# Engine-Level Parity Instrument — Bundled vs Hub

Status: Approved goal specification (2026-07-22). Companion to
`openmrs-dual-provider-parity-roadmap.md`; this document is the authoritative detail behind the
active `/goal` and is referenced by it.

## Goal statement

One patient, one question, one engine. Prove that ChartSearchAI's bundled and hub providers are
interchangeable at the LLM-engine boundary: capture the verbatim request each path delivers to the
engine, diff them under a versioned contract, and run a scored side-by-side where the only
uncontrolled variable is the orchestration path itself — not hardware, weights, or hidden prompt
drift.

Grounding for the boundary: bundled's `LlmEngine` (`api/impl/LlmEngine.java:31`) with
`RemoteLlmEngine` speaking OpenAI-compatible chat completions (GPs `chartsearchai.llm.engine`,
`chartsearchai.llm.remote.endpointUrl`, `chartsearchai.llm.remote.modelName`); hub's
`HttpHubStreamTransport.requestJson()` posting `{model: profileId, patient, messages, context}` to
`chartsearchai.hub.endpointUrl`, with the hub composing its own engine calls against
`LLM_BASE_URL`.

## Settled design decisions

- **D1 — Shared engine.** Parity config runs bundled with `chartsearchai.llm.engine=remote` and
  `chartsearchai.llm.remote.endpointUrl` pointed at the same host llama-router (`:8077`) and the
  same gemma-e4b model id the hub's `LLM_BASE_URL` uses. Same weights, same server, same Metal.
  `LocalLlmEngine`'s in-container subprocess is a deployment variant, out of scope for the
  instrument (side effect: no GGUF needs provisioning into the backend container for parity runs).
- **D2 — Capture at engine ingress.** A recording tap (thin logging proxy, one ingress port per
  arm, both forwarding to the router) records every request body byte-for-byte. Attribution is by
  ingress port — no content sniffing, no code changes in either module.
- **D3 — Contract-governed diff.** A versioned fixture (`engine-parity.v1`, sibling of
  `dual-provider-conformance.v1`) is the parity ledger: every difference between the two arms'
  engine requests is either documented-and-justified or a violation. Shrinking the documented list
  over time is the refactoring driver.

## Acceptance criteria

### AC-1 — Shared engine, verified not assumed
`make parity-engine-up` (or a dual-provider-up flag) configures the stack; a check asserts the
bundled GPs and the hub's `LLM_BASE_URL` resolve to the same server, and one probe turn per arm
shows both captured requests carry the same model id.
**Pass:** check exits 0; both artifacts' `model` fields are equal; run manifest records both
endpoint targets.

### AC-2 — Verbatim capture + external queryability
`scripts/parity-engine-probe.py --patient <uuid> --question "<q>"` runs one identical turn through
each provider (via `/chat` with `provider=bundled|hub`) and writes `engine_request.bundled.json` /
`engine_request.hub.json` — the exact POST bodies seen at the engine boundary. Replaying each
captured body from the host against its engine endpoint returns a valid completion.
**Pass:** probe exits 0, both artifacts exist, both replays return HTTP 200 with a non-empty
completion. This satisfies the "bundled interface accessible externally" requirement by
construction.

### AC-3 — Contract diff: zero undocumented divergence
`scripts/parity-engine-diff.py <a> <b>` classifies every JSON path of the answer-leg request (the
call whose final user message contains the verbatim question) into `identical |
documented_divergence(reason) | violation`. Initial documented set, from code: system-prompt
author (GP `chartsearchai.llm.systemPrompt` vs hub-owned), chart serialization format
(`PatientChartSerializer` vs hub `chart_serializer`), `response_format` schema family. Must-match:
model id, verbatim question text, sampling params where both set them.
**Pass:** red-first test in CI; zero violations across the demo scenario set.

### AC-4 — Retrieval parity (same chart in, provably)
Both arms' context originates from the same querystore index (the restored snapshot) with
equivalent retrieval parameters. The diff extracts the record-identifier sets from both answer-leg
prompts and compares them.
**Pass:** record sets are equal per turn, or the run fails — a retrieval-parameter difference
(limit/q policy) must be eliminated or added to the contract explicitly before this AC can pass.

### AC-5 — Scored parity run through the product boundary
`make validate-run SET=engine-parity-e4b` — comparison set with two arms (`provider=bundled`,
`provider=hub`), same scenarios, same `REFERENCE_DATE`. Needs the small harness plumbing:
`Backend.provider` field + `ChartSearchAiClient` passing `provider` in the POST body (the
controller already accepts it: `ChartSearchAiRestController.java:822`).
**Pass:** every scenario×arm cell has HTTP 200 + non-fallback answer per `_row_is_good`; report
renders both arms side-by-side; `run_meta.json` freezes both arms' engine endpoint + model,
proving AC-1 held for the whole run.

### AC-6 — Honest readiness
`GET /providers` reports bundled `ready:false` when its configured engine is unreachable, `true`
when reachable.
**Pass:** red-first test — stop llama-router → `ready:false`; start it → `ready:true`. (Today it
reports `ready:true` with no engine at all; a false-ready breaks the instrument.)

## Build inventory

Tap proxy + probe + diff scripts (new, harness-side), `engine-parity.v1` contract fixture,
`Backend.provider` plumbing (~4 small edits: `harness/validate/models.py`,
`harness/validate/client.py`, router-policy guard in `harness/validate/runner.py`, comparison-set
JSON), readiness fix in the provider registry/descriptor path, one comparison set + GP config
recipe. Estimate: 1.5–2 focused days, red-first throughout.
