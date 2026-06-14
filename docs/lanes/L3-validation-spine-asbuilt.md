# L3 — Validation spine: specs/006 as-built + close M2-F.1

**Status**: Ready — worktree exists; rebase onto current `main` before work (it was cut from an older `main`).
**Repo**: `clinical-ai-validation-harness`. Branch model: feature branch → PR → harness-ci → `main`, squash-only.
**Branch / worktree**: `docs/006-validation-spine-asbuilt` (off `main`) · `~/code/harness-wt-spine`
**Brief**: none — this is an as-built reconcile; the target spec is the home. **Spec target**: [`specs/006-validation-harness-mvp`](../../specs/006-validation-harness-mvp/spec.md) · **Index**: [`docs/dev-roadmap.md`](../dev-roadmap.md)

## What & why
`specs/006-validation-harness-mvp/spec.md` **is** the validation-spine spec ("operationalizes 003 + 012
+ 014"), but it's stale: it defers an LLM-as-judge subsystem, while `judge.jsonl` + the clinical-answer-
scoring skill shipped, and validator confidence, the run-index, and the live dashboard all postdate it.
Bring the spec to as-built and close the one substantive gap (**M2-F.1 / SC-015**). The canvas's phantom
M2/003 never materialized — 006 is the real spine; there is no new `specs/003`.

## Scope
**In:**
- Update 006 to as-built: reconcile its deferrals against what shipped (`judge.jsonl` + scoring skill, validator confidence, run-index, live dashboard).
- Execute **M2-F.1 (SC-015)**: produce the four artifacts `specs/002.../plan.md` names — `chartsearchai-live/{compose-up.log, indexer-warmup.json, search-response.json, citation-resolution.json}` — against the running `:8088` stack; **every citation must resolve to a translated demo record**.
- Fix the README slug-numbering note (says 006/007 are "reserved" while the dirs exist with real content); sweep stale spec statuses (006, 007 — verify 007 against the shipped prompt-override system).

**Out:** new evaluation depth beyond M2-F.1 (that's M4/M5, parked); standing up a second stack from the worktree.

## Merge gate
- harness CI: `pytest` + `diff-cover ≥90%` on changed lines; squash-only merge.
- The four M2-F.1 artifacts exist under `artifacts/<run>/chartsearchai-live/` and the citation-resolution check passes.
- The acceptance run **POSTs to the live `:8088` stack served from the MAIN checkout** — do NOT bring a second stack up from the worktree.

## Kickoff prompt (verbatim)
> Update `specs/006-validation-harness-mvp` to as-built: reconcile its deferrals against what shipped
> (`judge.jsonl` + scoring skill, validator confidence, run-index, live dashboard); execute M2-F.1 by
> producing the four artifacts named in `specs/002-openmrs-demo-data-2-8-remap/plan.md` row M2-F.1
> against the running `:8088` stack (indexer warmup → `POST /ws/rest/v1/chartsearchai/search` →
> citation-resolution check, per SC-015); fix the README slug-numbering note; sweep stale spec
> statuses (006, 007).
