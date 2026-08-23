# Catalyst workbench token map

Checkpoint 2 of `styling-remediation-roadmap.md` · Produced 2026-08-08 ·
No code changes — this is the decision record CP-3 executes.

Every one of the **390 hex literals** across **34 distinct values** in
`catalyst-ui/src/**/*.css` is accounted for below: each has a named Carbon
token, a named palette colour, or a written justification for changing.

Values were read out of the built bundle's `.cds--g10` block (327 tokens) and
`@carbon/colors`, not from the design document's prose — so the mapping is
against what Carbon actually emits at the version we now pin
(`@carbon/styles` 1.112.0, CP-0).

## What the numbers turned out to be

| | Count | Meaning |
| --- | --- | --- |
| Map to a **semantic g10 theme token** | 25 | direct substitution |
| Are a **Carbon palette colour** with no g10 semantic token | 5 | import from `@carbon/colors`, or accept a near semantic token |
| Are **not Carbon at all** | 4 | a decision, not a translation |

**The recon flagged one non-Carbon value. There are four.** That is the single
most useful correction this checkpoint makes.

## The base theme, restated

`catalyst-ui/src/App.tsx:14` sets `<Theme theme="white">`; §10 mandates **Gray
10**. Under White, `background` and `layer-01` are both `#ffffff`. Under Gray
10 they separate — `#f4f4f4` page, `#ffffff` layer — which is exactly the depth
the UI currently fakes with hairlines.

This matters for reading the table below: **the literals were chosen against
White but map onto Gray 10 tokens.** `#f4f4f4` is currently a hand-painted card
tint; as `--cds-background` it becomes the page. That is the intended
correction, and it is why CP-3 and CP-4 must land together behind the baseline.

The palette is emitted **only** under `.cds--white` / `.cds--g10` / `.cds--g90`
/ `.cds--g100` class selectors and never on bare `:root`. CP-3's first
assertion must be that every styled node sits inside the `<Theme>` subtree, or
substitution silently produces unstyled regions.

## Direct semantic mappings (25)

| Literal | Uses | Token | Note |
| --- | ---: | --- | --- |
| `#0f62fe` | 52 | `--cds-link-primary` · `--cds-border-interactive` · `--cds-focus` | Pick by role: link text, accent border, focus ring. Do not collapse to one. |
| `#e0e0e0` | 48 | `--cds-border-subtle-01` | |
| `#f4f4f4` | 44 | `--cds-background` | **Role change under Gray 10** — see above |
| `#525252` | 44 | `--cds-text-secondary` | |
| `#6f6f6f` | 33 | `--cds-text-helper` | |
| `#fff` | 28 | `--cds-layer-01` | not `background` — under Gray 10 the layer is the white one |
| `#c6c6c6` | 25 | `--cds-border-subtle-02` · `--cds-border-disabled` | |
| `#161616` | 22 | `--cds-text-primary` | |
| `#8d8d8d` | 17 | `--cds-border-strong-01` · `--cds-text-placeholder` | |
| `#8a3ffc` | 11 | `--cds-status-purple` | §10's AI/suggestion accent (purple-60) |
| `#da1e28` | 11 | `--cds-text-error` · `--cds-support-error` | |
| `#24a148` | 9 | `--cds-support-success` | |
| `#e8e8e8` | 8 | `--cds-layer-hover-01` | |
| `#fff1f1` | 4 | `--cds-notification-background-error` | |
| `#0e6027` | 3 | `--cds-tag-color-green` | |
| `#a8a8a8` | 3 | `--cds-border-tile-01` | |
| `#a2191f` | 2 | `--cds-tag-color-red` | |
| `#6929c4` | 2 | `--cds-syntax-control-keyword` | §10 calls it purple-70 |
| `#defbe6` | 1 | `--cds-notification-background-success` | |
| `#4589ff` | 1 | `--cds-support-info-inverse` | |
| `#750e13` | 1 | `--cds-button-danger-active` | |
| `#ffd7d9` | 1 | `--cds-tag-background-red` | |
| `#a7f0ba` | 1 | `--cds-tag-background-green` | |
| `#f1c21b` | 1 | `--cds-support-warning` | |
| `#e8daff` | 1 | `--cds-tag-background-purple` | |

