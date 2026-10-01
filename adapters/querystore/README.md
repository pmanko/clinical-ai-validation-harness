# QueryStore context contract reference

There is no standalone QueryStore execution adapter in this harness. Clinical
experiments use the configured ChartSearchAI API and capture the evidence it
returns; products may use QueryStore as their patient-context source.

Record projection, authorization, retrieval, date semantics, snapshot identity
and freshness belong to the maintained [QueryStore API contract](https://github.com/pmanko/openmrs-module-querystore/blob/harness-integration/docs/rest-api.md)
and [ADR](https://github.com/pmanko/openmrs-module-querystore/blob/harness-integration/docs/adr.md).
QueryStore is not a universal requirement for Med Agent Hub or harness execution.

The caller prepares any needed QueryStore service. Reactor tests, indexing,
configuration and deployment are product/umbrella operations, not adapter methods.
[Current API adapters](../README.md) describes the real harness entry points.
