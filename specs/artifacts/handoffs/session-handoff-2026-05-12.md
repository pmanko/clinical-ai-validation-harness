# Session Handoff: Validation Harness Repo

Date: 2026-05-12

This artifact captures the working context needed to switch IDE/workspace from
`openmrs-module-chartsearchai` to the new standalone repository.

- Local repo: `$HOME/code/clinical-ai-validation-harness` (example)
- GitHub repo: `<your-fork-or-org>/clinical-ai-validation-harness` (example)
- Current branch for this handoff: `<handoff-branch>` (example)

## Why This Exists

The current chat was started in the old `openmrs-module-chartsearchai` workspace.
Spec Kit was installed in the new standalone repo, so `/speckit-*` skills may not
appear in this chat/context. To use the installed Spec Kit skills, open Cursor on
your local clone path, for example:

```sh
$HOME/code/clinical-ai-validation-harness
```

The new repo contains the Spec Kit installation and agent integration files.

## Project Goal

`clinical-ai-validation-harness` is intended to be an umbrella validation and
orchestration repository for early clinical AI prototypes across OpenMRS and
OpenELIS work:

- `openmrs-module-chartsearchai`
- `openmrs-module-querystore`
- `openmrs_chatbot`
- OpenELIS Catalyst under `OpenELIS-Global-2/projects/catalyst`

The repo is not meant to be OpenMRS-only. The first implementation slice is the
OpenMRS demo-data remap because it gives the umbrella harness a realistic clinical
corpus and a concrete validation target: transform/remap/import
`large-demo-data-2-7-0.sql` into an OpenMRS Platform/Core 2.8 Ref App-compatible
candidate database, then validate through real chartsearchai and querystore paths.

The primary direction is for this repo to act as a lightweight monorepo-style
control plane for local development/testing and VM setup across all referenced
projects. The intended shape is not to vendor all upstream code by default, but to
provide repeatable checkout/build/run profiles and compose environments that can
work with sibling/local checkouts or VM-mounted code.

## Current Repo State

Main repo commits already pushed:

- `5e30917` - Initialize cross-project validation harness repository
- `50dc4ba` - Install Spec Kit with Cursor Agent integration
- `2baa382` - Add Claude Spec Kit integration alongside Cursor

The repo currently includes:

- `README.md`: quickstart, repo layout, Spec Kit notes, milestone contract
- `AGENTS.md`: agent/contributor guidance
- `CLAUDE.md`: generated Spec Kit Claude guidance stub
- `.specify/`: Spec Kit project scaffolding
- `.cursor/skills/`: Cursor Agent Spec Kit skills
- `.cursor/rules/specify-rules.mdc`: Cursor rule for Spec Kit
- `.claude/skills/`: Claude Code Spec Kit skills
- `specs/artifacts/`: supporting planning docs, research canvases, and handoff snapshots
- `specs/roadmap.canvas.tsx`: source-of-truth roadmap dashboard
- `specs/artifacts/planning/data-remap-2.8.md`: demo-data remap plan
- `specs/artifacts/planning/metadata-schema.md`: v0 manifest/event schema
- `specs/artifacts/planning/pccp-change-record-template.md`: governance/change-control template
- `compose/`: OpenMRS/MySQL and optional service compose stubs
- `datasets/`: sources, mappings, transforms, fixtures
- `harness/`: Python CLI/package scaffolding
- `adapters/`: chartsearchai, querystore, openmrs_chatbot, Catalyst adapter notes
- `evals/`: initial pytest skeletons

## Spec Kit Installation

Installed using the official GitHub Spec Kit release:

```sh
uvx --from git+https://github.com/github/spec-kit.git@v0.8.9 specify init \
  --here --force --integration cursor-agent --script sh
```

Then Claude was added through official multi-integration support:

```sh
uvx --from git+https://github.com/github/spec-kit.git@v0.8.9 specify integration install claude --script sh
```

Verification showed both integrations installed and Cursor remaining default:

- `cursor-agent`: installed, default
- `claude`: installed

Relevant generated files:

- `.specify/integration.json`
- `.specify/init-options.json`
- `.specify/integrations/cursor-agent.manifest.json`
- `.specify/integrations/claude.manifest.json`

Historical note (as of this handoff date): `.specify/memory/constitution.md` was
still the generated template and the next step at that time was:

```text
/speckit-constitution
```

In the current repository state, the constitution has since been ratified and the
canonical source is `.specify/memory/constitution.md`. The suggested principles
below are preserved as handoff context:

- Real production paths over simulations
- Deterministic, reviewed data transformations
- Record-level evidence before aggregate metrics
- Run metadata and JSONL traces as first-class outputs
- Tests must define behavior and must not be weakened to match bugs
- Clinical evidence data and operating metadata stay separate
- PCCP-style change records for material model/prompt/retrieval/mapping changes

## Research Canvas Artifacts

Three canvases were created during research and copied into the new repo:

- `specs/artifacts/canvases/validation-research.canvas.tsx`
- `specs/artifacts/canvases/cross-project-comparison.canvas.tsx`
- `specs/artifacts/canvases/clinical-ai-research-guidance.canvas.tsx`

These are intended as durable documentation snapshots, not build artifacts.

Content covered:

- chartsearchai validation roadmap
- demo-data 2.8 remap plan
- target validation architecture
- per-case validation process
- cross-project comparison across chartsearchai, openmrs_chatbot, and Catalyst
- recent clinical AI/RAG/agent/NL-to-SQL research guidance
- governance, OpenTelemetry GenAI metadata, and PCCP-shaped change control

## GitHub Repo Settings

Branch protection was applied to `main` via `gh`:

- PRs required for changes to `main`
- Admin enforcement enabled
- Stale review dismissal enabled
- Conversation resolution required
- Force pushes blocked
- Branch deletion blocked
- Auto-delete PR branches after merge enabled
- Required approvals set to `0` for now because only `pmanko` is a collaborator

Once another collaborator is added, raise required approvals to `1`.

## Important Correction During Session

The harness was accidentally first created and pushed inside
`openmrs-module-chartsearchai`. That was corrected:

- Mistaken module commit: `01209c6`
- Revert commit in module repo: `02bed2d`
- Standalone repo created and later renamed:
  <https://github.com/pmanko/clinical-ai-validation-harness>

The old module repo may still have local untracked files/folders from the work:

- `data/`
- `docs/local-dev-validation-runbook.md`
- `docs/openmrs-ai-dev-context.md`
- `openmrs-ai-validation-harness/`
- `clinical-ai-validation-harness/` if a renamed local checkout has been created

Those were not part of the standalone repo setup and should be reviewed before
deleting or committing.

## Current User Intent

The user wants this repo to act as a flexible monorepo/control-plane for setting
up and validating all referenced projects in:

- local development environments
- a running VM environment

Next implementation work should likely define:

- project registry for the four referenced codebases
- checkout/update scripts
- environment profiles for `local` and `vm`
- compose overlays for OpenMRS, OpenELIS/Catalyst, LM Studio-compatible endpoints,
  MySQL/Postgres/Elasticsearch/OTel as needed
- artifact/run directories that remain ignored
- adapter contracts that call real project commands/APIs rather than reimplementing
  behavior
- user-facing docs that clarify sibling checkout vs vendored/submodule choices

Do this through Spec Kit in the new repo:

```text
/speckit-constitution
/speckit-specify
/speckit-plan
/speckit-tasks
```

Use PRs for changes to `main`.

