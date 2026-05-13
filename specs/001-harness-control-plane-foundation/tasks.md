# Tasks: Harness Control Plane Foundation

**Input**: Design documents from `/specs/001-harness-control-plane-foundation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required for behavioral changes by the constitution and plan. Test tasks below should be written before the implementation tasks in the same phase and should fail before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or only reads shared files
- **[Story]**: Maps to user stories from `spec.md`
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish repo-level Python/dev workflow and target-repository scaffolding needed before control-plane code.

- [ ] T001 Verify the `uv` development workflow runs `make validate-plan` and `uv run pytest` successfully using `.python-version`, `uv.lock`, `Makefile`, and `pyproject.toml`
- [ ] T002 [P] Create the ignored target submodule root placeholder in `targets/.gitkeep`
- [ ] T003 Add reviewed absolute submodule entries for `chartsearchai`, `querystore`, and `openmrs_chatbot` in `.gitmodules` using `https://github.com/openmrs/openmrs-module-chartsearchai.git`, `https://github.com/openmrs/openmrs-module-querystore.git`, and `https://github.com/anichiti/openmrs_chatbot.git`
- [ ] T004 Document Catalyst as `evidence_status: unavailable` in `.gitmodules` review notes by leaving `targets/catalyst` unpinned until a standalone extracted Catalyst repository URL exists
- [ ] T005 [P] Create target registry test directory scaffolding in `evals/target_registry/.gitkeep`
- [ ] T006 [P] Create orchestration test directory scaffolding in `evals/orchestration/.gitkeep`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared target/config/metadata primitives that block every user story.

**Critical**: No user story work should begin until this phase is complete.

- [ ] T007 [P] Add target metadata schema fixture expectations in `evals/target_registry/test_targets_yaml_contract.py`
- [ ] T008 [P] Add submodule status command-planning tests in `evals/target_registry/test_submodule_plans.py`
- [ ] T009 [P] Add current OTel GenAI manifest field tests in `evals/metadata/test_run_manifest_control_plane.py`
- [ ] T010 Create reviewed initial target metadata in `harness/targets.yaml` covering `chartsearchai`, `querystore`, `openmrs_chatbot`, and Catalyst with `evidence_status: unavailable`, plus minimal `local` and `vm` profile stubs and shared infrastructure references so the file validates against `specs/001-harness-control-plane-foundation/contracts/targets.schema.yaml` from creation
- [ ] T011 Implement target metadata dataclasses, YAML loading, and schema validation in `harness/targets.py`
- [ ] T012 Implement submodule command planning and status models in `harness/submodules.py`
- [ ] T012a [P] Add required-services conflict detection tests for incompatible target service assumptions in `evals/orchestration/test_required_services_conflicts.py`
- [ ] T012b [P] Add compose-conflict detection tests for clashing service names, ports, credentials, or volumes between target-owned and harness-owned compose files in `evals/orchestration/test_compose_conflicts.py`
- [ ] T012c Implement required-services and compose-conflict detection in `harness/targets.py` and `harness/compose.py`
- [ ] T013 Implement harness root, artifact root, and target metadata loading in `harness/config.py`
- [ ] T014 Update run manifest dataclass fields for `evidence_status`, target provenance, and current OTel GenAI attributes in `harness/metadata.py`
- [ ] T015 Update existing `schema-diff` and `import-smoke` manifest creation to use `gen_ai.provider.name` instead of `gen_ai.system` in `harness/cli.py`
- [ ] T016 Run foundational tests with `uv run pytest evals/target_registry evals/orchestration evals/metadata` and fix failures in `harness/targets.py`, `harness/submodules.py`, `harness/config.py`, `harness/metadata.py`, and `harness/compose.py`

**Checkpoint**: Target metadata, submodule planning, conflict detection primitives, and metadata primitives are ready for story work.

---

## Phase 3: User Story 1 - Register Validation Targets (Priority: P1) MVP

**Goal**: A validation engineer can identify every supported target project, its pinned repository location, validation surface, and evidence/readiness status.

