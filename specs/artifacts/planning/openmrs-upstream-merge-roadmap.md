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

## 4. Iterations

Each iteration is validated on its own and logged in §7 before the next starts. An iteration
whose validation fails is "open", never "done".

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
- Depends on: I1 pushed (so replies cite final SHAs).
- Validation: 1.1 returns 0; 1.3 holds; 1.7 for querystore.
- Exit: #68 has no thread whose last comment is not ours.

### I3: Stale PR closure

- Scope: for each of the nine PRs, confirm its delta is either in #157/#23 or deliberately
  dropped (per the disposition record in `openmrs-dual-provider-upstream-inventory.md`), then
  close with a one-line supersession comment naming the successor.
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
- Depends on: 2.1 (the published SNAPSHOT is what makes the plain `build` job resolve). See
  the contingency in §6 if 2.1 is slow.
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
2. I4 waits for 2.1. If #68 shows no maintainer activity for seven days after I2 closes, run
   a conflict-only resync of #157 (keep the paired-build jobs) so it is not sitting DIRTY, and
   accept that it may need repeating.
3. Same-day reply to any new maintainer thread on any of the three PRs while M2 is open.
4. Nothing in this roadmap needs the parity roadmap's `dual_provider_parity_evidence.v1`
   bundle. That bundle remains open there and is not a gate here.

## 7. Iteration Log

| Date (UTC) | Iteration | Heads touched | Result | Evidence |
|---|---|---|---|---|
| 2026-09-14 | baseline | querystore `f2fca727`, chartsearchai `d46f517b`, esm `77f61c8a` | recorded | §2; submodule pins reset to PR heads this day |

## 8. Amendments

None.

## 9. Scope Guard

Until M2 closes, every push to a fork's `harness-integration` is a review fix or a resync. No
new capability lands there. That is how #157 reached 52 commits and 97 files, and it is the one
thing that can push M2 out indefinitely.
