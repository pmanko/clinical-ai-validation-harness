# Hub Consolidation Roadmap Status

Execution state for `MAH-CONSOLIDATION-2026-07-09-v1`.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`hub-consolidation-roadmap.md`](hub-consolidation-roadmap.md) |
| Approval | Explicit user instruction to implement the roadmap on 2026-07-09 |
| Approved roadmap SHA-256 | `5f625cb9f1ac4a1682001fb40fd3cc6852ceed16c96e9b54e435b4e591a64d3d` |
| Current execution boundary | M3 product/local proof in progress; User Signoff C granted 2026-07-10 |
| Next protected boundary | M4 evaluation and release requires successful M3 proof and User Release Signoff D |
| Approved amendments | A1: Git-owned temporal-facts provenance, approved by the user on 2026-07-11 |

The roadmap intentionally preserves the exact approved Plan Mode body, including its
pre-approval status line. This companion file is the authoritative execution-status record.

## Approved Amendment A1: Git-Owned Temporal-Facts Provenance

The temporal facts object is an internal, same-deployment data structure. It is not an independently
deployed public wire contract and the product will not run multiple temporal-facts formats. Git and
the existing run/deployment provenance identify the implementation that produced historical data.

Required implementation:

1. The current hub produces and consumes one object named `temporal_facts`; no runtime schema
   negotiation, converter, compatibility branch, or `temporal_facts.v*` identifier remains.
2. Active prompts, tests, context-dev metadata, trace summaries, and documentation refer to
   `temporal_facts` without enumerating historical versions.
3. Hub traces record `HUB_BUILD_REVISION`; harness runs continue to record their Git SHA and pinned
   hub commit. Historical run artifacts remain immutable and are not rewritten.
4. The deterministic temporal gate consumes the current object directly and never branches on a
   temporal-facts version string.
5. A repository gate fails if active hub/harness code or current documentation reintroduces a
   `temporal_facts.v*` identifier. Explicitly historical archived run artifacts are exempt.
6. This amendment applies only to the internal temporal facts object. Public or persisted contracts
   such as `temporal_gate.v1`, `sources.v1`, and judge/report artifact schemas retain their versions.

The same correction closes the independent review findings discovered during the checkpoint:

- a claimed last-visit date fails deterministic validation when the ledger has no explicit
  Encounter/Visit record; latest clinical activity remains separately labeled;
- automatic scoping of one declared citation is allowed only for one unambiguous prose claim;
- product citation canonicalization runs after every potentially mutating temporal gate; and
- final product-path tests prove these conditions before live proof resumes.

Amendment exit criteria: no active `temporal_facts.v*` identifiers, trace provenance identifies the
hub commit, the full hub and parent suites pass, and an independent re-review reports no blocker.

Amendment result: **Pass** at med-agent-hub `d7bd52e`. The hub emits one unversioned internal
`temporal_facts` object, traces require an exact hub commit, 355 hub tests pass, 34 focused parent
tests pass, the seven-repository drift scan passes, and the independent re-review reports no blocker.

## Baseline Snapshot

The first table is the pre-fetch snapshot observed when execution began. The second records the
immutable post-fetch baseline used for M0 classification and future reconciliation.

| Repository | Checked-out SHA | Branch | Pull request state at approval |
|---|---|---|---|
| harness | `c5749e6` | `feat/simple-5arm-benchmark` | #33 open, mergeable, CI blocked |
| med-agent-hub | `fb9cdbb` | `feat/hub-context-grounding` | #12 open, clean, CI green |
| chartsearchai | `d315500` | `harness-integration` lineage | #26 draft, conflicting |
| chartsearchai-esm | `58ed478` | `harness-integration` | #12 draft, conflicting; pin not yet remote-reachable |
| querystore | `de2ba8c` | `harness-integration` lineage | #63 open, clean, CI green |
| catalyst | `3c1f1aa` | `main` | unchanged baseline dependency |
| openmrs_chatbot | `2e723f8` | `main` | unchanged baseline dependency |

### Refreshed Baseline

All configured remotes were fetched with pruning on 2026-07-09. No upstream code was merged or
rebased during M0.

