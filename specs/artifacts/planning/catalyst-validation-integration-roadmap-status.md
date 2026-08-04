# Catalyst Validation Integration Roadmap Status

Execution state for the Catalyst validation integration remediation roadmap.

## Control Record

| Field | Value |
|---|---|
| Roadmap | [`catalyst-validation-integration-roadmap.md`](catalyst-validation-integration-roadmap.md) |
| Authorization | Explicit user instruction to implement the approved plan on 2026-07-21; A2 gate-order clarification and exact synthetic release publication authorized 2026-08-04 |
| Approved roadmap SHA-256 (pre-A1) | `b00a063bf2b78494a3a719436d4609127eb2e845153d1ab2f9153d1e018e6ef8` |
| Approved roadmap SHA-256 (A1) | `37c13c468d274b985a0f48e0e6e5cfb2e3e9eaf3b0fb0fd1ace6e73fca1cf1e7` |
| Approved roadmap SHA-256 (A2, current) | `d11d34f466f727e70a50eccc7024c85b334ad8c899ddb6a94ef0d26a09814dab` |
| Current execution boundary | P0–P4 and T135 complete; CVR-G13–G17 PASS; T136/CVR-G18 release hygiene is in progress |
| Next protected boundary | Finish CVR-G18 release hygiene, then pause for final MS-D acceptance |
| Deviations | None. Amendment A1 (2026-07-21) remaps P4/P5 entry gates to T094/T095/T111 acceptance; Amendment A2 (2026-08-04) orders CVR-G18 hygiene before final MS-D acceptance — see roadmap §1.2 |

## Active-feature gate mapping

| Roadmap id | Active 008 checkpoint | Status at latest update |
|---|---|---|
| **008-G5** | `specs/008-catalyst-query-workbench/roadmap.md` W2 **G5 user** | Not accepted — no longer a CVR entry gate (A1) |
| **008-G6** | `specs/008-catalyst-query-workbench/roadmap.md` W3 **G6 user** | Not accepted — no longer a CVR entry gate (A1) |
| **T094** | Diverse real-path notebook validation | PASS — accepted; final-pin matrix 12/12 PASS (run `0671dc34`), 24/24 PostgreSQL checks, 18/18 gold-result checks; final-pin failure/recovery PASS (run `fb6377c1`) |
| **T095** | G2.8c acceptance pause | PASS — accepted 2026-08-04; actual keyboard-only and 200%-browser-zoom checks PASS |
| **T111** | Clean-pin rerun + user acceptance | PASS — accepted 2026-08-04; T112 merge/repin/verification also complete |

## Current architecture and merged pins (2026-08-04)

The current implementation no longer uses Hub-owned Catalyst query profiles.
Catalyst Gateway owns the query-profile registry, prompts, writer/reviewer
composition, deterministic lint/re-lint, finalization, and query evidence.
Med-Agent Hub provides the generic `POST /v1/hub/generate` single-role model
boundary and retains a separate clinical-answer/report profile system.

