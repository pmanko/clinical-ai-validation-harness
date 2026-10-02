# Run a Catalyst experiment

Use the [harness README](../../README.md#run-an-experiment) for supported runner
commands and target configuration. Feature 008's [specification](spec.md),
[plan](plan.md), [tasks](tasks.md) and [comparison protocol](../catalyst-program-roadmap.md)
define the Catalyst evidence and study workflow.

## Prepare inputs

Supply an already running Catalyst Gateway, connection/authentication settings,
a source/profile selection, scenarios, reviewed references/rubric, output location
and any known target provenance. A local product checkout is not required.
For the optional assembled reference deployment, use the
[OpenClinAI operations guide](https://github.com/pmanko/openclinai.org/blob/main/docs/catalyst-demo-operations.md)
from the umbrella checkout. The harness does not invoke lifecycle or warmup tools.

Review ready-turn reference SQL once through the accepted Catalyst source and
store concise expected facts. Review clarification/unsupported responses against
its actual readable schema. References are not rerun during comparison. Obtain
owner review of the references and packet before paid model collection.

## Collect and inspect

Run the same selected suite and settings once per selected model setup. Execute
ready selected SQL once through Catalyst; retain non-SQL responses without execution.
Capture full conversation, actual model context, source/dialect/schema, SQL,
rows/error, static reference or expected response, rubric and available provenance.
Native database errors and bad model queries are observations, not automatic
invalidations. Mark incomplete collection explicitly.

Use one deliberate full-context reader pass by default. A frontier-model reader
is identified as model interpretation; there is no automatic threshold, rank,
tie-break or winner. Generate reports offline from captured run-local artifacts.
The [product register](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md#implementation-direction) and [delivery register](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#6-catalyst-delivery)
own UI, source, local/server and publication acceptance. A report is not their
completion evidence unless it actually exercised and demonstrated those criteria.
