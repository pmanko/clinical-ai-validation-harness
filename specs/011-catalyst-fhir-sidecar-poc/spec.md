# Feature Specification: Catalyst FHIR Sidecar POC

**Feature Branch**: `011-catalyst-fhir-sidecar-poc`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Catalyst FHIR sidecar POC (M10 / feature 011) from specs/artifacts/planning/catalyst-fhir-sidecar-brief.md and the canvas mockup specs/artifacts/canvases/catalyst-fhir-sidecar.canvas.tsx: define the sidecar's FHIR surface against OpenELIS-Global-2, the harness adapter entrypoint (reusing the 004 adapter interface), and the first judged validation scenario for lab AI. Design-first: spec + plan + mockup integration before any build. Resolve the brief's §12 open questions in /speckit-clarify first."

## Clarifications

No `[NEEDS CLARIFICATION]` markers remain in this draft. The source brief's five open questions (§12) were each resolved with a documented default and fallback in Assumptions below, rather than requiring an interactive round. Run `/speckit-clarify` before `/speckit-plan` if any of those defaults should be revisited with the user instead.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask the Five Canonical Lab Questions (Priority: P1)

A lab reviewer asks Catalyst one of the five canonical questions about a specific patient's labs ("Show recent lab results for patient X," "What tests were ordered for patient X," "Summarize abnormal results for patient X," "Which diagnostic reports are available for patient X," "What results are linked to order Y") and receives an answer grounded in OpenELIS Global 2's (OE2) real FHIR data, with every claim traceable to a specific, resolvable FHIR resource.

**Why this priority**: This is the non-negotiable acceptance bar for the POC. Without cited, resolvable answers to all five questions, there is no evidence the FHIR-first approach works at all, and nothing else in this feature has a foundation to sit on.

