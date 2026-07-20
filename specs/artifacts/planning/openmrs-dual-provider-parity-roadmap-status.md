# OpenMRS Dual-Provider Foundational Parity Roadmap Status

Execution record for `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`openmrs-dual-provider-parity-roadmap.md`](openmrs-dual-provider-parity-roadmap.md) |
| Approval | Explicit user instruction to implement the roadmap on 2026-07-20 |
| Approved roadmap SHA-256 | `cf2c8b33c81ab69ece6150d0171ea3e940f89edfa3968e02c6bd9bf8abc274f5` |
| Current boundary | Baseline, upstream-disposition, and conformance-contract foundation |
| Supersedes | `MAH-CONSOLIDATION-2026-07-09-v1` for active architecture and execution authority |
| Preserved prior decisions | Temporal-facts Git provenance, stable evaluation IDs, and medication-knowledge safety boundary remain active unless this roadmap explicitly changes them |
| Signoff 1 | Pending: baseline, contracts, upstream dispositions, and branch-rebuild procedure |
| Signoff 2 | Pending: foundational dual-provider product proof |
| Signoff 3 | Pending: validation-harness evidence, demo release, merges, and publication |

## Initial Baseline

| Repository | Head | PR / status |
|---|---:|---|
| harness (approval baseline) | `511c6ee` | #35 draft, mergeable, CI green |
| harness (roadmap foundation) | `8bc9caa` | Roadmap/hash/gate foundation committed and pushed |
| med-agent-hub | `32783bc` | #13 open, mergeable, CI green |
| querystore | `fd8a00c` | #63 open, mergeable, CI green |
| chartsearchai | `7ebca9c` | #26 draft and conflicting; backup required before rebuild |
| chartsearchai-esm | `30e94e7` | #12 draft and mergeable; backup required before rebuild |
| chartsearchai upstream | `577d818` | Freshly fetched local upstream reference; revalidate before branch rebuild |

The refreshed repository state, upstream dispositions, and rollback refs are recorded in
[`openmrs-dual-provider-upstream-inventory.md`](openmrs-dual-provider-upstream-inventory.md).

## Gate Evidence

| Gate | Status | Evidence |
|---|---|---|
| G01 Roadmap integrity | Passed | `8bc9caa`; `scripts/verify-dual-provider-parity-gates.sh --phase foundation` verifies the immutable SHA, supersession, index, and per-gate status rows. |
| G02 Baseline integrity | Passed | After `ef95ee2` was pushed, `scripts/verify-dual-provider-parity-gates.sh --phase foundation` confirmed every root/submodule tree is clean, every head is remote-reachable, both rollback refs exist, and the inventory is present. |
| G03 Contract first | Prepared | Versioned provider, context, temporal, freshness, and safety fixtures are checked in. Owning-language tests must be added red-first after Signoff 1. |
| G04 Provider isolation | Pending | No runtime implementation has begun. |
| G05 Provider selection | Pending | No runtime implementation has begun. |
| G06 Bundled preservation | Pending | No branch rebuild has begun. |
| G07 QueryStore semantics | Pending | No runtime implementation has begun. |
| G08 Freshness | Pending | No runtime implementation has begun. |
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

## Amendments and Deviations

None. Material changes require explicit user approval and a dated entry here with rationale, safer alternative, residual risk, and changed gates.
