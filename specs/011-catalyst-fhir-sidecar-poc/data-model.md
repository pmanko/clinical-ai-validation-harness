# Phase 1 Data Model: Catalyst FHIR Sidecar POC

Entities from the spec's Key Entities section, made concrete against the
harness's existing dataclasses (`harness/validate/models.py`,
`harness/metadata.py`) and Catalyst's own code (`targets/catalyst/`).

## Canonical Question

Fixed, not authored data — the five questions from spec §"Canonical Question"
are a constant, not a runtime entity. Represented in code as a checked-in list
(mirroring `pocQuestions` in the paired canvas) used to generate the harness
scenario fixtures described below; not user-editable at runtime.

| # | Question | Primary FHIR resources |
|---|----------|------------------------|
| 1 | Show recent lab results for patient X. | Patient, Observation |
| 2 | What tests were ordered for patient X? | Patient, ServiceRequest |
| 3 | Summarize abnormal results for patient X. | Patient, Observation |
| 4 | Which diagnostic reports are available for patient X? | Patient, DiagnosticReport |
| 5 | What results are linked to order Y? | ServiceRequest, Observation |

## FHIR Citation

Not a new class — a shape within `Sidecar Response.citations[]` (below).

| Field | Type | Notes |
|---|---|---|
| `index` | int | 1-based, matches the inline `[type/index]` marker in `answer` text |
| `resourceType` | string | One of `Patient`, `ServiceRequest`, `Observation`, `DiagnosticReport`, `Practitioner`, `Organization` |
| `id` | string | FHIR resource id; MUST resolve against OE2 at answer time (FR-002) |
| `url` | string | Fully resolvable URL against the FHIR surface used (`fhir_surface`) |
| `display` | string | Human-readable label (e.g., "Hemoglobin — 2026-04-15") |

## Evidence Card

UI-only projection, not persisted separately — derived at render time by
grouping `citations[]` by `resourceType`. No new backend entity.

## Sidecar Response

The `catalyst-gateway` response shape (spec FR-005), extending the current
`/v1/chat/completions`-shaped payload with Catalyst-specific fields. Backward
compatible: `answer` remains a valid OpenAI-style `choices[0].message.content`
string; `facts`/`citations`/`uiBlocks`/`provenance` are additive fields Catalyst
clients (sidecar UI, harness adapter) read, and generic OpenAI clients ignore.

```json
{
  "answer": "string",
  "facts": [{ "text": "string", "source_ref": "ResourceType/id" }],
  "citations": [
    {
      "index": 1,
      "resourceType": "Observation",
      "id": "string",
      "url": "string",
      "display": "string"
    }
  ],
  "uiBlocks": [
    { "type": "lab_result_table", "rows": [ /* LabResultRow[] */ ] },
    { "type": "lab_timeline", "events": [ /* LabTimelineEvent[] */ ] }
  ],
  "provenance": {
    "fhir_surface": "hapi | embedded | hybrid",
    "fhir_base_url": "string",
    "tools_called": ["string"],
    "resource_ids": ["ResourceType/id"]
  }
}
```

Full JSON Schema: [`contracts/sidecar_response.schema.json`](contracts/sidecar_response.schema.json).

### LabResultRow (uiBlocks[type=lab_result_table].rows[])

| Field | Type | Notes |
|---|---|---|
| `test` | string | Test name |
| `value` | string | Result value (kept as string — units/precision vary) |
| `unit` | string | e.g. "g/dL" |
| `refRange` | string | e.g. "12.0-16.0" |
| `flag` | `N\|L\|H\|LL\|HH\|null` | Abnormal flag; `null` when the source `Observation` has none (Edge Case: must not be fabricated) |
| `date` | string (ISO-8601) | Effective date |
| `orderRef` | string | `ServiceRequest/id` |

### LabTimelineEvent (uiBlocks[type=lab_timeline].events[])

| Field | Type | Notes |
|---|---|---|
| `date` | string (ISO-8601) | |
| `resourceType` | `Observation\|DiagnosticReport` | |
| `id` | string | |
| `display` | string | |
| `flag` | `abnormal\|normal\|null` | |

## MCP FHIR Tool

