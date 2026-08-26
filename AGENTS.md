# AGENTS.md

<!-- SPECKIT START -->
Active feature plan: `specs/008-catalyst-query-workbench/plan.md`

For Catalyst, read these authorities in order:

1. `specs/catalyst-program-roadmap.md` for phase order, product decisions,
   context behavior, and the model-team comparison;
2. `specs/catalyst-implementation-plan.md` for the current
   implementation sequence, checkpoints, and status;
3. the active Feature 008 specification and tasks for current product behavior;
4. `targets/catalyst/docs/dashboard-builder-mvp-design.md` and its populated
   binding 4c page for the Dashboard Builder interaction and visual
   contract.

Only the listed current documents define requirements. Run reports record
observations and do not define product behavior.

Catalyst core is a generic SQL-connected application. A source declares its
identity, label, connection configuration or reference, and SQL dialect. Model
and human tools receive every readable table, view, column, and type. Optional
descriptions may enrich that information but cannot hide relations. FHIR Data
Pipes -> Parquet -> Spark SQL is the selected reference deployment and is not
yet implemented; it is not the Catalyst product contract.

Validation is advisory. Exact selected SQL reaches the configured connection
through shared connection-execution code and returns bounded rows or the
database error. Do not add an application relation allowlist, fixed relation
count, SQL translation, direct-database harness replay, automatic factual
equivalence, score threshold, ranking, required repeated reader, or automatic
team choice.

Program order is Phase 1 session context and comparison, then definition of
Phase 2 conversation mode, then Phase 3 Dashboard Builder completion. The
Phase 1 connection implementation includes one Dataset-to-Superset regression smoke but does
not close or reduce Phase 3.

Before each owner review pause, surface unresolved implementation findings and
environment choices. Do not add a subsystem to solve a hypothetical problem;
record a concrete failure and return to the owner first.

For Phase 3, compare the live Workbench, Dataset review/library, Widget
review/library, Dashboard library/arrangement, and publish/import states side by
side with the binding design. Backend or evidence work cannot substitute for
browser-visible acceptance, and only explicit owner approval may change product
scope. On `codex/*` branches, run SpecKit with
`SPECIFY_FEATURE=008-catalyst-query-workbench`.

Use `scripts/catalyst-mvp.sh` for isolated-stack lifecycle, health, and Superset
operations. Do not invoke the target Compose file alone: the harness wrapper
establishes the isolated override, ports, sibling Hub context, and no-reseed
defaults. Seeding and reset remain explicit user-visible operations.
<!-- SPECKIT END -->

Guidance for AI agents and contributors working in this repository.

## Project Purpose

This is a standalone validation harness for early clinical AI prototypes across OpenMRS and OpenELIS work. The first milestone is a deterministic OpenMRS 2.8 Ref App-compatible remap/import path for `large-demo-data-2-7-0.sql`, followed by validation through real `chartsearchai` and `querystore` paths.

The active OpenMRS architecture is governed by
`specs/artifacts/planning/openmrs-dual-provider-parity-roadmap.md`: bundled ChartSearchAI inference
and configured med-agent-hub inference are separate providers behind one OpenMRS contract. Do not
remove bundled behavior, introduce silent provider fallback, or make Querystore a mandatory hub
dependency without an approved roadmap amendment. Consult the matching status, upstream inventory,
and conformance contract before changing provider, context, temporal, safety, or evidence behavior.

## Operating Principles

- Treat `.specify/memory/constitution.md` as the canonical governance source;
  keep this file, README, user-facing docs, and specs aligned when the constitution changes.
- Use real production paths for validation; do not simulate chartsearchai, querystore, OpenMRS, or Catalyst behavior when the real path can be exercised.
- Treat LLM-assisted mapping as advisory analysis only. Accepted mappings must live in reviewed config and deterministic scripts.
- Preserve record-level evidence and decision rationale. Do not claim a filter, mapping, retrieval result, or answer is correct from counts alone.
- Include diverse validation scenarios so tests do not only prove the exact case used to tune a prompt, mapping, adapter, or fixture.
- Keep clinical evidence data separate from operating metadata. Query Store/CQRS is for searchable clinical records; this harness stores run, trace, response, evaluation, and review metadata.
- Prefer small, reviewable changes that preserve reproducibility.

## Repository Branch Policy

- `clinical-ai-validation-harness` and `med-agent-hub` are maintained here. Changes use a
  short-lived branch and pull request, then tested/deployed revisions must already be in `main`.
- ChartSearchAI, ChartSearchAI ESM, and QueryStore are upstream-owned OpenMRS projects. Their
  proven companion work is consolidated on each fork's `harness-integration` branch, and this
  repository pins that exact remote head. The OpenMRS pull request must use
  `pmanko:harness-integration` as its head; do not publish the same tested commit from a separate
  feature branch.
- Other submodules remain on clean, remote-reachable commits unless an approved integration
  effort gives them an explicit branch policy.
- Run `scripts/verify-repository-lines.sh` before deployment. During a harness pull request, use
  `scripts/verify-repository-lines.sh --allow-harness-branch`; the strict check must pass after
  the pull request is merged. Before upstream publication or release signoff, also run
  `scripts/verify-repository-lines.sh --check-publication-prs` (or
  `make repository-publication-check` while the harness PR is open).

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
- Keep `specs/artifacts/planning/metadata-schema.md` aligned with emitted artifacts.
- Keep `specs/artifacts/planning/data-remap-2.8.md` aligned with the current import/remap strategy.
- Treat `specs/artifacts/` as durable planning and research snapshots, not generated build output.
- Keep `docs/` reserved for user-facing documentation.

## Safety and Governance

- Capture model/provider/prompt/dataset/schema-mapping provenance for every run.
- Align shared metadata fields with OpenTelemetry GenAI conventions where practical, while preserving clinical evaluation fields separately.
- Use PCCP-style change records for material model, prompt, retrieval, mapping, or pipeline changes.
