# Dual-provider conformance protocol

This harness protocol owns cross-language fixtures and experiment evidence for
`OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`. Application behavior is maintained by:

- [ChartSearchAI provider contract](https://github.com/pmanko/openmrs-module-chartsearchai/blob/main/README.md#provider-integration-contract): lifecycle, discovery, errors,
  conversation ownership and common answer requirements.
- [QueryStore API](https://github.com/pmanko/openmrs-module-querystore/blob/main/docs/rest-api.md) and ADR Decisions 16–18:
  record dates, completeness, freshness and shared selection.
- [Med Agent Hub](https://github.com/pmanko/med-agent-hub/blob/main/README.md): source adapters, caches, clinical stages and safety.
- [ChartSearchAI frontend](https://github.com/pmanko/openmrs-esm-chartsearchai/blob/main/README.md): capability-aware rendering, streaming controls,
  history, evidence and inspectable review output.
- [OpenClinAI delivery](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md#5-track-a-openmrs-contribution-delivery): assembly, release gates and owner signoffs.

Provider parity does not require identical implementations, feature sets or prose.
The caller prepares product targets; this protocol does not manage repositories,
component pins, builds or deployments.

## Versioned Fixtures

[`dual-provider-conformance.v1.json`](../../../datasets/validation/conformance/dual-provider-conformance.v1.json)
is the canonical cross-language fixture dataset. Each case has a stable identifier so
Java, Python, TypeScript, and harness tests can report the same failing case.

| Fixture family | Observed coverage | Owning test destination |
|---|---|---|
| `provider_lifecycle` | Required `answer_done` and one terminal event; optional events follow advertised capabilities; a provider change starts a new conversation | ChartSearchAI API tests; ESM reducer tests; hub stream tests |
| `provider_capabilities` | Bundled is default when configured; picker is absent for one provider; unavailable configured provider remains disabled; no implicit fallback | ChartSearchAI provider/config tests; ESM picker tests |
| `querystore_records` | Existing `date` is preserved; `clinicalDate`, `dateKind`, and `lastModified` are explicit; full pages share a snapshot ID | QueryStore REST/unit tests; hub client tests |
| `context_policy` | Typed-complete evidence, temporal recency, panel completion, mandatory inclusion, stable ordering, ceiling-not-target, and explicit overflow | QueryStore context-slice tests (selection invariants, per the 2026-07-22 amendment); bundled and hub thin-adapter conformance; harness trace tests |
| `temporal_gate` | Checked output cannot contain a malformed/non-ledger date, wrong date/value association, false appointment status, wrong last visit, or unsupported trend | Shared Java/Python fixture adapters; existing hub temporal tests |
| `drug_safety_status` | `checked`, `limited`, and `unavailable` are honest states; incomplete mapping/data/exposure cannot look checked | Java provider tests; hub safety tests; ESM rendering tests |

## Red-First Test Procedure

For a contract change, each owning repository first adds or updates an adapter test that consumes the
fixture and fails against the current behavior. The implementation follows in the same reviewable
commit group. The final gate records the exact test command and fixture case IDs. A test may not be
weakened or removed to turn the gate green.

## Runtime Evidence Bundle

Owner tests prove the behavior they actually exercise. Gates that claim live product
behavior additionally require a hash-bound JSON evidence bundle. Each observation names its gate and
identifier, lists the exact artifacts used, and evaluates values read from those artifacts:

```json
{
  "artifacts": [
    {"kind": "relay_probe", "path": "artifacts/.../probe.json", "sha256": "..."}
  ],
  "assertions": [
    {
      "name": "checked_answer_visible",
      "evaluator": "json_pointer_equals",
      "artifact_path": "artifacts/.../probe.json",
      "artifact_json_pointer": "/answerValidation/status",
      "expected": "checked"
    }
  ]
}
```

An assertion cannot certify itself with stored `actual` or `passed` fields. The gate evaluator
resolves the listed run-local artifact, verifies its SHA-256, reads the JSON pointer, and compares
that value with `expected`. Context-policy parity additionally requires exactly one
`parity_engine_diff` artifact with no ledger-identity violation, an approved retrieval status, and a
non-empty mandatory clinical core that is equal across providers.