| Repository | Local baseline | Integration remote | Upstream baseline | Divergence from upstream |
|---|---|---|---|---|
| harness | `d734df9` | `origin/feat/simple-5arm-benchmark` | `origin/main` at `a6f32b0` | integration branch contains the approved R0 artifact |
| med-agent-hub | `297208c` | `origin/feat/hub-context-grounding` | `origin/main` at `1c5d836` | 33 ahead, 0 behind after M0 goldens |
| chartsearchai | `d315500` | `origin/harness-integration` | `upstream/main` at `0abbd61` | 54 ahead, 13 behind |
| chartsearchai-esm | `58ed478` | `origin/harness-integration` | `upstream/main` at `3003cd2` | 39 ahead, 2 behind; local pin is now remote-reachable |
| querystore | `de2ba8c` | `origin/harness-integration` | `upstream/main` at `a10faa3` | 2 ahead, 9 behind |
| catalyst | `3c1f1aa` | `origin/main` | `origin/main` at `3c1f1aa` | 0 ahead, 0 behind; no incoming delta |
| openmrs_chatbot | `2e723f8` | `origin/main` | `origin/main` at `2e723f8` | 0 ahead, 0 behind; no incoming delta |

### M2 Post-Merge Refresh

The merged M1 parent baseline is `d08c12e`; hub PR #12 is merged on `main` at `7869c62`.
All active OpenMRS remotes were fetched with pruning before M2 edits.

| Repository | M2 local baseline | Refreshed upstream | Divergence and PR state |
|---|---|---|---|
| chartsearchai | `d315500` | `upstream/main` at `5223f92` | 54 ahead, 14 behind; PR #26 open, mergeability indeterminate |
| chartsearchai-esm | `58ed478` | `upstream/main` at `3003cd2` | 39 ahead, 2 behind; PR #12 open and conflicting |
| querystore | `de2ba8c` | `upstream/main` at `a10faa3` | 2 ahead, 9 behind; PR #63 head `fb50dd9` clean before rebase |

### M2 Reconciled Heads

| Repository | Tested head | Reconciliation result |
|---|---|---|
| med-agent-hub | `bbb369c` | PR #13 ports drug-safety follow-through, requires explicit kilogram units, enforces every product envelope, and selects available defaults in the hub |
| chartsearchai | `e6bb4de` | PR #26 is a fixed-endpoint hub relay, persists interrupted In-Depth and safety warnings, and preserves terminal In-Depth across a missing final envelope |
| chartsearchai-esm | `38a8ce3` | PR #12 excludes progressive preview, uses only hub-authoritative defaults, and prevents interrupted In-Depth from hydrating as pending |
| querystore | `3f54b8b` | PR #63 rebased onto upstream `a10faa3` without a feature-tree change |

### M3 Remediation Heads

| Repository | Committed head | Result |
|---|---|---|
| med-agent-hub | `d7bd52e` | Temporal/date-value enforcement, final grounding lifecycle, context selection traceability, network-independent unprivileged runtime health, explicit encounter evidence, product citation-scope checks, and Git-owned temporal-facts provenance; 355 tests pass and independent re-review is clean. |
| chartsearchai | `550acd0` | Dead relay services removed; authoritative hub wire, audit identity, interruption state, and no-review grounding persistence covered; 88 tests pass |
| chartsearchai-esm | `b3ad02d` | Validation interruption, feedback retry, no-review preemption, and resolved/unresolved evidence UX corrected; 182 tests plus lint/build pass |

## Roadmap Validation

Validation was run after the approved body was copied and before implementation work began.

| Check | Result |
|---|---|
| Approved-body integrity | Pass: SHA-256 is `5f625cb9f1ac4a1682001fb40fd3cc6852ceed16c96e9b54e435b4e591a64d3d` |
| Required structure | Pass: 10 numbered sections, 24 acceptance gates, and 6 execution milestones |
| Local references | Pass: all 21 checked local links resolve from the roadmap location |
| Wrapper contamination | Pass: no `<proposed_plan>` wrapper tags were copied |
| Artifact index | Pass: roadmap and status are linked from `specs/artifacts/README.md` |
| Supersession | Pass: the June lane roadmap is explicitly marked historical and superseded |
| Remote reachability | Pass: R0 commit `d734df9` and ESM pin `58ed478` are reachable on their integration remotes |