**The error family is ratified here.** `#da1e28`, `#fff1f1`, `#a2191f`,
`#ffd7d9`, `#750e13` appear nowhere in §10 — the handoff never drew error
states, so we invented them. They are exactly Carbon red-60/10/70/20/80, the
right answer reached without authority. They become tokens and §10 gains an
error row.

## Palette colours with no g10 semantic token (5)

Carbon has two layers: semantic theme tokens (`--cds-*`) and the raw palette
(`@carbon/colors`). These five are palette values the g10 theme does not bind
to any semantic name, so there is nothing to substitute *to* — they need an
explicit decision rather than a lookup.

| Literal | Uses | Palette | Recommendation |
| --- | ---: | --- | --- |
| `#262626` | 4 | `gray90` | Keep as palette. It is the demo banner, which is deliberately inverse and does not follow the page theme. |
| `#684e00` | 2 | `yellow70` | Keep as palette, or `--cds-text-on-color` inside a warning tag. |
| `#fddc69` | 1 | `yellow20` | Keep as palette — it is a tag background with no g10 token. |
| `#044317` | 1 | `green80` | Keep as palette. |
| `#d4bbff` | 1 | `purple30` | Keep as palette. |

Adopting them via `@carbon/colors` rather than a literal still buys the thing
that matters: one authored source, and a name that says which ramp step it is.

## Not Carbon — decisions, not translations (4)

| Literal | Uses | Where | Nearest Carbon | Decision |
| --- | ---: | --- | --- | --- |
| `#f7f2ff` | 4 | assistant/model accent background — `styles.css`, `DetailsPanel`, `TurnNotebook`, `WorkbenchPanel` | `purple10 #f6f2ff` (Δ1.0) | **Adopt purple-10.** §10 line 282 specifies `#f7f2ff` for the assistant suggestion background; at a distance of 1.0 it is purple-10 with a typo. Correct the design doc rather than preserve the typo. |
| `#e8f0fe` | 2 | selected/info surfaces — `DetailsPanel`, `WorkbenchRail` | `blue10 #edf5ff` (Δ7.1) | **Replace with blue-10.** Not Carbon, not in §10 — a Material/Google tint that leaked in. Blue-10 is the same family as the `#0f62fe` accent already beside it. |
| `#fdfdfd` | 1 | SQL editor background — `SqlEditor` | `white #ffffff` (Δ3.5) | **Replace with `--cds-field-01`.** An editor surface is a field; the near-white was approximating one. |
| `#fff8e1` | 1 | warning surface — `WorkbenchPanel` | `yellow10 #fcf4d6` (Δ12.1) | **Replace with `--cds-notification-background-warning`** (`#fcf4d6`). Visibly different, and deliberately so: this is a warning surface and should use the warning token, not a Material amber. |

## What CP-3 must do with this

1. Assert the `<Theme>` wrapper covers every styled node **before** substituting.
2. Substitute file by file, largest first: `WorkbenchRail` (80) · `TurnNotebook`
   (75) · `styles.css` (67) · `DashboardPublishPanel` (53) · `WorkbenchPanel`
   (45) · `DetailsPanel` (33) · `DatasetBrowser` (25) · `SqlEditor` (12).
3. Choose by **role**, not by value — `#0f62fe` is three different tokens
   depending on whether it is a link, a border, or a focus ring.
4. Name every baseline screenshot that moves, and why. Four of the surfaces
   *should* move: the ones using the four non-Carbon values.

*Acceptance for CP-2:* every literal above has a named token or a written
justification, and no "probably". No code changed in this checkpoint.
