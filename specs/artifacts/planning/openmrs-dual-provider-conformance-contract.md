# Dual-Provider Conformance Contract

**Roadmap:** `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`  
**Status:** Foundation contract. The fixtures define required behavior; implementation tests are
added red-first in the owning repository after Signoff 1.

## Purpose and Boundary

This contract keeps two valid implementation paths behind one OpenMRS experience without pretending
they must share an engine or produce identical prose. It specifies observable behavior:

- provider discovery and truthful capability disclosure;
- canonical turn lifecycle and terminal state;
- source/date/freshness representations;
- context-selection invariants and traceability;
- deterministic temporal and safety status semantics.

The hub remains directly usable without QueryStore. QueryStore remains an OpenMRS projection and
search service, not a prompt composer. Bundled retains its local/remote inference engines and
provider-specific features.

## Versioned Fixtures

[`dual-provider-conformance.v1.json`](../../../datasets/validation/conformance/dual-provider-conformance.v1.json)
is the source of truth for cross-language behavioral fixtures. Each case has a stable identifier so
Java, Python, TypeScript, and harness tests can report the same failing case.

| Fixture family | Required invariant | Owning test destination |
|---|---|---|
| `provider_lifecycle` | Required `answer_done` and one terminal event; optional events follow advertised capabilities; a provider change starts a new conversation | ChartSearchAI API tests; ESM reducer tests; hub stream tests |
| `provider_capabilities` | Bundled is default when configured; picker is absent for one provider; unavailable configured provider remains disabled; no implicit fallback | ChartSearchAI provider/config tests; ESM picker tests |
| `querystore_records` | Existing `date` is preserved; `clinicalDate`, `dateKind`, and `lastModified` are explicit; full pages share a snapshot ID | QueryStore REST/unit tests; hub client tests |
| `context_policy` | Typed-complete evidence, temporal recency, panel completion, mandatory inclusion, stable ordering, ceiling-not-target, and explicit overflow | QueryStore context-slice tests (selection invariants, per the 2026-07-22 amendment); bundled and hub thin-adapter conformance; harness trace tests |
| `temporal_gate` | Checked output cannot contain a malformed/non-ledger date, wrong date/value association, false appointment status, wrong last visit, or unsupported trend | Shared Java/Python fixture adapters; existing hub temporal tests |
| `drug_safety_status` | `checked`, `limited`, and `unavailable` are honest states; incomplete mapping/data/exposure cannot look checked | Java provider tests; hub safety tests; ESM rendering tests |

## Canonical Provider Contract

The Java provider boundary must expose the following conceptually stable fields. Concrete Java
types may differ, but the wire and persistence model must carry their equivalent.

```text
ProviderDescriptor
  id, label, enabled, ready, isDefault, modes[], capabilities[], unavailableReason?

TurnRequest
  patientId, conversationId, providerId, mode?, question, priorClinicalTurns, requestId

TurnEvent
  type, sequence, providerId, mode?, answer?, validation?, evidence?, inDepth?, warnings?, timing?

TurnResult
  providerId, mode?, finalAnswer, validation, evidence, inDepth?, warnings, timing, terminalState
```

Rules:

1. `answer_done` and exactly one of `turn_done` or `turn_error` are required for every accepted
   turn. `answer_validation`, `evidence_updated`, and In-Depth events are capability-driven.
2. A provider never silently falls back to another provider. Its error uses one normalized,
   machine-readable problem code.
3. Changing `providerId` creates a new conversation. Existing conversation records retain the
   provider and mode that produced them.
4. The browser consumes one event shape and one reducer. It does not make provider-specific model
   calls or infer an unavailable capability.

## Context Surface and State Ownership

QueryStore is the canonical **OpenMRS patient-context surface**. OpenMRS-hosted clinical record
sources are exposed through its serializer/provider SPIs and its authorized full-ledger and
ranked-search contracts. Bundled ChartSearchAI may consume that surface in-process; external
engines consume the same record, temporal, identity, and freshness semantics through the API.