## Upstream Disposition

Disposition status: Complete

`Keep` means replay the upstream change during M2. `Port` means preserve only the durable behavior
or documentation in its new owner and verify it there. `Exclude` means do not replay the change
because it conflicts with the approved architecture. The complete fetched deltas are listed below.

### Classified Upstream Snapshot

The gate binds each disposition inventory to a fixed baseline and classified upstream head. It
fails if any tracked upstream ref advances until the new commits are classified and this snapshot
is explicitly updated.

| Repository | Upstream ref | Baseline | Classified head | Inventory |
|---|---|---|---|---|
| Harness | `origin/main` | `d08c12e` | `d08c12e` | No incoming delta after the merged M1 baseline |
| med-agent-hub | `origin/main` | `7869c62` | `7869c62` | No incoming delta after merged hub PR #12 |
| ChartSearchAI | `upstream/main` | `d315500` | `5223f92` | Disposition table below |
| chartsearchai-esm | `upstream/main` | `58ed478` | `3003cd2` | Disposition table below |
| Querystore | `upstream/main` | `de2ba8c` | `a10faa3` | Disposition table below |
| Catalyst | `origin/main` | `3c1f1aa` | `3c1f1aa` | No incoming delta |
| openmrs_chatbot | `origin/main` | `2e723f8` | `2e723f8` | No incoming delta |

### ChartSearchAI (`d315500..upstream/main`)

| Commit | Disposition | Target and verification |
|---|---|---|
| `e16e93d` | Exclude | Embedded native-inference GPU documentation conflicts with G15/G19. |
| `b0c7abc` | Exclude | Progressive preview adds Java-owned inference orchestration and a provisional UI answer, both explicitly removed by G15/G17. |
| `49bf7a9` | Exclude | Patient-chart KV prewarm and bundled-engine lifecycle conflict with hub-owned readiness and the thin relay. |
| `cc3279a` | Exclude | Its core-event migration only feeds the excluded local index/prewarm path; no relay-owned behavior remains to port. |
| `f72bb89` | Exclude | Comment-only correction applies to services removed with the excluded prewarm/index path. |
| `65a76ce` | Keep | Preserve the Reference Application `3.7.0-rc.2` standalone baseline and verify it independently from the 2.8 data-remap contract. |
| `e9189cf` | Exclude | Documents the excluded Java prewarm global-property family. |
| `c27a41e` | Port | Move durable drug-KB demo guidance to med-agent-hub/harness ownership; do not restore Java KB ownership. |
| `ed5a153` | Port | Preserve the demo-patient naming correction with the ported guide. |
| `1b7c53e` | Port | Preserve the neutral patient identifier with the ported guide. |
| `e4dcf81` | Port | Translate bundled/custom KB wording to the hub's curated JSON and WHO-ATC sources. |
| `5678a36` | Port | Preserve the useful KB entry-schema reference against the hub schema. |
| `0abbd61` | Port | Move the demo override fixture to the hub/harness only if it passes the hub drug-safety contract. |
| `5223f92` | Port | Preserve its current-Core activator-test repair on the Java baseline; port weight-aware dosing, curated cross-branch reactivity groups, prose warnings, and null/fail-safe hardening to med-agent-hub before keeping Java drug ownership deleted. |

### ChartSearchAI ESM (`58ed478..upstream/main`)

| Commit | Disposition | Target and verification |
|---|---|---|
| `dc2d5f7` | Exclude | Progressive provisional-answer rendering conflicts with the committed fast Answer plus explicit checking lifecycle. |
| `3003cd2` | Keep | Replay the corrected O3 contributing link in the rebuilt integration branch. |

### Querystore (`de2ba8c..upstream/main`)