**Independent Test**: Can be fully tested by asking each of the five canonical questions against a patient with lab data present in OE2 (via OE2's embedded FHIR provider — the surface verified reachable for this POC, see Assumptions) and confirming each answer includes citation markers whose referenced FHIR resource IDs (`Patient`, `Observation`, `ServiceRequest`, `DiagnosticReport`) resolve to real resources in OE2.

**Acceptance Scenarios**:

1. **Given** a patient in OE2 with recorded lab observations, **When** a reviewer asks "Show recent lab results for patient X," **Then** the answer lists the results and cites the specific `Observation` resource IDs used, and each ID resolves against OE2's FHIR endpoint.
2. **Given** a patient with one or more lab orders, **When** a reviewer asks "What tests were ordered for patient X," **Then** the answer cites the specific `ServiceRequest` resource IDs used, and each ID resolves against OE2.
3. **Given** a patient with at least one abnormal result, **When** a reviewer asks "Summarize abnormal results for patient X," **Then** the answer identifies only results flagged abnormal in the source `Observation` resources and cites those specific resources.
4. **Given** an order with linked results, **When** a reviewer asks "What results are linked to order Y," **Then** the answer cites the `ServiceRequest` and the `Observation` resources actually referencing that order.
5. **Given** a patient with no lab data recorded in OE2, **When** a reviewer asks any of the five questions about that patient, **Then** the system states that no relevant data was found rather than producing an answer with fabricated or unresolvable citations.

---

### User Story 2 - Review Answers Through the Sidecar Report UI (Priority: P2)

A lab reviewer reads an answer through the Catalyst sidecar's report/analytics UI rather than a bare chat transcript: an answer panel with inline citation markers, evidence cards grouped by FHIR resource type, a lab-result table, and a time-ordered lab timeline with abnormal results highlighted.

**Why this priority**: The brief explicitly positions Catalyst against Scout-style evidence-carded output, not free-form chat. This is what makes the answer *reviewable* rather than merely plausible, and it's the interaction model the POC is meant to validate for future milestones — but it depends on Story 1's grounded answers existing first.

**Independent Test**: Can be fully tested by asking one of the five canonical questions and confirming the response renders an answer panel with citation markers, at least one evidence card per referenced resource type, a lab-result table for any `Observation` resources involved, and a lab timeline entry for each dated resource — without requiring the reviewer to read raw FHIR JSON.

**Acceptance Scenarios**:

1. **Given** an answer that cites two different FHIR resource types, **When** the reviewer views the response, **Then** the UI shows one evidence card group per resource type, each card showing the resource type, resource ID, and a human-readable display line.
2. **Given** an answer involving `Observation` resources, **When** the reviewer views the response, **Then** the lab-result table shows test name, value, units, reference range, abnormal flag, effective date, and the linked order reference for each observation.
3. **Given** an answer involving dated `Observation` or `DiagnosticReport` resources, **When** the reviewer views the lab timeline, **Then** entries appear in chronological order with abnormal entries visually distinguished from normal ones.
4. **Given** a reviewer wants to inspect the underlying mechanics, **When** they open the debug drawer, **Then** they can see which MCP tools were called, what FHIR queries were issued, and the raw resource IDs and snippets involved.

---

### User Story 3 - Run the POC Through the Harness's Adapter Interface (Priority: P3)

A harness operator runs a Catalyst validation scenario through the same adapter entrypoint pattern already established for chartsearchai (feature 004), proving that a second clinical system can be validated through the harness's existing control plane without harness-core changes specific to Catalyst.

**Why this priority**: This is the "reusable harness" proof named in the roadmap lane — it validates the harness's adapter abstraction generalizes beyond a single target, which matters for every future target beyond chartsearchai and Catalyst. It depends on Story 1 producing real, citable answers to drive through the adapter.

**Independent Test**: Can be fully tested by running one of the five canonical questions as a harness validation scenario against the Catalyst adapter entrypoint and confirming the run produces a result record on the harness's existing metadata spine (run manifest + event trace) without requiring new harness-core code paths beyond the adapter itself.

**Acceptance Scenarios**:

1. **Given** the Catalyst adapter entrypoint is implemented, **When** a harness operator runs a scenario against it, **Then** the run produces a `run_manifest` and per-turn result entries in the same shape used by other harness targets.
2. **Given** a completed adapter run, **When** a reviewer inspects the result, **Then** citations, provenance (`fhir_surface`, `fhir_base_url`, tools called, resource IDs), and the raw answer are all present in the persisted record.

---

### User Story 4 - Surface HAPI/Embedded FHIR Divergence as a Gap Log (Priority: P4)

> **Note**: This story's direction was corrected during planning (see `plan.md`/`research.md`) from the original brief's assumption. Hands-on verification found OE2's embedded FHIR provider — not the HAPI sidecar — is the surface actually reachable for this POC (the HAPI sidecar's TLS listener demands a client certificate this POC does not provision). Story 1 therefore answers questions using the embedded surface as its grounded path, and this story's parity probe checks whether the HAPI sidecar can be reached and matches it, the reverse of the original framing. The acceptance bar (a documented, non-blocking gap log) is unchanged.

After the embedded-grounded answer path works (Story 1), the same five canonical questions' underlying FHIR reads are replayed against OE2's HAPI FHIR sidecar, and any divergence — including the sidecar being unreachable at all — is recorded as a documented gap rather than silently ignored or treated as a blocking failure.

**Why this priority**: This is what makes the POC's evidence credible beyond "it works against the one surface we happened to get working" — it's a diagnostic pass, not a launch blocker, so it is correctly the lowest priority: valuable, but the POC still delivers value without it if time runs short.

**Independent Test**: Can be fully tested by replaying the five canonical questions' underlying FHIR reads against OE2's HAPI FHIR sidecar and confirming a gap-log entry is produced for every resource read that differs (or is unavailable) between the embedded surface and HAPI, without that divergence blocking the embedded-path answer already produced in Story 1.

**Acceptance Scenarios**:

1. **Given** a resource is available identically on both FHIR surfaces, **When** the parity probe runs, **Then** no gap-log entry is created for that resource.
2. **Given** a resource is available on the embedded surface but unavailable or materially different on HAPI (including HAPI being entirely unreachable), **When** the parity probe runs, **Then** a gap-log entry records the resource, the surface(s) involved, and the nature of the divergence, and the original embedded-grounded answer remains valid and visible.
3. **Given** the `Specimen` resource type has no dedicated embedded FHIR provider, **When** the parity probe encounters a question path that would touch `Specimen`, **Then** the gap is documented and the probe continues rather than failing the run.

