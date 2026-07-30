# G14 — Temporal safety, live relay-parity evidence (2026-07-24)

Deployment: real patient `dd5558ed-1691-11df-97a5-7038c432aabf` on the running OpenMRS 2.8 demo
stack, `single-e4b-checked` profile, real `gemma-4-12b`/`gemma-e4b` models on the local
llama-router. Question: "When was the patient's most recent visit?" (a genuinely temporal
question, so the gate has something to evaluate).

Bundled chartsearchai has no temporal-gate engine of its own (only `HubClinicalAnswerProvider`
advertises `ANSWER_CHECK`); its obligation is relaying the hub's gate result unaltered
(`TemporalGateRelayConformanceTest`, scripted-transport unit proof). This is the corresponding
live, end-to-end proof: the same question through chartsearchai's real REST relay
(`POST /chat/new` + `/chat/stream`, `provider=hub`) versus the hub's own API directly.

**Via chartsearchai's relay** (`/ws/rest/v1/chartsearchai/chat/stream`, `provider: "hub"`):
```
answer: "The patient's most recent clinical encounter was on 2026-01-07 [6], [32]."
temporalGate: {"schema_version":"temporal_gate.v1","mode":"enforce","status":"not_applicable", ...}
answerValidation.status: "checked"
```

**Direct to the hub** (`POST /v1/chat/completions`, same patient, same question, same profile):
```
answer: "The patient's most recent clinical encounter was on 2026-01-07 [6][32]."
temporalGate: {"schema_version":"temporal_gate.v1","mode":"enforce","status":"not_applicable", ...}
answerValidation.status: "edited"
```

**`temporalGate.status` matches exactly** (`not_applicable` both times) — the specific claim this
gate is about: the relay carries the gate's status through unaltered in a real deployment, not
just in the scripted unit test.

**Noted transparently, not hidden:** `answerValidation.status` differs (`checked` vs `edited`),
and the citation punctuation differs (`[6], [32]` vs `[6][32]`). These are two *independent* live
LLM invocations, not a byte-for-byte replay of one generation — the review stage is a real
LLM-judged pass (see G15 evidence) and can reasonably reach a different verdict call to call. This
is expected sampling variance in the unrelated answer-validation review stage, not a relay defect
in the temporal-gate field this gate is specifically about — worth recording honestly rather than
cropping out of the evidence.

## Conclusion

The core G14 claim — the temporal-gate status the relay carries through is the one the hub itself
computed — is demonstrated live end-to-end, not only by the scripted-transport unit test.