| Commit | Disposition | Target and verification |
|---|---|---|
| `c7e094f` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `cdc722c` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `796ff92` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `0f80220` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `c8a5922` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `0d40fba` | Keep | Review-skill prose only; rebase with no runtime impact. |
| `452f504` | Keep | Review-skill source-verification rule; rebase with no runtime impact. |
| `a5ea7a9` | Keep | Adds an OpenMRS module-review skill only; rebase with no runtime impact. |
| `a10faa3` | Keep | Review-skill prose only; rebase with no runtime impact. |

## M0 Verification

| Check | Result |
|---|---|
| Parent local CI | Pass: 561 passed, 37 environment-dependent skips, 3 slow-test deselections; no failures |
| Parent diff coverage | Pass: 93%, above the required 90% threshold; router policy is 97% covered |
| Parent remote CI | Pass: PR #33 `pytest-and-diff-coverage` succeeded at `d658d9b`; branch is mergeable |
| Hub local CI | Pass: 198 tests, including five byte-exact pre-refactor output contracts |
| Hub remote CI | Pass: PR #12 unit/contract and Docker checks succeeded at `297208c`; branch is mergeable |
| Pin reachability | Pass: every root submodule pin is contained by a fetched remote branch |
| Documentation drift | Pass: all seven repositories scanned; 19 historical marked files allowed |
| Red-first gate matrix | Pass: G01-G24 are emitted exactly once and any fail/pending result makes the script nonzero |
| Scope boundary | Pass: M0 changed tests, controls, status, and one reviewed harness bug; no M1 hub architecture implementation began |

The independent M0 review initially found that a remote endpoint carrying a hub-shaped model ID
could manage the local llama router, that tests preserved that behavior, and that G03/test coverage
could report stronger evidence than they actually checked. Commit `d658d9b` remediates those findings:

- router management now depends on an explicitly local endpoint, and a remote endpoint ignores even
  an explicit local-router residency cap;
- G03 validates each incoming SHA inside its repository-specific disposition section across the
  parent and all six submodules;
- the gate test executes the real shell matrix instead of checking source text alone; and
- the documentation-drift verifier explicitly recognizes architecture-verifier scripts as checks,
  not current-architecture claims.

The independent re-review found no remaining M0 blocker. It confirmed that batch/SSE convergence is
M1 G04 work, while M0 G06 correctly freezes the existing raw-leg batch envelopes before refactoring.

## M1 Verification

med-agent-hub PR #12 was squash-merged to `main` as `7869c62`. Its tree is byte-identical to the
tested consolidation/review head `31e6037`. It replaces the
flag-driven runner matrix with compiled profiles and one stream-and-drain stage engine, adds the
provider-neutral evidence ledger and exact context selector, enforces Answer and In-Depth safety,
and deletes the unused A2A/MCP/SDK runtime. The commit removes 8,594 lines and adds 7,992, a net
reduction of 602 lines while adding the required context and safety contracts.

| Check | Result |
|---|---|
| Hub unit/contract/integration suite | Pass: 246 tests; one third-party Starlette/httpx deprecation warning |
| Parent full suite | Pass: 569 passed, 37 environment-dependent skips, 3 slow-test deselections |
| Raw-leg compatibility | Pass: bridge and byte-exact golden suites remain green |
| Context quality | Pass: 12 cells, 48/48 required sources, 100% recall; 4 full and 8 selected contexts |
| Exact token budgets | Pass: measured inputs 16,226-20,478 tokens against a 20,480-token input limit |
| Proof integrity | Pass: artifact validates current comparison-set, hub-code, and router-config hashes |
| Documentation drift | Pass: all seven repositories scanned; 19 marked historical files allowed |
| Hub-scope acceptance gates | Pass: G04-G14 all green; G15 onward remain protected M2-M4 work |
| Remote reachability | Pass: hub merge commit `7869c62` is the head of `origin/main` |

The first independent M1 review reproduced seven blockers that the original checks had missed:
task-local budget loss between streamed events, inherited In-Depth grounding verdicts, a fallback
without temporal metadata, hidden product envelopes without exact budgets, a parallel team KB path,
a stale/weak context proof, and duplicated product/review-leg rewrite logic. All seven were converted
into runtime fixes and regression tests. A fresh independent reviewer reran those repros and found no
remaining blocker; its G04-G14 table is entirely green.

