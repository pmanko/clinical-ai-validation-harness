# Med-Agent-Hub Consolidation and Reliable Clinical Answer Roadmap

**Roadmap ID:** `MAH-CONSOLIDATION-2026-07-09-v1`  
**Status: Historical and superseded by `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`**
**Validated:** 2026-07-09 against the checked-out code, submodule history, open PRs, and references below

> **Supersession note:** This roadmap required removal of bundled Java inference. The approved
> dual-provider roadmap reverses that architectural premise while preserving completed work and
> still-valid safety, temporal, evidence, provenance, and medication-knowledge decisions. Active
> execution authority is [`openmrs-dual-provider-parity-roadmap.md`](openmrs-dual-provider-parity-roadmap.md).

## 1. Goal

Deliver a simple, reliable clinical answer path centered on med-agent-hub:

- med-agent-hub is the single client-facing inference and orchestration service.
- Product default is the fastest checked single-model profile, initially `single-e4b-checked`.
- Every Answer is deterministically temporally checked before first display, then optionally reviewed asynchronously.
- Every In-Depth claim is deterministically temporally checked before display.
- Citation resolution and grounding apply to the final post-review answer.
- Querystore is one optional context source, not a hub dependency.
- Small charts retain full context; oversized charts receive transparent, deterministic context selection.
- The design exposes a future selector extension point without implementing learned retrieval in this iteration.
- ChartSearchAI becomes a thin OpenMRS authorization, session, persistence, and streaming relay.
- The ESM renders lifecycle, evidence, and validation state without orchestrating model calls.
- Bundled Java inference, LM Studio defaults, client-composed stages, and dead A2A/MCP infrastructure are removed.

## 2. Roadmap Governance

1. Leaving Plan Mode, including an accidental UI mode change, is not approval.
2. Execution requires an explicit user statement approving roadmap ID `MAH-CONSOLIDATION-2026-07-09-v1`.
3. The first execution mutation copies this complete plan body verbatim, excluding only the `<proposed_plan>` tags, into `specs/artifacts/planning/hub-consolidation-roadmap.md`.
4. Execution metadata goes in `specs/artifacts/planning/hub-consolidation-roadmap-status.md`; the approved roadmap body is not edited for progress reporting.
5. The status artifact records the roadmap SHA-256, approval date, baseline SHAs, PR heads, upstream heads, gate results, signoffs, and deviations.
6. `specs/artifacts/README.md` links the roadmap. The stale June lane roadmap is marked superseded wherever it conflicts with this roadmap.
7. `scripts/verify-hub-consolidation-gates.sh` makes the acceptance matrix executable. Violations are added as failing checks before implementation.
8. A substantive architectural, interface, safety, scope, or acceptance change requires a written amendment and user approval. The execution agent may not add a compatibility bridge instead.
9. Each milestone ends with a pass/fail matrix and an independent review. A failed, skipped, or pending required gate means the milestone is partial.
10. No implementation crosses a user-signoff boundary until that signoff is explicitly granted.

## 3. Validated Baseline

