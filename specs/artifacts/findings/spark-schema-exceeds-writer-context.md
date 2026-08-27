# The complete Spark schema does not fit the writer's context

**Recorded 2026-08-27, on the running stack.** The implementation plan says
that if the complete readable schema fails, the concrete failure is recorded
and returned to the owner *before* adding selection, translation, fallback, or
another subsystem. This is that record. No filtering was added.

## What happened

A workbench turn against the OpenMRS HIV Spark source fails at
`writer_request` with `context_window_exceeded` — the model backend rejects the
query-generation request with HTTP 422.

That is the specified behaviour, not a regression: Phase 1 requires the
capacity error be recorded rather than context being quietly removed and
retried.

## Measured

Discovery through the Spark connection returns, for the HIV source:

| | relations | columns |
| --- | --- | --- |
| total discovered | 24 | 470 |
| unversioned aliases | 12 | 235 |
| timestamped snapshot twins | 12 | 235 |

The editor-catalog payload is ~336 KB of JSON.

Exactly half is snapshot twins. FHIR Data Pipes registers both an unversioned
alias and a timestamped snapshot for every resource table and ViewDefinition
view — for example `patient_flat` alongside
`patient_flat_2026_08_27t07_11_10_617056696z_2026_08_27t07_11_10_617168156z`,
with identical column shapes. `numOfDwhSnapshotsToRetain: 2` means the twins
accumulate per run, so this grows with every ingestion.

Discovery is behaving correctly: those twins are separately registered
relations, and live discovery reports what the connection exposes.

## What is not being done

No relation allowlist, ranking, selection, or truncation was added. The
guardrails forbid all four, and the failure is exactly the case they reserve
for the owner.

## Levers the owner may choose between

1. **Raise the writer's context window.** The schema is large but not
   pathological; this keeps the complete-schema principle intact.
2. **Change snapshot retention in the reference deployment.** Registering one
   set of relations per source rather than an accumulating pair halves the
   schema today and stops unbounded growth. This is FHIR Data Pipes
   configuration, not Catalyst selection.
3. **Accept a smaller reference source** for the comparison.

Options 1 and 2 compose. Both are deployment or model configuration; neither
puts selection logic in Catalyst.

## Reproduce

```
curl -s -X POST http://localhost:18000/v1/catalyst/workbench/sessions \
  -H 'Content-Type: application/json' \
  -d '{"contractVersion":"catalyst.workbench.session.request.v1",
       "deploymentMode":"demo","question":"How many patients are in the system?",
       "profileId":"catalyst-query-e4b-qwen14b","dataSourceId":"openmrs-hiv"}'
curl -s http://localhost:18000/v1/catalyst/workbench/sessions/<id>/turns
```
