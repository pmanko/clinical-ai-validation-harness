# Catalyst Phase 1 qualification-remediation roadmap

**Status:** Active execution roadmap, opened 2026-08-24. Phase 1 is built but
is not qualified or deployed. This roadmap governs the repairs needed to make
the model-team decision trustworthy and repeatable.

`specs/catalyst-program-roadmap.md` remains the authority for product scope,
the readable data surface, the context outcome, the three model teams, the
comparison method, and the P1 → P2 → P3 order. This file is its execution
roadmap. The planning brief and HTML artifact are historical evidence; they do
not reopen closed decisions.

## Goal

Produce a trustworthy Phase 1 comparison from fresh, comparable whole-suite
runs and a documented owner-reviewed decision. Deploy only a model team that
is selected from complete evidence.

The work is deliberately split into small pull requests. Measurement repairs
land before model or prompt tuning so the project does not optimize against a
known-broken check. Every tested or deployed revision must already be merged to
the relevant repository's `main` branch.

## Execution rules inherited from the program roadmap

The program roadmap owns the product and comparison decisions. This execution
roadmap applies only the rules needed to produce trustworthy evidence:

- One full suite run contains one live conversation for each of the three
  model teams and each of the twelve scenarios: 36 conversations total.
- The suite keeps `repetitions: 1`. Repeated measurement means rerunning the
  complete frozen suite, never retrying or repeating an individual cell inside
  a run.
- Before a live batch starts, record its planned number of complete suite runs
  and its decision method. Do not change either after seeing results. If the
  planned whole-suite evidence is insufficient, report it as inconclusive.
- Published catalog v6 and comparison suite v1 are immutable historical
  identities. Qualification repairs use catalog v7 and suite v2; no evidence
  is relabelled as if it used the newer versions.
- An interrupted run remains immutable, incomplete, and permanently excluded
  from composition. Recovery creates a new run with its own identity and a
  `resumedFrom` reference. After every frozen provenance field matches, the
  replacement reuses every complete, measurement-valid conversation regardless
  of whether the model answer passed or failed. This finishes one interrupted
  run; it does not count as another repetition.
- All three M1 ready answers are scored, including the historically flawed
  opening answer. Only harmless ordering and spacing inside the unique
  comma-separated medication list are normalized.
- M3's unrelated visit turn must match its independent database answer and
  carry no irrelevant CD4-specific assumptions into the visit answer. Sharing
  a relation or SQL form that is valid for both questions is not a failure.
- Validation is advisory. A selected `ready` query reaches PostgreSQL through
  the bounded read-only path; its findings, database result or diagnostic, and
  independent answer check are recorded. A wrong query is a model-quality
  result, not an invalid measurement when its evidence is complete.
- If no team is selected, record `none` or `inconclusive` and continue only
  through general product remediation tested outside the frozen suite. Freeze
  a completely new batch before measuring again.

## Verified starting point

The baseline for the first implementation branch is harness `main`
`bf9b38029059ed5bd6126587e9677eee4336e368`, which pins:

- Catalyst `50f15b10c7a63eef6ede338060edfc29f246e004`;
- Med-Agent Hub `e26c52af7cabc1aaac5f521f871ac42c9ae2539e`.

Current automated checks are green and the Phase 1 product foundation is
substantial: catalog v6, honest writer outcomes, retained instruction history,
guidance, relevant failure context, verified-example selection, live runner,
scorer, report, and browser-journey skeleton all exist.

Catalog v6 and suite v1 have already produced published evidence and are now
frozen. Their repaired successors are catalog v7 and suite v2.

On the clean roadmap branch, the full non-slow Harness suite passed 1,311 tests
with 40 environment-dependent skips and 4 deliberate deselections. The
documentation guard and SpecKit Feature 008 prerequisite check also passed.

The published development run
`9ae123db-8f40-4246-8769-d427a5551769` contains one complete 36-conversation
pass. Its 7/12, 7/12, and 8/12 team results justify the decision not to deploy
from that pass. It does not constitute the required repeated qualification
evidence and must not be pooled with the new batch because it used older code
and the measurement defects below.

