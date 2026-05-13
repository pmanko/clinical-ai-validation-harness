<!--
Sync Impact Report
Version change: 1.0.0 -> 1.1.0
Modified principles:
- I. Real Production Paths: unchanged
- II. Deterministic Reviewed Transforms: unchanged
- III. Record-Level Evidence: expanded to require rationale-bearing evidence
- IV. Metadata, Provenance, and Traceability: expanded to capture decision rationale
- V. Tests Define Behavior: expanded to require scenario diversity and overfit checks
Added sections:
- none
Removed sections:
- none
Templates requiring updates:
- updated: .specify/templates/plan-template.md
- updated: .specify/templates/spec-template.md
- updated: .specify/templates/tasks-template.md
- updated: .specify/templates/checklist-template.md
- updated: .specify/templates/commands/*.md (no command templates present)
- updated: README.md
- updated: AGENTS.md
- updated: specs/data-remap-2.8.md
- updated: specs/metadata-schema.md
Follow-up TODOs: none
-->
# clinical-ai-validation-harness Constitution

## Core Principles

### I. Real Production Paths

Validation MUST exercise the real OpenMRS, OpenELIS Catalyst, `chartsearchai`,
`querystore`, and `openmrs_chatbot` paths whenever those paths are available.
Adapters may orchestrate setup and command/API invocation, but they MUST NOT
replace target project behavior with harness-only simulations for validation
claims. Any mock, fixture, synthetic shortcut, or narrow honeypot scenario MUST
be labelled as development scaffolding and excluded from release evidence unless
paired with a real-path validation run.

Rationale: the harness exists to validate integration behavior and clinical AI
outputs as they will actually run, not an approximation of those systems.

### II. Deterministic Reviewed Transforms

LLM-assisted analysis MAY propose schema mappings, record mappings, prompts, or
retrieval changes, but accepted behavior MUST live in reviewed configuration,
scripts, or code. Data transforms MUST be deterministic, repeatable from a clean
baseline, and free of hidden manual repair steps. The default source corpus for
OpenMRS remap work is `large-demo-data-2-7-0.sql`; the target for the first
milestone is an OpenMRS Platform/Core 2.8 Ref App-compatible database.

Rationale: clinical validation evidence must be reproducible by reviewers and
future agents without relying on unstated judgment or transient model output.

### III. Record-Level Evidence

Claims about filtering, mapping, import success, retrieval quality, answer
quality, or safety MUST preserve record-level evidence and the rationale for the
judgment made from that evidence. Aggregate counts, success rates, and smoke-test
summaries are insufficient unless they link back to inspected records, cited
record identifiers, reviewer labels, decision rationale, or reproducible queries.
Known-answer fixtures and retrieval evaluations MUST make it possible to trace an
answer to the supporting clinical records and to any abstention or review
decision, including why the decision is clinically and operationally acceptable.

Rationale: clinical validation fails when a passing metric hides incorrect
patient-level evidence, unsafe citations, or changed clinical meaning.

### IV. Metadata, Provenance, and Traceability

Every harness run that produces validation evidence MUST emit versioned
metadata, including `run_manifest.json` and `events.jsonl` where applicable.
Metadata MUST capture project/component identity, git revision, dataset and
mapping versions, model/provider/prompt provenance when models are involved,
retrieval details, reviewer decisions, decision rationale, and schema versions.
Shared fields SHOULD align with OpenTelemetry GenAI conventions when practical,
while clinical-evaluation fields remain explicit harness extensions.

Rationale: reviewers need a durable chain from a result back to the code,
dataset, mapping, prompt, model, and execution environment that produced it.

### V. Tests Define Behavior

Behavioral changes MUST add or update tests before the change is considered
complete. Tests MUST NOT be weakened to match broken behavior, overfit to one
known fixture, or validate only the exact scenario used to tune the behavior.
Smoke tests MUST grow toward real OpenMRS startup, REST/API readability, schema
integrity, indexing, retrieval, metadata validity, and adapter checks. Evaluation
suites MUST include diverse clinical and operational scenarios when validation
evidence depends on model behavior, retrieval behavior, mappings, or external
tools, including ambiguous mappings, missing evidence, unsupported claims,
abstentions, and tool/API failures when relevant. Metadata tests MUST verify
emitted manifests and event traces remain valid and versioned.

Rationale: this repository is a validation harness; untested behavior changes
undermine the evidence the harness is supposed to produce.

## Validation Scope and Data Boundaries

This repository is a lightweight monorepo-style control plane for local and
VM-based setup, orchestration, and validation across early clinical AI projects.
It SHOULD coordinate sibling or mounted checkouts instead of vendoring upstream
code by default. Project registry, checkout, compose, and adapter work MUST keep
the referenced projects' real commands and APIs as the validation surface.

Clinical evidence data and operating metadata MUST remain separate. Query Store
and CQRS-style stores are for searchable clinical records; this harness stores
run metadata, traces, responses, evaluations, review records, and reports.
Artifacts generated by runs MUST live in ignored artifact/output locations unless
explicitly curated as durable documentation or fixtures.

Material changes to models, prompts, retrieval behavior, schema mappings, data
transforms, validation criteria, or pipeline behavior MUST include PCCP-style
change records or equivalent review context that describes the modification,
validation protocol, impact assessment, and residual risk.

## Development Workflow and Governance Gates

Plans MUST document how each feature satisfies the constitution before
implementation begins and again after design decisions are made. Specifications
MUST include measurable success criteria, independently testable user stories,
data boundaries, provenance needs, and evidence requirements when the feature
touches clinical data, mappings, retrieval, model behavior, or validation
artifacts. Plans and specifications MUST explain why the selected evidence,
tests, and governance controls are sufficient, not merely list what actions will
be taken.

Tasks MUST be small, reviewable, and ordered so reproducibility and evidence
capture are implemented with the behavior they validate. The task list MUST
include tests for behavioral changes and documentation updates for any changed
quickstart, metadata schema, remap strategy, or governance process.

Pull requests and reviews MUST check for real-path validation, deterministic
accepted mappings, record-level evidence, metadata emission, test coverage, and
PCCP-style review records when applicable.

## Governance

This constitution supersedes conflicting guidance in repository documentation,
Spec Kit templates, feature plans, and agent instructions. Repository guidance
such as `AGENTS.md`, `README.md`, user-facing `docs/`, and planning artifacts in
`specs/` MUST be kept aligned when this constitution changes.

Amendments require a pull request that explains the governance change, updates
affected templates, specs, and docs, and includes a Sync Impact Report in this
file.
Versioning follows semantic versioning:

- MAJOR: removes or redefines a core principle in a backward-incompatible way.
- MINOR: adds a principle or materially expands governance requirements.
- PATCH: clarifies wording, fixes typos, or makes non-semantic refinements.

Compliance review is required for every feature plan, task set, and material
change touching clinical evidence, mappings, metadata, retrieval, prompts,
models, or validation pipelines. Exceptions MUST be documented in the feature
plan with a justification, a safer alternative considered, and the residual risk.

**Version**: 1.1.0 | **Ratified**: 2026-05-12 | **Last Amended**: 2026-05-12
