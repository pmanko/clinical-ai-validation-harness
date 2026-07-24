# OpenMRS Dual-Provider Foundational Parity Roadmap Status

Execution record for `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`.

**Reading order:** the roadmap file is hash-pinned and immutable post-approval, so it must be read
TOGETHER with the Amendments section below — in particular, the 2026-07-21 context-surface and
2026-07-22 shared-context-slice amendments re-scope roadmap §5 (Context Modes) and the §12
non-goal "No model-context policy inside QueryStore": context selection invariants are now
implemented once in QueryStore (`getContextSlice`, its ADR Decisions 17–18) with engines as thin
adapters. The roadmap file alone under-describes context ownership.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`openmrs-dual-provider-parity-roadmap.md`](openmrs-dual-provider-parity-roadmap.md) |
| Approval | Explicit user instruction to implement the roadmap on 2026-07-20 |
| Approved roadmap SHA-256 | `a3948d648ba21303639b55e65226455a088e2fb61f693a16a2e769276f20bd72` (Revision 2, 2026-07-23; Revision 1 was `cf2c8b33c81ab69ece6150d0171ea3e940f89edfa3968e02c6bd9bf8abc274f5`, preserved at `8bc9caa`) |
| Current boundary | Signoff 1 granted; context-surface / authoritative-state amendment approved 2026-07-21; shared context-selection (QueryStore context slice) amendment approved 2026-07-22 with checkpoint plan `querystore-context-slice-plan.md`; ChartSearchAI rebuild and remaining roadmap runtime work authorized to proceed; Signoff 2 remains required before release/evaluation work |
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
| G03 Contract first | Passed 2026-07-24 | Versioned fixtures are checked in; ChartSearchAI consumes the provider lifecycle, capability, event, and error fixture families in red-first Java conformance tests (`TurnLifecycleConformanceTest`, `AnswerEnvelopeTest`, provider tests). The TypeScript ESM consumes the same canonical wire with red-first tests. QueryStore clinical/admin-date fixtures have serializer unit tests. **The hub-conformance remainder closed 2026-07-24** (see Step 5 closure below): med-agent-hub now loads the shared fixture directly (`tests/test_dual_provider_conformance_adapter.py`) for `temporal_gate` and the `context.mandatory-overflow-abstains` case; querystore's `ContextSliceTest` loads its 5 owned `context_policy` cases from the fixture instead of hand-duplicated literals; chartsearchai gained fixture-driven tests for `drug_safety_status` (`DrugSafetyStatusTest`) and a `temporal_gate` relay-conformance adapter (`TemporalGateRelayConformanceTest`). Every fixture family now has at least one owning repository that parses the JSON at test time rather than only citing case IDs in comments. |
| G04 Provider isolation | In progress | ChartSearchAI commits `9adce8e`–`e2bd0db` add the canonical lifecycle, provider-neutral boundary, bundled and hub adapters, the `AnswerEnvelope`, provider-neutral conversation/audit persistence, and REST wiring; the registry never substitutes providers. Bundled and hub use fully separate inference backends (bundled → LM Studio `:1234` via `chartsearchai.llm.remote.endpointUrl`; hub → router `:8077` via `med-agent-hub`). **G04(a) proven live 2026-07-22:** with the `med-agent-hub` container *stopped*, the bundled provider answered a full turn (token-streaming, real medication list, no error). **G04(b) proven live 2026-07-23:** with `providers.enabled=hub` and ZERO bundled model files in the container (remote-engine config), `GET /providers` returned hub-only with `pickerVisible:false`, a `provider=bundled` request was explicitly rejected (`provider_not_enabled` — no silent fallback), and a full hub turn completed (18 engine calls, grounded answer, replay 200). Configuration then restored to the design default (`bundled,hub` / default `bundled`), both providers ready. |
| G05 Provider selection | In progress | ChartSearchAI commit `5129dc8` adds configuration-driven discovery/default/readiness (`chartsearchai.providers.enabled`/`.default`), bundled default, no implicit fallback. **Proven live 2026-07-22:** `GET /providers` returns `pickerVisible:false` with bundled only and `pickerVisible:true` with bundled+hub; each provider answered on its own path with no fallback; the ESM provider picker (`e602faf`) is deployed and served. `ConversationService.startNew` closing/opening on switch and the picker's new-conversation-on-switch are covered by backend + ESM component/hook tests. **Remaining:** browser-level confirmation that a picker switch creates a new conversation (the wire is proven; the click is not). |
| G06 Bundled preservation | In progress | Rebuild starts from upstream `58c0daf`; the upstream 635-test baseline passed before changes and the suite now runs **686 tests, 0 failures, 0 errors, 34 skipped** (`mvn test`, 2026-07-22). Legacy bundled wire (`POST /search`, `/search/stream`) is retained. **Proven live 2026-07-22:** the bundled provider streams `reasoning_delta`/`answer_delta` → `answer_done` → `turn_done` on the assembled stack. **Runtime sweep 2026-07-23 (remote engine):** queryScoped ± grounding both answered live with replay-verified engine requests; the legacy bundled wire (`POST /search`) returned a 4-reference answer; hub-only isolation separately proven (G04). **Defect found AND FIXED same day:** `resolveMode()` in `ChartSearchAiRestController` hardcoded a `QUERY_SCOPED` default whenever a request omitted "mode" (the normal case — mode is the `chartsearchai.chartMode` deployment GP, not a per-request client field) — pinning every conversation to `query_scoped` regardless of the GP and making `chartsearchai.chartMode=fullChart` fail EVERY turn with `unsupported_mode` (the forced default never matched the provider's live-configured mode; the no-silent-fallback guard correctly rejected the mismatch — confirmed deterministic by a live experiment ruling out GP-cache timing). Red-first fix: `resolveMode` now returns `null` when unspecified, letting `streamProviderTurn`'s existing `provider.modes().get(0)` fallback (already sourced from the live GP) decide — 3 new tests + full suite green (api 649, omod 49), chartsearchai `b302622`. **Live-verified both modes post-fix:** fullChart turn succeeded (17,953-byte engine call, conversation bound `full_chart_stable`); queryScoped regression-checked immediately after (conversation bound `query_scoped`, matching the restored default GP). **Remaining:** the local-engine (GGUF) leg, warmup/caching legs. |
| G07 QueryStore semantics | In progress | QueryStore `856bdda` implements per-resource `getClinicalDate`/`getDateKind` (`clinical_event`/`administrative`/`unknown`) + `lastModified`, with serializer unit tests; the full-chart read API (`fd8a00c`) shares serializer/service behavior with ranked reads. **Live 2026-07-22:** the hub consumes the querystore chart end to end (grounding cites querystore records; a dateKind-rendering regression was found and fixed against the live path — see progress note). **CORRECTED 2026-07-23** (superseding the initial defect claim below, after direct root-cause instrumentation): neither observation was a querystore defect. (1) **"voided→delete not firing"** — the G07 test's `DELETE .../obs/{uuid}?purge=false&reason=...` call returned HTTP 200 but the DB showed `voided=0` (confirmed by direct query): OpenMRS's REST `ObsResource.delete()` (disassembled: correctly calls `Context.getObsService().voidObs(...)`) silently no-ops when an explicit `purge=false` query param is present, so no core event ever fired — there was nothing for querystore to miss. Omitting the param (`DELETE .../obs/{uuid}?reason=...`, HTTP 204) voids correctly, and the full pipeline (`onVoid`→`RecordProjector`→ES `delete`) was then verified live end-to-end with per-line System.err instrumentation: event fires, `toDelete=[uuid]`, delete confirmed in ES within ~300ms. Running the demo stack on platform 2.9.0-SNAPSHOT (confirmed via `/systeminformation`) was never actually in question. (2) **"per-patient reindex destroyed the chart"** — not reliably reproducible on a clean, settled stack; re-tested `POST /reindex` on two patients (one carrying the falsely-"voided" obs from finding 1) and both fully reprojected correctly (320/320 and 139/139, with a legitimate, correctly-handled 409 version-skip on the one record with a genuinely stale version). The original 0-1-doc observations most likely reflect a transient ES state shortly after the snapshot-restore-triggered backend restart, not a durable code defect. Test-data pollution (3 obs left non-voided in the demo dataset) has been cleaned up via the correct API call; patient dd5558ed verified back at the correct 320. All diagnostic instrumentation reverted (`git checkout`); module suite 491/0 on the clean tree; redeployed. **No fix required; no action item carried forward.** Original (superseded) claim, kept for the record: "Two defects found by the 2026-07-23 e2e freshness run (now G07 blockers): (1) voided→delete not firing — a REST-voided obs stayed in the read store (>30s; Decision 10 violated live; creates DO project, so events flow for saves); (2) per-patient POST /reindex destroyed the chart — bulkDeleteByPatient ran but reprojection indexed 1 document (the voided obs, compounding defect 1) and indexingstatus still reported complete:true. Recovered via the ES snapshot restore (514,682 docs)." |
| G08 Freshness | In progress | QueryStore `856bdda` adds a stable complete-chart `snapshotId`, a strong page-specific ETag with `private, must-revalidate` caching, `304 Not Modified` on `If-None-Match` (`QueryStoreRestController`), and rejection of mixed-snapshot multi-page reads, all covered by `PatientRecordEndpointTest`. **E2E proven live 2026-07-23:** `If-None-Match` revalidation returned `304` on the unchanged chart; a live obs write changed the snapshotId (`05f3552b…` → `41c136b8…`) and the new record appeared in the chart page. |
| G09 Source independence | In progress | Implementation exists and is exercised: `InlineChartSource`/`StaticKnowledgeSource` pass the same source contract (`context_sources.py`; 10 test references), hub config guards partial querystore configuration, and CP3 kept the slice consumption source-scoped with failure-degradation tests. **Remaining:** a recorded hub-start-without-querystore run under this roadmap's evidence conventions. |
| G10 Context policy | In progress | Engine-parity instrument (2026-07-22, `engine-parity-instrument.md`) measured both implementations against identical questions on one index: bundled has typed-complete + similarity + panel completion + temporal recency anchor but NO mandatory clinical core; hub has mandatory core + always-on clinical-date recency + budget but NO panel completion. Execution path: `querystore-context-slice-plan.md`. **CP0 complete (2026-07-22, chartsearchai `4772dfb`):** `buildScoped` carries the mandatory clinical core (allergies + active conditions) in every slice — red-first unit proof against fixture `context.enumerated-medications-are-complete`, full suite 647/0, live parity probe shows the penicillin allergy + active conditions in BOTH arms' medication prompts. **CP1 complete (2026-07-22, querystore `6bc783e`):** ADR Decision 17 — `getContextSlice(patient, question, {types, temporal})` + REST `patientrecord?mode=context`, tiers mandatory/recency_anchor/typed/similarity/panel, context_policy fixtures as red-first querystore tests (8/8; full build 488+35/0), live tier-tagged slice served on the harness stack (mandatory:8 typed:18 similarity:17 of a 320-doc chart). **CP2 complete (2026-07-22, chartsearchai `74d623b`):** `buildScoped` is a thin adapter over `getContextSlice` — question interpretation (intents/temporal/preprocessing/contributed scopes) stays bundled-side, selection is the shared contract; local mandatory-core/family-completion/cap-probe logic deleted; builder tests exercise the REAL querystore slice impl via a delegating stub; suite 648/0; live probe shows the shared slice (allergy + active conditions) in the bundled prompt. **CP3 complete (2026-07-22, med-agent-hub `d7b5e44`):** the querystore source consumes the tier-tagged slice with hub-side interpretation (cues mirroring QueryScopeRouter); slice-mandatory authoritative (union with local heuristic), slice-selected never zero-relevance, local recent-core yields to the slice's temporal-gated anchor; failure degrades to local policy; suite 611/0; live turn requested mode=context&temporal=true&types=drug_order,medication_dispense. **CP4 complete (2026-07-22, harness `16da491`):** diff gained the HARD mandatory-core parity gate (allergies + active conditions text-equal across both prompts — never excusable by documented divergence); divergence entry narrowed to the two measured residuals (caller-side similarity-input drift; hub additive lexical union). Sweep 3/3 PASS with core parity 7=7; scored engine-parity-e4b run 6/6 good cells (bundled 6.8-9.4s vs hub 86-121s on one shared gemma-e4b). **All five checkpoints of `querystore-context-slice-plan.md` are complete.** **v2 follow-through (2026-07-22, querystore `41105d1` / chartsearchai `a34b78b` / med-agent-hub `d7b5e44`+):** question interpretation + retrieval preprocessing centralized in querystore (its ADR Decision 18, `interpretQuestion`); both engines now send the RAW question — similarity-input drift ELIMINATED (verified: identical 51-record slices at source). Residuals are hub-side by design: token-budget ceiling trimming + lexical union. RemoteLlmEngine now surfaces context overflow as chart_too_large (explicit-overflow parity with the local engine, chartsearchai). |
| G11 Context ceiling | Passed 2026-07-24 | Bundled fullChart fails loud (`ChartTooLargeException`); the shared slice surfaces backend-cap truncation explicitly (`chartTruncated`); the hub trims its token budget over slice tiers with `mandatory` never droppable and slice-selected never zero-relevance (CP3, med-agent-hub `d7b5e44`). **Bundled's residual gap closed 2026-07-24** (chartsearchai `5a1a619`): `QueryStoreChartBuilder.applyContextBudget()` now enforces a real token ceiling over the query-scoped slice — a new `TokenCounter`/`LocalLlamaTokenCounter` delegates exact counting to `LocalLlmEngine`'s own llama-server `/tokenize` endpoint (never approximating, mirroring the hub's `RouterTokenCounter`); mandatory records never trim and abstain via a new `InsufficientContextException` → `insufficient_context` problem code (the identical wire string the hub's `InsufficientContextError` already uses) when they alone overflow; otherwise a fast accept when everything fits, else a greedy fill of optional tiers up to the ceiling instead of hard-failing on excess optional content. `RemoteLlmEngine` has no assumed `/tokenize` route (an arbitrary OpenAI-compatible endpoint may not expose one) so it keeps its existing `ChartTooLargeException` reactive backstop unchanged — a deliberate, documented asymmetry, not an oversight. Red-first: `QueryStoreChartBuilderBudgetTest`'s 5 cases (one driven directly by fixture `context.mandatory-overflow-abstains`'s `budget_tokens`/`mandatory_tokens` numbers) failed to compile before the seam existed. Full reactor 677/677 api + 56/56 omod. |
| G12 Cache isolation | In progress | The revalidating patient-ledger cache is keyed by (deployment identity, authorization scope, patient) (`context_sources.py:495`; `test_patient_ledger_cache.py`; landed with med-agent-hub `e44ee89`-line work). **Remaining:** prefix-reuse scope isolation evidence (depends on G13) and a recorded stale-on-error-never-served proof. |
| G13 Prefix proof | Deferred (user-directed 2026-07-24) | Per roadmap §8 step 6: this was surfaced as a conscious GO/DEFER call at Signoff-2 prep, not a silent gap — query-scoped is the operating default and the parity configuration runs the remote engine, so full-chart prompt-prefix reuse only matters if `full_chart_stable` becomes a near-term deployment target. User chose DEFER. Does not block Signoff 2. Revisit if/when `full_chart_stable` moves toward deployment; G12's "Remaining" (prefix-reuse scope isolation) stays open pending this. |
| G14 Temporal safety | In progress | The hub's deterministic temporal gate suite is implemented and heavily tested (`temporal.py`; 78 temporal test cases) and drove the published eval findings. **The shared fixture-corpus remainder closed 2026-07-24:** med-agent-hub's `test_dual_provider_conformance_adapter.py` drives all 4 `temporal_gate` fixture cases through the real `run_temporal_gate()` (4/4 passing against the pre-existing implementation, no behavior change needed). Bundled chartsearchai has no temporal-gate engine of its own — only `HubClinicalAnswerProvider` advertises `ANSWER_CHECK`, and it relays the hub's already-gated `temporalGate` object opaquely (`AnswerEnvelope`'s own contract) — so its fixture obligation is proving the relay never drops or reshapes the gate's status, not re-deriving a result; `TemporalGateRelayConformanceTest` drives all 4 cases through a scripted `HubStreamTransport` and was verified non-vacuous by temporarily stripping `temporalGate` in `envelopeOrNull` and confirming the test fails, then reverting. **Remaining:** recorded end-to-end parity evidence (a live run showing the same temporal-gate status on a shared question). |
| G15 Final-answer integrity | In progress | Hub review rewrites are re-gated and grounding binds to the final answer (the `b2bef83` grounding-source fix + rewrite-validator work are on #13). **Remaining:** recorded evidence that references are recomputed post-rewrite and prior-turn citation numbers cannot bind to current-turn evidence. |
| G16 Drug-safety honesty | In progress | The checked/limited/unavailable result contract is implemented on **both** sides as of 2026-07-24. Prior to this, neither side actually distinguished "checked, nothing found" from "disabled/unavailable" — the wire envelope only ever set `safetyWarnings` when non-empty, so all three cases were indistinguishable to any client. **Hub** (med-agent-hub `ba09e94`): `drug_safety.check_answer_safety()` returns a `SafetyCheckResult(status, warnings)` — `unavailable` when there is no dataset/patient context or the check raised, `limited` when the caller ran only a subset of dose/interaction/contraindication checks, `checked` otherwise; `validate_answer()` delegates to it unchanged (zero behavior change for its ~30 existing callers); wired through all three stream/bare/combined envelope paths as `safetyStatus`, verified end-to-end through the real profile-execution pipeline (`test_drug_safety_integration.py`), not by calling the checker directly. **Bundled** (chartsearchai `6c154ac`): `DrugSafetyValidator.validateWithStatus()` mirrors the same three states; `ChartAnswer` gained a `safetyStatus` field (legacy constructors default to `unavailable` rather than silently implying checked); wired through `LlmInferenceService`, `BundledClinicalAnswerProvider`, and all three `ChartSearchAiRestController` response sites. Both red-first (`test_drug_safety_status.py`, `DrugSafetyStatusTest` — confirmed failing/non-compiling before implementation) and fixture-driven against the shared `drug_safety_status` family. 622/622 hub tests + 677/677 chartsearchai api + 56/56 omod tests green. **Remaining:** ESM rendering of the new `safetyStatus` field (contract row also lists "ESM rendering tests" as an owner) — not yet started. |
| G17 Canonical UI | In progress | The ESM rebuild (`e602faf`, 203 tests) implements the canonical lifecycle reducer, conditional provider picker, and new-conversation-on-switch. **PR-fold item is obsolete** under the 2026-07-23 integration-branch model (proven work lands on `harness-integration` directly; a PR is a curated artifact cut later, not a gate). **Reload-survival evidence recorded and FIXED 2026-07-24:** `GET /chat` required a client-supplied `session` unconditionally (`MissingServletRequestParameterException` on every call, surfaced to the caller as a bare 500) — the ESM's `fetchChatHistory` has no session to send on a fresh page load by construction, so every reload silently rehydrated to an empty, default-provider panel; live-confirmed via three independent e2e specs failing on this exact exception. `session` is now optional; when omitted, `ConversationService.getLatestActiveConversation(patient)` (new) resolves the caller's own active conversation, and each restored assistant turn now carries its FULL persisted answer envelope (references, blocks, safety warnings, confidence, answer validation, In-Depth) via `turn.getProviderPayload()`, not just bare text — previously reload would have lost all evidence/validation/In-Depth state even had the session bug not existed. Red-first: `ChatHistoryEndpointTest` (5 new tests). **Live-verified:** `chartsearchai-demo.spec.ts`'s persisted-history assertion, which reads the reload/history endpoint directly, now returns the full rich envelope (previously a bare 500). chartsearchai `4e4c7ae`/`bd45105`. |
| G18 Cancellation | In progress | `CancellationSignal` was a first-class TYPE in the provider boundary but was never actually wired: the REST layer passed `CancellationSignal.NONE` (a signal that never cancels) for every turn, and `HubStreamTransport`'s interface had no way to interrupt a blocking hub read even if it had been real — a preempted turn ran to the hub's own completion, silently holding the router slot. **Fixed and proven live 2026-07-24 (chartsearchai `4e4c7ae`):** `TurnCancellation` binds the open hub response body so `cancel()` force-closes it from another thread (proven against a real local HTTP server: cancel unblocks an in-flight read in under 0.5s, not just asserted); `TurnPreemptionRegistry` cancels whichever turn currently holds a conversation's slot when a new one starts — the only preempt signal there is, since a conversation never runs two turns on purpose. A turn cancelled after it already produced a real answer (only In-Depth still generating) now completes as done with that answer, persisted with a dangling `inDepth.status: pending` rewritten to `failed` rather than being silently discarded; the REST sink swallows the trailing write once cancelled so a dead browser connection can't block persistence. **Live evidence:** the hub's own `cancellations.jsonl` trace, which recorded ZERO entries for any real preempt before this fix, now records `router_lock_released: true` for a genuine preempted turn; the existing `chartsearchai-preempt.spec.ts` e2e spec went from a 6-minute hang (`data-indepth-status` stuck at `pending`) to passing in ~25s with no code changes to the test itself. Exactly one assistant row settles per preempted turn — proven via `ProviderRestContractTest#aPreemptedTurnsTrailingEventIsSwallowedSoItsAnswerStillPersists` and confirmed live via `chartsearchai-demo.spec.ts`'s 3-turn persisted-history assertion. |
| G19 Honest demo | Pending | No runtime implementation has begun. |
| G20 Documentation | Pending | No runtime implementation has begun. |
| G21 QA and hygiene | Pending | No runtime implementation has begun. |
| G22 Next-stage readiness | In progress | Run metadata already identifies provider/mode/endpoint/model per arm (`run_meta.json` `backends` freeze), stage timings and hub traces have dedicated harness modules (`stage_timings.py`, `hub_trace.py`), and the parity instrument records selected evidence per run. **Remaining:** snapshot identity + cache state + gate results carried per run row. |

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
| chartsearchai | `codex/dual-provider-rebuild` | `6904d49` | Pushed to fork `origin/codex/dual-provider-rebuild`. Provider boundary, bundled + hub adapters, provider-neutral conversation/audit persistence, the REST provider/chat lifecycle, and the restored `GET /models` hub profile relay have landed. |
| querystore | `feat/patientrecord-read-api` | `856bdda` | Clean. Explicit clinical/admin date semantics, complete-chart snapshot identity, and conditional full-chart reads have landed. |
| med-agent-hub | `codex/drug-safety-parity-followthrough` | `e44ee89` | Pushed. Revalidating patient-ledger cache + ledger-checked ranked search; grounding-source regression fixed (`b2bef83`); in-depth no longer gated on answer-validation status, only on preemption (`e44ee89`). 607 tests pass. |
| chartsearchai-esm | `codex/m2-hub-profile-rebuild` | `e602faf` | Pushed. Chat stream aligned to the canonical turn lifecycle (`turn_started`/`turn_done`/`turn_error`) and a provider picker added (appears on `pickerVisible`, new conversation on switch, no fallback); 203 tests pass. |
| harness | `codex/m2-openmrs-relay-reconciliation` | `889144c` | Submodule pins updated to the tips above. |

ChartSearchAI test suite (`mvn test`, 2026-07-22): **686 tests run, 0 failures, 0 errors, 34 skipped** (baseline before rebuild: 635).

### Assembled-product runtime proof (2026-07-22)

New artifacts (chartsearchai `6904d49`, querystore `856bdda`, ESM `e602faf`, hub `e44ee89`) were built, deployed onto the running OpenMRS 2.8 stack, and exercised against a real patient over the live REST API:

- `GET /providers` → both providers, `pickerVisible: true`, `defaultProvider: bundled`; `GET /models` → all 5 hub product profiles.
- Hub `/chat/stream` → full staged lifecycle (`turn_started → answer_done → answer_validation → indepth_done → turn_done`), real clinical answer, conversation + turn persisted with the provider envelope stored content-agnostically.
- Bundled `/chat/stream` → token-streaming lifecycle (`reasoning_delta`/`answer_delta` → `answer_done` → `turn_done`).

Findings from the live run (all fixed): (1) redeploying a same-version `1.0.0-SNAPSHOT` omod over an existing install makes OpenMRS skip new Liquibase changesets (`chartsearchai-010`); a fresh DB runs it normally (worked around by hand — still needs a clean-DB confirmation). (2) the rebuild had dropped `GET /models`, blocking the ESM profile picker; restored in `6904d49`. (3) a regression I introduced in `faa0232` leaked the `[dateKind]` temporal marker into the grounding-source text, so the entailment layer rejected every answer's citations (`needs_review` on all turns, in-depth withheld); root-caused by A/B against the pre-change hub and fixed in `b2bef83`. Separately, on product decision the answer-validation in-depth gate was removed (`e44ee89`): in-depth is withheld only on preemption, never because the answer needs review.

**Deploy bug found AND fixed 2026-07-22 (G-deploy).** Verifying the clean-DB Liquibase path uncovered a real provisioning bug: a fresh `make seed` did NOT install the consumer modules' schema — OpenMRS logged "module did not change, skipping setup" and skipped their Liquibase, so `chartsearchai_conversation` etc. were never created (chat failed until tables were hand-applied). Root cause: OpenMRS records each module's installed version as a global_property `module.<moduleId>.version`, and `dump-loaded.sh` stripped `chartsearchai.*`/`querystore.*` rows but not `module.chartsearchai.version`; that marker rode into every dump and made OpenMRS treat the module as unchanged on restore. Also, the demo dump (2026-07-06) was stale (old provenance format + a retained `querystore_bootstrap_progress` table). **Fixed** (`12d5664`, `24494b5`): `dump-loaded.sh` now also strips `module.<prefix>.%` and consumer `global_property` rows; the dump was regenerated and passes `verify-portable-dump.py --require-portable`. **Verified end to end:** `make reset && make seed` on a fresh DB now applies `chartsearchai-010` (conversation + turn tables, audit columns) and querystore changesets via Liquibase with no manual DDL, and `GET /providers` returns both providers ready. Remaining: querystore's context-source backend still needs configuring after a fresh provision (`querystore.backend` unset → chart retrieval empty → hub turns `context_source_unavailable`); `make querystore-configure`/reindex is the restore step.

Outstanding before Signoff 2: a fresh ChartSearchAI draft PR from `codex/dual-provider-rebuild` (permission-gated push to upstream, not amending the abandoned #26); regenerate the demo dump, then the clean-DB (`make seed`) rerun confirming Liquibase applies `chartsearchai-010` automatically; G04(b) hub-only isolation + the G06 no-regression sweep exercised live; end-to-end G07/G08 freshness; and the remaining gates G09–G22.

### Status-sync audit — 2026-07-23

A gate-by-gate verification against the live repositories found the eight rows above stale in the
CONSERVATIVE direction: their "no runtime implementation has begun" seed text predated the rebuild
work that in fact implemented much of them. Each is now recorded as In progress with its
implementation pointers and its genuinely-remaining evidence. Still honestly Pending: G13 (no
`cache_prompt` prefix-reuse implementation or recorded backend timings anywhere yet) and the
closeout gates G19/G20/G21, which cannot precede the work they audit.

### G05/G17/G18 live e2e sweep — 2026-07-24

Running the project's own pre-existing Playwright suite (`tests/e2e/specs/*.spec.ts` — not a
newly-written harness, it already existed and covers preempt, demo, staged-validation,
low-confidence-review, table, and e4b-multiturn-trivial) surfaced two real, previously-undetected
regressions, both now fixed and covered above:

1. **ModelPicker never routed to the hub provider** — a regression from THIS session's own
   `be85909` (provider picker, 2026-07-21): `ProviderPicker` was bolted on for dual-provider work
   but never wired to `ModelPicker` (the hub product-profile picker), so selecting any hub profile
   — including the picker's own auto-selected default on mount — left the active provider on
   `bundled` (the config default), which silently ignores profile selection and has no In-Depth
   capability. This is why `chartsearchai-preempt.spec.ts` was failing with `data-indepth-status`
   stuck at `pending` for the full 6-minute timeout: it was exercising bundled, not hub. Fixed
   (chartsearchai-esm `986dbaf`) by routing to hub from an effect keyed on the picker's effective
   profile (covers both explicit clicks and the passive default-selection Carbon's radio group
   never fires `onChange` for).
2. **The local dev-loop's Caddy override served pre-rebuild ESM bundles indefinitely** —
   `compose/Caddyfile`'s `chartsearch_overrides` block sent no `Cache-Control` for the
   non-content-hashed chunk files `make chartsearch-esm-build` rewrites in place, so a browser that
   first loaded a chunk hours into a session computed a long RFC 7234 heuristic freshness lifetime
   and silently kept serving it from disk cache with zero network activity on every subsequent
   `make chartsearch-esm-build` — a rebuild landed on disk but the browser never saw it. This would
   have silently defeated verification for any future dual-provider ESM iteration, not just this
   one. Fixed (harness Caddyfile) with `Cache-Control: no-cache, must-revalidate` on those routes.

Both fixes are proven via the project's own real e2e suite, not new assertions written to match the
fix: `chartsearchai-preempt.spec.ts` went from a 6-minute hang to a 25s pass, and
`chartsearchai-demo.spec.ts` went from a bare-500 history endpoint to a fully-populated 3-turn
persisted history (see G17/G18 rows above).

**Four DISTINCT, pre-existing issues found by the same sweep — three root-caused and fixed same day
(2026-07-24), one partially fixed with a real, deeper gap remaining:**

- `chartsearchai-staged-validation.spec.ts` expected a profile labeled "Gemma 12B"; the hub's live
  `/models` response labels it `"Checked answer (12B)"` (`server/levels.yaml:52`) — a stale test
  default from before a label rename, unrelated to routing/reload/cancellation. **Fixed**
  (harness `a6ea154`): updated the spec's and `support/openmrs.ts`'s defaults to the live label.
  Live-verified passing.
- `chartsearchai-e4b-multiturn-trivial.spec.ts` expected the second of two plain sequential turns
  to carry 1 prior turn in the hub trace; observed 0, intermittently. **Root-caused via live
  diagnostic instrumentation on `resolveConversation`, then reverted**: a genuine race in the ESM's
  `useChartSearchAi` hook — the mount-time chat-history hydration fetch (fast, no LLM) could resolve
  AFTER the first real turn's own `onSession` callback had already corrected the session (e.g. after
  the reload fix made hydration return an old-provider conversation), silently overwriting the
  correct value with the stale one before the second turn read it. **Fixed** (chartsearchai-esm
  `b7d2129`): the hydration effect now only applies its response if nothing has updated the session
  since the fetch began. Red-first test (`useChartSearchAi.test.ts`), full suite 207/0, live-verified
  passing (also passed once before the fix by luck — the failure is a race, not deterministic, which
  is exactly why the guard is needed regardless of any single run's outcome).
- `chartsearchai-low-confidence-review.spec.ts` fully mocks the backend via `page.route(...)`, so its
  failure was purely a frontend-rendering question. Git-blamed to a genuine, deliberate ESM commit
  (`30e94e7`, "expose removed in-depth claims clearly") that renamed "Model draft for review" to
  "Removed In-Depth claims" and intentionally made the section collapsed-by-default (proven by that
  commit's own accompanying unit test asserting `not.toHaveAttribute('open')`) — the e2e spec was
  simply never updated to match. **Fixed** (harness `a6ea154`): spec now uses the current label and
  clicks to expand before checking the withheld content. Live-verified passing.
- `chartsearchai-table.spec.ts` expects a medications question to render a structured Carbon table.
  Live curl reproduction showed BOTH providers returning `blocks:[]`. Two independent causes found:
  (1) the **bundled** provider has no table-block support in its schema/prompt/domain model at all
  (`ChartAnswerResponseFormat.java:69-83`, `ChartSearchService.java` `ChartAnswer`) — a real feature
  gap, not a bug, out of scope for a same-day fix. (2) The **hub**'s `single-e4b-checked` profile DOES
  request tables (`synthesis-answer.txt`: "emit exactly ONE table block" for enumerated lists), but
  `team.py`'s flat-cell repair path (`_normalize_product_blocks`/`cell_matches_column`) only ever
  recognized `date`/`weight` column formats — every other column type (Medication, Dose, Route, ...)
  silently failed validation and the whole table was dropped, a regression from commit `7fd5bc7`
  ("harden product table and grounding checks", 2026-07-13) whose own tests only covered date/weight
  columns. **Fixed** (med-agent-hub `c0eaad6`): unrecognized column types now defer to the
  citation-consistency check (every cell in a repaired group shares the same non-empty refs) instead
  of failing outright; recognized types keep their stricter check (the existing
  reversed-cell-order-rejection test still passes unchanged). Full hub suite 611/611. **Remaining,
  NOT fixed:** even after this fix, the E4B model consistently (3/3 live retries) does not attempt a
  table block at all for "List the medications this patient is on." despite the prompt's explicit
  instruction — the repair-path regression was real and is fixed, but is not sufficient on its own;
  the E4B model's own prompt-compliance for table emission needs dedicated prompt-engineering/eval
  work this session did not attempt, to avoid guessing at a fix for small-model behavior without a
  proper evaluation harness.

A genuinely separate, transient infrastructure issue surfaced mid-sweep and is noted for the record,
not because it needed a code fix: recreating `med-agent-hub` via a raw `docker compose ... up
--force-recreate` (bypassing `make med-agent-hub-up`) skips sourcing
`artifacts/chartsearchai-local/querystore-service.env`, leaving `QUERYSTORE_BASE_URL` empty and every
hub turn failing `context_source_unavailable`. Always use `make med-agent-hub-up` (or `make
med-agent-hub-restart` for a lighter restart) to recreate this container, never a raw compose command.

**CORRECTED 2026-07-24** (superseding the "structural finding" below): the claimed divergence was a
false positive caused by comparing against LOCAL `harness-integration` branch refs that had not been
fetched since 2026-07-06 — three weeks stale, predating essentially all of the dual-provider work,
which made an old, since-superseded `harness-integration` history (the /search-deletion commits
described below) look current. After `git fetch origin harness-integration` on both submodules, the
real `origin/harness-integration` was found to be at the EXACT SAME commit as each working branch's
pre-this-session tip: chartsearchai's `origin/harness-integration` = `b302622` = `codex/dual-provider-rebuild`'s
tip before this session's commits; chartsearchai-esm's `origin/harness-integration` = `e602faf` =
the merge-base with `codex/m2-hub-profile-rebuild` (0 commits behind). `harness-integration` has been
kept in exact lockstep with the dual-provider working branches all along — it is not a separate or
older lineage, and fast-forwarding it to include this session's new commits is a clean,
conflict-free operation (no rebase/merge needed). **Fast-forwarded 2026-07-24 (user-confirmed):**
`origin/harness-integration` now points at chartsearchai `bd45105` and chartsearchai-esm `b7d2129` —
both plain fast-forwards, zero conflicts, exactly as predicted. `harness-integration` and each
fork's active working branch are back in lockstep, carrying this session's full G17/G18 fix set plus
the e2e test-gap sweep.

Original (superseded) claim, kept for the record: "both `targets/chartsearchai`
(`codex/dual-provider-rebuild`) and `targets/chartsearchai-esm` (`codex/m2-hub-profile-rebuild`) —
the branches this session's work (and all prior dual-provider work) actually landed on — have
diverged significantly from `harness-integration`, the branch `.gitmodules` pins and the
integration-branch model designates as the proven line: chartsearchai is ~20 commits ahead (the
dual-provider provider-boundary work) and ~20 commits behind (an upstream-sync migration on
`harness-integration` that deleted `/search` and the local-inference subsystem entirely);
chartsearchai-esm is 39 ahead / 26 behind on the same shape. [...] reconciling these two lines
(rebase or merge, likely with real conflicts given both touch chat/relay code extensively) is real,
undecided work the integration-branch model anticipated in principle but does not yet resolve in
practice."

### Step 5 closure — shared conformance fixtures consumed by real code — 2026-07-24

Per the 2026-07-22 shared-context-slice amendment's execution plan and
[`openmrs-dual-provider-conformance-contract.md`](openmrs-dual-provider-conformance-contract.md)'s
"Owning test destination" table and Red-First Test Procedure. Before this work, the shared
`dual-provider-conformance.v1.json` fixture was checked into three repos but only Java cited case
IDs in comments — nothing actually parsed the JSON at runtime, so a fixture edit or an
implementation regression could silently drift from what was documented. Investigated with three
parallel research agents (context-policy, drug-safety, temporal-safety) before any code changed,
converging on the conformance contract doc as the authoritative scope statement rather than
guessing at what "consume the fixture" should mean.

**`context_policy` (querystore, `f8eccd3`):** `ContextSliceTest`'s 5 owned scenarios (mandatory
core, recency anchor, non-temporal exclusion, panel completion, stable ordering) now load their
case by ID from a local fixture copy and assert against its declared ids/tiers instead of
hand-duplicated Java literals. This surfaced two real, pre-existing gaps the fixture-vs-test
comparison caught: the fixture's 3rd typed medication (`med-3`) had no chart document to select,
and `mandatory_ids`/`expected_included` omitted `cond-active` even though `isMandatoryCore` already
treats ACTIVE conditions as mandatory core — both fixed by reconciling the fixture (not by
weakening the test). `context.mandatory-overflow-abstains` is explicitly NOT owned here: querystore
never tracks tokens (`getContextSlice` selects tiers; budget enforcement is the answer engine's
job per `ContextSliceRecord`'s own contract) — this was tracked as a separate item and closed
below. 491/491 querystore tests green.

**`drug_safety_status` (hub `ba09e94` + chartsearchai `6c154ac`):** see the G16 row above — a
genuine missing feature built on both sides, not a wiring exercise.

**`temporal_gate` (hub `00829b4`/`84654a5` + chartsearchai `b4490af`):** see the G14 row above.

**`context.mandatory-overflow-abstains` (hub `a279a56` + chartsearchai `5a1a619`):** see the G11
row above — the one fixture case that turned into real new-feature work on the bundled side, after
the user pushed back on an initial "record as a known gap" recommendation with an architecture
question ("why would the boundary be inside the app... we currently do it in hub so that needs to
be reconciled") that led to grounding the actual design in the hub's `RouterTokenCounter` (which
delegates counting to the real engine's `/tokenize` endpoint, never approximates) before building
the mirrored Java version.

**Not pursued, explicitly scoped out:** ESM rendering of the new `safetyStatus` field (G16); a
from-scratch Java temporal-gate engine (bundled correctly has none — relay-conformance is the right
shape per its own architecture, not a gap); an approximate token counter for `RemoteLlmEngine`
(would violate the same "never approximate" principle the hub itself follows).

Combined final state across all three repos touched: querystore 491/491, med-agent-hub 622/622,
chartsearchai 677/677 api + 56/56 omod. All commits pushed to each fork's working branch and
fast-forwarded onto `harness-integration`; harness root submodule pins updated in lockstep
(`70fbff4`).

## Amendments and Deviations

### 2026-07-23 — Integration-branch merge model (user-directed)

Work is no longer gated on upstream merges: each fork's `harness-integration` branch is the
proven integration line (querystore → `41105d1`, chartsearchai → `a34b78b`, ESM → `e602faf`;
prior tips backed up: `codex/backup/harness-integration-20260723` on querystore; chartsearchai's
old tip was already `codex/backup/chartsearchai-pr-26-20260720`; ESM fast-forwarded). The
harness `.gitmodules` now names `harness-integration` for the three fork-model submodules.
Upstream PRs #63/#90/#22 remain open as curated artifacts to be refreshed or split from
integration when the user chooses to engage upstream review. Roadmap §8 step 1 updated; hash
re-pinned above.

### 2026-07-23 — Roadmap Revision 2 (amendments folded into the canonical body)

**Approval:** Explicit user direction to "update the roadmap properly so it can be used as the
foundation of the remaining work, and then carefully execute it."

**Changes:** the 2026-07-21 and 2026-07-22 amendments are folded into the body (§1 locked
decisions, §5 context contract and modes, §12 non-goal re-scope); §3 is labeled as the
at-approval baseline; §8 records the position at Revision 2 and the dependency-ordered remaining
work toward Signoff 2, including the explicit G13 GO/DEFER decision point and the standing
status-resync step; §10 code targets refreshed to the shipped classes and instruments. Gate IDs
and pass conditions are unchanged. Hash re-pinned above; Revision 1 preserved in git history.

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

### 2026-07-22 — Shared context-selection contract (QueryStore context slice)

**Approval:** Explicit user direction on 2026-07-22 ("this could be a higher level querystore or in
general OpenMRS service that's provided both for the local and remote engines"), after the
engine-parity instrument (see `engine-parity-instrument.md`) measured the two per-engine
context-policy implementations drifting symmetrically: bundled lacks the mandatory clinical core
(allergies + active conditions; fixture `context.enumerated-medications-are-complete` pins them),
the hub lacks obs-group/panel completion, and each re-derives semantics QueryStore already owns
(clinical-date kinds, group metadata). Record-set divergence on identical questions against one
index: 27v36, 27v41, 36v78, 42v70.

**Decision:**

- QueryStore's context surface is extended with a **tiered record-selection contract**:
  `getContextSlice(patientUuid, question, {types[], temporal})` (Java API + REST twin) returning
  records tagged `mandatory | recency_anchor | typed | similarity`, implementing the roadmap §5
  `query_scoped` selection invariants exactly once, at the owner of the index, date semantics,
  and group metadata. The shared `context_policy` fixtures become QueryStore's own red-first
  tests.
- Engines become thin adapters for QueryStore-sourced context and retain: prompt composition,
  serialization, token budgets (trimming over tiers; `mandatory` never droppable; explicit
  `insufficient_context` on overflow), question interpretation (intents/temporal flags,
  caller-side in v1), and all selection for non-QueryStore sources. The hub remains
  source-neutral and fully operational without QueryStore.
- Roadmap §12 non-goal "No model-context policy inside QueryStore" is **re-scoped to its
  intent**: no prompt composition and no model/token-aware policy inside QueryStore. Tiered
  record selection is model-agnostic retrieval semantics, consistent with the 2026-07-21
  context-surface amendment ("ranked-search contracts") and with ChartSearchAI's standing rule
  that retrieval logic belongs to the querystore module.

**Execution:** [`querystore-context-slice-plan.md`](querystore-context-slice-plan.md) — CP0
(bundled mandatory-core safety fix, immediate) → CP1 (slice contract, fixture-driven) → CP2
(bundled adapter) → CP3 (hub adapter) → CP4 (parity gate re-tightened to record-set equality for
QueryStore-sourced runs). Checkpoints are sequential; each is red-first and live-verified with
the engine-parity instrument.

**Affected gates:** G10 and G11 (implementation path), G03 (context fixtures gain their
single-implementation owner), G06 (bundled preservation guards CP0/CP2), G09 (source-neutrality
preserved by construction). No acceptance criterion is relaxed; record-set equality for
QueryStore-sourced runs becomes provable rather than aspirational.