The owner's existing checkout at the time this roadmap opened was 25 commits
behind `origin/main` with older catalog work staged and newer component
checkouts unstaged. Preserve that work for inspection. All remediation starts
from clean current-main worktrees instead of resetting or building on that
mixed checkout.

## Findings that block qualification

| ID | Finding | Consequence |
| --- | --- | --- |
| Q1 | A scenario has one `successorGoldCheck`, and the runner applies it after every follow-up. M2's final top-ten answer therefore judges its earlier unlimited regrouping turn. | A correct intermediate answer can fail and a premature limit can pass. Published M2 attribution is unreliable. |
| Q2 | M1 and M3 lack independent answer checks for every ready turn; irrelevant carryover into M3's visit answer is not measured. Several single-turn checks compare counts rather than every requested field or row. | Passing evidence does not prove the requested answers. |
| Q3 | Validation evidence proves only that the API returned HTTP 201, not what PostgreSQL returned for the exact query. Opening turns receive weaker provenance checks, and intermediate turn time is omitted. | Wrong and incompletely evidenced model output cannot be reported honestly. |
| Q4 | `score_runs` checks only `suiteId`. It accepts duplicate, partial, or differently configured runs. | Whole-run composition can pool incomparable evidence. |
| Q5 | The combined-run command prints JSON but cannot triage, qualify, report, or publish a complete batch. | Repeated measures cannot produce the required single decision artifact. |
| Q6 | The report applies only two provisional rates while claiming that it evaluated every decision rule. | A future report could overstate what the evidence supports. |
| Q7 | The model receives fewer readable relations than the human editor, token evidence can be absent, and a selected but unexecuted query can become a “verified” example. | Product and measurement behavior can disagree even with a correct scorer. |
| Q8 | The program roadmap, brief, and HTML retain obsolete fixed run counts, context mechanisms, and stale implementation status. | The supposed single source of truth gives incompatible instructions. |
| Q9 | The wrapper freezes configuration only after a run returns, but ordinary model failures make the command exit early. Resume creates a new run while its text claims to continue the old one, and the wrapper finds a run through a racy “newest directory” lookup. | Failed or interrupted comparisons can lack their frozen identity, and resumed evidence can be attached to the wrong run. |
| Q10 | The supported OpenELIS dependency stores PostgreSQL data in a path relative to the current Catalyst worktree while every worktree uses the same Compose project name. Starting from a second clean worktree can therefore replace the database container against a fresh host path while retaining an older FHIR container. | A normal no-reseed start can silently combine incompatible runtime state, fail health checks, and make real-path qualification depend on which checkout started the stack. |

## Required evidence standard

No pull request closes from a passing total alone. Comparison evidence must
identify the code, suite, configuration, data, catalog, model setup, actual
request context, and record-level database answers used. Each
behavioral change adds a nearby case that was not used to design the fix.

Each pull request must:

1. answer and resolve every actionable current-head review thread;
2. run its focused tests plus the owning repository's normal required checks;
3. preserve a clean remote-reachable component revision;
4. record any deferred real-path check; the final merged qualification
   candidate must supply real PostgreSQL proof before live comparison;
5. avoid seeding, resetting, deploying, or changing live access rules unless
   the step below explicitly calls for it and the operation is visible to the
   owner.

## Pull-request execution plan

The dependency order is R0; then R1, R5, and R6 may proceed in parallel; then
R2 → R3 → R4 → R7 → R8. R9 is conditional on `none`, `inconclusive`, or a
shared product blocker, and R10 is conditional on a selected team. Every transition between repositories is a
separate pull request based on that repository's current `main`. A Harness
gitlink update never points at an unmerged component branch.

### R0 — Authoritative roadmap and clean baseline

**Repository:** validation harness.

Create this roadmap, reconcile the active program roadmap and supporting
decision record, and add documentation checks that reject the obsolete
per-cell repetition language and stale Phase 1 status.

Acceptance:

- every active source says one conversation per team/scenario in a complete
  run and uses only complete-suite reruns for repeated measurement;
- the program roadmap says implemented but not qualified or deployed;
- current harness and component pins are correct;
- the prior report is labelled a development first pass whose no-deploy
  disposition remains valid;
