# Separate Answer and In-Depth evaluation

This protocol defines experiment comparisons. [Feature 006](../../006-validation-harness-mvp/spec.md)
owns collection, evaluation and portable reports; [Med Agent Hub](https://github.com/pmanko/med-agent-hub/blob/main/README.md)
owns staged clinical generation. [OpenClinAI](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#5-track-a-openmrs-contribution-delivery)
owns release and comparison scheduling.

## Comparison boundary

Evaluate the direct Answer and supported In-Depth output as separate artifacts,
with separate latency and judgments. In-Depth elaborates the answer and can arrive
later; do not delay the direct answer to combine them into one response. Product
capabilities determine whether In-Depth exists. An answer-only provider is not
required to gain an In-Depth feature to participate in an Answer comparison.

For a deliberately configured In-Depth comparison, apply the same reviewed
prompt/treatment across arms, using each arm's writer unless the experiment
explicitly fixes another model. Record actual models, context, calls and timing.
A harness-initiated additional generation is a separate experiment operation,
not evidence that the original provider supplied the feature.

Keep Answer quality and speed separate from In-Depth/background quality and
speed. Preserve original, changed and rejected drafts for inspection while
scoring only the accepted final artifact for each axis. Missing or failed stages
stay explicit; they must not inherit the other stage's result or timing. A
combined historical response cannot establish separate stage latency.

## Evidence and review

Capture actual inputs, outputs, stage timings and model/prompt provenance in the
run-local packet. Run deterministic checks before optional judging; preserve each
judgment's actor and input identity. Reports must expose both axes without forcing
one aggregate score or a winner. State which arms and stages actually ran.

The [June implementation/run record](https://github.com/pmanko/clinical-ai-validation-harness/blob/9b5b87ef67397fe7705b37467b98d3550c8d0e47/specs/artifacts/planning/answer-indepth-parity.md)
retains the earlier phase and 224-cell collection history. Its old PR and pending
phase statuses do not schedule current work. Historical Answer results remain
interpretable on their recorded method; combined In-Depth previews are not
substitutes for this separate-artifact comparison.
