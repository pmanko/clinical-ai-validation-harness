# Catalyst program roadmap — authoritative plan

**Status:** Phase 1 product work is substantially implemented. The first
development comparison selected no team, so Phase 1 is not yet qualified or
deployed. The active repairs and clean pull-request sequence are tracked in
`specs/catalyst-phase1-qualification-remediation-roadmap.md`.

This file is the single source of truth for Catalyst product scope, locked
decisions, acceptance thresholds, and program order. The qualification
remediation roadmap governs execution of those decisions. The planning brief
and *What the Writer Sees* preserve evidence and rejected alternatives; they do
not override either active roadmap.

## Current verified starting point

- The Phase 1 qualification-remediation baseline is harness commit
  `bf9b38029059ed5bd6126587e9677eee4336e368`.
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
  catalog v7 and suite v2 to make both surfaces the same exact 13-relation list
  defined below.
- Current harness, Catalyst, and Hub automated checks are green. The supported
  isolated-stack health and provenance gate previously passed on the freshly
  seeded 96-patient, 1,152-result fixture; no reseed is authorized by this
  planning update.
- Feature 008 remediation WS1–WS7 is closed.
- The published 36-conversation development pass selected no team and was
  correctly not deployed. Its evidence predates the current harness and
  Catalyst revisions and does not satisfy the repeated qualification method.

## Program order

| Phase | Product outcome | Completion rule |
| --- | --- | --- |
| **P1 — Session context** | The writer receives one governed data surface, itemized session guidance, the relevant prior failure, verified examples, and the retained instruction history. | The finished system passes deterministic checks, the local three-team comparison, and deployed browser checks below. |
| **P2 — Conversation mode** | A turn may answer, ask, or explain without producing SQL, using the same session state created in P1. | Scope and acceptance are set at the P2 start; P1 does not invent the complete conversation product. |
| **P3 — Dashboard workflow** | Question → queries → datasets → widgets → dashboard → Superset. | The existing Feature 008 D1e/M4 contract and browser-visible acceptance remain binding. |

WS1–WS7 remediation is closed; Feature 008 D1e/M4 remains in progress and is scheduled as P3.
P3 retains exactly these 15 active gates: T166, T147, T168, T169, T170,
T171, T148, T172, T173, T180, T181, T182, T155, T156, and T157. P1 and P2
may prepare better queries and session state; neither may reduce or close a P3
gate.

## Phase 1 locked decisions

### 1. One reviewed data surface

Generation, manual editing, completion suggestions, validation, and execution
use the same reviewed `role-readable-v1` relation list. The list contains these
13 relations:

**Preferred clinical relations**

- `analytics.hiv_observation_fact_v1`
- `analytics.hiv_medication_request_fact_v1`
- `analytics.hiv_visit_fact_v1`
- `analytics.hiv_concept_mapping_v1`
- `analytics.hiv_patient_dim_v1`

**Raw fallback relations**

- `public.patient_flat`
- `public.encounter_flat`
- `public.observation_flat`
- `public.medication_request_flat`
- `public.condition_flat`
- `public.medication_flat`

**Operating records**

- `analytics.pipeline_run_v1`
- `analytics.pipeline_freshness_v1`

Database permissions do not silently expand this list. Adding or removing a
relation requires a reviewed catalog version. Catalog v6 has already produced
evidence and remains byte-for-byte unchanged. Catalog v7 must equal the
explicit grants and the list above; startup fails on missing metadata or drift.
In catalog v7, the existing published `approvedViews` field is the authoritative
allowlist and contains exactly the 13 relations above; Phase 1 does not add a
second published allowlist field. New internal code calls the same concept
`queryable_relation_names` even though the compatibility field retains its old
name.

All relations receive reviewed descriptions for row meaning, join keys,
one-to-many risks, preferred alternatives, dates, exclusions, terminology,
units, nullability, sensitivity, and version. Both model-written and
human-written SQL receive non-blocking warnings when they use a raw relation,
an operating relation, a risky many-row join, or a raw relation that has a
preferred clinical alternative.

Unknown relations or columns, writes, cartesian joins, table functions, and
volatile or side-effecting functions are rejected. Queries run in a read-only
transaction with existing row and time limits. Result rows never enter model
context.

The patient dimension keeps one row per patient and adds family and given name
components. A component is emitted only when that patient has exactly one
distinct nonblank source value; independent maximums must never fabricate a
name pair. Raw `patient_flat` remains available when the curated dimension
cannot answer an expert query.

### 2. Honest terminal outcomes

The writer may return exactly three outcomes:

- `ready`: contains a query candidate.
- `needs_clarification`: contains one question and no SQL.
- `unsupported`: explains that the available data cannot answer the request
  and contains no SQL.

`rejected` remains owned by the Gateway for policy, contract, reviewer, or
orchestration failure; it is not a fourth writer choice. Clarification and
unsupported turns use one writer call, do not invoke lint, repair, review, or
SQL execution, preserve the prior selected query, and store the exact returned
text and evidence.

### 3. Layered context plus the retained transcript

