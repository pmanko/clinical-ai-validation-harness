# Querystore adapter contract

Querystore is an optional med-agent-hub patient-context source. The hub must also
start and answer with inline context when Querystore is absent.

Stable checks:

- `make querystore-test` runs the complete default reactor suite.
- `make querystore-test-integration` runs the real MySQL Testcontainers backend contract.

Live corpus checks use the existing configure, drift, reindex, and patient-record
read paths. The module remains one possible evidence source, not a hub dependency.