- the catalog v6 and suite v1 files are byte-locked, and both active roadmaps
  name catalog v7 and suite v2 as the qualification successors;
- the recovery, M1, M3, advisory-validation, and no-selection outcomes are
  recorded without an open interpretation gap;
- the dirty owner checkout is untouched;
- documentation consistency, `git diff --check`, and repository-line checks
  pass on the final branch.

### R1 — Frozen run identity and honest replacement recovery

**Repository:** validation harness. **Depends on:** R0.

Repair the lifecycle around the existing runner before changing its semantic
checks. A completed comparison containing wrong model answers is valid evidence
and must not be confused with a runner failure.

Acceptance:

- the exact secret-free configuration is frozen before the first warm-up or
  measured conversation, not after the command returns;
- one excluded, recorded, unscored warm-up must run in a fresh session before each
  profile in every complete suite run;
- the runner returns its run ID and directory directly; the wrapper never
  guesses through the newest directory;
- a completed run exits successfully when model answers fail but evidence is
  valid, and exits unsuccessfully for invalid, incomplete, or infrastructure-
  blocked measurement;
- an interrupted run stays immutable and incomplete; recovery always creates a
  replacement run ID and directory whose manifest records `resumedFrom`;
- a conversation is measurement-valid only when its outcome-specific evidence
  is complete; a ready path records its validation, execution decision, and
  oracle result, while a non-query path proves SQL, validation, and execution
  did not run;
- every eligible complete conversation is imported regardless of its model
  outcome, validation result, execution result, or answer correctness; recovery
  may not select or rerun cells based on quality;
- an infrastructure-failed, pre-turn, or partial conversation is never reused;
- the recorded configuration and evidence capable of changing a result must
  match before any reuse or live call;
- repeated replacement retains the full ancestry chain, never duplicates a
  team/scenario cell, and never rewrites an earlier run;
- infrastructure failures and replacements are recorded separately from model
  quality; persistent instability leaves the batch incomplete rather than
  invoking an arbitrary retry budget;
- the interrupted run never enters composition; only a complete replacement
  containing exactly one measurement-valid conversation for every cell may
  enter;
- frozen public configuration contains no password, absolute workstation path,
  private address, or security-group identifier;
- scoring and publication do not require the live database password;
- the current actionable review threads on merged runner/report pull requests
  are fixed or answered with later fixing evidence and resolved.

### R2 — Turn-scoped semantic adjudication

**Repository:** validation harness. **Depends on:** R1, R5, and R6 so suite v2
can bind final catalog v7 and profile/prompt identities.

Give each opening or follow-up turn its own execution and independent answer
contract. Preserve the published v1 suite bytes and evidence permanently.
Create an immutable v2 suite bound to catalog v7 for repaired qualification,
retain backward reading of older suites, and make v2 fail to load if a ready
turn lacks its required check.

Acceptance:

- each turn can declare its own validate, execute, answer-check, and expected
  outcome fields;
- all three M1 turns have separate row-level database answers; the opening
  answer is judged rather than accepted as inherited history, and only unique
  medication-list ordering and surrounding spacing are normalized;
- M2 turn 2 proves medication-and-gender grouping plus retained
  `do_not_perform` exclusion without a limit;
- M2 turn 3 independently proves the exact top-ten result and retained
  exclusion;
- every ready turn in M1 and M3 has an independent database answer; M3's visit
  control also proves that irrelevant CD4-specific assumptions did not change
  its answer;
- A1–A4 and B1–B3 compare every requested field or row set, not counts alone;
- duplicate aggregate keys fail rather than being silently collapsed;
- every `ready` query records advisory validation, reaches PostgreSQL through
  the bounded read-only path, and records its result or diagnostic plus the
  independent answer check; validator, database, or answer errors lower model
  quality but do not erase an otherwise complete measurement;
- opening and follow-up turns receive the same model, prompt, digest,
  forbidden-context, token, and timing evidence checks;
- all turns contribute to total calls, tokens, and elapsed time;
- triage refuses any passing row that lacks a promised turn-level check;
- older recorded evidence remains readable but is not silently upgraded into
  release evidence.
- the published v1 suite remains byte-identical; every semantic correction is
  versioned in v2 with an explicit migration note.
