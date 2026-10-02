# Feature 008: Catalyst experiment specification

Feature 008 defines scenarios, observable evidence and evaluation for an already
prepared Catalyst target. [Feature 006](../006-validation-harness-mvp/spec.md)
owns the reusable runner, configured adapters and portable report mechanics.
[Plan](plan.md) and [tasks](tasks.md) cover only this harness work.

[Catalyst](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md)
owns application requirements, its [implementation register](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md#implementation-direction)
owns product milestones, and [OpenClinAI delivery](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#6-catalyst-delivery) owns assembly,
local/server verification, publication and owner acceptance. Frozen mocks and
run reports are dated evidence, not competing requirements.

## Product contracts and experiment observations

Catalyst's maintained product specification and binding design own source
configuration/discovery, query generation, context assembly, advisory validation,
editor behavior, immutable state, connection execution, Dataset/Widget/Dashboard
behavior, publication and importer receipts. The harness does not duplicate those
requirements or implement their transport. [API consumption](contracts/workbench-api.md)
and local machine schemas define the captured formats used by current consumers.

Design experiment cases around these observable boundaries:

- Record the selected source identity, explicit SQL dialect and complete readable schema
  snapshot actually supplied to the model/editor. Credentials are excluded.
- Capture complete instructions, actual model context and omitted-item reasons,
  writer/checker identities, settings and available prompt/configuration provenance.
- Exercise ready, clarification and unsupported outcomes. Ready selected SQL runs
  once through Catalyst; the other outcomes execute none and preserve prior work.
- Preserve exact selected SQL and typed parameters, advisory findings, query lineage,
  digests, bounded typed rows or the native database diagnostic and timing. Generated
  and manually corrected queries both remain valid observations.
- Capture follow-up, failure/retry, refresh and saved-query reuse evidence against the
  product-owned behavior. A successful old result must not be mistaken for execution
  of a changed query. Do not invent state acceptance from backend unit tests.
- For query-backed publication, retain the originating execution, saved objects,
  bundle and explicit importer receipt; inspect one rendered value against the
  captured originating result without a second database query. Imported Datasets
  retain file/source provenance without fabricated SQL or query executions.

The caller prepares Catalyst, sources, model services and Superset and supplies
connection settings, reviewed scenarios, evaluator settings, provenance and an
output directory. The umbrella owns selected revisions and workspace operations.
The harness records supplied or observed identity and explicit missing metadata;
it never reads gitlinks, enforces pins or scans product source trees.

## Evaluation boundary

The [program roadmap](../catalyst-program-roadmap.md) owns the reader-led model
comparison. Catalyst owns the separately scheduled future-conversation scope. Each ready
reference is authored, run and reviewed once through accepted Catalyst before
comparison. Store static expected facts; clarification/unsupported cases store
reviewed expected responses based on the actual readable schema.

Collect the same complete suite and rubric for each selected team. The harness
never reruns reference SQL, connects directly to an analytics database, computes
automatic factual equivalence, applies rankings or chooses a model team. A bad
query or native SQL error is evidence, not an automatic disqualification.

Preserve full conversation, actual model context, source/dialect/schema identity,
SQL, rows/error, static reference or expected response, frozen rubric and available
model/target provenance. One full-context reader pass is the default; retain actor,
input digest and rationale. Additional runs/readers are deliberate follow-up,
not mandatory repetition. A frontier-model reader is labeled model interpretation,
not independent human review. Incomplete collection stays visible.

[Feature 006](../006-validation-harness-mvp/spec.md) owns reusable runner execution,
capture, review and offline report generation. Reports consume run-local frozen
inputs and evidence, not current targets, product files or authored dataset paths.

## Experiment acceptance

- Execute configured Gateway cases without Git, component sources, pins, direct
  analytics-database access or environment-management tools.
- Author and review static references against the accepted source once at design
  time; clarification/unsupported expectations use its actual readable schema.
- Collect the complete packet for every selected turn; distinguish target/model
  outcomes from transport/collection failures and label incomplete collection.
- Regenerate reports from copied run-local inputs and evidence offline, without
  targets, evaluator services, authored dataset paths or product checkouts.
- Interpret complete evidence through the [comparison protocol](../catalyst-program-roadmap.md).
  No automatic equivalence, rank, winner or production-readiness inference.

Real product and clinical acceptance uses actual product interfaces. Test doubles
prove runner mechanics only. The caller supplies target identity or it is observed
through the interface; unavailable revision/model/prompt metadata stays explicit.
Do not add per-run reference replay, another database query path, mandatory
repeated readers, reseeding or environment-parity gates.
