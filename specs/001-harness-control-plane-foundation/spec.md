# Feature Specification: Harness Control Plane Foundation

**Feature Branch**: `001-harness-control-plane-foundation`

**Created**: 2026-05-12

**Status**: Complete (M0 — harness control plane shipped; foundation for all downstream features)

**Input**: User description: "001-harness-control-plane-foundation based on the roadmap and supporting documentation."

## Clarifications

### Session 2026-05-12

- Q: Which target repository layout should this spec lock in for the control plane? → A: Use pinned Git submodules under `targets/<id>` plus a lightweight `harness/targets.yaml` for target metadata that `.gitmodules` cannot carry.
- Q: What repository shape should the Catalyst target use? → A: Catalyst is intended as a standalone extracted repository at `targets/catalyst`; until extraction lands it MUST appear in `harness/targets.yaml` with `evidence_status: unavailable` and without a `.gitmodules` entry; future OpenELIS Java/frontend integration remains a separate dependency boundary.
- Q: How should contributors and VM environments materialize pinned target repositories while allowing local forks? → A: Provide a harness-level `targets sync` workflow that initializes pinned submodules by default, with `HARNESS_TARGET_<ID>` environment overrides for forks or active local clones.
- Q: How should Compose ownership work across the harness and target repositories? → A: Target-owned Compose files remain in target repositories by default, while the harness owns and orchestrates shared infrastructure Compose files when multiple targets need common services.
- Q: What OTel GenAI conventions should the control plane align to? → A: Align to the current Development-status OTel GenAI conventions (post-v1.36.0) using `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`, not the old `gen_ai.system` field; use `gen_ai.provider.name` and the full current attribute set; note that stable status has not yet been reached.
- Q: How should the harness handle CI and VM submodule initialization? → A: Use `git submodule update --init --recursive` with optional `--depth 1` shallow clones for CI and VM speed; use absolute URLs in `.gitmodules`; `targets sync` must initialize submodules explicitly rather than relying on implicit clone behavior.
- Q: How should run manifests distinguish override/fork runs from reviewed-pin runs? → A: Run manifests for override runs MUST record `target_override: true`, the local path or fork URL, and the actual target SHA used; override runs are development conveniences and MUST NOT be promoted as release evidence without a reviewed change record.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register Validation Targets (Priority: P1)

A validation engineer can open the harness control plane and identify every supported target project, where its pinned target repository lives under `targets/`, which validation surface it exposes, and whether it is ready to be exercised locally or in a VM environment.

**Why this priority**: The rest of the roadmap depends on stable assumptions about project locations, target components, and real validation paths. Without this registry, later OpenMRS, metadata, adapter, safety, and cross-project work would duplicate assumptions.

**Independent Test**: Can be fully tested by reviewing `.gitmodules`, `targets/`, and `harness/targets.yaml` for the initial target projects and confirming that each entry states its project identity, pinned repository location, supported environments, evidence status, and validation surface.

**Acceptance Scenarios**:

1. **Given** a contributor has a fresh checkout of the harness, **When** they inspect the control-plane target list, **Then** they can identify `chartsearchai`, `querystore`, `openmrs_chatbot`, and Catalyst as distinct validation targets with declared submodule paths or explicit unavailable status where no submodule pin exists yet.
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

