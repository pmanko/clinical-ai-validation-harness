# Phase 0 Research: Catalyst FHIR Sidecar POC

Each item resolves one open technical question from the spec's Technical Context
or Assumptions. Format: Decision / Rationale / Alternatives considered.

## 1. What "reuse the feature 004 adapter interface" actually means in code

**Decision**: Implement a `CatalystClient` that satisfies the `_Client` Protocol
already defined in `harness/validate/runner.py` (`new_session(patient) -> str`,
`chat(patient, session, question, *, profile=None, request_id=None) -> ChatResult`),
the same shape `ChartSearchAIClient` (`harness/validate/client.py`) implements.
Add `"catalyst"` as a third accepted value to `ComparisonSet.transport` in
`harness/validate/models.py` (currently `{"chartsearchai", "med-agent-hub"}`),
and add a `catalyst` branch to `validate_execution_contract`
(`harness/validate/execution.py`) analogous to the existing `med-agent-hub` branch.

**Rationale**: Inspecting the actual code (not just the brief's prose) shows two
different things both loosely called "the adapter": `harness/adapters/*.py`
(thin, ~15-line dataclasses with a `command_plan()` list of shell commands, used
for build/CI validation, not live scenario runs) and the `_Client` Protocol in
`harness/validate/runner.py` (the actual pluggable interface `run_comparison()`
accepts, already home to two implementations — chartsearchai and med-agent-hub).
The spec's Story 3 ("harness's existing adapter interface") is best satisfied by
the Protocol, since that's what actually drives a scenario end-to-end and emits
run manifests/results today. `harness/adapters/catalyst.py` (matching the
existing `chartsearchai.py`/`querystore.py` files) can still be added as the
project-identity/command-plan record for consistency, but it is not on the
critical path for Story 3's acceptance scenario.

**Alternatives considered**: Building a wholly new generic adapter abstraction
layer above both `harness/adapters/` and `harness/validate/` was rejected as
scope creep — the constitution's Development Workflow gate asks plans to
explain why the *selected* evidence/tests are sufficient, not to redesign an
unrelated part of the harness this feature doesn't need to touch.

## 2. Catalyst gateway API shape vs. the `_Client` Protocol

**Decision**: `CatalystClient.chat()` calls Catalyst's `catalyst-gateway`
`POST /v1/chat/completions` (OpenAI-compatible; verified working locally against
the local llama-router). `new_session()` is a client-side no-op that returns a
generated UUID — Catalyst's M0.0 gateway is stateless per request (no
session/patient-context persistence server-side, unlike chartsearchai's
`/chat` REST surface). The `profile` kwarg is unused for Catalyst (no
product-profile concept); `patient` is folded into the question text sent to
the gateway, since MCP-side patient resolution (`search_patient`,
`get_patient_context`) happens inside Catalyst's own tool-calling loop, not via
a session-scoped patient parameter on the wire.

**Rationale**: Verified directly — `catalyst-gateway`'s `/health` and
`/v1/chat/completions` endpoints were exercised locally in this session and
return a standard OpenAI-shaped chat completion. No session or patient
parameter exists in that contract today.

**Alternatives considered**: Adding real session state to Catalyst's gateway to
mirror chartsearchai's `/chat` semantics was rejected as out of scope — it's
Catalyst-repo work (`openelis-catalyst`), not something this harness feature
should drive, and the spec's five canonical questions are all single-turn.

## 3. FHIR data access path: embedded-first (corrected from the brief's HAPI-first assumption), MCP-mediated

**Decision (revised after hands-on verification — supersedes the brief's §5
"HAPI-first for POC" framing)**: Catalyst's MCP server (`catalyst-mcp`) gains
the seven FHIR tools listed in spec FR-003, implemented against **OE2's
embedded FHIR provider** (`https://<oe2-host>/OpenELIS-Global/fhir/*`, HTTP
Basic auth) as the **primary** surface, with the HAPI sidecar
(`fhir.openelis.org`) treated as the **gap-logged, currently-unreachable**
surface instead of primary. This is the inverse of the brief's original
framing. `MCP_DB_ENABLED` stays `false` — the existing mocked
`get_query_context`/`validate_sql` tools are retained but not required by any
of the five canonical questions (spec FR-015).

**Rationale**: Directly verified against the running local stack, not assumed
from the brief:
- HAPI sidecar (`fhir.openelis.org`, host ports 8081 plain / 8444 TLS): the
  TLS listener demands a client certificate at the transport layer
  (`curl -v` shows `TLS handshake, Request CERT` followed by a `bad
  certificate` alert) — this blocks every request before the application
  layer is even reached, regardless of credentials. Confirmed unreachable
  without real client-cert provisioning, which is out of scope (brief §11).
- Embedded FHIR (`/OpenELIS-Global/fhir/*` on the main webapp, HTTPS on the
  same host/port as the app): reachable and functional. `GET
  .../fhir/Patient` with **no** auth returns a Spring Security redirect (302);
  with HTTP Basic auth using `admin:adminADMIN!` (the compose stack's
  `DEFAULT_PW`, distinct from the OpenMRS side's `Admin123` — confirmed by
  testing both), it returns `200` with a valid FHIR `Bundle`.
- FHIR sync is not automatic (`transformOnStartup=false`, matching the brief):
  fixture data loaded directly via SQL had `fhir_uuid IS NULL` on `patient`
  rows and 0 patients visible over FHIR. A `GET
  .../OpenELIS-Global/OEToFhir` (authenticated) triggers the backfill
  synchronously; afterward `patient.fhir_uuid` was populated and the embedded
  `Patient` FHIR endpoint returned all 3 fixture patients correctly.