**Independent Test**: `uv run harness-cli targets list --format json` and `uv run harness-cli targets status --profile local --format json` show the four initial targets with submodule path, supported profiles, validation surface, evidence status, and decision rationale where blocked or unavailable.

### Tests for User Story 1

- [ ] T017 [P] [US1] Add contract tests for `harness-cli targets list --format json` in `evals/target_registry/test_targets_cli.py`
- [ ] T018 [P] [US1] Add readiness classification tests for missing, initialized, drifted, dirty, and `evidence_status: unavailable` targets in `evals/target_registry/test_readiness_summary.py`
- [ ] T019 [P] [US1] Add target override detection tests for `HARNESS_TARGET_<ID>` variables in `evals/target_registry/test_target_overrides.py`
- [ ] T020 [P] [US1] Add `targets sync --plan` tests for recursive submodule commands and optional `--depth` in `evals/target_registry/test_targets_sync_cli.py`

### Implementation for User Story 1

- [ ] T021 [P] [US1] Implement `ValidationTarget`, `TargetPin`, `TargetOverride`, and `ReadinessSummary` behavior in `harness/targets.py`
- [ ] T022 [P] [US1] Implement gitlink SHA, working-tree SHA, dirty-state, and override status detection in `harness/submodules.py`
- [ ] T023 [US1] Implement `targets list`, `targets status`, and `targets sync` parser branches in `harness/cli.py`
- [ ] T024 [US1] Implement text and JSON serializers for target lists and readiness summaries in `harness/targets.py`
- [ ] T025 [US1] Add `openmrs_chatbot` command-plan adapter stub that documents the unavailable real validation surface in `harness/adapters/openmrs_chatbot.py`
- [ ] T026 [US1] Add `catalyst` command-plan adapter stub that documents the extracted-standalone target boundary and reports `evidence_status: unavailable` before submodule pinning in `harness/adapters/catalyst.py`
- [ ] T027 [US1] Update adapter command-plan tests for `openmrs_chatbot` and `catalyst` in `evals/indexing/test_adapter_command_plans.py`
- [ ] T028 [US1] Run `uv run pytest evals/target_registry evals/indexing` and fix target registration failures in `harness/cli.py`, `harness/targets.py`, `harness/submodules.py`, and `harness/adapters/`

**Checkpoint**: User Story 1 is independently functional and provides the MVP target registry/readiness surface.

---

## Phase 4: User Story 2 - Choose an Environment Profile (Priority: P2)

**Goal**: A contributor can compare local and VM profiles, including target locations, service dependencies, credentials, compose ownership, and output locations before evidence is produced.

**Independent Test**: `uv run harness-cli profiles list --format json` and `uv run harness-cli profiles compose-plan --profile local --format json` show local/VM profile assumptions, harness-owned shared compose files, target-owned compose references, required environment variables, and artifact roots without starting services.

### Tests for User Story 2

- [ ] T029 [P] [US2] Add environment profile schema and fixture tests in `evals/orchestration/test_environment_profiles.py`
- [ ] T030 [P] [US2] Add compose ownership tests for harness-owned shared infrastructure and target-owned compose files in `evals/orchestration/test_compose_plan.py`
- [ ] T031 [P] [US2] Add CLI contract tests for `profiles list` and `profiles compose-plan`, including at least one positive readiness scenario per supported profile, in `evals/orchestration/test_profiles_cli.py`
- [ ] T032 [P] [US2] Add blocked-readiness tests for missing required services or credentials in `evals/orchestration/test_profile_readiness.py`

### Implementation for User Story 2

- [ ] T033 [P] [US2] Expand local and VM environment profile entries with artifact roots, shared compose files, and required environment variables in `harness/targets.yaml`
- [ ] T034 [P] [US2] Add Docker Compose `profiles:` to opt-in shared services in `compose/services.yml`
- [ ] T035 [P] [US2] Add Docker Compose `profiles:` to opt-in OpenMRS/MySQL shared services in `compose/openmrs-2.8-refapp.yml`
- [ ] T036 [US2] Implement `EnvironmentProfile` loading and validation in `harness/targets.py`
- [ ] T037 [US2] Implement shared-infrastructure and target-owned compose planning in `harness/compose.py`
- [ ] T038 [US2] Implement `profiles list` and `profiles compose-plan` parser branches in `harness/cli.py`
- [ ] T039 [US2] Integrate profile service/credential checks into readiness summaries in `harness/targets.py`
- [ ] T040 [US2] Run `uv run pytest evals/orchestration evals/target_registry` and fix environment profile failures in `harness/targets.py`, `harness/compose.py`, `harness/cli.py`, and `compose/`

