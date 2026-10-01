# Using the validation harness

The harness runs configured experiments against prepared APIs, captures evidence,
evaluates results and generates portable offline reports. Install and command
examples are in the [repository guide](../README.md); experiment requirements
are in [Feature 006](../specs/006-validation-harness-mvp/spec.md).

- [API adapters](../adapters/README.md): supported clinical and Catalyst interfaces.
- [Catalyst experiment quickstart](../specs/008-catalyst-query-workbench/quickstart.md):
  selected source, reviewed scenarios, collection and reader review.
- [Catalyst demo operations](catalyst-demo-operations.md): a consumer guide to
  umbrella-owned deployment commands and retained server configuration. Run its
  workspace commands from OpenClinAI, not from the harness.

The caller supplies connection settings, scenarios/fixtures, evaluation settings,
provenance and an output directory. Git, submodules and product source trees are
not harness prerequisites. Checkouts, pins, builds, deployment, release gates and
website publication belong to [OpenClinAI](https://github.com/pmanko/openclinai.org).
Website relocation remains pending; the harness's current website files are not
part of the experiment runner interface.
