# Feature 004: Real Adapter Entrypoints — chartsearchai PoC

**Roadmap slot**: M3 (`004-real-adapter-entrypoints`) per `specs/roadmap.canvas.tsx`
**Scope of this PR**: chartsearchai adapter only — proof of concept against `openmrs_test` from feature 002
**Status**: in progress | **Started**: 2026-05-16

## Goal

Drop the chartsearchai OpenMRS module (built from our `targets/chartsearchai/` submodule) into the existing harness backend, swap the harness frontend + gateway to the chartsearch-flavored images, point chartsearchai at LM Studio (or any OpenAI-compat endpoint) for remote LLM inference, and verify in a browser that a clinician question against a real demo patient (Zabella Halambe, 303 obs / 39 orders from feature 002) returns a grounded answer with citations.

This is M3 scoped to the chartsearchai adapter. The other M3 adapter targets (querystore, openmrs_chatbot, Catalyst) are explicit deferrals. See `plan.md` for the measured querystore situation justifying why it's not part of this PR.

## Success criteria

- **SC-004.1**: `make chartsearch-build` produces a `.omod` from our submodule SHA and drops it under `artifacts/openmrs/modules/`.
- **SC-004.2**: After restart with `OPENMRS_REFAPP_TAG=nightly-chartsearch` on frontend + gateway (backend stays on `:3.6.0`), `GET /ws/rest/v1/module/chartsearchai` reports `started: true`.
- **SC-004.3**: `make chartsearch-configure` sets the 3 chartsearchai LLM global properties (`engine`, `remote.endpointUrl`, `remote.modelName`) via REST; backend env carries `OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY` so the API key lands in `openmrs-runtime.properties`.
- **SC-004.4**: Browser flow against Zabella Halambe (uuid `dd75c020-1691-11df-97a5-7038c432aabf`) returns a streamed answer with at least one numbered citation when asked "What medications is this patient on?".
- **SC-004.5**: New architecture canvas at `specs/artifacts/canvases/chartsearchai-and-querystore.canvas.tsx` captures today's architecture, future querystore-backed architecture, port map, measured upstream status, and harness integration points.

## Functional requirements

- **FR-004.1**: The chartsearchai `.omod` MUST be built from the harness's `targets/chartsearchai/` submodule via `mvn -DskipTests package`. The submodule SHA is the pin.
- **FR-004.2**: The PoC MUST use chartsearchai's **remote** LLM engine (OpenAI-compatible). The bundled local llama-server is out of scope.
- **FR-004.3**: The harness MUST minimize customization vs upstream: no Dockerfile variants, no separate compose stack, no Maven build inside Docker. Only an env-var addition to the existing compose, an env-file template, a Makefile target wrapping `mvn package + cp`, and a small `chartsearch-configure.sh` wrapping 3 REST POSTs.
- **FR-004.4**: The PoC MUST NOT depend on querystore. Today's chartsearchai uses its own internal retrieval; querystore-backed retrieval is M8 (`009-querystore-parity-testbed`), deferred.
- **FR-004.5**: The architecture canvas MUST capture both the current standalone-chartsearchai shape and the future querystore-backed shape, with the migration gap and open-bug count from upstream so future planning has measured context.

## Demo patient anchor

| Field | Value |
|---|---|
| `patient_id` | 2429 |
| `uuid` | `dd75c020-1691-11df-97a5-7038c432aabf` |
| Given name | Zabella |
| Family name | Halambe |
| Gender | F |
| Birthdate | 1978-10-08 |
| Obs count | 303 |
| Encounter count | 11 |
| Order count | 39 |
| Condition count | 0 |
| Allergy count | 0 |

Richest chart in `openmrs_test`. Anchors the smoke on a known-populated medication history (39 orders).

**Smoke question**: *"What medications is this patient on?"*

**Assertions** (manual): (a) streamed answer text non-empty within ~60s, (b) References panel renders with ≥1 numbered citation, (c) citation links resolve to a chart tab.

NOT asserted: specific drug names. Brittle vs LLM phrasing; smoke is about wiring.

## Out of scope

- Local LLM engine (bundled `llama-server` + GGUF model) — `chartsearchai.llm.engine=remote` only
- Playwright automation — v2 follow-up
- chartsearchai's embedding/Lucene/hybrid/elasticsearch retrieval pipelines — default `preFilter=false` (full-chart mode) is the simplest path
- querystore module bringup — pre-alpha upstream, blocked by 5 critical runtime bugs + 4 open ADR questions (see `plan.md`)
- openmrs_chatbot + Catalyst adapters — future M3 iterations
- Digest-pinning the `:nightly-chartsearch` published image — v2 follow-up

## Non-functional notes

- **`:nightly-chartsearch` floats**: published image rebuilt nightly from upstream main. Acceptable for PoC; pin to digest in v2.
- **Backend stays at `:3.6.0`**: stock Amazon Linux 2 base hosts the chartsearchai `.omod` fine in remote-engine mode (the bundled `llama-server` is never invoked, so the glibc-2.39+ requirement is moot).
- **LM Studio**: default endpoint URL in `.env.chartsearch.example` is `http://host.docker.internal:1234/v1/chat/completions`. Anthropic/OpenAI shown as commented alternatives.
