# AGENTS.md

Guidance for AI agents and contributors working in this repository.

## Project Purpose

This is a standalone validation harness for early clinical AI prototypes across OpenMRS and OpenELIS work. The first milestone is a deterministic OpenMRS 2.8 Ref App-compatible remap/import path for `large-demo-data-2-7-0.sql`, followed by validation through real `chartsearchai` and `querystore` paths.

## Operating Principles

- Treat `.specify/memory/constitution.md` as the canonical governance source;
  keep this file, README, user-facing docs, and specs aligned when the constitution changes.
- Use real production paths for validation; do not simulate chartsearchai, querystore, OpenMRS, or Catalyst behavior when the real path can be exercised.
- Treat LLM-assisted mapping as advisory analysis only. Accepted mappings must live in reviewed config and deterministic scripts.
- Preserve record-level evidence and decision rationale. Do not claim a filter, mapping, retrieval result, or answer is correct from counts alone.
- Include diverse validation scenarios so tests do not only prove the exact case used to tune a prompt, mapping, adapter, or fixture.
- Keep clinical evidence data separate from operating metadata. Query Store/CQRS is for searchable clinical records; this harness stores run, trace, response, evaluation, and review metadata.
- Prefer small, reviewable changes that preserve reproducibility.

## Testing Expectations

- Add or update tests when implementing behavior.
- Do not weaken tests to match broken behavior.
- Smoke tests should grow from placeholders into real OpenMRS startup, REST/API readability, schema integrity, indexing, and retrieval checks.
- Metadata tests must verify emitted `run_manifest.json` and `events.jsonl` remain valid and versioned.

## Data Mapping Rules

- Source corpus: `large-demo-data-2-7-0.sql` unless explicitly changed.
- Target environment: OpenMRS Platform/Core 2.8 Ref App-compatible database.
- Store LLM proposals separately from accepted mappings.
- Promote only reviewed mappings into `datasets/mappings/openmrs-2.7-to-2.8.yaml`.
- Transforms in `datasets/transforms/` must be deterministic and repeatable from a clean baseline.

## Documentation

- Keep `README.md` current for quickstart and milestone status.
- Keep `specs/metadata-schema.md` aligned with emitted artifacts.
- Keep `specs/data-remap-2.8.md` aligned with the current import/remap strategy.
- Treat `specs/artifacts/` as durable planning and research snapshots, not generated build output.
- Keep `docs/` reserved for user-facing documentation.

## Safety and Governance

- Capture model/provider/prompt/dataset/schema-mapping provenance for every run.
- Align shared metadata fields with OpenTelemetry GenAI conventions where practical, while preserving clinical evaluation fields separately.
- Use PCCP-style change records for material model, prompt, retrieval, mapping, or pipeline changes.
