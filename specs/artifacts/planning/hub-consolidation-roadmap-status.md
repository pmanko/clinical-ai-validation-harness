# Hub Consolidation Roadmap Status

Execution state for `MAH-CONSOLIDATION-2026-07-09-v1`.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`hub-consolidation-roadmap.md`](hub-consolidation-roadmap.md) |
| Approval | Explicit user instruction to implement the roadmap on 2026-07-09 |
| Approved roadmap SHA-256 | `5f625cb9f1ac4a1682001fb40fd3cc6852ceed16c96e9b54e435b4e591a64d3d` |
| Current execution boundary | M1 hub consolidation complete; awaiting User Signoff B |
| Next protected boundary | M2 OpenMRS reconciliation requires User Signoff B |
| Deviations | None |

The roadmap intentionally preserves the exact approved Plan Mode body, including its
pre-approval status line. This companion file is the authoritative execution-status record.

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

### ChartSearchAI (`d315500..upstream/main`)

| Commit | Disposition | Target and verification |
|---|---|---|
| `e16e93d` | Exclude | Bundled llama-server GPU documentation conflicts with G15/G19. |
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

med-agent-hub consolidation commit `1ca429b`, plus review remediation `31e6037`, is pushed on
`origin/feat/hub-context-grounding`. It replaces the
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
| Remote reachability | Pass: hub commit `31e6037` is contained by `origin/feat/hub-context-grounding` |

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
parent suites pass; refreshed companion CI is required before this remediation is complete.

The first refreshed parent PR #33 run after M1 failed because GitHub Actions checked out the parent
without submodules while run metadata now resolves authoritative profile configuration from the
pinned hub. The production behavior and local submodule-backed test passed; the submodule-free CI
copy emitted an empty frozen arm configuration. The follow-up makes checkout recursive while keeping
test execution scoped to the parent with `--ignore=targets`, and adds direct tests for the context
quality proof command. Local CI-equivalent results are 567 passed, 37 skipped, and 3 deselected, with
93% changed-line coverage. GitHub Actions run `29119406818` passed both the full harness suite and
changed-line coverage on commit `a2af5fa`. The run reported a non-blocking deprecation annotation for
Node 20-based action runtimes; GitHub currently forces those actions to Node 24.

## Milestones

| Milestone | Status | Evidence or blocker |
|---|---|---|
| R0 Persist roadmap | Complete | Roadmap/status/index committed and pushed at `d734df9`; post-copy validation is recorded above |
| M0 Stabilize baseline | Complete | All refreshed pins are reachable, upstream deltas are classified, raw-leg goldens are pinned, and the independent re-review has no blocker |
| M1 Consolidate hub | Verification pending | Hub `31e6037` is pushed; 246 hub tests, 569 parent tests, hash-bound context proof, and independent re-review pass. Refreshed companion CI must pass after review remediation. |
| M2 Reconcile OpenMRS integration | Blocked by signoff | Requires User Signoff B |
| M3 Product/local proof | Pending | Requires M2 completion and User Signoff C |
| M4 Evaluation and release | Pending | Requires M3 completion and User Release Signoff D |

## Acceptance Gates

| Gate | Status | Current evidence |
|---|---|---|
| G01 Roadmap integrity | Pass | Structure/link validation passed; approved SHA-256 recorded above |
| G02 Baseline integrity | Pending | Review remediation is pushed to hub #12; refreshed hub and parent CI must pass on the updated companion heads |
| G03 Upstream reconciliation | Pass | Every incoming commit across the parent and all six submodules is absent or has a repository-bound keep/port/exclude disposition |
| G04 One engine | Pass | Streaming and blocking drain one `StageEngine`; old runners/flag bridge are deleted; cancellation and budget context tests pass |
| G05 Profile correctness | Pass | Profiles compile immutable stage plans, invalid order fails, unknown IDs return `model_not_found`, and metadata is authoritative |
| G06 Raw-leg compatibility | Pass | Five byte-exact pre-refactor envelopes, including all three raw legs, remain green at pushed hub commit `31e6037`; the complete 246-test suite passes |
| G07 Source independence | Pass | Inline, optional Querystore, static KB, and mock alternate adapters share one normalized source contract; hub starts without Querystore |
| G08 Context budgeting | Pass | Every product envelope requires exact tokenizer-backed budgeting; actual chat payloads are counted and capped before backend calls |
| G09 Context quality | Pass | Hash-bound proof retains 48/48 required sources over 12 E4B/12B cells within exact budgets |
| G10 Answer temporal safety | Pass | Every product Answer and fallback records enforce-gate metadata; malformed/non-ledger dates and non-substantive output cannot ship checked |
| G11 In-Depth temporal safety | Pass | Every displayed claim is gated; rejected or empty claim sets cannot report complete |
| G12 Review ordering | Pass | Product and review legs share one conservative review implementation; rewrites are re-gated and final Answer refs are re-resolved before grounding |
| G13 Citation integrity | Pass | Prior-turn markers are stripped; Answer and In-Depth citations resolve to the current ledger and receive separate grounding checks |
| G14 Drug-safety parity | Pass | Curated JSON and WHO-ATC contract/integration suites pass in the 239-test hub suite |
| G15 Thin OpenMRS relay | Fail | Legacy Java inference/discovery/orchestration remains for M2 deletion after M1 |
| G16 Product discovery | Fail | LM Studio/client-curated discovery residue and missing authoritative default metadata remain |
| G17 Lifecycle UX | Fail | Complete Answer and In-Depth validation lifecycle UX is not implemented |
| G18 Multi-turn and cancellation | Pending | Existing tests are baseline evidence; final live proof remains |
| G19 Local setup | Fail | Canonical portable `chartsearchai-local` command does not yet exist |
| G20 Performance | Pending | Warm E4B benchmark not yet run |
| G21 Evaluation | Pending | Deterministic QA and candidate run not yet run |
| G22 Documentation | Pass | `scripts/verify-doc-drift.sh` passes on the M0 baseline; final alignment remains a release rerun |
| G23 Independent QA | Pending | M0 independent review passed after remediation; complete DIGI-UW/code-qa evidence remains a release requirement |
| G24 Release hygiene | Pending | Final CI, E2E, PR, pin, and clean-tree proof required |

## Signoffs

| Signoff | Status | Scope unlocked |
|---|---|---|
| Roadmap approval | Granted 2026-07-09 | R0 and M0 |
| User Signoff A | Granted 2026-07-10 | M1 hub consolidation |
| User Signoff B | Pending | M2 OpenMRS integration reconciliation |
| User Signoff C | Pending | M3 product/local proof completion and release preparation |
| User Release Signoff D | Pending | Merge, publication, obsolete-PR closure, and release completion |

## Amendments

None.