Copilot's merge review then identified four configuration-edge findings. Commit `31e6037` sends
backend bearer authentication during profile discovery, removes invented OpenMRS administrator
credentials, rejects partial Querystore configuration at startup, preserves explicit source
failures, and corrects the stale empty-chart docstring. The paired parent change removes Compose
credential defaults and requires a least-privileged `Get Patients` service account. Local hub and
parent suites pass. Hub unit/contract and Docker checks are green on the tree-identical tested head
`31e6037`; parent GitHub Actions run `29121901758` passed the full harness suite and changed-line
coverage on `59c2df4`. PR #12 was then squash-merged as `7869c62` with no tree delta.

The first refreshed parent PR #33 run after M1 failed because GitHub Actions checked out the parent
without submodules while run metadata now resolves authoritative profile configuration from the
pinned hub. The production behavior and local submodule-backed test passed; the submodule-free CI
copy emitted an empty frozen arm configuration. The follow-up makes checkout recursive while keeping
test execution scoped to the parent with `--ignore=targets`, and adds direct tests for the context
quality proof command. Local CI-equivalent results are 567 passed, 37 skipped, and 3 deselected, with
93% changed-line coverage. GitHub Actions run `29119406818` passed both the full harness suite and
changed-line coverage on commit `a2af5fa`. The run reported a non-blocking deprecation annotation for
Node 20-based action runtimes; GitHub currently forces those actions to Node 24.

## M2 Verification

The OpenMRS integration branches were rebuilt from current upstream rather than merging the old
integration histories. Safety backup tags and separate rebuild branches were pushed before the
existing PR heads were updated with exact force-with-lease checks.

| Check | Result |
|---|---|
| Hub drug-safety follow-through | Pass: 263 tests; weight observations require explicit kilogram units; every product envelope enforces temporal checks; authoritative available-default selection passes |
| ChartSearchAI module | Pass: clean packaged OMOD; 83 current tests with no failures, errors, or skips; pending interruption, terminal EOF, and safety-warning reload are covered |
| Thin relay boundary | Pass: no bundled inference, Java stage decomposition, Java grounding/safety/context pipeline, Querystore dependency, client endpoint switching, or bundled serving weights |
| ESM contracts | Pass: TypeScript and lint clean; 173 tests; production build succeeds with the existing asset-size warning only |
| Profile discovery | Pass: product-only metadata, authoritative labels/default, unavailable-state handling, and profile-only request tests |
| Lifecycle persistence | Pass: fast Answer, validation update, In-Depth, same-message update, hydration, multi-turn, and cancellation unit/contract tests |
| Querystore PR #63 | Pass: rebased onto all nine classified upstream commits; 471 tests with no failures/errors and two optional-model eval skips |
| Documentation drift | Pass: all seven repositories scanned; 19 marked historical files allowed |
| Remote PR CI | Pass at exact heads: parent `f54442a`, hub `bbb369c`, ChartSearchAI `e6bb4de`, ESM `38a8ce3`, and Querystore `3f54b8b`; all required checks are green |
| Stage-refactor matrix | Pass for all M2-owned checks at the reconciled heads; only the live multi-turn/preempt checks reserved for M3 are pending because `RUN_E2E=1` was not set |
| Independent review | Pass after remediation: the targeted re-review found no blocker, reran 11 focused Java tests, and confirmed pending interruption plus `indepth_done`/`indepth_error` EOF semantics; the exact-head fix is `e6bb4de` |

## M3 Verification

