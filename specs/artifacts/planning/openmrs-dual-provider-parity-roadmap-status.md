# OpenMRS Dual-Provider Foundational Parity Roadmap Status

Execution record for `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`openmrs-dual-provider-parity-roadmap.md`](openmrs-dual-provider-parity-roadmap.md) |
| Approval | Explicit user instruction to implement the roadmap on 2026-07-20 |
| Approved roadmap SHA-256 | `cf2c8b33c81ab69ece6150d0171ea3e940f89edfa3968e02c6bd9bf8abc274f5` |
| Current boundary | Signoff 1 granted; context-surface / authoritative-state amendment approved 2026-07-21; ChartSearchAI rebuild and remaining roadmap runtime work authorized to proceed; Signoff 2 remains required before release/evaluation work |
| Supersedes | `MAH-CONSOLIDATION-2026-07-09-v1` for active architecture and execution authority |
| Preserved prior decisions | Temporal-facts Git provenance, stable evaluation IDs, and medication-knowledge safety boundary remain active unless this roadmap explicitly changes them |
| Signoff 1 | Granted by user on 2026-07-20: baseline, contracts, upstream dispositions, and branch-rebuild procedure approved |
| Signoff 2 | Pending: foundational dual-provider product proof |
| Signoff 3 | Pending: validation-harness evidence, demo release, merges, and publication |

## Initial Baseline

| Repository | Head | PR / status |
|---|---:|---|
| harness (approval baseline) | `511c6ee` | #35 draft, mergeable, CI green |
| harness (roadmap foundation) | `8bc9caa` | Roadmap/hash/gate foundation committed and pushed |
| med-agent-hub | `32783bc` | #13 open, mergeable, CI green |
| querystore | `fd8a00c` | #63 open, mergeable, CI green |
| chartsearchai | `7ebca9c` | #26 draft and conflicting; backed up as `codex/backup/chartsearchai-pr-26-20260720` |
| chartsearchai-esm | `30e94e7` | #12 draft and mergeable; backed up as `codex/backup/chartsearchai-esm-pr-12-20260720` |
| chartsearchai upstream | `58c0daf` | Revalidated 2026-07-21 before rebuild execution: 1 new commit since the `577d818` capture (`58c0daf`, disposed as Keep in the upstream inventory); ESM upstream unchanged |
| chartsearchai rebuild branch | `codex/dual-provider-rebuild` | Created 2026-07-21 from exact base `58c0daf` (fresh `upstream/main`). A verbatim replay of the old branch was structurally impossible — its first commit deletes the bundled inference classes upstream since extended (modify/delete conflicts on every bundled file) — so the old branch (`codex/m2-hub-relay-rebuild`, backup `codex/backup/chartsearchai-pr-26-20260720`) serves as the behavior reference and history backup while relay behavior is reimplemented behind the provider boundary on the fresh base. |

The refreshed repository state, upstream dispositions, and rollback refs are recorded in
[`openmrs-dual-provider-upstream-inventory.md`](openmrs-dual-provider-upstream-inventory.md).

## Gate Evidence

| Gate | Status | Evidence |
|---|---|---|
| G01 Roadmap integrity | Passed | `8bc9caa`; `scripts/verify-dual-provider-parity-gates.sh --phase foundation` verifies the immutable SHA, supersession, index, and per-gate status rows. |
| G02 Baseline integrity | Passed | After `ef95ee2` was pushed, `scripts/verify-dual-provider-parity-gates.sh --phase foundation` confirmed every root/submodule tree is clean, every head is remote-reachable, both rollback refs exist, and the inventory is present. |
| G03 Contract first | In progress | Versioned fixtures are checked in; ChartSearchAI consumes the provider lifecycle, capability, event, and error fixture families in red-first Java conformance tests (`TurnLifecycleConformanceTest`, `AnswerEnvelopeTest`, provider tests) on `codex/dual-provider-rebuild`. QueryStore clinical/admin-date fixtures are covered by serializer unit tests on `feat/patientrecord-read-api` (`856bdda`). Remaining owning-language adapters (Python hub, TypeScript ESM) are still required. |
| G04 Provider isolation | In progress | ChartSearchAI commits `9adce8e`–`e2bd0db` add the canonical lifecycle, provider-neutral boundary, bundled and hub adapters (`BundledClinicalAnswerProvider`, `HubClinicalAnswerProvider`, `HttpHubStreamTransport`), the `AnswerEnvelope`, provider-neutral conversation/audit persistence (`ClinicalConversation`/`ClinicalConversationTurn`, Liquibase `chartsearchai-010`), and REST wiring (`/providers`, `/chat/*`). The registry (`ClinicalAnswerProviderRegistry`) never substitutes providers. Runtime isolation proof — bundled answers with hub absent, hub answers without bundled model files on the assembled product — remains for Signoff 2. |
| G05 Provider selection | In progress | ChartSearchAI commit `5129dc8` adds configuration-driven discovery/default/readiness (`chartsearchai.providers.enabled`/`.default`) with bundled as the fresh-install default and no implicit fallback. REST metadata is wired: `GET /rest/v1/chartsearchai/providers` returns descriptors with `pickerVisible`/`defaultProvider` (`e2bd0db`), and `ConversationService.startNew` closes the active conversation and opens a new one on provider/mode switch. ESM picker UI remains. |
| G06 Bundled preservation | In progress | Rebuild branch `codex/dual-provider-rebuild` starts from upstream `58c0daf`; the upstream 635-test baseline passed before changes and the full suite now runs 684 tests, 0 failures, 0 errors, 34 skipped (`mvn test`, verified 2026-07-21) after all provider and REST slices. Legacy bundled wire (`POST /search`, `/search/stream`) is retained for ESM compatibility. Assembled-product no-regression proof (engines, modes, streaming, grounding, safety, caching, warmup at runtime) remains for Signoff 2. |
| G07 QueryStore semantics | In progress | QueryStore `feat/patientrecord-read-api` (`856bdda`) implements per-resource `getClinicalDate`/`getDateKind` across all record serializers (`clinical_event`/`administrative`/`unknown` semantics) plus `lastModified`, backed by serializer unit tests; the full-chart read API (`fd8a00c`) shares serializer/service behavior with ranked reads. End-to-end harness exercise across resource fixtures remains for Signoff 2. |
| G08 Freshness | In progress | QueryStore `856bdda` adds a stable complete-chart `snapshotId`, a strong page-specific ETag with `private, must-revalidate` caching, `304 Not Modified` on `If-None-Match` (`QueryStoreRestController`), and rejection of mixed-snapshot multi-page reads, covered by `PatientRecordEndpointTest`. End-to-end freshness/invalidation proof remains for Signoff 2. |
| G09 Source independence | Pending | No runtime implementation has begun. |
| G10 Context policy | Pending | No runtime implementation has begun. |
| G11 Context ceiling | Pending | No runtime implementation has begun. |
| G12 Cache isolation | Pending | No runtime implementation has begun. |
| G13 Prefix proof | Pending | No runtime implementation has begun. |
| G14 Temporal safety | Pending | No runtime implementation has begun. |
| G15 Final-answer integrity | Pending | No runtime implementation has begun. |
| G16 Drug-safety honesty | Pending | No runtime implementation has begun. |
| G17 Canonical UI | Pending | No runtime implementation has begun. |
| G18 Cancellation | Pending | No runtime implementation has begun. |
| G19 Honest demo | Pending | No runtime implementation has begun. |
| G20 Documentation | Pending | No runtime implementation has begun. |
| G21 QA and hygiene | Pending | No runtime implementation has begun. |
| G22 Next-stage readiness | Pending | No runtime implementation has begun. |

## Foundation Closeout

- The five companion PR descriptions were verified after update on 2026-07-20. Each now states its
  actual branch scope, the dual-provider target, and whether it is amend-in-place (#13/#63) or a
  draft requiring a post-signoff rebuild (#26/#12).
- `scripts/verify-dual-provider-parity-gates.sh --phase full` is intentionally red at this point:
  it reports G03-G22 as unimplemented rather than allowing the roadmap or fixture files to stand in
  for product behavior. This is the recorded red baseline for the red-first implementation stage.
- No runtime code, submodule pin, branch rewrite, reset, rebase, force-push, report publication, or
  evaluation change had been made under this roadmap before Signoff 1. Runtime implementation is now
  authorized, subject to the recorded gates and later signoff boundaries.

## Execution Progress — 2026-07-21

Verified against live repository tips on 2026-07-21:

| Repository | Branch | Tip | State |
|---|---|---|---|
| chartsearchai | `codex/dual-provider-rebuild` | `e2bd0db` | 8 commits ahead of `upstream/main` (`58c0daf`); pushed to fork `origin/codex/dual-provider-rebuild`. Provider boundary, bundled + hub adapters, provider-neutral conversation/audit persistence, and the REST provider/chat lifecycle have landed. |
| querystore | `feat/patientrecord-read-api` | `856bdda` | Clean. Explicit clinical/admin date semantics, complete-chart snapshot identity, and conditional full-chart reads have landed. |
| med-agent-hub | `codex/drug-safety-parity-followthrough` | `faa0232` | Pushed. Revalidating patient-ledger cache and ledger-checked ranked search landed as disposable engine state (606 tests pass). |
| chartsearchai-esm | `codex/m2-hub-profile-rebuild` | `30e94e7` | Old draft branch; canonical-lifecycle rebuild not started. |
| harness | `codex/m2-openmrs-relay-reconciliation` | `8110091` | Submodule pins are not yet updated to the tips above. |

ChartSearchAI test suite (`mvn test`, 2026-07-21): **684 tests run, 0 failures, 0 errors, 34 skipped** (baseline before rebuild: 635).

Outstanding before Signoff 2: ESM rebuild on the canonical lifecycle and conditional picker; harness submodule pin updates; a fresh ChartSearchAI PR from `codex/dual-provider-rebuild` (not amending the abandoned #26); and assembled-product runtime proof for G04, G06, G07, G08 and the remaining gates G09–G22.

## Amendments and Deviations

### 2026-07-21 — OpenMRS context surface and authoritative-state ownership

**Approval:** Explicitly approved by the user on 2026-07-21 after an architecture review of CDS Hooks /
SMART on FHIR, MCP, production LLM session-state patterns, clinical-AI audit guidance, and
engine-managed conversation-state counterexamples. The same instruction authorized continuing
roadmap execution under this ownership split.

**Decision:**

- QueryStore is the canonical **OpenMRS patient-context surface**. OpenMRS-hosted clinical record
  sources are exposed through its serializer/provider SPIs and its authorized, freshness-versioned
  full-ledger and ranked-search contracts. Bundled ChartSearchAI may consume that surface
  in-process; external engines such as med-agent-hub consume the same semantics through the API.
- This does not make QueryStore a mandatory hub dependency or a prompt composer. The hub remains
  source-neutral and continues to support inline charts, static knowledge, and alternate context
  adapters.
- The common OpenMRS layer owns authoritative conversation identity/history, provider/mode
  attribution, retention, feedback, and audit because it is the shared authorization boundary and
  system of record for bundled and hub providers. Provider output is persisted content-agnostically;
  Java does not reinterpret hub validation, evidence, temporal, safety, or In-Depth content.
- Engines may keep conversation-keyed prefix/KV caches, patient-ledger caches, and similar execution
  state only as bounded, memory-only, disposable optimization state. Engine state is never the
  authoritative conversation or audit record and never makes correctness depend on cache survival.

**Rationale:** This follows the EHR-as-context-client pattern in CDS Hooks, the separation between
context servers and application state in MCP, and the standard stateless-inference/stateful-
application split. It also preserves a complete bundled-only installation and avoids creating a
second durable PHI system outside OpenMRS.

**Safer alternative considered:** Durable hub-owned sessions were rejected because bundled-only
installs would still require a parallel OpenMRS store, producing split history and audit, while the
hub would gain independent PHI retention, backup, access-control, and incident-response duties.

**Residual risk:** Prior turns must be replayed to stateless engines, which has token and latency
costs; long-conversation compaction needs an explicit future contract; and the Java persistence
schema must remain content-agnostic as provider payloads evolve. Prefix reuse may optimize replay
but cannot become a correctness dependency.

**Affected gates:** Clarifies implementation evidence for G04, G09, G12, G13, G17, G20, and G21;
it does not relax any acceptance criterion or authorize Signoff 2/3 work.
