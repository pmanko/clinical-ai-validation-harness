# Data Model: Experiment Readiness and Evidence

These are semantic entities, not a global registry file or a new CLI API.
Concrete input loaders and emitted schemas remain owned by their experiment module.

## Experiment configuration

- Selected adapter/transport and target project/component identity.
- Connection/execution settings and required capabilities.
- Credential references resolved at runtime, never captured secret values.
- Scenario/fixture inputs, evaluation/review settings and output location.

Validate only selected experiment dependencies. Local and remote targets share
this boundary; neither requires a local product repository or workspace profile.
The caller prepares the target and any model services.

## Readiness assessment

- Selected experiment and target identity.
- Ready, blocked, scaffolding-only, fixture-only or unavailable classification.
- Checked capabilities/connectivity and the limits of configuration-only checks.
- Missing prerequisites and decision rationale.

Readiness is not product/release acceptance. An unknown revision does not block a
capable target. No checkout, pin, working-tree or service startup state is required.

## Run provenance

`run_manifest.json` retains run/project/component/time/schema identity,
`evidence_status`, nullable `git_sha`, `target_provenance`, dataset/mapping and
applicable model/provider/prompt provenance. See the
[shared metadata guide](../artifacts/planning/metadata-schema.md).

Each target entry records supplied or observed identity with origin, including
revision, image/deployment identity and runtime configuration when available.
Missing facts are explicit. Caller assertions and target observations remain
distinguishable; disagreement is evidence, not a pin-enforcement failure. No Git
lookup, source scan, mandatory path, reviewed revision or override-promotion policy
is part of this model.

## Evidence packet

- Frozen comparison/suite, scenarios, configuration and required clinical fixtures.
- Input identities/digests, including missing expected inputs.
- Requests, responses, traces and bounded source/clinical evidence.
- Deterministic findings, separately attributed model evaluation and human review.
- Review identity, time, rationale and links to exact evaluated input.
- Generated report and evidence completeness/missing-input disclosures.

References are contained relative paths within the run directory. Copying the run
preserves report inputs. Reports cannot fall back to current authored datasets,
product source or live services. Review-only drafts stay separate from final
answer evidence. Operating metadata is not a clinical record database.

## OTel alignment

Use `gen_ai.provider.name` and `gen_ai.operation.name` when available. Relevant
agent/tool/data-source attributes may be retained from observed traces. Record
schema/convention identity; do not emit `gen_ai.system` or infer missing fields
from source code. Trace correlation must reject explicit identity mismatches.
