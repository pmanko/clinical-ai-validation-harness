# Catalyst Phase 1 qualification-remediation roadmap

**Status:** Active execution roadmap, opened 2026-08-24. Phase 1 is built but
is not qualified or deployed. This roadmap governs the repairs needed to make
the model-team decision trustworthy and repeatable.

`specs/catalyst-program-roadmap.md` remains the authority for product scope,
the reviewed data surface, the context contract, the three model teams, the
acceptance thresholds, and the P1 → P2 → P3 order. This file is its execution
roadmap. The planning brief and HTML artifact are historical evidence; they do
not reopen closed decisions.

## Goal

Produce a release-grade Phase 1 qualification decision from fresh, comparable
whole-suite runs, then deploy and close Phase 1 only if one or more model teams
pass every locked gate.

The work is deliberately split into small pull requests. Measurement repairs
land before model or prompt tuning so the project does not optimize against a
known-broken check. Every tested or deployed revision must already be merged to
the relevant repository's `main` branch.

## Decisions that remain locked

- One full suite run contains one live conversation for each of the three
  model teams and each of the twelve scenarios: 36 conversations total.
- The suite keeps `repetitions: 1`. Repeated measurement means rerunning the
  complete frozen suite, never retrying or repeating an individual cell inside
  a run.
- Start with three fresh complete suite runs. Extend the unchanged batch to
  five if any scored turn's terminal outcome or answer correctness varies
  across the first three runs; if leaving out any one run changes whether a
  team passes any qualification gate; or if the two leading teams differ by no
  more than one complete-scenario success among their 36 measurements. Stop at
  five and report a remaining close result as inconclusive.
- A run is local model-quality evidence. The deployed server receives only the
  three final browser journeys after a team qualifies. Local and server
  measurements are not pooled.
- All thirteen reviewed relations are available to both the model and the
  person editing SQL. Database permissions do not silently change that list.
- Published catalog v6 and comparison suite v1 are immutable historical
  identities. Qualification repairs use catalog v7 and suite v2; no evidence
  is relabelled as if it used the newer versions.
- The writer may choose `ready`, `needs_clarification`, or `unsupported`.
  Gateway-owned `rejected` remains separate.
- An interrupted run remains immutable, incomplete, and permanently excluded
  from composition. Recovery creates a new run with its own identity and a
  `resumedFrom` reference. After every frozen provenance field matches, the
  replacement reuses every complete, measurement-valid conversation regardless
  of whether the model answer passed or failed.
- All three M1 ready answers are scored, including the historically flawed
  opening answer. Only harmless ordering and spacing inside the unique
  comma-separated medication list are normalized.
- M3's unrelated visit turn must match its independent database answer, use a
  different query digest, and copy no CD4/observation relation, predicate, or
  projection from either earlier turn.
- A ready query may proceed when validation is `valid`, or when validation is
  `warning` and every warning rule code is on the suite's frozen non-blocking
  allowlist. `invalid`, unknown status, or an unlisted warning fails the turn.
- If no team qualifies, record `none` and continue only through general
  product remediation tested outside the frozen suite. Freeze a completely
  new batch before measuring again.
- Phase 1 does not make causal claims about individual context practices.
- Phase 2 conversation mode and all fifteen Phase 3 Dashboard Builder gates
  remain outside this remediation.

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
| Q2 | M1 and M3 lack independent answer checks for every ready turn; the M3 no-copy control is not measured. Several single-turn checks compare counts rather than every requested field or row. | Passing evidence does not prove the requested answers. |
| Q3 | Validation evidence proves only that the API returned HTTP 201, not that the model query was valid. Opening turns receive weaker provenance checks, and intermediate turn time is omitted. | Invalid or incompletely evidenced model output can enter a score. |
| Q4 | `score_runs` checks only `suiteId`. It accepts duplicate, partial, or differently configured runs. | Whole-run composition can pool incomparable evidence. |
| Q5 | The combined-run command prints JSON but cannot triage, qualify, report, or publish a complete batch. | Repeated measures cannot produce the required single decision artifact. |
| Q6 | Qualification applies only overall and worst-scenario rates while describing those as every gate. | A future team could be declared eligible without satisfying the locked contract. |
| Q7 | The catalog/grant boundary can drift, token accounting can fail open, and a selected but unexecuted query can become a “verified” example. Query-policy coverage also omits several locked unsafe forms. | Product-level zero-tolerance failures remain possible even with a correct scorer. |
| Q8 | The program roadmap, brief, and HTML retain obsolete per-cell three-to-five language and stale implementation status. | The supposed single source of truth gives incompatible instructions. |
| Q9 | The wrapper freezes configuration only after a run returns, but ordinary model failures make the command exit early. Resume creates a new run while its text claims to continue the old one, and the wrapper finds a run through a racy “newest directory” lookup. | Failed or interrupted comparisons can lack their frozen identity, and resumed evidence can be attached to the wrong run. |
| Q10 | The supported OpenELIS dependency stores PostgreSQL data in a path relative to the current Catalyst worktree while every worktree uses the same Compose project name. Starting from a second clean worktree can therefore replace the database container against a fresh host path while retaining an older FHIR container. | A normal no-reseed start can silently combine incompatible runtime state, fail health checks, and make real-path qualification depend on which checkout started the stack. |

