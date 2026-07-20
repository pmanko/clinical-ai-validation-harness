# OpenMRS Dual-Provider Foundational Parity Roadmap Status

Execution record for `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`openmrs-dual-provider-parity-roadmap.md`](openmrs-dual-provider-parity-roadmap.md) |
| Approval | Explicit user instruction to implement the roadmap on 2026-07-20 |
| Approved roadmap SHA-256 | `cf2c8b33c81ab69ece6150d0171ea3e940f89edfa3968e02c6bd9bf8abc274f5` |
| Current boundary | Roadmap persistence and executable-gate foundation |
| Supersedes | `MAH-CONSOLIDATION-2026-07-09-v1` for active architecture and execution authority |
| Preserved prior decisions | Temporal-facts Git provenance, stable evaluation IDs, and medication-knowledge safety boundary remain active unless this roadmap explicitly changes them |
| Signoff 1 | Pending: baseline, contracts, upstream dispositions, and branch-rebuild procedure |
| Signoff 2 | Pending: foundational dual-provider product proof |
| Signoff 3 | Pending: validation-harness evidence, demo release, merges, and publication |

## Initial Baseline

| Repository | Head | PR / status |
|---|---:|---|
| harness | `511c6ee` | #35 draft, mergeable, CI green |
| med-agent-hub | `32783bc` | #13 open, mergeable, CI green |
| querystore | `fd8a00c` | #63 open, mergeable, CI green |
| chartsearchai | `7ebca9c` | #26 draft and conflicting; backup required before rebuild |
| chartsearchai-esm | `30e94e7` | #12 draft and mergeable; backup required before rebuild |
| chartsearchai upstream | `577d818` | Freshly fetched local upstream reference; revalidate before branch rebuild |

## Gate Evidence

| Gate | Status | Evidence |
|---|---|---|
| G01 Roadmap integrity | In progress | Canonical file, hash, supersession markers, and gate script added; verification pending |
| G02-G22 | Pending | No runtime implementation has begun |

## Amendments and Deviations

None. Material changes require explicit user approval and a dated entry here with rationale, safer alternative, residual risk, and changed gates.