---

### Edge Cases

- A canonical question references a patient name that matches multiple patients in OE2 — the system must not silently pick one.
- A canonical question references an order (`ServiceRequest`) that does not exist or has no linked results.
- OE2's embedded FHIR endpoint (the primary path, see Assumptions) is unreachable or times out mid-query.
- A FHIR resource referenced by a citation is deleted or changes between answer generation and reviewer verification.
- The `Specimen` resource type is requested indirectly by a question but has no dedicated embedded FHIR provider (see User Story 4).
- An `Observation` has no reference range or abnormal flag recorded — the lab-result table and timeline must degrade gracefully rather than fabricate a flag.
- The HAPI FHIR sidecar requires a client certificate the parity probe does not have (verified: this is the actual current state, not a hypothetical) — the probe records this as a gap rather than crashing the run.
- A patient has orders (`ServiceRequest`) but no results yet synced to FHIR (verified: this is the actual current state of local demo data) — the system must abstain on result-shaped questions for that patient rather than fabricate results, while still answering order-shaped questions correctly.
- A reviewer opens the debug drawer for an answer that made zero tool calls (pure abstention) — the drawer must show that plainly rather than appearing broken.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST answer all five canonical questions (§6 of the source brief) using live reads against OE2's embedded FHIR provider as the primary data path (corrected from the source brief's HAPI-first assumption — see Assumptions and `research.md` item 3 for why).
- **FR-002**: Every answer MUST cite the specific FHIR resource ID(s) it used, and every cited ID MUST resolve to a real resource in OE2 at answer time.
- **FR-003**: The system MUST provide MCP tools covering, at minimum: patient search, patient demographic/identifier context, service requests (lab orders) for a patient, observations (lab results) for a patient, diagnostic reports for a patient, resolving an arbitrary FHIR reference, and building a chronological lab timeline for a patient.
- **FR-004**: Catalyst's agent layer MUST call FHIR data access exclusively through the MCP protocol tools; it MUST NOT bypass MCP via a direct in-process stub.
- **FR-005**: The system MUST produce a structured response containing the answer text, extracted facts with source references, a citation list (resource type, ID, resolvable URL, display text), UI blocks (lab-result table, lab timeline), and provenance (FHIR surface used, base URL, tools called, resource IDs touched).
- **FR-006**: The sidecar UI MUST render an answer panel with inline citation markers, evidence cards grouped by FHIR resource type, a lab-result table, and a chronological lab timeline with abnormal entries visually distinguished.
- **FR-007**: The sidecar UI MUST provide an on-demand debug view showing which MCP tools were called, what FHIR queries were issued, and the raw resource IDs and snippets involved.
- **FR-008**: When no relevant FHIR data exists for a question, the system MUST state that rather than producing an answer with fabricated or unresolvable citations.
- **FR-009**: The system MUST provide a harness adapter entrypoint for Catalyst that follows the existing adapter interface pattern established in feature 004, producing run manifests and per-turn results on the harness's existing metadata spine.
- **FR-010**: After the embedded-grounded answer path is validated, the system MUST support replaying the five canonical questions' underlying FHIR reads against OE2's HAPI FHIR sidecar and recording any divergence (missing resource, differing content, unavailable surface — including a wholesale-unreachable sidecar) as a gap-log entry rather than failing the run.
- **FR-011**: A recorded parity-probe divergence MUST NOT invalidate or hide the original embedded-grounded answer produced for the same question.
- **FR-012**: The system MUST identify whether validation uses real OE2 FHIR data/APIs or non-evidence scaffolding (e.g., mocked schema responses), consistent with the harness's existing evidence-status model.
- **FR-013**: The system MUST preserve record-level evidence for each answer — which FHIR resources were read, why they support the answer's claims, and the surface (HAPI vs embedded) they came from.
- **FR-014**: The system MUST NOT place identifiable patient data into LLM prompt context beyond what is already accepted practice for the existing chartsearchai/med-agent-hub pipeline; full "LocalPHI" hardening remains explicitly out of scope for this POC (see Assumptions).
- **FR-015**: SQL execution against OE2's relational database MUST remain out of the critical path for this POC; the existing `validate_sql` MCP tool MAY remain available but MUST NOT be required by any of the five canonical questions.

