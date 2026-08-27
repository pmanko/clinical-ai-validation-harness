# Feature 008 contracts

The Markdown contracts in this directory describe the accepted product
behavior. The JSON schemas mirror formats used by the current implementation so
the running code and its tests use the same definitions.

The running wire formats currently include `catalog`, a PostgreSQL-only dialect
value, judge results, repetitions, and automatic evaluation fields. The
[Catalyst implementation plan](../../catalyst-implementation-plan.md) changes
the schemas and their consumers together. Product requirements are stated only
in the program roadmap, Feature 008 specification, and human-readable API
contracts.

The harness copies several live Catalyst schemas here for validation. While both
copies have runtime consumers they remain byte-identical and change atomically.
