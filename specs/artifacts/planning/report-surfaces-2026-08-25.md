# Catalyst report surfaces — decisions of 2026-08-25

**Status:** Shipped and live (harness PRs #87, #92; landing #91). This file is
the durable record of the owner-approved contracts; the working artifacts were
"Catalyst Report Revamp" and "Catalyst Judge Review" (claude.ai artifacts
78c7bd40, 6446a932).

These contracts govern `harness/catalyst/report.py`, the curated index card in
`scripts/build-reports-index.py`, and the phase-1 entry copy. Future changes
to these surfaces should honor them or supersede this record explicitly.

## The report page (`report.html`)

Order: plain-language abstract → gate verdict → judge summary → (comparative
standing, when a ranking pass exists) → scenario matrix → dialogue-framed
scenario cards → SQL diffs → timeline → judge detail → methods & provenance
(folded).

### The abstract ("In plain terms")

- **Generated from run data only** — tallies, failure clustering, judge axis
  medians — so it cannot drift from the numbers. Wording templates may be
  seeded from the frozen run-config's publish block (`plainSubject`,
  `plainSummary`, `plainTakeaway`); nothing else is hand-written.
- **No pass/fail gates.** Thresholds are publication policy and appear only in
  the Result section, printed beside the policy that set them ("Against the
  gates in force at publication (…): …").
- **Relative performance, honestly framed:** every team's score by short name;
  a spread within one question at n=12 is stated as a practical tie; the
  caveat line says differences of a question or two are within noise.
- **Failure anatomy:** which questions the misses landed on, shared-by-every-
  measured-team vs team-specific (a team with no valid measurement is not in
  the "every team" denominator), and the errors' nature argued from the
  judge's axes over the failing scenarios' own queries — with a neutral
  fallback sentence when the axis pattern does not hold.

### The judge summary

- **Axes lead; composite trails.** Median plus min–max range per axis; the
  composite is a labeled convenience with the team floor after it.
- **No score cutoffs.** "Weakest queries" = anything the judge marked down on
  any axis (rubric anchors), worst first, at most three per team, each linked
  to its full rationale (anchored `<details>`, opened on navigation).
- **Stated limits, in place:** single-actor runs say self-agreement is not
  validity; unadjudicated runs say "No human adjudication." Multi-actor runs
  report shared-cell counts and the widest disagreement; adjudicated runs
  report the agreement rate. (PCCP:
  `specs/008-catalyst-query-workbench/pccp/2026-08-25-catalyst-judge-rank-v1.md`.)

### Vocabulary and semantics (from the conformance rework, PR #82–#87 era)

- A cell is one conversation; rows are turns; "repetition" only ever means a
  composed suite rerun.
- Judge rows join their scenario rows per (team, scenario) — never by bare
  scenario id, which collides across teams. INVALID (conformance-broken) is
  never rendered as FAIL.

## The curated index card (reports.openclinai.org)

- Catalyst cards label links by the question each page answers: "Read the
  report" / "Compare the teams" / "Inspect every conversation" / "Run seed
  (JSON)".
- Entry copy is plain language; the takeaway states the decision-relevant
  facts without harness dialect. The staged `run-config.json` ships with every
  package.

## The landing page (openclinai.org)

- Catalyst is presented as an AI-assisted analytics and reporting platform;
  OpenELIS and OpenMRS are example connections, not the definition.
- One full-scenario demo video (question → checked SQL → Datasets → Widgets →
  dashboard → Superset), produced by the dual-mode Playwright spec in the
  catalyst repo (`catalyst-ui/e2e/full-scenario-demo.spec.ts`): the same steps
  run as an e2e test or a recording; cuts are authored from measured
  milestones (`scripts/author_timeline.py`) and rendered by
  `scripts/render_demo_video.py`. A recut takes a new filename (immutable
  media cache).