## Required evidence standard

No pull request closes from a passing total alone. Evidence must identify the
exact code, suite, configuration, data, catalog, model files, prompts,
tokenizer, context limits, and record-level database answers used. Each
behavioral change adds a nearby case that was not used to design the fix.

Each pull request must:

1. answer and resolve every actionable current-head review thread;
2. run its focused tests plus the owning repository's full required checks;
3. preserve a clean remote-reachable component revision;
4. record any intentionally skipped real-path check and keep the PR open until
   that check is supplied;
5. avoid seeding, resetting, deploying, or changing live access rules unless
   the step below explicitly calls for it and the operation is visible to the
   owner.

## Pull-request execution plan

The dependency order is R0; then R1, R5, and R6 may proceed in parallel; then
R2 → R3 → R4 → R7 → R8. R9 is conditional on a `none` result, and R10 is
conditional on an eligible team. Every transition between repositories is a
separate pull request based on that repository's current `main`. A Harness
gitlink update never points at an unmerged component branch.

### R0 — Authoritative roadmap and clean baseline

**Repository:** validation harness.

Create this roadmap, reconcile the active program roadmap and supporting
decision record, and add documentation checks that reject the obsolete
per-cell repetition language and stale Phase 1 status.

Acceptance:

- every active source says one conversation per team/scenario in a complete
  run and three complete runs, extending the complete batch to five;
- the program roadmap says implemented but not qualified or deployed;
- current harness and component pins are correct;
- the prior report is labelled a development first pass whose no-deploy
  disposition remains valid;
- the catalog v6 and suite v1 files are byte-locked, and both active roadmaps
  name catalog v7 and suite v2 as the qualification successors;
- the owner-approved recovery, M1, M3, validation-warning, and no-qualifier
  decisions are recorded without an open interpretation gap;
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
- suite bytes, frozen configuration, component revisions, dataset and catalog
  identities, team/profile/model/prompt/tokenizer identities, scenario order,
  and every imported evidence digest must match before any reuse or live call;
- repeated replacement retains the full ancestry chain, never duplicates a
  team/scenario cell, and never rewrites an earlier run;
- across the linked chain, a team may replace two infrastructure failures; its
  third infrastructure failure invalidates that team's constituent run;
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
  control also has a query digest different from both CD4 turns and reuses no
  CD4/observation relation, predicate, or projection;
- A1–A4 and B1–B3 compare every requested field or row set, not counts alone;
- duplicate aggregate keys fail rather than being silently collapsed;
- an accepted model query must have validation status `valid`, or status
  `warning` with every finding's rule code on the suite's frozen non-blocking
  allowlist; `invalid`, unknown status, or an unlisted warning fails before
  execution; every accepted query then executes and matches its turn's answer;
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
- composition requires identical suite bytes, frozen run configuration,
  thresholds, dataset and catalog identity, harness/Catalyst/Hub revisions,
  profile and prompt digests, exact model-file identity, tokenizer, context
  window, and output reserve;
- every constituent manifest and indexed evidence digest verifies before
  scoring;
- infrastructure failures remain outside model denominators; the first two per
  team may be replaced and the third invalidates that team's constituent run;
- the combined artifact names every run and preserves each run's separate
  provenance;
- scoring the same ordered batch twice produces identical bytes;
- changing run-directory order does not change the canonical score.

### R4 — Full qualification, selection, and consolidated publication

**Repository:** validation harness. **Depends on:** R3.

Encode the complete Phase 1 decision instead of two proxy thresholds.

Acceptance:

- eligibility covers complete-scenario rate, each scenario floor, ready-answer
  correctness, clarification recall and precision, post-clarification answer
  correctness, unsupported accuracy, retained guidance, the verified-example
  control, validation/execution, token completeness, and time limit;
- every zero-tolerance product or evidence failure is explicit and blocks the
  affected product or team as specified by the program roadmap;
- selection applies the locked tie-break order and chooses none when no team
  qualifies;
- the report includes scheduled, completed, model-failed,
  infrastructure-failed, and invalid counts; outcome and answer metrics;
  calls; total tokens; median and 95th-percentile time; intervals; and exact
  failure reasons linked to evidence;
- `finish` accepts several complete run IDs, performs triage and deterministic
  replay, and publishes one consolidated report, comparison, dashboard, score,
  decision, frozen configuration, and provenance package;
