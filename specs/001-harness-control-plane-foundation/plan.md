# Implementation Plan: Harness Control Plane Foundation

**Branch**: `001-harness-control-plane-foundation` | **Date**: 2026-05-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-harness-control-plane-foundation/spec.md`

## Summary

Establish the harness as a cross-project control plane that pins target repositories under `targets/`, records target metadata in `harness/targets.yaml`, provides target sync/readiness workflows, and separates harness-owned shared infrastructure from target-owned app startup. The implementation replaces hardcoded local checkout assumptions with reviewed submodule pins plus explicit override provenance, updates metadata toward current OTel GenAI conventions, and adds tests that prevent scaffolding or override runs from being mistaken for release evidence.

## Technical Context

**Language/Version**: Python 3.11+ for the harness CLI/package, with `uv` managing interpreter installation, dependency resolution, and the project virtual environment; Docker Compose for shared infrastructure orchestration; Git submodules for target repository pins.

**Primary Dependencies**: Existing `PyYAML>=6.0` for `harness/targets.yaml`; standard library `argparse`, `dataclasses`, `pathlib`, `json`, `subprocess`; `uv` for local/VM Python environment reproducibility; Docker Compose CLI and Git CLI as external tools invoked by documented workflows. No new runtime dependency is required for M0 planning beyond existing `PyYAML`.

**Storage**: Files only. Persistent reviewed inputs: `.gitmodules`, gitlink pins under `targets/`, `harness/targets.yaml`, compose files. Generated outputs: ignored `artifacts/**` run directories containing `run_manifest.json`, `events.jsonl`, readiness summaries, and reports.

**Testing**: `pytest` under `evals/` for target metadata schema/validation, target sync command planning, readiness classification, manifest override provenance, OTel GenAI field shape, and compose profile ownership checks.

**Target Platform**: Local macOS/Linux developer environments and VM environments capable of running Git, Python 3.11+, Docker Compose, and target-specific build tools. Windows is not an M0 target.

**Project Type**: Python CLI/control-plane package with file-based configuration, command-planning adapters, and compose orchestration helpers.

**Performance Goals**: `harness-cli targets status` should complete in under 5 seconds for four initialized targets when not starting external services. `harness-cli targets sync --plan` should render planned Git operations in under 2 seconds. Readiness checks must not start long-running services unless explicitly requested.

**Constraints**: Real-path validation must use pinned target repositories unless an override is explicitly flagged. Target overrides must be captured in run metadata and cannot count as release evidence without review. Harness-owned compose files are for shared infrastructure only; target app services remain target-owned. OTel GenAI fields must use current Development-status names (`gen_ai.provider.name`, `gen_ai.operation.name`, `gen_ai.agent.*`, `gen_ai.tool.*`) rather than `gen_ai.system`.

**Scale/Scope**: Initial scope is four targets (`chartsearchai`, `querystore`, `openmrs_chatbot`, `catalyst`), two environment profiles (`local`, `vm`), shared infra compose for OpenMRS/MySQL/Elasticsearch/OTel, and extracted Catalyst as a standalone `targets/catalyst` submodule once available. This feature does not implement OpenMRS demo-data remap, metadata spine M2, real adapter execution M3, retrieval evaluation M4, or Catalyst extraction itself.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Real production paths**: PASS. Target repositories are pinned submodules under `targets/`; validation surfaces point to target-owned commands/APIs. Overrides and scaffolding are labelled non-release evidence unless reviewed.
- **Deterministic reviewed transforms**: PASS. No data transform is introduced. Accepted behavior lives in `.gitmodules`, gitlink pins, `harness/targets.yaml`, compose files, CLI code, and tests.
- **Record-level evidence**: PASS. This foundation does not create clinical evidence itself, but it defines readiness/evidence status, target pin provenance, and override-run metadata required for later record-level evidence.
- **Metadata and provenance**: PASS. Plan updates metadata shape to include target SHAs, override provenance, OTel GenAI version/attributes, readiness decisions, and run manifest/event destinations.
- **Tests define behavior**: PASS. Behavioral changes require tests for target metadata validation, sync planning, readiness status, override provenance, OTel field shape, and compose ownership.
- **Data boundaries and governance**: PASS. Clinical data remains in target/source systems; harness stores operating metadata and generated run artifacts. Target pin bumps, evidence-status promotions, and override evidence promotion require review context.
- **Why this is sufficient**: The plan treats repository pins and target metadata as reviewed inputs, forces readiness classification before evidence claims, preserves source/pin/override provenance in manifests, and keeps target-owned app startup separate from shared infrastructure.

## Project Structure

### Documentation (this feature)

```text
specs/001-harness-control-plane-foundation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── run-manifest-control-plane.schema.yaml
│   └── targets.schema.yaml
├── checklists/
│   └── requirements.md
└── tasks.md                 # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
.gitmodules                  # Target repo URLs and submodule paths
targets/
├── chartsearchai/            # Submodule
├── querystore/               # Submodule
├── openmrs_chatbot/          # Submodule
└── catalyst/                 # Extracted Catalyst submodule, once available

harness/
├── cli.py                    # Adds targets/status/sync/profile commands
├── config.py                 # Loads harness root, artifacts, and target metadata
├── metadata.py               # Adds current OTel GenAI and target provenance fields
├── targets.py                # Target metadata parsing/validation/readiness
├── compose.py                # Shared-infra profile planning and compose-file resolution
├── submodules.py             # Submodule status/sync command planning
├── adapters/
│   ├── chartsearchai.py
│   ├── querystore.py
│   ├── openmrs_chatbot.py
│   └── catalyst.py
└── targets.yaml              # Reviewed target metadata

compose/
├── openmrs-2.8-refapp.yml    # Harness-owned shared OpenMRS/MySQL infra
└── services.yml              # Harness-owned shared Elasticsearch/OTel infra

evals/
├── indexing/
├── metadata/
├── orchestration/
└── target_registry/

artifacts/                    # Ignored generated run outputs
docs/                         # User-facing documentation only
specs/                        # Roadmap and feature spec directories
```

**Structure Decision**: Use the existing harness/control-plane layout. Add a `targets/` submodule root and `harness/targets.yaml` as reviewed source-of-truth metadata. Add small Python modules for target registry, submodule planning, and compose profile planning rather than embedding this behavior in existing CLI functions.

## Complexity Tracking

No constitution violations require justification.

## Phase 0: Research

Completed in [research.md](./research.md). All design unknowns from clarification are resolved: submodules vs subtree, target metadata vs `.gitmodules`, Catalyst extraction boundary, target sync/override workflow, Compose profile ownership, OTel GenAI current fields, submodule CI/VM hardening, and override-run provenance.

## Phase 1: Design

Design artifacts:

- [data-model.md](./data-model.md): Target metadata, environment profiles, readiness summaries, override runs, and manifest fields.
- [contracts/targets.schema.yaml](./contracts/targets.schema.yaml): YAML schema for `harness/targets.yaml`.
- [contracts/run-manifest-control-plane.schema.yaml](./contracts/run-manifest-control-plane.schema.yaml): Control-plane run manifest additions.
- [contracts/cli.md](./contracts/cli.md): User-facing CLI command contracts.
- [quickstart.md](./quickstart.md): Local/VM setup and evidence-status workflow.

### Post-Design Constitution Check

- **Real production paths**: PASS. Contracts require target submodules and real validation surfaces, with target overrides clearly non-release until reviewed.
- **Deterministic reviewed transforms**: PASS. No transforms introduced; reviewed inputs are deterministic files and pinned submodule SHAs.
- **Record-level evidence**: PASS. Readiness and manifest contracts preserve target pin/override evidence and decision rationale; downstream clinical records remain in source systems.
- **Metadata and provenance**: PASS. Run manifest contract records harness SHA, target SHA, override status/source, target metadata version, OTel GenAI convention status, and evidence status.
- **Tests define behavior**: PASS. Contracts are directly testable with fixture target metadata, mocked submodule status, and manifest examples.
- **Data boundaries and governance**: PASS. Override promotion and target evidence-status changes require review context; compose ownership avoids vendoring target app definitions into harness shared infra.
- **Why this is sufficient**: The design makes every later validation run traceable to reviewed target pins and explicit target metadata while keeping development overrides possible but non-ambiguous.
