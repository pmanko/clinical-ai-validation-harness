# OpenMRS Upstream Merge Roadmap

**Roadmap ID:** `OPENMRS-UPSTREAM-MERGE-2026-09-14`
**Status:** Approved for execution (user direction, 2026-09-14)
**Relationship:** Executes the "merges and publication" item of Signoff 3 in
[`openmrs-dual-provider-parity-roadmap.md`](openmrs-dual-provider-parity-roadmap.md). It does
not supersede that roadmap or change any architecture decision in it. The integration-branch
model in that roadmap's §8 stays in force until M2 below closes; M3 retires it.

This file is the single record for this roadmap. Section 7 is the mutable iteration log; every
other section is fixed once approved and changes only by a dated amendment appended to §8.

## 1. Goal

The dual-provider ChartSearchAI work lives upstream. querystore #68, chartsearchai #157 and
esm #23 are merged into `openmrs/*@main`, the harness pins upstream `main` for all three, and
the `pmanko/*` forks stop being where the truth lives.

Three milestones. M1 is entirely in our hands. M2 is the maintainer's. M3 is ours again and
is small.

## 2. Validated Baseline (2026-09-14)

Every number below was read live on 2026-09-14 from GitHub, CI, or a fetched clone. The
submodule pins equal the PR heads byte for byte.

Names used in this roadmap, so the numbers are not load-bearing: the **QueryStore read-API PR**
is querystore #68; the **backend PR** is chartsearchai #157; the **frontend PR** is esm #23;
the **account-context PR** is fork #33; the **nine stale PRs** are chartsearchai #72, #25,
#22, #21, #20, #19 and esm #11, #10, #9.

