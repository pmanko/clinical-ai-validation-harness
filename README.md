# clinical-ai-validation-harness

A validation harness for early clinical AI tools — helping teams test AI-powered clinical systems against realistic health data and real integration paths, with traceable, reviewable evidence at every step.

The harness currently focuses on OpenMRS-based clinical AI (chart search, query retrieval, clinical chat) and OpenELIS lab-system AI (Catalyst). Validation means real systems, real data, and decisions that can be traced back to specific clinical records — not just passing unit tests.

## Why this matters

Much of the world's primary care runs in settings with intermittent connectivity, modest hardware, few IT staff, and strong reasons to keep patient data local. Clinical AI for these settings has to run **offline and on less-powerful hardware**, keep **patient data on-site** (privacy and local data ownership), and **fit local clinical reality** — guidelines, and the data most AI is trained on, come from better-resourced settings, leaving the conditions, formularies, and populations of low-resource clinics underrepresented in clinical research and guidelines. That shapes every choice here: local small-model profiles, including both fast single-model and deliberate team configurations, a knowledge base contextualized to each deployment's own concepts and drugs, and validation against real local systems with every claim traceable to a specific record. The intent mirrors WHO's [SMART Guidelines](https://www.who.int/teams/digital-health-and-innovation/smart-guidelines) — let local programs benefit from global evidence while adapting it to their own context — applied to the question "can we trust this AI here?"

## Who this is for

- **Clinical and program stakeholders** — understand how AI answers are evaluated, what evidence backs a validation claim, and where the governance guardrails are.
- **Technical collaborators** — run the harness locally or on a VM, inspect transforms and run artifacts, and contribute code or mapping reviews.
- **AI validation and research readers** — explore the evidence model, evaluation methodology, and metadata schema across retrieval, answer quality, citation, abstention, and safety dimensions.
- **OpenMRS / OpenELIS community members** — see how demo data is modernized for the latest Reference Application, how harness tools relate to existing modules, and what parts could be reused.

## What this harness validates

The harness coordinates validation across four clinical AI projects:

| Project | What it does | Role here |
|---------|-------------|-----------|
| `chartsearchai` | OpenMRS clinical-chat module with bundled and med-agent-hub provider paths | Product integration target: shared lifecycle UX, persistence, evidence display, cancellation, and security |
| `querystore` | Read-optimized OpenMRS clinical-record projection and optional med-agent-hub source | Context-source validation: materialized records, indexing integrity, date/freshness semantics, and retrieval experiments |
| `openmrs_chatbot` | Python clinical chatbot with patient/doctor interfaces and agent workflow scaffolding | Future expansion: multi-turn grounding and role-aware answer evaluation |
| `Catalyst` (OpenELIS) | Supervised reporting workbench: OpenELIS → HAPI FHIR → FHIR Data Pipes → governed query/table → versioned Dataset/Widget/Dashboard drafts → Superset bundle | Query/notebook MVP accepted; Superset-backed Dashboard Builder selected next; data, repair, evaluation, narrative, and production paths remain independently gated |

## Current priority: the validation spine and active lanes