**Checkpoint**: User Story 2 is independently functional and can explain local/VM profile readiness without launching services.

---

## Phase 5: User Story 3 - Prepare Evidence Output Boundaries (Priority: P3)

**Goal**: A reviewer can determine where run outputs, traces, reports, review records, generated artifacts, curated fixtures, and durable spec artifacts belong.

**Independent Test**: Existing and new manifest-producing commands emit versioned metadata with evidence status, target provenance when relevant, current OTel GenAI fields, and clear output destinations under ignored artifact roots.

### Tests for User Story 3

- [ ] T041 [P] [US3] Add manifest override provenance tests covering `target_override`, override source, actual SHA, and non-release evidence status in `evals/metadata/test_target_override_manifest.py`
- [ ] T042 [P] [US3] Add artifact boundary tests for generated outputs versus curated fixtures and spec artifacts in `evals/metadata/test_artifact_boundaries.py`
- [ ] T043 [P] [US3] Add tests preventing `otel.gen_ai.system` from appearing in generated manifests in `evals/metadata/test_run_manifest_control_plane.py`
- [ ] T044 [P] [US3] Add readiness decision-rationale event tests in `evals/metadata/test_readiness_events.py`

### Implementation for User Story 3

- [ ] T045 [P] [US3] Add artifact boundary constants and helper functions in `harness/artifacts.py`
- [ ] T046 [US3] Add target provenance construction helpers in `harness/metadata.py`
- [ ] T047 [US3] Emit readiness summary events with decision rationale in `harness/cli.py`
- [ ] T048 [US3] Update `schema-diff` and `import-smoke` output manifests to include evidence status and current OTel GenAI fields in `harness/cli.py`
- [ ] T049 [US3] Update user-facing quickstart and milestone notes for target sync, profile checks, and artifact boundaries in `README.md`
- [ ] T050 [US3] Run `uv run pytest evals/metadata evals/dataset_import` and fix evidence-boundary failures in `harness/metadata.py`, `harness/artifacts.py`, and `harness/cli.py`

**Checkpoint**: User Story 3 is independently functional and run artifacts are distinguishable from curated specs/fixtures.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete M0 control plane and align documentation, contracts, and governance notes.

- [ ] T051 [P] Update control-plane quickstart examples after implementation in `specs/001-harness-control-plane-foundation/quickstart.md`, ensuring downstream specs reference `harness/targets.yaml`, environment profile names, and artifact boundary categories instead of redefining baseline identities (SC-006)
- [ ] T052 [P] Update metadata planning notes for current OTel GenAI fields and target provenance in `specs/artifacts/planning/metadata-schema.md`
- [ ] T053 [P] Update adapter README files with target-owned validation surface status in `adapters/chartsearchai/README.md`, `adapters/querystore/README.md`, `adapters/openmrs_chatbot/README.md`, and `adapters/catalyst/README.md`
- [ ] T054 [P] Update `specs/roadmap.canvas.tsx` with M0 control-plane foundation status and an explicit list of downstream roadmap features unblocked versus still blocked by this milestone
- [ ] T054a [P] Document downstream features unblocked by the M0 control-plane foundation in `specs/artifacts/handoffs/control-plane-foundation-unblocking.md`
- [ ] T055 Review all readiness and manifest tests for narrow overfit to one fixture in `evals/target_registry/`, `evals/orchestration/`, and `evals/metadata/`
- [ ] T056 Run full validation with `make validate-plan`, `uv run pytest`, `uv run harness-cli targets list`, `uv run harness-cli targets status --profile local`, and `uv run harness-cli profiles compose-plan --profile local`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2. This is the MVP.
- **Phase 4 US2**: Depends on Phase 2 and can run alongside US1 after shared target metadata exists.
- **Phase 5 US3**: Depends on Phase 2 and can run alongside US1/US2 after metadata primitives exist.
- **Phase 6 Polish**: Depends on the selected user stories being complete.