This context boundary does not turn QueryStore into a prompt composer or a mandatory dependency of
med-agent-hub. The hub remains source-neutral: inline charts, static knowledge, and alternate
adapters remain valid sources. Per the 2026-07-22 shared context-selection amendment
(`openmrs-dual-provider-parity-roadmap-status.md`), QueryStore additionally serves the tiered
record-selection contract (`getContextSlice`: mandatory | recency_anchor | typed | similarity) for
QueryStore-sourced context, so the `context_policy` selection invariants are implemented once at
the data owner. Each answer engine owns prompt composition, token budgeting over the tiers,
question interpretation, context selection for non-QueryStore sources, reasoning, deterministic
gates, evidence processing, and provider-specific output semantics.

The common OpenMRS layer owns the authoritative conversation and audit record:

- conversation identity, patient/user authorization, provider and mode attribution;
- durable user/assistant turn history, retention, feedback, and rate-limit accounting;
- lifecycle persistence and normalized terminal status; and
- provider output stored content-agnostically, without Java reinterpreting hub validation,
  evidence, temporal, safety, or In-Depth content.

Providers may keep bounded, memory-only conversation-keyed prefix/KV caches, patient-ledger caches,
and similar execution state. Such state is disposable optimization only: it is never the
authoritative conversation or audit record, never persists PHI-bearing ledgers to disk, and never
makes correctness depend on cache survival. A stateless engine receives the prior clinical turns
needed for each request from the common layer.

## QueryStore Record and Freshness Contract

`GET /ws/rest/v1/querystore/patientrecord` preserves existing full-chart and `patient + q` behavior.
The representation adds, without removing, these nullable/public fields:

```json
{
  "resourceType": "obs",
  "resourceUuid": "stable-record-id",
  "date": "2026-01-15",
  "clinicalDate": "2026-01-15",
  "dateKind": "clinical_event",
  "lastModified": "2026-01-16T12:00:00Z",
  "text": "...",
  "metadata": {}
}
```

`dateKind` is one of `clinical_event`, `administrative`, or `unknown`. Serializers assign it while
they still know the OpenMRS resource semantics. `date` remains the compatibility/order field;
downstream temporal presentation must not substitute an administrative date as a clinical event.

Complete-chart pages include a stable `snapshotId` and a strong ETag derived from the complete,
deterministically ordered record representation. A matching `If-None-Match` returns `304`. A hub
ledger refresh accepts a chart only when every page reports the same snapshot. One mixed-snapshot
retry is permitted; a second mismatch is an explicit source failure, never a stale answer.

## Context-Policy Contract

Both providers adapt the same records into their own prompt form. They must report selected and
excluded stable IDs plus deterministic reasons.

`query_scoped` always includes demographics, mandatory safety evidence, exact ID/date/quoted
matches, all typed records for an enumeration request, QueryStore ranked candidates, temporal
recency only when the question is temporal, and complete lab/panel families. It does not add
unrelated records merely to use the remaining budget.

`full_chart_stable` includes the complete deterministic ledger in stable bytes before
question-specific material. It either fits or returns `insufficient_context`; neither provider
silently truncates. Both modes compute temporal, citation, and safety facts from the complete
ledger rather than only the prompt view.

## Temporal, Citation, and Safety Contract

Every output labeled `Checked` has a recorded deterministic gate result. A rewrite is re-gated;
citations are resolved again; semantic grounding evaluates the final answer only. A deterministic
failure may be preserved for manual review as `Needs review`, with original output inspectable,
but it cannot be presented as checked.

Drug safety always reports one of:

- `checked`: required source package, mapping/exposure resolution, and rule execution completed;
- `limited`: a partial but specifically described check completed;
- `unavailable`: the requested check could not complete.

Neither an empty warning list nor a missing source package implies `checked`.

## Red-First Test Procedure

After Signoff 1, each owning repository first adds an adapter test that consumes the fixture and
fails against its current behavior. The implementation follows in the same reviewable commit group.
The final gate records the exact test command and fixture case IDs. A test may not be weakened or
removed to turn the gate green.
