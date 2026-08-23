# Catalyst workbench styling remediation and revamp

Status: proposed · Recon date: 2026-08-08 · Scope: `targets/catalyst/catalyst-ui`

## Why this is remediation, not redesign

The design handoff (`docs/dashboard-builder-mvp-design.md` §10) opens its token
table with an instruction:

> Carbon Gray 10 theme. Everything below is already a Carbon token — **use the
> token, not the hex.**

We used the hex. The measured state of the tree:

| Metric | Value |
| --- | --- |
| Hardcoded hex literals in `src/**/*.css` | **390** |
| Distinct hex values | **34** |
| Occurrences of `var(--cds-*)` | **0** |
| Carbon custom properties already emitted into `dist/assets/index-*.css` | **446** |

The token layer is already built, bundled, and served on every page load. Nothing
references it. This is the whole problem, and it is why the UI reads flat: with
no token indirection there is no layer model, no theme switch, and no guarantee
that a component we wrote sits on the same ground as one Carbon shipped.

### Literal inventory, by frequency

```
52 #0f62fe   48 #e0e0e0   44 #f4f4f4   44 #525252   33 #6f6f6f   28 #fff
25 #c6c6c6   22 #161616   17 #8d8d8d   11 #da1e28   11 #8a3ffc    9 #24a148
 8 #e8e8e8    4 #fff1f1    4 #f7f2ff    4 #262626    3 #a8a8a8    3 #0e6027
 2 #e8f0fe    2 #a2191f    2 #6929c4    2 #684e00    1 each: #fff8e1 #ffd7d9
 #fdfdfd #fddc69 #f1c21b #e8daff #defbe6 #d4bbff #a7f0ba #750e13 #4589ff #044317
```

Per file: `WorkbenchRail.css` 80 · `TurnNotebook.css` 75 · `styles.css` 67 ·
`DashboardPublishPanel.css` 53 · `WorkbenchPanel.css` 45 · `DetailsPanel.css` 33 ·
`DatasetBrowser.css` 25 · `SqlEditor.css` 12.

### Two findings the spec does not cover

1. **The error palette is undocumented drift.** `#da1e28` (11 uses), `#fff1f1`,
   `#a2191f`, `#ffd7d9`, `#750e13` appear nowhere in §10 — the handoff never drew
   error states, so we invented them. They happen to be Carbon red-60/10/70/20/80,
   which is the right answer reached without authority. Ratify them into the spec.
2. **`#e8f0fe` is not a Carbon color.** It is a Material/Google blue tint. A
   non-Carbon value leaked in and must be replaced, not translated.

### The base theme — SETTLED 2026-08-08

Recon left this open and guessed the mechanism was a bare `@use "@carbon/react"`
in `src/carbon.scss` falling back to Carbon's default. That guess was wrong in
mechanism and right in effect. The actual cause is one line:

```tsx
// src/App.tsx:14
<Theme theme="white">
```

**We are on White, deliberately and explicitly, while §10 mandates Gray 10.**

Two consequences the rest of this document depends on:

1. **The flatness has a named cause.** Under White, `--cds-background: #fff`
   and `--cds-layer-01: #f4f4f4`. Under Gray 10 they swap — `#f4f4f4` page,
   `#fff` layer — which is exactly the page-versus-card depth cue the UI is
   missing and currently fakes with grey hairlines. Correcting it is a
   one-word change, and it is why CP-4 (the layer model) is mostly free once
   CP-3 lands rather than a redesign.
2. **Token migration cannot precede it.** The colour tokens are emitted *only*
   under `.cds--white` / `.cds--g10` / `.cds--g90` / `.cds--g100` class
   selectors — `:root` carries the grid, layout and `--cds-layer` alias tokens
   but no palette. So `var(--cds-background)` resolves only inside a `<Theme>`
   subtree. Migrating literals to tokens without confirming that every styled
   node sits under the theme wrapper would silently produce unstyled regions.
   CP-3 must assert the wrapper's coverage before substituting anything.

Dark mode is the same knob: `g90` / `g100` are already in the bundle, so CP-7
is a theme-value swap plus a persisted preference, not new CSS.

The change itself is **not** made here. It shifts every surface at once, so it
belongs behind CP-1's baseline harness where the diff can be reviewed rather
than merged on faith.

## Library currency (audited 2026-08-08)

`npm outdated` against the registry. **CodeMirror and sql-formatter are already
at latest** — static SQL highlighting needs no upgrade and no new dependency.

**In-range (a `npm update` away — do these together, before any CSS work):**

