# Catalyst open-pull-request remediation roadmap

**Status:** **Closed historical record.** The queue completed on 2026-08-24 at
harness `main` `49040ee3e16c3785a5beed23657cda61a3243965`. This file preserves the
review plan and evidence requirements; it governs no current work. Current
Catalyst sequencing and acceptance live only in
`specs/catalyst-program-roadmap.md`.

**Evidence baseline:** 2026-08-23

**Scope:** Harness pull requests #49, #50, #51, #52, #54, #55, and #57

## Closeout

- #51, #52, #54, #55, #57, and #50 merged; #49 closed after its unique work
  was salvaged into #54 and #57.
- The final head recorded 1,142 passing tests, 40 skips, clean repository-line
  verification, clean submodule initialization, and green required checks.
- The medication-code correction was verified locally and on the demo host;
  the landing page was republished and checked live.
- All review threads received dispositions, the closeout checklist was posted
  on #57, and branch protection returned to one required approving review.
- Issue #58 was discovered during closeout and remains separate: it predates
  this queue and is not a regression from these pull requests.

The remainder of this document is the plan as executed. Future-tense language
below is retained only to preserve the audit trail.

## 1. Outcome

Finish the current Catalyst-related pull-request queue without losing unique
work, merging invalid pins, accepting misleading contracts, or leaving review
threads unresolved.

Completion means:

- #49 is closed unmerged after its unique content is recoverably moved.
- #51, #54, #57, #52, #55, and #50 are merged in the order defined below.
- Every merged pull request passes its topic-specific acceptance criteria on
  its final head and updated base.
- Every review thread is answered with a fixing commit or an evidence-backed
  disposition and is resolved before merge or closure.
- A final clean-main verification passes after the last merge.

This document coordinates pull-request cleanup only. It does not replace the
Feature 008 plan, change Dashboard Builder requirements, or authorize new P1
product implementation.

## 2. Locked decisions and invariants

1. **Program order approved by the owner on 2026-08-23:** P1 session playbook,
   then P2 conversation mode, then P3 Dashboard workflow. Superset end to end
   remains the chosen Dashboard direction.
2. **Dashboard scope is preserved:** WS1–WS7 remediation is closed; Feature 008
   D1e/M4 remains in progress and is scheduled as P3. P3 inherits the existing
   D1e/M4 meaning, binding visual contract, exit criteria, and 15 active gates.
3. **Canonical component pins:** Catalyst
   `655b796a96e2cb2f96d6a3e21e66aa74ba1b84ca` and Med-Agent Hub
   `8b81320ef428d06422c9ed69a8f411799a5144f9`.
4. **#49 is superseded:** its stale Catalyst pin is discarded. Its valid Hub
   pin moves to #54 and its unique 91-line `spec.md` clarification moves to
   #57.
5. **Carbon dependency:** #57 is rebased only after #54 merges. At the approved
   Catalyst pin, `@carbon/styles` resolves to 1.112.0; no separate Carbon bump
   belongs in #57.
6. **No hidden data mutation:** use the harness stack wrapper. Preserve volumes
   by default. Seeding or reset is announced explicitly before execution.
7. **Owner gate:** automated review and tests advise; the owner makes every
   final merge or close decision.

## 3. Baseline and disposition

