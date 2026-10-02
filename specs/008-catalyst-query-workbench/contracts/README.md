# Feature 008 contracts

The Markdown guide describes the harness's API consumption and evidence boundary.
Product behavior belongs to the maintained [Catalyst contracts](https://github.com/DIGI-UW/catalyst-ai/tree/main/docs/contracts).
The JSON schemas mirror formats used by current runtime consumers so the running
code and tests use the same definitions.

Some running wire formats retain legacy fields while their current consumers
are consolidated. Change a schema and its consumers together. Catalyst product
behavior belongs to its product specification and binding design; Feature 008
owns validation protocols and evidence; the umbrella owns delivery coordination;
the comparison protocol owns model experiments and reader interpretation. Human-readable API contracts describe the
current interface.

The harness copies several live Catalyst schemas here for validation. While both
copies have runtime consumers they remain byte-identical and change atomically.