### Key Entities

- **Canonical Question**: One of the five fixed acceptance questions from the source brief; each names the primary FHIR resource types it exercises and is not expandable without a spec change.
- **FHIR Citation**: A reference from an answer to a specific FHIR resource (type + ID + resolvable URL + display text) that a reviewer can independently verify against OE2.
- **Evidence Card**: A UI element grouping citations by FHIR resource type, showing resource ID and human-readable display text, rendered in the sidecar report UI.
- **Sidecar Response**: The structured object (answer, facts, citations, UI blocks, provenance) produced by the Catalyst gateway and consumed by both the sidecar UI and the harness adapter.
- **MCP FHIR Tool**: One of the new MCP tools (search_patient, get_patient_context, get_service_requests, get_observations, get_diagnostic_reports, get_resource_by_reference, build_patient_lab_timeline) that replace the current mocked schema tools as the FHIR data-access surface.
- **Gap-Log Entry**: A recorded divergence between OE2's HAPI and embedded FHIR surfaces for a specific resource, produced by the parity probe; filed for upstream OE2 follow-up rather than fixed inside this harness.
- **Harness Adapter Entrypoint (Catalyst)**: The Catalyst-specific implementation of the harness's existing adapter interface (established in feature 004) that lets a harness validation scenario drive Catalyst and record results on the shared metadata spine.

### Evidence, Provenance & Data Boundaries *(mandatory when clinical data, models, retrieval, mappings, or validation artifacts are involved)*

- **Clinical evidence records**: FHIR resources (`Patient`, `ServiceRequest`, `Observation`, `DiagnosticReport`, `Practitioner`, `Organization`) held in OE2's HAPI FHIR sidecar and embedded FHIR providers, backed by the shared `clinlims` PostgreSQL database. This feature does not create new clinical records; it reads existing OE2 demo/fixture data.
- **Decision rationale**: Each answer's citations are the decision rationale — a reviewer must be able to trace every claim in an answer back to the specific FHIR resource ID(s) that support it, via the evidence cards and debug drawer.
- **Operating metadata**: Run manifests and per-turn results on the harness's existing metadata spine (via the Story 3 adapter entrypoint); the gap-log entries produced by the Story 4 parity probe; sidecar response provenance (`fhir_surface`, `fhir_base_url`, `tools_called`, `resource_ids`) persisted with every answer.
- **Accepted deterministic inputs**: The five canonical questions and their required FHIR resource types (fixed, not expandable without a spec change); the MCP tool contract (FR-003); the sidecar response contract shape (FR-005).
- **Advisory inputs**: The LLM-generated answer text and fact summaries are advisory — they must be grounded by and traceable to the deterministic FHIR citations, and a citation that fails to resolve makes the associated claim untrusted.
- **PCCP/change record needs**: Expanding or altering the five canonical questions, changing which FHIR surface (HAPI vs embedded) is treated as primary, or promoting parity-probe gap-log entries into blocking failures are all material changes requiring a reviewed spec update, not a silent implementation change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer asking any of the five canonical questions about a patient with relevant OE2 data receives an answer where 100% of cited FHIR resource IDs resolve to real resources in OE2.
- **SC-002**: A reviewer asking any of the five canonical questions about a patient with no relevant OE2 data receives an explicit "no data found" response rather than a fabricated answer, 100% of the time.
- **SC-003**: A reviewer can identify the evidence behind any answer (which resources, what they show) using only the sidecar UI's evidence cards, lab-result table, and lab timeline, without needing to read raw FHIR JSON.
- **SC-004**: A harness operator can run at least one Catalyst validation scenario end-to-end through the harness adapter entrypoint and find a complete run manifest and result record afterward, using the same inspection workflow as an existing chartsearchai run.
- **SC-005**: The HAPI-FHIR parity probe completes a full pass over all five canonical questions' underlying resource reads and produces a gap-log entry for every detected divergence, with zero of those divergences causing the original embedded-grounded answer to be withdrawn or hidden.
- **SC-006**: A reviewer can open the debug drawer for any answer and see the exact MCP tool calls and FHIR queries that produced it, closing the loop between the answer panel and its underlying evidence.

