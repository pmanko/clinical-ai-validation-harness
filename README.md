# clinical-ai-validation-harness

A validation harness for early clinical AI tools — helping teams test AI-powered clinical systems against realistic health data and real integration paths, with traceable, reviewable evidence at every step.

The harness currently focuses on OpenMRS-based clinical AI (chart search, query retrieval, clinical chat) and OpenELIS lab-system AI (Catalyst). Validation means real systems, real data, and decisions that can be traced back to specific clinical records — not just passing unit tests.

## Who this is for

- **Clinical and program stakeholders** — understand how AI answers are evaluated, what evidence backs a validation claim, and where the governance guardrails are.
- **Technical collaborators** — run the harness locally or on a VM, inspect transforms and run artifacts, and contribute code or mapping reviews.
- **AI validation and research readers** — explore the evidence model, evaluation methodology, and metadata schema across retrieval, answer quality, citation, abstention, and safety dimensions.
- **OpenMRS / OpenELIS community members** — see how demo data is modernized for the latest Reference Application, how harness tools relate to existing modules, and what parts could be reused.

## What this harness validates

The harness coordinates validation across four clinical AI projects:

| Project | What it does | Role here |
|---------|-------------|-----------|
| `chartsearchai` | Embedded OpenMRS module: searches patient chart records using embeddings and lexical retrieval, then generates cited answers | Primary validation target: retrieval quality, answer grounding, citation, abstention, and security |
| `querystore` | Emerging read-optimized store that will back `chartsearchai` retrieval | Parity testbed: compare retrieval behavior before and after migration |
| `openmrs_chatbot` | Python clinical chatbot with patient/doctor interfaces and agent workflow scaffolding | Future expansion: multi-turn grounding and role-aware answer evaluation |
| `Catalyst` (OpenELIS) | Lab AI sidecar over OpenELIS Global 2: FHIR-grounded retrieval over HAPI and embedded FHIR providers, resource-cited answers, and a Scout-style lab report/analytics UI | M10 (Planning): FHIR-first sidecar POC — canonical question set, evidence cards, lab timeline, and embedded-FHIR parity probe |

## Current priority: OpenMRS demo-data remap (Roadmap M1)

The first major deliverable transforms the publicly available OpenMRS 2.7 demo corpus (`large-demo-data-2-7-0.sql`) into a Reference Application 3.x / Core 2.8-compatible database. This creates a realistic, importable clinical corpus that `chartsearchai` and other tools can be validated against.

Work includes profiling the source corpus (schema, terminology, modules), mapping concepts onto the CIEL clinical terminology standard, running deterministic SQL transforms, validating the imported database against a live OpenMRS stack, and running chart search and coverage checks against real imported data.

Status: actively in progress. See the [Feature 002 spec](specs/002-openmrs-demo-data-2-8-remap/spec.md) and [quickstart](specs/002-openmrs-demo-data-2-8-remap/quickstart.md) for step-by-step detail.

## How the docs fit together