- A target repository submodule is missing, uninitialized, renamed, or checked out at a different commit than the reviewed pin.
- The Catalyst standalone target is not yet available or is out of sync with the extracted upstream repository expected at `targets/catalyst`.
- A target project is present but its real validation surface is unavailable, unhealthy, or not yet documented.
- A contributor selects an environment profile that conflicts with available services or credentials.
- Multiple target projects require the same external service but with incompatible assumptions.
- A target-owned Compose file and a harness shared-infrastructure Compose file define conflicting service names, ports, credentials, or volumes.
- A contributor activates a Compose profile that depends on an opt-in service that has not been started or is not available in the current environment.
- A run is attempted before artifact destinations, metadata expectations, or evidence status are known.
- Non-evidence scaffolding is available for development, but no real-path validation run has been completed.
- A run manifest emitted during a target override run is mistakenly treated as release evidence; the `target_override` field is missing or was not checked before promotion.
- A CI or VM environment fails to initialize submodules explicitly, resulting in empty `targets/` directories and silent build failures.
- An OTel GenAI attribute name from the v1.36.0 era is emitted into an event trace while later downstream tooling expects the current `gen_ai.provider.name` form.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define the initial validation targets as `chartsearchai`, `querystore`, `openmrs_chatbot`, and Catalyst.
- **FR-002**: Each validation target MUST include a human-readable project identity, pinned target repository path, supported environment profiles, and current readiness status.
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
- **FR-014**: The system MUST treat target repositories as pinned Git submodules under `targets/`, with submodule changes reviewed as explicit target-version changes.
- **FR-015**: The system MUST maintain lightweight target metadata in `harness/targets.yaml` for information not represented by `.gitmodules`, including target identity, target path, validation surface, required services, optional compose overlays, environment overrides, and evidence status.
- **FR-016**: The system MUST treat Catalyst as the intended standalone extracted target at `targets/catalyst`. Until the standalone Catalyst repository is extracted and pinned, Catalyst MUST be represented in `harness/targets.yaml` with `evidence_status: unavailable` and without a `.gitmodules` entry; future OpenELIS Java/frontend integration remains a separate dependency boundary rather than as part of the M0 target pin.
- **FR-017**: The system MUST provide a target synchronization workflow that initializes reviewed submodule pins for all enabled targets without requiring contributors to remember raw Git submodule commands.
- **FR-018**: The system MUST support per-target environment overrides for active development or fork testing without changing reviewed submodule pins.
- **FR-019**: The system MUST treat target-owned Compose files as the default source for target-specific app services and MUST NOT duplicate those service definitions in the harness unless the harness is intentionally providing shared infrastructure.
- **FR-020**: The system MUST allow harness environment profiles to orchestrate shared infrastructure Compose files when multiple targets require common services, while preserving target-owned startup definitions for target-specific services.
- **FR-021**: The system MUST use Docker Compose `profiles:` to mark opt-in services so environment-specific services such as LM Studio, Gemini-proxy, or a target-specific model provider are only started when the corresponding profile is active.
- **FR-022**: The system MUST use absolute URLs in `.gitmodules` and MUST initialize target submodules explicitly via `git submodule update --init --recursive` (with optional `--depth 1` for CI and VM speed) rather than relying on implicit clone behavior.
- **FR-023**: Run manifests produced while a `HARNESS_TARGET_<ID>` override is active MUST record `target_override: true`, the override source path or fork URL, and the actual target git SHA used; these runs MUST NOT be promoted as release evidence without a reviewed change record.
- **FR-024**: The control-plane metadata contract MUST align to the current OTel GenAI conventions (`OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` era) and MUST use `gen_ai.provider.name` instead of the deprecated `gen_ai.system` field; agent and tool spans MUST use `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.operation.name`, and `gen_ai.tool.name` where applicable.

### Key Entities

- **Validation Target**: A referenced project or component that the harness can prepare or validate; includes project identity, pinned repository path, supported profiles, readiness status, and evidence status.
- **Target Metadata**: Reviewed metadata in `harness/targets.yaml` that describes each target's validation surface, required services, optional compose overlays, environment override name, and evidence status.
- **Catalyst Target**: The intended standalone Catalyst repository at `targets/catalyst`; until extraction and submodule pinning land, control-plane metadata MUST carry `evidence_status: unavailable`. Once pinned, evidence scope covers the Catalyst Python gateway, agent, MCP, tests, and dev services, with OpenELIS Java/frontend integration tracked separately.
- **Target Override**: A per-target environment setting that points a harness target at an alternate local checkout for active development while preserving the reviewed submodule pin as the default evidence source.
- **Shared Infrastructure Profile**: A harness-owned environment profile that starts common services such as OpenMRS, MySQL, Elasticsearch, OpenTelemetry, or model-provider dependencies needed by more than one target; uses Docker Compose `profiles:` to keep opt-in services inactive by default.
- **Target-Owned Compose**: A Compose file maintained inside a pinned target repository and used by the harness as the source of truth for that target's app-specific service startup.
- **Override Run**: A run produced while a `HARNESS_TARGET_<ID>` environment override is active; emits `target_override: true` in its manifest, records the override source and actual SHA, and cannot count as release evidence without a reviewed change record.
- **OTel GenAI Alignment**: Metadata emitted by the harness aligns to the current Development-status OTel GenAI conventions (`gen_ai.provider.name`, `gen_ai.operation.name`, `gen_ai.agent.name/id/version`, `gen_ai.tool.name`, `gen_ai.data_source.id`) rather than the v1.36.0 `gen_ai.system` field; MCP spans from targets are included where instrumentable.
- **Environment Profile**: A named operating context such as local or VM validation; includes target-location assumptions, required services, required credentials, and output-location expectations.
- **Validation Surface**: The real command, workflow, user-visible behavior, or project-owned interface that must be exercised for evidence-producing validation.
- **Readiness Summary**: A user-facing assessment of whether a selected target and profile can produce evidence, require setup, or are limited to non-evidence scaffolding.
- **Artifact Boundary**: A declared separation between generated run outputs, curated fixtures, durable spec artifacts, and clinical evidence stores.
- **Evidence Status**: A classification that states whether an output is release evidence, development scaffolding, fixture-backed support, or unavailable.