- scoring or publication does not require a database password after the live
  runs have finished;
- tests prove that no page can say “meets every gate” when only a subset was
  evaluated.

### R5 — Exact data surface and query safety

**Repositories:** Catalyst first, then validation harness repin and source
configuration. **Depends on:** R0; may run in parallel with R1 and R6.

Enforce the already approved thirteen-relation contract without narrowing the
owner's chosen surface. Preserve the published catalog v6 files byte-for-byte;
the corrected contract is catalog v7.

Acceptance:

- catalog v7 generation, editor suggestions, model lint, manual lint, and
  execution use the same exact qualified relation set;
- before either current unversioned catalog file changes, copy the exact v6
  overlay and generated catalog to new paths whose filenames identify v6, then
  retarget the immutable digest guard to those archived files;
- the new active overlay and generated catalog identify v7, and the guard
  verifies both preserved v6 bytes and the v7 identity;
- startup and deployment fail when the reviewed catalog, database grants, or
  discovered surface differ;
- all thirteen relations and columns have reviewed, non-placeholder meaning,
  grain, join, terminology, unit, exclusion, nullability, sensitivity, and
  version metadata;
- raw, operating, multiplicative-grain, and preferred-relation warnings are
  deterministic and retained for both model and manual SQL;
- unknown or unqualified relations and columns, writes, cartesian joins, table
  functions, and volatile or side-effecting functions fail before execution;
- the database role is explicitly read-only with bounded statements and
  results, and new grants cannot silently publish new relations;
- local and demo environments expose matching catalog, grant, and surface
  digests before deployed acceptance.

### R6 — Context and token integrity

**Repositories:** Med-Agent Hub first, then Catalyst, then validation harness
repin. **Depends on:** R0; may run in parallel with R1 and R5.

Finish the locked context contract without changing its caps or precedence.

Acceptance:

- every writer, checker, and repair call counts the fully rendered messages
  with the declared exact tokenizer before model invocation;
- missing token accounting or overflow fails before the call, with no hidden
  truncation or character-count substitute;
- model-file identity, tokenizer identity, context window, output reserve, and
  generation settings are digest-bound and recorded;
- physical request order matches the locked context order and the static
  prefix is byte-identical for identical static inputs;
- verified examples require a successfully validated and executed kept
  version with matching source and catalog digests;
- pin-from-failure accepts only an eligible retained finding and records the
  accepting actor and provenance;
- every omitted guidance entry, example, failure, or history item is itemized
  with its reason;
- Hub advertises the versioned capability before Catalyst sends the request
  shape, and mixed-version startup fails visibly instead of substituting.

### R7 — Required real-path checks and repository safeguards

**Repositories:** validation harness, Catalyst, and Hub as separate reviewable
pull requests. **Depends on:** R5 and R6 before their release checks.

Acceptance:

- real PostgreSQL catalog, semantic-answer, permission-drift, and SQL-safety
  tests run as required checks rather than skipping when the database is
  absent;
- the strict repository-line check is required on merge candidates and passes
  after every repin;
- Catalyst and Hub `main` branches receive protection consistent with the
  documented pull-request policy;
- Catalyst standalone bootstrap uses a merged Hub revision or an explicit
  supported override, never a feature-only commit;
- the supported isolated wrapper gives its retained OpenELIS test database one
  stable location independent of the current Git worktree; starting the same
  pinned stack from a second clean worktree neither initializes a different
  database nor combines retained service containers with a new database;
- a no-reset, no-reseed restart from a second clean worktree preserves the
  existing fixture and passes the full supported health check;
- unresolved current review threads on merged Phase 1 pull requests are
  answered and resolved, including already-fixed findings;
- Hub image publication, if retained, publishes the tested image by immutable
  digest rather than rebuilding or trusting a mutable tag.

### R8 — Fresh whole-suite qualification batch

**Environment:** owner's local GPU through the supported isolated wrapper.
**Depends on:** R1–R7 merged and exact harness/component pins on `main`.

Before starting, freeze one signed-off suite v2/catalog v7 batch identity. In
each complete run, run one fresh-session, recorded, unscored warm-up per profile,
exclude it from qualification, and then run the entire suite.
Run three complete suites initially. No prompt, model, catalog, code, data,
threshold, ordering, or environment change is permitted inside the batch.

Acceptance:

- each run contains exactly 36 distinct conversations and its multi-turn
  conversations preserve their internal session;
- each run is independently triage-clean and all three compose under R3;
- after the first three complete runs, extend the entire suite twice under the
  same identity if any scored turn varies in terminal outcome or answer
  correctness, any leave-one-run-out score changes a qualification verdict, or
  the leading teams differ by at most one complete-scenario success out of 36;
  never extend individual cells;
