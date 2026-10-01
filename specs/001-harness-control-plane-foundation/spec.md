# Feature 001: Experiment Readiness, Configuration and Evidence Foundation

**Created**: 2026-05-12
**Current scope**: readiness, experiment configuration, fixture/endpoint identity
and evidence boundaries. Implementation/isolation verification is tracked in
[Feature 006's plan](../006-validation-harness-mvp/plan.md), not implied complete
by this specification.

## User scenarios and testing

### US1 — Identify the configured validation surface (P1)

An operator can identify the selected adapter, target endpoint/execution interface,
required capabilities and whether a run exercises a real product or scaffolding.

**Independent test**: Supply experiment settings with a real configured endpoint,
a test double or a missing target. Readiness states the surface and reasons without
reading Git, a workspace catalog, product pins or local product sources.

**Acceptance**: A reachable capable target can be used; missing capabilities or
credentials are explained as blocked; fixture-only/test-double output is labeled
and cannot establish product acceptance. A missing source revision is disclosed
but does not itself block execution.

### US2 — Select experiment connection and input settings (P2)

An operator chooses local or remote target settings, scenario/fixture inputs,
credential references and output location before collection.

**Independent test**: Use two supplied configurations with different endpoints and
output roots. Checks resolve only the selected settings; failures identify missing
inputs/services without starting or preparing a target.

**Acceptance**: Credential values remain outside captured metadata; unsupported
transport/configuration combinations fail explicitly; target preparation stays
with the caller. No fixed local/VM profile catalog is required.

### US3 — Preserve evidence boundaries (P3)

A reviewer can locate metadata, bounded clinical evidence, reports and review
rationale, distinguish generated outputs from curated fixtures, and move a run
packet for offline reporting.

**Independent test**: Validate artifact identity/path containment and regenerate a
report from a copied run directory after removing original inputs and services.

**Acceptance**: Manifests/events reference run-local evidence; missing inputs remain
visible; record-level claims link to records and rationale rather than counts.

## Functional requirements

Retained IDs identify current validation responsibilities; numbering gaps are not
new requirements.

- **FR-002**: Each configured target MUST identify the project/component, adapter,
  connection/execution surface and readiness for the selected experiment.
- **FR-003**: State the real product interface required for product acceptance.
- **FR-004**: Distinguish real-path readiness, scaffolding, fixture-only and
  unavailable states without equating readiness with successful validation.
- **FR-005**: Users MUST be able to compare supplied local/remote experiment
  configurations before treating a run as evidence.
- **FR-006**: Configuration MUST declare required connections/capabilities,
  scenario/fixture inputs, credential references and output location.
- **FR-007**: Readiness MUST identify missing target capabilities, services,
  credentials and non-evidence states before collection. Checks MUST NOT prepare
  targets or control service processes; configuration-only checks state that limit.
- **FR-008**: Define output boundaries for manifests, events, reports, review
  records, captured clinical inputs, curated fixtures and durable spec artifacts.
- **FR-009**: Identify real project interface use versus non-evidence scaffolding.
- **FR-010**: Preserve record-level clinical/mapping/retrieval/model/review evidence
  and rationale explaining why it supports each decision.
- **FR-011**: Emit versioned metadata/provenance for runs, transforms, retrieval,
  model calls, responses, evaluation and review where applicable. Provenance is
  supplied or observed, not derived from Git or enforced against workspace pins;
  unavailable revision/model/prompt metadata MUST be explicit and nullable.
- **FR-012**: Cover diverse ambiguous, missing, unsupported, abstention and failure
  scenarios where relevant, not only tuning fixtures.
- **FR-024**: Use `gen_ai.provider.name`, not `gen_ai.system`, and applicable
  `gen_ai.operation.name`, agent/tool/data-source attributes. Record the emitting
  schema/convention identity; unavailable model details remain explicit.

## Success criteria

- **SC-001**: An operator identifies selected targets, their interfaces and evidence
  classification in under ten minutes from configuration/readiness documentation.
- **SC-002**: Every supported experiment distinguishes real-path, fixture and
  scaffolding evidence.
- **SC-003**: Every selected configuration declares connection/capability, credential
  reference, input and output expectations without a required workspace catalog.
- **SC-004**: A reviewer distinguishes ready, blocked and scaffolding-only states
  without implementation-internal inspection.
- **SC-005**: Each supported adapter/configuration mode has positive and blocked
  cases, including required-credential/capability failure where applicable.
- **SC-006**: Consumers reuse these readiness/evidence categories and the shared
  metadata contract rather than redefining a global target registry.
- **SC-007**: Catalyst readiness depends on its configured Gateway capabilities,
  not the location, existence or revision of a local source checkout.
- **SC-012**: Emitted manifests use canonical OTel GenAI field names and declare
  unavailable fields explicitly.

## Data, provenance and safety

The [data model](data-model.md) and
[manifest contract](contracts/run-manifest.schema.yaml) define this
family's foundation. The [shared metadata guide](../artifacts/planning/metadata-schema.md)
owns common meanings; feature emitters own executable schemas.

Capture required scenario/configuration/fixture bytes and digests in run artifacts.
Store bounded clinical evidence separately from operating metadata, with safe
relative references. Keep credentials, private reasoning and private deployment
paths out of publishable artifacts. Missing evidence must not turn into a passing
claim. Material criteria/pipeline changes require reviewed impact and residual-risk
context. Product and release acceptance remain explicit, separate decisions.

The caller prepares targets. Repository URLs identify product authorities; local
product source is not an input requirement. Component catalogs, pins, checkouts,
builds, environments, deployment and publication belong to the OpenClinAI umbrella.
