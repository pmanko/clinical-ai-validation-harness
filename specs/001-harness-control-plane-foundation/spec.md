# Feature Specification: Harness Control Plane Foundation

**Feature Branch**: `001-harness-control-plane-foundation`

**Created**: 2026-05-12

**Status**: Draft

**Input**: User description: "001-harness-control-plane-foundation based on the roadmap and supporting documentation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register Validation Targets (Priority: P1)

A validation engineer can open the harness control plane and identify every supported target project, where it is expected to live, which validation surface it exposes, and whether it is ready to be exercised locally or in a VM environment.

**Why this priority**: The rest of the roadmap depends on stable assumptions about project locations, target components, and real validation paths. Without this registry, later OpenMRS, metadata, adapter, safety, and cross-project work would duplicate assumptions.

**Independent Test**: Can be fully tested by reviewing the control-plane registry for the initial target projects and confirming that each entry states its project identity, expected checkout or mount location, supported environments, evidence status, and validation surface.

**Acceptance Scenarios**:

1. **Given** a contributor has a fresh checkout of the harness, **When** they inspect the control-plane target list, **Then** they can identify `chartsearchai`, `querystore`, `openmrs_chatbot`, and Catalyst as distinct validation targets.
2. **Given** a target project entry exists, **When** a reviewer checks the entry, **Then** the entry states whether validation claims for that target must use a real project command or API, or whether the entry is still non-evidence scaffolding.
3. **Given** a target project is not available in the contributor's environment, **When** the contributor reviews its status, **Then** the harness clearly distinguishes "unavailable" from "validated" without implying evidence was produced.

---

### User Story 2 - Choose an Environment Profile (Priority: P2)

A contributor can choose between local and VM validation profiles and understand which assumptions change for project locations, service dependencies, credentials, and output locations before any validation run is treated as evidence.

**Why this priority**: The repository is intended to coordinate both local and VM-based validation. A shared profile model prevents downstream specs from hard-coding environment assumptions.

**Independent Test**: Can be fully tested by selecting each supported profile and confirming that the expected target locations, required services, required secrets or credentials, and artifact locations are visible before validation begins.

**Acceptance Scenarios**:

1. **Given** the contributor selects the local profile, **When** they review the readiness summary, **Then** the harness shows the local assumptions for target project locations and output locations.
2. **Given** the contributor selects the VM profile, **When** they review the readiness summary, **Then** the harness shows the VM assumptions for target project locations and output locations.
3. **Given** a required service or credential is missing, **When** the contributor reviews the selected profile, **Then** the harness reports the missing prerequisite without producing validation evidence.

---

### User Story 3 - Prepare Evidence Output Boundaries (Priority: P3)

A reviewer can determine where run outputs, traces, reports, and review records will be stored, which outputs are ignored generated artifacts, and which artifacts are curated as durable planning or fixture evidence.

**Why this priority**: Record-level evidence and metadata provenance are constitutional requirements. The control plane must establish output boundaries before downstream runs emit validation artifacts.

**Independent Test**: Can be fully tested by inspecting the control-plane output contract and confirming that it separates generated run outputs from curated spec artifacts and clinical evidence stores.

**Acceptance Scenarios**:

1. **Given** a validation run is prepared, **When** the reviewer checks the output contract, **Then** the expected run manifest, event trace, reports, and review records have a declared destination.
2. **Given** a run output is generated, **When** the reviewer checks whether it should be committed, **Then** the harness distinguishes ignored generated outputs from curated fixtures or durable spec artifacts.
3. **Given** a validation claim involves clinical data or model behavior, **When** evidence output is reviewed, **Then** the output boundary includes record-level evidence and decision rationale.

---

### Edge Cases