| Check | Result |
|---|---|
| Canonical local startup | Implemented; proof pending: `scripts/chartsearchai-local.sh` delegates hub deployment to `make med-agent-hub-up`, verifies profile availability/default integrity, warms E4B, and runs a full reviewed-lifecycle relay/persistence probe. The hub runtime no longer contacts a package mirror for curl; Compose inherits its Python health check, maps a non-root host UID/GID for trace writes, rejects root launchers, and proves the actual bind mount is writable. G19 remains pending until regenerated on clean committed heads. |
| Local patient source | Pass: the generated `med-agent-hub` OpenMRS user has only the `Get Patients` privilege and returned records through the Querystore adapter |
| Default profile discovery | Pass: `single-e4b-checked` is available, authoritative, human-readable, and marked default; the ESM picker renders hub profile metadata |
| Deterministic local checks | Pass on the committed companion trees: 355 hub tests; 182 ESM tests plus lint/build; 88 Java tests through the complete Maven reactor; and 639 parent tests with 35 expected skips and 3 deselections. The parent suite required normal macOS process/semaphore permissions for its existing SQLMesh and Playwright tests. |
| Product Answer contract | Pass in code at hub `d7bd52e`: product profiles always apply the hub-owned strict `chart_answer` schema, including when a caller supplies a conflicting `response_format`; raw low-level legs remain caller-controlled. ChartSearchAI marks every product request with `require_product_profile`, and the hub rejects internal/experimental legs on that path while preserving direct low-level hub clients. Exact accounting uses the same model/messages/tools payload; llama.cpp applies `response_format` as an out-of-band generation grammar with zero prompt tokens, and the supported apply-template fallback is tested to preserve that boundary. ChartSearchAI `550acd0` removes its duplicate schema builder and preserves the full hub wire for synchronous clients. Exact-head deployment proof remains below. |
| Compiled execution plan | Pass with a simpler implementation: immutable `Profile.stages` is the validated compiled plan consumed by runtime. The unused `StagePlan` copy and its test-only accessor were removed rather than preserving a ceremonial wrapper. |
| Product temporal anchor | Pass in code and live product trace: product profiles default to wall-clock today in the configured clinical/site timezone (`2026-07-10` for the Honolulu host while the container was on UTC July 11), a fixed `HUB_ANCHOR=2026-06-20` remains authoritative for evaluation, and low-level experimental legs retain latest-record behavior when no anchor is supplied. The engine resolves this date once and shares the same ISO value with drug safety and temporal facts. |
| Temporal/In-Depth remediation | Pass in code and adversarial review: table rows preserve date/value associations; every selected numeric claim is checked against the full series ledger; ranges, ordinal pairing, mixed measurements, and Unicode clinical-unit typography are covered; In-Depth claims without citations are withheld; patches stay within original citations; unsafe claims are removed; and non-substantive Answers deterministically withhold In-Depth. |
| Citation-set grounding | Pass: claims supported by multiple citations are checked against a bounded combined source set; claim/path-level checks are retained; mixed, unchecked, and unsupported In-Depth support cannot report complete; and positive/negative source-set UI wording does not imply an individual-record verdict |
| Grounding-before-preemption | Pass in code: `answer_validation` is emitted only after final post-review grounding, so the ESM cannot unlock/preempt while Answer references are still `checking`; `indepth_pending` then starts the separately preemptable tail. |
| Atomic In-Depth evidence | Pass: `indepth_done`/`indepth_error` carry the full final envelope while preserving their legacy top-level fields; Java persists final references and verdicts with the terminal In-Depth state, and EOF coverage requires them |
| Warm performance observation | Pending recollection: the previous identity-bound distribution described hub `de8614e`; G20 must be recollected against committed hub `d7bd52e` and its exact labeled image. The criterion remains relative with `fixed_latency_threshold: null`. |
| Live multi-turn/preemption | Pending committed-head rerun: the focused proof on `de8614e` observed a positive Q2 cancellation marker with `router_lock_released=true` and a completed Q3 trace, but the current hub is now `d7bd52e`. |
| Video proof | Stale: the 2026-07-10 video predates the final temporal/reviewer remediation and is retained only as a prior artifact. A new paced video is required against the final labeled image. |
| M3 independent review | Pass after iterative remediation. Architecture, clinical-safety, and integration reviewers report no remaining P0-P2 blocker. Their findings drove red-first coverage for date/value edge cases, test isolation, no-review preemption, full-envelope hydration, complete ESM asset provenance, feedback identity/retry, and evidence-title/resolution UX. |
| Release-proof hardening | Pass in code: the 24-cell audit has positive and failure-injection coverage; complete In-Depth now requires substantive text plus an enforce-gate terminal result; independent judge manifests require actor/model/method and source/output hashes; combined scores are deterministically recomputed; per-cell review requires an explicit comparable baseline or a reason it is not comparable; DIGI-UW/code-qa must report zero blockers against exact reviewed SHAs. |
| Source indexing | Complete for candidate readiness: Elasticsearch contains 427,890 observation documents against 427,897 active source rows and all other Querystore clinical indexes are populated. The remaining seven-row difference must not affect the fixed candidate patients; preflight verifies each scenario before launch. |
| Remaining proof | Push the committed companions and parent pin, deploy those exact clean heads, regenerate G09/G18-G20 and video evidence, then run, independently judge, inspect, and publish the 24-cell candidate. Final DIGI-UW/code-qa and release hygiene remain pending. |