- **Known data gap, not a code gap**: `ServiceRequest`/`Observation`/
  `DiagnosticReport` did not sync even after triggering `/OEToFhir`, despite
  14 real `analysis` (order) rows existing in `clinlims` for the fixture
  patients. `sample`/`sample_human`/`analysis` carry no `fhir_uuid` column at
  all (only `patient`/`organization`/`provider` do), so whatever join path the
  embedded `ServiceRequest`/`Observation` providers use evidently requires
  fixture state (e.g., a specific accession/result status) that OE2's own
  `--profile=core`/`--profile=harness` E2E fixtures don't produce — those
  fixtures exist to test storage/order UI workflows, not to produce
  FHIR-complete lab results. Root-causing OE2's transform-eligibility rule is
  OE2-side engineering, explicitly out of scope (brief §11: "Full OE2 FHIR
  sync / backfill engineering"). Practical effect: with current fixture data,
  questions 2 and 5 (ServiceRequest-shaped) can be exercised once
  order-resource sync is unblocked; questions 1, 3, and 4
  (Observation/DiagnosticReport-shaped) will correctly exercise the
  **abstention path** (spec FR-008, Edge Case, Acceptance Scenario 5) rather
  than a fabricated answer — legitimate, spec-required behavior, not a bug.

**Alternatives considered**: Direct PostgreSQL access to `clinlims` (the
`MCP_DB_ENABLED=true` path already scaffolded in `catalyst-mcp/src/config.py`)
was rejected per the brief's explicit reboot away from NL-to-SQL for the POC
(brief §11: SQL execution out of scope). Manually inserting synthetic `result`
rows via raw SQL to force all five questions to have "real" data was
considered and rejected: the `result` table's foreign keys
(`test_result_id`, `analyte_id`) and clinical-value semantics aren't something
to hand-fabricate under time pressure without domain review — doing so would
violate the constitution's Deterministic Reviewed Transforms principle
(unreviewed, ad hoc data does not count as a reviewed accepted transform) and
would misrepresent fabricated values as real OE2 production data.

## 4. Sidecar UI hosting technology

**Decision**: Gateway-served, server-rendered HTML with light HTMX-style partial
updates, served directly from `catalyst-gateway` (new routes alongside the
existing `/v1/chat/completions` and `/health`). No separate frontend build,
package, or dev server.

**Rationale**: The brief itself states this is simpler for a POC (brief §12
item 4), and the spec deliberately left this open only if it materially
affected Story 2's acceptance scenarios — it doesn't: evidence cards, a
lab-result table, and a lab timeline are all renderable as server-generated
HTML/CSS without a client framework. Keeping Catalyst's dependency footprint at
"FastAPI + Jinja2" (already available in the gateway's stack) avoids adding a
Node/Vite toolchain to a Python-only submodule.

**Alternatives considered**: A separate Vite/React app in `openelis-catalyst`
was rejected for the POC — it would duplicate `chartsearchai-esm`'s Node
tooling investment for a UI whose brief explicitly says integration into any
real frontend (OE2 Carbon, or a durable Catalyst app) is deferred past this
POC (brief §7, §11).

## 5. OE2 HAPI-sidecar mTLS requirement (new fact, not in the brief; corrects which surface is blocked)

**Decision**: Document this as a Story 4 (parity probe) gap-log entry rather
than building client-certificate handling into Catalyst for the POC. The
parity probe records "HAPI FHIR sidecar unreachable without a client
certificate" as a divergence and continues; it does not block the
embedded-path answer (which, per item 3 above, is now the primary path, not
the parity-probe side).

**Rationale**: Verified directly during local OE2 setup: `curl` against OE2's
external HAPI container (`https://localhost:8444/fhir/...`) fails TLS
handshake with `Request CERT` / `bad certificate` — the container's HTTPS
listener requires a client certificate, which the source brief did not
identify (brief §3 says HAPI has "no application-layer auth", which is
consistent — this is a transport-layer mTLS requirement, a layer below the
app). Building certificate provisioning for the parity probe is real,
non-trivial OE2-side work and squarely matches the brief's own "out of scope"
category for OE2-side FHIR-layer hardening (brief §11). Since HAPI, not
embedded, turns out to be the surface with real friction, and embedded turns
out to be reachable with ordinary HTTP Basic auth (item 3), Story 4's parity
probe direction is effectively reversed from the brief's assumption: it now
probes "does HAPI work at all" against the working embedded baseline, rather
than probing "does embedded match the working HAPI baseline."

**Alternatives considered**: Skipping the parity probe (Story 4) entirely was
considered, but rejected — the gap itself (mTLS required on the HAPI surface)
is exactly the kind of finding the parity probe exists to surface, and
recording "surface unreachable, here's why" is a valid, low-cost gap-log entry
that still satisfies Story 4's acceptance scenarios without solving the
underlying OE2 auth problem.

## 6. Harness target metadata update

**Decision**: `harness/targets.yaml`'s `catalyst` entry (`evidence_status:
scaffolding`, `validation_surface.kind: unavailable`) is updated as part of
this feature's implementation (not this planning phase) once the adapter
client and MCP FHIR tools are real, per the comment already in that file:
"Specific validation commands will be declared by a future feature that
exercises Catalyst's real path" — this is that feature.

**Rationale**: Constitution Principle I (Real Production Paths) requires
adapters to exercise real target behavior, not harness-only simulation; leaving
stale `scaffolding`/`unavailable` metadata after this feature ships real FHIR
reads would misrepresent evidence status to reviewers.

**Alternatives considered**: N/A — this is a direct constitutional requirement,
not a design choice.
