# OpenMRS Demo Data Remap (2.7 -> 2.8)

## Goal

Transform `large-demo-data-2-7-0.sql` into a deterministic OpenMRS 2.8 Ref App-compatible import candidate.

## Workflow

1. Load source dump into disposable `legacy_27_raw`.
2. Create clean `refapp_28_clean` baseline.
3. Extract schema and metadata from both.
4. Produce machine-readable diff under `artifacts/schema-diff/`.
5. Generate LLM mapping proposals (advisory only).
6. Review and accept mappings into `datasets/mappings/openmrs-2.7-to-2.8.yaml`.
7. Execute deterministic transforms from `datasets/transforms/`.
8. Validate import with smoke tests and API readability checks.

## Required Reviews

- Unmapped concept and encounter metadata.
- Module-owned tables and Liquibase state.
- Any table/key rewrite that could alter clinical meaning.

## Acceptance

- Candidate DB can be rebuilt from clean baseline without manual edits.
- Import smoke checks pass.
- Chartsearchai and querystore adapter checks can run against imported corpus.
