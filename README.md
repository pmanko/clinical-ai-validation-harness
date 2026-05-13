# clinical-ai-validation-harness

Umbrella validation and orchestration harness for early clinical AI systems:

- `chartsearchai`
- `querystore`
- `openmrs_chatbot`
- `Catalyst` (OpenELIS)

The repository is intended to coordinate local and VM-based setup, testing, and validation across the referenced projects. The first implementation slice is the OpenMRS demo-data remap/import because it provides a realistic clinical corpus and concrete validation target for `chartsearchai` and `querystore`.

## Scope and Principles

The canonical constitution is `.specify/memory/constitution.md`.

- Run real production paths, not test-only simulations.
- Keep clinical evidence stores separate from operating metadata.
- Treat LLM mapping output as advisory only.
- Promote only reviewed mappings into deterministic scripts.
- Use run manifests and event traces for every run.
- Preserve record-level evidence and rationale for validation claims.
- Cover diverse validation scenarios, not only the narrow case used to tune a
  prompt, mapping, or adapter.
- Use PCCP-style review records for material model, prompt, retrieval, mapping,
  or pipeline changes.

## Repository Layout

- `docs/`: user-facing documentation only.
- `specs/`: roadmap, milestone specs, feature planning docs, and research artifacts.
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

This repo is initialized with GitHub Spec Kit `v0.8.9` using multi-agent integrations:

- Spec Kit config: `.specify/`
- Cursor skills: `.cursor/skills/`
- Cursor rule: `.cursor/rules/specify-rules.mdc`
- Claude skills: `.claude/skills/`
- Claude guidance: `CLAUDE.md`
- Agent guidance: `AGENTS.md`

Useful Spec Kit skills:

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
- retain durable copies of research canvases in `specs/artifacts/`.

## Notes

- Expected legacy source: `/Users/pmanko/code/openmrs-module-chartsearchai/data/large-demo-data-2-7-0.sql`.
- Querystore repository is expected as sibling checkout:
  - `/Users/pmanko/code/openmrs-module-querystore`