### Evidence, Provenance & Data Boundaries *(mandatory when clinical data, models, retrieval, mappings, or validation artifacts are involved)*

- **Clinical evidence records**: This foundation does not create clinical evidence records itself, but it MUST declare how downstream features will keep clinical records in their source systems or fixture locations while storing run metadata and review artifacts separately.
- **Decision rationale**: Readiness and evidence-status decisions MUST explain why a target/profile can produce evidence, why it is blocked, or why it is limited to non-evidence scaffolding.
- **Operating metadata**: Prepared runs MUST have declared destinations for versioned run manifests, event traces, reports, readiness summaries, and review records. Override runs MUST additionally record `target_override: true`, override source, and actual target SHA.
- **Accepted deterministic inputs**: `.gitmodules`, pinned target submodule SHAs, accepted target metadata, environment profile definitions, artifact boundary rules, evidence-status rules, and the OTel GenAI attribute version in use are binding control-plane inputs once reviewed.
- **Advisory inputs**: Roadmap notes, research canvases, handoff notes, and LLM-assisted analysis are advisory unless promoted into reviewed control-plane definitions.
- **PCCP/change record needs**: Changes to target evidence criteria, validation surfaces, artifact boundaries, or release-evidence status require governance review when they affect downstream clinical validation claims. Promotion of override-run evidence to release evidence requires a reviewed change record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new contributor can identify all initial validation targets, their pinned repository locations or declared unavailable submodule paths, and their evidence status in under 10 minutes using the control-plane documentation or readiness summary.
- **SC-002**: 100% of initial validation targets declare whether evidence requires a real project command/API, fixture-backed support, or non-evidence scaffolding.
- **SC-003**: 100% of supported environment profiles declare required target locations, required services, required credentials or secrets, and output-location expectations.
- **SC-004**: A reviewer can determine whether a prepared run is evidence-producing, blocked, or scaffolding-only without inspecting implementation internals.
- **SC-005**: At least one positive and one blocked-readiness scenario are covered for each supported environment profile.
- **SC-006**: No downstream feature spec needs to redefine target project identities, environment profile names, or baseline artifact boundary categories.
- **SC-007**: Catalyst readiness clearly states whether the standalone `targets/catalyst` repository is unavailable, initialized at the reviewed pin once pinned, or blocked for another declared reason, and whether any OpenELIS Java/frontend integration dependency remains outside the current evidence scope.
- **SC-008**: A contributor can materialize all enabled pinned target repositories through one documented harness workflow and can identify any active target override in the readiness summary.
- **SC-009**: A reviewer can identify, for each environment profile, which services are harness-owned shared infrastructure and which services come from target-owned startup definitions.
- **SC-010**: 100% of run manifests emitted during a target override run include `target_override: true`, the override source, and the actual target SHA; zero override-run manifests are indistinguishable from reviewed-pin run manifests.
- **SC-011**: CI and VM submodule initialization follows the explicit `git submodule update --init --recursive` pattern; zero CI runs produce empty `targets/` directories due to missing submodule initialization.
- **SC-012**: Harness run manifests use `gen_ai.provider.name` and current OTel GenAI attribute names, not the deprecated `gen_ai.system` field from v1.36.0.

## Assumptions

- The first supported environment profiles are local development and VM-based validation.
- The initial target projects are the four projects named in the roadmap and README: `chartsearchai`, `querystore`, `openmrs_chatbot`, and Catalyst.
- Target repositories are managed as Git submodules beneath `targets/`, while `harness/targets.yaml` carries control-plane metadata not expressible in `.gitmodules`; `.gitmodules` must use absolute URLs for CI/VM reliability.
- The default evidence source for a target is the reviewed submodule pin; local or fork overrides are development conveniences and must be flagged in run manifests with `target_override: true`.
- Catalyst is expected to become a standalone extracted repository and be pinned under `targets/catalyst`; the prior `OpenELIS-Global-2/projects/catalyst` location is treated as the extraction source, not the long-term harness target path.
- Harness-owned Compose files are intended for shared infrastructure; Docker Compose `profiles:` handles opt-in environment-specific services; target-owned app services remain in pinned target repositories.
- The harness metadata schema targets the current OTel GenAI Development-status conventions rather than the v1.36.0 era fields; `gen_ai.system` is replaced by `gen_ai.provider.name`; stable OTel GenAI status has not yet been reached as of 2026-05-12.
- This feature establishes the control-plane contract and readiness model; it does not itself complete OpenMRS demo-data remap, metadata schema implementation, real adapter execution, or retrieval evaluation.
- Fixture-backed and scaffolding-only states are allowed for development when clearly labelled, but they do not count as release validation evidence.
- The canonical constitution remains `.specify/memory/constitution.md`, and the roadmap remains `specs/roadmap.canvas.tsx`.