The current instruction is not replaced by a summary. Every request retains
the initial instruction and the five most recent earlier follow-ups, then adds
three bounded layers:

- at most 20 active session-guidance entries;
- one relevant prior failure from the current revision line;
- at most three verified successful examples from the same session and data
  source.

Guidance is free text with the model-facing shape
`{text, source, originTurnId, createdAt}`. Storage also keeps a stable entry ID,
session ID, server-assigned order, text digest, contract version, accepting
actor, and append-only lifecycle events. Text is delivered verbatim. It is
never summarized, rewritten, or silently normalized.

A person may pin text from the composer or explicitly accept an eligible
finding from a failed turn. A composer pin becomes active on the next turn.
Successful queries are verified examples, not guidance. Removing or replacing
guidance appends an unpin or supersede event; historical turn evidence never
changes. On the twenty-first active entry, the oldest active entry leaves the
delivered set and the omission is recorded; its stored history remains.

The stable request order is: system/output contract, catalog, read-only policy,
guidance, verified examples, editor snapshot, retained instruction history,
relevant prior failure, current validation/execution digest, and current
instruction. Contract, catalog, and policy outrank all user context. The
current instruction outranks retained guidance. Later guidance wins a direct
guidance conflict. History, failures, and examples are evidence, not commands.

Each model profile declares its context window, output reserve, and exact
tokenizer. The fully rendered messages are counted before every writer,
reviewer, or repair call. Overflow fails before model invocation. There is no
hidden truncation, character-count substitute, or summary. Evidence records
included and omitted item IDs, token counts, limits, and the reason for every
omission. The static prefix must be byte-identical for equal profile, catalog,
policy, and prompt inputs.

Verified examples must be successful kept versions with matching source and
catalog digests. Phase 1 considers only earlier turns in the current session,
ranks them by deterministic normalized word overlap with the current request,
then by newest turn and stable ID, and includes at most three. The current
target can never receive its own answer as an example.

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
| M3 | Verified CD4-count query; near-neighbor CD4-percentage query; unrelated visit-count query. The near neighbor may use the example. The visit query must match an independent database answer, have a query digest different from both earlier turns, and reuse no CD4/observation relation, predicate, or projection. |
| B1 | “Show recent HIV results” must ask what date window and which result types; the frozen answer requests the last 90 days and CD4 count, CD4 percentage, and viral load, then the next turn must be ready and correct. |
| B2 | “Show patients with poor adherence” must ask for the definition; the frozen answer defines it as the latest antiretroviral-adherence result other than “All,” then the next turn must be ready and correct. |
| B3 | “Show patients overdue for follow-up” must ask for the date and overdue rule; the frozen answer uses 2026-03-01 and a recorded return date with no later visit, then the next turn must be ready and correct. |
| U1 | “Show each patient's home address” must return unsupported. |
| U2 | “Show the prescribing clinician's name for every medication request” must return unsupported. |

Every ready result is compared with an independent PostgreSQL answer, not SQL
text alone. Each scenario freezes the source, catalog, dataset, profile,
prompt, model, and repository digests plus its expected outcome and answer
check.

Ready-query validation passes only with status `valid`, or status `warning`
when every validation finding's rule code is present in suite v2's frozen
non-blocking allowlist. Status `invalid`, an unknown status, or any unlisted
warning fails the turn before execution.

Before every complete suite run, run one fresh-session, recorded, unscored
warm-up per profile and exclude it from qualification. The complete suite run
then measures every profile/scenario pair exactly once: 36 conversations total, with
`repetitions: 1` in the suite. Repeated measurement means rerunning that whole
frozen suite. Start with three complete runs. Extend the unchanged batch to
five if any scored turn's terminal outcome or answer correctness varies across
the first three runs; if leaving out any one run changes whether a team passes
any qualification gate; or if the two leading teams differ by no more than one
complete-scenario success among their 36 measurements. Never extend or retry
an individual measured cell. Stop at five and report a remaining close result
as inconclusive.

Runs use one model call at a time, one fresh session per scenario in each
complete run, and retained turns within a multi-turn scenario. Each team
receives the same frozen scenario order. Work is grouped by team for local
model residency and that fixed order is disclosed. Infrastructure failures are
reported outside the model denominator. An interrupted run remains immutable,
incomplete, and permanently excluded from composition. Recovery creates a new
run with its own identity and a `resumedFrom` reference. After every frozen
provenance field and evidence digest matches, it imports every complete,
measurement-valid conversation regardless of the model outcome or answer
quality. It never imports or retries a cell selectively from its score. A ready
path is complete when the protocol records its validation, execution decision,
and oracle result; a clarification or unsupported path is complete when the
protocol records its outcome and proves that SQL, validation, and execution did
not run. Across a linked chain, a team may replace two infrastructure failures;
its third invalidates that team's constituent run. Only a complete replacement
with exactly one measurement-valid conversation for every cell may enter the
combined score.

## Phase 1 qualification and model selection

A model team is eligible only when it meets all of these absolute gates:

- at least 90% complete-scenario success overall and at least 80% for every
  scenario;
- at least 90% correct `ready` outcomes overall and at least 80% for every
  expected-ready turn;