- when suite v2 is created, the consistency guard verifies its exact suite ID,
  catalog v7 identity, `repetitions: 1`, and absence of extended, per-scenario,
  or command-line repetition overrides in comparison mode.

### R3 — Comparable complete-run composition

**Repository:** validation harness. **Depends on:** R2.

Make a batch of complete suite runs a first-class evidence object.

Acceptance:

- each constituent run contains exactly one cell for every frozen
  team/scenario pair and no duplicate pair;
- duplicate run IDs, partial matrices, internal cell repetitions, and
  untriaged runs are rejected;
- composition requires the same frozen suite, decision method, and recorded
  configuration for everything capable of changing a result;
- every constituent manifest and indexed evidence digest verifies before
  scoring;
- infrastructure failures remain outside model-quality results; replacements
  are visible and never selected according to answer quality;
- the combined artifact names every run and preserves each run's separate
  provenance;
- scoring the same ordered batch twice produces identical bytes;
- changing run-directory order does not change the canonical score.

### R4 — Full qualification, selection, and consolidated publication

**Repository:** validation harness. **Depends on:** R3.

Produce the complete Phase 1 comparison and documented decision instead of
claiming that two provisional percentages are a full qualification.

Acceptance:

- before live execution, the batch records its owner-reviewed decision method;
  the implementation does not hard-code universal percentages, automatic
  disqualifiers, or a tie-break chain;
- the comparison covers answer and terminal-outcome correctness,
  clarification, unsupported requests, retained guidance, verified examples,
  PostgreSQL results, evidence completeness, reliability, tokens, and time;
- the decision selects one team, `none`, or `inconclusive` and explains why;
- the report includes scheduled, completed, model-failed,
  infrastructure-failed, and invalid counts; outcome and answer metrics;
  calls, tokens, timing, and exact failure reasons linked to evidence;
- `finish` accepts several complete run IDs, performs triage and deterministic
  replay, and publishes one consolidated report, comparison, dashboard, score,
  decision, frozen configuration, and provenance package;
- scoring or publication does not require a database password after the live
  runs have finished;
- tests prove that no page can claim a selection rule was met unless that rule
  was recorded before the batch and evaluated completely.

### R5 — Shared readable catalog and execution boundary

**Repositories:** Catalyst first, then validation harness repin and source
configuration. **Depends on:** R0; may run in parallel with R1 and R6.

Remove the model-only catalog restriction while preserving the workbench's
deliberately advisory manual validation. Preserve the published catalog v6
files byte-for-byte; catalog v7 records the corrected behavior.

Acceptance:

- every model and human tool can use every relation the configured read-only
  database role can read; metadata may guide use but cannot hide a relation,
  and refreshes do not fail merely because access changed;
- legacy fields such as `approvedViews` may remain readable for compatibility
  but cannot filter the runtime surface;
- manual validation remains advisory; the database's read-only controls, time
  limit, and result limit remain authoritative;
- before either current unversioned catalog file changes, copy the exact v6
  overlay and generated catalog to new paths whose filenames identify v6, then
  retarget the immutable digest guard to those archived files;
- the new active files identify v7, while guards preserve the v6 bytes and v7
  identity;
- qualification records the catalog used by each batch and starts a new batch
  if it changes; local and demo identities are recorded separately.

### R6 — Honest context evidence

**Repositories:** Med-Agent Hub first, then Catalyst, then validation harness
repin. **Depends on:** R0; may run in parallel with R1 and R5.

Finish the required context outcome without making ordinary demo availability
depend on qualification-only evidence.

Acceptance:

- evidence records what each model call actually received and which resolved
  profile, model, settings, and context limits it used;
- context is never silently truncated, summarized, or substituted;
- included and omitted guidance, examples, failures, and history remain
  identifiable with the reason for each omission;
- verified examples come only from prior kept queries that were validated and
  executed successfully for the same source;
- missing or inconsistent evidence makes a run ineligible for qualification;
  it does not take unrelated demo features offline;
- a capability mismatch is visible and never causes silent model or contract
  substitution.

### R7 — Real-path and stable-database proof

