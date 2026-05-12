# Validation Harness Constitution

## Purpose

This harness exists to produce reproducible, reviewable clinical AI validation evidence across multiple projects.

## Operating Principles

1. Use real execution paths over simulations.
2. Preserve provenance for every result.
3. Separate advisory LLM analysis from accepted deterministic transforms.
4. Prefer reversible, scripted, repeatable runs.
5. Version all schemas and mappings.
6. Keep clinical evidence data separate from operating metadata.
7. Treat baseline changes as governance events requiring review context.

## Non-negotiables

- No hidden manual database repair.
- No undocumented mapping acceptance.
- No metric-only claims without inspected records.
