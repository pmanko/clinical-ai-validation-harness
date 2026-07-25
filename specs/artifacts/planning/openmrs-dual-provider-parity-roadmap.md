# OpenMRS Dual-Provider Foundational Parity Roadmap

**Roadmap ID:** `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`  
**Revision:** 2 (2026-07-23) — folds the two approved amendments (context surface 2026-07-21;
shared context slice 2026-07-22) into the body, records the executed context-slice consolidation,
and re-sequences the remaining work toward Signoff 2; §8's merge model updated same day to the
user-directed integration-branch flow (prove on `harness-integration`, cut upstream PRs from it
when ready). Authorized by explicit user direction to
update the roadmap as the foundation of the remaining work. Revision 1 is preserved in git history
(`8bc9caa`); the status document re-pins the SHA-256.  
**Status:** Approved for execution  
**Relationship:** Replaces `MAH-CONSOLIDATION-2026-07-09-v1`

## 1. Summary

Preserve bundled ChartSearchAI inference and med-agent-hub as two providers behind one OpenMRS clinical-chat contract.

Foundational parity means shared lifecycle, evidence traceability, context-policy invariants, deterministic temporal safety, persistence, cancellation, and honest capability disclosure. It does not require identical implementation, feature sets, or answer text.

Locked decisions:

- Bundled remains the default for a fresh OpenMRS distribution.
- When hub is configured, the OpenMRS UI offers both providers.
- Changing provider starts a new conversation.
- QueryStore owns OpenMRS record projection, search, metadata, dates, freshness, and — per the
  2026-07-22 amendment — the shared tiered context-slice selection and opt-in question
  interpretation (its ADR Decisions 17–18). It still owns no prompt composition and no
  model/token-aware policy; those stay engine-side.
- Providers consume QueryStore's context slice as thin adapters (raw question +
  module-contributed scopes in; tier-tagged records out) and are held to the shared
  conformance fixtures; the harness engine-parity instrument measures residual divergence
  per run.
- `query_scoped` and `full_chart_stable` are explicit modes; small-model defaults use `query_scoped`.
- No automatic context-mode switching in this stage.
- Hub gains revalidated chart caching and RAM prompt-prefix reuse.
- Final answers are never cached.
- Disk KV persistence, learned retrieval, and automatic mode selection require later research and approval.
- Drug safety requires honest contract parity now; equivalent reviewed rule coverage remains a linked medication-knowledge track.
- The current stage ends with dual-provider product proof. Comparative runs, judging, and publication are the next harness stage.

## 2. First-Class Roadmap Governance

The first execution change must:

1. Save this approved body verbatim as `specs/artifacts/planning/openmrs-dual-provider-parity-roadmap.md`.
2. Create `openmrs-dual-provider-parity-roadmap-status.md` for mutable progress, SHAs, PR heads, gate evidence, signoffs, and approved deviations.
3. Record and verify the roadmap SHA-256.
4. Fold the prior draft pivot audit into this canonical artifact; do not retain a second active roadmap.
5. Mark `hub-consolidation-roadmap.md` and its status as historical and superseded while linking completed evidence and still-valid decisions.
6. Update `specs/artifacts/README.md`, root `README.md`, `AGENTS.md`, active specifications, and PR descriptions.
7. Add `scripts/verify-dual-provider-parity-gates.sh`.
8. Commit and push the roadmap artifacts before runtime implementation.

The approved roadmap body is immutable. Material architecture, safety, interface, caching, scope, or acceptance changes require a recorded amendment and user approval. Failed, skipped, or pending required gates mean "partial," never "done."

## 3. Validated Baseline (at approval, 2026-07-20)

Historical record — current tips, pins, and PR states live in the status document's
Execution Progress and the workstream audit. Notably: ChartSearchAI PR #26 was closed as
unrebuildable and superseded by upstream draft PR #90 from `codex/dual-provider-rebuild`.

