# Verification obligations: Experiment Readiness and Evidence

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

The [Feature 006 plan](../006-validation-harness-mvp/plan.md) owns runtime slice
implementation and verification status. These retained task IDs describe current
foundation checks; they are not historical completion claims.

- [ ] T009 Verify versioned manifest field shapes, canonical OTel names and
  nullable revisions in `harness/metadata.py` and emitter tests.
- [ ] T018 Verify readiness distinguishes capable, blocked, fixture-only and
  scaffolding configurations without Git, registry or product source access.
- [ ] T032 Verify missing selected capabilities/services/credential references are
  actionable and do not cause target preparation or process control.
- [ ] T041 Verify supplied/observed/missing target provenance, including conflicting
  identities, with no pin-enforcement or source-discovery fallback.
- [ ] T042 Verify generated/curated artifact boundaries, path containment and
  captured clinical inputs needed for portable reporting.
- [ ] T043 Verify no `otel.gen_ai.system` emission.
- [ ] T044 Verify readiness/evidence decisions retain rationale and claim limits.
- [ ] T051 Verify quickstart commands against the runtime CLI and offline packet.
- [ ] T052 Verify emitters and consumers agree with the shared metadata guide.
- [ ] T055 Review scenarios for diversity and narrow tuning-fixture overfit.
- [ ] T056 Run focused runtime/metadata tests, then harness tests and the isolation
  verification in Feature 006; record command/result and acceptance limits.

Tests and concrete runtime edits belong with the implementing agents. This
contract alignment does not mark their implementation or acceptance complete.
