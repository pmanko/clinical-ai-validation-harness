# Feature 008 contracts

The Markdown contracts in this directory describe the accepted product
behavior. The JSON schemas mirror formats used by the current implementation so
the running code and its tests use the same definitions.

Some running wire formats retain legacy fields while their current consumers
are consolidated. Change a schema and its consumers together. Catalyst product
behavior belongs to its product specification and binding design; Feature 008
owns integration and delivery acceptance; the program roadmap owns comparison
and broader conversation decisions. Human-readable API contracts describe the
current interface.

The harness copies several live Catalyst schemas here for validation. While both
copies have runtime consumers they remain byte-identical and change atomically.
