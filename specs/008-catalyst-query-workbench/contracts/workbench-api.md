# Catalyst Workbench API consumer

The harness consumes a prepared Catalyst Gateway. Product transport and
application behavior are owned by the maintained
[Catalyst specification](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md),
[machine contracts](https://github.com/DIGI-UW/catalyst-ai/tree/main/docs/contracts)
and [Dashboard Builder API](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/contracts/dashboard-builder-api.md).
These references do not require a local product checkout.

## Validation boundary

The configured connection is Catalyst-owned: the harness does not connect to the
analytics database, translate SQL, prepare deployments or replay reference SQL.
It observes Catalyst's advisory validation and exact selected-query execution
through the Gateway. A database diagnostic remains an experimental observation,
not an invented model failure or an automatic factual-equivalence verdict.

A collected case retains its source ID, explicit dialect, complete readable
schema snapshot, session/turn identity, actual model context, selected SQL and
typed parameters, lineage/digests, rows or error, timing and available provenance.
Clarification/unsupported turns retain their response and evidence that no SQL
executed. Imported Datasets retain origin-specific provenance without fabricated
SQL or execution history. Superset validation compares a displayed value with
the originating captured Catalyst result, without a second database query.

The [local schemas](README.md) are executable validation inputs used by current
consumers; they do not make the harness a product contract owner. Update schema
copies with their consumers when the product format changes.
[Feature 008](../spec.md) owns experiment protocols and evidence.