| PR | Baseline head | Current finding | Planned disposition |
| --- | --- | --- | --- |
| [#51](https://github.com/pmanko/clinical-ai-validation-harness/pull/51) | `084167c456a4` | Code and CI clean; configured labels do not exist | Repair label precondition, merge |
| [#54](https://github.com/pmanko/clinical-ai-validation-harness/pull/54) | `b59918ed53b5` | Catalyst gitlink is unreachable; CI fails checkout | Rewrite to canonical two-pin change, validate, squash-merge |
| [#49](https://github.com/pmanko/clinical-ai-validation-harness/pull/49) | `6e5392c97833` | Mixed umbrella PR; stale Catalyst pin; two unique useful changes | Salvage, reply to threads, close unmerged |
| [#57](https://github.com/pmanko/clinical-ai-validation-harness/pull/57) | `fd4e104c7f8d` | Durable record is useful; governance/status conflicts and identifiers remain | Rebase, reconcile, redact, merge |
| [#52](https://github.com/pmanko/clinical-ai-validation-harness/pull/52) | `f1949579c931` | Fabricated medication code/system pairs and an unversioned catalog change | Repair with executable semantic coverage, merge |
| [#55](https://github.com/pmanko/clinical-ai-validation-harness/pull/55) | `cba42b07847f` | Media-host direction is sound; publisher and guards have gaps | Repair, merge |
| [#50](https://github.com/pmanko/clinical-ai-validation-harness/pull/50) | `7039a6091f27` | Useful renderer polish; stale media metadata, cleanup/font/duration defects, red coverage | Rebase after #55, repair, merge |

## 4. Required execution order

1. #51 label/configuration correction and merge.
2. #54 canonical Catalyst and Hub repin, runtime validation, and merge.
3. #49 salvage proof and unmerged closure.
4. #57 rebase, governance reconciliation, redaction, and merge.
5. #52 medication-fact repair, semantic/live acceptance, and merge.
6. #55 media-host publishing repair and merge.
7. #50 rebase, renderer/media repair, and merge.
8. Final clean-main verification and queue closeout.

The merge order is serial. Read-only investigation and branch-local repair may
run in parallel, but no pull request crosses a dependency gate early.

## 5. Gate applying to every pull request

A pull request may merge only when all applicable items below pass:

- The final head SHA and its current base SHA are recorded in the pull request.
- The final diff contains only the declared topic and has been reviewed against
  the updated base.
- Required checks are green on that exact head; an earlier green run does not
  count.
- Topic-specific tests run rather than skip because a dependency is absent.
- Each active or substantively valid outdated review thread is answered with
  the fixing commit or a concrete evidence-backed disposition, then resolved.
- Copilot reviews the final head after the last material change and reports no
  unresolved actionable finding.
- A fresh current-head Codex diff review reports no blocker.
- Repository-line verification passes with `--allow-harness-branch` while the
  pull request is open.
- The owner reviews the final diff and explicitly decides merge, close, or
  further repair.

Because there are no active collaborators, `REVIEW_REQUIRED` alone is not a
quality signal. If repository rules require an external approval that cannot be
self-supplied, use an owner/admin override only after the gates above are
recorded; do not weaken branch protection as part of this work.

Each final evidence comment should record:

```text
Head / base:
Declared scope:
Fixing commits:
Automated checks:
Topic-specific acceptance:
Review-thread dispositions:
Residual risk / rollback:
Owner decision:
```

## 6. PR-specific remediation and acceptance

### R1 — #51: explicit submodule tracking and Dependabot

**Required work**

1. Keep all six explicit tracking branches: Catalyst, Hub, and OpenMRS Chatbot
   on `main`; ChartSearchAI, ChartSearchAI ESM, and QueryStore on
   `harness-integration`.
2. Keep the root `gitsubmodule` Dependabot job, weekly cadence, and six-pull-
   request limit.
3. Create the configured `dependencies` and `submodule-repin` repository labels
   before merge (verified 2026-08-23: neither exists; only default labels do).
   If the owner declines repository-label creation, remove the custom
   `labels:` block so Dependabot's valid defaults apply. Do not retain a
   configuration whose labels are silently ignored because they do not exist.

**Acceptance**

- Every `.gitmodules` branch exists on its declared remote.
- The Dependabot YAML parses and contains exactly the intended ecosystem,
  directory, cadence, cap, and label behavior.
- Both configured labels are returned by the GitHub labels API, or the custom
  label block has been removed and default labeling is documented.
- Current-head CI and repository-line verification pass.
- Copilot has no actionable thread on the final head.

**Exit:** owner-approved squash merge. No code-level blocker otherwise exists.

### R2 — #54: canonical Catalyst and Hub pins

**Required work**

1. Rebase on the main branch containing #51.
2. Replace the unreachable Catalyst gitlink with the approved Catalyst SHA and
   add the approved Hub SHA. The diff must contain exactly those two gitlinks.
3. Update the title/body to describe both component ranges and the actual
   validation. Describe the old value only as an unreachable or
   transcription-corrupted gitlink; its creation mechanism is not proven.
4. Collapse the accumulated repin changes into one reviewable commit.

**Acceptance**

- Full-SHA remote lookup succeeds for both targets and each SHA equals its
  approved remote `main` head.
- `git ls-tree` reports the two exact approved SHAs.
- Both initialized submodules are clean and their checked-out heads equal their
  parent gitlinks.
- `scripts/verify-repository-lines.sh --allow-harness-branch` passes.
- With existing volumes, `scripts/catalyst-mvp.sh up` followed by
  `scripts/catalyst-mvp.sh health` passes. If the stack is uninitialized, the
  owner is told that `boot` seeds data before it is run. No reset is part of
  acceptance.
- The isolated UI and Gateway bind at ports `13000` and `18000`, and the health
  evidence reports the exact Catalyst and Hub revisions.
- All CI checks and the final review gate pass.

**Exit:** owner-approved squash merge.

**Rollback:** use a new pull request to restore the last known-good valid pins
while retaining volumes. Never restore the unreachable gitlink.

### R3 — #49: salvage and close as superseded

**Required work**

1. Before intentional #57 edits, reconfirm that `tasks.md`, the styling
   roadmap, token map, and UX follow-through document have no unique #49
   content relative to #57.
2. Move the unique 91-line `spec.md` clarification to #57, reconciling any
   language that could be mistaken for M4 completion.
3. Confirm #54 contains the exact Hub pin. Discard #49's stale Catalyst pin.
4. Reply to #49's three review threads:
   - mixed scope is superseded by #54 and #57;
   - Carbon 1.112.0 becomes true after #54 and the #57 rebase;
   - checkbox capitalization is fixed in #57.
5. Post one close comment mapping every salvaged item to its successor pull
   request and fixing commit.

**Acceptance**

- A file-by-file comparison proves no unsalvaged unique change remains.
- The shared-file equality proof is recorded before #57 intentionally changes
  those files.
- #57 recoverably contains the clarification and #54 recoverably contains the
  Hub pin.
- All three review threads have explicit dispositions.

**Exit:** owner-approved close without merge. Retain the branch for recovery.

### R4 — #57: durable record and program-governance reconciliation

**Required work**

1. Rebase on main after #54 and verify the exact two pins. Confirm the pinned
   Catalyst lockfile resolves Carbon 1.112.0.
2. Incorporate #49's unique clarification.
3. Record the owner decision accurately: the program goals and order were
   approved on 2026-08-23; the six detailed P1 scope/measurement decisions
   remain gated.
4. Include this invariant verbatim:

   > WS1–WS7 remediation is closed; Feature 008 D1e/M4 remains in progress and
   > is scheduled as P3.

5. State that P3 inherits the unchanged D1e/M4 requirements, binding reference,
   and exit criteria. Remove or constrain any "scope at phase start" wording
   that could shrink that contract.
6. Correct "21 tasks remain gating" to 15 active gates:
   `T166`, `T147`, `T168`, `T169`, `T170`, `T171`, `T148`, `T172`, `T173`,
   `T180`, `T181`, `T182`, `T155`, `T156`, and `T157`. Preserve the two
   consolidated historical ceremonies (`T144`, `T149`) as unchecked but do not
   count them as separate active gates.
7. Reconcile every live status source, including:
   - `specs/catalyst-program-roadmap.md`
   - Feature 008 `plan.md`, `tasks.md`, `spec.md`, `quickstart.md`, Dashboard
     delivery goal, and detailed roadmap
   - `README.md` and `AGENTS.md`
   - Catalyst product-roadmap and validation-integration status documents
8. Redact the two concrete workstation addresses and six security-group rule
   identifiers from the unmerged branch. Preserve only the useful security
   posture and lifecycle evidence. Do not copy the identifiers into replacement
   documents or review replies.
9. Correct the internal remediation-roadmap path, use a proper `https://`
   Markdown link for the external artifact, and normalize the six lowercase
   task markers to `[X]`.
10. Update the pull-request title/body so it distinguishes approved program
    order from still-gated P1 detail.

**Acceptance**

- Parent and submodule trees prove the approved pins and Carbon version.
- The tracked remediation record contains no concrete IPv4 `/32` value and no
  `sgr-*` identifier.
- No lowercase `- [x]` marker remains in `tasks.md`.
- An automated task audit reports 17 literal unchecked Phase 10 entries and
  exactly the 15 active gates listed above.
- No live status source still calls Dashboard Builder the program's selected
  next milestone. Historical snapshots, if retained, are labeled historical.
- All live sources agree on P1 → P2 → P3 and on the unchanged open M4 scope.
- The internal path resolves and the external link is clickable.
- Feature 008 cross-document review reports no unresolved critical/high
  inconsistency.
- `git diff --check`, repository-line verification, CI, and the global review
  gate pass.
- All #57 threads, including still-valid outdated comments, are answered and
  resolved.

**Exit:** owner confirms the governance wording and final diff, then
squash-merges.

**Rollback:** before merge, amend the branch. After merge, use a dated
governance amendment for decision changes; never restore redacted identifiers.

### R5 — #52: truthful medication-request fact

**Dependency gate**

#54 is merged and #52 is rebased. The pinned Catalyst includes approved-view
discovery, the wrapper health/provenance gate passes, and raw flat tables are
not promoted into the approved query surface.

**Verified defect baseline**

- `medication_flat` contains 477 coding rows for 359 Medication resources.
- Independent `MAX(code)` and `MAX(system)` fabricate 59 source-impossible
  pairs, affecting 5,441 of 43,412 requests.
- The current view still has one row per request, zero blank names in this data,
  and the independent women/non-`doNotPerform` truth is 28,866.
- The approved catalog surface changes while retaining catalog identity v3;
  that is a separate merge blocker.

**Red-first semantic coverage**

Extend `tests/test_hiv_fact_view_semantics.py` before changing SQL. A real
scratch PostgreSQL test must cover:

- referenced Medication with local, CIEL, and SNOMED codings;
- request and Medication coding cross-products;
- direct `medicationCodeableConcept` with multiple systems;
- request-display, direct-display, Medication text, and Medication coding-
  display precedence;
- blank/missing names;
- `doNotPerform` true, false, and null;
- unresolved patient exclusion;
- exact per-system preservation, one row per eligible request, and zero
  fabricated combinations.

The required CI job must provide PostgreSQL. A skipped semantic test is a
failure, not acceptance.

**SQL and catalog repair**

1. Remove the generic `medication_code` and `medication_code_system` pair.
2. Pivot both FHIR medication arms into four explicit columns:
   `medication_code_openmrs`, `medication_code_ciel`,
   `medication_code_snomed`, and `medication_code_who_anc`.
3. Use system-filtered aggregation, with direct request coding first and the
   referenced Medication as deterministic fallback.
4. Define name precedence as request reference display, direct coding display,
   referenced Medication text, then referenced coding display. Treat blank
   strings as absent.
5. Preserve `BOOL_OR(COALESCE(doNotPerform, false))`.
6. Fail ingestion if one resource has multiple codes for the same system or if
   an unexpected non-null system would be discarded.
7. Advance the catalog from `openmrs-hiv-catalog-v3` to v4. Keep the new view at
   view version 1.
8. Mark `medication_name` nullable, mark `do_not_perform` non-null, update SQL
   comments/overlay, and regenerate the catalog. A second regeneration must
   produce no diff.

**Database acceptance**

- 43,412 rows and 43,412 distinct request IDs.
- Zero source-impossible emitted codes, same-system multiplicity violations,
  or unexpected systems.
- Current data still has zero blank names while the contract truthfully permits
  null.
- Women with `do_not_perform=false` equals 28,866 and matches an independent
  raw-table distinct-request calculation.
- Grouping produces 30 medication types summing to 28,866, including the
  established leading counts: Lamivudine 6,600; Stavudine 6,516; Nevirapine
  5,928.

**Gateway acceptance**

- The gateway reports catalog v4 and the four system-specific columns.
- The curated fact is approved; raw medication-request and patient tables are
  absent from the approved surface.
- A fresh request for medication requests prescribed to women by medication
  type uses only the curated fact, returns 30 groups totaling 28,866, and emits
  no validation warning.
- Wrapper health and provenance report the final #52 head and #54 pins.

**Review/exit**

- All three #52 threads are fixed, answered, and resolved.
- The catalog-version blocker and non-skipping PostgreSQL coverage are shown in
  the evidence comment.
- CI, fresh reviews, and owner final diff review pass before squash merge.

**Rollback:** restore the previous overlay/catalog through a new change so the
view is no longer approved, revert #52, and reapply the prior view definition if
needed. Preserve source data and volumes; no reset/reseed is implicit.

### R6 — #55: move demo recordings out of Git safely

**Required work**

1. Make `landing/index.html` the publication source of truth. Extract every
   remote video and poster URL actually referenced by the page; remove the fixed
   filename verification list.
2. Verify those remote assets before `rsync` or any deployment mutation. A
   missing new asset must leave the currently published page unchanged.
3. Map `/media/<name>` correctly when testing for stale local aliases under
   `landing/media/<name>`.
4. Reject tracked video symlinks by Git-index pathname. Distinguish gitlinks,
   but do not blanket-ignore mode `120000`.
5. Narrow the policy, module documentation, and pull-request claim to what this
   change actually governs: tracked videos of any size and the explicitly
   enumerated oversized media formats. Do not claim detection of every binary
   format. Test each governed suffix and compound-extension rule.
6. Clarify that recordings left repository/landing sync but still require the
   separate Catalyst media-host deployment.
7. Update the recording guide to name both consumers: the landing page and the
   Catalyst demos canvas.

**Acceptance**

- Negative tests prove a missing page-referenced video or poster fails before
  deployment mutation.
- A regular tracked MP4, a tracked MP4 symlink, and an oversized governed media
  asset each fail with the offending path.
- Hosted/local path mapping covers `/media/<name>`.
- `uv run pytest tests/test_landing_site.py tests/test_no_committed_media.py`
  and `shellcheck scripts/publish-landing.sh` pass, followed by full CI.
- Every page-referenced remote asset returns 200, the expected media type, and
  nonzero content length.
- Four current review threads plus the three valid suppressed findings are
  answered with fixing commits or explicit dispositions and resolved.

**Exit:** fresh reviews and owner final diff review, then squash merge.

**Rollback:** revert the landing/publisher change while leaving remote assets
intact. Repository history is not rewritten in this remediation.

### R7 — #50: deterministic renderer polish and current media metadata

**Dependency gate**

#55 is merged. Rebase/retarget #50 onto the resulting main and prove it does not
reintroduce committed media or fixed publisher filenames.

**Required work**

1. Correct both canvas entries to the dated poster filenames and measured
   metadata:
   - OpenELIS: about 53 seconds; MP4 byte count 2,214,189.
   - OpenMRS: about 52 seconds; MP4 byte count 1,692,521.
2. Add coverage for the footer path so diff coverage meets policy.
3. Make temporary-file ownership explicit: tests pass `tmp_path`; normal CLI
   execution creates one managed temporary directory and removes it after
   `ffmpeg` completes or fails.
4. Remove the unconditional `Helvetica Neue` default. Either use an explicitly
   configured and validated font in the declared render environment or omit the
   font option and narrow the cross-platform determinism claim accordingly.
5. Reject non-finite/non-positive card duration before building the graph and
   ensure fade durations/start times can never be zero or negative.
6. Inherit #55's page-derived asset verification and consumer-consistency tests.

**Acceptance**

- Unit tests cover footer rendering, explicit/default font behavior, invalid
  card durations, fade generation, and temporary-directory cleanup on success
  and failure.
- `uv run pytest tests/test_render_demo_video.py tests/test_landing_site.py
  tests/test_no_committed_media.py` passes.
- The drawtext-enabled `ffmpeg` smoke test executes rather than skips in the
  declared acceptance environment and produces a playable MP4 and poster with
  the expected duration.
- Full CI passes and diff coverage is at least 90%; the current 75% is not
  acceptable.
- Both dated videos and posters return 200 with correct media types; landing and
  canvas agree on filenames, posters, durations, and size labels; both clips
  play in a browser.
- All four current review threads are fixed, answered, and resolved.

**Exit:** fresh reviews and owner final diff review, then squash merge.

**Rollback:** revert the renderer/metadata merge without changing hosted media
or the #55 no-binary policy.

## 7. Final clean-main acceptance

After #50 merges:

- Update local main and initialize every pinned target at its recorded gitlink.
- Run `scripts/verify-repository-lines.sh` without the pull-request allowance.
- Run the complete harness CI suite on main.
- Run the Catalyst wrapper health/provenance gate without reseeding and confirm
  the approved Catalyst/Hub pins, UI port `13000`, and Gateway port `18000`.
- Re-run the #52 database and gateway reconciliation checks.
- Re-run the landing/media checks and browser playback smoke.
- Confirm #49 is closed unmerged and every other pull request in this roadmap is
  merged.
- Confirm there is no unresolved review thread in the seven-pull-request set.
- Confirm no remaining open Catalyst-related pull request lacks a recorded
  disposition.
- Record the final main SHA and a compact result table in the roadmap closeout
  comment.

P1 **implementation pull requests** may begin only after this cleanup closes
and the owner resolves the six detailed scope/measurement decisions. The
approved program order alone is not authorization to start P1 implementation.
The P1 planning discussion itself and read-only preparation (for example,
curating the CE0 scenario corpus from recorded generation evidence) may run in
parallel with this cleanup — they touch no pull request in this queue.

## 8. Owner checkpoints

- **A — Roadmap approval:** approve or amend this document.
- **B — #51 merge:** approve after the label precondition is fixed.
- **C — #54 merge:** approve the exact two-pin diff and runtime evidence.
- **D — #49 close:** approve the salvage map and closure.
- **E — #57 merge:** approve the governance wording, redaction proof, and
  unchanged M4 contract.
- **F — #52 merge:** approve the catalog v4 contract and live data evidence.
- **G — #55 merge:** approve the preflight and repository guard behavior.
- **H — #50 merge:** approve the renderer output and media consistency.
- **I — Closeout:** accept the final clean-main evidence.
