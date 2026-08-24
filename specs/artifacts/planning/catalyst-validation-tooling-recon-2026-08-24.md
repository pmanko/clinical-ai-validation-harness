# Validation-run tooling and the Catalyst integration — recon (2026-08-24)

Written while the first full Phase 1 three-team comparison ran. Everything
here was verified against the code and against three live shakeout runs on
the isolated stack; each shakeout caught real defects, all fixed and merged
the same day (harness #64, catalyst #68–#70, hub #21–#22).

## The toolchain, end to end

| Stage | Tool | State |
| --- | --- | --- |
| Run | `harness-cli catalyst run` → `harness/catalyst/notebook_validation.py` | One command runs the whole frozen comparison: `comparisonProfiles` sweeps every scenario across every team (teams outer, same frozen order), `dataSourceId` binds every request to the suite's source, `--resume <run-dir>` reuses finished (team, scenario) pairs from the incrementally written `rows.jsonl`. |
| Score | `harness/catalyst/notebook_scoring.py` | Pooled view plus per-team scores under `profiles`; the opening question is scored turn 1; byte-identical on replay (`score_run(..., as_json=True)`). |
| Watch | `scripts/validate-dashboard.py` (:8099) | Picks the newest run under `artifacts/validate/*` and `artifacts/catalyst-notebook-validation/*` by results-write time; `DASH_RUN` pins one. The matrix is (team × scenario); a catalyst cell shows PASS/FAIL, the SQL or the writer's verbatim question/refusal, expected-vs-observed outcomes per turn, each failed check's one-sentence disagreement, and the first rows the query returned. |
| Review | cell click-through | Fed by `results.jsonl` rows, which now carry `metrics.passed`, the answer, outcomes, `failedAssertions[{name, evidence}]`, and `resultPreview{columns, rows, returned}`. |
| Publish | `scripts/publish-report.sh <family> <run_dir> <slug> …` | Stages `report.html` + evidence into `artifacts/reports/<slug>/`, freezes `dashboard.html` (now for catalyst too — this was the lost "Interactive dashboard" link), appends to the curated `reports-index.json`, rebuilds `index.html`. |
| Narrate | `harness/catalyst/report.py`, `profile_comparison_report.py` | Single-run narrative; the comparison page still expects one run dir per profile (see gaps). |

## What the shakeouts caught (all fixed)

1. **Runner never sent `dataSourceId`** — the HIV comparison was silently
   answered by the OpenELIS source; discovery failed only by luck (catalog
   version mismatch). Suites now bind their source.
2. **Answering a clarification crashed the runner** — it read the editor
   snapshot off a base that doesn't exist. A turn on a session with no query
   now sends `editorSnapshot: null` (the Gateway's answered-question shape,
   catalyst #68).
3. **Acceptance criteria coupled to the model's column names** — A1–A3
   scored correct answers as wrong because the model called its count column
   `visit_count`. Comparators are now name-independent (single unambiguous
   stand-in resolution) and a failed check reports a one-sentence
   `disagreement`, not a wall of `None` diffs.
4. **Token evidence was never published** — G4 built `account_for_tokens`
   and nothing called it. The Hub now counts each role's fully rendered
   request with the model's own chat template and tokenizer (router
   `/apply-template` + `/tokenize`) against the launched `--ctx-size`
   (hub #22); the engine, service, storage and both contracts carry it to
   where the runner reads it (catalyst #70).
5. **One answer could erase hours of run** — an oversized model result
   (>5000 rows), a model query exceeding the checker's 30s statement
   timeout, and a third infrastructure failure *per scenario* rather than
   per run. All three are now scored or budgeted correctly; gold references
   that were themselves slow (B2/B3 correlated subqueries) were rewritten to
   hash-join forms returning the identical verified answers (108, 4665).
6. **The infrastructure replacement budget was per-scenario** — a
   twelve-scenario suite would have absorbed 24 failures while declaring a
   budget of two. Now per team run, as the roadmap states.

## Verified working (third shakeout, writer-only team)

A1–A4 PASS with real result tables (patient names included — the original
turn-3 gap), M1 PASS (the recorded c973eeba sequence that opened Phase 1),
M2 PASS (pinned guidance honored twice without repetition), exact token
evidence on every turn (e.g. 8,269 prompt tokens / 24,576 window / 1,024
reserve, counted by the model's own tokenizer). M3/B1 fail genuinely
(writer doesn't bind every named analyte; the checked teams get a reviewer
pass at exactly this). U1 declines correctly; U2 confabulates a
practitioner-name query — precisely what U2 exists to catch.

## Remaining gaps, in priority order

1. **`profile_comparison_report.py` predates the one-run comparison** — it
   joins several run dirs, one per profile. Adapt it to read one comparison
   run's per-team scores (small; do before publishing the comparison).
2. **`report.py` (single-run narrative) is team-blind** — evidence paths
   now nest per team (`scenarios/<team>/<scenario>/…`); the narrative page
   should section by team. (Medium.)
3. **Dashboard judge panels are ChartSearchAI-shaped** — "Judged scores"
   and "Arms" boxes render empty for catalyst runs; harmless but noisy.
   (Cosmetic.)
4. **`reconcile.py` judge composites are unused by the catalyst path** —
   deterministic gates + database answers replaced them for Phase 1, by
   design ("a model judge may be shown as advice but never replaces the
   database and rule-based checks"). Leave as is.
5. **Dashboard cell order for multi-team runs** — the "running" frontier
   marker walks cells in manifest order, which is now team-major; correct,
   but the grid renders scenario-major, so the yellow cell can look
   out of place. (Cosmetic.)

## Operating notes

- Dashboard: `python3 scripts/validate-dashboard.py` (:8099). Runs land in
  `artifacts/catalyst-notebook-validation/<run-id>/`; the newest active one
  is auto-tracked; `DASH_RUN=<run-id>` pins.
- Full comparison: `uv run harness-cli catalyst run --suite
  datasets/validation/catalyst/catalyst-phase1-comparison-v1.json
  --output-dir artifacts/catalyst-notebook-validation --postgres-dsn
  postgresql://catalyst_readonly:…@127.0.0.1:15443/catalyst_analytics_hiv`
  — interruption-safe; re-run with `--resume <run-dir>` to continue.
- Publish: `scripts/publish-report.sh catalyst <run_dir> <slug> "<title>"
  "<summary>" "<takeaway>"` — stages report + frozen dashboard and links
  both from the curated index.
