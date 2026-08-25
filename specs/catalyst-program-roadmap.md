# Catalyst program roadmap — authoritative plan

**Status:** Phase 1 product work is substantially implemented. The first
development comparison selected no team, so Phase 1 is not yet qualified or
deployed. The active repairs and clean pull-request sequence are tracked in
`specs/catalyst-phase1-qualification-remediation-roadmap.md`.

This file is the single source of truth for Catalyst product scope, current
decisions, comparison method, and program order. The qualification
remediation roadmap governs execution of those decisions. The planning brief
and *What the Writer Sees* preserve evidence and rejected alternatives; they do
not override either active roadmap.

## Current verified starting point

- Harness R1 is merged at
  `4a6cc59dc2be5187df5d44ee40efdb5b9858db59`.
- Catalyst is pinned at `50f15b10c7a63eef6ede338060edfc29f246e004`.
- Med-Agent Hub is pinned at
  `e26c52af7cabc1aaac5f521f871ac42c9ae2539e`.
- Pull requests #51, #52, #54, #55, #57, and #50 are merged. #49 was closed
  after its useful work was salvaged. The closeout recorded 1,142 passing
  tests, clean repository-line verification, clean submodule initialization,
  and green checks on the final head.
- The medication-code repair is live locally and on the demo host.
- Issue #58 is closed. Locally and on the demo host, all 143 rows in
  `analytics.hiv_concept_mapping_v1` have an OpenMRS-native code, the mapping
  equals an independent raw-table calculation in both directions, and the
  native concept and coded-answer displays have zero differences. The public
  demo serves catalog v5 with schema `analytics-v1`: its human editor catalog
  lists 13 readable relations, while its model-writing allowlist still contains
  4 approved views. Current main contains catalog v6 and published suite v1;
  both identities are now immutable historical evidence. Qualification uses
  catalog v7 and suite v2 to remove that model-only restriction: both paths use
  every relation the configured read-only database role can read. The current
  count of 13 is an environment snapshot, not a product limit.
- Current harness, Catalyst, and Hub automated checks are green. The supported
  isolated-stack health and provenance gate previously passed on the freshly
  seeded 96-patient, 1,152-result fixture; no reseed is authorized by this
  planning update.
- Feature 008 remediation WS1–WS7 is closed.
- The published 36-conversation development pass selected no team and was
  correctly not deployed. Its evidence predates the current harness and
  Catalyst revisions and does not satisfy the whole-suite comparison method.

## Program order

| Phase | Product outcome | Completion rule |
| --- | --- | --- |
| **P1 — Session context** | The writer receives the same readable data surface as the human editor, itemized session guidance, relevant failure information, verified examples, and retained instruction history. | Deterministic checks and the local three-team comparison complete; the owner records a selected team, `none`, or `inconclusive`; deployed browser checks follow only a selection. |
| **P2 — Conversation mode** | A turn may answer, ask, or explain without producing SQL, using the same session state created in P1. | Scope and acceptance are set at the P2 start; P1 does not invent the complete conversation product. |
| **P3 — Dashboard workflow** | Question → queries → datasets → widgets → dashboard → Superset. | The existing Feature 008 D1e/M4 contract and browser-visible acceptance remain binding. |

WS1–WS7 remediation is closed; Feature 008 D1e/M4 remains in progress and is scheduled as P3.
P3 retains exactly these 15 active gates: T166, T147, T168, T169, T170,
T171, T148, T172, T173, T180, T181, T182, T155, T156, and T157. P1 and P2
may prepare better queries and session state; neither may reduce or close a P3
gate.

## Phase 1 product and evaluation decisions

### Decision summary