- A target project is missing, renamed, or located outside the expected sibling checkout path.
- A target project is present but its real validation surface is unavailable, unhealthy, or not yet documented.
- A contributor selects an environment profile that conflicts with available services or credentials.
- Multiple target projects require the same external service but with incompatible assumptions.
- A run is attempted before artifact destinations, metadata expectations, or evidence status are known.
- Non-evidence scaffolding is available for development, but no real-path validation run has been completed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define the initial validation targets as `chartsearchai`, `querystore`, `openmrs_chatbot`, and Catalyst.
- **FR-002**: Each validation target MUST include a human-readable project identity, expected checkout or mount assumption, supported environment profiles, and current readiness status.
- **FR-003**: Each validation target MUST state the real validation surface that must be exercised before downstream claims count as evidence.
- **FR-004**: The system MUST distinguish real-path validation readiness from development scaffolding, unavailable targets, and fixture-only states.
- **FR-005**: Users MUST be able to compare local and VM environment profiles before a validation run is treated as evidence.
- **FR-006**: Each environment profile MUST declare required target locations, required services, required credentials or secrets, and expected output locations.
- **FR-007**: The system MUST provide a readiness summary that identifies missing targets, missing services, missing credentials, and non-evidence states before validation begins.
- **FR-008**: The system MUST define artifact output boundaries for run manifests, event traces, reports, review records, curated fixtures, and durable spec artifacts.
- **FR-009**: The system MUST identify whether validation uses real project commands/APIs or non-evidence scaffolding.
- **FR-010**: The system MUST preserve record-level evidence for claims involving clinical data, mappings, retrieval, model responses, or reviewer decisions, including why the evidence supports the decision.
- **FR-011**: The system MUST emit or update versioned metadata/provenance artifacts when a run, transform, retrieval, model call, response, evaluation, or review record is produced.
- **FR-012**: The system MUST cover scenario diversity for validation behavior, including ambiguous, missing, unsupported, abstention, and failure cases when they are relevant to the target being validated.
- **FR-013**: The system MUST document which downstream roadmap features are unblocked by the control-plane foundation and which remain blocked until additional data, metadata, or adapter specs are complete.

### Key Entities

- **Validation Target**: A referenced project or component that the harness can prepare or validate; includes project identity, expected location, supported profiles, readiness status, and evidence status.
- **Environment Profile**: A named operating context such as local or VM validation; includes target-location assumptions, required services, required credentials, and output-location expectations.
- **Validation Surface**: The real command, workflow, user-visible behavior, or project-owned interface that must be exercised for evidence-producing validation.
- **Readiness Summary**: A user-facing assessment of whether a selected target and profile can produce evidence, require setup, or are limited to non-evidence scaffolding.
- **Artifact Boundary**: A declared separation between generated run outputs, curated fixtures, durable spec artifacts, and clinical evidence stores.
- **Evidence Status**: A classification that states whether an output is release evidence, development scaffolding, fixture-backed support, or unavailable.

### Evidence, Provenance & Data Boundaries *(mandatory when clinical data, models, retrieval, mappings, or validation artifacts are involved)*

- **Clinical evidence records**: This foundation does not create clinical evidence records itself, but it MUST declare how downstream features will keep clinical records in their source systems or fixture locations while storing run metadata and review artifacts separately.
- **Decision rationale**: Readiness and evidence-status decisions MUST explain why a target/profile can produce evidence, why it is blocked, or why it is limited to non-evidence scaffolding.
- **Operating metadata**: Prepared runs MUST have declared destinations for versioned run manifests, event traces, reports, readiness summaries, and review records.
- **Accepted deterministic inputs**: Accepted target definitions, environment profile definitions, artifact boundary rules, and evidence-status rules are binding control-plane inputs once reviewed.
- **Advisory inputs**: Roadmap notes, research canvases, handoff notes, and LLM-assisted analysis are advisory unless promoted into reviewed control-plane definitions.
- **PCCP/change record needs**: Changes to target evidence criteria, validation surfaces, artifact boundaries, or release-evidence status require governance review when they affect downstream clinical validation claims.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new contributor can identify all initial validation targets, their expected locations, and their evidence status in under 10 minutes using the control-plane documentation or readiness summary.
- **SC-002**: 100% of initial validation targets declare whether evidence requires a real project command/API, fixture-backed support, or non-evidence scaffolding.
- **SC-003**: 100% of supported environment profiles declare required target locations, required services, required credentials or secrets, and output-location expectations.
- **SC-004**: A reviewer can determine whether a prepared run is evidence-producing, blocked, or scaffolding-only without inspecting implementation internals.
- **SC-005**: At least one positive and one blocked-readiness scenario are covered for each supported environment profile.
- **SC-006**: No downstream feature spec needs to redefine target project identities, environment profile names, or baseline artifact boundary categories.

## Assumptions

- The first supported environment profiles are local development and VM-based validation.
- The initial target projects are the four projects named in the roadmap and README: `chartsearchai`, `querystore`, `openmrs_chatbot`, and Catalyst.
- This feature establishes the control-plane contract and readiness model; it does not itself complete OpenMRS demo-data remap, metadata schema implementation, real adapter execution, or retrieval evaluation.
- Fixture-backed and scaffolding-only states are allowed for development when clearly labelled, but they do not count as release validation evidence.
- The canonical constitution remains `.specify/memory/constitution.md`, and the roadmap remains `specs/roadmap.canvas.tsx`.
