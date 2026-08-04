# Catalyst T094 — Three-Repetition Digest-Variance Analysis

**Status:** development evidence (T094 in progress; not a release claim)
**Author date:** 2026-07-21
**Run:** `5794eb05-5c63-48c9-9aa2-c04b914a3712`
under `artifacts/catalyst-validation/t094-t095-20260721T143955Z/notebook-gold/`
**Stack:** real Catalyst → Hub → PostgreSQL; Gemma 4 12B writer / Qwen 2.5 14B
reviewer; `temperature: 0`, `dryMultiplier: 0`.

## 1. Purpose

T094 requires running three fresh-session repetitions of each real-path
scenario and **reporting candidate/query digest equality or variance without
assuming reproducibility** (008 roadmap, T094/T095 acceptance execution). This
document records that comparison for the automatic matrix and characterizes the
one instance of observed variance.

`temperature: 0` reduces but does **not** guarantee determinism: sampling is
near-greedy, but tokenization, batching, and kernel non-associativity can still
flip a token. So variance is measured, not presumed absent.

## 2. Method

For each scenario the runner records, per repetition:

- **candidate digests** — SHA-256 of each model-generated SQL candidate;
- **selected-query digest** — SHA-256 of the SQL the flow actually executed;
- **gold execution-match** — the model's own SQL executed unbounded against
  PostgreSQL and compared to a hand-authored reference (count / row_set /
  aggregate_by_key / scalar).

Digest equality across reps = byte-identical generation. Digest **inequality**
is then adjudicated by the gold layer: different SQL text that returns the same
verified result set is *execution-equivalent* (benign), not a correctness fault.

Scope: 4 of the 5 T094 families ran in the automatic ×3 matrix. The fifth,
`bounded-hub-tool-failure`, is the manual family (0 automatic assertions) and is
**out of scope here** — it remains open under T094.

## 3. Results

| Scenario | Candidate digest across reps | Selected digests | Gold (×3) | Variance |
|---|---|---|---|---|
| `narrowing-unchanged-base` | `fbeb97c8…` ×3 (identical) | 1 distinct | base 962/962, succ 194/194 (row_set) | none |
| `semantic-distinct-patient-review` | `4e373581…` ×3 (identical) | 1 distinct | base 962/962 (row_set), succ scalar 96==96 | none |
| `unresolved-parameter-correction` | `0da0eef0…` ×3 (identical) | 1 distinct | succ 384/384 (row_set) | none |
| `aggregation-dirty-base-profile-switch` | rep1 `53d1ce1a…`, reps 2–3 `4f3c0d43…` | **2 distinct** | succ 4/4 months, no key/value mismatch (aggregate_by_key) | **observed — benign (see §4)** |

**Summary: 3 of 4 scenarios were fully byte-reproducible across all three
repetitions. One scenario varied in SQL text but produced the gold-verified
correct result in all three repetitions.**

## 4. The one observed variance (characterized, not just flagged)

`aggregation-dirty-base-profile-switch` produced two distinct selected-query
digests. The difference, extracted from the per-repetition generation evidence,
is a single aggregate expression:

```
  DATE_TRUNC('month', observed_at) AS observed_month,
- COUNT(observation_id) AS result_count,     -- repetition 1
+ COUNT(*)              AS result_count,      -- repetitions 2 and 3
  ...
```

`COUNT(observation_id)` and `COUNT(*)` are **execution-equivalent** whenever
`observation_id` is non-nullable (it is the row identifier), because `COUNT(col)`
only differs from `COUNT(*)` by excluding NULLs in `col`. The gold
`aggregate_by_key` check confirms this empirically: all three repetitions matched
the reference on **4/4 months with no key or value mismatch**. The variance is
therefore surface-form only — the model expressed the same intent two ways — and
carries no correctness impact.

This is the expected shape of residual `temperature: 0` nondeterminism: an
occasional semantically-neutral token flip, caught and neutralized by
execution-level ground truth rather than by brittle string comparison.

## 5. Conclusion

- The real-path pipeline is **highly reproducible**: 3/4 scenarios identical
  byte-for-byte across three fresh sessions.
- The single divergence is **bounded and explained**: one execution-equivalent
  aggregate rewrite, gold-verified correct in every repetition.
- No repetition produced an incorrect or unverifiable result. Reproducibility is
  reported as measured (not assumed), satisfying the T094 digest-variance
  requirement for the automatic matrix.

## 6. Caveats / open items

- `bounded-hub-tool-failure` (manual family) is not covered here and remains open
  under T094, alongside the live accessibility matrix.
- Single run of the matrix; this characterizes *that* run's variance, not a
  long-run stability distribution.
- Development evidence only — release claims remain reserved for the clean-pin
  path per the CVR roadmap (Amendment A1: P4/P5 gate on T094/T095/T111
  acceptance).