**Repositories:** validation harness, Catalyst, and Hub as separate reviewable
pull requests. **Depends on:** R5 and R6 before their release checks.

Acceptance:

- the exact merged qualification candidate passes real PostgreSQL catalog
  refresh, semantic-answer, advisory-validation, and read-only execution tests
  before the live comparison; changes that affect this path run the proof
  earlier when practical;
- the supported isolated wrapper gives its retained OpenELIS test database one
  stable location independent of the current Git worktree; starting the same
  pinned stack from a second clean worktree neither initializes a different
  database nor combines retained service containers with a new database;
- a no-reset, no-reseed restart from a second clean worktree preserves the
  existing fixture and passes the full supported health check;
- the same retained fixture supports the final comparison without being
  recreated for each check.

### R8 — Fresh whole-suite qualification batch

**Environment:** owner's local GPU through the supported isolated wrapper.
**Depends on:** R1–R7 merged and exact harness/component pins on `main`.

Before starting, freeze one signed-off suite v2/catalog v7 batch identity, its
planned number of complete runs, and its owner-reviewed decision method. In
each complete run, run one fresh-session, recorded, unscored warm-up per
profile, exclude it from qualification, and then run the entire suite. No
prompt, model, catalog, code, data, decision method, or environment change is
permitted inside the batch.

Acceptance:

- each run contains exactly 36 distinct conversations and its multi-turn
  conversations preserve their internal session;
- each run is independently triage-clean and every planned run composes under
  R3;
- repeated measurement uses complete-suite reruns only; never extend or retry
  selected measured cells after observing their quality;
- the consolidated R4 package is byte-stable, public, secret-free, and names
  every run and exact component revision;
- the owner performs the final evidence and diff review;
- if no team is selected, record `none` or `inconclusive` and do not deploy.

### R9 — Evidence-led product remediation, only if needed

**Repositories:** determined by the fresh failures. **Depends on:** R8 selects
`none`, is inconclusive, or exposes a common product blocker.

Do not assume that the old B1, B3, M2, or U2 labels remain the right targets.
Use the repaired evidence to identify the smallest shared capability failure.
If no team is selected, first record `none` or `inconclusive`. Remediate only
the general behavior, add diverse nearby and adversarial tests not copied from
the frozen suite, merge new exact revisions, and start an entirely new R8
batch. Never tune to a frozen question or pool pre-fix and post-fix runs.

Acceptance:

- each change has record-level before/after evidence and a change record for
  material prompt, model, context, catalog, or policy behavior;
- tests demonstrate the general rule on cases outside the frozen suite;
- the locked suite and its expected answers are not weakened or edited to make
  the change pass;
- a new versioned batch is evaluated from the beginning.

### R10 — Selected-team deployment and Phase 1 closeout

**Environment:** demo host. **Depends on:** a selected team from R8 or a later
clean batch.

Resolve demo profile and environment issues before deployment. Deploy only
exact merged revisions and run the three locked browser journeys side by side
with their database answers and stored session state.

Acceptance:

- the selected team is available with no fallback or substitution;
- local and demo component, catalog, profile, and prompt identities are
  recorded separately;
- patient-name ready → validate → execute matches the independent database
  result in the browser;
- clarification → frozen answer → ready remains complete after refresh with
  the exact selected version restored;
- retained `do_not_perform` guidance survives reload and remains honored, then
  the address request returns unsupported with no SQL and preserves the prior
  selected version;
- current-head automated checks and the three live journeys pass;
- the program roadmap records the selected team and evidence, or explicitly
  records that Phase 1 remains open if deployment fails.

## Verification commands

Run focused and normal repository checks for each change. Run the real stack
checks before live qualification and whenever a change directly affects that
path. These commands are evidence surfaces, not universal pull-request gates.

**Validation harness pull requests**

```bash
uv run pytest tests/test_catalyst_notebook_validation.py \
  tests/test_catalyst_notebook_scoring.py \
  tests/test_catalyst_profile_comparison_report.py \
  tests/test_catalyst_run_config.py tests/test_triage_run.py -q
uv run pytest -m 'not slow' --ignore=targets \
  --cov=harness --cov=scripts --cov-report=xml --cov-report=term-missing
uv run diff-cover coverage.xml --compare-branch origin/main --fail-under 90
bash scripts/verify-docs-consistency.sh
bash scripts/verify-repository-lines.sh --allow-harness-branch
git diff --check
```

