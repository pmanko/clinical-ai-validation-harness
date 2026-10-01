# Plan: Independent Modular Validation Runtime

**Spec**: [spec.md](spec.md) | **Direction**: current implementation and verification
obligations; no completion claim is made by this plan.

## Design and ownership

Keep experiment-specific loaders, adapters, capture, evaluators, review and reports.
The caller prepares endpoints/model services and supplies inputs, safe connection
settings, provenance and output location. Remove the Python workspace target
registry, Git/submodule lookups and pin gates from execution. Remove model-router
process control and local product/model/prompt source scans; record supplied or
API-observed facts and explicitly missing metadata instead.

Use the existing clinical and Catalyst interfaces and file-first artifact spine.
Freeze scenario/suite/configuration content and required clinical fixtures with
run-local safe references and digests. Preserve response and trace identity,
deterministic findings, separate optional model judgments and reviewer rationale.
Reports consume captured artifacts only, without original data roots or services.

[Spec 001](../001-harness-control-plane-foundation/spec.md) retains common readiness,
identity and evidence requirements. The [metadata guide](../artifacts/planning/metadata-schema.md)
and [manifest contract](../001-harness-control-plane-foundation/contracts/run-manifest.schema.yaml)
define common meanings; emitters own executable schemas. Product contracts linked
from the feature own API and provider behavior. Product gitlinks and preparation
operations move directly to the umbrella in coordinated slices; website relocation
and Feature 008 ownership consolidation remain separate work.

## Constitution check

- Independent runtime: installation and selected experiments require no Git,
  submodules, pins, product sources or umbrella; no service lifecycle or delivery gates.
- Real paths: doubles test mechanics; real interfaces support product/clinical claims.
- Determinism: reviewed configuration/mapping inputs are frozen; proposals remain advisory.
- Evidence: record-level support and rationale; explicit unknowns and conflicts;
  final output is separate from review-only drafts.
- Provenance: nullable revisions, versioned schemas, canonical OTel names and
  safe references; no metadata discovery through source scans.
- Safety/governance: no secrets/private reasoning; clinical sharing is reviewed;
  material model/prompt/retrieval/mapping changes carry impact/residual-risk context.

These controls support inspectable, portable experiment evidence, not release
approval. Re-check compliance after runtime design and emitter changes.

## Implementation and verification

1. Remove workspace registry/Git/pin prerequisites from clinical and Catalyst
   collection and CLI imports. Validate selected configuration/capabilities only.
2. Remove model-router lifecycle and source-based metadata discovery. Test absent
   model/prompt/revision metadata and separately supplied/observed identities.
3. Capture inputs and bounded fixtures needed by evaluators/reports. Preserve
   completeness errors, response/trace correlation, review-only evidence and resume ancestry.
4. Regenerate clinical and Catalyst reports from copied packets after removing
   original authored inputs, product trees and service access. No fallback reads.
5. Run focused adapter/provenance/report tests, then `uv run pytest`. Exercise an
   installed environment without Git or product source access for both paths;
   record commands, results and any remaining limitations with implementation evidence.
6. Verify product behavior through real configured interfaces separately. Do not
   equate unit tests, doc checks or umbrella workspace checks with deployed acceptance.

Foundation task IDs remain in [Spec 001 tasks](../001-harness-control-plane-foundation/tasks.md).
Do not duplicate their status here. Implementation findings and dated test evidence
must distinguish code changes, local verification, isolation acceptance and publication.