## Milestones

| Milestone | Status | Evidence or blocker |
|---|---|---|
| R0 Persist roadmap | Complete | Roadmap/status/index committed and pushed at `d734df9`; post-copy validation is recorded above |
| M0 Stabilize baseline | Complete | All refreshed pins are reachable, upstream deltas are classified, raw-leg goldens are pinned, and the independent re-review has no blocker |
| M1 Consolidate hub | Complete | Hub PR #12 is merged at `7869c62`; 246 hub tests, 569 parent tests, hash-bound context proof, independent re-review, review remediation, and companion CI pass. User Signoff B granted. |
| M2 Reconcile OpenMRS integration | Complete | Five independent-review findings and the terminal EOF follow-up are remediated; exact-head local suites, companion CI, architecture gates, documentation drift, and final independent review pass. User Signoff C granted. |
| M3 Product/local proof | In progress | User Signoff C granted 2026-07-10; portable startup, readiness, live E2E, performance, and video proof are underway |
| M4 Evaluation and release | Pending | After M3 correctness and deterministic QA are clean, run, judge, and publish a fresh profile-based candidate report before final validation; final release still requires User Release Signoff D |

## Acceptance Gates

| Gate | Status | Current evidence |
|---|---|---|
| G01 Roadmap integrity | Pass | Structure/link validation passed; approved SHA-256 recorded above |
| G02 Baseline integrity | In progress | Hub #12 and parent #33 are merged, but current M3 companion heads remain ahead of their remotes and the parent integration tree is intentionally dirty until final proof and review complete |
| G03 Upstream reconciliation | Pass | Fixed baseline-to-classified-head ranges cover every disposition, and the gate fails if a tracked upstream ref advances |
| G04 One engine | Pass | Streaming and blocking drain one `StageEngine`; old runners/flag bridge are deleted; cancellation and budget context tests pass |
| G05 Profile correctness | Pass | Profiles compile immutable stage plans, invalid order fails, unknown IDs return `model_not_found`, and metadata is authoritative |
| G06 Raw-leg compatibility | Pass | Five byte-exact pre-refactor envelopes remain green; merged hub `7869c62` is tree-identical to tested head `31e6037`, where the complete 246-test suite passed |
| G07 Source independence | Pass | Inline, optional Querystore, static KB, and mock alternate adapters share one normalized source contract; hub starts without Querystore |
| G08 Context budgeting | Pass | Every product envelope requires exact tokenizer-backed budgeting; the exact rendered model/messages/tools prompt is counted and capped before backend calls, while llama.cpp's output schema remains a zero-input-token generation grammar |
| G09 Context quality | In progress | The selector now records an inclusion reason for every selected record and uses token-boundary identifier matching; the prior proof predates that schema and must be regenerated on the final hub head |
| G10 Answer temporal safety | Pass | Every `output: product` profile ignores attempts to disable temporal facts or weaken enforce; ChartSearchAI marks product requests and the hub rejects low-level/internal profile ids on that path |
| G11 In-Depth temporal safety | Pass | Every displayed claim is deterministically temporally gated and must cite current-ledger evidence; uncited, rejected, mixed, unchecked, unsupported, reviewer-unavailable, or empty claim sets cannot report complete |
| G12 Review ordering | Pass | Product and review legs share one conservative review implementation; rewrites are re-gated and final Answer refs are re-resolved before grounding |
| G13 Citation integrity | Pass | Prior-turn markers are stripped; Answer and In-Depth citations resolve to the current ledger; claim/path checks and source sets survive the wire and terminal persistence |
| G14 Drug-safety parity | Pass | Hub parity, unit-safe weight, Java assistant-wire persistence, and history rehydration contracts pass |
| G15 Thin OpenMRS relay | Pass | Java has one fixed hub endpoint and one profile request; it no longer supplies prompts or an answer schema, preserves the complete hub wire for sync and staged clients, maps structured `insufficient_context`, and has deleted the dead local chart-size exception plus legacy inference/discovery/grounding/context code |
| G16 Product discovery | Pass | Hub availability plus explicit `selection_priority` produces at most one available default; ESM never invents a list-order fallback |
| G17 Lifecycle UX | Pass in code | Reviewed and no-review profiles remain non-preemptable until final Answer grounding; Java preserves terminal validation if In-Depth is interrupted; the ESM resolves stale checking states, preserves checked preemption, and shows unresolved sources and withheld In-Depth explicitly |
| G18 Multi-turn and cancellation | In progress | Positive cancellation and slot-release evidence passed on `de8614e`; rerun is required on the final product head before this gate returns to Pass |
| G19 Local setup | In progress | Canonical startup and a full reviewed-lifecycle probe are implemented. The proof requires exact event order, final grounding, complete In-Depth, byte-equivalent stream/hydration envelopes, mounted OMOD identity, and every staged/served ESM asset plus import-map target; regeneration on clean committed heads is required. |
| G20 Performance | In progress | The collector binds deployed image revision plus source/config/model identity; the warm distribution must be recollected on hub `d7bd52e` without an arbitrary absolute latency threshold. |
| G21 Evaluation | In progress | The exact 24-cell E4B/12B candidate, deterministic audit, independent-actor provenance, recomputed consensus, and per-cell baseline contract are executable; source indexing is complete and exact-head deployment/preflight are next |
| G22 Documentation | Pass | Current READMEs, contributor rules, workflow comments, API docs, and all submodules pass the seven-repository drift scan |
| G23 Independent QA | Pending | The gate now requires all five DIGI-UW/code-qa reviews to pass with zero blockers, hash-bound reports, and exact root/submodule SHAs; final-head review execution remains pending |
| G24 Release hygiene | Pending | Final CI, E2E, PR, pin, and clean-tree proof required |