The OpenMRS demo-data remap (Roadmap M1 / feature 002) is **complete** — the public 2.7 demo corpus is transformed and imported as the canonical 5,284-patient 2.8 demo schema the harness validates against. (See the [Feature 002 spec](https://github.com/pmanko/clinical-ai-validation-harness/blob/main/specs/002-openmrs-demo-data-2-8-remap/spec.md) and [quickstart](https://github.com/pmanko/clinical-ai-validation-harness/blob/main/specs/002-openmrs-demo-data-2-8-remap/quickstart.md) for that work.)

Current work is the **dual-provider foundational-parity roadmap**: preserve bundled ChartSearchAI
inference as the fresh-install default while allowing a configured med-agent-hub provider through
the same OpenMRS conversation, evidence, persistence, and cancellation contract. QueryStore remains
an OpenMRS projection with an optional hub adapter, not a hub dependency. The current integration
branches carry that contract and are the source of truth for harness proof; upstream PR merge state
does not gate local integration. See the checked-in [roadmap](specs/artifacts/planning/openmrs-dual-provider-parity-roadmap.md),
[status](specs/artifacts/planning/openmrs-dual-provider-parity-roadmap-status.md), and
[upstream inventory](specs/artifacts/planning/openmrs-dual-provider-upstream-inventory.md).

## How the docs fit together

| What you need | Where to go |
|---------------|-------------|
| Visual project overview and navigation | [Public docs site](https://pmanko.github.io/clinical-ai-validation-harness/) |
| Roadmap — what is planned, why, and in what order | [Feature roadmap canvas](https://pmanko.github.io/clinical-ai-validation-harness/#/canvas/specs/roadmap) |
| Development operating plan — lanes, gates, launch sequence | `specs/artifacts/lanes/` (in-repo) |
| Validation evidence model and evaluation methodology | [Validation research canvas](https://pmanko.github.io/clinical-ai-validation-harness/#/canvas/specs/artifacts/canvases/validation-research) |
| Current priority operator walkthrough | [Feature 002 quickstart](https://github.com/pmanko/clinical-ai-validation-harness/blob/main/specs/002-openmrs-demo-data-2-8-remap/quickstart.md) |
| Harness foundation and control-plane detail | [Feature 001 spec](https://github.com/pmanko/clinical-ai-validation-harness/blob/main/specs/001-harness-control-plane-foundation/spec.md) |
| Catalyst product pathways and selected milestone | [Catalyst product roadmap status](specs/artifacts/planning/catalyst-product-roadmap-status.md) |
| All planning artifacts, canvases, and research docs | [specs/artifacts/](https://github.com/pmanko/clinical-ai-validation-harness/tree/main/specs/artifacts) |
| Superseded pre-hub cloud guide | [docs/cloud-deploy.md](https://github.com/pmanko/clinical-ai-validation-harness/blob/main/docs/cloud-deploy.md) |

The public docs site auto-deploys from `main` and publishes the public-facing surface — this README and the visual canvases. The detailed feature specs, plans, briefs, and per-lane dossiers are dev-internal: they live in the repo (under `specs/`), not on the published site. Browse the site locally with `cd site && npm install && npm run dev` (opens at `http://127.0.0.1:4321/clinical-ai-validation-harness/`).

## Milestone names and IDs

Human-facing docs use plain names. IDs appear in parentheses on first use and inside technical specs.

| Plain name | Roadmap ID | Feature folder | Status |
|-----------|-----------|----------------|--------|
| Harness foundation | M0 | `001` | Complete |
| OpenMRS demo-data remap | M1 | `002` | Complete |
| Validation spine | M2 | `006` | In progress (validation-harness MVP; runner/report/feedback shipped — see lane L3) |
| Real adapter entrypoints | M3 | `004` | In progress |
| med-agent-hub service | F005 | `005` | Shipped as the configured profile-driven provider; Catalyst uses its shared profile schema and named-role executor |
| LLM config overrides | F007 | `007` | Superseded by explicit provider/profile configuration |
| med-agent-hub MCP tools | F010 | `017` | Superseded; dead MCP/A2A runtime removed |
| ChartSearchAI model gateway | F008 | `008` | Bundled and configured-Hub providers preserved behind the [dual-provider roadmap](specs/artifacts/planning/openmrs-dual-provider-parity-roadmap.md) |
| Clinical knowledge base | F009 | `009` | [Brief + research](https://github.com/pmanko/clinical-ai-validation-harness/blob/main/specs/artifacts/planning/clinical-kb-brief.md) |
| Retrieval evaluation | M4 | `010` | Planned |
| Catalyst supervised reporting | M10 | `008` | Query/workbench foundation accepted; Superset import spike implemented; Dashboard Builder MVP open |
| Answer, citation, and abstention | M5 | `012` | Planned |
| Safety and red-team | M6 | `013` | Planned |
| Clinician governance review | M7 | `014` | Planned |
| Querystore parity testbed | M8 | `015` | Planned |
| Cross-project expansion | M9 | `016` | Planned |

> **Note on feature 002 internal phases:** Work inside the OpenMRS demo-data remap (M1 / `002`) uses implementation sub-labels `M2-A` through `M2-Z` in detailed feature docs. These are internal planning labels for that feature's phases — not related to roadmap milestone M2 (Validation spine).

> **Note on F-prefixed IDs and non-monotonic slugs:** F005, F007, F008, F009, F010 are features inserted into the roadmap after the M0–M10 sequence was authored. The validation spine (M2) shipped as slug `006` (validation-harness MVP) — the earlier `003` slug was never created. `007` is LLM config overrides (F007); `017` is the med-agent-hub MCP tools (F010). The Roadmap IDs (M0–M10, F005–F010) carry the semantic ordering anchor; folder slugs are filesystem identifiers and may be non-monotonic. See [`specs/roadmap.canvas.tsx`](https://pmanko.github.io/clinical-ai-validation-harness/#/canvas/specs/roadmap) for the dependency DAG.

> **Note on M10 and repository ownership:** The harness is the umbrella repository. Catalyst and Med-Agent Hub are pinned as sibling submodules under `targets/`; Catalyst contains no nested Git submodules. The umbrella runner builds the pinned Hub sibling directly. Standalone Catalyst may clone the same unmodified Hub commit as a disposable fallback, alongside its disposable OpenELIS and FHIR Data Pipes checkouts.

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
site/          Static-site build of the README and canvases (public surface); auto-deployed to GitHub Pages
targets/       Pinned submodule checkouts of the four target projects
```

## Quickstart

**Requirements:** Python 3.11+, `uv`, Docker / Docker Compose, Git.

## Catalyst query workbench and dashboard direction

Initialize the two sibling targets without `--recursive`:

```bash
git submodule update --init targets/catalyst targets/med-agent-hub
```

The local sandbox brings up OpenELIS, HAPI FHIR, FHIR Data Pipes, the analytics
database, Catalyst Gateway, the pinned sibling Hub, and the sidecar UI; an
explicit seed command loads the synthetic multi-analyte cohort. Hub owns the
shared Catalyst query profile, prompts, role models, and model knobs. Gateway
owns catalog/context assembly, SQL lint and policy, writer/reviewer
orchestration, execution, and query-version lineage.

The prior final-pin manual workbench was accepted on 2026-08-04 after a 12/12 real-model
matrix, independent PostgreSQL/gold comparisons, bounded failure/recovery, and
actual keyboard-only plus 200%-browser-zoom checks. The deterministic
Playwright notebook path preserves the corresponding focus and reflow boundary.
The current Hub-owned profile migration requires a fresh exact-pin live gate
before dashboard implementation resumes.

The selected next product milestone is the Superset-backed Dashboard Builder:
promote governed executions through immutable Dataset, Widget, and multi-widget
Dashboard drafts, then publish a deterministic native ZIP to a shared local
outbox for import by pinned Superset 6.1.0. Catalyst owns the iterative desired
configuration in this one-way MVP; Superset renders it. The prototype's Ask
shell integrates the accepted query notebook without removing its profile/model evidence, single
SQL editor, manual versions, Validate/Run, diagnostics/results, contextual
follow-up, history, refresh, or New session behavior; only the dataset-preview
presentation moves into the builder's Dataset tile/review panel. Multi-source/lossless
onboarding, targeted SQL repair, session-export/comparative experiments,
evidence-linked narratives, and production security are parallel pathways, not
sequential prerequisites. Superset REST API publication, embedded viewing,
cross-system reconciliation, model-generated visualization specifications,
sharing, scheduling, automatic refresh, and production access control remain
outside this milestone.

The current table-only bundle/import implementation is a Superset import spike,
not a smaller Dashboard MVP. The MVP remains open through real-profile query
proof, the actual multi-widget experience, native Superset import, PostgreSQL
reconciliation, accessibility/evidence gates, and explicit user acceptance.

The P5 Catalyst report is published at
[reports.openclinai.org/catalyst-t094-release](https://reports.openclinai.org/catalyst-t094-release/):
13/13 scenario repetitions and 411/411 deterministic assertions passed, with
three advisory judge passes retained alongside record-level evidence. PR #43
merged green at `136067a`; optional future evaluation expansion is parallel and
is not a Dashboard MVP implementation dependency.

Start the local OpenAI-compatible router on port `1234`; it must advertise the
exact `google/gemma-4-e4b` writer and `qwen2.5-14b-instruct-mlx` reviewer model
IDs. The only supported manual path is then:

```bash
make catalyst-mvp-external
```

That first-time path starts the isolated stack and explicitly loads the demo
OpenELIS → FHIR → analytics pipeline. Day-to-day restarts retain the stack's
named Docker volumes and do not reload that data:

```bash
make catalyst-mvp-restart
```

Use `make catalyst-mvp-seed` only to deliberately reload the fixture and
`make catalyst-mvp-reset` only to discard the isolated data state.

When a Catalyst dashboard bundle is published, inspect or import it into the
same isolated Superset instance with `make catalyst-superset-status` and
`make catalyst-superset-import`. The latter records the exact Catalyst commit
in its durable local receipt; it does not reload OpenELIS or FHIR data.

The external model URL defaults to `http://host.docker.internal:1234`; override
`MVP_EXTERNAL_ROUTER_URL` only when the real router is elsewhere. Startup fails
if the router cannot advertise both configured profile models. Open
`http://localhost:13000` after the health gate succeeds. Every `make
catalyst-mvp-*` target runs the isolated stack
(`compose/catalyst-mvp-isolated.override.yml`), which publishes the UI on
`13000` and the gateway on `18000` so they cannot collide with another stack on
this host. `3000` is Catalyst's own default, which you get only when running
its compose directly from `targets/catalyst`. `CATALYST_UI_PORT` overrides
either. The profile picker shows only available Hub-owned query profiles and
their exact writer/reviewer models; see
[Catalyst manual LLM testing](docs/catalyst-manual-llm-testing.md). This is
demo-data engineering evidence, not a clinical-quality claim.

After the real-model health gate passes, run the versioned validation suite
against that live Gateway. Hub discovery records the exact model and prompt
configuration used by each role.

```bash
uv run python scripts/run-catalyst-validation.py \
  --suite datasets/validation/catalyst/catalyst-mvp-v1.json \
  --gateway-url http://127.0.0.1:18000
```

Run evidence is written under `artifacts/catalyst-validation/<run-id>/`.

The iterative-query notebook uses the same top-level CLI and reporting archive
as ChartSearchAI. By default it independently checks both the selected query
execution and the hand-authored gold query against read-only PostgreSQL:

```bash
uv run harness-cli catalyst run \
  --suite datasets/validation/catalyst/catalyst-notebook-t094-v1.json

uv run harness-cli catalyst report \
  artifacts/catalyst-notebook-validation/<run-id>
```

After three judge passes are finalized, stage or publish the report and its
relative evidence links with the family-aware publisher:

```bash
scripts/publish-report.sh catalyst \
  artifacts/catalyst-notebook-validation/<run-id> \
  catalyst-t094-release "Catalyst T094 validation"
```

Use `PUBLISH_DRY_RUN=1 REPORTS_ROOT=<temporary-directory>` to render, index,
and verify a publication without cloud or VM access. The legacy
`scripts/validate-publish.sh <run-id> ...` command remains a ChartSearchAI
compatibility wrapper.

```bash
# 1. Install uv (Python environment manager) if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Set up the Python environment and install all dev dependencies
make setup

# 3. Bring up the OpenMRS Reference Application stack through its stable launcher
make up

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

For the full OpenMRS demo-data remap workflow, see [specs/002-openmrs-demo-data-2-8-remap/quickstart.md](https://github.com/pmanko/clinical-ai-validation-harness/blob/main/specs/002-openmrs-demo-data-2-8-remap/quickstart.md).

## ChartSearch operations

The approved product shape is **two providers behind one ChartSearchAI experience**. A standard
OpenMRS installation defaults to bundled ChartSearchAI inference. Deployments that configure
med-agent-hub may expose it as an additional provider; changing provider begins a new conversation.
The hub remains a supported direct service and owns its own profile/stage, temporal, review,
grounding, and In-Depth behavior. It is not a required dependency for bundled operation.

The existing hub-relay integration and local commands remain useful for development while the
dual-provider rebuild is in progress, but they do not define the final provider configuration.
Use the roadmap's product-proof gates before treating either path as the released canonical UI.

```bash
# Development helper for the hub path. It does not replace bundled inference or
# declare the hub the default provider in a fresh OpenMRS installation.
make chartsearchai-local

# Useful focused operations:
./scripts/chartsearchai-local.sh --check  # validate prerequisites without starting services
make local-stack-up                  # fast resume: no builds; waits for the existing stack
make local-stack-down                # stop Compose + its managed router; keep named volumes
make openmrs-source-pair-build        # build/stage current Querystore, then ChartSearchAI
make openmrs-source-pair-test         # install pinned Querystore, then test/build pinned ChartSearchAI
make llama-router-models             # inspect raw models behind the hub
make chartsearch-build               # same ordered pair build; ChartSearchAI depends on current Querystore API
make med-agent-hub-up                # (re)start the hub on its own
make chartsearch-configure           # write the fixed hub endpoint; profile discovery supplies the default
make chartsearch-doctor              # verify router, hub profile metadata, and module status

# Retrieval backend — querystore's CQRS read store tier
make chartsearch-backend BACKEND=elasticsearch   # or lucene | mysql
```

`make chartsearchai-local` remains the canonical first-run and source-change workflow: it
builds or verifies artifacts, configures the product path, and exercises the real integration.
The `local-stack-*` targets are intentionally narrower daily helpers. They require a configured
`.env.chartsearch` and already-built images/artifacts, start Docker Desktop when supported, and
fail rather than silently rebuilding or reporting an unready stack as healthy. Teardown preserves
the Compose named volumes and only stops a llama-router recorded as managed by this checkout.

**Provider and profile selection.** The final ESM shows no picker with bundled-only configuration.
With hub configured, it shows a provider choice first and the provider's supported profile/mode choices
second. Unready configured providers remain visibly disabled; the UI never invents raw model choices or
silently falls back to another provider.

**Cloud.** The older GCE/LM Link workflow predates the hub-only product boundary and is not the canonical M3
proof path. Use the local workflow above while the cloud scripts are reconciled with the same hub profile API.

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