| Area | Current rule |
| --- | --- |
| Data surface | Model and human tools can use every relation the configured read-only database role can read. Relation counts are environment snapshots, and metadata cannot hide a readable relation. |
| Startup and catalog changes | A database-access change refreshes the catalog; it does not by itself stop ordinary startup. If the catalog changes during a comparison batch, record the new identity and start a new batch. |
| Manual execution | Validation is advisory and the application adds no blanket query bans. The exact selected SQL reaches PostgreSQL, bounded by the configured read-only account, read-only transaction, timeout, and result limit. PostgreSQL returns the result or diagnostic. |
| Measurement validity | A wrong query, database diagnostic, or wrong answer is a model-quality result when the measurement evidence is complete. |
| Environments | Local and demonstration catalog identities are recorded separately and do not have to match. |
| Repetition | Repeated measurement reruns the complete frozen suite. The planned run count and decision method are recorded before live work and do not change after results are visible. |
| Selection | The specification sets no universal pass percentage, automatic disqualifier, or fixed tie-break. The owner-reviewed decision may select a team, select `none`, or record `inconclusive`. |
| Infrastructure failures | Infrastructure failures are reported separately. The specification sets no fixed retry or failure allowance. |
| Context | Supply useful context that fits the configured model and record inclusions and omissions. The specification sets no fixed count, physical order, or ranking formula. |
| Independent visit check | The visit answer must answer the independent visit question without irrelevant carryover; it is not rejected merely for sharing a relation or SQL form with an earlier query. |
| Real database proof | Real PostgreSQL proof is required before the live comparison, not on every ordinary pull request. |
| Repository administration | Branch settings, image publishing, and similar repository work are not Phase 1 product blockers. |

### 1. One shared readable data surface

Generation, manual editing, completion suggestions, validation, and execution
use every relation the configured read-only database role can read. The 13
relations in catalog v6 record one historical fixture; they are not an
allowlist or a product limit. A catalog refresh adds or removes relations as
the role's access changes without altering the database schema.

Reviewed metadata improves descriptions and warnings for known relations but
does not decide whether a readable relation is available. Catalog v6 remains
unchanged as historical evidence; catalog v7 records this corrected behavior.

Manual validation remains advisory. A person may run the exact SQL and receive
the database's result or diagnostic. The read-only database user, read-only
transaction, time limit, and returned-row limit are the execution boundary.
Result rows never enter model context.

For reproducible comparison, each qualification batch records the runtime
catalog it actually used. If that catalog changes during a batch, start a new
batch rather than hiding the new relation or failing ordinary Catalyst startup.

The patient-name scenario must be answerable from the role-readable data. Phase
1 does not require a particular view or schema change to provide it.

### 2. Honest terminal outcomes

The writer may return exactly three outcomes:

- `ready`: contains a query candidate.
- `needs_clarification`: contains one question and no SQL.
- `unsupported`: explains that the available data cannot answer the request
  and contains no SQL.

`rejected` remains owned by the Gateway for contract or orchestration failure;
it is not a fourth writer choice. Clarification and unsupported turns do not
execute SQL, preserve the prior selected query, and retain what the writer
returned.

### 3. Useful session context with honest evidence

The writer can receive the current instruction, relevant earlier instructions,
person-pinned guidance, relevant failure information, and verified examples
from the same session. A person can pin free-text guidance from the composer or
explicitly accept a useful finding from a failed turn. Its source and later
removal or replacement remain recorded. Successful queries are examples, not
guidance.

This roadmap does not prescribe fixed context caps, physical request ordering,
or a ranking formula. The implementation may select what fits the configured
model, but it must record what the model actually received and identify every
omission with its reason. It must not silently summarize, truncate, or
substitute context. Earlier session material cannot silently replace the
current instruction.

Verified examples come only from earlier kept queries in the same session that
were validated and executed successfully against the same source. The current
target can never receive its own answer as an example.

Missing or inconsistent context evidence makes that run unusable for the model
comparison. It does not take unrelated demo features offline.

### 4. Final-system comparison, not individual-effect claims

All Phase 1 changes are completed before the live comparison. There is no
published old-system baseline and no run that removes one change at a time.
The report may say whether the finished system qualifies and compare complete
model setups. It must not claim which individual context practice caused a
change.

The large comparison runs locally on the owner's GPU. The deployed server gets
only the three browser journeys described below. Local and server results are
not pooled or presented as equivalent performance measurements.

### 5. Three model teams

| Team | Profile | Writer | Checker |
| --- | --- | --- | --- |
| Writer only | `catalyst-query-gemma-4-12b` | `gemma-4-12b-q4` | none |
| Same-family check | `catalyst-query-gemma-4-12b-q4-checked` | `gemma-4-12b-q4` | `gemma-4-12b-q4` |
| Cross-family check | `catalyst-query-gemma-4-12b-qwen2.5-14b-checked` | `gemma-4-12b` | `qwen2.5-14b` |