| Line | PR | Head | Age | Size | Mergeable | vs upstream `main` | CI | Maintainer threads |
|---|---|---|---|---|---|---|---|---|
| querystore | [#68](https://github.com/openmrs/openmrs-module-querystore/pull/68) | `f2fca727` | 40 d | +4,438 / -91, 59 files, 16 commits | CLEAN | 16 ahead, 20 behind | green | 19 total, 17 unresolved |
| chartsearchai | [#157](https://github.com/openmrs/openmrs-module-chartsearchai/pull/157) | `d46f517b` | 40 d | +10,983 / -343, 97 files, 52 commits | CONFLICTING | 52 ahead, 19 behind | required green; `build against querystore HEAD` fails | 3, none from the maintainer |
| esm | [#23](https://github.com/openmrs/openmrs-esm-chartsearchai/pull/23) | `77f61c8a` | 40 d | +8,075 / -1,837, 39 files, 51 commits | CLEAN | 51 ahead, 0 behind | green | 5, none from the maintainer |

Dependency chain, confirmed by CI rather than convention: #157's `build against querystore HEAD`
job fails with nine `cannot find symbol` errors in `QueryStoreChartBuilder.java` on
`PatientChartRead`, `ContextSlice`, `ContextSliceRecord` and `ContextSliceRequest`, the exact
types #68 adds. #157 cannot compile against upstream querystore until #68 merges and its
`querystore-api` SNAPSHOT publishes.

Upstream chartsearchai velocity since W32: 37, 22, 14, 24, 34, 17 commits per week. Each #157
resync buys roughly one week before it conflicts again. Upstream querystore and esm are quiet.

#68 review state on 2026-09-09 23:45 UTC (last event on any of the three PRs):

- 10 threads from 2026-08-05/06, answered by us on 2026-09-08, not yet resolved by the
  maintainer.
- 7 threads from 2026-09-09 with no reply. Three are correctness findings with reproductions:
  1. `LuceneBackendStore`: `LuceneSchemaManager.listAllIndexes()` swallows a directory whose
     writer will not open (stale `write.lock`), so the index never reaches `knownIndexNames()`
     and the read reports `chartTruncated:false` with a whole resource type missing.
  2. `QueryStoreServiceImpl`: a failed cold touch inside `ensureIndexedSafely` returns
     `{"results":[],"chartTruncated":false,"projectionComplete":true}` for a real patient.
  3. `context-query-stopwords.txt`: `right` is a stopword and `left` is not, so laterality is
     stripped from one side only; `nor` and `off` flagged alongside.
  Four are smaller: the dead two-argument `PatientRecordView.snapshotId` overload that assumes
  `projectionComplete = true`; `RestConstants.MAX_RESULTS_ABSOLUTE` never tracking
  `webservices.rest.maxResultsAbsolute` (use `RestUtil.getAbsoluteLimit()`); an `adr.md`
  sentence now inverted against `ContextSlice.getChartSnapshotId()`; a missing re-bootstrap
  advisory for the new `date_kind` field.

Stale PRs from the pre-integration-branch model, still open under pmanko: chartsearchai #72,
#25, #22, #21, #20, #19; esm #11, #10, #9. (#26 and #12 were closed with supersession notes.)

Test baselines from the 2026-09-09 source validation: querystore API 520 + OMOD 51 (two skips);
chartsearchai API 2,126 + OMOD 198 (57 skips); esm 462.

Status hub (`specs/artifacts/project-status/`, published at `/status/`): `pull-requests.json`
(as of 2026-09-12) carries all twelve PRs above with `nextAction` text; efforts
`clinical.dual_provider` and `upstream.older_prs` name the same work; `roadmaps.json` has no
row for this roadmap; the hub README's ChartSearchAI row points at the parity roadmap only. The
crosswalk already marks the parity status doc (CLIN-A03) and the upstream inventory (CLIN-A05)
as stale.

Pending fork work that the scope guard in §9 applies to: `pmanko/openmrs-module-chartsearchai`
#33 (account-context transport, +542 / -32, 12 files, base `harness-integration`, MERGEABLE,
paired with harness #148). It is new capability, not a review fix or resync; landing it on
`harness-integration` grows #157. Its disposition is an open decision recorded in §8.

## 3. Milestones and Acceptance Criteria

Each criterion has a check that returns a value. "Now" is the 2026-09-14 reading.

### M1: Review-complete (ours)

Definition: nothing on any of the three PRs is waiting on us.

| # | Acceptance criterion | Check | Now |
|---|---|---|---|
| 1.1 | Every unresolved #68 thread has our reply as its last comment, citing the fixing commit or a reasoned decline | `unresolved-waiting-on-us` query in §5 returns 0 | 7 |
| 1.2 | The three #68 bug findings each have a red-first test that fails on `f2fca727` and passes on the fix | test class named in the thread reply; commit SHA cited | 0 of 3 |
| 1.3 | #68 stays CLEAN and green after the fixes | `gh pr view 68 --repo openmrs/openmrs-module-querystore --json mergeable,statusCheckRollup` | CLEAN, green |
| 1.4 | #157 is MERGEABLE against current `upstream/main` | `gh pr view 157 --repo openmrs/openmrs-module-chartsearchai --json mergeable` | CONFLICTING |
| 1.5 | #157's `build.yml` carries no paired-build machinery | `git diff upstream/main origin/harness-integration -- .github/workflows/build.yml` is empty | +72 / -1 |
| 1.6 | The nine stale PRs are closed with a supersession comment | `gh pr list --author pmanko --state open` on both repos returns only #157 and #23 | 9 open |
| 1.7 | Full reactors green at the final heads with no fewer tests than the baseline in §2 | commands in §5 | baseline |
| 1.8 | Status hub current: this roadmap has a `roadmaps.json` row; `clinical.dual_provider` and `upstream.older_prs` name it as the next deliverable; every PR row touched by an iteration carries that iteration's head and next action | `scripts/project-status.sh check` exits 0; `roadmaps.json` row exists | no row |

### M2: Merged (maintainer)

| # | Acceptance criterion | Check |
|---|---|---|
| 2.1 | #68 merged and a `querystore-api` SNAPSHOT containing `ContextSlice` is published | `gh pr view 68 --json state` = `MERGED`; `Deploy SNAPSHOT to Maven` job SUCCESS on querystore `main` |
| 2.2 | #157 merged, `build against querystore HEAD` green beforehand | `gh pr view 157 --json state` = `MERGED` |
| 2.3 | #23 merged | `gh pr view 23 --json state` = `MERGED` |

We do not control timing here. Our job during M2 is a same-day reply to any new thread and
re-running I4 if #157 goes red while waiting.

### M3: Fork buffer retired (ours)

| # | Acceptance criterion | Check |
|---|---|---|
| 3.1 | `.gitmodules` points the three submodules at `openmrs/*` with `branch = main` | `grep -B1 -A2 'branch = main' .gitmodules` lists all three |
| 3.2 | Recorded submodule heads are reachable from `openmrs/*@main` | `git merge-base --is-ancestor <pin> upstream/main` exits 0 for each |
| 3.3 | Repository-line gate passes under the new model | `scripts/verify-repository-lines.sh --check-publication-prs` exits 0 after it stops expecting fork PRs |
| 3.4 | Stack works at the merged heads: one bundled and one hub turn complete on `/chat/stream` | `scripts/probe-chartsearchai-relay.py --identity-only` succeeds for both providers |
| 3.5 | The parity roadmap status doc records the merge SHAs and marks Signoff 3's merges-and-publication item done | `openmrs-dual-provider-parity-roadmap-status.md` |
| 3.6 | No current surface still describes `harness-integration` as the publication head; historical surfaces are labelled, not rewritten | the I7 inventory is worked through; `git grep -n harness-integration -- ':!targets' ':!specs/artifacts/planning/archive' ':!specs/artifacts/lanes'` returns only labelled history and this roadmap; `verify-docs-consistency.sh` exits 0 |

## 4. Iterations

Each iteration is validated on its own and logged in §7 before the next starts. An iteration
whose validation fails is "open", never "done".

Every iteration's exit includes the status-hub update: refresh the `pull-requests.json` rows
for the PRs it touched (head, mergeability, checks, dated `nextAction`), update the effort row's
`status`, `next_deliverable`, `evidence` and `last_checked`, append the §7 log row, then run
`scripts/project-status.sh refresh`. The hub is the dashboard; a roadmap that moves without it
is the drift this roadmap exists to remove.

### I0: Register the roadmap in the status hub

- Scope: add a `roadmaps.json` row for this file (current authority for the merge and
  retirement sequence; the parity roadmap keeps requirement authority); point
  `clinical.dual_provider` and `upstream.older_prs` at it as the next deliverable; make the hub
  README's ChartSearchAI row name it.
- Depends on: nothing.
- Validation: `scripts/project-status.sh refresh` exits 0; 1.8 holds.
- Exit: the dashboard shows this roadmap as the ChartSearchAI next checkpoint.

### I1: #68 correctness fixes

- Scope: the three bug findings in §2, red-first. Write each test, run it against `f2fca727`
  and record the failure, then fix.
- Depends on: nothing.
- Validation: each new test fails on `f2fca727` and passes on the fix; full querystore reactor
  green with test counts at or above baseline; push to `pmanko:harness-integration`; #68 CI
  green; 1.3 holds.
- Exit: three commits pushed, three threads replied with test name and SHA.

### I2: #68 hygiene findings and thread closeout

- Scope: the four smaller findings in §2; one reply per thread citing the commit. Then one
  reply on each of the ten 2026-09-08 threads asking the maintainer to resolve or restate.
  Threads are left open for the maintainer to resolve; we do not resolve our own (§8 A2).
- Depends on: I1 pushed (so replies cite final SHAs).
- Validation: 1.1 returns 0; 1.3 holds; 1.7 for querystore.
- Exit: #68 has no thread whose last comment is not ours.

### I3: Stale PR closure

- Scope: for each of the nine PRs, confirm its delta is either in #157/#23 or deliberately
  dropped (per the disposition record in `openmrs-dual-provider-upstream-inventory.md`), then
  close with a one-line supersession comment naming the successor. Owner approval for
  content-confirmed closures was granted 2026-09-14 (§8 A2); a PR carrying unique live work
  stays open and is reported instead.
- Depends on: nothing. Do it before I4 so #157 is the only chartsearchai PR of ours on the
  board.
- Validation: 1.6 returns only #157 and #23.
- Exit: nine PRs closed, none deleted.

### I4: #157 resync and paired-build removal

- Scope: merge `upstream/main` into `pmanko:harness-integration`, resolve the conflict files
  (as of 2026-09-14: `ChartSearchService`, `LlmInferenceService`, `LlmProvider`,
  `PatientClinicalContext`, `PatientClinicalContextBuilder`, `ArchitectureGuardTest`,
  `ChartSearchAiConditionRuleCoverageTest`, `ChartSearchAiInteractionPairExtentTest`); keep
  `safetyStatus` on `ChartAnswer` per the recorded decision. Remove the paired-build jobs and
  the `build against querystore HEAD` job from `.github/workflows/build.yml` so the file
  matches upstream.
- Depends on: 2.1 (the published SNAPSHOT is what makes the plain `build` job resolve). Rule 2
  in §6: no resync before then unless work must land on the branch.
- Validation: install querystore from `targets/querystore` first, build chartsearchai with
  `-nsu`; 1.7 for chartsearchai; push; 1.4 MERGEABLE; every check green including the plain
  `build`; 1.5 empty diff.
- Exit: #157 in the same CLEAN-and-green state #68 holds now.

### I5: #23 refresh

- Scope: rebase or merge `upstream/main` only if #23 has drifted; otherwise no change.
- Depends on: 2.2 (the ESM is the UI half of #157's wire contract).
- Validation: MERGEABLE; build green; 1.7 for esm.
- Exit: #23 ready for the maintainer's merge.

### I6: Fork buffer retirement

- Scope: `.gitmodules` to `openmrs/*@main` for the three; bump pins to the merged upstream
  heads; update `scripts/verify-repository-lines.sh` so it verifies upstream reachability
  instead of fork PR heads; record merge SHAs in the parity status doc.
- Depends on: 2.1, 2.2, 2.3.
- Validation: 3.1 through 3.5.
- Exit: harness PR merged into `main`; the forks' `harness-integration` branches are left in
  place as history, not deleted.

### I7: Consolidation sweep

- Scope: every tracked surface that still encodes the fork or integration-branch model, read
  on 2026-09-14 with `git grep -n -E 'harness-integration|pmanko/openmrs' -- ':!targets'`.
  Three groups:
  1. Rewire or remove (they will be wrong, not just stale):
     `AGENTS.md:103-105` (publication-head rule); `Makefile:172,204` and the targets those
     comments annotate; `.github/workflows/harness-ci.yml:59` (fetches `harness-integration`);
     `scripts/openmrs-source-pair-test.sh` and `tests/test_openmrs_source_pair_script.py`
     (assert HEAD equals `origin/harness-integration`); `scripts/verify-repository-lines.sh`
     and `tests/test_repository_lines_script.py` (I6); the `.guards.json`
     `pinned_ref_in_file` rule for `build.yml` and `targets/querystore` (dead once I4 removes
     the paired build; drop it in I4, not here).
  2. Reconcile status prose to the merged state: the parity roadmap status doc (CLIN-A03) and
     upstream inventory (CLIN-A05), both already marked stale in the crosswalk; hub
     `efforts.json` rows `clinical.dual_provider`, `upstream.older_prs`, `querystore.context`;
     hub `README.md` current-work row and `dashboard.json` ChartSearchAI summary; the
     published canvases `specs/artifacts/canvases/upstream-contribution-and-compatibility.canvas.tsx`
     (models `harness-integration -> openmrs`) and `chartsearchai-and-querystore.canvas.tsx`
     (pin figures from 2026-06-12); `landing/wahs/index.html:125` (cites fork revision
     `8dc6ef9`; cite the merged upstream revision or label it as dated evidence).
  3. Leave as labelled history: `specs/artifacts/lanes/L4-*`, `lanes/dev-roadmap.md`,
     `specs/artifacts/planning/archive/*`, `hub-consolidation-roadmap*.md`, `specs/004-*`,
     `specs/007-*`, `specs/ux-staged-states-remediation.md`, `specs/roadmap.canvas.tsx` (its
     two hits already describe the hub buffer's retirement).
- Depends on: I6.
- Validation: 3.6; `verify-docs-consistency.sh` exits 0; `scripts/project-status.sh check`
  exits 0; the docs site build that prerenders the canvases passes.
- Exit: one harness PR; the crosswalk rows CLIN-A03 and CLIN-A05 no longer read "stale".

## 5. Validation Commands

Unresolved #68 threads waiting on us (1.1):

```sh
gh api graphql -f query='query{repository(owner:"openmrs",name:"openmrs-module-querystore"){pullRequest(number:68){reviewThreads(last:100){nodes{isResolved comments(last:1){nodes{author{login}}}}}}}}' \
  --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved|not) | select(.comments.nodes[0].author.login != "pmanko")] | length'
```

Reactors (1.7), run from the harness root at the exact heads being validated:

```sh
mvn -f targets/querystore/pom.xml clean install          # install first: chartsearchai consumes querystore-api
mvn -f targets/chartsearchai/pom.xml -nsu clean verify    # -nsu keeps the local querystore-api from being clobbered
scripts/test-chartsearchai-esm.sh
```

PR state (1.3, 1.4, 2.x):

```sh
gh pr view 68  --repo openmrs/openmrs-module-querystore     --json state,mergeable,mergeStateStatus,statusCheckRollup
gh pr view 157 --repo openmrs/openmrs-module-chartsearchai  --json state,mergeable,mergeStateStatus,statusCheckRollup
gh pr view 23  --repo openmrs/openmrs-esm-chartsearchai     --json state,mergeable,mergeStateStatus,statusCheckRollup
```

Stale PRs (1.6):

```sh
gh pr list --repo openmrs/openmrs-module-chartsearchai --author pmanko --state open
gh pr list --repo openmrs/openmrs-esm-chartsearchai    --author pmanko --state open
```

## 6. Sequencing Rules and Contingencies

1. I1 and I2 before anything on #157. #68 is CLEAN, its upstream is quiet, and it gates the
   rest; nothing is gained by touching #157 first.
2. Resync the backend PR only when there is a reason to touch it: I4, once the querystore-api
   SNAPSHOT publishes, or when work must land on the branch. No calendar-driven resync; a
   DIRTY badge while nobody is reviewing costs nothing.
3. Same-day reply to any new maintainer thread on any of the three PRs while M2 is open.
4. Nothing in this roadmap needs the parity roadmap's `dual_provider_parity_evidence.v1`
   bundle. That bundle remains open there and is not a gate here.
5. Status-hub sync is part of every iteration's exit (§4), not a separate cleanup at the end.
   I7 exists for the surfaces that can only be corrected once the merged state is known.
6. The account-context PR stays on its own branch until M2 closes, then goes upstream as its
   own PR (§8 A2). Harness #148 waits with it: `scripts/openmrs-source-pair-test.sh` requires
   the pin to equal `origin/harness-integration`, so #148 cannot pass its source-pair check
   with #33 on a side branch.

## 7. Iteration Log

| Date (UTC) | Iteration | Heads touched | Result | Evidence |
|---|---|---|---|---|
| 2026-09-14 | baseline | querystore `f2fca727`, chartsearchai `d46f517b`, esm `77f61c8a` | recorded | §2; submodule pins reset to PR heads this day |
| 2026-09-14 | I0 | harness `docs/openmrs-upstream-merge-roadmap` | done | `roadmaps.json` row CLIN-A60; efforts `clinical.dual_provider` and `upstream.older_prs` repointed; hub README row; `render.py --check` 16/16 views match; `status:test` 5/5; `status:build` OK; `verify-docs-consistency.sh` OK |
| 2026-09-14 | I1 | querystore `f2fca727` -> `1b1c995f` (branch `codex/qs-68-review-round-2`, fast-forwarded to `harness-integration`) | done | three red-first tests failed on `f2fca727` (Lucene `truncated=false docs=1`; service `truncated=false`; interpreter `pain knee`), pass on `d675fe9` / `3057478` / `1b1c995`; full reactor API 523 + OMOD 51, 0 failures, 2 skips; #68 CI Java 8/11/17/21 SUCCESS on `1b1c995f`; three thread replies posted, threads left open |

## 8. Amendments

### A1, 2026-09-14: status-hub integration and consolidation sweep

Added before the roadmap PR merged, on user direction that the roadmap must include the meta
work of keeping the existing specs, dashboards and docs consistent. Adds the per-iteration
status-hub exit rule, I0 (register in the hub), I7 (consolidation sweep with the grounded
surface inventory), acceptance criteria 1.8 and 3.6, sequencing rules 5 and 6, and the §2
paragraphs on the status hub and on fork #33.

Open decision recorded here, not made here: whether fork #33 (account-context transport)
lands on `harness-integration` before M2, growing #157 by twelve files, or waits on its own
branch (harness #148 pins its exact commit either way) and goes upstream as its own PR after
M2. The scope guard in §9 says wait; the #148 companion note says land first. Decided in A2.

### A2, 2026-09-14: four owner decisions

1. The account-context PR (#33) is held on its branch until M2 closes; harness #148 waits
   with it. Rule 6 updated.
2. The backend PR (#157) is resynced only when there is a reason to touch it (I4, or new work
   landing on the branch), never on a calendar. Rule 2 replaced; the seven-day contingency is
   withdrawn.
3. The nine stale PRs: audit each against the frontend and backend PRs and the upstream
   inventory, then close the content-confirmed ones with a supersession comment without a
   second approval round. Anything with unique live work stays open and is reported. I3
   updated.
4. On the QueryStore read-API PR, replies cite the fixing commit and test and threads are
   left for the maintainer to resolve. I2 updated; 1.1 stays as written.

## 9. Scope Guard

Until M2 closes, every push to a fork's `harness-integration` is a review fix or a resync. No
new capability lands there. That is how #157 reached 52 commits and 97 files, and it is the one
thing that can push M2 out indefinitely.
