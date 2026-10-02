# Configuring clinical comparison arms

## Owners

[ChartSearchAI](https://github.com/pmanko/openmrs-module-chartsearchai/blob/harness-integration/docs/adr.md)
owns bundled inference and configured Hub provider behavior. Selecting a Hub
profile is distinct from choosing a provider. A bundled installation does not
require Hub, and unavailable providers must not silently become another arm.

[Med Agent Hub](https://github.com/pmanko/med-agent-hub) owns profiles, role models,
prompts, stage composition, sampling settings and supported low-level experiment
legs. [QueryStore](https://github.com/pmanko/openmrs-module-querystore/blob/harness-integration/docs/rest-api.md)
owns its context API. Read these product contracts before changing target
configuration; do not use this harness guide as a second product specification.

The [OpenClinAI umbrella](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md)
owns checkouts, pins, shared environments, model-serving configuration and
service lifecycle. Its [scripts](https://github.com/pmanko/openclinai.org/tree/main/scripts)
run from the umbrella root. Independently prepared remote targets need no
umbrella or local product checkout.

## Experiment inputs

Configure comparison arms using the selected target endpoint, supported
provider/profile, authored scenarios and fixtures, reference date, evaluator
settings, supplied provenance and output directory. Label direct Hub/model arms
as experiments, not ChartSearchAI product acceptance. Do not derive model or
prompt identity by scanning `targets/` or invoking Git.

Freeze the actual configuration and required input bytes with the run. Record
supplied or observed model/profile identity, prompt/configuration digests when
available, and explicit unavailable fields. A profile name or repository URL
alone does not prove which model or revision served a response. Preserve
conflicting observations rather than overwriting them.

Material model, prompt, retrieval or evaluation changes require reviewed change
context and focused diverse scenarios, including missing evidence, unsupported
claims, abstention and API failure. Run deterministic checks before optional
model judging. Keep judgments attributed separately and capture reviewer
rationale. Service restart, source preparation and release checks are separate
caller actions, never effects of `validate run`.

[Feature 006](../../006-validation-harness-mvp/spec.md) and the
[metadata guide](metadata-schema.md) own reusable execution and provenance.
Reports regenerate from captured run artifacts without targets or product files.
