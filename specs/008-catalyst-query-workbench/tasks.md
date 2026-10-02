# Feature 008: Catalyst experiment tasks

This register contains harness work only. Product implementation belongs to
[Catalyst](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md#implementation-direction); environment and delivery acceptance belongs to
[OpenClinAI](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#6-catalyst-delivery). The [comparison protocol](../catalyst-program-roadmap.md)
owns the 12-scenario/21-turn study and selected model teams.

## Reference and reader readiness

- [ ] Confirm that the selected comparison source and readable-schema identity
  are accepted, and that no other source's schema is mixed into the packet.
- [ ] Author/run/review each ready-turn reference once through Catalyst and store
  expected facts. Review clarification/unsupported expectations without SQL.
- [ ] Return concrete missing semantic needs to the owner before a source-owned
  view is added; do not invent a harness transformation or another warehouse.
- [ ] Verify the complete conversation, actual model context, selected SQL,
  rows/error, static reference/expected response, rubric and configuration packet.
- [ ] Review scenario references and the reader packet before paid collection.

## Comparison and interpretation

- [ ] Start a new result set after the included source and references are accepted.
- [ ] Hold suite, rubric, data and selected model setups constant; record the
  identities actually used and execute the complete suite once per setup.
- [ ] Confirm each case has a complete packet; label unfinished collection.
- [ ] Initiate one full-context human or frontier-model reader using the shared
  rubric. Identify model interpretation as such, not independent human review.
- [ ] Supply the report and linked evidence to the umbrella publication owner;
  no automatic scoring, disqualification, ranking, tie-break or winner.
- [ ] Obtain owner review of the report before Phase 1 closeout and the separately
  owned future-conversation scope decision.

These pending evidence checkpoints are not a claim that the runner is unimplemented.
The independent runner's implementation and isolation status lives in
[Feature 006](../006-validation-harness-mvp/plan.md). The
[selected-baseline task history](https://github.com/pmanko/clinical-ai-validation-harness/blob/9b5b87ef67397fe7705b37467b98d3550c8d0e47/specs/008-catalyst-query-workbench/tasks.md) retains previous product
implementation and run results. Delivery tasks FP-001 through FP-010 are routed by
the umbrella; they are not duplicated in this harness register.
