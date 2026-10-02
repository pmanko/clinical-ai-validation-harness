# Plan: Experiment Readiness and Evidence Foundation

**Spec**: [spec.md](spec.md)

Spec 001 owns readiness/configuration/evidence semantics; Feature 006 owns the
[first standalone runtime implementation and verification](../006-validation-harness-mvp/plan.md).
Do not treat the old directory slug as authority for workspace control duties.

## Design

Use experiment-specific configuration and loaders. Check selected transport,
connection, capabilities, credential references and inputs. Record reasons and
check limits; do not initialize a global workspace registry or prepare targets.

Record supplied/observed provenance with nullable unavailable revisions. Preserve
input bytes/digests, response/trace evidence and review rationale under the run
output boundary. Reports consume captured artifacts only. Executable feature
schemas and validators must agree with the
[manifest contract](contracts/run-manifest.schema.yaml) and
[metadata meanings](../artifacts/planning/metadata-schema.md).

## Constitution gates

- Independent runtime: no Git, pins, product source or umbrella requirement;
  caller owns preparation; no model-service process control.
- Real paths: configured product interfaces establish product acceptance; doubles
  only establish runner mechanics.
- Deterministic inputs: reviewed scenario/fixture/configuration content is frozen.
- Evidence and metadata: record-level support, explicit missing facts, separately
  attributed judgments and versioned safe evidence references.
- Safety: no secret/private-reasoning disclosure; review-only drafts do not become
  final evidence. Material changes have impact/residual-risk review context.
- Tests: positive/blocked readiness, missing metadata and portable offline reports
  for clinical and Catalyst paths; implementation status requires test evidence.

## Acceptance and coordination

[Tasks](tasks.md) records this family's remaining verification obligations. Runtime
results and completion belong in Feature 006's plan, not copied status tables here.
Topology, umbrella workspace operations, website relocation and Feature 008
consolidation are separately coordinated. Product contracts remain product-owned.
