# Catalyst Validation Integration Roadmap Status

Execution state for the Catalyst validation integration remediation roadmap.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`catalyst-validation-integration-roadmap.md`](catalyst-validation-integration-roadmap.md) |
| Authorization | Explicit user instruction to implement the approved plan on 2026-07-21 |
| Approved roadmap SHA-256 (pre-A1) | `b00a063bf2b78494a3a719436d4609127eb2e845153d1ab2f9153d1e018e6ef8` |
| Approved roadmap SHA-256 (A1, current) | `37c13c468d274b985a0f48e0e6e5cfb2e3e9eaf3b0fb0fd1ace6e73fca1cf1e7` |
| Current execution boundary | P0–P3 complete and signed off (MS-A/B/C PASS 2026-07-21); P4/P5 entry-gated on T094/T095/T111 acceptance (A1) |
| Next protected boundary | P4 and P5 require recorded **T094/T095/T111** user acceptance (Amendment A1, 2026-07-21) |
| Deviations | None. Amendment A1 (2026-07-21, user-authorized): P4/P5 entry gates re-mapped from 008-G5/008-G6 to T094/T095/T111 acceptance — see roadmap §1.2 |

## Active-feature gate mapping

| Roadmap id | Active 008 checkpoint | Status at latest update |
|---|---|---|
| **008-G5** | `specs/008-catalyst-query-workbench/roadmap.md` W2 **G5 user** | Not accepted — no longer a CVR entry gate (A1) |
| **008-G6** | `specs/008-catalyst-query-workbench/roadmap.md` W3 **G6 user** | Not accepted — no longer a CVR entry gate (A1) |
| **T094** | Diverse real-path notebook validation | In progress — July 30 PR-head model/PostgreSQL matrix 12/12 PASS (run `cbc41bcd`); one-shot transport failure and same-session recovery PASS (run `68da21db`); responsive 390/320 and 200%-layout-equivalent checks PASS; **open: final merged-pin rerun plus actual keyboard-only/zoom confirmation** |
| **T095** | G2.8c acceptance pause | Open |
| **T111** | Clean-pin rerun + user acceptance | Open |

## Current architecture and candidate pins (2026-08-03)

The current implementation no longer uses Hub-owned Catalyst query profiles.
Catalyst Gateway owns the query-profile registry, prompts, writer/reviewer
composition, deterministic lint/re-lint, finalization, and query evidence.
Med-Agent Hub provides the generic `POST /v1/hub/generate` single-role model
boundary and retains a separate clinical-answer/report profile system.