| What you need | Where to go |
|---------------|-------------|
| Visual project overview and navigation | [Public docs site](https://pmanko.github.io/clinical-ai-validation-harness/) |
| Roadmap — what is planned, why, and in what order | [Feature roadmap canvas](specs/roadmap.canvas.tsx) |
| Development operating plan — lanes, gates, launch sequence | [docs/dev-roadmap.md](docs/dev-roadmap.md) |
| Validation evidence model and evaluation methodology | [Validation research canvas](specs/artifacts/canvases/validation-research.canvas.tsx) |
| Current priority operator walkthrough | [Feature 002 quickstart](specs/002-openmrs-demo-data-2-8-remap/quickstart.md) |
| Harness foundation and control-plane detail | [Feature 001 spec](specs/001-harness-control-plane-foundation/spec.md) |
| All planning artifacts, canvases, and research docs | [specs/artifacts/](specs/artifacts/) |
| Cloud/GCE deploy guide | [docs/cloud-deploy.md](docs/cloud-deploy.md) |

The public docs site auto-deploys from `main` and includes all canvases and spec markdown. Browse locally with `cd site && npm install && npm run dev` (opens at `http://127.0.0.1:4321/clinical-ai-validation-harness/`).

## Milestone names and IDs

Human-facing docs use plain names. IDs appear in parentheses on first use and inside technical specs.

| Plain name | Roadmap ID | Feature folder | Status |
|-----------|-----------|----------------|--------|
| Harness foundation | M0 | `001` | Complete |
| OpenMRS demo-data remap | M1 | `002` | Complete |
| Validation spine | M2 | `006` | In progress (validation-harness MVP; runner/report/feedback shipped — see lane L3) |
| Real adapter entrypoints | M3 | `004` | In progress |
| med-agent-hub bridge | F005 | `005` | Shipped (model-switch + Carbon picker + model warmup + Tier-1 KB) |
| LLM config overrides | F007 | `007` | Planned |
| med-agent-hub MCP tools | F010 | `017` | In progress (lane L1) |
| Chartsearchai model gateway | F008 | `008` | [Brief](specs/artifacts/planning/chartsearchai-model-gateway-brief.md) |
| Clinical knowledge base | F009 | `009` | [Brief + research](specs/artifacts/planning/clinical-kb-brief.md) |
| Retrieval evaluation | M4 | `010` | Planned |
| Catalyst FHIR sidecar POC | M10 | `011` | [Brief](specs/artifacts/planning/catalyst-fhir-sidecar-brief.md) |
| Answer, citation, and abstention | M5 | `012` | Planned |
| Safety and red-team | M6 | `013` | Planned |
| Clinician governance review | M7 | `014` | Planned |
| Querystore parity testbed | M8 | `015` | Planned |
| Cross-project expansion | M9 | `016` | Planned |

> **Note on feature 002 internal phases:** Work inside the OpenMRS demo-data remap (M1 / `002`) uses implementation sub-labels `M2-A` through `M2-Z` in detailed feature docs. These are internal planning labels for that feature's phases — not related to roadmap milestone M2 (Validation spine).

> **Note on F-prefixed IDs and non-monotonic slugs:** F005, F007, F008, F009, F010 are features inserted into the roadmap after the M0–M10 sequence was authored. The validation spine (M2) shipped as slug `006` (validation-harness MVP) — the earlier `003` slug was never created. `007` is LLM config overrides (F007); `017` is the med-agent-hub MCP tools (F010). The Roadmap IDs (M0–M10, F005–F010) carry the semantic ordering anchor; folder slugs are filesystem identifiers and may be non-monotonic. See [`specs/roadmap.canvas.tsx`](specs/roadmap.canvas.tsx) for the dependency DAG.

> **Note on M10 and sibling checkouts:** The Catalyst FHIR sidecar POC (M10) consumes OpenELIS Global 2 as a **sibling checkout** at `../OpenELIS-Global-2/` (or `$OPENELIS_ROOT`). OE2 is not a submodule of this harness. Catalyst Python services live in `targets/catalyst` (submodule pinned to `DIGI-UW/openelis-catalyst`). The Spec Kit Phase 2 workflow (`/speckit-specify` through `/speckit-tasks`) runs against the [source brief](specs/artifacts/planning/catalyst-fhir-sidecar-brief.md) to produce `specs/011-catalyst-fhir-sidecar-poc/`.

## Principles

How validation claims are made and how evidence is handled:

- **Use real paths.** Run real OpenMRS, real `chartsearchai`, and real adapters. Stubs and simulations are labeled as scaffolding and cannot count as production-path evidence.
- **Separate clinical data from operating metadata.** Record-level clinical evidence lives in the database or SQL artifacts. Run manifests, event traces, and evaluation records are metadata kept separate.
- **Keep LLM output advisory.** Machine-generated mapping proposals are starting points only. Accepted mappings must be reviewed and stored in deterministic, versioned artifacts before use.
- **Require record-level evidence.** Validation claims trace to specific records — not just counts or aggregate metrics.
- **Cover diverse scenarios.** Evaluation sets include edge cases, absent-data cases, and adversarial inputs — not only the happy path used to tune a prompt or mapping.
- **Document material changes.** Significant changes to models, prompts, retrieval, mappings, or pipelines require a change record (PCCP — see Key Terms). This keeps decisions reviewable and reproducible.

The canonical governance reference is `.specify/memory/constitution.md`.

## Repository layout

```
docs/          User-facing guides and operator runbooks
specs/         Feature specs, plans, research docs, and canvases; specs/artifacts/ for cross-cutting materials
compose/       Docker Compose files for the OpenMRS/MariaDB stack and optional services
datasets/      Source pointers, mapping artifacts, deterministic transforms, and fixtures
harness/       Python orchestration package and CLI (harness-cli)
adapters/      Adapter contracts for invoking real project validation paths
evals/         pytest suites for import, indexing, retrieval, and metadata checks
artifacts/     Per-run outputs: manifests, events, reports (gitignored)
site/          Static-site build of specs and canvases; auto-deployed to GitHub Pages
targets/       Pinned submodule checkouts of the four target projects
```

## Quickstart

**Requirements:** Python 3.11+, `uv`, Docker / Docker Compose, Git.

```bash
# 1. Install uv (Python environment manager) if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Set up the Python environment and install all dev dependencies
make setup

# 3. Bring up the OpenMRS Reference Application stack (MariaDB + backend + frontend)
docker compose -f compose/openmrs-2.8-refapp.yml up -d

# 4. Run a schema diff between the legacy 2.7 source and the clean 2.8 baseline
uv run harness-cli schema-diff --output-dir artifacts/schema-diff

# 5. Run the smoke test suite
make smoke
```

If `make` is unavailable:

```bash
uv python install 3.11
uv sync --extra dev
uv run pytest evals/dataset_import evals/metadata
```

Python 3.11+ is required. The project tracks `.python-version = 3.11` and `requires-python = ">=3.11"` in `pyproject.toml`.

For the full OpenMRS demo-data remap workflow, see [specs/002-openmrs-demo-data-2-8-remap/quickstart.md](specs/002-openmrs-demo-data-2-8-remap/quickstart.md).

## ChartSearch operations

The chartsearchai adapter (feature 004) and its Med Agent Hub team are operated through `make` targets that
wrap the build, the LLM engine, the retrieval backend, and the per-endpoint model picker:

The **canonical LLM path** is chartsearchai → Med Agent Hub (`:8080`) → llama-router (`:8077`): a llama.cpp
Router Mode server serving the tier GGUFs the hub maps its per-role models onto. LM Studio (`:1234`) and the
module's bundled in-process `llama-server` remain configurable alternatives.

```bash
# Build chartsearchai's .omod from the submodule and stage it for the backend
make chartsearch-build

# Canonical local LLM backend (foreground server, own terminal). TIER=low|med|high.
make llama-router-up                 # serves the tier GGUFs on :8077
make llama-router-models             # probe what :8077 is serving

# Bring up / configure the stack
make chartsearch-up
make med-agent-hub-up               # the agent team; routes to llama-router (:8077)
make chartsearch-configure          # sets the chartsearchai.llm.* global properties from .env.chartsearch

# LLM engine — switch between the bundled local model and a remote endpoint
make chartsearch-engine ENGINE=local     # chartsearchai's own bundled llama-server, in-process (module OOTB default)
make chartsearch-engine ENGINE=remote    # OpenAI-compatible endpoint (Med Agent Hub / LM Studio / cloud) — harness default

# LM Studio is an alternative remote endpoint; warm its models if you use it
make chartsearch-warmup

# Retrieval backend — querystore's CQRS read store tier
make chartsearch-backend BACKEND=elasticsearch   # or lucene | mysql
```

**Model picker.** When `CHARTSEARCH_REMOTE_ENDPOINTS` (a JSON array of `{label, url}`) is set in
`.env.chartsearch`, the chat panel shows a sectioned picker — one section per endpoint (e.g. *Med Agent Hub*,
*llama-server*, *LM Studio*). Selecting a model sends it as a per-request `{endpointUrl, modelName}` override on
that chat only; it does not change the config-controlled global default (shown with a faded "default" tag). With
no registry set, the picker collapses to the single configured endpoint.

**Cloud.** `make cloud-deploy` ships the backend (`.omod`) and `make cloud-deploy-esm` ships the frontend
bundle; `make cloud-status` / `cloud-ssh` inspect the VM. The cloud runs the same engine + picker + Med Agent
Hub setup as local (it reaches the operator's LM Studio over the LM Link).

## Key terms

| Term | Meaning |
|------|---------|
| **Harness** | This repository — it orchestrates validation across the four target projects without living inside any of them. |
| **Target** | One of the four clinical AI projects validated here: `chartsearchai`, `querystore`, `openmrs_chatbot`, or Catalyst. |
| **Canvas** | An interactive visual summary page (`.canvas.tsx`) authored in Cursor and published on the docs site. |
| **CIEL** | Columbia International eHealth Laboratory dictionary — the open clinical concept terminology standard used by OpenMRS. |
| **OCL** | Open Concept Lab — the terminology service that hosts CIEL and other clinical dictionaries. |
| **FHIR** | Fast Healthcare Interoperability Resources — used here as the grammar for terminology mapping artifacts (ConceptMap format). |
| **Ref App** | OpenMRS Reference Application, the standard OpenMRS distribution. "O3 Ref App" refers to the current 3.x version on Core 2.8. |
| **SQLMesh** | The deterministic data transformation framework used to materialize the OpenMRS 2.7 → 2.8 migration. |
| **run_manifest.json** | Machine-readable provenance record emitted for every harness run: inputs, versions, component SHAs, and evidence status. |
| **events.jsonl** | Append-only event trace for a run: queries, retrievals, model calls, evaluations, and reviewer actions. |
| **PCCP** | Predetermined Change Control Plan — a structured change record (adapted from FDA AI guidance) used here for material changes to models, prompts, retrieval, mappings, or pipelines. Keeps decisions auditable. |

## Spec Kit and contributor automation

This repository uses [GitHub Spec Kit](https://github.com/github/spec-kit) (`v0.8.9`) for AI-assisted feature specification and planning. Agent and contributor guidance lives in `AGENTS.md`. Cursor skills are in `.cursor/skills/`; Claude skills are in `.claude/skills/`.

Useful skills for contributors:

- `/speckit-specify` — create or update a feature spec
- `/speckit-plan` — generate an implementation plan
- `/speckit-tasks` — generate task lists from a plan
- `/speckit-implement` — execute tasks from `tasks.md`
- `/speckit-analyze` — cross-artifact consistency check

## Notes on source data and sibling repositories

The OpenMRS 2.7 demo corpus (`large-demo-data-2-7-0.sql`) is not stored in this repository. It is expected as a sibling checkout alongside this repo:

```
../openmrs-module-chartsearchai/data/large-demo-data-2-7-0.sql
```

Use an environment variable to override the location:

```bash
export HARNESS_TARGET_CHARTSEARCHAI=/path/to/openmrs-module-chartsearchai
```

The `querystore` source repository is also expected as a sibling checkout (`../openmrs-module-querystore`) or via `HARNESS_TARGET_QUERYSTORE`.

For OpenELIS feasibility analysis (feature 002, sub-phase M2-H), the OpenELIS Global 2 repository is read from a sibling checkout (`../OpenELIS-Global-2`) or via `OPENELIS_ROOT=/path/to/OpenELIS-Global-2`.