## Signoffs

| Signoff | Status | Scope unlocked |
|---|---|---|
| Roadmap approval | Granted 2026-07-09 | R0 and M0 |
| User Signoff A | Granted 2026-07-10 | M1 hub consolidation |
| User Signoff B | Granted 2026-07-10 | M2 OpenMRS integration reconciliation |
| User Signoff C | Granted 2026-07-10 | M3 product/local proof completion and release preparation |
| Pre-final report authorization | Granted 2026-07-10 | Run, judge, and publish one fresh profile-based candidate report after deterministic QA and before final validation; this does not authorize final release, merges, or obsolete-PR closure |
| User Release Signoff D | Pending | Merge, publication, obsolete-PR closure, and release completion |

## Amendments

| Date | Approved change | Reason and replacement evidence |
|---|---|---|
| 2026-07-10 | G20 no longer uses the roadmap's fixed 30-second local Answer threshold as a pass/fail criterion. | User clarified that local-machine performance is variable and the absolute limit is arbitrary. M3 discloses cold/warm state, records host/runtime provenance and warm-run distributions, and separates pre-display pipeline overhead from the underlying answer-stage work. Browser tests require eventual lifecycle completion but do not fail on an absolute latency number. |
| 2026-07-10 | A fresh judged report must be run and published before final validation. | After the known M3 correctness blockers are fixed and deterministic QA is clean, create a new candidate set that exercises the product profiles rather than the obsolete two-call experimental arms. Run `single-e4b-checked` as the default product path and `single-12b-checked` as the quality comparison across the 12 temporal/date scenarios, exclude high-team, preserve independent judgments, publish the report, and inspect per-cell regressions before the final validation/release pass. This is limited publication authorization for that report, not User Release Signoff D. |