| Component | Candidate revision | State |
|---|---|---|
| Catalyst | `9aa0e0f` (PR #5) | Standalone fallback pinned to merged Hub `main`; all five PR CI jobs green; no unresolved review threads |
| Med-Agent Hub | `092b5cd` (`main`; PR #15 merged) | Generic role executor and final model-inventory dependencies available on merged `main` |
| Harness | `80c2bb7` on `codex/catalyst-mvp-umbrella` (PR #37) | Reconciled with current Harness `main`; pins Catalyst `9aa0e0f`/Hub `092b5cd`; checks green/neutral, all six review threads resolved, approval required |

The authoritative July 30 PR-head run
`cbc41bcd-56f7-4074-931f-98ed42fea202` passed 12/12 scenario repetitions on
harness `e475d7a`, Catalyst `bb36126`, and Hub `198d5f6`, with every result
independently checked against PostgreSQL/gold SQL. The corresponding PR-head run
`68da21db-2178-4010-9fd4-5c73fd477261` also proved a one-shot typed Hub
transport failure leaves the human base current; same-session turn
`bbd77610-2660-4ae8-84fa-6dffe57d760e` then recovered using matching
validation/execution context. Responsive checks passed at 390 and 320 CSS px,
plus a 200%-zoom layout-equivalent viewport. Actual Tab traversal and actual
browser zoom remain unverified, so T094/T095/T111 remain open pending that
manual accessibility check and explicit user acceptance.

Focused pin/layout coverage then exposed a stale standalone fallback SHA in
Catalyst. Candidate `95515a2` changes only that fallback default from Hub
`946afa9` to current Hub `198d5f6`; the umbrella runtime supplies the sibling
Hub context. Focused coverage passes 57/57. Clean umbrella `93689d5` run
`4dd70443-ba23-4415-b0cd-d393d2352061` passed 1/1 real-model/PostgreSQL
narrowing at Catalyst `95515a2` and Hub `198d5f6`; the complete 12/12 live
matrix remains correctly attributed to parent `bb36126`.

Catalyst `be3f95c` subsequently removes only the redundant CI assertion that
duplicated the former Hub SHA. It does not change runtime behavior; the exact
MVP assembly CI command completes 38 tests with one expected local `psycopg`
skip.

The deterministic T111 preflight drift is resolved by T123: the committed suite
now uses the real Gateway writer-only and Gemma/Qwen reviewed IDs, retains a
per-turn profile switch, and represents reviewer identity as optional only for
writer-only profiles. No live result is inferred from that repair.

T124 repaired the runtime-availability boundary: Hub publishes a versioned
backend model inventory, `LocalHub` requires every exact writer/reviewer alias,
and unavailable profiles fail closed before state or model calls. Component
coverage and the isolated exact-pin live proof are green.

The final merged-pin T111 rerun is now pending on Harness `80c2bb7`, Catalyst
`9aa0e0f`, and Hub `092b5cd`. No T094/T095/T111 status is promoted from the
older runs; the definitive matrix, durable evidence receipt, actual keyboard/
200%-zoom check, and explicit user acceptance remain required.

## Baseline Snapshot (CVR-G00)

| Field | Value |
|---|---|
| Captured at | 2026-07-21 |
| Branch | `codex/catalyst-mvp-umbrella` |
| Diff-cover base branch | `origin/codex/catalyst-mvp-umbrella` (fallback `origin/main`) |
| Pytest collect | `684` tests collected under `uv run pytest -m 'not slow' --ignore=targets --collect-only -q` |
| Pytest deselected | `3` (`slow` marker) |
| Pytest skip count (collection) | `0` |

## Constitution Check (§1.1)

| Principle | Disposition | Notes |
|---|---|---|
| I Real production paths | PASS | Fixtures labelled development; release claims reserved for P5 live path |
| II Deterministic reviewed transforms | PASS | Gold checks authoritative; rubric/schema/report in reviewed files |
| III Record-level evidence | PASS | Gold/judge verdicts must link SQL, parameters, digests, evidence paths |
| IV Metadata / provenance | PASS | Notebook `events.jsonl` + judge provenance gated before publish (P2/P4) |
| V Tests define behavior | PASS | Red-first except green-before-green golden characterization tests |
| Governance / PCCP | PASS | P2 PCCP required before rubric acceptance; P5 code-qa required |

## Roadmap self-validation findings (resolved before persistence)

| Finding | Disposition |
|---|---|
| Gate id collision with 008 G0–G6 | Resolved: unique `CVR-G00`–`CVR-G18` namespace |
| P3 forward-referenced Catalyst CLI | Resolved: P3 calls `build_report()` directly |
| Gitignored archived run as CI dependency | Resolved: committed PHI-free fixtures |
| Publish/index ChartSearchAI-only paths | Resolved: family-aware `report_family` / `run_path` |
| `comparison_set` overloaded for suite id | Resolved: Catalyst uses `suite_id` / `suite_sha256` |
| Missing notebook `events.jsonl` | Resolved: P4 contract; P2 judge finalize appends later |
| Judge axes/formula underspecified | Resolved: D6 formula + schemas + three-pass median |
| Escaping semantics diverge | Resolved: `esc` + `esc_inline` |
| Code-qa missing companion-pr artifact | Resolved: five-file D13 set |
| P4/P5 vs 008 W3 ordering | Resolved: hard entry gates on 008-G5 / 008-G6 + T094/T095/T111 |

## Post-implementation self-validation (2026-07-21)

| Check | Disposition |
|---|---|
| Cross-artifact consistency | PASS — P0–P3 land on `harness/common`, `harness/report_shell`, `harness/catalyst/{reconcile,report}.py`; P4/P5 remain entry-gated |
| Internal consistency | PASS — every P0–P3 task maps to a CVR gate; no Catalyst CLI until P4; signoffs MS-A–C pending user |
| Clarity | PASS — CVR gates retain single PASS interpretation; runtime MS/008 acceptance recorded here rather than assumed |
| Fixture repair during P3 | PASS — `results.json` now includes `gold-fail-high-judge` + `multi-version-successor`; gold FAIL evidence carries `mismatch_rationale` |
| P4/P5 entry guards | PASS — `scripts/verify-catalyst-validation-roadmap-gates.sh blocked` reports BLOCKED |

## Gate Board

| Gate | Status | Evidence |
|---|---|---|
| CVR-G00 | PASS | Roadmap + status committed; README linked; baselines + constitution recorded |
| CVR-G01 | PASS | PHI-free fixtures + provenance tests green |
| CVR-G02 | PASS | shared utility + uniqueness tests green |
| CVR-G03 | PASS | `verify… g03`: 719 passed / 36 runtime skipped / 3 deselected; diff-cover 100% vs `origin/codex/catalyst-mvp-umbrella`; collection skip baseline still 0 |
| CVR-G04 | PASS | byte-identical ChartSearchAI golden with frozen clock |
| CVR-G05 | PASS | `harness/report_shell/` four modules; ownership/import tests green |
| CVR-G06 | PASS | DOM canon + golden semantic parity + dashboard/index theme marker tests green |
| CVR-G07 | PASS | G03/G05/G06 green; MS-A signed off 2026-07-21 (Piotr Mankowski) |
| CVR-G08 | PASS | PCCP + `catalyst-judge-v1` schemas + skill + reconcile/schema tests |
| CVR-G09 | PASS | finalize + gold-fail/perfect-judge precedence tests |
| CVR-G10 | PASS | Fixture three-pass + `judge.jsonl`/`judge_manifest.json` present and tests green; MS-B signed off 2026-07-21 (Piotr Mankowski) |
| CVR-G11 | PASS | Offline `harness.catalyst.report.build_report` with socket blocked |
| CVR-G12 | PASS | Import-boundary + no-judge tests green; MS-C signed off 2026-07-21 (Piotr Mankowski) |
| CVR-G13 | BLOCKED | Waiting on T094/T095/T111 acceptance (A1) |
| CVR-G14 | BLOCKED | Waiting on T094/T095/T111 acceptance (A1) |
| CVR-G15 | BLOCKED | Waiting on T094/T095/T111 acceptance (A1) |
| CVR-G16 | BLOCKED | Waiting on T094/T095/T111 acceptance (A1) |
| CVR-G17 | BLOCKED | Waiting on T094/T095/T111 acceptance (A1) |
| CVR-G18 | BLOCKED | Waiting on T094/T095/T111 acceptance (A1) |

## Signoffs

| Signoff | Status | Reviewer | Date |
|---|---|---|---|
| MS-A (Signoff A) | PASS | Piotr Mankowski | 2026-07-21 |
| MS-B (Signoff B) | PASS | Piotr Mankowski | 2026-07-21 |
| MS-C (Signoff C) | PASS | Piotr Mankowski | 2026-07-21 |
| MS-D (Signoff D) | BLOCKED | | |

## Phase completion notes

### P0 — complete
Shared `harness/common/{jsonl,text}.py`; dashboard `_match_trace` removed; committed PHI-free fixtures.

### P1 — complete; Signoff A PASS (2026-07-21)
`harness/report_shell/` extracted; ChartSearchAI `report.py` consumes shell; dashboard/index theme assets migrated; CVR-G05/G06 green. MS-A signed off → CVR-G07 PASS.

### P2 — complete; Signoff B PASS (2026-07-21)
PCCP, skill, schemas, `harness/catalyst/reconcile.py`, `scripts/catalyst-judge-finalize.py`, fixture three-pass judge artifacts. MS-B signed off → CVR-G10 PASS.

### P3 — complete; Signoff C PASS (2026-07-21)
`harness/catalyst/report.py` offline report on shell; socket-blocked tests. MS-C signed off → CVR-G12 PASS.

### P4 — not started (entry gate)
`scripts/verify-catalyst-validation-roadmap-gates.sh blocked` → CVR-G13–G15 BLOCKED until T094/T095/T111 are recorded PASS in this status artifact (Amendment A1).

### P5 — not started (entry gate)
CVR-G16–G18 BLOCKED until T094/T095/T111 are recorded PASS here (Amendment A1).