| Repository | Current pin/head | Open work and risk |
|---|---|---|
| [Harness](https://github.com/pmanko/clinical-ai-validation-harness) | `c5749e6` | [PR #33](https://github.com/pmanko/clinical-ai-validation-harness/pull/33) is mergeable but CI-blocked. Existing operating roadmap is stale. |
| [med-agent-hub](https://github.com/pmanko/med-agent-hub) | `fb9cdbb` | [PR #12](https://github.com/pmanko/med-agent-hub/pull/12) is green. `StagePlan` exists, but old flags, duplicate run paths, unknown-model passthrough, direct Querystore coupling, and dead A2A/MCP code remain. |
| [ChartSearchAI](https://github.com/openmrs/openmrs-module-chartsearchai) | `d315500` | [PR #26](https://github.com/openmrs/openmrs-module-chartsearchai/pull/26) conflicts with upstream. Local refs show 54 commits ahead and 13 behind. Upstream reintroduces bundled inference, prewarm, and progressive preview concepts that must not return. |
| [ChartSearchAI ESM](https://github.com/openmrs/openmrs-esm-chartsearchai) | `58ed478` | [PR #12](https://github.com/openmrs/openmrs-esm-chartsearchai/pull/12) conflicts with upstream. The pinned commit is not currently reachable from an origin remote branch. LM Studio-specific types and picker assumptions remain. |
| [Querystore](https://github.com/openmrs/openmrs-module-querystore) | `de2ba8c` | [PR #63](https://github.com/openmrs/openmrs-module-querystore/pull/63) is green and mergeable but must be refreshed against upstream. |
| Other submodules | Current root pins | Catalyst, `openmrs_chatbot`, and all configured submodules remain in drift, documentation, and clean-tree scans even when behavior is unchanged. |

The OpenMRS demo-data transform remains 2.8-compatible as required by repository governance. Product integration testing follows the exact Reference Application/Core versions declared by the refreshed upstream ChartSearchAI baseline; these are separate compatibility concerns.

## 4. Target Architecture

### 4.1 Profiles and Stages

Replace the team-shaped `Level` flag matrix with validated profiles:

- `Profile`: id, human label, topology, stage list, role models, prompts, policies, capabilities, and readiness requirements.
- `StagePlan`: compiled immutable execution order with invalid combinations rejected at startup.
- Product profiles declare complete behavior. Single profiles have no fake orchestrator.
- Low-level legs remain supported:
  - `answer:<model>@<prompt>~<gate>~temp<n>`
  - `answer-review:<model>@<prompt>`
  - `indepth-only:<model>@<prompt>`
- Raw `answer:` remains `{context, answer, gate}` and does not add product grounding.
- Unknown IDs return a structured `model_not_found` error. They are never forwarded as raw backend models.
- Product discovery advertises configured profiles only, with label, staged capability, validation capability, temporal enforcement, availability, and default status.
- Direct hub clients may use product profiles or explicit low-level legs; the hub is not limited to ChartSearchAI or the harness.

### 4.2 One Execution Engine

Implement one asynchronous stage engine that both streams and drains:

`context -> optional gather -> answer -> answer gate -> resolve refs -> answer_done -> optional review -> answer gate -> final resolve refs -> ground verdicts -> indepth -> indepth gate -> done`

- `run_team`, `run_team_stream`, and flag-driven branch duplication are removed.
- Streaming emits stage events from the engine.
- Blocking requests and harness runs drain the same events into the existing envelope.
- With review: `answer_done -> answer_validation -> indepth_pending -> indepth_done|indepth_error -> done`.
- Without review, `answer_validation` is omitted.
- Cancellation propagates into the active model request and releases the router slot.
- Existing assembly, trace, confidence, gate, and reference helpers are reused until safely consolidated.

### 4.3 Context and Evidence

Introduce internal `ContextSource`, `EvidenceRecord`, `EvidenceLedger`, `ContextSelector`, `ContextView`, and `TokenCounter` contracts:

- Sources return normalized records plus provenance; they do not format prompts.
- Initial adapters are inline chart context, optional Querystore patient records, and existing static knowledge sources.
- Hub startup and inline-chart use must work when Querystore is absent or unavailable.
- Drug safety remains a deterministic specialized subsystem, with WHO-ATC and curated JSON parity preserved.
- The complete evidence ledger is built before prompt selection and drives temporal facts, citation mapping, safety checks, and trace metadata.
- Small charts that fit the exact model budget retain the current full chart and full temporal rendering byte-for-byte.
- Oversized charts use a deterministic, disclosed selector:
  1. include source-marked mandatory safety records;
  2. include exact identifier, date, code, and quoted-phrase matches;
  3. rank remaining records lexicographically by normalized query-token overlap, recency, source priority, and stable record ID;
  4. greedily include whole records until the exact token budget is reached;
  5. record included and excluded IDs and reasons.
- Temporal facts and gate inputs are computed from the complete patient ledger, not only selected prompt records.
- If mandatory context alone exceeds the budget, return `insufficient_context`; do not silently truncate it.
- Product profiles require a known context window and exact tokenizer-backed counter. Character estimates cannot determine readiness.
- Multi-turn budgeting preserves the current question and latest completed turn, removes turn-local `[N]` markers from prior answers, and drops oldest earlier turns deterministically with trace disclosure.
- A future learned selector may rerank existing candidate IDs only. It cannot create evidence, alter provenance, bypass mandatory records, or replace the deterministic fallback. Learned retrieval itself is out of scope here.

### 4.4 Temporal, Review, and Grounding

- `temporal_facts.v1` remains a deterministic sidecar over source evidence.
- The Answer temporal gate runs for every product answer, even when its result is `not_applicable`.
- Product requests cannot disable temporal facts or weaken `enforce`; `off` and `warn` remain low-level experimental options.
- Review rewrites are re-gated before shipping.
- In-Depth is generated from the final checked or edited Answer and every claim is gated before `indepth_done`.
- Safe deterministic patches are applied. Unsafe claims are removed and reported as edited; if no useful claims remain, In-Depth is withheld as `needs_review`/failed.
- Answer and In-Depth validation metadata distinguish `checking`, `checked`, `edited`, `needs_review`, and `unavailable`; clinician-facing text uses “Checked,” not “Validated.”
- Reference resolution is deterministic and may appear as `checking` at `answer_done`.
- Semantic grounding runs only after review and re-resolution. Final verdicts therefore describe the final answer and citations.
- Evidence references include stable source ID, resource type, UUID when available, date, title/text snapshot, usage location, and resolution/grounding state.
- Citation count is descriptive metadata, never a trust score.

### 4.5 OpenMRS and Local Operation

- ChartSearchAI retains patient authorization, session lifecycle, audit, persistence, and SSE relay responsibilities.
- Java sends patient, profile ID, question, and cleaned prior turns in one hub request.
- Java does not compose `answer:`, review, or In-Depth calls.
- Remove bundled/native inference, local-chat fallback, Java prompt orchestration, Java grounding, Java temporal/drug validation, `/search`, clinical `/warmup`, frozen chart snapshots, refresh-context UX, LM Studio discovery/load APIs, and progressive-preview paths.
- Replace `ModelSwitchService` endpoint parsing with a hub-profile metadata relay.
- ESM picker content comes from hub profile metadata. Its default is the available profile marked default, initially `single-e4b-checked`.
- ESM preserves the fast Answer, validation lifecycle, whole In-Depth phase, final evidence verdicts, safety warnings, session hydration, and original-answer disclosure after edits.
- `make chartsearchai-local` becomes the canonical local path. It starts or verifies llama.cpp, med-agent-hub, OpenMRS, and the ESM; only the hub endpoint is configured in ChartSearchAI.
- macOS uses a host-native llama.cpp process for Metal; Linux may use the supported container. Both use the same portable preset generated from environment variables, with no user-specific paths.
- Startup preloads and exercises the default E4B profile, waits for router and hub readiness, and then starts the demo. This is model readiness, not patient-chart warmup.
- Cold model-load time and warm Answer latency are measured separately.

## 5. Execution Milestones

| Milestone | Required work | Exit and signoff |
|---|---|---|
| **R0: Persist roadmap** | Copy this body verbatim, create status artifact and integrity hash, update artifact index, mark the old lane roadmap superseded, commit and push before code changes. | Roadmap diff reviewed; integrity and clean-tree checks pass. |
| **M0: Stabilize baseline** | Push the pinned ESM commit so it is reachable; fetch all remotes; capture exact manifests/SHAs; add the gate script and red-first checks; repair PR #33 CI without weakening coverage; record every upstream commit as keep, port, or exclude. | Harness CI green, all pins reachable, no unclassified upstream commit. **User Signoff A.** |
| **M1: Consolidate hub** | Implement profiles, one stage engine, context/evidence contracts, exact budgeting, Answer/In-Depth temporal enforcement, final grounding order, discovery metadata, explicit errors, and dead-code/dependency deletion. Preserve raw-leg goldens and drug-safety behavior. | Hub unit/contract/integration suites and gates pass; simplicity and coverage reviews pass. **User Signoff B.** |
| **M2: Reconcile OpenMRS integration** | Rebuild existing ChartSearchAI and ESM integration branches from refreshed upstream, replay only approved behavior, simplify Java relay and ESM picker/UX, rebase Querystore #63, and update paired PR descriptions. | Maven, ESM, relay, persistence, multi-turn, abort, and semantic drift checks pass. No force-push to existing upstream PR branches before Signoff B. **User Signoff C.** |
| **M3: Product/local proof** | Deliver portable E4B startup/readiness, exact context configuration, local profile discovery, complete evidence UX, and live warm multi-turn/preempt flows. | One-command clean startup and live E2E pass; warm latency target met; video evidence created. |
| **M4: Evaluation and release** | Run deterministic temporal/date/context QA, candidate runs, independent Scout judging, DIGI-UW/code-qa, documentation drift checks, final pin updates, and PR cleanup. | All acceptance gates pass with no required skips; curated report approved. **User Release Signoff D.** |

Milestones are reviewable commit groups inside the existing companion PRs, not one PR per milestone. After PR #33 lands, use one parent harness integration PR for pins, scripts, runtime configuration, roadmap status, and proof. Reuse hub #12, ChartSearchAI #26, ESM #12, and Querystore #63 unless a user-approved exception is recorded.

## 6. Executable Acceptance Matrix

| Gate | Unambiguous pass condition |
|---|---|
| **G01 Roadmap integrity** | Checked-in roadmap matches this approved body; stored SHA-256 verifies; status artifact lists every gate. |
| **G02 Baseline integrity** | Root and every submodule are clean, pinned commits are remote-reachable, PR #33 is green, and no credential or generated artifact is committed. |
| **G03 Upstream reconciliation** | Every new upstream commit has a reviewed keep/port/exclude disposition and associated verification; no bundled inference, prewarm, or preview behavior is silently restored. |
| **G04 One engine** | Batch and SSE execute the same stage engine; active runtime contains no duplicate `run_team`/`run_team_stream` business paths or old topology flags. |
| **G05 Profile correctness** | Single profiles have no orchestrator; invalid stage order fails startup; unknown model IDs return `model_not_found`; product metadata is human-readable and authoritative. |
| **G06 Raw-leg compatibility** | Golden tests prove unchanged `answer:`, `answer-review:`, and `indepth-only:` envelopes remain byte-exact where specified. |
| **G07 Source independence** | Hub starts without Querystore, inline context succeeds, Querystore failure is explicit, and at least one mock alternate source passes the same contract suite. |
| **G08 Context budgeting** | Small charts remain full and byte-identical; oversized selection is deterministic; exact token count stays within model input budget; mandatory overflow safely abstains. |
| **G09 Context quality** | Required-source recall is 100% on the context dev set; temporal and safety records are never lost; every selected/excluded record has a trace reason. |
| **G10 Answer temporal safety** | Every product Answer records an enforce-gate result; malformed/non-ledger dates, bad date-value bindings, wrong trends, and non-substantive output cannot ship as checked. |
| **G11 In-Depth temporal safety** | Every displayed In-Depth claim records a gate result; unsafe unpatchable claims are absent; a fully rejected section cannot report `complete`. |
| **G12 Review ordering** | A review rewrite is re-gated, references are recomputed, and final grounding evaluates only the final answer and citations. |
| **G13 Citation integrity** | All displayed citations resolve to the current patient/source ledger; prior-turn `[N]` tokens cannot bind to current-turn records; unsupported citations are visibly distinct. |
| **G14 Drug-safety parity** | Existing curated JSON and WHO-ATC contract tests pass; safety warnings persist through live, final, and rehydrated responses. |
| **G15 Thin OpenMRS relay** | Active Java contains no bundled LLM engine, local fallback, Java stage decomposition, grounding validator, chart snapshot, refresh path, LM Studio handling, `/search`, or clinical warmup. |
| **G16 Product discovery** | ChartSearchAI and ESM consume hub metadata; refresh and restart retain a valid picker selection; default is the fastest available checked profile, not LM Studio. |
| **G17 Lifecycle UX** | Fast Answer appears with Checking/Checked/Updated/Needs review state; In-Depth remains distinct; final evidence verdicts and edited originals survive reload. |
| **G18 Multi-turn and cancellation** | Prior clinical referents work across turns; a new question can preempt trailing In-Depth; disconnect and abort release the inference slot deterministically. |
| **G19 Local setup** | A clean documented machine with prerequisites runs `make chartsearchai-local`; no absolute developer path exists; only med-agent-hub is configured as the OpenMRS inference endpoint. |
| **G20 Performance** | On the reference Mac after startup preparation, median trivial E4B `answer_done` is at most 30 seconds; hub overhead is at most 2 seconds or 10% over direct warm router latency, whichever is larger. |
| **G21 Evaluation** | `date-format-dev` and `temporal-core-dev` have zero enforce-arm deterministic blockers; the 12-scenario candidate has no new harm/temporal failures and no unexplained per-cell regression over 10 points. |
| **G22 Documentation** | README, AGENTS, active specs, comments, examples, environment templates, Make targets, and all submodules describe the same architecture; historical material is explicitly marked. |
| **G23 Independent QA** | DIGI-UW/code-qa meaningful-test-coverage, simplicity-review, spec-code-alignment, cross-repo companion review, and evidence-bundle produce no unresolved blocking finding. |
| **G24 Release hygiene** | Required CI and live E2E have no fail/skip/pending status; paired PRs are cross-linked and reviewable; final submodule pins match tested heads; every tree is clean. |

## 7. Test and Evaluation Sequence

1. Add deletion, source-independence, gate-order, In-Depth temporal, token-budget, and product-path checks that fail on the current violations.
2. Capture raw-leg and representative legacy-profile golden envelopes before refactoring.
3. Run hub unit and contract suites after every hub milestone.
4. Run ChartSearchAI Maven and ESM unit/build/lint suites after every integration milestone.
5. Add contract tests for profile metadata, SSE ordering with and without review, same-row persistence, reload hydration, final grounding, and source resolution.
6. Add context fixtures covering under-budget, exact-boundary, oversized, mandatory-overflow, old-but-relevant evidence, and multi-source failure.
7. Run `date-format-dev`, `temporal-core-dev`, then the context-supply dev set with E4B and 12B.
8. Run the 12-scenario candidate only after deterministic checks are clean. Judge afterward using independent actors and preserve separate judgments plus combined/adjudicated reporting.
9. Run `scripts/verify-hub-consolidation-gates.sh`, `scripts/verify-stage-refactor-gates.sh`, `scripts/verify-doc-drift.sh`, all repo CI suites, and `RUN_E2E=1` live gates.
10. Record a paced Playwright multi-turn/preempt video against the warmed E4B profile, with screenshots, MP4, timing trace, and narrated evidence report.

## 8. Primary Code Targets

- Hub runtime: [`team.py`](../../../targets/med-agent-hub/server/team.py), [`levels_loader.py`](../../../targets/med-agent-hub/server/levels_loader.py), [`levels.yaml`](../../../targets/med-agent-hub/server/levels.yaml), [`openai_compat.py`](../../../targets/med-agent-hub/server/openai_compat.py), and [`temporal.py`](../../../targets/med-agent-hub/server/temporal.py).
- Hub sources and safety: [`querystore_client.py`](../../../targets/med-agent-hub/server/querystore_client.py), [`chart_serializer.py`](../../../targets/med-agent-hub/server/chart_serializer.py), [`kb.py`](../../../targets/med-agent-hub/server/kb.py), and [`drug_safety.py`](../../../targets/med-agent-hub/server/drug_safety.py).
- Java relay: [`ChartSearchAiRestController.java`](../../../targets/chartsearchai/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java), [`ChatServiceImpl.java`](../../../targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/ChatServiceImpl.java), and [`ModelSwitchService.java`](../../../targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/impl/ModelSwitchService.java).
- ESM: [`chartsearchai.ts`](../../../targets/chartsearchai-esm/src/api/chartsearchai.ts), [`useChartSearchAi.ts`](../../../targets/chartsearchai-esm/src/hooks/useChartSearchAi.ts), [`model-picker.component.tsx`](../../../targets/chartsearchai-esm/src/components/model-picker.component.tsx), and [`ai-response-panel.component.tsx`](../../../targets/chartsearchai-esm/src/components/ai-response-panel.component.tsx).
- Parent integration: [`Makefile`](../../../Makefile), [`.env.chartsearch.example`](../../../.env.chartsearch.example), [`llama-router.ini`](../../../scripts/llama-router.ini), [`verify-stage-refactor-gates.sh`](../../../scripts/verify-stage-refactor-gates.sh), and [`verify-doc-drift.sh`](../../../scripts/verify-doc-drift.sh).

## 9. Research Basis

- Long advertised windows are not reliable effective windows: [RULER](https://arxiv.org/abs/2404.06654), [Lost in the Middle](https://arxiv.org/abs/2307.03172), and [Context Length Alone Hurts](https://aclanthology.org/2025.findings-emnlp.1264/). These support full context for small charts, exact budgeting, deterministic reduction for large charts, and explicit context evaluation.
- Structured timelines and post-generation temporal reflection improve temporal reasoning, including for smaller models: [TIMER](https://www.nature.com/articles/s41746-025-01965-9) and [TISER](https://aclanthology.org/2025.acl-long.1358/).
- Latency guidance favors fewer input tokens, fewer requests, smaller suitable models, parallel independent work, and reducing perceived wait: [OpenAI latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization).
- Stable outer workflows with bounded specialists support profile-composed stages: [OpenAI orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration). Output guardrails belong before output leaves the system: [OpenAI guardrails](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals).
- Evaluation should define behavior, use representative labeled data, analyze results, and iterate: [OpenAI evals](https://developers.openai.com/api/docs/guides/evals).
- Evidence-first clinical review and traceability inform the source ledger and evidence UX: [Duke DIHI Scout](https://dihi.org/scout/) and [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework).
- The local serving approach follows llama.cpp’s OpenAI-compatible router, model presets, autoloading, readiness, and model limits: [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
- OpenMRS configuration should remain implementation-facing through module settings and O3 schemas/distribution configuration: [OpenMRS configuration](https://openmrs.atlassian.net/wiki/spaces/docs/pages/150930332/Configuration%2BSystem), [distribution guidance](https://openmrs.atlassian.net/wiki/spaces/docs/pages/151093958/Create%2Ba%2BDistribution), and [module structure](https://devmanual.openmrs.org/case_study/yourfirstmodule/).
- Execution controls follow requirements traceability, immutable accepted decisions, small reviewable changes, and required checks: [NASA traceability guidance](https://standards.nasa.gov/system/files/tmp/2026-01-07%20NASA-HDBK-1005%20-%20Final%20-%20Revalidated.pdf), [AWS ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html), [Google small changes](https://google.github.io/eng-practices/review/developer/small-cls.html), and [GitHub required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
- Final proof uses [DIGI-UW/code-qa](https://github.com/DIGI-UW/code-qa) for meaningful coverage, simplicity, spec-code alignment, companion PR management, and evidence bundling.

## 10. Defaults and Exclusions

- Default product profile: `single-e4b-checked`; 12B remains the quality comparison, and high-team remains quarantined from publishable runs.
- Temporal mode: `enforce` for every product profile; low-level experimental legs may explicitly choose another mode.
- Selection implementation: deterministic only in this roadmap; learned retrieval/reranking is a future extension.
- Querystore: supported optional adapter, never an import-time or startup requirement.
- Generic chart and source ledger remain the clinical source of truth; sidecars are deterministic indexes, not new clinical evidence.
- Data remap remains OpenMRS 2.8-compatible; integration runtime follows the refreshed upstream module manifest.
- Existing upstream PRs are reused. No additional PR is opened merely to represent a milestone.
- No merge, force-push of rebuilt upstream branches, report publication, or obsolete-PR closure occurs without the corresponding signoff.
