# Quickstart: Experiment Readiness and Evidence

Install the harness, select supplied scenario/fixture and adapter settings, and
prepare the target through its product-owned or
[umbrella workflow](https://github.com/pmanko/openclinai.org). Follow the
[README quickstart](../../README.md#run-an-experiment) and CLI `--help` for clinical
and Catalyst commands. No target registry, workspace synchronization or profile
lifecycle command is part of this runtime contract.

Before claiming evidence, check selected transport compatibility, capabilities,
credential references and input completeness. `validate check` is a configuration
check, not live health or successful clinical validation. Readiness must state
its limits and reasons.

Inspect the run manifest/events and feature evidence. Missing provenance is
explicit, not filled by a Git/source lookup. Copy the complete run directory and
regenerate its report without original dataset directories or live services.
Review record-level evidence, caveats and rationale, not just success counts.

Use [Feature 006's plan](../006-validation-harness-mvp/plan.md) for runtime isolation
acceptance and [the metadata guide](../artifacts/planning/metadata-schema.md) for
field meanings. Offline artifacts require privacy review before publication.
