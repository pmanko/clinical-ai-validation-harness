# openmrs-ai-validation-harness

Standalone cross-project validation harness for early clinical AI systems:

- `chartsearchai`
- `querystore`
- `openmrs_chatbot`
- `Catalyst` (OpenELIS)

The first milestone in this repository is OpenMRS-specific: deterministic remap/import of `large-demo-data-2-7-0.sql` into an OpenMRS 2.8 Ref App-compatible candidate database, then validation through real `chartsearchai` and `querystore` paths.

## Scope and Principles

- Run real production paths, not test-only simulations.
- Keep clinical evidence stores separate from operating metadata.
- Treat LLM mapping output as advisory only.
- Promote only reviewed mappings into deterministic scripts.
- Use run manifests and event traces for every run.

## Repository Layout

- `docs/`: architecture, governance, mapping notes, metadata schema, canvases.
- `compose/`: OpenMRS/MySQL and optional service stack compose files.
- `datasets/`: source pointers, mapping specs, deterministic transforms, fixtures.
- `harness/`: Python orchestration package and CLI.
- `adapters/`: wrappers/contracts for project-specific validation integration.
- `evals/`: pytest suites for import, indexing, retrieval, metadata checks.
- `artifacts/`: output folder for run manifests, JSONL events, and reports.

## Quickstart

1. Create a Python 3.11+ environment.
2. Install package and dev dependencies:
   - `pip install -e .[dev]`
3. Prepare stack:
   - `docker compose -f compose/openmrs-2.8-refapp.yml up -d`
4. Run a schema diff:
   - `harness-cli schema-diff --output-dir artifacts/schema-diff`
5. Run smoke tests:
   - `pytest evals/dataset_import evals/metadata`

## Spec Kit

This repo is initialized with GitHub Spec Kit `v0.8.9` using the Cursor Agent integration:

- Spec Kit config: `.specify/`
- Cursor skills: `.cursor/skills/`
- Cursor rule: `.cursor/rules/specify-rules.mdc`
- Agent guidance: `AGENTS.md`

Useful Cursor Agent skills:

- `/speckit-constitution`
- `/speckit-specify`
- `/speckit-clarify`
- `/speckit-plan`
- `/speckit-tasks`
- `/speckit-analyze`
- `/speckit-implement`

## Milestone 1 Contract

Milestone 1 is complete when the harness can:

- compare legacy source schema vs clean Ref App 2.8 schema,
- produce reviewable mapping artifacts,
- run deterministic transforms repeatedly from scratch,
- validate OpenMRS startup + API readability + core table sanity,
- run chartsearchai/querystore adapter entrypoints,
- emit `run_manifest.json` + `events.jsonl` for each run,
- retain durable copies of research canvases in `docs/canvases/`.

## Notes

- Expected legacy source: `/Users/pmanko/code/openmrs-module-chartsearchai/data/large-demo-data-2-7-0.sql`.
- Querystore repository is expected as sibling checkout:
  - `/Users/pmanko/code/openmrs-module-querystore`
