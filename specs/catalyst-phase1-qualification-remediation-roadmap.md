# Catalyst Phase 1 comparison repair — execution plan

**Status:** Active. The owner-approved direction is recorded in R0. The Phase 1
product foundation exists; the remaining work is to make the planned experiment
and report trustworthy. This is not a production-approval or model-selection
plan.

`specs/catalyst-program-roadmap.md` is the authority for product scope, the
readable data surface, session-context direction, the three model teams, the
comparison intent, and the P1 → P2 → P3 order. This file only sequences the
remaining work. Its historical filename is retained to avoid link churn.

Implementation follows the sequence below. Reporting work must not get ahead of
the evidence, data-surface, and context behavior on which it depends.

## Goal

Exercise the complete Phase 1 behavior through real product and database paths,
collect the planned three-team result set, and publish a context-rich report
that a reader can evaluate against the rubric.

The experiment does not have to identify a winner. A preference, no clear
preference, or a deliberately chosen demo configuration are interpretations or
practical choices, not Phase 1 gates. Phase 2 is not blocked by the comparison
outcome.

## Working rules

- The comparison is exploratory validation. It does not impose production
  approval, automatic team selection, or a required result label.
- Every role-readable database relation is available to model and human tools.
  Metadata explains and warns; it does not hide readable relations.
- The advisory validator records findings but does not prevent the exact
  user-selected SQL from reaching PostgreSQL under the existing read-only
  account, read-only transaction, time limit, and result limit.
- Wrong SQL, a database diagnostic, a wrong answer, clarification, and an
  unsupported response are all observable model behavior when the supporting
  evidence is complete.
- One Phase 1 run covers the complete frozen team-and-scenario matrix once.
  Any repeated measure is another complete run, not extra calls for selected
  cells.
- Machine or service interruptions are recorded separately from model
  behavior. The roadmap defines no fixed allowance. Recovery belongs in
  harness code and tests.
- Retained conversation history is the current context baseline. The value of
  separate session guidance remains a research question, and Phase 1 requires
  no Pin interface.
- Exact revisions, test totals, pull-request state, operational history, and
  generated evidence stay in Git, tests, continuous integration, pull
  requests, and the report. This roadmap does not mirror them.
- Review is based on direct inspection of the roadmap, code, tests, and result
  evidence.
- No seed, reset, deployment, or live access change occurs unless the owner
  explicitly approves that operation.

## Why the current evidence is not enough

| Area | Verified problem | Required outcome |
| --- | --- | --- |
| Turn checks | One follow-up answer check was applied to more than its intended turn, and several ready turns lack complete independent answers. | Each scored turn has its own expected outcome and database-backed factual check. |
| Database evidence | Some records prove only that an endpoint accepted a request, not what PostgreSQL returned for the exact SQL. | The report links the displayed SQL, validator findings, PostgreSQL result or diagnostic, and independent answer check. |
| Result-set integrity | Existing composition can accept missing, accidentally duplicated, or differently configured evidence. | The result set matches the collection declared by one frozen experiment definition and is internally consistent. |
| Reporting | Legacy report code turns provisional percentages into verdict and ranking language and advertises several judge passes. | The report presents the evidence and one manual full-context rubric review by default, without automatic team verdicts. |
| Data and context | The writer can receive a narrower catalog than the human, exact context evidence may be absent, and an unexecuted query can appear as a verified example. | Model and human share the readable surface; examples are genuinely verified; supplied and omitted context is visible. |
| Real-path stability | The retained OpenELIS database location can depend on the worktree that starts the stack. | The supported stack preserves the same test fixture across clean worktrees without a hidden seed or reset. |

The development comparison already published remains useful diagnostic
evidence. Its measurement defects mean it cannot settle the repaired
experiment or establish a ranking. It remains available under its original
suite and catalog identities.

## Sequence

R0 establishes the plan. R1 establishes the collection lifecycle.
R5, R6, and R7 can proceed in parallel after R0. R2 binds the finished data and
context contracts; R3 then establishes result-set integrity; R4 produces the
reporting and manual-review path. R8 runs the experiment. R9 is optional work
chosen after reading the results. R10 closes Phase 1 once the real product path
and report are complete.

### R0 — Align the authoritative plan

**Repository:** validation harness. **State:** complete.

Align the program roadmap and this execution plan with the current direction.
Supporting research remains available but cannot silently restore discarded
requirements.

