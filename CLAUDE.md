# Claude context

<!-- SPECKIT START -->
Active feature: `specs/006-validation-harness-mvp/spec.md`.
Read `specs/006-validation-harness-mvp/plan.md` for the standalone runtime slice
and verification obligations. Use `SPECIFY_FEATURE=006-validation-harness-mvp`.
<!-- SPECKIT END -->

Read `AGENTS.md` and `.specify/memory/constitution.md` before changing this
repository. Spec 001 retains readiness/configuration/evidence; the shared metadata
guide owns common provenance semantics. Product behavior is governed by its owning
repository, linked from `AGENTS.md`, not by local nested source paths.

The harness runs configured experiments and generates captured evidence and
reports. The caller prepares services; the umbrella manages workspaces, pins,
builds, deployment, release coordination and website publication. Do not introduce
Git/pin/source prerequisites, model-service lifecycle control or source scanning
for runtime metadata. Reports consume run-local captured inputs only.

Session handoffs and run reports are supporting evidence, not current requirements.
Keep implementation, verification and publication distinct. The umbrella owns
component gitlinks, workspace operations, website sources and publication tooling;
`openmrs_chatbot` is excluded. Reconcile mixed specs, including Feature 008,
by requirement, maintained owner and consumer.
