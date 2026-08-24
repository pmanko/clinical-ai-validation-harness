# Catalyst workbench — UX v2 follow-through goals

> **Historical/advisory document (dated 2026-08-08).** For current status and
> sequencing see `specs/catalyst-program-roadmap.md`.

Status: proposed · Written 2026-08-08 · Scope: `targets/catalyst`

Priority order set by the user on 2026-08-08: **the UX/style revamp comes
first**, CI must actually go green, and the acceptance-spec fix ships as
another stacked PR. **Merging is explicitly out of scope** — every goal below
lands as a PR stacked on `feat/workbench-ux-v2-empty-session` (#16) and stays
open until the user decides to merge the stack.

## Where this starts

| Fact | Evidence |
| --- | --- |
| UX v2 is built and deployed | https://catalyst.openelis-global.org, and locally on :13000 |
| Seven stacked PRs, none merged | #10 cells → #11 rail → #12 one-source → #13 details → #14 composer → #15 sessions → #16 empty-session |
| Local suites green | 154 UI tests, 241 gateway tests, lint, typecheck, build |
| **#10's UI job fails** (25m42s) | Playwright `deterministic` asserts the pre-rail shell |
| **#11–#16 have no CI at all** | `.github/workflows/ci.yml` triggers on `pull_request: branches: [main]`; stacked PRs target each other |

The decisions these goals build on are recorded in
`specs/008-catalyst-query-workbench/spec.md`, clarifications session
**2026-08-08 — workbench UX v2**, and in the amendments list at the top of
`targets/catalyst/docs/dashboard-builder-mvp-design.md`.

---

## Goal 1 — Restore the acceptance suite and make CI run on the whole stack

**PR:** `feat/workbench-ux-v2-acceptance`, based on
`feat/workbench-ux-v2-empty-session` (#16).

This is first not because it outranks the styling work but because it *is* the
styling work's instrument. The styling roadmap's CP-1 requires a deterministic
visual baseline before a single colour changes; the Playwright `deterministic`
project is that harness. Fixing it buys CI green and the baseline in one pass.

**Why it is red.** `catalyst-ui/e2e/query-to-table.spec.ts` (1242 lines) still
describes the shell that seven PRs replaced. Known-stale anchors:

| Line | Asserts | Now |
| --- | --- | --- |
| 892 | `navigation` named "Catalyst" | `complementary` named Catalyst, with a nested `navigation` named "Sections" |
| 908 | `Available data ·` disclosure | the rail's DATA section |
| 925, 1014, 1106 | `Refine Query v1` / `v3` | `Refine [1]` / `[3]` — cells, not versions |
| 993, 1054 | `Results from Query v2` heading | compact results in a cell render no heading |
| 539 | `Dataset from Query v3` | dataset titles no longer cite a version |

`e2e/openelis-lab-demo.spec.ts` and `e2e/openmrs-hiv-demo.spec.ts` carry the
same drift; they only run against a live gateway, so they are updated for
consistency but are not the CI gate.

**Also required for CI to mean anything:** remove the `branches: [main]` filter
from the `pull_request` trigger in `targets/catalyst/.github/workflows/ci.yml`,
so a PR targeting another branch still runs. Without this, six of seven PRs
remain structurally invisible to CI regardless of how good the spec is.

**Done when:** `npx playwright test --project=deterministic` passes locally;
CI reports UI / Gateway / Agents / MCP / MVP-assembly green on **#10 and every
PR above it**; the screenshot set regenerates twice with no diff.

**Specified by:** ASK-01–ASK-04 in `spec.md` (lines 640–643) — rewrite the spec
to prove those invariants against the current shell, not to re-encode old
selectors. `styling-remediation-roadmap.md` CP-1 defines the baseline
requirement this satisfies.

---

## Goal 2 — The style revamp *(the priority)*

**Roadmap:** `specs/008-catalyst-query-workbench/styling-remediation-roadmap.md`
— nine checkpoints, each with a falsifiable gate. Read it before starting; the
summary below is a pointer, not a substitute.

**The finding that frames it.** The design handoff's own token table says *"use
the token, not the hex."* The tree has **390 hex literals, 34 distinct values,
zero uses of `var(--cds-*)`, and 446 Carbon custom properties already bundled
and unreferenced.** This is conformance to a spec we were handed, not a
redesign.

**Settled 2026-08-08 — the base theme.** `catalyst-ui/src/App.tsx:14` sets
`<Theme theme="white">` explicitly, while §10 of the design mandates **Gray
10**. Under White the page and cards are both `#fff`, which is why depth is
faked with grey hairlines; under Gray 10 they separate for free. Two
consequences:

1. Correcting it is a one-word change with a whole-app visual diff, so it goes
   **behind Goal 1's baseline** where the diff can be reviewed rather than
   trusted.
2. The palette is emitted only under `.cds--white` / `.cds--g10` / `.cds--g90` /
   `.cds--g100` class selectors and **never on `:root`**. Token migration must
   first assert the `<Theme>` wrapper covers every styled node, or substitution
   silently produces unstyled regions.

**Suggested PR split** (each stacked on the previous):

- `feat/workbench-theme-tokens` — CP-0 version currency, CP-2 token map, CP-3
  mechanical migration. Gate: `grep -c '#[0-9a-f]\{3,8\}'` reaches zero in
  `src/features/query/**`; baseline screenshots differ only where a token
  corrects a wrong value, each diff named in the PR body.
- `feat/workbench-layer-model` — CP-4 layer model (this is where Gray 10
  lands), CP-5 semantic palette driven by the `data-status` / `data-author`
  hooks the cells already carry. Gate: contrast ≥ 4.5:1 text, ≥ 3:1 borders.
- `feat/workbench-sql-highlighting` — CP-6. `@codemirror/language` is already
  installed and exports `highlightTree`; **no new dependency**, and committed
  cells share the editor's grammar so the two cannot drift. Gate: a 20-cell
  thread mounts zero extra CodeMirror views, asserted on instance count.
- `feat/workbench-dark-mode` — CP-7. `g90`/`g100` are already in the bundle.
  Full light palette on bare `:root`; never define a colour only inside a
  media query. Persist the preference through `browserState`, which already
  carries `railWidth` / `railSection` / `sqlWrapLines`. Gate: all three
  resolution paths (explicit light, explicit dark, system) verified, and the
  full baseline set captured in dark.
- `feat/workbench-type-density` — CP-8, against §10's type table.

**Two spec corrections to make along the way**, both named in the roadmap: the
error palette (`#da1e28` and family) is undocumented drift that happens to be
correct Carbon red — ratify it into §10 rather than leaving it unauthored; and
`#e8f0fe` is a Material/Google tint that is not Carbon at all and must be
replaced, not translated.

---

## Retracted — a finding that was not one

An earlier revision of this document claimed the refine composer renders on
the Widgets and Dashboards screens, read off a screenshot diff showing
`Refine [3]` on a library page. **That was wrong.** The notebook and its
composer sit inside `<section hidden={activeSection !== "ask"}>`
(`QueryWorkspace.tsx` 1519–1747) and are absent from every library screen —
confirmed by driving the app: the composer is not in the DOM on Datasets,
Widgets or Dashboards.

What the diff actually showed was the overlay artifact of a *mis-captured*
baseline: three library screenshots were racing each other on a shared dev
server, so one recorded a neighbour's screen. Fixing that race was the real
correction; the composer was never the problem. Recorded here rather than
deleted, because a wrong finding that quietly disappears is worse than one
that is struck out.

## Goal 2b — Generation has to show its work *(reported 2026-08-08)*

Raised from use, and diagnosed against the live gateway on session
`8169f441`. Three defects, one story.

1. **No pending state.** Asking for the next query shows nothing where the
   answer will appear. The only feedback is the submit button's label, inside
   a composer that may be scrolled away. A cell should appear at the foot of
   the thread the moment generation starts, in a generating state, and become
   the answer in place.
2. **A failed generation is silent.** `createWorkbenchTurn` returning a turn
   with `status: "failed"` is treated as success: no error is surfaced, the
   instruction box is cleared, and nothing moves. The observed failure was
   `reviewer_output_contract_failed` — "query review was not valid JSON" —
   and the user saw nothing at all.
3. **A failed turn lands mid-thread.** `threadCells` orders by the selected
   version's ordinal; a failed turn has no version, so it inherits
   `previous + 0.5` and sorts *before* every later hand-edited run. On the
   observed session the new turn was filed as cell [2] of 5. Turns and
   versions both carry `createdAt`, which is the honest shared clock and
   handles a turn that produced no version.

**Done when:** a generating cell appears at the end of the thread and becomes
the result; a failed generation states why, keeps the instruction, and moves
to the cell carrying the failure; and a turn that produced no version is
ordered by when it happened.

## Goal 2c — Make it look like something, in both themes *(requested 2026-08-08)*

"It's so grey and bleh." It is, and the research says that is not a taste
problem — it is four capabilities Carbon ships that we do not spend. All four
are theme-aware, so light and dark both improve from the same work, and none
of them is a redesign.

Measured against the built bundle on 2026-08-08.

### 1. The type scale is entirely unused — the biggest lever

| Carbon type tokens referenced in our CSS | **0** |
| Hand-rolled `font-size: Xrem` declarations | **134** |

Carbon's type scale is not just sizes: each step pairs a size with a
line-height, weight and letter-spacing that were designed together. 134
independent guesses is why the page reads as undifferentiated grey text —
nothing establishes hierarchy, so everything has the same visual weight.
Adopting `--cds-heading-*` / `--cds-body-*` / `--cds-label-*` is mechanical,
exactly like CP-3, and measurable the same way.

### 2. Depth is flat — one layer doing the work of three

| `--cds-layer-01` uses | **29** |
| `--cds-layer-02` / `-03` uses | **0** |

CP-4 separated the page from the cards. Inside a card nothing separates
further: the dataset tile, the result table and the review panel all sit on
the same white. Carbon's layer model exists for exactly this nesting, and
`layer-02`/`layer-03` are already emitted in every theme.

### 3. Carbon ships an AI visual language and we use none of it

| `--cds-ai-*` tokens in the bundle | **21** |
| Referenced by us | **0** |

`ai-aura-start/end`, `ai-border-start/end`, `ai-popover-background`,
`ai-drop-shadow`, `ai-inner-shadow`. This product's entire premise is that a
model wrote the query — Carbon has a designed vocabulary for exactly that
claim, and we render it as a flat purple tint. They are theme-aware out of the
box: `ai-border-start` is `#a6c8ffa3` in Gray 10 and `#a6c8ff5c` in Gray 100;
`ai-popover-background` flips `#fff` to `#161616`.

Highest impact per line changed, and the most on-brand: it makes
model-authored content *look* model-authored instead of merely being labelled.

### 4. IBM Plex is not actually shipped

`src/carbon.scss` sets `$css--font-face: false`, and the built bundle contains
**0 `@font-face` rules**. The CSS asks for `IBM Plex Sans` and the browser
falls back to system-ui for anyone who does not happen to have Plex installed
locally — which is most people, including every visitor to the demo host. It
renders correctly on a developer Mac with Plex installed, which is why nobody
noticed. Carbon's whole typographic identity rests on this font.

`@ibm/plex` is not a declared dependency. Adding it, or flipping the flag, is
the smallest change on this list with a visible effect on every screen.

**Sequencing:** these belong with CP-7, not after it. Dark mode is a theme
swap, and all four items above are theme-aware — doing them first means dark
mode arrives already looking composed rather than needing a second pass. Item
4 is independent and can land immediately.

**Done when:** Carbon type tokens replace the hand-rolled sizes; nesting uses
the layer model; model-authored content uses the AI tokens; Plex is served
rather than assumed; and the full baseline is captured in **both** themes.

## Goal 3 — Build the repair turn ("Fix query")

The one advertised feature with nothing behind it.
`targets/catalyst/catalyst-gateway/src/catalyst/repairs.py` **does not exist**.

**Specified by:** `tasks.md` T028–T034 (US2), and the W2 section of
`roadmap.md` (line 2183, "W2 — Targeted remediation") with its G4/G5 gates.
The design's `auto` badge and "Repaired in [n]" pill are described in
`targets/catalyst/docs/dashboard-builder-mvp-design.md`.

Note the constraint written into T031/T032: the Gateway owns the typed
repair-proposal contract and SQL policy; any model role runs **only** through
the Hub's generic configured-role endpoint. Do not add Catalyst query logic to
the Hub, and do not repurpose the internal G2.3 retry as an accept/decline
workflow.

**Done when:** T029's AST unit / frozen-digest / patch-integrity tests pass,
a repair turn appears as its own cell in the thread, and G4/G5 in `roadmap.md`
are recorded.

---

## Goal 4 — Make `tasks.md` tell the truth

`specs/008-catalyst-query-workbench/tasks.md` has 40 unchecked boxes, and
several describe work that already shipped. Verified 2026-08-08:

| Task | Claims not done | Reality |
| --- | --- | --- |
| T167 | implement `dashboard_routes.py` | **exists** |
| T165 | implement `scripts/mvp-superset.sh` | **exists**, routed through `catalyst-mvp.sh` |
| T164 | implement `scripts/superset-import-state.py` | **exists** |
| T145/T146 | `dashboard_store.py` + its tests | genuinely missing — the store lives in `dashboard_builder.py` |
| T030 | `repairs.py` | genuinely missing (Goal 3) |

The full Dataset → Widget → Dashboard → `bundle_ready` chain was walked end to
end on 2026-08-08 and works, including compatibility-filtered presentation
kinds and the out-of-band Superset import producing a receipt.

**Done when:** every box reflects the tree; tasks whose file exists under a
different name are either closed with a pointer or rewritten to name the real
remaining work. Cross-check against the 2026-08-07 scope disposition
(`roadmap.md` line 2111) and the D1e acceptance plan (line 2153) so the M4 gate
count stays honest.

---

## Stacked-PR plan

```
main
 └── #10 … #16                     (existing, unmerged)
      └── acceptance                Goal 1  ← CI green + baseline harness
           └── theme-tokens         Goal 2  CP-0/2/3
                └── layer-model     Goal 2  CP-4/5  (Gray 10 lands here)
                     └── sql-highlighting   Goal 2  CP-6
                          └── dark-mode     Goal 2  CP-7
                               └── type-density   Goal 2  CP-8
```

Goals 3 and 4 are independent of that chain and may branch from #16 directly.

Nothing merges as part of these goals.