**Real HIV source and stack checks**

```bash
uv run pytest tests/test_catalyst_hiv_catalog_surface.py -q
uv run pytest tests/test_hiv_fact_view_semantics.py -q
scripts/catalyst-mvp.sh up
scripts/catalyst-mvp.sh health
```

Use `up`, not a direct Compose invocation, and do not reseed or reset as part
of these commands. Verify the expected UI `13000` and Gateway `18000` bindings.

**Catalyst pull requests**

```bash
cd catalyst-gateway
uv run ruff format --check .
uv run ruff check .
PYTHONPATH="$PWD" uv run pytest tests/ -v
```

Also run the exact UI type check, lint, build, unit tests, and deterministic
browser tests defined by current Catalyst continuous integration.

**Med-Agent Hub pull requests**

```bash
poetry run pytest -q tests/
docker build .
```

**Selected-team deployed proof**

```bash
PLAYWRIGHT_LIVE=true \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:13000 \
PHASE1_PROFILE=<selected-team> \
npx playwright test e2e/phase1-journeys.spec.ts
```

Before any merge or deployment, run SpecKit against the existing Feature 008
scope with `SPECIFY_FEATURE=008-catalyst-query-workbench`; no remediation item
may change the fifteen Phase 3 gates.

## Pull-request tracker

