# PCCP-style Change Record: Catalyst Judge v1

**Status:** Release-candidate evidence complete; final MS-D acceptance pending

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
- Does not authorize a release claim before CVR-G16–G18 and final MS-D
  acceptance. Amendment A1 replaced the former 008-G6 entry condition with
  recorded T094/T095/T111 acceptance; Amendment A2 orders CVR-G18 before MS-D.

## Rollback

1. Remove or quarantine `judge.jsonl` / `judge_manifest.json` from published runs.
2. Revert report consumers to gold/assertion-only rendering.
3. Keep gold execution-match as the sole deterministic quality gate.

## Residual risk

- Single-judge LLM variance remains; three-pass medians reduce but do not eliminate it.
- Manual skill invocation is not a CLI-reproducible generation path; finalization and
  schema validation are the deterministic controls.
- Fixtures and development scoring are not release evidence.

## P5 release-candidate disposition (2026-08-04)

- Clean-pin run `7e3adf47-c21f-4d8c-9595-fd73d3dbfb24` passed 13/13
  scenario repetitions, 411/411 deterministic assertions, independent
  PostgreSQL comparisons, and configured gold checks.
- Exactly three judge passes used provider `openai`, model `gpt-5.6-sol`, model
  version `runtime-reported:gpt-5.6-sol`, and the reviewed rubric digest.
  Finalization covered all 25 executed query versions.
- The public candidate is
  `https://reports.openclinai.org/catalyst-t094-release/`. Its report,
  manifests, and all 81 report-relative evidence links were fetched from the
  live host and matched the staged bundle byte-for-byte.
- The judge consistently scored one narrowing successor 63 because repetition
  3 omitted the requested `result_status = 'final'` predicate while still
  matching the current rows. Deterministic gold therefore passed, but the
  semantic weakness remains visible rather than being normalized away.
- Residual risks remain advisory-judge dependence, model-output variance even
  at temperature zero, and dataset-contingent gold matches. The rollback above
  remains valid. CVR-G18 has passed; evidence stays `development` until final
  MS-D acceptance.
