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

This is the pre-fetch snapshot observed when execution began. M0 will refresh remotes and record
the resulting immutable upstream baseline before implementation work.

| Repository | Checked-out SHA | Branch | Pull request state at approval |
|---|---|---|---|
| harness | `c5749e6` | `feat/simple-5arm-benchmark` | #33 open, mergeable, CI blocked |
| med-agent-hub | `fb9cdbb` | `feat/hub-context-grounding` | #12 open, clean, CI green |
| chartsearchai | `d315500` | `harness-integration` lineage | #26 draft, conflicting |
| chartsearchai-esm | `58ed478` | `harness-integration` | #12 draft, conflicting; pin not yet remote-reachable |
| querystore | `de2ba8c` | `harness-integration` lineage | #63 open, clean, CI green |
| catalyst | `3c1f1aa` | `main` | unchanged baseline dependency |
| openmrs_chatbot | `2e723f8` | `main` | unchanged baseline dependency |

## Milestones

| Milestone | Status | Evidence or blocker |
|---|---|---|
| R0 Persist roadmap | In progress | Roadmap copied and validated; status/index/commit/push remain |
| M0 Stabilize baseline | Pending | Begins after the R0 commit is remote-reachable |
| M1 Consolidate hub | Blocked by signoff | Requires User Signoff A |
| M2 Reconcile OpenMRS integration | Blocked by signoff | Requires User Signoff B |
| M3 Product/local proof | Pending | Requires M2 completion and User Signoff C |
| M4 Evaluation and release | Pending | Requires M3 completion and User Release Signoff D |

## Acceptance Gates

| Gate | Status | Current evidence |
|---|---|---|
| G01 Roadmap integrity | Pass | Structure/link validation passed; approved SHA-256 recorded above |
| G02 Baseline integrity | Pending | PR #33 CI and ESM pin reachability remain |
| G03 Upstream reconciliation | Pending | M0 disposition inventory not yet captured |
| G04 One engine | Pending | M1 work; current duplicate runtime paths remain |
| G05 Profile correctness | Pending | M1 work |
| G06 Raw-leg compatibility | Pending | M0 goldens and M1 verification required |
| G07 Source independence | Pending | M1 work |
| G08 Context budgeting | Pending | M1 work |
| G09 Context quality | Pending | M1 and M4 work |
| G10 Answer temporal safety | Pending | Existing partial coverage; product invariant remains to prove |
| G11 In-Depth temporal safety | Pending | Current In-Depth claims are not deterministically gated |
| G12 Review ordering | Pending | Existing Answer ordering tests pass; unified-engine proof remains |
| G13 Citation integrity | Pending | Product and multi-turn proof remains |
| G14 Drug-safety parity | Pending | Existing hub suite is baseline evidence; final parity remains |
| G15 Thin OpenMRS relay | Pending | Upstream reconciliation and deletion gates remain |
| G16 Product discovery | Pending | LM Studio-specific discovery residue remains |
| G17 Lifecycle UX | Pending | Existing staged UI is partial baseline evidence |
| G18 Multi-turn and cancellation | Pending | Existing tests are baseline evidence; final live proof remains |
| G19 Local setup | Pending | Canonical portable command does not yet exist |
| G20 Performance | Pending | Warm E4B benchmark not yet run |
| G21 Evaluation | Pending | Deterministic QA and candidate run not yet run |
| G22 Documentation | Pending | New roadmap is canonical; cross-repo final alignment remains |
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
