# Data Model: Harness Control Plane Foundation

## Entity: ValidationTarget

Represents one target project the harness can prepare, inspect, or validate.

### Fields

- `id`: Stable identifier. Initial values: `chartsearchai`, `querystore`, `openmrs_chatbot`, `catalyst`.
- `display_name`: Human-readable project name.
- `submodule_path`: Path under `targets/`.
- `submodule_url`: Absolute upstream repository URL from `.gitmodules`.
- `project_subpath`: Optional path within the submodule for targets that need it. Default is repository root.
- `environment_overrides`: Environment variable names that can redirect the target to a local checkout, e.g. `HARNESS_TARGET_CHARTSEARCHAI`.
- `validation_surface`: Target-owned command/API/workflow that must be exercised for evidence.
- `build_commands`: Target-owned build or dependency setup commands.
- `test_commands`: Target-owned smoke or validation commands.
- `required_services`: Shared services the target needs.
- `target_compose_files`: Compose files owned by the target repository.
- `shared_profiles`: Harness-owned shared infrastructure profiles compatible with the target.
- `evidence_status`: One of `release`, `development`, `fixture`, `scaffolding`, `unavailable`.
- `notes`: Short reviewer-facing explanation.

### Validation Rules

- `id` MUST be unique.
- `submodule_path` MUST be under `targets/`.
- `submodule_url` MUST be an absolute URL.
- `evidence_status=release` MUST require a real validation surface.
- Target overrides MUST NOT change the reviewed `submodule_path` or `submodule_url`.
- Catalyst MUST use `targets/catalyst` as its target path once extracted.

## Entity: TargetPin

Represents the reviewed git state for a target.

### Fields

- `target_id`: References `ValidationTarget.id`.
- `reviewed_sha`: Git SHA recorded by the parent repository gitlink.
- `branch_hint`: Optional upstream branch used for human review.
- `initialized`: Whether the working tree exists locally.
- `current_sha`: Actual checked-out SHA.
- `dirty`: Whether the target working tree has local changes.
- `override_active`: Whether `HARNESS_TARGET_<ID>` redirects the target.

### State Transitions

1. `missing`: submodule path absent or uninitialized.
2. `initialized`: submodule path exists at reviewed pin.
3. `drifted`: working tree SHA differs from reviewed pin.
4. `dirty`: working tree has uncommitted changes.
5. `override`: environment override is active.

## Entity: TargetMetadata

The reviewed contents of `harness/targets.yaml`.

### Fields

- `schema_version`: Metadata schema version.
- `targets`: List of `ValidationTarget` entries.
- `profiles`: List of `EnvironmentProfile` entries.
- `shared_infrastructure`: Harness-owned shared service definitions and compose-file references.

### Validation Rules

- Every `.gitmodules` target path used by this feature MUST have a corresponding `targets.yaml` entry.
- Every `targets.yaml` target intended for sync MUST have a matching `.gitmodules` entry unless explicitly marked `unavailable`.
- Every `required_services` value MUST resolve to either a shared infrastructure service or target-owned startup definition.

## Entity: EnvironmentProfile

Represents a named operating context such as local development or VM validation.

### Fields

- `id`: `local` or `vm` for M0.
- `description`: Human-readable purpose.
- `enabled_targets`: Target IDs enabled by default.
- `shared_compose_files`: Harness-owned compose files to include.
- `active_compose_profiles`: Docker Compose profile names to activate.
- `required_env`: Required environment variables.
- `artifact_root`: Output root for generated artifacts.
- `allows_overrides`: Whether target overrides are permitted.

### Validation Rules

- Profiles MUST identify output locations before evidence-producing runs.
- Profiles MUST list required credentials or secrets without storing secret values.
- VM profiles MUST use the same reviewed target pins as local profiles unless an override is explicitly recorded.

## Entity: ReadinessSummary

User-facing status for target/profile readiness.

### Fields

- `profile_id`: Selected environment profile.
- `target_id`: Target being checked.
- `status`: `ready`, `blocked`, `scaffolding_only`, `override`, or `unavailable`.
- `reasons`: List of missing prerequisites or warnings.
- `evidence_status`: Inherited target evidence status after checks.
- `target_sha`: Reviewed or override target SHA.
- `override_source`: Optional local path or fork URL.
- `decision_rationale`: Explanation of why the status was assigned.

### Validation Rules

- `status=ready` for release evidence MUST require initialized target pin, no unreviewed override, real validation surface, and required services available.
- `status=override` MUST include `override_source` and actual `target_sha`.
- `decision_rationale` is required for every non-ready status.

## Entity: RunManifestTargetProvenance

Target-specific provenance embedded into `run_manifest.json`.

### Fields

- `target_id`
- `target_source`: `reviewed_submodule` or `override`
- `target_path`
- `target_url`
- `target_reviewed_sha`
- `target_actual_sha`
- `target_dirty`
- `target_override`
- `target_override_source`
- `target_metadata_version`
- `evidence_status`
- `decision_rationale`

### Validation Rules

- Override runs MUST set `target_override=true`.
- Override runs MUST NOT be indistinguishable from reviewed-pin runs.
- Release evidence MUST use `target_source=reviewed_submodule` unless a reviewed change record explicitly promotes override evidence.

## Entity: OTelGenAIAlignment

Records the GenAI semantic convention version and field set used by emitted metadata.

### Fields

- `semconv_status`: `development` for current OTel GenAI conventions.
- `stability_opt_in`: Expected value `gen_ai_latest_experimental`.
- `provider_name`: Maps to `gen_ai.provider.name`.
- `operation_name`: Maps to `gen_ai.operation.name`.
- `agent_name`, `agent_id`, `agent_version`
- `tool_name`, `tool_call_id`, `tool_type`
- `data_source_id`

### Validation Rules

- New manifests MUST NOT emit `gen_ai.system`.
- If model or agent behavior is involved, `gen_ai.provider.name` and `gen_ai.operation.name` are required when available.
- Tool and MCP operations SHOULD include `gen_ai.tool.name` or `gen_ai.data_source.id` when instrumentable.
