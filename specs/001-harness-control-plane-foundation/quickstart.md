# Quickstart: Harness Control Plane Foundation

This quickstart describes the intended M0 workflow after implementation.

## 1. Install the harness

```bash
uv python install 3.11
uv sync --extra dev
```

## 2. Initialize target repositories

Use the harness workflow instead of remembering raw submodule commands:

```bash
harness-cli targets sync
```

For CI or a VM where shallow target clones are preferred:

```bash
harness-cli targets sync --depth 1
```

To preview commands without mutating the checkout:

```bash
harness-cli targets sync --plan
```

## 3. Inspect configured targets

```bash
harness-cli targets list
```

The initial target list is:

- `chartsearchai`
- `querystore`
- `openmrs_chatbot`
- `catalyst`

Each target reports its submodule path, validation surface, supported profiles, and evidence status.

## 4. Check readiness

Local profile:

```bash
harness-cli targets status --profile local
```

VM profile:

```bash
harness-cli targets status --profile vm
```

Readiness output must distinguish:

- `ready`: reviewed target pin is initialized and required prerequisites are available.
- `blocked`: prerequisites are missing.
- `scaffolding_only`: target is present but does not yet produce release evidence.
- `override`: a `HARNESS_TARGET_<ID>` override is active.
- `unavailable`: target cannot currently be materialized or checked.

## 5. Use a local target override for development

Overrides point a target at an active local checkout or fork without changing the reviewed submodule pin.

```bash
export HARNESS_TARGET_CHARTSEARCHAI=../openmrs-module-chartsearchai
harness-cli targets status --profile local --target chartsearchai
```

Any run produced with an active override must record:

- `target_override: true`
- override source path or URL
- actual target SHA
- evidence status and decision rationale

Override runs are development conveniences and cannot count as release evidence without a reviewed change record.

## 6. Plan Compose startup

```bash
harness-cli profiles compose-plan --profile local
```

The compose plan should identify:

- Harness-owned shared infrastructure compose files, such as OpenMRS/MySQL, Elasticsearch, and OTel.
- Target-owned compose files that remain inside pinned target repositories.
- Docker Compose profiles required for opt-in services.

## 7. Run existing smoke commands

Existing commands remain available:

```bash
harness-cli schema-diff
harness-cli import-smoke
```

Generated run artifacts go under `artifacts/` and include `run_manifest.json` and `events.jsonl` where applicable.

## 8. Verify before task completion

```bash
uv run pytest
```

The test suite should cover:

- Target metadata validation.
- Submodule sync command planning.
- Readiness status classification.
- Override provenance in manifests.
- Current OTel GenAI field names.
- Shared-infrastructure vs target-owned compose ownership.