| Work item | Repository | State | Pull request | Merge evidence |
| --- | --- | --- | --- | --- |
| R0 roadmap and truth | Harness | Complete | [#89](https://github.com/pmanko/clinical-ai-validation-harness/pull/89) | `30c3187b17639b06b0a501d87f3835b32a3ff4b5` |
| R1 run identity and replacement recovery | Harness | Complete | [#90](https://github.com/pmanko/clinical-ai-validation-harness/pull/90) | `4a6cc59dc2be5187df5d44ee40efdb5b9858db59` |
| R2 turn-scoped adjudication | Harness | Not started | — | — |
| R3 complete-run composition | Harness | Not started | — | — |
| R4 qualification and publication | Harness | Not started | — | — |
| R5 shared readable catalog | Catalyst → Harness | Not started | — | — |
| R6 honest context evidence | Hub → Catalyst → Harness | Not started | — | — |
| R7 real-path and stable-database proof | All three | Not started | — | — |
| R8 fresh qualification batch | Harness evidence | Blocked on R1–R7 | — | — |
| R9 product remediation if needed | Evidence-selected | Blocked on R8 | — | — |
| R10 deployment and closeout | Harness + Catalyst | Blocked on selected team | — | — |

Update this table and the append-only log in the same pull request that changes
a work item's state. A bridge, repin, report, or evidence task cannot close its
prerequisite product behavior.

## Rollback and invalidation rules

- Revert a faulty code pull request through a new pull request; never reset or
  rewrite merged evidence history.
- A measurement-contract change increments its version and invalidates earlier
  runs for composition, even when old evidence remains readable.
- A code, data, catalog, model, prompt, context, decision-method, or suite change
  starts a new batch identity.
- A failed deployment reverts to the last known-good merged pins without
  reseeding or deleting volumes unless the owner explicitly approves that
  separate operation.
- Published development evidence remains available with its limitations; it is
  never relabelled as release evidence after the fact.

## Append-only status log

### 2026-08-24 — roadmap opened

- Robust current-main audit completed.
- Owner confirmed that repeated measurement is a rerun of the complete suite,
  not repeated cells inside one run.
- Owner approved immutable catalog v6/suite v1 successors (catalog v7/suite
  v2), replacement-run recovery through `resumedFrom`, the M1 and M3 answer
  rules, fail-closed warning adjudication, and the generic-remediation/new-batch
  path when no team qualifies.
- Owner confirmed that recovery reuses every complete measurement regardless of
  answer quality, the interrupted run never composes, two infrastructure
  replacements are allowed per team, the third invalidates that team run, the
  three-to-five trigger is computed from variation/leave-one-out verdicts/the
  one-of-36 leading-team margin, and v6 is archived before active paths become
  v7.
- Existing dirty checkout preserved; clean branch
  `codex/catalyst-phase1-qualification-roadmap` created from `bf9b380`.
- Clean-branch verification: 1,311 passed, 40 skipped, 4 deselected;
  documentation consistency and Feature 008 prerequisite checks passed.
- The three stale review threads on merged harness PR #57 were reverified
  against fixing commit `4f17747` and resolved.
- R0 started. No product, model, live-data, deployment, or access-rule change
  was made.

### 2026-08-24 — R0 merged and R1 real-path smoke

- R0 merged through harness pull request #89 at
  `30c3187b17639b06b0a501d87f3835b32a3ff4b5`.
- R1 implementation froze the secret-free run seed before discovery, recorded
  one excluded warm-up per team, separated answer quality from measurement
  validity, and added immutable replacement-run recovery with preflighted
  evidence copying and full ancestry.
- Development smoke `2ac36fed-ce4c-4253-8e24-0cf07df870f6` ran scenario A1
  once through each of the three intended live model teams. It recorded three
  warm-ups and three measurement-valid rows; all three rows happened to pass.
  Its frozen seed records the A1-only selection, suite-owned repetition,
  database cross-check, and 900-second timeout without a password or local
  source path. This targeted run is implementation evidence only and is not
  part of the qualification batch.
- Preliminary smoke `7b8228d8-e1da-4d79-9002-148540364f5d` exposed that a
  command-line scenario filter was not yet represented in the frozen seed;
  that gap was fixed before the final smoke. Run
  `990f2f17-5310-4ec0-a536-1397c39a6f7b` was correctly marked invalid and
  excluded after the still-running stack build replaced the Gateway during a
  request and exhausted that team's infrastructure budget. Neither artifact
  may enter qualification composition.
- The same startup exposed Q10. The OpenELIS database bind mount is relative to
  `.openelis-docker/configs/database/data` in the initiating worktree. Docker
  recreated the database service from the new clean worktree while retaining
  the older FHIR service, which then failed on absent `hfj_search` and
  `hfj_blk_import_job` tables. This was not a planned schema change. R7 now
  requires stable retained storage across worktrees and a no-reseed restart
  proof before qualification.
- R1 opened as harness pull request #90 from commit `26fdf04`.

### 2026-08-25 — data-boundary correction

- The owner clarified that the observed count of 13 readable relations was
  never intended as a fixed product allowlist.
- The model and human paths must use the same complete catalog exposed by the
  configured read-only database role. Reviewed metadata guides use but does
  not decide availability.
- Manual validation remains advisory, consistent with Feature 008. PostgreSQL
  evaluates the exact displayed SQL under the existing read-only and bounded
  execution controls.
- Fixed-surface startup failure, blanket exploratory-SQL bans, and identical
  local/demo relation requirements were removed from R5. No Catalyst change
  based on those superseded requirements was committed, pushed, or opened as a
  pull request.
- R1 is merged through harness pull request #90 at
  `4a6cc59dc2be5187df5d44ee40efdb5b9858db59`.

### 2026-08-25 — outcome-focused simplification

- The owner removed the fixed three-to-five run rule, numerical pass gates,
  automatic tie-breaks, and the fixed infrastructure retry budget. A batch now
  records its complete-run count and owner-reviewed decision method before live
  execution and reports an inconclusive result when the planned evidence is not
  enough.
- Advisory validation no longer blocks the selected SQL from reaching the
  bounded read-only PostgreSQL path. Wrong SQL, a database diagnostic, or a
  wrong answer is model-quality evidence when the measurement record is
  complete.
- The M3 visit control now tests the independent answer and irrelevant
  CD4-specific carryover. It does not ban an otherwise useful relation or SQL
  form.
- The context contract now specifies visible inputs, omissions, provenance,
  and verified examples without fixing caps, physical ordering, or a ranking
  formula.
- Real PostgreSQL proof remains mandatory before live comparison, but is not a
  universal pull-request gate. Branch administration, image publication, and
  similar repository operations are not Phase 1 product acceptance criteria.
- These decisions supersede the numerical and mechanism-specific statements in
  the earlier append-only entries.
