# Code-QA audit of 2026-08-24 — durable record and cleanup backlog

**Status:** Persisted from the working artifact "Catalyst Program Audit"
(claude.ai artifact c248aed6). Audited heads: harness `64e0ff3`, catalyst
`50f15b1`; method: DIGI-UW/code-qa skills (simplicity-review,
meaningful-test-coverage, spec-code-alignment, cross-repo-companion-pr),
adversarially verified; 34 of 35 findings survived, and the one that did not
taught the lesson recorded at the end.

**Relationship to the qualification-remediation roadmap:** the audit's
qualification-blocking findings are already governed there as Q1–Q10 with the
R0–R10 execution plan (`specs/catalyst-phase1-qualification-remediation-roadmap.md`)
— they are NOT duplicated here. This file carries what that roadmap does not:
the CI false-green fix detail, the dead-code and coverage inventories, the
spec-document verdicts, and the owner scope calls, so they survive the
artifact.

## The standing headline: the fan-out guards never run in CI (false green)

Both repos' real-Postgres grain/fan-out semantics tests `SkipTest` when no
database is reachable, and no workflow provisions one (`services:` absent
everywhere). With an unreachable DSN, 15 of 17 harness tests skip and pytest
exits 0; catalyst's `unittest discover` prints "OK" while its 2 semantics
guards never appear. Six of the harness guards were mutation-tested at
authorship and have never executed in the pipeline.

**Proven fix (~6 lines per repo):** a `services: postgres` block, one
`CREATE ROLE catalyst_readonly`, and the DSN env var. Verified against a stock
`postgres:16` image: harness 17/17 in 0.43s, catalyst 2/2 in 0.47s — the
tests seed their own scratch schema and need no ingested data. Also: make an
unreachable database FAIL the default pipeline rather than skip, and fix
`test_multi_source.py`'s docstring, which advertises this net as if it were
up.

## Unslotted-filename family (three of a kind)

`_HTTP_STEP_STEMS` enumerates only turn-1 filenames, so the
infrastructure-retry gate is blind to `-t2/-t3` HTTP failures (downgraded to
low: such failures still fail loudly as conformance breaks — the published
36/36 was not contaminated). Same family: `_selected_answer_sql` re-reads
unslotted `09-refreshed-session.json` (turn 1's SQL as the "selected answer"
on multi-turn scenarios), and `report.py`'s `_extract_sql` guesses version
identity from filename substrings. All three re-derive from disk what the run
loop already holds in memory; fix by carrying the in-memory value.

## Owner scope calls — roadmap claims with nothing behind them

Each is "build it" or "strike the claim"; the audit could not tell which.

| # | Claim in "Phase 1 locked decisions" | Reality | Severity |
| --- | --- | --- | --- |
| 1 | Cartesian joins, table functions, volatile/side-effecting functions rejected | No such logic in `policy.py`/`query_lint.py`; predicate-less joins and `pg_sleep()` pass. READ ONLY + statement_timeout bound blast radius only | Scope? (overlaps Q7) |
| 2 | Pre-call token accounting | `account_for_tokens()` implemented and tested, zero call sites; live path records post-hoc Hub numbers, writer role only | Scope? (overlaps Q7) |
| 3 | Warning-severity lint on relation choice | Every lint finding is severity error; nothing inspects relation choice | Scope? |
| 4 | Startup fails on catalog drift | `with_discovered_relations()` raises only if ALL 13 relations vanish; 1–12 lost = silently shrunken catalog | Med |
| 5 | 7-layer request order | `LAYER_ORDER` enforced by nothing; only 3 of 7 layers emitted; latent contract, not live bug | Med |
| 6 | Hub capability negotiation | `LocalHub` injects `SESSION_CONTEXT_CONTRACT` via setdefault for every profile — the gate cannot fail where it was exercised | Med |

Also: G3's "produce catalog v6" — the public demo still serves catalog v5
(now folded into the v7 successor plan).

