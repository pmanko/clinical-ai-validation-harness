# Profile: Catalyst Harness Adapter Client

Describes `CatalystClient` (new, `harness/validate/catalyst_client.py`), the
concrete implementation that lets a harness validation scenario drive Catalyst
(spec Story 3, FR-009). Mirrors `ChartSearchAIClient` in
`harness/validate/client.py`.

## Interface satisfied

The `_Client` Protocol already defined in `harness/validate/runner.py`:

```python
class _Client(Protocol):
    def new_session(self, patient: str) -> str: ...
    def chat(
        self,
        patient: str,
        session: str | None,
        question: str,
        *,
        profile: str | None = None,
        request_id: str | None = None,
    ) -> ChatResult: ...
```

No new Protocol is introduced. See research.md item 1 for why this Protocol,
not `harness/adapters/*.py`, is the real reusable interface point.

## Method behavior

- **`new_session(patient)`**: Client-side no-op — generates and returns a
  UUID. Catalyst's M0.0 `catalyst-gateway` is stateless per request; no
  server-side session exists to create (research.md item 2). The returned
  value is still passed back into `chat()` for interface compatibility and
  appears in the harness's own run bookkeeping only.
- **`chat(patient, session, question, *, profile=None, request_id=None)`**:
  1. Sends `POST {endpointUrl}` (Catalyst gateway's `/v1/chat/completions`)
     with the OpenAI-compatible chat body; `patient` is folded into the
     question text (e.g., prefixed as context) rather than sent as a separate
     field — Catalyst's MCP tools resolve patient identity from the question
     itself via `search_patient`/`get_patient_context`.
  2. `profile` is accepted but ignored (Catalyst has no product-profile
     concept); passing a non-null value MUST NOT raise.
  3. Parses the sidecar response (`contracts/sidecar_response.schema.json`)
     into a `ChatResult`, with `envelope` set to the full parsed JSON body
     (so `citations`, `uiBlocks`, and `provenance` survive into the harness's
     `results.jsonl`, not just `answer`).
  4. On a non-2xx or unparseable response, returns a `ChatResult` whose
     envelope carries an explicit error shape — mirrors
     `ChartSearchAIClient`'s existing retry/error handling for the
     `_RETRYABLE` status set; reuse that set rather than redefining it.

## Backend registry entry shape

No change to `Backend`'s dataclass fields. A Catalyst backend entry in a
comparison set's backend registry JSON:

```json
{
  "catalyst-e4b": {
    "label": "Catalyst (gemma-e4b via llama-router)",
    "endpointUrl": "http://localhost:8000/v1/chat/completions",
    "modelName": "catalyst"
  }
}
```

`modelName` is a required field on `Backend` but unused by
`CatalystClient` — set to a fixed placeholder value; it is not forwarded to
the gateway request body (Catalyst's own `.env` already pins the model via
`LMSTUDIO_MODEL`, see the target's own configuration, not the harness).

## ComparisonSet wiring

`transport: "catalyst"` is added as a third accepted value on `ComparisonSet`
(`harness/validate/models.py`). `validate_execution_contract`
(`harness/validate/execution.py`) gains a `catalyst` branch: Catalyst backends
carry no `kind`/`provider` distinction (those are chartsearchai-specific
concepts, see `Backend.kind`), so the new branch only needs to reject backends
that set `provider` (a chartsearchai-only concept, same guard already used for
the `med-agent-hub` branch).

## Run manifest fields

`RunManifest.component = "catalyst"`. `target_provenance` records the
`targets/catalyst` submodule SHA at run time (same mechanism already used for
`chartsearchai`/`querystore` runs). No new manifest schema fields are
required — the sidecar response's own `provenance` object (fhir_surface,
fhir_base_url, tools_called, resource_ids) rides inside each result row's
persisted envelope, per FR-013.
