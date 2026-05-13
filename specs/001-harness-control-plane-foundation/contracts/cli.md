# CLI Contract: Harness Control Plane Foundation

The existing `harness-cli schema-diff` and `harness-cli import-smoke` commands remain available. This feature adds target and profile commands for M0 readiness.

## `harness-cli targets list`

Lists reviewed target metadata.

### Options

- `--format text|json`: Output format. Default: `text`.

### Required Behavior

- Reads `harness/targets.yaml`.
- Shows target id, display name, submodule path, supported profiles, validation surface, and evidence status.
- Does not mutate the working tree.

## `harness-cli targets status`

Reports readiness for selected targets and profile.

### Options

- `--profile local|vm`: Environment profile. Default: `local`.
- `--target <id>`: Repeatable target filter. If omitted, checks all enabled targets for the profile.
- `--format text|json`: Output format. Default: `text`.

### Required Behavior

- Reads `.gitmodules`, submodule gitlink state, `harness/targets.yaml`, and active `HARNESS_TARGET_<ID>` overrides.
- Classifies each target as `ready`, `blocked`, `scaffolding_only`, `override`, or `unavailable`.
- Includes decision rationale for blocked, scaffolding-only, override, or unavailable status.
- Identifies whether services come from harness-owned shared infrastructure or target-owned startup definitions.
- Does not start services and does not run target validation commands.

## `harness-cli targets sync`

Initializes reviewed target submodule pins.

### Options

- `--target <id>`: Repeatable target filter. If omitted, syncs all enabled targets.
- `--depth <n>`: Optional shallow clone depth for CI/VM speed.
- `--plan`: Print Git commands without executing them.

### Required Behavior

- Plans or runs explicit `git submodule update --init --recursive` commands.
- Uses `--depth <n>` when provided.
- Does not alter `HARNESS_TARGET_<ID>` override paths.
- Reports missing `.gitmodules` entries as blocked setup, not validation evidence.

## `harness-cli profiles list`

Lists environment profiles.

### Options

- `--format text|json`: Output format. Default: `text`.

### Required Behavior

- Shows required target locations, shared compose files, active Compose profiles, required environment variables, and artifact root.
- Does not start services.

## `harness-cli profiles compose-plan`

Prints the Docker Compose files and profiles required for a selected environment profile.

### Options

- `--profile local|vm`: Environment profile. Default: `local`.
- `--target <id>`: Repeatable target filter.
- `--format text|json`: Output format. Default: `text`.

### Required Behavior

- Includes harness-owned compose files for shared infrastructure.
- Includes target-owned compose files only from initialized target repositories or clearly marks them unavailable.
- Uses Docker Compose profiles for opt-in services.
- Does not duplicate target app service definitions in harness-owned compose output.

## Existing Run Commands

Existing commands that create `run_manifest.json` MUST preserve their current behavior while moving new metadata toward the control-plane manifest contract:

- `schema-diff`
- `import-smoke`

### Required Manifest Additions

- Harness `git_sha` when available.
- `evidence_status`.
- Current OTel GenAI fields under `otel`.
- Target provenance whenever a target is involved.
- Override source and actual target SHA when `HARNESS_TARGET_<ID>` is active.