- the consolidated R4 package is byte-stable, public, secret-free, and names
  every run and exact component revision;
- the owner performs the final evidence and diff review;
- if no team passes every gate, the recorded selection is explicitly `none`
  and no deployment occurs.

### R9 — Evidence-led product remediation, only if needed

**Repositories:** determined by the fresh failures. **Depends on:** R8 selects
none or exposes a common product blocker.

Do not assume that the old B1, B3, M2, or U2 labels remain the right targets.
Use the repaired evidence to identify the smallest shared capability failure.
If no team qualifies, first record the selection as `none`. Remediate only the
general behavior, add diverse nearby and adversarial tests not copied from the
frozen suite, merge new exact revisions, and start an entirely new R8 batch.
Never tune to a frozen question or pool pre-fix and post-fix runs.

Acceptance:

- each change has record-level before/after evidence and a change record for
  material prompt, model, context, catalog, or policy behavior;
- tests demonstrate the general rule on cases outside the frozen suite;
- the locked suite and its expected answers are not weakened or edited to make
  the change pass;
- a new versioned batch is evaluated from the beginning.

### R10 — Selected-team deployment and Phase 1 closeout

**Environment:** demo host. **Depends on:** an eligible team from R8 or a later
clean batch.

Resolve demo profile and environment issues before deployment. Deploy only
exact merged revisions and run the three locked browser journeys side by side
with their database answers and stored session state.

Acceptance:

- the selected team is available with no fallback or substitution;
- local and demo component, catalog, grant, surface, profile, and prompt
  identities are recorded;
- patient-name ready → validate → execute matches the independent database
  result in the browser;
- clarification → frozen answer → ready remains complete after refresh with
  the exact selected version restored;
- retained `do_not_perform` guidance survives reload and remains honored, then
  the address request returns unsupported with no SQL and preserves the prior
  selected version;
- current-head automated checks, strict repository-line verification, and the
  three live journeys pass;
- the program roadmap records the selected team and evidence, or explicitly
  records that Phase 1 remains open if deployment fails.

## Verification commands

Run the focused checks for each change and the owning repository's full checks.
These are minimum evidence surfaces, not substitutes for a requirement-specific
test named above.

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
| R1 run identity and replacement recovery | Harness | In review | [#90](https://github.com/pmanko/clinical-ai-validation-harness/pull/90) | — |
| R2 turn-scoped adjudication | Harness | Not started | — | — |
| R3 complete-run composition | Harness | Not started | — | — |
| R4 qualification and publication | Harness | Not started | — | — |
| R5 data surface and safety | Catalyst → Harness | Not started | — | — |
| R6 context and tokens | Hub → Catalyst → Harness | Not started | — | — |
| R7 real-path checks and safeguards | All three | Not started | — | — |
| R8 fresh qualification batch | Harness evidence | Blocked on R1–R7 | — | — |
| R9 product remediation if needed | Evidence-selected | Blocked on R8 | — | — |
| R10 deployment and closeout | Harness + Catalyst | Blocked on eligible team | — | — |

Update this table and the append-only log in the same pull request that changes
a work item's state. A bridge, repin, report, or evidence task cannot close its
prerequisite product behavior.

## Rollback and invalidation rules

- Revert a faulty code pull request through a new pull request; never reset or
  rewrite merged evidence history.
- A measurement-contract change increments its version and invalidates earlier
  runs for composition, even when old evidence remains readable.
- A code, data, catalog, model, prompt, tokenizer, context, threshold, or suite
  change starts a new batch identity.
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

### 2026-08-25 — measurement-surface work landed beside this plan (no R state change)

- The owner-directed judging review executed outside the R sequence but inside
  its rules: harness PR #92 reworks the report abstract (data-argued, no
  gates), replaces the `<80` flag with rubric-anchor flagging, leads the judge
  summary with axes, states single-actor/no-adjudication limits in place, adds
  the `catalyst-judge-rank-v1` comparative-ranking rubric and machinery, and
  gives the runner per-turn `goldCheck` support — the Q1/R2 enabler. A draft
  minimal "suite v2" was created and then **withdrawn** the same day: the
  shipped v2 is R2's to create, bound to catalog v7 with per-turn contracts
  for every scenario. Suite v1 remains byte-identical. Records:
  `specs/artifacts/planning/judging-review-2026-08-25.md`,
  `specs/008-catalyst-query-workbench/pccp/2026-08-25-catalyst-judge-rank-v1.md`.
- The published report and landing surfaces changed under
  `specs/artifacts/planning/report-surfaces-2026-08-25.md` (PRs #87/#91/#92);
  the 2026-08-24 code-QA audit's non-Q findings (CI false-green fix detail,
  dead code, coverage gaps, spec-document verdicts, owner scope calls) are
  persisted in `specs/artifacts/planning/code-qa-audit-2026-08-24.md`.
