# API adapters

Adapters invoke already-prepared product interfaces and capture validation
responses. They do not plan Maven builds, check out repositories, enforce pins,
configure deployments or manage service processes.

- [ChartSearchAI](chartsearchai/README.md): real clinical chat requests through
  `harness/validate/client.py`, with explicit provider/profile selection.

- Catalyst: public Gateway routes consumed by `harness/catalyst/`; there is no
  second Catalyst adapter implementation in this directory.

[Feature 006](../specs/006-validation-harness-mvp/spec.md) defines experiment,
evidence and review requirements. The caller supplies connection settings and
prepares targets independently of the harness installation.