| Repository | Current integration head | Current state |
|---|---:|---|
| Harness | `511c6ee` | [PR #35](https://github.com/pmanko/clinical-ai-validation-harness/pull/35), draft, mergeable, CI green; planning draft currently uncommitted |
| med-agent-hub | `32783bc` | [PR #13](https://github.com/pmanko/med-agent-hub/pull/13), open, mergeable, CI green |
| QueryStore | `fd8a00c` | [PR #63](https://github.com/openmrs/openmrs-module-querystore/pull/63), open, mergeable, builds green |
| ChartSearchAI | `7ebca9c` | [PR #26](https://github.com/openmrs/openmrs-module-chartsearchai/pull/26), draft and conflicting; current branch deletes bundled inference |
| ChartSearchAI ESM | `30e94e7` | [PR #12](https://github.com/openmrs/openmrs-esm-chartsearchai/pull/12), draft, mergeable |
| ChartSearchAI upstream | locally fetched `577d818` | Contains query-scoped context, top-K tuning, bundled inference, warmup, caching, streaming, grounding, and drug-safety work |

Before branch rebuilding, fetch every configured remote and classify every upstream commit as **keep**, **port**, or **exclude**, with tests or rationale. Resolve the observed discrepancy between the locally fetched ChartSearchAI upstream head and PR base metadata rather than hard-coding either SHA.

## 4. Target Architecture

### Shared OpenMRS Layer

Introduce one provider-neutral Java boundary:

```java
interface ClinicalAnswerProvider {
    ProviderCapabilities capabilities();
    List<ProviderMode> modes();
    CompletionStage<ChatTurn> execute(
        TurnRequest request,
        TurnEventSink events,
        CancellationSignal cancellation
    );
}
```

The common Java layer owns OpenMRS patient authorization, provider routing, sessions, persistence, audit, feedback, rate limits, cancellation, hydration, and canonical error mapping.

Initial implementations:

- `BundledClinicalAnswerProvider`: adapts current upstream ChartSearchAI without removing its local/remote model engines, QueryStore integration, streaming, context modes, grounding, cache, or warmup behavior.
- `HubClinicalAnswerProvider`: makes one med-agent-hub profile request and relays its stage events.
- No automatic fallback between providers.

Provider metadata exposes ID, human label, readiness, modes, default state, and capabilities including token streaming, deterministic answer checking, async review, In-Depth, grounding, drug safety, structured blocks, and multi-turn context.

### Provider Selection and UI

- OpenMRS configuration selects enabled providers and defaults to bundled.
- If only bundled is configured, no provider picker appears.
- If hub is configured, the picker shows both providers and real readiness.
- Unavailable configured providers remain visibly disabled rather than silently disappearing.
- Provider choice is persisted on the conversation.
- Switching provider starts a new conversation and preserves the old one in history.
- The validation harness targets providers directly and does not depend on the interactive picker.
- Hub profile selection remains distinct from provider selection.

### Canonical Lifecycle

Normalize both providers into one event contract:

`turn_started -> optional reasoning_delta -> optional answer_delta -> answer_done -> optional answer_validation -> optional evidence_updated -> optional indepth_pending -> optional indepth_done|indepth_error -> turn_done|turn_error`

`answer_done` and one terminal event are required. Optional events are capability-driven. The ESM uses one parser and reducer, with no provider-specific wire parser.

The common Answer envelope carries final text, blocks, references, warnings, validation state, evidence state, provider/mode identity, timing, and inspectable original output when edited or withheld.

## 5. QueryStore and Context Contract

### Shared QueryStore Primitives

Extend PR #63 without turning QueryStore into an AI prompt service:

- Preserve `patient` full-chart and `patient + q` ranked-search behavior.
- Preserve existing `date` for compatibility and ordering.
- Add nullable `clinicalDate`.
- Add `dateKind: clinical_event | administrative | unknown`.
- Expose source `lastModified`.
- Add complete-chart `snapshotId`.
- Return a strong page ETag derived from snapshot ID and pagination parameters.
- Support `If-None-Match` and `304 Not Modified`.
- Use `Cache-Control: private, no-cache, must-revalidate`.
- Require every page in one acquisition to carry the same snapshot ID.
- Keep embeddings private and preserve OpenMRS authorization.
- **Landed (amendment 2026-07-22, QueryStore ADR Decisions 17–18):** the tiered context-slice
  read — `getContextSlice(patient, question, {types, temporal, interpretQuestion})` and REST
  `patientrecord?mode=context` — returning records tagged
  `mandatory | recency_anchor | typed | similarity | panel` in chart order, with the effective
  interpretation traced (`effectiveTypes`, `temporalApplied`) and backend chart-cap truncation
  surfaced explicitly. Retrieval preprocessing (panel-abbreviation expansion, stopword
  stripping) runs server-side; interpretation cues are conservative word-boundary matching,
  not NLU.

`clinicalDate` and `dateKind` originate in QueryStore serializers, where the underlying OpenMRS object is known. Shared fixtures cover observations, visits, encounters, orders, conditions/onset, programs/enrollment, dispenses/hand-over, allergies, and patient records.

The snapshot digest covers the complete deterministic record representation: stable identity, existing date, clinical date semantics, text, canonical metadata, and last-modified value.

### Hub Source and Cache

The hub remains source-neutral:

- `ContextSource` continues to support inline charts, QueryStore, static knowledge, and alternate adapters.
- Add an optional ranked-search capability; QueryStore implements it through `patient + q`, while alternate sources may use deterministic lexical retrieval.
- Hub startup and inline-chart requests work without QueryStore.

Add a bounded, memory-only, single-flight ledger cache:

- Key: source/deployment identity, authorization scope, patient identity.
- Revalidate on every turn using the first-page ETag.
- Reuse only after `304`.
- On change, fetch every page and require one snapshot ID.
- Retry one inconsistent pagination snapshot, then fail explicitly.
- Never serve stale context after source or validation failure.
- Do not persist PHI-bearing ledgers to disk.
- Recompute temporal facts and reference-date-dependent checks every turn.

Ranked results must resolve to the cached ledger by stable identity and content digest. A mismatch triggers one full refresh and retry, then fails explicitly.

### Context Modes

`query_scoped` (selection invariants implemented ONCE in QueryStore's context slice; engines are
thin adapters — executed as CP0–CP4 + v2 of `querystore-context-slice-plan.md`):

- Always include patient demographics, mandatory safety evidence (allergies + active
  conditions), and exact ID/date/quoted-phrase matches.
- Include every record for matched medication, allergy, program, condition, visit, or order enumeration intents.
- Union QueryStore ranked candidates.
- Add a recency anchor only for temporal questions.
- Complete observation/lab panel families.
- Deduplicate and order deterministically.
- Treat the token budget as a ceiling, not a target; do not add irrelevant records to fill it
  (budget trimming is engine-side, over the slice tiers; `mandatory` is never droppable).
- Fail `insufficient_context` if mandatory or typed-complete evidence cannot fit; bundled
  additionally surfaces engine context overflow as `chart_too_large` on BOTH engines.

`full_chart_stable`:

- Include the complete ordered ledger with stable bytes and explicit clinical dates.
- Place the stable chart prefix before question-specific material.
- Fail explicitly if the full chart cannot fit.
- Never silently truncate.

Both modes record included/excluded IDs and reasons. The complete ledger, not the selected prompt slice, drives temporal checks, drug safety, and citation resolution.

## 6. Prompt Reuse and Efficiency

For `full_chart_stable`, add a backend capability for in-memory prompt-prefix reuse:

- Explicitly request llama.cpp `cache_prompt`.
- Preserve a stable model/system/chart prefix.
- Record `cache_n`, `prompt_n`, `prompt_ms`, total prompt tokens, and whether reuse occurred.
- Scope reuse by patient snapshot, provider/profile, model artifact, tokenizer/template, system prompt digest, and authorization boundary.
- Invalidate naturally when any fingerprint changes.
- Preserve deterministic safety and output-envelope behavior whether cache reuse occurs or not.

Do not add:

- final-answer caching;
- TTL-only chart reuse;
- disk-persisted KV slots;
- cross-patient or cross-tenant prefix reuse.

Disk KV persistence remains a later benchmark and security decision because it stores PHI-derived model state. Prefix reuse is expected to reduce prefill work, not output-token generation, consistent with [llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) and [vLLM prefix caching](https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/).

## 7. Temporal, Citation, and Safety Parity

- Preserve the hub's single Git-managed `temporal_facts` shape.
- Define a language-neutral temporal behavior specification and shared Java/Python fixture corpus.
- Every provider Answer advertised as Checked must pass deterministic non-substantive, malformed-date, non-ledger-date, date/value-binding, appointment, last-visit, single-point-trend, and trend-direction checks.
- Hub review rewrites are re-gated before shipping.
- In-Depth remains a hub capability and is gated before display.
- Reference resolution is deterministic for both providers.
- Semantic grounding evaluates the final post-review Answer and final citations.
- Prior-turn citation numbers cannot bind to current-turn evidence.
- A failed check may remain visible for manual review, but must be labeled `Needs review`, retain the original output, and never appear Checked.

Drug safety uses one common result contract:

- `checked`, `limited`, or `unavailable`;
- warnings, coverage, package/source identity, provenance, and issues;
- no empty-success state when mappings, exposure, data, or execution are incomplete;
- unreviewed ATC or seed rules cannot emit deterministic clinical warnings.

Equivalent approved DDI content, CIEL mappings, exposure resolution, the medication graph package, and CDS Hooks remain a linked first-class development track with separate clinical review gates.

## 8. Implementation Sequence and Signoffs

### Roadmap and Contract Foundation

- Persist and validate the roadmap.
- Refresh every repo and PR baseline.
- Back up the current #26 and #12 heads before any rewrite.
- Capture bundled and hub golden behavior.
- Define provider capabilities, canonical turn/events/errors, QueryStore record/freshness contract, context-policy fixtures, and temporal conformance fixtures.
- Add failing executable gates before implementation.
- Update PR descriptions with requirement-to-commit maps.

**User Signoff 1:** Approves the baseline, contracts, upstream dispositions, and backed-up branch-rebuild procedure.

### Source, Hub, and OpenMRS Implementation

- Extend QueryStore PR #63 with date semantics, snapshot/ETag behavior, and tests.
- Add context-policy parity, QueryStore ranked candidates, ledger caching, and RAM prefix reuse to med-agent-hub PR #13 in distinct commit groups.
- Rebuild ChartSearchAI PR #26 from freshly verified upstream while preserving bundled behavior and adding the provider boundary.
- Rebuild ESM PR #12 around one canonical lifecycle and conditional provider picker.
- Keep harness PR #35 as the parent integration/pin/proof PR.
- Do not create a PR per internal phase.
- Do not force-push rebuilt upstream PR branches before Signoff 1.

### Position at Revision 2 (2026-07-23)

Signoff 1 granted; runtime implementation is well advanced. Executed under the amendments: the
context-slice consolidation (CP0–CP4 + v2 — shared selection, interpretation, and preprocessing
in QueryStore; both engines as thin adapters), honest bundled readiness, explicit context
overflow on both engines, and the engine-parity instrument (tap/probe/diff + hard mandatory-core
gate + scored `engine-parity-e4b` runs) as standing proof machinery. Sixteen gates are In
progress, two Passed; genuinely un-started: G13 and the closeout gates G19–G21. The status
document's Gate Evidence table is the per-gate ledger.

### Remaining Work toward Signoff 2 (dependency order)

1. Integration-branch model (user-directed 2026-07-23): proven work lands on each fork's
   `harness-integration` branch — the harness pins and proves against those, gated on nothing
   upstream. The open upstream PRs (#63, #90, #22; hub #13 in its own repo) are curated
   artifacts cut or refreshed from integration when ready, and may be split at that point.
   Upstream CI red caused only by unpublished cross-repo snapshots (e.g. #90 awaiting #63)
   is expected and non-blocking under this model.
2. ESM PR rebuilt: upstream draft #22 from `codex/m2-hub-profile-rebuild`; #12 closed
   (the #26→#90 pattern). DONE 2026-07-23.
3. Product-proof evidence runs: G04(b) hub-only install; G06 runtime no-regression sweep
   (engines × chart modes × grounding — the local-engine leg needs its GGUF provisioned and may
   be recorded as a follow-up); G07/G08 end-to-end freshness (chart change → new snapshot
   identity; `304` reuse under the harness); cancellation settle-one-row proof (G18).
4. Playwright paced proof: provider switch creates a new conversation; reload survival (G05/G17).
5. Shared-fixture parity: the hub consumes the versioned conformance fixture families
   (context/temporal/drug-safety), completing G03 and evidencing G14–G16.
6. **G13 decision point:** full-chart prompt-prefix reuse (`cache_prompt` + recorded backend
   timings) is the one unstarted build item. At Signoff-2 prep it is a conscious GO / DEFER
   call — query-scoped is the operating default and the parity configuration runs the remote
   engine, so its value depends on whether `full_chart_stable` is a near-term deployment target.
   Deferring requires recording the decision here; it does not block Signoff 2 if deferred.
7. Closeout: G19 honest-demo review, G20 documentation sweep, G21 QA/hygiene (including a
   status-doc resync against the repos — a standing pre-signoff step as of the 2026-07-23
   audit), G22 run-metadata completeness.

**User Signoff 2:** Marks the current foundational implementation complete and authorizes the next validation-harness stage.

### Next Validation-Harness Stage

Design a controlled matrix that holds model, prompt, sampling, chart, question, and reference date fixed while varying one of provider, context mode, checking stages, or cache state.

Run deterministic audits before judging, preserve separate judgments, report per-cell evidence, and publish quality and latency differences without requiring identical answers or one shared aggregate score.

**User Signoff 3:** Approves final demo release, companion merges, curated publication, and PR cleanup.

## 9. Executable Acceptance Matrix

Gate IDs and pass conditions are stable across revisions. The 2026-07-22 amendment moved
G10/G11's implementation locus into QueryStore's shared context slice without changing what
they must prove.

| Gate | Pass condition |
|---|---|
| G01 Roadmap integrity | Canonical roadmap hash verifies; old roadmap is marked superseded; status lists every gate and signoff |
| G02 Baseline integrity | Every repo is clean, every pin is reachable, all upstream commits are classified, and current PR heads are backed up |
| G03 Contract first | Provider, event, error, QueryStore, context, temporal, and safety fixtures fail before implementation and pass afterward |
| G04 Provider isolation | Bundled answers with hub absent; hub answers without bundled model files |
| G05 Provider selection | Picker appears only when multiple providers are configured; switching creates a new conversation; no automatic fallback exists |
| G06 Bundled preservation | Upstream local/remote engines, query/full modes, streaming, grounding, safety, caching, warmup, and existing tests remain intact unless separately approved |
| G07 QueryStore semantics | Full and ranked reads share service behavior; clinical/admin dates and last-modified fields are correct across resource fixtures |
| G08 Freshness | ETag/304 reuse works; any chart change alters snapshot identity; mixed-page snapshots are rejected |
| G09 Source independence | Hub starts without QueryStore; inline and mock alternate sources pass the same source contract |
| G10 Context policy | Both implementations pass typed completeness, recency, panel completion, mandatory evidence, stable ordering, and trace-reason fixtures |
| G11 Context ceiling | Token budget is never treated as a fill target; mandatory overflow and full-chart overflow fail explicitly |
| G12 Cache isolation | Ledger and prefix reuse are scoped by patient, authorization, source snapshot, model, tokenizer, and prompt; no stale-on-error path exists |
| G13 Prefix proof | Stable full-chart follow-up reuses prompt tokens and records backend timings; query-scoped behavior does not claim unsupported reuse |
| G14 Temporal safety | Every Checked Answer has a deterministic gate result; shared Java/Python fixtures agree |
| G15 Final-answer integrity | Review rewrites are re-gated; references are recomputed; grounding binds only to final text |
| G16 Drug-safety honesty | Both providers expose checked/limited/unavailable correctly; unreviewed rules cannot emit deterministic warnings |
| G17 Canonical UI | One reducer handles both providers; validation, evidence, original output, warnings, optional In-Depth, and terminal states survive reload |
| G18 Cancellation | Disconnect and new-turn preemption settle one assistant row and release provider/model work where supported |
| G19 Honest demo | Model errors may exist, but false Checked states, hidden rejected output, broken evidence, and silent downgrade are prohibited |
| G20 Documentation | README, AGENTS, active specs, configuration examples, comments, PR descriptions, and all submodules describe the same dual-provider architecture |
| G21 QA and hygiene | Required CI, real-path smoke tests, code-qa reviews, drift gates, and clean-tree checks pass with no unresolved blocker |
| G22 Next-stage readiness | Run metadata can identify provider, mode, snapshot, selected evidence, gate results, cache state, model/prompt, and per-stage timing |

## 10. Primary Code Targets

- QueryStore: `QueryStoreServiceImpl.getContextSlice` + `ContextQuestionInterpreter` (ADR
  Decisions 17–18), serializers, `QueryStoreRestController` (`mode=context`, `interpret`), and
  `PatientRecordView` (tiered slice envelope).
- med-agent-hub: `context_sources.py` (slice consumption, tier-aware ranking, ledger cache),
  `querystore_client.py` (`fetch_context_slice`), `temporal.py`, and stage/trace assembly.
- ChartSearchAI: the provider boundary (`ClinicalAnswerProvider`, registry, bundled + hub
  adapters, `CancellationSignal`), `QueryStoreChartBuilder` as thin slice adapter, both
  `LlmEngine`s with explicit overflow, honest readiness in the bundled descriptor.
- ESM: canonical-lifecycle turn reducer, provider picker, session store, response/evidence UI
  (`codex/m2-hub-profile-rebuild`).
- Harness: roadmap/status + gate script, the engine-parity instrument
  (`engine-tap.py`, `parity-engine-probe.py`, `parity-engine-diff.py`, `engine-parity.v1`),
  provider-arm scored runs (`Backend.provider`, `/chat/stream` client), and the stable
  no-reindex ES reset (`dual-provider-up.sh`, `querystore-snapshot.sh`).

## 11. Research Basis

- Long advertised contexts are not equivalent to reliable use, supporting conservative query-scoped defaults and explicit full-chart evaluation: [RULER](https://arxiv.org/abs/2404.06654) and [Lost in the Middle](https://arxiv.org/abs/2307.03172).
- Conditional GET with ETag and `If-None-Match` is the standard mechanism for efficient freshness validation: [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html). Authenticated clinical responses require private, revalidated caching boundaries: [RFC 9111](https://www.rfc-editor.org/rfc/rfc9111.html).
- Prefix caching benefits repeated long-document and multi-turn prefixes but affects prefill rather than decoding: [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) and [vLLM automatic prefix caching](https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/).
- Provider choice belongs in validated implementer configuration with reasonable defaults: [OpenMRS O3 configuration](https://o3-docs.openmrs.org/en-US/docs/configuration-system/).
- A Java backend-for-frontend can normalize provider differences while keeping browser logic stable: [Azure BFF pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/backends-for-frontends).
- Named optional lifecycle events support progressive provider capabilities: [MDN Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).
- Stable machine-readable errors use [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457.html).
- Execution controls follow traceable requirements, immutable accepted decisions, reviewable changes, and required checks: [NASA requirements traceability](https://standards.nasa.gov/system/files/tmp/2026-01-07%20NASA-HDBK-1005%20-%20Final%20-%20Revalidated.pdf), [AWS ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html), and [GitHub required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
- Final engineering review uses [DIGI-UW/code-qa](https://github.com/DIGI-UW/code-qa).

## 12. Explicit Non-Goals

- No automatic provider failover.
- No identical-output requirement.
- No prompt composition and no model/token-aware policy inside QueryStore (re-scoped by the
  2026-07-22 amendment: tiered record selection and opt-in question interpretation are
  retrieval semantics and in scope).
- No QueryStore dependency for generic hub operation.
- No final-answer cache.
- No disk KV persistence.
- No learned retrieval or automatic context-mode routing.
- No requirement that bundled implement hub review, In-Depth, teams, or structured blocks.
- No claim of equivalent DDI coverage before clinically approved shared content and CIEL mapping work.
- No full comparative run, judging, or publication before Signoff 2.
