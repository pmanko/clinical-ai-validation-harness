# Reports & Human Feedback — Source Brief

**Status**: Source brief — feeds `/speckit-specify` for lane **L2** (an amendment to feature 006).
**Roadmap entry**: amends the feature 006 (validation-harness-mvp) report layer; driven by reviewer feedback.
**Repo**: `clinical-ai-validation-harness` (feature branch → PR → harness-ci → `main`, squash-only).
**Companion dossier**: [`docs/lanes/L2-reports-human-feedback.md`](../../../docs/lanes/L2-reports-human-feedback.md).
**Last updated**: 2026-06-14.

This is the architectural brief for evolving the validation report into something real human reviewers
can use, and for ending the report/dashboard parity problem structurally. It is the input to Spec Kit;
generated artifacts land under `specs/006-validation-harness-mvp/` (this amends 006, it is not a new feature).

---

## 1. Problem framing

Feature 006 ships the validation report today: 0–10 rubric scores (`harness/validate/report.py`
legend + `fmt10`), a per-cell adjudication form (SC-006.5), and a `feedback.jsonl` export ("Download
feedback.jsonl" button with the optional `FEEDBACK_ENDPOINT` POST seam). It works, but it was built
for the author, not for an outside reviewer.

Two problems to solve:

1. **The report doesn't speak to a human reviewer.** Reviewer feedback (Ian): the 0–10 scores read as
   arbitrary, the rubric judgement is hidden behind a click-a-cell heatmap, there's no explanation of
   what the "AI team" even is, and the "Unsafe Answers" stat is a dead end (no link to the offending
   answers). And there's no separation between the machine-facing deep-dive and the surface a human
   should actually rank/annotate on.
2. **Report ↔ dashboard parity is enforced by discipline, and discipline has failed.** `report.py`
   (static report) and `scripts/validate-dashboard.py` (the live `:8099` dashboard) are separate
   renderers that have **diverged before** — most painfully on per-section confidence inversion. This
   is the structural fix the lane must not skip.

---

## 2. Scope

### 2.1 Reviewer-facing changes (Ian's feedback)
- **Scores as percentages**, not 0–10 (carry the underlying rubric value; change the presentation).
- **Per-scenario rubric judgement inline** with each response (today it's a click-a-cell heatmap note).
- An **"AI team" explainer** — what the tiers/roles/system prompts are, so a reviewer understands what
  produced the answer.
- The **"Unsafe Answers" stat links to the flagged answers** (jump-to, not just a count).

### 2.2 Two-part report split
- A **Claude-review deep-dive** (the machine-facing analytical view — full traces, judge rationale,
  confidence internals).
- A **human-feedback view** — answer **ranking + annotation** by a reviewer, minimal and focused. This
  view is the intake mechanism for the parked UCD / real-user requirements work.

### 2.3 Feedback export redesign
- Redesign the `feedback.jsonl` export for usability, grounded in web + repo research on what validation
  feedback is worth capturing (`specs/artifacts/planning/eval-methodology-brief.md`, the Scout rubric).
- Keep the **no-backend default**; the `FEEDBACK_ENDPOINT` POST seam stays optional. Static hosting only.

### 2.4 Parity mechanism (decided — non-negotiable in the spec)
Two parts:
1. **Extract the shared semantics into ONE module** under `harness/validate/` that both renderers import:
   the confidence-inversion rules (red→caveat+collapse, yellow→note-collapse, green→plain), the
   score→percentage formatting, and the label strings.
2. **Parity tests** that feed the same fixture run through **both** `report.py` and `validate-dashboard.py`
   and assert identical confidence treatment and score strings (extend the pattern in
   `evals/validate/test_report_confidence.py`).

Discipline-based parity is over; the shared module + parity tests are the mechanism.

---

## 3. Constraints
- **Static hosting only** (GitHub Pages compatible) — no required backend. The POST seam is opt-in.
- This **amends feature 006** — generated spec/plan/tasks update `specs/006-validation-harness-mvp/`;
  it is not a new numbered feature.
- The dashboard's `confSection` is the current source of truth for per-section confidence inversion;
  the shared module must reproduce its behavior exactly (parity tests prove it).
- Trace/role schema (`kb_search` / `medical_expert` step roles) must not be renamed — the dashboard
  correlates on it.

---

## 4. Open questions for `/speckit-clarify`
1. **Percentage mapping** — is the 0–10 → % a linear ×10, or a rubric-defined banding (e.g. safety-weighted)?
2. **Ranking model** — absolute score per answer, pairwise comparison, or ordinal rank within a scenario?
3. **One page or two** — is the deep-dive vs. human-feedback split two routes/files, or two tabs in one page?
4. **Annotation persistence** — purely client-side download (current model), or is the POST seam expected
   to be wired for a real reviewer round?
5. **AI-team explainer source** — generated from `server/levels.yaml` at render time, or authored prose?

---

## 5. References
- `harness/validate/report.py` — the static report renderer (legend, `fmt10`, confidence handling).
- `scripts/validate-dashboard.py` — the live `:8099` dashboard (`confSection` is the confidence-inversion
  source of truth).
- `evals/validate/test_report_confidence.py` — the confidence-inversion tests to extend for parity.
- `specs/artifacts/planning/eval-methodology-brief.md` — what validation feedback to capture (Scout rubric).
- `specs/006-validation-harness-mvp/spec.md` — the feature this amends (SC-006.5 adjudication form).
