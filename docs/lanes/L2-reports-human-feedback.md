# L2 — Reports & human feedback

**Status**: Ready — worktree exists; rebase onto current `main` before work (it was cut from an older `main`).
**Repo**: `clinical-ai-validation-harness`. Branch model: feature branch → PR → harness-ci → `main`, squash-only.
**Branch / worktree**: `feat/report-human-feedback` (off `main`) · `~/code/harness-wt-report`
**Brief**: [`specs/artifacts/planning/report-human-feedback-brief.md`](../../specs/artifacts/planning/report-human-feedback-brief.md) · **Spec target**: amends `specs/006-validation-harness-mvp` · **Index**: [`docs/dev-roadmap.md`](../dev-roadmap.md)

## What & why
Evolve feature 006's report layer for real human reviewers, and end the report↔dashboard parity
problem structurally. The 006 report ships 0–10 rubric scores, a per-cell adjudication form, and a
`feedback.jsonl` export — built for the author, not an outside reviewer. See the brief for the full design.

## Scope
**In:**
- Scores as **percentages** (not 0–10); per-scenario rubric judgement **inline** with each response.
- An **"AI team" explainer** (tiers, roles, system prompts); the **Unsafe Answers** stat links to the flagged answers.
- **Two-part split**: a Claude-review deep-dive vs. a human-feedback view with answer ranking/annotation.
- Redesign the `feedback.jsonl` export for usability; keep the no-backend default (POST seam stays optional).
- **Parity (decided, non-negotiable)**: extract confidence-inversion + score→% formatting + labels into ONE shared module under `harness/validate/` imported by both `report.py` and `validate-dashboard.py`, plus parity tests rendering one fixture through both (extend `evals/validate/test_report_confidence.py`).

**Out:** any required backend (static hosting only); a new numbered feature (this amends 006); renaming trace/role schema.

**Files touched:** `harness/validate/report.py`, `scripts/validate-dashboard.py` (the live `:8099` dashboard), the new shared-rules module under `harness/validate/`, run-index/site rendering, `evals/validate/test_report_confidence.py`.

## Merge gate
- harness CI: `pytest` + `diff-cover ≥90%` on changed lines; squash-only merge.
- Parity tests pass: one fixture rendered through both renderers asserts identical confidence treatment and score strings.

## Kickoff prompt (verbatim)
> `/speckit-specify` Report evolution for human reviewers: convert scores to percentages, surface
> per-scenario rubric judgements inline with each response, add an AI-team explainer (tiers, roles,
> system prompts), link the Unsafe Answers stat to the flagged answers, split the report into a
> Claude-review deep-dive and a human-feedback view with answer ranking/annotation, and redesign the
> existing JSON feedback download for usability — grounded in web + repo research on what validation
> feedback to capture. Static hosting only. Parity is implemented as: a shared rules module under
> `harness/validate/` imported by both `report.py` and `validate-dashboard.py`, plus parity tests
> rendering one fixture through both (extend `evals/validate/test_report_confidence.py`).
