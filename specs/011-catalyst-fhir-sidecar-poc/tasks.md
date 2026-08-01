# Tasks: Catalyst FHIR Sidecar POC

**Input**: Design documents from `/specs/011-catalyst-fhir-sidecar-poc/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: Required — constitution Principle V (Tests Define Behavior) makes this a hard MUST, not optional, for every behavioral task below.

**Primary FHIR surface note**: All tasks reference OE2's **embedded** FHIR provider (`/OpenELIS-Global/fhir/*`, HTTP Basic auth) as the working primary path — corrected from the source brief's HAPI-first assumption during planning (see research.md items 3 and 5, spec.md Assumptions). The HAPI sidecar is the Story 4 parity-probe target, not the answer path.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup

**Status**: Already verified working locally this session (quickstart.md §1–4). Listed for completeness/traceability; do not re-run if the environment is already in the state quickstart.md describes.

- [x] T001 Verify `targets/catalyst` submodule initialized at pinned SHA (`git submodule status`)
- [x] T002 [P] Verify OE2 sibling checkout at `../OpenELIS-Global-2` with `docker compose up -d` running, port `18443` remap applied in `docker-compose.yml` (host `8443` already owned by the harness's own proxy)
- [x] T003 [P] Load OE2 fixture data: `./src/test/resources/load-test-fixtures.sh --profile=harness` (supersedes `--profile=core` — includes `analysis`/order rows needed for US1's Q2/Q5)
- [x] T004 [P] Verify `targets/catalyst/.env` configured with `LMSTUDIO_BASE_URL=http://localhost:8077/v1`, `LMSTUDIO_MODEL=gemma-e4b`; Python deps installed for all 3 components (`uv sync --extra dev`); llama-router running

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 [P] Trigger OE2's FHIR backfill (`GET /OpenELIS-Global/OEToFhir`, Basic auth `admin:adminADMIN!`) and confirm via `GET .../fhir/Patient` that all 3 fixture patients are visible with `total: 3` — this is an operational precondition every US1+ task depends on, not application code
- [x] T006 [P] Add FHIR client config to `targets/catalyst/catalyst-mcp/src/config.py`: `load_fhir_config()` reading `OE2_FHIR_BASE_URL`, `OE2_FHIR_USERNAME`, `OE2_FHIR_USERNAME`, `OE2_FHIR_TIMEOUT_S` from env (mirrors the existing `load_database_config()` pattern); add corresponding vars to `targets/catalyst/env.recommended`
- [x] T007 [P] Create the shared sidecar response model in `targets/catalyst/catalyst-gateway/src/models.py` (NEW): dataclasses/Pydantic models for `Citation`, `Fact`, `LabResultRow`, `LabTimelineEvent`, `UiBlock`, `Provenance`, `SidecarResponse`, matching `contracts/sidecar_response.schema.json` field-for-field
- [ ] T008 Add `"catalyst"` as a third accepted value to `ComparisonSet.transport` in `harness/validate/models.py` (currently `{"chartsearchai", "med-agent-hub"}`)
- [ ] T009 Add a `catalyst` branch to `validate_execution_contract` in `harness/validate/execution.py`, rejecting Catalyst backends that set `provider` (a chartsearchai-only concept), mirroring the existing `med-agent-hub` branch

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Ask the Five Canonical Lab Questions (Priority: P1) 🎯 MVP

**Goal**: Answer all five canonical questions with citations that resolve against real OE2 embedded-FHIR resources; abstain honestly when no relevant data exists.

**Independent Test**: Ask each of the five canonical questions against a fixture patient (`E2E-PAT-001`/`002`/`003`) and confirm citation resource IDs resolve against OE2's embedded FHIR endpoint, or an explicit no-data response for questions touching resource types not yet synced (see Setup/data-gap note in spec.md Assumptions).

### Tests for User Story 1 (write first; must fail before implementation)

- [x] T010 [P] [US1] MCP FHIR tool tests for all 7 tools (`search_patient`, `get_patient_context`, `get_service_requests`, `get_observations`, `get_diagnostic_reports`, `get_resource_by_reference`, `build_patient_lab_timeline`) against the live local OE2 embedded FHIR endpoint in `targets/catalyst/catalyst-mcp/tests/test_fhir_tools.py` — cover found, not-found, and surface-unreachable cases per `contracts/catalyst_mcp_tools.schema.yaml`'s `error_handling` section
- [x] T011 [P] [US1] Contract test: a real `catalyst-gateway` response for a grounded question validates against `contracts/sidecar_response.schema.json` in `targets/catalyst/catalyst-gateway/tests/test_sidecar_response_contract.py`
- [x] T012 [P] [US1] Ambiguous-patient test: a name matching multiple patients returns all matches, does not silently pick one, in `targets/catalyst/catalyst-mcp/tests/test_fhir_tools.py` (same file as T010, distinct test)
- [x] T013 [P] [US1] Abstention test: a question about a resource type with zero synced data (e.g. `Observation` today, per the documented data gap) produces an explicit no-data answer with empty `citations[]`, not a fabricated one, in `targets/catalyst/catalyst-agents/tests/test_fhir_grounding.py`
- [x] T014 [P] [US1] Citation-resolvability test: every citation in a generated answer is independently re-fetched and confirmed to resolve, in `targets/catalyst/catalyst-agents/tests/test_fhir_grounding.py` (same file as T013, distinct test)

### Implementation for User Story 1

- [x] T015 [US1] Implement the 7 FHIR MCP tools in `targets/catalyst/catalyst-mcp/src/tools/fhir_tools.py` per `contracts/catalyst_mcp_tools.schema.yaml`, using the FHIR client config from T006 (depends on T006, T010)
- [x] T016 [US1] Register the new FHIR tools with the MCP server in `targets/catalyst/catalyst-mcp/src/server.py`, alongside (not replacing) the existing mocked `get_query_context`/`validate_sql` tools (depends on T015)
- [x] T017 [US1] Replace `catalyst_executor.py`'s stub `mcp_client.get_schema()` bypass with real MCP protocol tool calls in `targets/catalyst/catalyst-agents/src/agents/catalyst_executor.py` (brief M10-C; depends on T016) — also fixed `schema_executor.py`'s sync call to the same stub, out of scope but broken by the same rewrite
- [x] T018 [US1] Extend `catalyst-gateway`'s `/v1/chat/completions` response building to populate `facts`/`citations`/`uiBlocks`/`provenance` using the T007 models, in `targets/catalyst/catalyst-gateway/src/gateway.py` (depends on T007, T017) — implemented in `a2a_client.py`'s `send_chat_completion` (parses the JSON artifact and merges fields), not `gateway.py` itself, which stayed a thin passthrough
- [x] T019 [US1] Add citation-resolvability verification in the agent layer: before including a citation, re-resolve it against the FHIR surface (fail closed — drop the claim rather than cite an unverified ID) in `targets/catalyst/catalyst-agents/src/agents/catalyst_executor.py` (depends on T017) — implemented in `fhir_grounding.py`: citations are only ever built from resources actually returned by an MCP tool call, never LLM-proposed, so there is nothing to re-resolve after the fact
- [x] T020 [US1] Add abstention handling: when no relevant FHIR data is found for a question, produce the explicit no-data response shape (empty `citations`, explanatory `answer`) rather than an unconstrained LLM answer, in `targets/catalyst/catalyst-agents/src/agents/catalyst_executor.py` (depends on T017) — implemented in `fhir_grounding._no_data_response`, which also preserves real `tools_called`/`resource_ids` provenance (a bug caught and fixed during testing)
- [x] T021 [US1] Add decision-rationale linkage: each `facts[].source_ref` is set from the actual FHIR resource the fact was extracted from (not inferred after the fact) in `targets/catalyst/catalyst-agents/src/agents/catalyst_executor.py` (depends on T017) — implemented in `fhir_grounding.py`'s `_add_observation`/`_add_service_request`/`_add_diagnostic_report` helpers

**Verified**: all 66 tests across catalyst-mcp/catalyst-gateway/catalyst-agents pass (`./tests/run_tests.sh all`); full real HTTP -> A2A -> MCP protocol -> live OE2 FHIR round trip manually verified for grounded-order, abstention, and order-linked paths.

**Checkpoint**: User Story 1 fully functional and independently testable — this is the MVP.

---

## Phase 4: User Story 2 - Review Answers Through the Sidecar Report UI (Priority: P2)

**Goal**: Render Story 1's answers as evidence cards, a lab-result table, a lab timeline, and a debug drawer — not bare chat text.

**Independent Test**: Ask a canonical question and confirm the rendered page shows grouped evidence cards, a populated lab-result table when `Observation` data exists, a chronological timeline, and an on-demand debug drawer showing tool calls.

### Tests for User Story 2

- [ ] T022 [P] [US2] UI rendering test: given a fixture `SidecarResponse`, the rendered page contains one evidence-card group per cited resource type, correct lab-result table rows, and chronological timeline ordering, in `targets/catalyst/catalyst-gateway/tests/test_sidecar_ui.py`
- [ ] T023 [P] [US2] Debug-drawer test: a pure-abstention response (zero tool calls) renders the drawer without erroring, in `targets/catalyst/catalyst-gateway/tests/test_sidecar_ui.py` (same file as T022, distinct test)

### Implementation for User Story 2

- [ ] T024 [P] [US2] Create gateway-served Jinja2 templates (answer panel, evidence cards, lab-result table, lab timeline, debug drawer) in `targets/catalyst/catalyst-gateway/src/sidecar_ui/templates/`
- [ ] T025 [US2] Add `GET /sidecar` (question form) and `POST /sidecar/ask` (renders the answer) routes in `targets/catalyst/catalyst-gateway/src/gateway.py` (depends on T018, T024)
- [ ] T026 [US2] Wire the debug drawer to `provenance.tools_called` / `provenance.resource_ids` from the `SidecarResponse` (depends on T024, T025)

**Checkpoint**: Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Run the POC Through the Harness's Adapter Interface (Priority: P3)

**Goal**: Drive a canonical question through the harness's existing validate-run machinery and get a standard run manifest + result record.

**Independent Test**: Run `harness-cli validate run 011-catalyst-poc` and confirm `artifacts/<run_id>/run_manifest.json` (`component: "catalyst"`) and `results.jsonl` exist with the full sidecar response envelope persisted.

### Tests for User Story 3

- [ ] T027 [P] [US3] `_Client` Protocol-conformance test for `CatalystClient` (mocked HTTP) in `evals/validate/test_catalyst_client.py`
- [ ] T028 [P] [US3] Metadata/provenance test: a real (or fixture-backed) run produces `run_manifest.json` with `component="catalyst"` and `results.jsonl` rows carrying `citations`/`uiBlocks`/`provenance`, in `evals/validate/test_catalyst_client.py` (same file as T027, distinct test)

### Implementation for User Story 3

- [ ] T029 [P] [US3] Implement `CatalystClient` in `harness/validate/catalyst_client.py` per `contracts/catalyst_adapter_client.profile.md` (depends on T008, T009, T018 — needs the real gateway response shape to parse)
- [ ] T030 [P] [US3] Add `harness/adapters/catalyst.py` project-identity record, mirroring `harness/adapters/chartsearchai.py` (non-critical-path, for consistency)
- [ ] T031 [US3] Add a `catalyst` entry to `datasets/validation/backends.json` (`endpointUrl: http://localhost:8000/v1/chat/completions`, `modelName: "catalyst"`) and author one scenario in `datasets/validation/scenarios/catalyst-lab-questions.json` covering the five canonical questions against the fixture patients, plus a comparison set `datasets/validation/comparison_sets/011-catalyst-poc.json` (`transport: "catalyst"`) (depends on T029)
- [ ] T032 [US3] Run `harness-cli validate run 011-catalyst-poc` end-to-end against the live local stack and confirm the manifest/results shape (depends on T031)

**Checkpoint**: Stories 1–3 all work independently.

---

## Phase 6: User Story 4 - Surface HAPI/Embedded FHIR Divergence as a Gap Log (Priority: P4)

**Goal**: Replay the five canonical questions' FHIR reads against the HAPI sidecar and log divergence from the embedded-grounded answers, without blocking them.

**Independent Test**: Run the parity probe and confirm it produces a gap-log entry for the (currently expected) HAPI-unreachable case, without altering or hiding any Story 1 answer.

### Tests for User Story 4

- [ ] T033 [P] [US4] Gap-log entry test: an unreachable HAPI surface (the current, verified real state) produces one non-blocking gap-log entry per resource read, and a reachable-but-differing resource produces a divergence entry with both surfaces' status, in `targets/catalyst/catalyst-mcp/tests/test_parity_probe.py`

### Implementation for User Story 4

- [ ] T034 [US4] Implement the parity probe (replays the five canonical questions' underlying FHIR reads against HAPI, compares to the embedded-surface result, writes `artifacts/<run_id>/catalyst_gap_log.jsonl` per the Gap-Log Entry shape in data-model.md) in `targets/catalyst/catalyst-mcp/src/tools/parity_probe.py` (depends on T015, T033)
- [ ] T035 [US4] Run the parity probe against the live local stack and confirm it records the real HAPI mTLS-unreachable gap without touching Story 1's answers (depends on T034)

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T036 [P] Update `harness/targets.yaml`'s `catalyst` entry: `evidence_status` from `scaffolding` to reflect the real FHIR path now exercised, `validation_surface.kind` from `unavailable`, per research.md item 6 (depends on all of US1–US3 being real)
- [ ] T037 [P] Update `adapters/catalyst/README.md` from placeholder to describe the real adapter (per brief §13, "placeholder, updated in Phase 3")
- [ ] T038 [P] Update `specs/artifacts/lanes/L5-catalyst-fhir-sidecar.md` and `specs/artifacts/lanes/dev-roadmap.md` lane status from "Queued" to reflect implementation progress
- [ ] T039 [P] Run `quickstart.md` end-to-end from a clean state and fix any drift between the doc and actual behavior
- [ ] T040 Review the five canonical questions' test coverage for overfitting to a single fixture patient; ensure at least 2 of the 3 fixture patients are exercised across the test suite
- [ ] T041 [P] File the HAPI mTLS requirement and the ServiceRequest/Observation FHIR-sync gap as upstream OE2 issues (or as entries in the paired canvas's gap log), per brief §11's "filed upstream from the M10-F gap log" convention

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Already complete (verified this session)
- **Foundational (Phase 2)**: Blocks all user stories; T005 (FHIR backfill) blocks T010/T011/T012/T013/T014 (all US1 tests need real synced data to test against); T006 blocks T015; T007 blocks T018
- **User Stories (Phase 3–6)**: US1 is the MVP and has no dependency on US2–US4. US2 depends on US1's response shape (T018) existing. US3 depends on US1's response shape (T018) for `CatalystClient` to parse. US4 depends on US1's MCP tool implementation (T015) to know what to replay.
- **Polish (Phase 7)**: Depends on desired stories being complete; T036 specifically depends on US1–US3.

### Parallel Opportunities

- T002, T003, T004 (Setup) — different concerns, already done
- T005, T006, T007 (Foundational) — different files
- T008, T009 (Foundational, harness side) — sequential within the same file area but independent of T005–T007
- All Phase 3 test tasks (T010–T014) in parallel; T010/T012 share a file (sequential within it), T011 and T013/T014 are separate files
- T027/T028 (US3 tests, same file — sequential within it) can run parallel to US2's tests

---

## Parallel Example: User Story 1 tests

```bash
Task: "MCP FHIR tool tests in targets/catalyst/catalyst-mcp/tests/test_fhir_tools.py"
Task: "Contract test in targets/catalyst/catalyst-gateway/tests/test_sidecar_response_contract.py"
Task: "Abstention + citation-resolvability tests in targets/catalyst/catalyst-agents/tests/test_fhir_grounding.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (already done) → Phase 2 Foundational → Phase 3 US1
2. **STOP and VALIDATE**: ask all five canonical questions against the live local stack; confirm 2 abstain honestly (data gap) and up to 2 answer with real, resolvable citations (order-shaped questions, once T003's richer fixtures are loaded)
3. This alone proves the FHIR-first reboot works end-to-end against a real system — the brief's core ask

### Incremental Delivery

1. Foundational → US1 (MVP: grounded answers + honest abstention)
2. US2 (make answers reviewable, not just correct)
3. US3 (prove harness reusability — the "second target through the same control plane" thesis)
4. US4 (diagnostic gap log — valuable but correctly last)
5. Polish (update the stale `harness/targets.yaml` scaffolding metadata now that it's false)
