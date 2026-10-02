# Validation runner architecture

The harness runs configured experiments against prepared interfaces. It owns
adapters, scenario replay, input/output/trace capture, evaluation, human review
and offline evidence reports. [Feature 006](../../006-validation-harness-mvp/spec.md)
owns requirements and its [plan](../../006-validation-harness-mvp/plan.md) owns
implementation/isolation verification. The [metadata guide](metadata-schema.md)
defines shared provenance meanings.

The caller supplies endpoint/adapter settings, scenarios and fixtures, evaluation
settings, target provenance and output location. Readiness checks verify these
inputs and required capabilities, not Git, submodules, product pins or sources.
No target build, deployment, checkout or model-service process control occurs
inside experiment execution. [OpenClinAI](https://github.com/pmanko/openclinai.org/blob/main/specs/architecture.md)
owns workspace management and website publication.

Clinical collection uses the real ChartSearchAI API with explicit supported
provider/profile selection. Direct Hub/model arms are labeled experiments.
Catalyst collection uses its prepared Gateway; Catalyst owns SQL workflow and
connection execution. [API adapters](../../../adapters/README.md) link current
entry points and product contracts, not command-plan wrappers.

Freeze required input bytes, configuration without secrets, bounded evidence,
responses, traces, evaluations and review rationale in the run packet. Target
identity is supplied or API-observed; missing fields and conflicts stay explicit.
Optional model judges are separately attributed and cannot override deterministic
safety findings. Reports regenerate from the copied packet without targets,
evaluators, authored dataset directories or product checkouts.

Test doubles verify runner mechanics. Product and clinical acceptance require
actual interfaces and record-level evidence. Local isolation tests do not prove
publication, release or deployed-runtime acceptance.