| Component | Candidate revision | State |
|---|---|---|
| Catalyst | `e7eba21` (`main`; PR #5 merged) | Source head `5f23c4e` passed all five CI jobs, including the deterministic browser workflow, then squash-merged; standalone fallback remains pinned to Hub `main` |
| Med-Agent Hub | `092b5cd` (`main`; PR #15 merged) | Generic role executor and final model-inventory dependencies available on merged `main` |
| Harness | `776a363` (`main`; PR #37 merged) | Pins Catalyst `e7eba21`/Hub `092b5cd`; full health/provenance PASS and post-merge real-model/PostgreSQL/gold smoke `70d76a43` PASS 1/1 |

The authoritative July 30 PR-head run
`cbc41bcd-56f7-4074-931f-98ed42fea202` passed 12/12 scenario repetitions on
harness `e475d7a`, Catalyst `bb36126`, and Hub `198d5f6`, with every result
independently checked against PostgreSQL/gold SQL. The corresponding PR-head run
`68da21db-2178-4010-9fd4-5c73fd477261` also proved a one-shot typed Hub
transport failure leaves the human base current; same-session turn
`bbd77610-2660-4ae8-84fa-6dffe57d760e` then recovered using matching
validation/execution context. Responsive checks passed at 390 and 320 CSS px,
plus a 200%-zoom layout-equivalent viewport. On 2026-08-04 the user also
completed actual keyboard-only traversal and actual 200% browser zoom; both
passed, and the user accepted the MVP candidate. A deterministic Playwright
regression now covers uninterrupted Tab traversal and 200%-equivalent reflow.

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

The final merged-Hub-pin T111 evidence was accepted. Harness run
`0671dc34-26c6-4d52-8443-47e0a833a539` passed 12/12 real-model repetitions,
24/24 independent PostgreSQL comparisons, and 18/18 gold-result comparisons on
Catalyst `9aa0e0f` and Hub `092b5cd`. Run
`fb6377c1-0b60-492a-8053-cc668a201d15` passed the expected one-shot Hub failure;
the next turn in that same session then generated, validated, executed, and
matched PostgreSQL after the direct router was restored. The accepted PHI-safe
receipt is `specs/008-catalyst-query-workbench/evidence/`
`t111-final-acceptance-2026-08-03.json`. The user-confirmed keyboard-only and
actual 200%-zoom checks promote T094/T095/T111 to accepted. Catalyst #5 and
harness #37 subsequently squash-merged in dependency order, and T112 is complete.

## P4/P5 current state (2026-08-04)

The audit distinguishes reusable prework from passed roadmap gates:

- **Already implemented:** the real notebook runner writes `run_manifest.json`,
  `results.json`, additive `results.jsonl`/`events.jsonl`, and bounded evidence;
  the live dashboard can discover notebook runs; the three-pass Catalyst judge
  schema/finalizer and offline shared-shell Catalyst report pass fixture tests.
- **CVR-G13 PASS:** manifests carry `report_family`, `suite_id`, and the exact
  suite SHA-256; versioned run/scenario/turn/version/execution events resolve
  their evidence references; judge finalization appends idempotent
  provider/model/version/rubric evaluation events without rewriting the
  run-start manifest. Focused gate: 51 tests PASS.
- **CVR-G14 PASS:** `harness-cli catalyst run` exposes every legacy runner
  option and both PostgreSQL checkers; `harness-cli catalyst report <run_dir>`
  renders the offline report; the legacy script delegates to the shared CLI.
  Focused gate: 5 selected tests PASS.
- **CVR-G15 PASS:** `publish-report.sh` stages either family and its relative
  evidence, emits exclusive family metadata with safe root-relative
  `run_path`, skips Catalyst dashboard freezing, preserves the legacy
  ChartSearchAI wrapper, and builds one mixed index with Catalyst gold and
  advisory judge-median metrics without calling Scout. The two-fixture dry-run
  and republish test pass under a temporary `REPORTS_ROOT`; 27 tests PASS.
- **CVR-G16 PASS:** all five D13 independent code-QA reports are present,
  non-empty, anchored to reviewed implementation `380301d`, and record zero
  open BLOCKER findings. The executable G16 gate passes.
- **P5 is in progress:** clean-pin run
  `7e3adf47-c21f-4d8c-9595-fd73d3dbfb24` passed 13/13 scenario repetitions
  and 411/411 assertions. Exactly three independent judge passes cover all 25
  executed versions and finalize successfully. The report renders and its
  family-aware dry-run publication passes. Live publication/URL verification,
  release hygiene, and MS-D signoff remain.

### T135 / CVR-G17 release-run checkpoint (2026-08-04)

- Harness `9f4b26a` ran clean reviewed Catalyst `e7eba21` and Hub `092b5cd`.
  The isolated runtime reported 96 patients, 1,152 results, 9 test types, and
  pipeline run `full-20260804T203050Z`.
- All 12 automatic repetitions and the bounded one-shot Hub-failure scenario
  passed. The fault proxy injected exactly one HTTP 502 for the isolated Hub's
  first chat completion; the failed turn preserved its base, and the Hub was
  immediately restored to the direct router.
- Independent PostgreSQL cross-checks and every configured gold check passed.
  Passing gold is not treated as semantic perfection: narrowing repetition 3
  omitted the explicitly requested `result_status = 'final'` predicate while
  still matching the current data. All three advisory judge passes therefore
  score that successor 63; the other 24 executed versions finalize at 100.
- Judge identity is constant across 75 rows: provider `openai`, model
  `gpt-5.6-sol`, version `runtime-reported:gpt-5.6-sol`, rubric SHA-256
  `5dc94bbd30424f6f5f87b708a15a9f8615617d9e91180170f7c72df9c6e8f483`.
- After explicit authorization for the exact synthetic payload, the report was
  published at `https://reports.openclinai.org/catalyst-t094-release/`. The live
  index contains its Catalyst card; the public report, run/results/judge
  manifests, and representative evidence from every scenario family match the
  staged bundle byte-for-byte. All 81 relative evidence links in the live report
  returned HTTP 200 and matched their staged files.
- Dry-run staging is byte-identical to the source bundle for every manifest,
  result, event, evidence-index, and judge artifact; every rendered relative
  evidence link resolves. The staged index contains 18 cards, including the
  Catalyst release candidate and existing ChartSearchAI reports. Release-file
  SHA-256 values are: manifest `f789b5d5d73d4a9bca39816b30c412abd8b6a5034927ae4134db07bfef29b664`,
  results `4cd68dc4a2710330c7df3f2d42de9f731615f19c8a6ed09a976f94d92a803737`,
  events `779a9016dd5196b006521944e137a12a39e33ebc9fc0b2e4e16e9f3850059927`,
  finalized judge `9349787e3330641bfe7ca236334139c3cbc69c0118a27b679528b619ffe73c01`,
  and report `16d8ff16f1e3dd2955c6e0e08182384f6a8b31dc3ceca6bb891126c5a055024b`.

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
| P4/P5 vs 008 W3 ordering | Resolved: T094/T095/T111 and T112 are complete; P4 is active independently of product W2/W3 |

## Post-implementation self-validation (2026-07-21)

| Check | Disposition |
|---|---|
| Cross-artifact consistency | PASS — P0–P3 land on `harness/common`, `harness/report_shell`, `harness/catalyst/{reconcile,report}.py`; T094/T095/T111 acceptance opens P4/P5 |
| Internal consistency | PASS — every P0–P3 task maps to a CVR gate; no Catalyst CLI until P4; signoffs MS-A–C complete and MVP acceptance recorded |
| Clarity | PASS — CVR gates retain single PASS interpretation; runtime MS/008 acceptance recorded here rather than assumed |
| Fixture repair during P3 | PASS — `results.json` now includes `gold-fail-high-judge` + `multi-version-successor`; gold FAIL evidence carries `mismatch_rationale` |
| P4/P5 entry guards | PASS at implementation time; Amendment A1's acceptance condition is now satisfied and the gate-state script must be advanced before P4 work |

## Resolved roadmap consistency decision (2026-08-04)

The user approved Amendment A2: CVR-G18 proves CI/pins/docs/PCCP and repository
hygiene, then MS-D is the final release-acceptance decision. The roadmap no
longer requires CVR-G18 and MS-D to have passed before one another.

## Gate Board

| Gate | Status | Evidence |
|---|---|---|
| CVR-G00 | PASS | Roadmap + status committed; README linked; baselines + constitution recorded |
| CVR-G01 | PASS | PHI-free fixtures + provenance tests green |
| CVR-G02 | PASS | shared utility + uniqueness tests green |
| CVR-G03 | PASS | `verify… test`: 1088 passed / 38 runtime skipped / 4 deselected; diff-cover 92% vs `origin/codex/catalyst-mvp-umbrella` |
| CVR-G04 | PASS | byte-identical ChartSearchAI golden with frozen clock |
| CVR-G05 | PASS | `harness/report_shell/` four modules; ownership/import tests green |
| CVR-G06 | PASS | DOM canon + golden semantic parity + dashboard/index theme marker tests green |
| CVR-G07 | PASS | G03/G05/G06 green; MS-A signed off 2026-07-21 (Piotr Mankowski) |
| CVR-G08 | PASS | PCCP + `catalyst-judge-v1` schemas + skill + reconcile/schema tests |
| CVR-G09 | PASS | finalize + gold-fail/perfect-judge precedence tests |
| CVR-G10 | PASS | Fixture three-pass + `judge.jsonl`/`judge_manifest.json` present and tests green; MS-B signed off 2026-07-21 (Piotr Mankowski) |
| CVR-G11 | PASS | Offline `harness.catalyst.report.build_report` with socket blocked |
| CVR-G12 | PASS | Import-boundary + no-judge tests green; MS-C signed off 2026-07-21 (Piotr Mankowski) |
| CVR-G13 | PASS | 51-test metadata/event/finalizer/runner gate; T129–T130 complete |
| CVR-G14 | PASS | 5 selected CLI and compatibility-wrapper tests; T131 complete |
| CVR-G15 | PASS | 27-test mixed-family index/publisher dry-run gate; T132–T133 complete |
| CVR-G16 | PASS | Five independent D13 reports; zero open BLOCKER findings; `verify… g16` PASS against reviewed implementation `380301d` |
| CVR-G17 | PASS | Run `7e3adf47` is 13/13 with 411/411 assertions; 3 × 25 judge rows finalized; live report/index published; 81/81 relative evidence links HTTP 200 and byte-identical to staging |
| CVR-G18 | IN PROGRESS | Final CI/pin/docs/PCCP/repository hygiene must establish readiness for MS-D |

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

### P4 — complete
T128–T133 are complete. CVR-G13–G15 and the continuous suite are green on the
stacked feature branch; the implementation remains development evidence until
the P5 live release and MS-D acceptance.

### P5 — in progress
T094/T095/T111, the merge chain, P4 parity gates, T134/CVR-G16, and
T135/CVR-G17 are complete. The live report and all 81 relative evidence links
are verified against the staged bundle. T136/CVR-G18 release hygiene is in
progress; MS-D remains the final user-acceptance boundary.