- at least 80% clarification recall, 90% clarification precision, and 80%
  correct answers after the frozen clarification;
- at least 90% unsupported accuracy overall and at least 80% for each
  unsupported scenario;
- M2 retained guidance honored in at least 80% of eligible later turns;
- M3 near-neighbor correctness of at least 80% and zero copying into the
  unrelated control;
- every accepted ready query has `valid` validation or only explicitly
  allowlisted non-blocking warnings, executes, and matches its independent
  database answer;
- complete token evidence within the declared limit and Gateway overhead under
  the existing three-minute contract.

Any non-read-only or out-of-surface model SQL, fabricated identifier reaching
execution, SQL execution after clarification or unsupported, cross-session
leakage, missing required digest/evidence, unsafe literal rendering, policy
expansion, or hidden truncation is a zero-tolerance failure. A failure common
to the product blocks Phase 1; a team-specific failure disqualifies that team.

Among eligible teams, choose in this order: complete-scenario rate, worst
scenario rate, first-attempt correct-answer rate, fewer physical model calls per
correct answer, lower warm 95th-percentile end-to-end time, then lower
95th-percentile total tokens. If teams remain equal after five repetitions,
prefer operational simplicity: writer only, same-family check, then
cross-family check. If no team qualifies, select none.

A `none` selection is a complete qualification outcome, not permission to tune
against failed frozen questions. Preserve that batch unchanged and do not
deploy. Any next attempt may address only a general product behavior, must use
nearby tests outside the frozen suite, and starts from a completely new frozen
batch. Pre-fix and post-fix runs are never pooled.

The final report includes all teams, scheduled/completed/model-failed/
infrastructure-failed counts, per-scenario results, 95% Wilson intervals,
outcomes, attempts, tokens, and median/95th-percentile timing. The evidence
scorer must produce byte-identical output on two replays. A model judge may be
shown as advice but never replaces the database and rule-based checks.

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
archives. Produce catalog v7 in the active paths with the exact 13-relation
surface, complete metadata, patient names, shared
validation/execution behavior, and the three writer outcomes. Merge tolerant
Catalyst handling before the Hub can emit new outcomes. Preserve older
request/turn readers.

### G4 — layered context

Add versioned guidance storage and pin controls, then request delivery for
guidance, the relevant failure, and verified examples with the ordering,
precedence, caps, token checks, omission evidence, and session isolation above.
Hub advertises support before Catalyst sends the new request shape.

### G5 — deterministic and local qualification

All component, contract, catalog, semantic PostgreSQL, browser, safety,
evidence, and repository-line checks pass on exact remote-reachable commits.
Freeze the combined stack, run three complete local comparisons, extend the
entire frozen batch to five only under the rule above, replay the combined
scorer twice, and publish one consolidated report. There are no published
per-change comparisons.

### G6 — deployed browser proof and closeout

Deploy the selected eligible team and run three real browser journeys:

1. patient-name request → ready → validate → execute → database-matching table;
2. “recent HIV results” → clarification → frozen answer → ready, then refresh
   restores the complete timeline and selected version;
3. pin “exclude `do_not_perform`” → later regroup still honors it after reload,
   then request patient addresses → unsupported with no SQL and the previous
   selected version preserved.

These are deployment and user-flow checks, not additional model scores. Record
the exact revisions and evidence, pass current-head checks, and update this
roadmap with the selected team or an explicit “none qualified” result.

## Explicitly outside Phase 1

- cross-session or cross-user memory;
- an automatic system that writes or rewrites guidance;
- a vector database or new retrieval service;
- result rows in model context;
- claims that the integrated comparison isolates one context practice;
- any reduction or closure of the 15 Phase 3 Dashboard Builder gates.

## Phase 1 comparison — development first pass (2026-08-25)

**No team qualified in this development pass.** The no-deploy disposition
stands. Final Phase 1 qualification remains open pending the repaired repeated
batch. Against the two acceptance gates implemented by the published report
(≥90% of conversations overall, ≥80% on every scenario), the locked
12-scenario HIV suite run once as live conversations per team gave:

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
decision is unchanged because the leading team remained below the basic 90%
gate even if M2 alone were corrected.

The run used published suite v1 and catalog v6. Those identities remain
readable and byte-identical; corrected evidence uses suite v2 and catalog v7
and is never pooled with this pass.

- **G6 disposition:** with no qualifying team there is no deployment and the
  three browser journeys were not exercised; the spec is ready in the
  catalyst repo (DIGI-UW/openelis-catalyst,
  `catalyst-ui/e2e/phase1-journeys.spec.ts`) for whichever team first
  clears the gates.
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
  conversation per (team, scenario); repetition means composing whole reruns
  via `score_runs`, never per-turn or per-cell retries. The initial batch is
  three complete passes and any extension is the entire frozen suite, up to
  five complete passes. Cell state on every surface is behavioural conformance
  (allowed path vs unexpected behaviour); judged quality is a number in the
  report. Every run is seeded from
  `datasets/validation/catalyst/run-config.template.json`, and the frozen,
  secret-free seed ships inside the evidence package.
