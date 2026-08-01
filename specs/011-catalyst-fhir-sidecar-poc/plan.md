# Implementation Plan: Catalyst FHIR Sidecar POC

**Branch**: `011-catalyst-fhir-sidecar-poc` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-catalyst-fhir-sidecar-poc/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Give Catalyst (`targets/catalyst`, currently mocked/scaffolding) a real FHIR
data path against OpenELIS Global 2 (sibling checkout), answer the five
canonical lab questions from the source brief with citations that resolve
against live OE2 FHIR resources, render those answers through a gateway-served
Scout-style report UI, drive at least one question through the harness's
existing validate-run adapter interface (the `_Client` Protocol in
`harness/validate/runner.py`), and replay the same questions against OE2's
embedded FHIR providers to log HAPI/embedded divergence as a non-blocking gap
log. SQL execution, OE2 frontend integration, RBAC, and PHI-in-prompt hardening
stay out of scope per the source brief.

## Technical Context

**Language/Version**: Python 3.11 (Catalyst's three components: `catalyst-gateway`, `catalyst-agents`, `catalyst-mcp`, all already on this version per `targets/catalyst/.python-version`); Python 3.11 harness code (`harness/validate/`)

**Primary Dependencies**: FastAPI + uvicorn (gateway/agents/mcp, already in place); `httpx` (already a `catalyst-gateway` dependency, unused for FHIR today — this feature is its first real use); Jinja2 or equivalent server-side templating for the sidecar UI (new — see research.md item 4); `requests` (harness's existing HTTP client library, matching `ChartSearchAIClient`)

**Storage**: N/A for new storage — reads OE2's existing `clinlims` PostgreSQL via FHIR (not direct SQL, per research.md item 3); harness-side gap-log and validate-run artifacts use the existing `artifacts/<run_id>/` JSONL convention, no new store

**Testing**: pytest (matches `targets/catalyst/tests/` and `harness/` conventions); Catalyst's existing `tests/run_tests.sh` orchestrator extended with FHIR-tool and sidecar-response-contract tests; harness-side `evals/` pytest for the new `CatalystClient`

**Target Platform**: Local developer machine (macOS verified this session) and CI (Linux); no new deployment target

**Project Type**: Harness/control-plane feature extending an existing target (Catalyst) — Option 1 in the plan template, not a new web-application project

**Performance Goals**: No hard SLA — CPU-only local LLM inference is already known to take up to several minutes per multi-turn chartsearchai answer (see prior session evidence); FHIR reads themselves (deterministic, no LLM) are expected sub-second against OE2's local HAPI sidecar

**Constraints**: Fully offline-capable (local llama-router, no cloud API dependency, matching the project's stated goal for under-resourced-community deployability); OE2 consumed as a sibling checkout, never vendored/submoduled (spec Assumptions); no new client-certificate/mTLS handling built for the POC (research.md item 5 — documented as a gap instead)

**Scale/Scope**: 5 canonical questions, 7 new MCP tools, 1 new harness transport value + client, 1 gateway response-contract extension, 1 gateway-served UI (no separate frontend app) — a POC, not a production-scale build

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Real production paths**: PASS. Plan exercises OE2's real embedded FHIR provider (verified reachable and functional this session, after correcting the source brief's HAPI-first assumption — see research.md items 3 and 5) as the primary path; the existing mocked `get_query_context`/`validate_sql` tools remain but are explicitly labeled non-critical-path scaffolding (spec FR-015), not conflated with the new FHIR evidence.
- **Deterministic reviewed transforms**: PASS. The five canonical questions, the MCP tool contract, and the sidecar response contract are all fixed, reviewed artifacts in this plan (data-model.md, contracts/) — not left to model-output convention.
- **Record-level evidence**: PASS. Every answer's citations must resolve to a specific OE2 FHIR resource ID (FR-002); the sidecar response schema makes citation shape a hard contract, not prose.
- **Metadata and provenance**: PASS. `RunManifest.component` stays `"validate"` (hardcoded for every transport, not per-target — verified by running a real scenario, see data-model.md's corrected note) plus each result row's persisted `provenance` object (fhir_surface, fhir_base_url, tools_called, resource_ids) and `dataset_provenance.comparison_set` gives the same run-manifest/event-trace chain other targets already have; no new manifest schema needed.
- **Tests define behavior**: PASS (planned, not yet implemented — this is Phase 1 design, not Phase 2/3 code). `tasks.md` (next phase) must include: MCP FHIR tool tests against a fixture/live OE2, sidecar-response-schema validation tests, `CatalystClient` Protocol-conformance tests, and at least one abstention-path test (Edge Case: no data found) alongside the five happy-path questions — satisfying the constitution's scenario-diversity requirement, not just the tuning case.
- **Data boundaries and governance**: PASS. Clinical evidence (FHIR resources) stays in OE2; the harness only persists run metadata, results, and gap-log entries (data-model.md). No PCCP-style change record is needed for *this* plan since it establishes new capability rather than modifying an accepted model/prompt/mapping already in production — but any later change to the five canonical questions or to which FHIR surface is primary requires one (spec PCCP note).
- **Why this is sufficient**: The plan's evidence chain (resolvable FHIR citations → structured response contract → persisted run manifest/results → optional parity gap log) gives a reviewer everything needed to verify a Catalyst answer without trusting model prose: the same evidentiary bar chartsearchai's validate-run spine (feature 006) already established, extended to a second target rather than reinvented.

## Project Structure

### Documentation (this feature)

```text
specs/011-catalyst-fhir-sidecar-poc/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── sidecar_response.schema.json
│   ├── catalyst_mcp_tools.schema.yaml
│   └── catalyst_adapter_client.profile.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
# Harness side (this repo) — Option 1: Harness/control-plane feature
harness/
├── validate/
│   ├── models.py             # MODIFY: ComparisonSet.transport gains "catalyst"
│   ├── execution.py          # MODIFY: validate_execution_contract gains a catalyst branch
│   ├── runner.py             # UNCHANGED: _Client Protocol already generic
│   └── catalyst_client.py    # NEW: CatalystClient implementing _Client
├── adapters/
│   └── catalyst.py           # NEW (optional, non-critical-path): project-identity record, mirrors chartsearchai.py
└── targets.yaml               # MODIFY (implementation phase, not this plan): catalyst entry's evidence_status/validation_surface once real path lands

# Catalyst submodule (targets/catalyst, DIGI-UW/openelis-catalyst — changes land
# upstream in that repo, tracked here as the dependency this feature drives)
catalyst-mcp/
└── src/
    └── tools/
        └── fhir_tools.py      # NEW: the 7 FHIR MCP tools (contracts/catalyst_mcp_tools.schema.yaml)

catalyst-gateway/
└── src/
    ├── gateway.py             # MODIFY: extend /v1/chat/completions response with facts/citations/uiBlocks/provenance
    └── sidecar_ui/            # NEW: gateway-served HTML templates (research.md item 4)

catalyst-agents/
└── src/
    └── agents/
        └── catalyst_executor.py  # MODIFY: replace stub mcp_client.get_schema() bypass with real MCP protocol calls (brief M10-C)

# OE2 sibling checkout (../OpenELIS-Global-2) — not modified by this feature;
# read-only dependency. Any OE2-side gap (mTLS requirement, nginx /fhir
# routing) is filed upstream per research.md item 5, not patched here.

evals/ (or harness's existing test tree — exact location per project convention)
└── validate/
    └── test_catalyst_client.py   # NEW: Protocol-conformance + error-path tests
```

**Structure Decision**: This is a harness/control-plane feature (Option 1)
extending two existing codebases: the harness's `harness/validate/` module
(new transport + client, following the exact pattern already used for
`chartsearchai`/`med-agent-hub`) and the `targets/catalyst` submodule (new MCP
tools, extended gateway response, new gateway-served UI). No new top-level
project or separate frontend application is introduced (research.md item 4).

## Complexity Tracking

*No constitution gate failures requiring justification — table intentionally empty.*