Acceptance:

- both roadmaps describe exploratory comparison and reader-led interpretation;
- neither roadmap requires thresholds, an automatic winner, a formal
  no-winner label, team-dependent deployment, or a Pin interface;
- Phase 1 completion and Phase 2 progress do not depend on a team preference;
- collection shape is defined by the frozen suite and harness rather than
  prescribed again here;
- the owner reviews and approves the final roadmap diff before reporting
  implementation resumes.

### R1 — Honest collection identity and interruption handling

**Repository:** validation harness. **State:** in review.

The collection freezes a secret-free identity before live calls, returns the
exact evidence location, preserves interrupted evidence, and treats wrong
model answers as experimental results rather than runner failures. A machine
or service interruption stops the current collection as incomplete; the
operator chooses when to resume. Historical suite v1 evidence stays unchanged,
and its legacy replacement setting has no active effect.

Acceptance:

- completed model responses remain evidence regardless of answer quality;
- collection interruptions and model behavior are represented separately;
- no fixed machine-failure allowance controls the experiment;
- an explicit recovery reuses only complete, unchanged conversations and
  produces a self-contained run without repeating those conversations;
- lifecycle and recovery behavior is proven by focused harness tests rather
  than restated as product policy.

### R2 — Turn-specific factual evidence

**Repository:** validation harness. **Depends on:** R1, R5, and R6.

Create suite v2 without changing published suite v1. Give every opening and
follow-up turn its own expected outcome, database execution evidence when SQL
is produced, and independent factual answer check.

Acceptance:

- every ready turn in A1–A4, M1–M3, and B1–B3 checks every requested field or
  row set rather than a count alone;
- M1's three answers are checked separately;
- M2's regrouping and top-ten answers are checked separately and both honor the
  earlier `do_not_perform` instruction;
- M3's visit answer matches its independent database result without irrelevant
  CD4-specific carryover;
- clarification and unsupported turns prove that no SQL execution occurred;
- validator findings, the exact SQL, PostgreSQL output or diagnostic, answer
  observations, context evidence, model calls, tokens, and timing remain
  connected to the correct turn;
- an ordinary bad model query stays in the result set when this evidence is
  present.

### R3 — Complete result-set integrity

**Repository:** validation harness. **Depends on:** R2.

Treat the frozen suite's declared team-and-scenario collection as one
reviewable evidence set. Validate its completeness and frozen configuration
before reporting it.

Acceptance:

- the result set contains every conversation declared by the frozen suite with
  no unintended omission or duplicated evidence record;
- repeated measures, when requested, are separate complete suite runs;
- every conversation has the suite, data, catalog, code, model, prompt, and
  context evidence needed to understand what ran;
- mixed or internally inconsistent evidence is reported plainly and cannot be
  presented as the completed experiment;
- infrastructure-interrupted collection is distinct from completed model
  behavior;
- replaying the stored evidence produces the same factual report content.

### R4 — Context-rich report and manual rubric review

**Repository:** validation harness. **Depends on:** R3.

Use the existing result preparation and manual finalization path. Remove the
legacy automatic pass/fail, percentage-threshold, ranking, tie, and
prescribed review-count semantics from the active report.

Acceptance:

- the reader can inspect every complete conversation, actual model context,
  output, selected SQL, validator findings, PostgreSQL result or diagnostic,
  independent factual checks, timings, calls, tokens, and relevant provenance;
- one manually initiated frontier-model review of the entire prepared result
  set against the frozen rubric is the default;
- the same complete case context and rubric is supplied for every team;
- if the owner wants another perspective, it uses a different model or agent
  and its rationale remains separate;
- the report does not average reviewers, manufacture consensus, rank a winner,
  or convert commentary into an automatic team verdict;
- no separate comparative judge receives thinner or different context;
- the report is the human-readable entry point and links to its underlying
  machine-readable evidence rather than creating several parallel decision
  artifacts.

### R5 — Shared readable data surface

**Repositories:** Catalyst, then validation harness source/catalog integration.
**Depends on:** R0.

Remove the model-only catalog restriction while preserving advisory validation.
Keep published catalog v6 under its historical identity and record the actual
catalog identity and readable surface used by the repaired experiment.

Acceptance:

- model generation and human tools can use every relation readable by the
  configured read-only role;