| Package | Current | Latest |
| --- | --- | --- |
| **@carbon/react** | 1.112.0 | **1.113.0** |
| **@carbon/styles** (token source) | **1.111.0** | **1.112.0** |
| @carbon/icons-react | 11.84.0 | 11.85.0 |
| react / react-dom | 19.2.7 | 19.2.8 |
| vite | 8.1.4 | 8.2.1 |
| @playwright/test | 1.61.1 | 1.62.1 |
| eslint · typescript-eslint · sass · globals · @vitejs/plugin-react · @types/* · user-event | — | minor/patch |

`@carbon/react` dist-tags are `latest: 1.113.0`, `next: 1.113.0` — no v2 pending,
no prerelease divergence. `@carbon/styles` is the package that emits the 446
custom properties and it is the one lagging furthest; migrating 390 literals
against a stale token set risks mapping onto tokens that were renamed or missing
tokens that now exist.

**Majors — deliberate, and deliberately NOT bundled with visual work:**

| Package | Current | Latest | Risk |
| --- | --- | --- | --- |
| typescript | 6.0.3 | 7.0.2 | compiler major |
| jsdom | 29.1.1 | 30.0.1 | test environment |
| @testing-library/jest-dom | 6.9.1 | 7.0.0 | matcher semantics |

These are test-infra risk with no visual surface. Landing them inside a styling
refactor would contaminate the screenshot diffs that are the acceptance
instrument for every checkpoint below — if a baseline moves, you must be able to
say which change moved it. Ship them before Checkpoint 0 or after Checkpoint 7,
never between.

## Checkpoints

Each checkpoint is one PR, stacked on the previous. No checkpoint merges without
its acceptance criteria demonstrably met.

### CP-0 · Version currency

Apply the in-range bumps, Carbon first.

*Acceptance:* `npm outdated` lists only the three majors · 152 UI tests, lint,
typecheck, build green · no CSS touched in this PR (`git diff --stat` shows zero
`.css` lines).

### CP-1 · Visual baseline harness

Extend the existing mock-API Playwright harness into a committed, named
screenshot set: empty session · generated turn · expanded dataset tile · failed
run · each library section · review dialog · rail at min/default/max width.

*Acceptance:* the set regenerates twice with **byte-identical output** · runs
against the deterministic mock only, no live models · a single documented command
produces it. This instrument is what every later checkpoint is measured with;
it is built before a pixel changes.

### CP-2 · Resolve the base theme; publish the token map

Confirm White vs Gray 10. Then map all 34 literals → Carbon token, marking the
red family and `#e8f0fe` as **decisions** rather than translations.

*Acceptance:* every literal has a named token or a written justification, with
zero entries reading "probably" · the red family is ratified into §10 by an edit
to the design doc · no code changes in this PR.

### CP-3 · Mechanical token migration

Replace literals with `var(--cds-*)`, file by file, largest first.

*Acceptance:* `grep -rc '#[0-9a-fA-F]\{3,8\}' src/features/query/**/*.css src/styles.css`
returns 0 · CP-1 baselines differ **only** where a token corrects a wrong value,
and every such diff is enumerated in the PR body with its justification · tests,
lint, typecheck, build green.

### CP-4 · Adopt the layer model

Page → cell → dataset tile become `layer-01/02/03` instead of three white boxes
separated by grey hairlines.

*Acceptance:* before/after from the CP-1 set showing depth · text contrast
≥ 4.5:1 and border/non-text contrast ≥ 3:1, measured and recorded, not asserted.

### CP-5 · Spend the semantic palette

Drive color from the `data-status` (`succeeded`/`failed`/`not-run`) and
`data-author="human"` hooks the cells already carry, plus the dataset tile's
Draft/Saved state. §10 already assigns purple to model/AI, green to success,
red to failure, blue to interactive.

*Acceptance:* a stated and enforced rule — **no color that does not encode
state** · a screenshot in which succeeded / failed / not-run / hand-edited are
distinguishable at a glance without reading text.

### CP-6 · Static SQL syntax highlighting

Committed cells render `<pre>{version.sql}</pre>` as plain text while the editor
directly below shows the same dialect in full color. Fix with `highlightTree`
from `@codemirror/language` (**already installed at 6.12.4, latest**) over the
same SQL grammar and the same highlight style as the editor, so the two cannot
drift. Promote `@codemirror/language` to a direct dependency.

*Acceptance:* a committed cell and the open editor render identical SQL
identically · a 20-cell thread mounts **zero** additional CodeMirror `EditorView`
instances, asserted by instance count in a test, not by inspection.

### CP-7 · Dark mode

Token overrides only, now that CP-3 has made that possible.

*Acceptance:* the complete light palette is defined on bare `:root`; dark
overrides appear under `@media (prefers-color-scheme: dark)` guarded against an
explicit light choice, **and** under an explicit dark attribute — all three
resolution paths (system / explicit-dark / explicit-light) verified · **no color
whose only definition lives inside a media query** · CodeMirror dark theme
matching CP-6's highlight style · the full CP-1 baseline set captured in dark
with contrast re-measured · the preference persists via `browserState` alongside
`railWidth` / `railSection` / `sqlWrapLines`.

### CP-8 · Type and density

Carbon's type scale against §10's table for the cell header / SQL / footer
hierarchy.

*Acceptance:* the `[1]`/`[2]` gutter numbering reads as a deliberate motif ·
no ornament added that does not carry meaning.

## Sequencing constraints

- **CP-0 before CP-3.** Migrating against a stale token set is rework.
- **CP-1 before everything.** Without the baseline there is no acceptance test.
- **CP-2 before CP-3/CP-4.** If the base theme is wrong, those two partly
  collapse into fixing it.
- **CP-3 before CP-7.** Dark mode over 390 hardcoded literals means touching
  every rule twice.
- **Majors isolated.** Never in the same PR as a visual change.