### User Story Dependencies

- **US1 Register Validation Targets**: Requires foundational metadata/submodule primitives only.
- **US2 Choose an Environment Profile**: Requires foundational target/profile schema; integrates with US1 readiness summaries but remains independently testable through `profiles` commands.
- **US3 Prepare Evidence Output Boundaries**: Requires foundational metadata manifest primitives; can be tested with existing `schema-diff` and `import-smoke` commands.

### Within Each User Story

- Write and run the story's tests first.
- Implement models/config loaders before CLI branches.
- Implement CLI JSON output before text polish.
- Run the story-specific pytest command before moving to another story.

## Parallel Opportunities

- T005 and T006 can run with T003/T004 because they create separate test directories.
- T007, T008, T009, T012a, and T012b can be written in parallel before foundational implementation (T012c consumes those tests).
- US1 tests T017-T020 can be written in parallel.
- US2 tests T029-T032 can be written in parallel.
- US2 compose file edits T034 and T035 can be done in parallel with T033.
- US3 tests T041-T044 can be written in parallel.
- Polish docs T051-T054 and T054a can be done in parallel after behavior stabilizes.

## Parallel Example: User Story 1

```bash
# Parallel test-writing work:
Task: "T017 Add contract tests for harness-cli targets list --format json in evals/target_registry/test_targets_cli.py"
Task: "T018 Add readiness classification tests in evals/target_registry/test_readiness_summary.py"
Task: "T019 Add target override detection tests in evals/target_registry/test_target_overrides.py"
Task: "T020 Add targets sync --plan tests in evals/target_registry/test_targets_sync_cli.py"

# Parallel implementation work after foundational models exist:
Task: "T021 Implement target/readiness behavior in harness/targets.py"
Task: "T022 Implement submodule status detection in harness/submodules.py"
Task: "T025 Add openmrs_chatbot adapter stub in harness/adapters/openmrs_chatbot.py"
Task: "T026 Add catalyst adapter stub in harness/adapters/catalyst.py"
```

## Parallel Example: User Story 2

```bash
# Parallel test-writing work:
Task: "T029 Add environment profile schema tests in evals/orchestration/test_environment_profiles.py"
Task: "T030 Add compose ownership tests in evals/orchestration/test_compose_plan.py"
Task: "T031 Add profiles CLI contract tests in evals/orchestration/test_profiles_cli.py"
Task: "T032 Add blocked-readiness tests in evals/orchestration/test_profile_readiness.py"
```

## Parallel Example: User Story 3

```bash
# Parallel test-writing work:
Task: "T041 Add manifest override provenance tests in evals/metadata/test_target_override_manifest.py"
Task: "T042 Add artifact boundary tests in evals/metadata/test_artifact_boundaries.py"
Task: "T043 Add tests preventing otel.gen_ai.system in evals/metadata/test_run_manifest_control_plane.py"
Task: "T044 Add readiness decision-rationale event tests in evals/metadata/test_readiness_events.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational primitives and tests.
3. Complete Phase 3 US1.
4. Stop and validate `uv run pytest evals/target_registry evals/indexing`.
5. Demo `uv run harness-cli targets list --format json` and `uv run harness-cli targets status --profile local --format json`.

### Incremental Delivery

1. Setup + Foundational: `targets.yaml`, metadata model, submodule planning, manifest field shape.
2. US1: target registry/readiness/sync MVP.
3. US2: environment profiles and compose planning.
4. US3: artifact boundaries and manifest provenance.
5. Polish: docs, metadata notes, adapter READMEs, roadmap status, full validation.

### Notes

- Commit after each phase or independently testable story.
- Do not treat Catalyst as release evidence until a standalone extracted repository is pinned.
- Do not promote any override run as release evidence without a reviewed change record.
- Keep target-owned app Compose definitions in target repositories; harness Compose files are shared infrastructure only.