## Dead code (grep-verified unreachable/uncalled)

- **The entire classic ask→preview→accept→poll flow in the UI** — only runs
  when the injected api lacks workbench methods, which production never does.
  `QueryPreview.tsx`, `ProvenancePanel.tsx`, `ResultsTable.tsx` orphaned with
  it. Caution: the gateway-side compatibility API may be deliberate — confirm
  before touching the server half.
- **22 of 25 api methods optional only for tests**, taxing 28 real call sites
  with guards for a case that cannot occur (`usesWorkbench`/`usesNotebook`
  exist only to compute it). Fix: required methods + one `makeFullApi()`
  fixture; collapses a 9-member WorkflowState union.
- **`catalyst_workbench_findings`** — table, two immutability triggers, and
  insert loop written on every validation; no SELECT anywhere. Consumers read
  the `validation_json` blob.
- Smaller: `guidance_history()` (only test callers), pin/unpin `actor_id` (no
  actor concept exists; see catalyst #74 for the guidance surface
  disposition), `blame()`'s ledger parameter (never passed in production),
  `DatasetBrowser.onInsertColumn` (built, tested, never wired).

## Coverage gaps (inversion-tested: reverting the logic fails no test)

- **`checkOutcome` gate-status surface** — zero references in tests; delete
  the `versionId === currentVersionId` scoping and a superseded version's
  errors would display against a clean query, silently.
- **Latest-execution-wins collapse** — triplicated
  (QueryWorkspace/WorkbenchPanel/DashboardPublishPanel), every fixture
  supplies one execution; reverse the comparator, all tests pass. One fixture
  with two executions on a version covers all three copies.
- **G6 journeys** — real, selector-verified, but self-gated behind
  `PLAYWRIGHT_LIVE=true` which no CI sets; Journey 1's patient-name assertion
  (`/family/i`) is satisfied by the column header alone.
- **`_has_latest_per_patient_grain`** — confirms a ROW_NUMBER/DISTINCT ON with
  the right PARTITION BY appears in the text; never the ordering direction or
  the rank-1 filter.

## Spec inventory verdicts (as of 2026-08-24)

| Document | Verdict |
| --- | --- |
| `catalyst-program-roadmap.md` | Was Mixed (stale Status header; superseded §6 repetitions text) — header since corrected by the remediation lane; §6 residue tracked as Q8 |
| `008/roadmap.md` | Stale: frozen 2026-08-06, lists 21 gating tasks where tasks.md/program roadmap say 15; `plan.md` still routes gate evidence here — live process gap |
| `008/data-model.md` | Stale: no writer outcomes (ready/needs_clarification/unsupported) or Gateway-owned rejected state |
| `008/quickstart.md` | Stale: pre-WS4 port and profiles |
| `008/ux-audit-2026-07-18.md`, `008/ux-composer-research.md` | Stale, unbannered: describe the pre-UX-v2 surface |
| `008/spec.md`, `plan.md`, `tasks.md` | Current, mutually consistent with the 15-gate P3 framing |
| `008/research.md`, `followup-notebook-research.md` | Current, binding rationale |
| The five 008 remediation docs | Correctly bannered historical; no action |

## Priorities as proposed (P1/P2/P3 need no judgement; P4 needs the owner)

1. Make the SQL guards actually run in CI (fix above) and fail-not-skip.
2. Delete the provably dead (list above).
3. Cover the two uncovered behaviors + tighten Journey 1's assertion.
4. Owner calls: the six scope claims; banner-or-update the five stale docs;
   strike §6's superseded text.

## The meta-lesson the audit recorded about itself

Two of three headline findings were retracted on re-verification: adversarial
verification confirmed what the quoted documents *said* without asking whether
that text was still *in force*. "Adversarial verification checks claims; it
does not check framing." Reviews in this program must identify the
authoritative document first (the remediation roadmap now names itself), and
treat superseded-but-unstruck text as the hazard it is.
