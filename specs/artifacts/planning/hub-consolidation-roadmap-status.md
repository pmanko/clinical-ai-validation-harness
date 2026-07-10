# Hub Consolidation Roadmap Status

Execution state for `MAH-CONSOLIDATION-2026-07-09-v1`.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`hub-consolidation-roadmap.md`](hub-consolidation-roadmap.md) |
| Approval | Explicit user instruction to implement the roadmap on 2026-07-09 |
| Approved roadmap SHA-256 | `5f625cb9f1ac4a1682001fb40fd3cc6852ceed16c96e9b54e435b4e591a64d3d` |
| Current execution boundary | R0 and M0 authorized |
| Next protected boundary | M1 requires User Signoff A |
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
| chartsearchai-esm | `58ed478` | `origin/harness-integration` | `origin/main` at `3003cd2` | 39 ahead, 2 behind; local pin is now remote-reachable |
| querystore | `de2ba8c` | `origin/harness-integration` | `upstream/main` at `a10faa3` | 2 ahead, 9 behind |
| catalyst | `3c1f1aa` | checked-out remote branch | fetched remote head | no integration delta classified for this roadmap |
| openmrs_chatbot | `2e723f8` | checked-out remote branch | fetched remote head | no integration delta classified for this roadmap |

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

### ChartSearchAI ESM (`58ed478..origin/main`)

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

## Milestones

| Milestone | Status | Evidence or blocker |
|---|---|---|
| R0 Persist roadmap | Complete | Roadmap/status/index committed and pushed at `d734df9`; post-copy validation is recorded above |
| M0 Stabilize baseline | In progress | Remotes fetched, ESM pin published, goldens captured, red-first gate script added, and local PR #33 coverage is 93%; CI confirmation remains |
| M1 Consolidate hub | Blocked by signoff | Requires User Signoff A |
| M2 Reconcile OpenMRS integration | Blocked by signoff | Requires User Signoff B |
| M3 Product/local proof | Pending | Requires M2 completion and User Signoff C |
| M4 Evaluation and release | Pending | Requires M3 completion and User Release Signoff D |

## Acceptance Gates

| Gate | Status | Current evidence |
|---|---|---|
| G01 Roadmap integrity | Pass | Structure/link validation passed; approved SHA-256 recorded above |
| G02 Baseline integrity | Pending | ESM pin is reachable and local CI/diff coverage pass; PR #33 must confirm the pushed repair |
| G03 Upstream reconciliation | Pass | Every fetched ChartSearchAI, ESM, and Querystore upstream commit has a keep/port/exclude disposition above |
| G04 One engine | Pending | M1 work; current duplicate runtime paths remain |
| G05 Profile correctness | Pending | M1 work |
| G06 Raw-leg compatibility | Pass | Five byte-exact pre-refactor envelopes, including all three raw legs, are pinned in hub `tests/goldens/`; hub commit `297208c` is pushed and 198 tests pass |
| G07 Source independence | Pending | M1 work |
| G08 Context budgeting | Pending | M1 work |
| G09 Context quality | Pending | M1 and M4 work |
| G10 Answer temporal safety | Pending | Existing partial coverage; product invariant remains to prove |
| G11 In-Depth temporal safety | Pending | Current In-Depth claims are not deterministically gated |
| G12 Review ordering | Pass | Existing post-rewrite re-gate ordering tests pass; M1 must preserve this through the unified engine |
| G13 Citation integrity | Pending | Product and multi-turn proof remains |
| G14 Drug-safety parity | Pass | Curated JSON and WHO-ATC unit/integration tests pass in the 197-test hub baseline |
| G15 Thin OpenMRS relay | Pending | Upstream reconciliation and deletion gates remain |
| G16 Product discovery | Pending | LM Studio-specific discovery residue remains |
| G17 Lifecycle UX | Pending | Existing staged UI is partial baseline evidence |
| G18 Multi-turn and cancellation | Pending | Existing tests are baseline evidence; final live proof remains |
| G19 Local setup | Pending | Canonical portable command does not yet exist |
| G20 Performance | Pending | Warm E4B benchmark not yet run |
| G21 Evaluation | Pending | Deterministic QA and candidate run not yet run |
| G22 Documentation | Pass | `scripts/verify-doc-drift.sh` passes on the M0 baseline; final alignment remains a release rerun |
| G23 Independent QA | Pending | Runs at each milestone and final release |
| G24 Release hygiene | Pending | Final CI, E2E, PR, pin, and clean-tree proof required |

## Signoffs

| Signoff | Status | Scope unlocked |
|---|---|---|
| Roadmap approval | Granted 2026-07-09 | R0 and M0 |
| User Signoff A | Pending | M1 hub consolidation |
| User Signoff B | Pending | M2 OpenMRS integration reconciliation |
| User Signoff C | Pending | M3 product/local proof completion and release preparation |
| User Release Signoff D | Pending | Merge, publication, obsolete-PR closure, and release completion |

## Amendments

None.
