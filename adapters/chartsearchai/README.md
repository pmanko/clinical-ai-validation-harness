# ChartSearchAI API adapter

[`ChartSearchAiClient`](../../harness/validate/client.py) calls the configured
OpenMRS ChartSearchAI chat API. Clinical comparison cells select a supported
provider/profile explicitly and replay each scenario's turns in one session.
The runner captures responses, evidence, timing and available provenance.

Bundled inference and configured Med Agent Hub workflows remain distinct product
capabilities. The adapter does not replace them, choose a fallback, build a
module or start a deployment. The caller supplies the endpoint and credentials
and prepares the chosen provider.

Authorization, discovery, transport, cancellation, persistence and clinical
behavior belong to the [ChartSearchAI product contract](https://github.com/pmanko/openmrs-module-chartsearchai/blob/harness-integration/docs/adr.md)
and [frontend repository](https://github.com/pmanko/openmrs-esm-chartsearchai).
[Feature 006](../../specs/006-validation-harness-mvp/spec.md) owns collection,
evaluation and portable reporting. A passing client test double proves runner
mechanics; product claims require the actual API.
