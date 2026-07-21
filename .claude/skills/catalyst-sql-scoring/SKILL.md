---
name: "catalyst-sql-scoring"
description: "Score a Catalyst notebook validation run's query versions with the catalyst-judge-v1 rubric (intent_fidelity/sql_quality/schema_discipline + followup_coherence on successors), emitting judge.pass-N.jsonl. Use when asked to judge/score/evaluate a Catalyst notebook run, populate Catalyst report judge sections, or run the Catalyst LLM-as-judge layer."
argument-hint: "A Catalyst run directory (e.g. artifacts/catalyst-notebook-validation/<run> or evals/fixtures/catalyst-notebook-golden)"
metadata:
  author: "clinical-ai-validation-harness"
  rubric: "rubric.md (this skill dir)"
  schema: "specs/008-catalyst-query-workbench/contracts/catalyst-judge-v1.schema.json"
  foundation: "specs/008-catalyst-query-workbench/pccp/2026-07-21-catalyst-judge-v1.md"
user-invocable: true
disable-model-invocation: false
---

# Catalyst SQL scoring (the Catalyst judge)

You are the **judge**. Apply the Catalyst rubric ([`rubric.md`](rubric.md)) to each
executed query version in a Catalyst notebook run, scoring it against the scenario
instruction and run evidence, and write one `catalyst-judge-v1` JSONL row per
`(scenario_id, turn, version_id)` into a pass file. There is no judge-generation
CLI — the agent applying the rubric IS the judge.

Release scoring uses **exactly three independent passes** with the same recorded
provider/model/version, writing `judge.pass-1.jsonl`, `judge.pass-2.jsonl`, and
`judge.pass-3.jsonl`. Finalize with:

```bash
uv run python scripts/catalyst-judge-finalize.py <run_dir>
```

That produces deterministic `judge.jsonl` + `judge_manifest.json` (per-axis medians,
recomputed composites). Do not invent a fourth pass or mix models across passes.

## Inputs (gather these first)

1. **The run:** `<run_dir>/results.json` and scenario evidence under
   `<run_dir>/scenarios/<scenario_id>/repetition-*/`.
2. **Instructions:** scenario initial question (base, `turn=0`) and follow-up
   instruction (successor, `turn>=1`) from the suite definition / evidence.
3. **SQL + parameters:** version save / generation evidence (`04-save-base-version.json`,
   follow-up generation evidence, `version-*.json`).
4. **Execution + gold:** `06-execute-base.json` / `13-execute-successor.json` and
   `15-gold-execution-match-base.json` / `16-gold-execution-match-successor.json`
   when present. Gold FAIL is authoritative for reporting (D7); still score the judge
   axes from evidence — do not inflate scores to “rescue” a gold failure.
5. **Skip list:** omit scenarios marked `judgeSkipped` / no-judge variants. Do not
   invent rows for versions that were never executed.

## Procedure (per version)

1. Identify the version: `scenario_id`, integer `turn` (`0` base, `>=1` successor),
   and `version_id` from evidence.
2. Read the instruction for that turn and the generated SQL/parameters.
3. For successors, also read the prior version SQL and confirm whether required
   prior constraints were preserved.
4. Score applicable axes 0–3 per [`rubric.md`](rubric.md):
   - always: `intent_fidelity`, `sql_quality`, `schema_discipline`
   - successors only: `followup_coherence`
5. Write a short per-axis rationale that cites concrete evidence paths (SQL file,
   execution, gold verdict). Rationales are required fields, not optional notes.
6. Compute `composite` with D6 weights via
   `harness.catalyst.reconcile.composite_score` (or the formula in `rubric.md`).
7. Record identical `provider`, `model`, `model_version` across all three passes for
   a release run. Set `rubric_sha256` to the SHA-256 of this skill’s `rubric.md`.
8. Set `repetition` to match the pass file (`1` in `judge.pass-1.jsonl`, etc.).

## Output

Append one JSON object per judged version to `judge.pass-<N>.jsonl`. Field names are
**PINNED** by `catalyst-judge-v1.schema.json`:

```
schema = "catalyst-judge-v1",
scenario_id, turn (int), version_id, repetition ∈ {1,2,3},
provider, model, model_version, rubric_sha256, evaluated_at,
intent_fidelity, sql_quality, schema_discipline,          # 0–3
followup_coherence,                                       # successors only; omit on base
intent_fidelity_rationale, sql_quality_rationale,
schema_discipline_rationale,
followup_coherence_rationale,                             # successors only
evidence_paths[] (relative to the run dir), composite (0–100)
```

Then finalize:

```bash
uv run python scripts/catalyst-judge-finalize.py <run_dir>
```

## Caveats (carry into the published report)

- **Advisory, not gating.** Gold execution-match FAIL always reports FAIL even if
  every judge axis is 3 (D7).
- **Three-pass variance.** Single-judge LLM variance remains; medians reduce but do
  not eliminate it. Fixtures and development scores are not release evidence.
- **Evidence-bound.** Score only from run artifacts; do not use wall-clock knowledge
  or invent catalog columns.
- Note N (versions judged) and the single-judge caveat in any summary.