The exact resolved aliases and profile digests are frozen before the run; no
substitution or switching is allowed. The third team changes both the checker
family and the Gemma build, so it is a product-setup comparison, not proof of
the checker's isolated effect.

### 6. Frozen scenario set and repetitions

Qualification suite v2 contains 12 scenarios and 21 scored user turns per full
run. Published suite v1 remains readable and byte-identical but cannot enter
the repaired qualification batch:

| ID | Turns and expected behavior |
| --- | --- |
| A1 | One ready query: CD4 count results since 2026-02-01 with patient, value, unit, and observed date. |
| A2 | One ready query: count HIV visits by encounter type since 2025-01-01, highest count first. |
| A3 | One ready query: count medication requests for female patients by medication name, excluding `do_not_perform`, highest count first. |
| A4 | One ready query: list each OpenMRS-native concept with no CIEL mapping, its name, and total observation count, highest count first. |
| M1 | The exact recorded `c973eeba…` three-turn medication → refinement → patient-name sequence, with its recorded instruction and request digests. All three ready answers are scored, including the historically flawed opening answer. Only harmless ordering and surrounding spacing inside the unique comma-separated medication list are normalized. |
| M2 | Count medication requests by name; pin “exclude `do_not_perform`”; regroup by gender; then return the ten highest medication-and-gender groups. Both later turns must preserve the pin without repetition. |
| M3 | Verified CD4-count query; near-neighbor CD4-percentage query; unrelated visit-count query. The near neighbor may use the example. The visit answer must match its independent database answer and must not carry irrelevant CD4-specific assumptions into the new question. |
| B1 | “Show recent HIV results” must ask what date window and which result types; the frozen answer requests the last 90 days and CD4 count, CD4 percentage, and viral load, then the next turn must be ready and correct. |
| B2 | “Show patients with poor adherence” must ask for the definition; the frozen answer defines it as the latest antiretroviral-adherence result other than “All,” then the next turn must be ready and correct. |
| B3 | “Show patients overdue for follow-up” must ask for the date and overdue rule; the frozen answer uses 2026-03-01 and a recorded return date with no later visit, then the next turn must be ready and correct. |
| U1 | “Show each patient's home address” must return unsupported. |
| U2 | “Show the prescribing clinician's name for every medication request” must return unsupported. |

Every ready result is compared with an independent PostgreSQL answer, not SQL
text alone. Each scenario freezes the source, catalog, dataset, profile,
prompt, model, and repository digests plus its expected outcome and answer
check.

Validation is advisory. For a `ready` answer, the comparison records the
validator's findings and submits the exact query through the bounded read-only
database path. It records either the result or the database diagnostic. A bad
query fails the answer check but remains a valid measurement when its evidence
is complete.

Before every complete suite run, run one fresh-session, recorded, unscored
warm-up per profile and exclude it from qualification. The complete suite run
then measures every profile/scenario pair exactly once: 36 conversations total,
with `repetitions: 1` in the suite. Repeated measurement means rerunning that
whole frozen suite, never repeating selected cells. Before a live batch starts,
record how many complete runs it will contain and the decision method that will
be applied. Do not change either after seeing the results. If the planned batch
does not support a clear decision, report it as inconclusive.

Each scenario starts in a fresh session and retains its turns. Every team
receives the same frozen suite and configuration. Infrastructure failures are
reported separately from model results. An interrupted run remains immutable
and incomplete. Recovery creates a new run with a `resumedFrom` reference and
may reuse complete measurements only when their recorded configuration and
evidence still match. It never chooses work for reuse based on whether the
answer passed. An infrastructure retry replaces a missing measurement; it is
not an additional model measurement or another repetition. It only finishes
one interrupted constituent run. Only a complete replacement with exactly one
measurement for every team/scenario pair may enter the combined result.

## Phase 1 comparison and model selection

The roadmap does not impose universal percentage gates, automatic
disqualifiers, or a fixed tie-break chain. Before the first live call in a
batch, record the owner-reviewed decision method alongside its frozen suite and
planned run count. The method cannot change after results are visible.