- metadata guides use but cannot hide a readable relation;
- a catalog refresh does not stop ordinary startup merely because role access
  changed;
- the exact selected SQL reaches the bounded read-only PostgreSQL path;
- local and demo catalogs are recorded separately and need not be identical;
- the experiment records the catalog it actually used.

### R6 — Honest context evidence and guidance research seam

**Repositories:** Med-Agent Hub, Catalyst, then validation harness integration.
**Depends on:** R0.

Make actual session context observable without deciding in advance that a
separate guidance control is useful.

Acceptance:

- evidence shows the current instruction, retained history, failure
  information, verified examples, and any explicit guidance actually supplied
  to every model call;
- omissions are visible with their reason; context is not silently summarized,
  truncated, or substituted;
- verified examples come only from earlier kept queries with recorded advisory
  validation and successful database execution against the same source;
- validator findings stay with those examples but do not veto their use;
- existing application-programming-interface guidance may remain available for
  experiments, but no composer or Pin control is required;
- separate nearby research cases compare retained history, explicit guidance,
  and durable catalog or example knowledge before a user-facing design is
  proposed;
- general reusable rules are evaluated as durable metadata or examples rather
  than assumed to belong in a session pin.

### R7 — Real database path and stable retained fixture

**Repositories:** validation harness, Catalyst, and Med-Agent Hub as needed.
**Depends on:** R5 and R6 for final proof.

Prove the experiment through real PostgreSQL and make the supported retained
test database independent of the worktree that launches Catalyst.

Acceptance:

- the exact code intended for R8 passes real catalog refresh, semantic-answer,
  advisory-validation, and bounded read-only execution checks;
- starting the same stack from another clean worktree preserves the same
  fixture and does not combine incompatible retained services;
- a supported no-reset, no-seed restart passes health checks;
- the stable fixture can be used throughout the experiment without routine
  recreation;
- local and demonstration environments record their own observed state rather
  than being forced to match.

### R8 — Run and publish the Phase 1 experiment

**Environment:** owner's local GPU through the supported isolated stack.
**Depends on:** R1–R7 complete on the exact code used for collection.

Freeze the current suite v2, rubric, model setups, data, observed catalog
identity, and environment. Exercise all three teams across the full scenario
set and publish the complete evidence and R4 review.

Acceptance:

- every suite-declared conversation is present and retains its internal session
  context;
- every result is traceable to the frozen experiment definition and passes R2
  and R3 evidence checks;
- wrong model answers remain visible findings;
- machine or service interruptions remain separate and an unfinished
  collection is reported as unfinished;
- the public report is secret-free, links to the underlying evidence, and
  shows the manual rubric rationale;
- the reader can evaluate the result set without an automatic winner or formal
  outcome label;
- completing and publishing this experiment satisfies the comparison part of
  Phase 1 regardless of the reader's preference.

### R9 — Optional evidence-led next-goal planning

**Depends on:** R8 report available.

After reading the report, the owner may choose a product repair, a focused
research experiment, a model change, or no immediate follow-up. This item is
optional and does not automatically loop the comparison or block Phase 1
closeout.

If work is chosen, it should address a general behavior and use nearby cases
that were not copied from the frozen comparison questions. The change receives
a direct code-and-test review. The old result remains intact; any later
experiment is reported under its own definition.

### R10 — Confirm the real product path and close Phase 1

**Depends on:** R8 report and a working real Catalyst path. A team preference
is not required.

Use an explicitly recorded demonstration configuration to verify the browser
journeys named in the program roadmap. The demonstration proves that the
session-context product path works; it does not prove that its model setup won
or is approved for production.

Acceptance is intentionally small:

- the real browser path visibly exercises ready, clarification, retained
  earlier instruction, and unsupported behavior against the real database;
- the comparison report is published and linked from the current roadmap;
- observed limitations are stated plainly;
- the owner confirms that the Phase 1 completion rule is met.

## Verification approach

Each code change runs the focused tests for the behavior it changes plus the
repository's current required checks. Real PostgreSQL proof is required before
R8. The supported `scripts/catalyst-mvp.sh` wrapper is used for stack lifecycle,
and seed or reset remains an explicit owner-approved operation. Browser
acceptance compares the live behavior with the expected database answer and
visible product state.

The repository's current scripts, continuous-integration configuration, and
tests are the canonical commands and assertions; this roadmap does not copy
their operational details.
