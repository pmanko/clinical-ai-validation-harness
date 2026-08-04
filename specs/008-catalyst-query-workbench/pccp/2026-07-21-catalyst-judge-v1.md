# PCCP-style Change Record: Catalyst Judge v1

**Status:** Approved for implementation under the Catalyst validation integration roadmap

**Date:** 2026-07-21
**Reviewer decision:** The project owner approved the full remediation roadmap, including
manual `catalyst-judge-v1` scoring with deterministic three-pass finalization.

## Modification and rationale

Catalyst notebook validation already has deterministic gold execution-match
(count / row_set / aggregate_by_key / scalar). That layer proves whether executed
SQL produces the expected result set. It does not score intent fidelity, SQL
idiom quality, schema discipline, or follow-up coherence beyond exact predicates.

This change adds an advisory LLM-as-judge rubric (`catalyst-judge-v1`) applied by
a manual agent skill. Deterministic finalization (exactly three same-model
repetitions, per-axis median, recomputed composite) and hard gold-precedence keep
judge scores from masking failed gold checks.

## Criteria, weights, and formula

Applicable axes are integers 0–3:

- `intent_fidelity`
- `sql_quality`
- `schema_discipline`
- `followup_coherence` (successor turns only)

Per-repetition composite (integer 0–100):

```
round(100 * Σ(weight × axis) / (3 * Σ(weight)))
```

- Base turns: weights 47 / 29 / 24 for intent / sql / schema
- Successor turns: weights 40 / 25 / 20 / 15 including followup_coherence

Release scoring uses three independent passes with identical recorded
provider/model/version, writing `judge.pass-1.jsonl` … `judge.pass-3.jsonl`.
Finalization writes `judge.jsonl` and `judge_manifest.json`.

## Protocol and provenance

1. Author/review the skill and schemas before wiring report/publish consumers.
2. Score only from run evidence (SQL, parameters, executions, gold verdicts).
3. Every row carries provider/model/version, rubric SHA-256, evaluated timestamp,
   per-axis rationale, and `evidence_paths[]` into the run bundle.
4. Gold execution-match FAIL always yields reported FAIL regardless of judge scores.

## Impact assessment

- Adds advisory quality scores for SQL/analytics runs without changing Scout.
- Requires new reconcile/finalize code and report sections.
- Does not authorize comparative release claims before 008-G6 + T094/T095/T111.

## Rollback

1. Remove or quarantine `judge.jsonl` / `judge_manifest.json` from published runs.
2. Revert report consumers to gold/assertion-only rendering.
3. Keep gold execution-match as the sole deterministic quality gate.

## Residual risk

- Single-judge LLM variance remains; three-pass medians reduce but do not eliminate it.
- Manual skill invocation is not a CLI-reproducible generation path; finalization and
  schema validation are the deterministic controls.
- Fixtures and development scoring are not release evidence.