## Assumptions

- OE2 is consumed as a sibling checkout (`../OpenELIS-Global-2` or `$OPENELIS_ROOT`/`$HARNESS_OE2_ROOT`), not a submodule, matching the existing convention used for feature 002's OpenELIS feasibility work; this has been verified working locally.
- The POC operates against OE2's demo/fixture data (synthetic patients and lab records), not real PHI; full "LocalPHI mode" hardening for real patient data in LLM context is explicitly deferred per the source brief and is out of scope here.
- **Corrected during planning, not merely assumed**: OE2's embedded FHIR provider (`/OpenELIS-Global/fhir/*`, HTTP Basic auth) is the primary data path for this POC, not the HAPI FHIR sidecar the source brief assumed. Direct verification found the HAPI sidecar's TLS listener requires a client certificate this POC does not provision (a hard block, not a missing-credential issue), while the embedded surface is reachable today with ordinary Basic auth once OE2's manual FHIR backfill (`GET /OpenELIS-Global/OEToFhir`) has run. Adding client-certificate handling for HAPI is out of scope and tracked as the Story 4 gap-log's primary finding instead. See `research.md` items 3 and 5.
- No additional authentication is added to OE2's HAPI FHIR sidecar for this POC; the dev container's existing lack of application-layer auth is accepted as a POC-only, non-PHI, localhost/dev-network condition. Hardening HAPI auth (including the client-certificate requirement above) is out of scope and tracked as an OE2-side follow-up.
- If the `Specimen` resource type is not reliably available via OE2's embedded FHIR providers, the gap is documented via User Story 4 and the five canonical questions proceed unmodified — none of the five require `Specimen` as a primary resource.
- **Verified local demo-data gap**: with the OE2 fixture data currently loaded (`load-test-fixtures.sh --profile=core`/`--profile=harness`), `Patient` and `Organization` resources sync to the embedded FHIR surface via the manual backfill trigger, but `ServiceRequest`/`Observation`/`DiagnosticReport` do not, despite real order (`analysis`) rows existing in `clinlims` — root-causing OE2's transform-eligibility rule for those resource types is OE2-side engineering and out of scope (source brief §11). Practically: this POC can be demonstrated fully for order-shaped questions (Q2, Q5) once that sync is unblocked by richer fixture data, and demonstrates the required abstention behavior (FR-008) today for result-shaped questions (Q1, Q3, Q4) rather than a fabricated answer.
- The roadmap lane and spec-directory naming for this feature use `catalyst` (project-naming) rather than `openelis` (host-context naming), consistent with the source brief's framing that Catalyst, not OE2, is the project being validated.
- Sidecar UI hosting technology (gateway-served HTMX vs. a separate frontend application) is an implementation decision for `/speckit-plan`, not this spec; either choice must satisfy FR-006/FR-007 and Story 2's acceptance scenarios.
- SQL execution, OE2 frontend/Carbon UI integration, Catalyst RBAC/audit Java backend integration, full OE2 FHIR sync/backfill engineering, and `openelis-catalyst` repository housekeeping remain out of scope for this POC, per source brief §11.
- The harness adapter entrypoint (Story 3) reuses the interface pattern established by feature 004 for chartsearchai; it does not require changes to harness-core beyond the Catalyst-specific adapter implementation.
- Evidence-card drill-down links back into OE2's legacy web UI when available, falling back to showing FHIR resource data alone when a legacy-UI deep link cannot be constructed; this default may be revisited in `/speckit-clarify` if it materially affects UI scope.