The comparison reports answer correctness against the database, terminal
outcome correctness, clarification behavior, retained-guidance behavior,
verified-example behavior, model and infrastructure failures, model calls,
tokens, and elapsed time for every team and scenario. Validator findings and
database diagnostics remain visible. A wrong model answer is a scored result,
not missing evidence. A measurement is unusable only when the evidence needed
to understand what ran is absent or inconsistent.

The owner-reviewed decision may select one team, select `none`, or record an
inconclusive result. It must state the reasons and cannot silently substitute a
different model setup.

A `none` selection is a complete qualification outcome, not permission to tune
against failed frozen questions. Preserve that batch unchanged and do not
deploy. Any next attempt may address only a general product behavior, must use
nearby tests outside the frozen suite, and starts from a completely new frozen
batch. Pre-fix and post-fix runs are never pooled.

The final report includes all teams, scheduled/completed/model-failed/
infrastructure-failed counts, per-scenario results, variability across complete
runs, outcomes, attempts, tokens, timing, and the recorded decision. Replaying
the stored evidence produces the same report. A model judge may be shown as
advice but never replaces the database checks or owner review.

## Delivery gates

### G0 — authoritative planning record

Preserve the research evidence submitted in unmerged PR #59, replace its stale
recommendations with the decisions in this file, and close #59 as superseded.
The program roadmap, brief, artifact, Feature 008 status sources, and
documentation consistency check must agree. The old pull-request cleanup
roadmap becomes a closed historical record. Every actionable review thread is
fixed, answered, and resolved; checks pass on the final reviewed head.

### G1 — repair issue #58 — complete

Ship the source correction separately from Phase 1 behavior:

- treat both SQL null and empty string as the OpenMRS-native coding-system arm
  in every relevant observation/concept predicate;
- test production empty-string and compatibility-null records and assert the
  exact native code and display;
- advance only the catalog identity from v4 to v5, retaining schema
  `analytics-v1`, concept view version 1, and exactly four approved views;
- regenerate the catalog twice with identical bytes and execute the real
  PostgreSQL semantic tests;
- locally prove 143 rows, 143 nonblank native codes, and zero difference in
  either direction from an independent raw-table calculation;
- apply and verify the same correction on the demo host without reseeding.

G1 blocks the final comparison, not parallel development of the runner or
context features.

**Completion evidence:** harness PR #61 merged the correction; the catalog was
generated twice with identical bytes; the real PostgreSQL semantic suite
passed 13 tests; both local and demo databases returned `143|143|0|0|0` for
mapping rows, nonblank native codes, the two set differences, and display
differences; and the demo Gateway reports catalog v5. Neither environment was
reingested or reseeded to apply this HIV source correction. A separate
supported synthetic OpenELIS seed was run afterward to restore the local MVP
validation baseline recorded above.

### G2 — runner and frozen evidence

Extend `harness/catalyst/notebook_validation.py`; do not create a second runner.
Support arbitrary ordered turns; the writer outcomes `ready`,
`needs_clarification`, and `unsupported`; the separate Gateway-owned
`rejected` state; one measurement per cell in a complete suite run;
turn-scoped independent database checks; exact token evidence; separate
infrastructure counts; comparable whole-run composition; and byte-stable
evidence replay. Recovery uses a new `resumedFrom` run and preserves the
interrupted run unchanged. Profile or digest drift fails before a live run.
Preserve suite v1 bytes and put corrected qualification semantics in suite v2.
Suite v2 and the runner reject extended, per-scenario, and command-line
repetition overrides in comparison mode.

### G3 — data and outcome contracts

Before changing the current unversioned catalog files, copy their exact v6
bytes to new versioned v6 paths and retarget the immutable digest guard to those
archives. Produce catalog v7 in the active paths with one shared
runtime-readable surface, patient names, advisory manual validation, and the
three writer outcomes. Catalog metadata may guide use but may not hide readable
relations. Preserve older request/turn readers.

### G4 — layered context

Add versioned guidance storage and pin controls, then deliver relevant guidance,
failure information, verified examples, and retained instructions with honest
omission evidence and session isolation. Hub advertises support before Catalyst
sends the new request shape.

