# Research: Harness Control Plane Foundation

## Decision: Use Git submodules for target repositories

**Decision**: Pin target repositories as Git submodules under `targets/<id>`.

**Rationale**: Submodules preserve the boundary between the harness and the real upstream projects while giving every validation run an auditable target SHA. This aligns with the constitution's real-path and reproducibility requirements. A submodule pin is reviewable in a PR and easy to record in `run_manifest.json`.

**Alternatives considered**:

- **Git subtrees**: Rejected because they vendor upstream project code into the harness, blur ownership boundaries, increase repository size, and make validated upstream SHAs harder to read from run metadata.
- **Sibling checkouts only**: Rejected because absolute paths are not reproducible across contributors or VMs and do not provide a reviewed default pin.
- **On-demand clone without submodule**: Rejected because a clone script would need its own lockfile and review model duplicating Git's submodule behavior.

## Decision: Add `harness/targets.yaml`

**Decision**: Keep `.gitmodules` for repository URLs and paths, and add `harness/targets.yaml` for target metadata that Git cannot express.

**Rationale**: `.gitmodules` does not carry validation surfaces, required services, evidence status, environment override names, optional compose overlays, or readiness labels. A small YAML file lets the harness produce readiness summaries and contracts without scattering this metadata across adapter code and README files.

**Alternatives considered**:

- **`.gitmodules` only**: Rejected because it cannot support readiness or evidence classification.
- **Python-only registry**: Rejected because target metadata should be reviewable by non-Python contributors and not require code edits for path or evidence-status changes.
- **Large declarative orchestration file**: Rejected for M0 because Compose and target adapters already own most service and command behavior.

## Decision: Extract Catalyst as a standalone target

**Decision**: Treat Catalyst as an extracted standalone repository pinned at `targets/catalyst`. Its current M0 evidence scope is the Python gateway/agent/MCP stack and tests; future OpenELIS Java/frontend integration remains a separate dependency boundary.

**Rationale**: Ground-truth review of `/Users/pmanko/code/OpenELIS-Global-2/projects/catalyst` shows a self-contained Python project with `README.md`, `.python-version`, `env.recommended`, `Procfile.dev`, `catalyst-dev.docker-compose.yml`, three component `pyproject.toml` files, `uv.lock` files, tests, and a path-scoped CI workflow. The OpenELIS Java/frontend/config integration paths named in the README do not currently exist locally and are better modeled as future integration dependencies.

**Alternatives considered**:

- **Full OpenELIS submodule**: Rejected for M0 because it pulls a large repository for a currently self-contained Catalyst Python target.
- **Sparse checkout of OpenELIS**: Rejected because sparse submodule management adds complexity and fragile checkout behavior.
- **Metadata placeholder only**: Rejected because the extracted repository path is now the intended target shape and can be represented directly.

## Decision: Provide `targets sync` with override support

**Decision**: Add a harness-level target synchronization workflow that runs explicit submodule initialization and supports per-target `HARNESS_TARGET_<ID>` overrides.

**Rationale**: Contributors and VMs should not need to remember raw submodule commands. A harness command can initialize reviewed pins, report status, and show when overrides are active. Overrides enable fork/local development while preserving reviewed submodule pins as the default evidence source.

**Alternatives considered**:

- **Manual Git commands only**: Rejected because empty submodule directories are a common failure mode and undermine readiness checks.
- **Auto-sync during every status check**: Rejected because status should be read-only and must not mutate the checkout unexpectedly.
- **No sync in M0**: Rejected because downstream specs depend on stable target materialization.

## Decision: Harden submodules for CI and VM environments

**Decision**: Use absolute URLs in `.gitmodules` and initialize with `git submodule update --init --recursive`; CI/VM workflows may use `--depth 1` for speed.

**Rationale**: Current Git and CI guidance recommends explicit recursive submodule initialization in every CI run. Absolute URLs reduce CI ambiguity. Shallow submodule clones preserve pinned-SHA reproducibility while limiting clone time.

**Alternatives considered**:

- **Relative URLs**: Rejected because fork/CI remotes can resolve unexpectedly.
- **Implicit clone behavior**: Rejected because fresh clones often omit submodule content.
- **Always full history**: Rejected because target repositories may be large and M0 only needs pinned working trees.

## Decision: Keep target-owned Compose in target repositories

**Decision**: Harness-owned Compose files are for shared infrastructure; target app services stay in target repositories. Harness profiles can reference target-owned compose files or commands when orchestrating a shared environment.

**Rationale**: Target repos own their app-specific service definitions and should not be duplicated in the harness. Docker Compose profiles are the right mechanism for opt-in services, and multi-file compose merges are appropriate for shared-infra plus target-owned overlays.

**Alternatives considered**:

- **Centralize all compose files in harness**: Rejected because it creates stale duplicates and weakens target ownership.
- **Target-owned only**: Rejected because shared services such as OpenMRS, MySQL, Elasticsearch, and OTel are needed by multiple validation lanes.
- **Defer compose orchestration**: Rejected because environment profiles are core to M0 readiness.

## Decision: Align to current OTel GenAI Development conventions

**Decision**: The control-plane metadata contract aligns to the current OpenTelemetry GenAI Development-status conventions, including `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`, `gen_ai.provider.name`, `gen_ai.operation.name`, `gen_ai.agent.*`, `gen_ai.tool.*`, and `gen_ai.data_source.id`.

**Rationale**: OpenTelemetry GenAI conventions are not stable as of 2026-05-12. Current guidance indicates existing v1.36.0-era instrumentation should not silently change default output and should opt into latest experimental conventions. The existing harness metadata uses `gen_ai.system`, which should be updated under this feature so future metadata work starts on current names.

**Alternatives considered**:

- **Keep `gen_ai.system`**: Rejected because it reflects older convention names and would cause drift with current planning.
- **Wait for stable conventions**: Rejected because the harness needs a known metadata direction now; the plan records the development status explicitly.
- **Use only custom harness fields**: Rejected because the constitution asks for OTel GenAI alignment where practical.

## Decision: Override runs are development evidence only unless reviewed

**Decision**: Run manifests emitted while a `HARNESS_TARGET_<ID>` override is active must record `target_override: true`, the override source path or fork URL, and the actual target SHA. Override runs cannot count as release evidence without a reviewed change record.

**Rationale**: Overrides are useful for active development, but they bypass reviewed submodule pins. Explicit manifest fields prevent fork/local runs from being indistinguishable from reviewed-pin runs.

**Alternatives considered**:

- **Disallow overrides**: Rejected because active development and fork testing are important for a bridge harness.
- **Allow overrides without manifest changes**: Rejected because it breaks provenance and could promote unreviewed code as release evidence.
- **Treat every override as release evidence if tests pass**: Rejected because passing tests alone do not satisfy governance review of target-version changes.
