# Feature 008: Catalyst experiment implementation plan

The [specification](spec.md) defines the evidence to collect. The
[comparison protocol](../catalyst-program-roadmap.md) owns scenarios/model setups
and reader interpretation. [Tasks](tasks.md) records the harness work.
Product milestones live in [Catalyst](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md#implementation-direction); cross-project order and
acceptance live in [OpenClinAI](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#6-catalyst-delivery).

## Implementation

1. Consume configured Gateway endpoints, authentication, source/profile settings,
   scenarios and output locations. Targets can be prepared independently; no Git,
   product checkout, component pin, build or deployment is a runner prerequisite.
2. Capture actual context and outcomes through the product interfaces. Ready
   selected SQL executes once; clarification/unsupported outcomes execute none.
   Wrong queries/database errors remain observations with their full evidence.
3. Capture static reference facts or reviewed expected responses, scenario/rubric
   bytes, responses, bounded rows, traces and supplied/observed provenance in the
   run directory. Never populate missing provenance by reading a product tree.
4. Expose a complete per-case reader packet and explicit incomplete-collection
   state. Reader runs are deliberate, with actor, input identity and rationale.
5. Produce portable offline reports using captured run-local artifacts only.
   [Feature 006](../006-validation-harness-mvp/plan.md) owns shared isolation and
   report mechanics; do not create a parallel implementation.

## Verification

Use focused runner/adapter/evidence tests for configuration, failed collection,
missing metadata and portable report reconstruction. A source archive or installed
wheel must work without Git or product sources. Use real prepared product targets
for claims about their behavior, with results linked to the captured revisions
and configuration. No direct analytics database, reference replay, automatic
factual-equivalence score, mandatory repeated model run or second reader gate.

## Comparison readiness

Use the selected accepted source schema to prepare static references. Review the
references and reader packet before paid model collection. Any concrete missing
semantic need returns to the owner before adding a minimal source-owned view.
Run the fixed suite once per selected team and report incomplete batches honestly.
The owner reviews the resulting report; a model preference is optional.

The [selected-baseline plan](https://github.com/pmanko/clinical-ai-validation-harness/blob/9b5b87ef67397fe7705b37467b98d3550c8d0e47/specs/008-catalyst-query-workbench/plan.md) and
[task history](https://github.com/pmanko/clinical-ai-validation-harness/blob/9b5b87ef67397fe7705b37467b98d3550c8d0e47/specs/008-catalyst-query-workbench/tasks.md) preserve dated implementation/run evidence.
They do not schedule current product or environment work.
