# Clinical AI validation harness

Run configured clinical AI experiments, capture their inputs and outputs, evaluate
results and produce reviewable evidence. The harness supports clinical-answer
comparisons through ChartSearchAI or explicitly labeled Med Agent Hub experiments,
and SQL-workflow validation through Catalyst.

The goal is evidence a reviewer can inspect: which records supported an answer,
which SQL actually ran, what failed, and why a reviewer accepted or rejected a
result. Aggregate scores alone are not clinical validation.

## Run an experiment

Use Python 3.11+ and `uv` to install from this repository:

```sh
uv sync --extra dev
uv run harness-cli --help
```

Prepare your target through its own deployment workflow, then supply its connection
settings and experiment inputs. The harness's runtime contract is an independent
runner: the caller owns target preparation; validation does not require product
source checkouts, Git or workspace pins. Standalone isolation verification is
tracked in the [runtime plan](specs/006-validation-harness-mvp/plan.md), separately
from this documentation alignment and product acceptance.

For the included clinical demo, configure `CHARTSEARCH_BASE_URL`,
`CHARTSEARCH_ADMIN_USER` and `CHARTSEARCH_ADMIN_PASSWORD` in your environment. The
prepared OpenMRS service must contain the reviewed patient fixtures and advertise
the selected profile (`single-e4b-checked` in the current `demo` set).

```sh
uv run harness-cli validate check demo --data-root datasets/validation
uv run harness-cli validate run demo --data-root datasets/validation --output-dir artifacts/validate
```

`validate check` checks transport/configuration compatibility, not live health or
clinical correctness. `validate run` contacts the target, creates chat sessions,
uses configured model services and writes a run directory. It may take substantial
time and may incur provider charges. Use authorized demo/de-identified data;
remote endpoints receive the selected clinical inputs.

For Catalyst, choose a reviewed suite and an already-running Gateway:

```sh
uv run harness-cli catalyst run --help
uv run harness-cli catalyst report --help
```

Use each command's `--help` for the supported input/settings flags. Catalyst
collection requires a caller-prepared source and reviewed suite; it does not
provision the Gateway or its database. Cross-project target setup belongs to the
[OpenClinAI umbrella](https://github.com/pmanko/openclinai.org), not this runner.

## Inspect and review evidence

Each run records `run_manifest.json`, `events.jsonl` and feature-specific evidence
such as `results.jsonl`, captured inputs, traces and review records. Provenance is
supplied by the caller or observed from the target; unknown revisions/model details
are recorded as missing, not substituted with workspace pins.

Reports present captured evidence for human review. Optional model judgments are
separately attributed and do not override deterministic safety findings. Final
answers and In-Depth output remain visible with their caveats; rejected or changed
drafts are labeled separately and excluded from final evidence/judge input.

To regenerate a clinical report from an existing packet:

```sh
uv run harness-cli validate report --run-dir artifacts/validate/your-run-id
```

Replace `your-run-id` with the emitted run directory. Catalyst report inputs are
shown by `harness-cli catalyst report --help`.

Copy the complete run directory for offline report regeneration. Reports must use
that captured input set, not current product sources, live services or the author's
original dataset directory. Offline artifacts may still contain sensitive clinical
evidence: review and redact before sharing. OpenClinAI publication consumes selected
harness outputs through separate umbrella-owned tooling.

## Documentation and ownership

| Need | Reference |
| --- | --- |
| Operator steps | [Run an experiment](#run-an-experiment) and CLI `--help` |
| Scenarios, evaluation, review and isolation acceptance | [Feature 006](specs/006-validation-harness-mvp/spec.md) and [plan](specs/006-validation-harness-mvp/plan.md) |
| Readiness, configuration and evidence boundaries | [Spec 001](specs/001-harness-control-plane-foundation/spec.md) |
| Common artifact/provenance semantics | [Metadata guide](specs/artifacts/planning/metadata-schema.md) |
| Governance | [Constitution](.specify/memory/constitution.md) |
| Contributor/agent instructions | [AGENTS.md](AGENTS.md) |
| Cross-project priorities and implementation status | [OpenClinAI roadmap](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md) |
| Component boundaries | [OpenClinAI architecture](https://github.com/pmanko/openclinai.org/blob/main/specs/architecture.md) |

Product contracts live with
[ChartSearchAI](https://github.com/pmanko/openmrs-module-chartsearchai),
[QueryStore](https://github.com/pmanko/openmrs-module-querystore),
[Med Agent Hub](https://github.com/pmanko/med-agent-hub) and
[Catalyst](https://github.com/DIGI-UW/catalyst-ai).
The harness defines experiments, evidence, scoring and review—not product behavior.

The [OpenClinAI workspace](https://github.com/pmanko/openclinai.org) provides
component version selection, checkouts, builds, deployment and release coordination.
It also contains the OpenClinAI website and publication tooling.

## Contribute

Behavioral changes need focused tests, diverse failure/abstention cases, versioned
metadata and record-level evidence. Accepted data mappings/transforms are reviewed
and deterministic; LLM proposals remain advisory. Material model, prompt,
retrieval, mapping or pipeline changes require a change record describing the
validation protocol, impact and residual risk.

```sh
uv run pytest
```

Unit tests establish runner mechanics. Product, deployed-runtime and clinical
acceptance require their own real-path evidence.
