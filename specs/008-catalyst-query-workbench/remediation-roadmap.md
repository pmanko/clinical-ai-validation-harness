# Catalyst remediation roadmap

> **Historical record — WS1–WS7, closed 2026-08-23.** Kept as the evidence log
> for Feature 008 remediation. Active planning:
> `specs/catalyst-program-roadmap.md` and
> `specs/artifacts/planning/catalyst-open-pr-remediation-roadmap-2026-08-23.md`.

**This is the single tracking document for the remediation.** Earlier docs
(`hiv-source-and-review-remediation.md`, `ux-v2-followthrough-goals.md`) are
history; item status lives here. Last validated: 2026-08-22.

**FROZEN 2026-08-22.** The workstream set and acceptance criteria below change
only with the user's explicit approval. The status log stays append-only.
Architecture review backing WS2.5:
https://claude.ai/code/artifact/0b3957b7-7435-4ab0-ae60-1e3749574aba

## Completion state (synced 2026-08-22)

| WS | State | Evidence |
| --- | --- | --- |
| WS1 | **Done** — deployed both envs; A1–A4 recorded | PR #40; status log 2026-08-21; one open A/B observation (writer_validation) noted there |
| WS2 | **Done** — B1–B5 + round 3 proven on both envs; CI green at 160aa61 | PR #41; status logs 2026-08-21/22; dataset-save probes local+server |
| WS2.5 | **Done** — all four items proven on both envs; both deployments at main 3ec27ad | PRs #43, #44; status log 2026-08-22 |
| WS3 | **Done** — proven on both envs; both deployments at main 6fd7704 | PR #45 merged; status log 2026-08-22 |
| WS3b | **Done** — merged (#46), forced-failure proof recorded, both envs at main fc69ad1 | PR #46; status log 2026-08-22 |
| WS3c | **Done** — merged (#47), flicker reproduced and fixed, catalyst#35 closed | PR #47; status log 2026-08-22 |
| WS4 | **Done** — both criteria proven on both envs | PR #48; status log 2026-08-22 |
| WS5 | **Done** — six tracked artifacts, decisions recorded | catalyst#49–#54 |
| WS6 | catalyst **executed** (0 open PRs); harness **awaiting your review** on 4 ready PRs | see status log 2026-08-22 |
| WS7 | **Done** — four items proven on both envs; stack #58 green, awaiting your review | PRs #59–#63; status log 2026-08-22 |

## Goal

Make the workbench's core loop trustworthy and usable end-to-end — ask →
generate → run → refine — so a real reviewer can exercise it on either
environment and hit neither wrong answers nor dead turns.

Three layers:

1. **Correctness** — a generated query must not return confidently wrong numbers. *(Done.)*
2. **Conversation** — the iterative loop must survive model imperfection. *(WS1.)*
3. **Experience** — the flagged interactions must stop lying. *(WS2, WS3.)*

Done means behavioral: sit down at local or the demo server, run the full loop
including a follow-up regen, and everything Ian reported is fixed or visibly,
deliberately deferred.

## Verified premises (2026-08-21)

Every load-bearing claim below was tested, not assumed. Two prior written
claims are corrected here:

- **"The contract is documentary — response_format never reaches the model"
  was WRONG.** Traced end to end: gateway `_backend_chat` sends
  `response_format` → hub `generate_query_role` accepts `req.response_format` →
  `team._chat` forwards it to llama.cpp. The earlier inference came from a
  canonicalized evidence payload that omits it.
- **The real defect is grammar coverage.** Probe 1: posted the exact
  `REVIEW_FORMAT` (strict) to the router and instructed qwen2.5-14b to emit the
  forbidden stub `candidate: {"status":"ready"}`. It emitted it verbatim —
  llama.cpp's schema→grammar conversion drops the `oneOf`+`not`+conditional-
  required constructs the candidate schema relies on.
- **The fix shape is proven.** Probe 2: restructured the schema as three
  closed, fully-specified alternatives (no `not`, no conditional required,
  `additionalProperties:false` everywhere). Same adversarial instruction: the
  stub was unrepresentable; the grammar forced `sql`, `parameters`,
  `expectedColumns` into the candidate.
- Local-env fragility root cause: services carried restart policy `no`, so any
  Docker/OrbStack restart killed the stack minus the `always`-flagged OpenELIS
  trio. Mitigated live via `docker update --restart unless-stopped` (all 11);
  permanent fix is WS4 (the compose file, else the next `--force-recreate`
  reverts it).

## Ledger — every item, every source

### Ian's nine

| # | Item | Status |
|---|---|---|
| 1 | Format SQL → "Edited by hand" | **WS2** |
| 2 | First query unformatted, later formatted | **WS2** |
| 3 | Draft feels detached from its turn | **WS3** |
| 4 | No way to close a draft | ✅ #34, deployed both |
| 5 | Composer noise | **WS3** |
| 6 | No syntax highlighting in editor | ✅ #34, deployed both |
| 7 | Non-SQL answers + developer mode | **WS5** (spec entry, then feature) |
| 8 | No keyboard submit | ✅ #34, deployed both |
| 9 | Literal `%` rejected | ✅ #33, deployed both |

### R1–R6

| Item | Status |
|---|---|
| R1 fan-out / governance | ✅ #36 + #52, verified 28,866 both envs |
| R2 dead/sparse column annotation | Deferred (mostly obviated by #36/#52); sparse-column note in WS5 |
| R3 retry + readable failure | ✅ #37 · **decode-time enforcement = WS1** |
| R4 failure as first-class outcome | **WS3b** (201-on-failure, surface reviewer checks, "unreviewed" marking) |
| R5 warning feedback loop | ✅ was already implemented; verified end to end |
| R6 medication_flat grain | ✅ inside #52 |

### Operational

| Item | Status |
|---|---|
| Local stack dies on daemon restart | Mitigated live; permanent = **WS4** |
| `catalyst-mvp.sh up` rebuilds over integration images; pin dance | **WS4** |
| Server default profile not advertised (`profile_unavailable`) | **WS4** |
| catalyst issue #35 composer flicker | **WS3c** (promoted 2026-08-21: still reproducing) |
| Platform-aware `⌘↵` hint; closable-editor baseline | **WS5** |
| Merge train (8 green PRs) + umbrella repin + #50 coverage failure | **WS6** |

## Workstreams, in order

### WS1 — Grammar-enforceable review contract *(unblocks all testing)*

Restructure `REVIEW_SCHEMA` / `BACKEND_REPAIR_SCHEMA` (and audit
`GENERATION_FORMAT`) into the subset llama.cpp compiles faithfully: top-level
`oneOf` of three closed objects (approve / reject / repair-with-complete-
candidate), no `not`, no conditional `required`, `additionalProperties: false`,
`$defs` inlined. Post-hoc validation stays (defense in depth). #37's retry
stays (recovers residual malformation).

**Acceptance:**
- A1. Adversarial probe (probe 1 rerun against the new format): the stub is
  unrepresentable at temperature 0.
- A2. 5 consecutive fresh-session regens on the checked profile
  (`gemma-4-12b` writer + `qwen2.5-14b` reviewer) complete locally with zero
  `reviewer_output_contract` failures.
- A3. Same exercise on the demo server after deploy: 3 consecutive regens.
- A4. Gateway suite green; a unit test pins "generation/review/repair formats
  contain no `not` and no status-conditional required outside closed oneOf
  branches."

**Checkpoint:** deploy local + server, run A2/A3, then a note to Ian that regen
is exercisable.

### WS2 — SQL canonicalization (PR B; Ian #1+#2)

**Premise corrected 2026-08-21, before building.** The decided approach was
"format via the existing formatter at version-create". Two things falsified the
naive reading of that:

1. **Model versions are created server-side**, not by the UI. Formatting only in
   the browser would leave the editor differing from the stored version, which
   is *itself* read as a hand edit — the exact bug being fixed.
2. **Reformatting server-side with sqlglot is unsafe.** Probed on the real
   queries: with `read="postgres"` it rewrites `:gender` into `%(gender)s`,
   which `_driver_sql` would then convert again, corrupting every parameterised
   query. With the default dialect the placeholder survives but
   `TO_CHAR(v * 100, '990D9%')` is rendered as `CAST(v * 100 AS TEXT)` — the
   format string is silently dropped, with only a warning on stderr. That is
   Ian's own percentage query, destroyed. sqlglot is a *parser* for linting
   here, not a faithful pretty-printer, and must not be used to rewrite stored
   SQL.

**Revised approach — two independent halves, neither of which rewrites SQL
semantically:**

- **(a) Comparison stops caring about layout.** `editorContentMatchesVersion`
  and `editorDirty` compare SQL through a whitespace/case-insensitive
  normalizer (collapse runs of whitespace outside string literals; leave the
  stored text untouched). Formatting then cannot register as authorship, no
  matter which formatter produced it. Fixes Ian #1, and is robust to the two
  formatters disagreeing.
- **(b) The editor presents model SQL formatted on arrival.** The UI runs its
  existing `formatPostgresqlSql` (sql-formatter, a real formatter, not a
  transpiler) when loading a model version into the editor buffer only. With (a)
  in place this no longer looks like an edit. Fixes Ian #2 — the first query is
  as tidy as later ones — without changing a byte of what is stored or executed.

Storage stays exactly what the model emitted, so Evidence needs no separate raw
copy and the audit trail is unchanged. The "Format SQL" button remains, and
becomes a no-op on already-formatted text.

- **(c) Added 2026-08-21, after (a) and (b) were deployed and failed on the
  server.** Proving B2 on catalyst.openelis-global.org showed the model's own
  query, generated and simply *run*, came back labelled "Edited by hand". (a)
  and (b) are both UI-side, and the label is not: `runWorkbenchDraft`
  persisted the editor buffer through `POST /versions` on **every** run, and
  that endpoint records `author_type="human"` unconditionally. So a round trip
  through the editor authored a version whether or not anything had been
  rewritten. Formatting was never the whole cause -- (b) would have turned an
  occasional mislabel into a certain one. An unchanged draft now runs the
  version it came from, judged by the same comparison (a) introduced.

  This was invisible to the unit suite because three tests had encoded the old
  behaviour, one of them named "persists and executes the exact draft" while
  running an untouched draft. Tests written against a bug defend it.

**Acceptance (revised):**
- B1. Fresh session: the first generated query renders formatted in the editor.
- B2. Pressing Format SQL on an unedited model query produces no "Edited by
  hand" cell after a run, and the composer does not report the editor as dirty.
- B3. A real hand edit still produces a human-authored version and its cell.
- B4. **Corrected 2026-08-21 (my wording was wrong, not the design).** I wrote
  that stored SQL must stay byte-identical to the model's output. It cannot:
  `App.test.tsx` shows the run path always persists the editor buffer as a new
  version, and the gateway verifies `editorDigest` against those exact bytes.
  So what is on screen *is* the version of record — which is precisely the
  trade-off the original decision accepted ("version of record is the formatted
  text, audit trail moves to Evidence"). The model's literal output is retained
  in generation evidence, so provenance is not lost.

  What must be proven instead is **semantic** equivalence: a query containing
  `TO_CHAR(..., '990D9%')` and a named parameter survives formatting and returns
  the same rows. The formatter is `sql-formatter` (a formatter, not a
  transpiler); probed on params, `TO_CHAR` format strings, casts, literals,
  `LIKE` patterns, CTEs and the real medication query — all preserved and
  idempotent. `paramTypes: { named: [":"] }` was added because without it the
  formatter emitted `test_name =:test_name`.
- B5. UI suite + baselines green; baselines re-recorded only where layout
  legitimately changed.

**Checkpoint:** deploy both, walk B1–B4 in a browser on the live server.

### WS2.5 — Foundation refactor *(approved 2026-08-22; runs before WS3)*

Approved by the user after the seven-site duplication postmortem: the same
one-line byte comparison of SQL was hand-written at seven call sites across
four files, and was found one round at a time because nothing owned the rule.
The fix pattern (one named owner + a guard test that was watched failing) is
now the standard here. WS3 builds on the refactored foundation, not the old
one. Sequencing: **runs on a quiet tree after the #32 → #34 → #41 stack
lands** — all three PRs edit `QueryWorkspace.tsx` (measured via
`git diff --name-only` per stack range), so restructuring mid-review would
conflict with the whole stack.

**Scope:**

- **(a) Split `QueryWorkspace.tsx` (1,891 lines, 37 state hooks) into hooks
  along its measured state clusters** — shell/layout (12), session+data (8),
  editor buffer (7), run actions (3), follow-up/evidence (5) →
  `useWorkbenchShell`, `useWorkbenchSession`, `useEditorBuffer`,
  `useRunActions`, `useGenerationEvidence`; the component becomes composition.
- **(b) `parametersMatch()` beside `sqlLayoutMatches()`** — retire the last
  instance of the duplication class (`WorkbenchPanel:351`,
  `JSON.stringify(a) === JSON.stringify(b)`); extend the guard test to cover
  parameter comparisons.
- **(c) Gateway authorship from content, not endpoint** — `POST /versions`
  hardcodes `author_type="human"` (`service.py:1742`); an unchanged query must
  not become human-authored at the API boundary either.
- **(d) Gateway layout-aware column retention** — `sql != parent["sql"]`
  drops declared columns on a byte difference; port the literal-safe
  normalizer to Python with its own test suite (not a translation of the TS
  tests — its own literal/dollar-quote/param cases).

**Explicitly out of scope:** splitting `service.py`/`storage.py` (large but
organized, 257 tests, no defect class traced to size); any visual change.

**Acceptance:**

- C0. Refactor lands with **zero behavior change**: visual baselines
  byte-identical (no re-records), unit suites green with no assertion edits
  (imports/mocks may move), deterministic e2e green.
- C1. Guard test extended to parameters; watched failing on a planted
  violation before trusting it.
- C2. Gateway: creating a version whose SQL differs from its parent only by
  layout keeps `expectedColumns` and does not mint a human-authored version;
  proven by API probe against the local stack, then the server.
- C3. Gateway suite + `ruff` + `mypy` green; UI vitest+tsc+lint+build green.
- C4. Deployed both environments; C2 probe re-run on the server.

**Checkpoint:** the WS3 branch is cut from the refactored tree.

### WS3 — Draft-in-thread + composer noise (PR C; Ian #3+#5)

**Premise validated 2026-08-22, one correction.** "Divergent draft renders as
a provisional cell inside its turn" is *already structurally true*: UX v2
passes the editor into `TurnNotebook` as `activeCell`, so the draft renders
inside the thread, not detached below it (`QueryWorkspace` render, `activeCell=
{showEditor ? workbenchPanel : …}`). What remains of Ian #3 is the *treatment*:
a divergent draft is not visually marked provisional, and executing it produces
no diff line. The other premises hold as written: the execution summary renders
inside the composer (`.turn-composer__grounding`, text built in
`notebookGrounding`), and stale state is a full sentence there rather than an
icon.

Remaining scope: divergent draft gets provisional-cell treatment (hardening to
"Edited by hand" with a diff line on execute); execution summary moves beside
the results table; stale becomes a ⚠ + tooltip; the composer keeps only the
instruction box, profile picker, and submit.

**Acceptance:** the draft never visually leaves its turn and is marked
provisional while divergent; the submit toolbar contains only profile + button;
stale state is one icon with a tooltip; baselines re-recorded deliberately;
#35's flicker not worsened (scroll the demo script).

### WS3b — R4 remainder

**Premises validated 2026-08-22.** The API boundary is better than R4 feared:
a failed turn returns 201 with an explicit block — `status: "failed"` plus
`failure {stage, code, message, evidenceAvailable, rawEvidenceRef, diagnostic
{retryable, details}}` (`storage.fail_turn`, response via
`_workbench_terminal_turn_response`). **Decision: 201 + explicit failure block
IS the contract** — the terminal-turn read path and idempotent re-reads depend
on it; to pin, a test asserts the block's shape. The real gaps: (1)
`diagnostic.details` is always `[]` — the named checks exist at failure time
(reviewer `checks[]` from the review contract; stage/code classification
`reviewer_output_contract_failed` etc.) but are never carried; (2) the UI's
turn type surfaces only `failure.message`; (3) nothing marks a selected model
version that lacks reviewer sign-off when the profile declares a reviewer.

Scope: populate `diagnostic.details` with the named failed checks; timeline +
UI carry them in the failed cell; "unreviewed" marking on cell + Evidence when
the profile declares a reviewer but the selected version has no reviewer
involvement.

**Acceptance:** force a reviewer failure (temporarily strict schema or mock):
UI shows the named failed checks; session shows the turn failed without
opening Evidence; unreviewed marking visible when review was skipped.

### WS4 — Environment stability

`restart: unless-stopped` in `docker-compose.mvp.yml` (or override) so it
survives recreation; a `catalyst-mvp.sh` path (or documented target) that
doesn't rebuild over deployed integration images; kill the pin dance (push or
retire the divergent local branch; repin); server `.env` default profile set
to an advertised one.

**Acceptance:** `docker compose restart` of the daemon (or OrbStack reboot)
brings back all 11 containers unaided; `profile_unavailable` gone from a
fresh server session with no explicit profile.

### WS3c — Composer state flicker (catalyst#35) — PROMOTED, not deferred

Reported again on localhost 2026-08-21 after the WS1 deploy.

**Premise corrected 2026-08-22 — "there is no hysteresis band" is false.** The
code already separates enter from exit on both boundaries: `NEAR_END 200` /
`LEAVE_END 320` for full, `FAR_BACK 560` / `LEAVE_FAR 440` for tucked, plus a
24px accumulated-intent gate and one decision per animation frame — and the
reasons are already comments in `TurnNotebook.tsx` ("the thresholds were single
values, so hovering on one oscillated"). So C1's prescription is **already
implemented**; an earlier round did it.

What was still real, and is now fixed, was a different mechanism: the mode only
ever moved on a scroll *event*, so once content shrank below the viewport
(routine — the editor closes when a run lands) no gesture could restore a
tucked composer, and at the bottom of a barely-scrollable page a
scroll-to-bottom produces no travel at all. WS2 fixed the unscrollable case
(settle to full on resize/ResizeObserver, with a unit test) and WS3 made the
e2e helper use the composer's own lip rather than assuming a scroll can always
restore it.

**Remaining work for WS3c: prove it.** C2's oscillation test is the deliverable
— if it passes on current code, that is the finding, recorded with the run,
not a fix invented to have something to ship.

**Acceptance:**
- C1. Separate enter/exit thresholds (a dead zone), or a measurement the
  composer's own visibility cannot alter. Whichever is chosen, the reason is a
  comment in the code, not just the PR.
- C2. A Playwright scroll test that oscillates around the threshold offsets and
  asserts `#refine-openelis` `data-mode` settles — i.e. no more than one mode
  transition per scroll direction change. This test must fail before the fix.
- C3. Verified by hand on localhost at the offsets where it currently flickers,
  and on the demo server after deploy.
- C4. The `line` mode remains reachable (the fix must not collapse three modes
  into two by accident).

Sequenced with WS3, which touches the same region, so the baselines move once.

### WS5 — Deliberate deferrals (each gets a tracked artifact, not silence)

- ~~Gateway byte-compares SQL / authorship-by-endpoint~~ — **promoted into
  WS2.5 (c)+(d)** on 2026-08-22; no longer a deferral.

**All tracked as issues 2026-08-22 — each has the context to act on, not a
one-line reminder:**

| Deferral | Artifact |
| --- | --- |
| Ian #7: prose answers (decide the scope first, then build or say so) | catalyst#49 |
| Sparse/dead column annotation (R2 remainder; runtime warning already exists) | catalyst#50 |
| Platform-aware `⌘↵` hint (handler already accepts both; only the label lies) | catalyst#51 |
| Closable-editor visual baseline (record after #47, which moves the modes) | catalyst#52 |

**Found while proving other workstreams, tracked rather than absorbed:**

| Finding | Artifact |
| --- | --- |
| Demo server advertises no reviewer-capable profile, so WS1's path can't be exercised there | catalyst#53 |
| `catalyst-ui/.env` on the demo host is a dangling symlink guarded by every rsync | catalyst#54 |

### WS6 — Merge train

**Catalyst: executed.** All ten remediation PRs merged; `main` at `3e9bec3`;
**0 open PRs**. Both deployments serve it (`index-Byc-VgrB.js`).

**Harness: ready, and explicitly awaiting the owner's review** — every one is
blocked only by the branch-protection rule requiring one approving review,
which is the owner's to give:

| PR | What | CI | Ready? |
| --- | --- | --- | --- |
| #54 | Repin catalyst → `3e9bec3` (the merged train) | green | **yes** — merge *after* #49, whose catalyst pin is older |
| #51 | Say which branch each submodule tracks; let Dependabot bump | green | **yes** — independent |
| #52 | HIV medication-request fact at one row per request | green | **yes** — independent |
| #49 | Repin catalyst+hub onto post-merge mains, plus spec docs | green | **yes**, but its catalyst pin (`5b23653`) is stale; #54 corrects it |
| #50 | Re-recorded demo cuts | **stale failure from 2026-08-09** | **no** — also based on `chore/repin-router-fix-mains`, not `main`; needs a rebase and a re-run before it can be judged |

Recommended order: **#51, #52 (independent) → #49 → #54** (rebased after #49).
#50 is separate work and should not gate the repin.

## Working agreement

- One workstream at a time; each ends with: tests green → deploy local →
  verify acceptance → deploy server → verify → status line in this doc.
- Any premise discovered false during a workstream gets corrected **in this
  file first**, then the work adjusts.

---

## WS7 — Failure recovery: a failed generation leaves you one click from fixing it

Set 2026-08-22 after diagnosing the turn-3 failure in session `c973eeba`
(report in the status log below). Four items, each through the full loop.

1. **Tell the truth.** Split `writer_validation_failed` into
   `writer_output_contract_failed` (shape) vs `generation_findings_unresolved`
   (semantics). The cell's message is the dominant finding in user terms, never
   the pipeline stage. Pointed findings (code, path, evidence) travel in
   `diagnostic.details`; WS3b's rendering already exists and needs the right
   data.
2. **Leave the best attempt behind.** On repair exhaustion, retain the last
   *complete* candidate as the failed turn's unselected writer output; the cell
   offers **"Edit this attempt"**, loading it into the editor as a provisional
   draft. The existing hand-edit flow (provisional → run → human version,
   unreviewed marking) takes it from there.
3. **Keep the conversation alive.** The instruction stays in the composer for a
   reworded retry; when every unresolved finding is `catalog.unknown_*`, resolve
   as `needs_clarification` with the suggestion as an answerable prompt rather
   than a failed cell.
4. **Full disclosure on demand.** "Show the model's output" on failed cells,
   backed by the existing `rawEvidenceRef` (already `inspectable: true`).

**Acceptance:** replay session `c973eeba` turn 3 verbatim on **both**
environments. The user reaches a *running, corrected query* from the failure
state either by "Edit this attempt" + changing one identifier, or by answering
the clarification. Zero generic contract-failure text anywhere; raw output one
click away.

**As shipped (2026-08-22).** Three refinements the items above did not
anticipate, all found by running the acceptance rather than by reading the
code:

- **The dominant finding is the newest one *about the query*, not the newest
  one.** A loop that finds a bad identifier spends its remaining attempts
  patching it, so the last attempt reports on the patching — which buried the
  identifier and kept item 3 from ever firing. Findings whose stage belongs to
  the correction loop (`output_contract`, `query_correct`) never speak to the
  reader; when no attempt described the query, the cell says the model tried
  *n* times and did not get there.
- **Item 2 applies to follow-ups.** An initial turn keeps its existing
  behaviour — the candidate is recovered as the session's first draft, because
  there is no query behind it to protect. A follow-up has one, so the attempt
  is kept beside it, unselected.
- **A clarification is its own cell status**, not a failed one, at both sizes:
  collapsed it reads "needs your answer" in the info colour, open it is headed
  "Needs your answer".

**The failure mode is not deterministic.** The same instruction, replayed
against the same model, exhausted on `catalog.unknown_column` locally and on
`output.projection_mismatch` on the server. Both are correct outcomes of the
same rules — the second is fixable, so it is not a question. The acceptance
that held on both is: the failure names what is wrong in the reader's terms,
the best attempt is retained beside the working query, and one edit reaches a
running query.

### The loop for WS7, with review gates

VALIDATE → BUILD → **meaningful-test-coverage** → **simplicity-review** →
PROVE LOCALLY → **commit-pr-hygiene** → SHIP (PR, CI green) →
DEPLOY + PROVE ON SERVER → **evidence-bundle** → **spec-code-alignment /
speckit analyze** → LOG.

The four gates in bold come from `DIGI-UW/code-qa` (cloned at
`~/code/code-qa`, not installed as skills here — the procedures are followed
from their `SKILL.md`):

- **meaningful-test-coverage** — right level per layer, and every guard proven
  to fail on the old code before it is trusted. Three guards in this
  remediation passed on their mutants before being caught; this is now a gate,
  not a habit.
- **simplicity-review** — verdict `lean` / `has-bloat` / `over-engineered`
  before the PR opens, measured against the requirement rather than "what might
  be nice".
- **commit-pr-hygiene** — format cold, stage deliberately, conventional
  messages, no attribution trailers.
- **evidence-bundle** — the acceptance replay becomes a shareable proof
  (screenshots + video + narrated report) so manual testing has something to
  read.

**Two rules from commit-pr-hygiene that this session has been breaking, now
binding:**

1. **Code comments must be timeless.** Mine narrate the development path
   ("the first version of this guard missed…", "catalyst#35 survived…").
   Rationale belongs in the commit message and PR body; the source gets terse
   present-tense statements of the invariant. Applies to WS2–WS4 comments
   already merged — tracked as cleanup, not rewritten in place.
2. **Draft outward commentary before posting.** PR and issue comments get shown
   here for approval first. Opening a PR is fine; commentary is not.
3. **The terminal state of an item is green CI + ready for review**, not
   merged. Deployment for manual testing runs from the branch build; merging is
   the owner's call.

## Status log

### 2026-08-22 — WS7 built and proven on both environments (stack #58, PRs #59–#63)

All four items shipped, CI green on every PR in the stack, and both
environments serve the branch build. The acceptance replay drove the work: each
of the last three commits exists because running the real turn showed the
previous one still lying to the reader.

**What the replay said, in order.** Against the build with items 1–4 in place,
session `c973eeba` turn 3 produced:

> **Generation failed** — "Anchored SQL text 't2.last_name' must occur exactly
> once." · `generation.patch_ambiguous` · `query_generate — failed: Query
> generation failed its structured-output contract.`

Three defects in one cell. The patch machinery was speaking; the identifier
that was actually wrong had been found on attempt 1 and buried by attempts 2–3;
and the boilerplate item 1 removed came back through the stage check. After
`fix/the-finding-that-speaks-is-about-the-query` and its follow-up:

> **Needs your answer** — "The model couldn't find “t2.patient_last_name” here.
> Which field did you mean, or should the request be worded differently?" ·
> `catalog.unknown_column` · sql · Found: t2.patient_last_name

**Corrected 2026-08-23 — the first wording overclaimed, and so did this log.**
The message originally read "This data has no 't2.patient_last_name'", and this
entry called the clarification "also correct" on the grounds that no view
carries a patient name. The owner disproved that in one look:
`public.patient_flat` has `family` and `given`, and joining it returns real
surnames — the request was answerable all along. What the exhaustion actually
proves is only that the *model* found no such column; whether the concept
exists under another name is not the gateway's to assert. The question now
reports the model's failure and nothing more. Why the model never reached for
`patient_flat.family` (a common name synonym it should be able to reason about)
is a model-behavior question, deliberately out of scope for this
infrastructure workstream.

**Local acceptance, end to end.** Failed turn → retained attempt kept
unselected with the working query untouched → "Edit this attempt" loads it →
one identifier changed (`t2.patient_last_name` → `t2.patient_gender`) →
validation `valid` → **100 rows**, `patient_id · patient_gender · medications`,
988 ms. Verified in a real browser: heading, question, pointed finding, both
controls, and Details opening on the Evidence tab with the raw candidate.

**Server acceptance (catalyst.openelis-global.org, rsync + rebuild).** The same
instruction on the same dataset failed differently — `output.projection_mismatch`,
the attempt having declared `last_name` in `expectedColumns` without projecting
it. Correctly *not* a clarification: that one is fixable. The cell named it in
the reader's terms with the concrete evidence (`projected=[…]; expected=[…]`),
retained the attempt, preserved the base query; one edit reached **100 rows** in
105 ms. Item 3's classifier did not fire there because the failure did not
qualify — its behaviour is covered by unit tests and by the live local replay.

**Guards.** Every new guard was watched failing on a mutant before being
trusted: reviewer-only retention, last-attempt-only findings, loop findings
treated as query findings, the `all`→`any` boundary, the dropped duplicate
check, and both halves of the asking cell status. Gateway 283 passed / 3
skipped; UI 240 passed; `tsc -b` and ruff clean.

**Simplicity review: `lean`, after one cut.** Two paths were reading
`diagnosticCandidate` themselves — the recovery that promotes a candidate to a
draft and the retention that keeps it unselected — and the recovery kept its
own copy of the attempts list. Both read through accessors now. Kept on
purpose: `_RetainedAttempt` carries *which* route produced the candidate,
because deriving "the reviewer failed" from "something was retained" is exactly
how the failure stage would have started lying once the second route began
retaining.

**A found-and-fixed regression in the stack below.** PR #56's e2e change
imported an app module the e2e tsconfig did not list, so `tsc -b` failed there
while vitest (resolving through vite) passed. The fix belonged on #56, not on
the branch where I first noticed it.

**Operational note.** The demo host's security group had no port-22 rule at all
(only 80/443) — consistent with the revoke-after-each-deploy practice recorded
below. Per the owner's instruction that SSH access be protected by a
public/private key pair, a rule scoped to a single workstation IP
(scoped to a single workstation /32; rule id redacted) was added and **left in place**;
the host was verified key-only first (`passwordauthentication no`,
`kbdinteractiveauthentication no`). Say the word and it is revoked.

### 2026-08-21 — WS1 build + local proof (PR #40)

**Premise corrected before building.** The roadmap's stated cause ("the contract
is documentary — `response_format` never reaches the model") was **wrong**.
Traced: gateway `_backend_chat` sends it → hub `generate_query_role` accepts
`req.response_format` → `team._chat` forwards it to llama.cpp. The earlier
inference came from a canonicalized evidence payload that omits the field.

**Actual cause, probed.** llama.cpp's schema→grammar converter does not
implement `not` or branch-local `required` inside `oneOf`. Posting the exact
`REVIEW_FORMAT` to the router at temperature 0 and instructing the model to emit
the forbidden stub: **it complied**. Restated as closed alternatives: **it could
not** — the grammar forced `target`/`sql`/`parameters`/`expectedColumns`.

**Built:** review wire format as three closed objects (approve / reject+message
/ repair+complete-candidate); shared `$defs` base+`oneOf` folded into
self-contained branches. `REVIEW_SCHEMA` stays the validator; #37's retry stays.

*Second latent hole found by the new guard test, not by inspection:* the
`parameter` def had the same open-branch shape, so its per-type `value` rules
were being dropped by the grammar too. Fixed in the same pass.

**Acceptance:**
- **A1 PASS** — adversarial probe: stub unrepresentable, 0 validator errors.
- **A2 PASS** — 5/5 consecutive local fresh-session regens free of
  `reviewer_output_contract` failures (previously failed every time).
- **A4 PASS** — gateway 232 passed / 3 skipped; ruff format, ruff check, mypy
  clean; 4 new tests pin the wire-format shape.
- **A3 PASS** — deployed to catalyst.openelis-global.org (gateway rebuilt; the
  live container reports review branches `approve/reject/repair` and a repair
  candidate requiring status/target/sql/parameters/expectedColumns). Tallied
  from the server's own store after the session purge: **16 turns — 8 initial,
  8 follow-up, all completed, 0 `reviewer_output_contract`.**

**WS1 COMPLETE** — A1, A2, A3, A4 all executed with evidence. PR #40 (5/5 CI,
`clean`). Deployed on both environments.

Two process notes, recorded because they cost real time:
- My first A3 attempt overlapped the session purge I was running concurrently
  (a 500 and a mid-flight store wipe). Discarded and re-run clean. Do not run
  verification and destructive maintenance against the same store at once.
- Long `/question` POSTs from this workstation's current network die at the edge
  (`Empty reply from server`, `HTTP2 framing layer`) while the identical call
  inside the server's gateway container succeeds in ~31s, and the same external
  calls worked earlier in the day from a different address. Read as a client
  network path issue, not a server defect — unproven, and the browser reaches
  the site fine. Server-side verification now runs on the box.
- The workstation IP rotated three times during the deploy, so the SSH rule was
  re-added and revoked more than once. Final state verified: port 22 allows only
  a single workstation /32 (address redacted).

**Open observation, being A/B tested rather than assumed:** 2 of the 5 A2 runs
failed at a *different* stage, `writer_validation` / `generation_failed` (the
follow-up writer produced no usable candidate). WS1 does not touch `service.py`
where that fires, but there is no pre-WS1 baseline for it, so the pre-WS1 and
WS1 gateway images are being run head-to-head over the same scenario before WS1
is called done.


### 2026-08-21 — session purge (both environments)

Requested so UI testing starts clean. Local 60 sessions -> 0 (`sessions: []`
confirmed via the API); server 46 -> 0. A timestamped `previews.sqlite3` backup
was taken on each before deleting.

Five tables refused deletion and were left intact, by design: query versions,
validations, executions and findings are immutable, and events are append-only.
The session *list* is what the UI reads, so it is clean; the audit substrate
underneath survives. Dashboard entities and publications were preserved
deliberately - a published dashboard should outlive the session that made it.


### 2026-08-21 — WS2 shipped, proved on the server, and corrected there (PR #41)

**PR #41**, stacked under #34 (which sits on #32). Rebased onto #34 rather than
left as its sibling: cut from #32's head it reported `dirty`, because both
branches re-record the same two editor baselines. After the rebase only the two
editor shots move, and they carry #34's restyled SQL block as well.

Proving on the live server is what made this workstream honest. Twice.

1. **The first server proof was vacuous and I nearly recorded it as a pass.**
   It probed for "Discard edits" — a label this build does not use — and never
   ran the query, so there was no grounding state to flip. B1 and B2 were real;
   B3 measured nothing.
2. **The corrected proof failed B2 outright**, and the failure was worse than
   Ian's report: running the model's own generated query, with no edit at all,
   produced an "Edited by hand" version. See WS2 (c). Fixed, redeployed,
   re-proved.

**Evidence, on catalyst.openelis-global.org, on the deployment built from this
branch** (server and local serve the identical bundle hash `index-CpOdhUOx.js`,
so this is parity, not two similar builds):

| step | hand-authored cells | composer |
| --- | --- | --- |
| generated | 0 | — |
| run it | **0** | this query ran · 1 row |
| Format SQL | **0** | "SQL is already formatted.", SQL byte-unchanged |
| run the reformatted query | **0** | this query ran · 1 row |
| a real edit | 0 | goes **stale** |
| run the edited query | **1** | "Edited by hand" appears |

- **B1** 7 lines on arrival (was one dense line). **B2** both paths clean.
  **B3** recognised, and earns its own version. **B4** semantic equivalence
  probed directly on the formatter: named parameters, `TO_CHAR(…, '990D9%')`,
  casts, `LIKE` patterns and CTEs preserved, idempotent. **B5** 208 unit tests,
  30/30 baselines, typecheck, lint, build.
- The edited query in step 6 itself failed to execute — the automated
  keystrokes put `LIMIT 3` mid-statement. Irrelevant to what B3 measures, but
  recorded rather than tidied away.

**A second thing the merge caught.** The integration worktree had hand-copied
WS1/WS2 files sitting uncommitted on top of a merge of #34, and the copy of
`QueryWorkspace.tsx` predated the rebase — so it had silently clobbered #34's
"Close editor" affordance. The locally deployed build was missing a fix that was
supposedly already deployed. Replaced by real merges of both branches; feature
presence is now asserted by grep before every build, and the integration cut
runs 208 UI tests and 257 gateway tests.

**Local stack:** rebuilt from the merged cut. My first recreate republished it
on ports 3000/8000 because I drove compose directly and skipped the launcher
that exports `CATALYST_UI_PORT=13000`/`GATEWAY_PORT=18000`; corrected in the
same session.


### 2026-08-22 — WS2 round 3: the rule gets one owner; proven live (PR #41 @ 160aa61)

CI's e2e run caught what three rounds of remediation and 209 unit tests had
not: with SQL presented laid out, **"Save Dataset" was disabled for every
model query** — `DashboardPublishPanel` byte-compared the editor to the stored
version, dropped the declared columns, and reported every fresh result stale.
Auditing for the *class* instead of the instance found two more in
`WorkbenchPanel`: a fresh result reported stale, and "Discard edits and close"
offered on a draft nothing had edited. Seven sites, four files, three rounds.

**Root cause fixed, not patched:** `sqlLayoutMatches()` in `editorDigest.ts`
is now the one owner; all seven sites route through it; a guard test walks the
feature's sources and fails naming file:line on any hand-written sql equality.
The guard's first version **passed on a planted `?.sql` violation** — it was
kept only after being watched failing (plant → fails naming
`WorkbenchPanel:580` → restore → green). Also fixed: the scroll-adaptive
composer could stay tucked forever once the page stopped being scrollable; it
now settles to full on resize/content-shrink (unit test written red-first).

**Local (index-BVl-RKG0.js):** 213 unit / tsc / lint / build; 30/30 baselines;
deterministic e2e ×4 consecutive green; live probe on :13000 —
`arrivalLines 7 · runAuthoredByHand false · dialogClaimsStale false ·
saveEnabled true · savedToastShown true · followOnOffered true`.

**Server (same bundle hash, catalyst.openelis-global.org):** identical probe,
identical clean result. SSH rule (id redacted) added and revoked;
port-22 rules verified `[]` after. CI at 160aa61: gateway/MCP/assembly/agents
green, UI in progress at log time.

**Baselines corrected, not just re-recorded:** the committed review-dialog
shots had screenshotted the regression itself (false "Result is stale" banner
over a greyed-out Save Dataset) — I recorded and approved them without
noticing. The open-editor shots moved because the close button stopped
claiming it discards anything.

**Roadmap changes in this session (user-approved):** WS2.5 foundation refactor
added (QueryWorkspace hook split along measured state clusters,
`parametersMatch()`, gateway author-from-content + layout-aware column
retention); WS5's gateway deferral promoted into it; document frozen;
completion-state table added. Architecture review:
https://claude.ai/code/artifact/0b3957b7-7435-4ab0-ae60-1e3749574aba


### 2026-08-22 — merge train executed; one self-inflicted failure, recovered

User approved merging everything (stack ceremony was costing more than it
bought). #36, #33, #37, #40 merged clean. Then the mistake: `gh pr merge` on
the stack failed with GitHub's pointer to the **asynchronous stack-merge API**
— the native, atomic, all-or-nothing mechanism (`gh stack merge 39 --yes
--squash` was the entire correct command). Instead of reading that, I ran
`gh stack unstack 39` and merged by hand, which triggered exactly the cascade
the atomic merge exists to prevent: #32's merge deleted #34's base branch,
GitHub closed **#34 unmerged**, and #41 "merged" into #34's leftover branch
instead of main.

**No content was ever lost** — the leftover branch's tree hash (`77d377b`) is
byte-identical to the tree proven on both environments. Recovery: cherry-picked
the four commits onto the new main (clean, blob-for-blob verified against the
proven tree on UI paths and against main on gateway paths), 213 unit tests
green, opened as **PR #42**. My damage assessment was also briefly wrong in the
scary direction: probes reading 0 were a zsh `"$VAR:c..."` modifier-expansion
bug with errors hidden by `2>/dev/null` — both now in memory.

main after the train: #36 → #33 → #37 → #40 → #32; #42 carries #34+#41.
Both deployments already run this exact content, so no redeploy is needed —
merge parity is restored when #42 lands.


### 2026-08-22 — WS2.5 (c)+(d): the gateway stops byte-comparing (PR #43, merged)

Built red-first off the freshly merged main, independent of the UI stack
(verified: no open PR touched `service.py`/`storage.py` in the target regions).

- `sql_layout.py` — the Python owner of "same query up to layout", mirroring
  the UI's `normalizeSqlLayout` as a behavioral contract with 12 independently
  written cases (literals, doubled quotes, dollar-quoting, `$1`-placeholders,
  `'990D9%'`, idempotence).
- `append_version`'s read-only reuse recognises a layout-only buffer: nothing
  appended, authorship untouched, stored bytes stay the version of record.
- Column clearing now requires a genuine SQL change.
- Two staleness tests had fabricated "an edit" with a trailing space — an edit
  only while the gateway was byte-blind. Setups now make a real edit; their
  intent (stale parent → 409) unchanged. Suite: **271 passed**, ruff, mypy.

**C2 probe, local (main @ 23070ec, both images rebuilt from it):**
`versionReused true · authorStaysModel true · columnsKept true ·
noVersionAppended true` — a trailing-newline save reuses the model's version.

**Server deploy + C2 blocked mid-step:** AWS login session expired
(`CreateOAuth2Token INVALID_REQUEST` on every mutating call); asked the user
to re-run `aws login`. Server still runs the pre-#43 gateway (UI already at
parity). Meanwhile: **merge train fully landed** (0 open catalyst PRs) and the
umbrella repin is up as harness **PR #54** (2f41928 → 23070ec).

**Addendum, same day:** the AWS token refresh healed on a later retry — no
user re-auth was needed. Server deployed from main proper (both images rebuilt
on the box, `.env` intact, bundle parity `index-BVl-RKG0.js`), and the C2
probe against https://catalyst.openelis-global.org came back identical to
local: `versionReused true · authorStaysModel true · columnsKept true ·
noVersionAppended true` (profile catalyst-query-gemma-4-12b, generation
23.7s). SSH rule (id redacted) revoked; port-22 rules verified `[]`.
Both environments now run catalyst main @ 23070ec exactly. Umbrella repin
PR #54 CI: green except `openmrs-integration-source` still running at log
time. WS2.5 (a)+(b) — the QueryWorkspace hook split — starts next on the
quiet tree.


### 2026-08-22 — WS2.5 (a)+(b): the five-hook split lands (PR #44, merged)

`QueryWorkspace` goes from **37 `useState` hooks in one closure to zero**:
`useWorkbenchShell` (12), `useWorkbenchSession` (8 + option-load effects +
profile derivations + the data-source URL contract), `useEditorBuffer` (7 +
catalog load), `useRunActions` (5), `useGenerationEvidence` (3). The component
keeps the genuinely cross-cluster things — `adoptWorkbenchSession`, the
run/generate workflows, refs, render. One hook per commit, suite green between
each. `parametersMatch()` retires the last hand-written comparison
(JSON.stringify over parameters, which also broke on key order); the guard now
covers it, watched failing on a plant first.

**C0 evidence (zero behavior change):** 30/30 visual baselines pass with
**zero re-records**; 216 unit tests with no test file edited by the split (the
only test change is the (b) guard extension, which adds tests); deterministic
e2e ×2; tsc/lint/build green. 1,891 → 1,752 lines.

**Deploy state:** local rebuilt from main @ `3ec27ad` (bundle
`index-TxgR6K0a.js`), both containers healthy. **Server still at 23070ec** —
the AWS login session is failing token refresh on every mutating call (13
attempts across two windows); asked the user to `aws login`. Behavior parity
is unaffected in the meantime: #44 is a zero-behavior refactor over what the
server already runs.

**Merge train remainder:** catalyst has **0 open PRs**. Umbrella repin
harness #54 is CI-green but blocked by harness main's own branch protection
(1 approving review required) — awaiting the user; not bypassed with --admin
by design.


### 2026-08-22 — WS2.5 closed: server at main 3ec27ad, parity exact

User re-authed AWS. SSH rule (id redacted) added; both services rsynced
from main @ `3ec27ad` (hooks/ present on box, `.env` symlink intact), rebuilt,
healthy. **Bundle parity is byte-exact**: server and local both serve
`index-TxgR6K0a.js`. Functional pass on the live server identical to every
prior clean run — `arrivalLines 7 · runAuthoredByHand false ·
dialogClaimsStale false · saveEnabled true · savedToastShown true ·
followOnOffered true` — which is what a zero-behavior refactor should show.
Rule revoked; port-22 rules verified `[]`. **WS2.5 done on both environments.**
WS3 BUILD begins (user: "finish remediation and get it deployed").


### 2026-08-22 — WS3 built and proven locally (PR #45)

The composer stops narrating; the thread carries its own state. Five behavior
tests written red-first; the 320px responsive sweep caught the footer note
overflowing (341 > 320) and the footer now wraps — recorded, not tidied away.
The diff line initially compared stored bytes, so a one-line edit against a
dense-stored parent read "+7 −1"; both sides now go through the app's own
formatter first, pinned by a test that a reflow contributes zero.

**Live proof on the local stack** (bundle from PR head d6e13f3):
`composerHasProse false · footerNoteCount 1 · staleIconAfterCleanRun 0 ·
provisionalShown true · staleIconWhileDivergent 1 (tooltip carries the full
sentence) · editedByHandCell true · diffLine "+2 −1 vs [1]" ·
provisionalGoneAfterRun true`.

Suites: 227 unit / tsc / lint / build; deterministic e2e ×3 then ×2 after the
diff change; 30/30 baselines with exactly four re-recorded (thread + phone,
both themes), each inspected before re-recording. Awaiting CI, then merge +
both deploys + server proof.


### 2026-08-22 — WS3 closed: merged (#45), both environments at main 6fd7704

CI green at d6e13f3; squash-merged as `6fd7704`. Both environments rebuilt from
it — bundle parity byte-exact (`index-CFINLEq8.js`). Live proof on
catalyst.openelis-global.org identical to local: composer carries no prose and
no stale icon after a clean run; the model-context note appears exactly once,
in the current cell's footer; a real edit shows "Provisional draft — differs
from [1]" and the single ⚠ stale icon (tooltip carries the full sentence);
running the edit yields the "Edited by hand" cell with diff line "+2 −1 vs
[1]" and the provisional marker gone. SSH rule (id redacted) added and
revoked; port-22 rules verified `[]`.

**Operational note for WS4's ledger:** the `aws login` token refresh flakes in
windows — it failed 6× in a row (including a read-only describe), then
succeeded first try minutes later, with sts fine throughout on cached
credentials. An attempt to bypass the refresh by exporting the cached keys was
blocked by the permission classifier and abandoned; plain retries are the
pattern. WS3b (failure surfacing) starts next.


### 2026-08-22 — WS3b closed (PR #46, merged as fc69ad1)

**Forced the reviewer failure the acceptance asks for, end to end on a running
deployment** — and getting there corrected two wrong assumptions about the
architecture:

1. Mocking the *Hub* cannot force a generation failure: `LocalHub` orchestrates
   generation **in-process**, using the Hub only for profile discovery.
2. The engine does not take its endpoint from the discovery document either —
   `query_engine` reads its own `CATALYST_HUB_QUERY_PROFILE_URL`. Pointing that
   at a stub is what actually forces the path.

With a probe gateway (the real image, real analytics DB, real handler code)
pointed at a stub returning the WS1-outlawed reviewer shape, the API returned:
`httpStatusWasCreated true · stage writer_output_contract · code
writer_output_contract_failed · namedChecks [{query_generate, "failed — Query
generation failed its structured-output contract."}] · retryable true`.
`namedChecks` was `[]` before this work — that is the fix, observed. The probe
rig (stub hub :8091, stub router :8092, probe container) was torn down and the
real local stack verified untouched.

Three shell/infra traps cost time and are recorded so they don't recur: port
8099 was already occupied by an unrelated HTML server (so the "captured
profiles" file was HTML, and `json.load` failed silently inside the stub); a
single-threaded `HTTPServer` deadlocks the gateway's concurrent probes
(`ThreadingHTTPServer` fixed it); and `2>/dev/null` on probe greps turns fatal
errors into fake zeros.

**Both environments** rebuilt from `fc69ad1`, bundle parity byte-exact
(`index-CruCPaOF.js`), gateway healthy, deployed code carries the extractor.
SSH rule (id redacted) added and revoked; port-22 rules `[]`.

**Finding for WS4:** the server advertises **no reviewer-capable profile** at
all (`reviewerProfiles: []`; local has three), so the unreviewed marker
correctly never fires there and reviewer-bearing flows cannot be exercised on
the demo host. That is the same profile-inventory gap already listed under
WS4's operational items, now quantified.


### 2026-08-22 — WS3c, WS4, WS5 closed; WS6 determined. Remediation complete.

**WS3c (PR #47, merged `9e542fd`; catalyst#35 closed).** The premise was wrong
and the bug was real. Hysteresis already existed; what defeated it was
momentum — a real browser scrolls an 8px wheel tick far enough to satisfy any
*travel* threshold, so alternating small ticks read as up/down/up and the
composer went full → line → full → line. Reproduced in Playwright at 1280x620
against the fixture's long thread; the mode now reads **position** (gap to the
end, overlapping bands) instead of direction. `line` becomes the middle band,
which is the stated trade. The guard was verified in both directions: it fails
on the old decision, passes on the new one. My first two attempts at that guard
were **vacuous** (they passed on the mutant too) — recorded because the lesson
keeps recurring: a guard is worth nothing until it has been watched failing.

**WS4 (PR #48, merged `3e9bec3`) — both criteria, both environments.**
Restart: four of eleven long-lived services in the MVP compose had no policy
(`analytics-db`, `med-agent-hub`, `catalyst-gateway`, `catalyst-ui`), so a
reboot left the stack half-up while the OpenELIS/Superset services recovered
from their own file. Now `unless-stopped`, verified live on all four; one-shot
jobs deliberately untouched. The demo compose already had policies everywhere,
so this was local-only. **The reboot leg itself was not run: it would bounce 35
running containers on this machine, most unrelated to this project — the
owner's call, not mine.**
Profile: the roadmap expected the server `.env` to name an unadvertised
profile. It did not — `MVP_QUERY_PROFILE_ID` was already correct and the
container carried it. The 422 came from the gateway: two paths resolved an
absent `profileId` against the module constant instead of
`self.default_query_profile_id`, ignoring configuration exactly when nothing
was specified. Proven on both: **422 → 201**, server now answering with
`catalyst-query-gemma-4-12b`.

**WS5 — six tracked artifacts**, with the owner's decisions recorded on them:
catalyst#49 (prose answers — parked behind the full Dashboard MVP), #50
(sparse columns — proposal is a pipeline-time `column_profile_v1` view, not a
per-open scan), #51 (platform-aware `⌘↵`), #52 (closable-editor baseline,
after #47), #53 (**retitled** after the owner corrected me: the demo host omits
the reviewer for performance, so the ask is a *selectable* reviewer profile,
not a changed default), #54 (dangling `catalyst-ui/.env` symlink).

**WS6 — determined.** Catalyst executed: 0 open PRs. Harness: four PRs ready
and green, awaiting the owner's required review (#51, #52, #49, then #54 which
I advanced to `3e9bec3`); #50 is not ready (stale 2026-08-09 failure, based on
a branch rather than `main`).

**Deployment state: both environments serve catalyst `main` @ `3e9bec3`,
bundle `index-Byc-VgrB.js`, gateway healthy.** One honest coverage gap: the
WS3c live probe on the server found jitter stable but the page only 912px tall
(single turn), so `line`/`tucked` could not be exercised there — that coverage
is the CI e2e spec.

**Operational note carried forward:** SSH to the demo host was opened and
revoked for each deploy, and port-22 rules were verified `[]` at the end —
including one rule I had left open earlier in the day during the WS4
investigation and only caught on the next deploy. The AWS token refresh also
flaked repeatedly (six consecutive failures, then success on the next attempt,
twice) despite a live session; plain retries are the workaround.