### G5 — deterministic and local qualification

All component, contract, catalog, semantic PostgreSQL, browser, and evidence
checks pass on exact remote-reachable commits. Freeze the combined stack, record
the planned number of complete runs and decision method, run the whole-suite
batch, and publish one consolidated report. There are no published per-change
comparisons.

### G6 — deployed browser proof and closeout

Deploy the selected team and run three real browser journeys:

1. patient-name request → ready → validate → execute → database-matching table;
2. “recent HIV results” → clarification → frozen answer → ready, then refresh
   restores the complete timeline and selected version;
3. pin “exclude `do_not_perform`” → later regroup still honors it after reload,
   then request patient addresses → unsupported with no SQL and the previous
   selected version preserved.

These are deployment and user-flow checks, not additional model scores. Record
the exact revisions and evidence, pass current-head checks, and update this
roadmap with the selected team or an explicit `none` or `inconclusive` result.

## Explicitly outside Phase 1

- cross-session or cross-user memory;
- an automatic system that writes or rewrites guidance;
- a vector database or new retrieval service;
- result rows in model context;
- claims that the integrated comparison isolates one context practice;
- any reduction or closure of the 15 Phase 3 Dashboard Builder gates.

## Phase 1 comparison — development first pass (2026-08-25)

**No team was selected from this development pass.** The no-deploy disposition
stands. Final Phase 1 selection remains open pending a repaired whole-suite
batch. The published report applied two provisional percentage gates that are
not current Phase 1 requirements. Its single live pass gave:

| Team | Judged | Failures |
| --- | --- | --- |
| `catalyst-query-gemma-4-12b` (writer-only) | 7/12 (58%) | B1 B2 B3 M2 U2 |
| `catalyst-query-gemma-4-12b-q4-checked` | 7/12 (58%) | B1 B3 M2 M3 U2 |
| `catalyst-query-gemma-4-12b-qwen2.5-14b-checked` | **8/12 (67%)** | B1 B3 M2 U2 |

Evidence package (report, decision document, frozen dashboard, run seed,
full run copy): <https://reports.openclinai.org/catalyst-phase1-comparison/>.
Run `9ae123db-8f40-4246-8769-d427a5551769`; its published manifest labels the
evidence `development` and records harness `a0c0b5c`, Catalyst `aa90485`, and
Med-Agent Hub `e26c52a`. The run contained 36/36 conformed conversations and
the scorer replayed byte-identically. Later audit found that M2's final
top-ten answer check was also applied to its earlier unlimited regrouping turn,
that M1/M3 lacked complete independent answer checks, and that only two of the
locked qualification gates were applied. The detailed failure attribution is
therefore diagnostic, not release evidence. The conservative no-selection
decision remains appropriate because the evidence itself is not release-valid.

The run used published suite v1 and catalog v6. Those identities remain
readable and byte-identical; corrected evidence uses suite v2 and catalog v7
and is never pooled with this pass.

- **G6 disposition:** with no selected team there is no deployment and the
  three browser journeys were not exercised; the spec is ready in the
  catalyst repo (DIGI-UW/openelis-catalyst,
  `catalyst-ui/e2e/phase1-journeys.spec.ts`) for the selected team.
- **Finding corrected:** an earlier run (`58b74775`) suggested reviewer arms
  scored below writer-only. That ordering was a measurement artifact — a
  gateway response-echo contract bug destroyed the qwen-reviewed team's
  cross-family B2/B3 evidence. On valid measurements the qwen-reviewed team
  is the strongest arm. The prior conclusion is retracted.
- **The old shared-failure list is a remediation hypothesis, not a tuning
  target:** B1, B3, and U2 remain useful diagnostic findings. M2 must be
  remeasured after its turn-scoped check is repaired. No model or prompt is
  tuned against these labels before qualification evidence is trustworthy.
- **Measurement amendments now in force:** one suite pass = one live
  conversation per (team, scenario); repetition means composing predeclared
  whole-suite reruns via `score_runs`, never selected per-turn or per-cell
  retries. Cell state on every surface separates evidence completeness from
  answer quality. Every run is seeded from
  `datasets/validation/catalyst/run-config.template.json`, and the frozen,
  secret-free seed ships inside the evidence package.