Row-per-tool contract for `catalyst-mcp`, replacing/extending the mocked
`get_query_context`/`validate_sql` pair (FR-003, FR-004). Full parameter/return
shapes: [`contracts/catalyst_mcp_tools.schema.yaml`](contracts/catalyst_mcp_tools.schema.yaml).

| Tool | Primary resource | Notes |
|---|---|---|
| `search_patient` | Patient | Name/identifier search; returns a `Patient` bundle |
| `get_patient_context` | Patient | Demographic + identifier summary |
| `get_service_requests` | ServiceRequest | Lab orders for a patient; optional date range |
| `get_observations` | Observation | Lab results; optional test-code filter |
| `get_diagnostic_reports` | DiagnosticReport | |
| `get_resource_by_reference` | any | Resolves `ResourceType/id` |
| `build_patient_lab_timeline` | Observation, DiagnosticReport | Chronological merge |

## Gap-Log Entry

Produced by the Story 4 parity probe. Not part of the sidecar response —
written to a separate run artifact (`artifacts/<run_id>/catalyst_gap_log.jsonl`,
following the harness's existing `artifacts/<run_id>/` convention).

| Field | Type | Notes |
|---|---|---|
| `question_num` | int | 1-5, which canonical question triggered this read |
| `resource_type` | string | |
| `resource_id` | string \| null | `null` when the resource could not be identified at all on one surface |
| `hapi_status` | `present\|absent\|error` | |
| `embedded_status` | `present\|absent\|error` | |
| `divergence` | string | Human-readable description (e.g., "HAPI surface unreachable — TLS handshake halted at Request CERT, client certificate required") |
| `blocking` | `false` (always) | Gap-log entries never invalidate the embedded-path answer (FR-011) |

## Harness Adapter Entrypoint (Catalyst)

Extends existing harness validate-run entities rather than introducing new
ones:

- **`ComparisonSet.transport`** (`harness/validate/models.py`): add `"catalyst"`
  as a third accepted value alongside `"chartsearchai"` and `"med-agent-hub"`.
- **`CatalystClient`** (new, `harness/validate/catalyst_client.py`, mirroring
  `client.py`): implements the `_Client` Protocol from `harness/validate/runner.py`
  (`new_session`, `chat`) against `catalyst-gateway`'s `/v1/chat/completions`.
  See research.md item 2 for why `new_session` is a client-side no-op.
- **`Backend`** (existing dataclass, unchanged shape): a Catalyst backend entry
  in the JSON registry needs only `endpointUrl` (the gateway's
  `/v1/chat/completions` URL) and `modelName` (unused by Catalyst but required
  by the existing schema — set to a fixed placeholder like `"catalyst"`).
- **`RunManifest.component`** (existing field, `harness/metadata.py`): **correction
  after running the real flow** — `run_comparison()` hardcodes
  `component="validate"` for every transport (`harness/validate/runner.py`),
  not per-target; this is not a per-transport field today, contrary to this
  document's original assumption. Target identity for a Catalyst run is
  instead recoverable from `dataset_provenance.comparison_set` (references
  `011-catalyst-poc.json`, whose `transport: "catalyst"` is embedded) and
  each `results.jsonl` row's `backend_id`/response `provenance`. No schema
  change was needed either way. (Also observed: manifest's
  `dataset_provenance.missing_chart_fixtures` flags the scenario's
  `patient_ref` as a missing chartsearchai-style chart fixture — a harmless,
  informational chartsearchai-specific check that doesn't apply to
  FHIR-sourced data and doesn't block the run.)

## Relationships

```
Canonical Question (fixed, 5)
   └─ drives → Scenario (authored fixture, harness/validate shape)
                  └─ run via → CatalystClient.chat()
                                   └─ produces → Sidecar Response
                                                    ├─ citations[] ──resolves against──> OE2 FHIR resource (embedded surface)
                                                    ├─ uiBlocks[] ──rendered by──> Sidecar UI (Story 2)
                                                    └─ provenance ──persisted into──> RunManifest / results.jsonl (Story 3)

Sidecar Response citations[] ──replayed by Story 4 parity probe──> Gap-Log Entry (per divergence)
```
