# Iterative, Governed Text-to-SQL for Catalyst

**Status:** implementation design based on primary research and live MVP failures
**Date:** 2026-07-16
**Scope:** Catalyst analytics questions generated through a Med-Agent Hub profile and validated by the clinical AI validation harness

## Decision

Catalyst should not use a one-pass `question -> SQL -> model review` pipeline.
The MVP query profile should use a bounded, evidence-producing loop:

1. resolve the question against a versioned semantic catalog;
2. generate one structured candidate with the configured Hub generation role;
3. run deterministic contract, syntax, binding, catalog, policy, and planner checks;
4. if a check fails, send only structured, actionable findings back to the
   generation role and request a complete replacement candidate;
5. stop after a small configured attempt budget or when progress stalls;
6. independently review only a deterministically clean candidate;
7. re-run every deterministic check after any model-authored revision;
8. expose the candidate for human acceptance, then execute it through the real
   read-only Catalyst path;
9. evaluate the result against scenario-specific record and aggregate evidence.

The LLM authors SQL. Deterministic code decides whether that SQL is structurally
eligible to proceed. The independent reviewer judges intent alignment but cannot
waive deterministic failures.

## Why this shape is supported by the research

- Constraining formal-language generation works. PICARD rejects inadmissible
  tokens during decoding and materially improves text-to-SQL validity. The
  current local runtime does not expose PICARD-style token constraints, so the
  practical analogue is strict structured output followed immediately by an AST
  parser and a bounded correction turn. [PICARD, EMNLP 2021](https://aclanthology.org/2021.emnlp-main.779/)
- Execution feedback is a useful correctness signal. Execution-guided decoding
  rejects faulty partial programs and improved multiple text-to-SQL systems in
  the original study. For this clinical MVP, pre-acceptance feedback should stop
  at safe parse/analyze/plan checks; result-producing execution remains behind
  explicit acceptance. [Wang et al., 2018](https://www.microsoft.com/en-us/research/publication/robust-text-to-sql-generation-with-execution-guided-decoding/)
- Decomposition matters. DIN-SQL separates schema linking, complexity handling,
  generation, and correction rather than asking one prompt to solve the whole
  problem. The Catalyst analogue is semantic linking followed by generation,
  deterministic linting, and independent review. [DIN-SQL, NeurIPS 2023](https://papers.neurips.cc/paper_files/paper/2023/hash/72223cc66f63ca1aa59edaec1b3670e6-Abstract-Conference.html)
- Real database contents matter in addition to schemas. BIRD shows that value
  comprehension, external knowledge, and SQL efficiency create failures that
  schema-only benchmarks miss. Catalyst therefore needs versioned catalog
  terminology and controlled dataset statistics, plus result-level validation
  on its real analytics view. [BIRD, NeurIPS 2023](https://arxiv.org/abs/2305.03111)
- Interactive code generation is best evaluated as actions followed by
  environment feedback, not as a single static translation. InterCode provides
  a reproducible execution-feedback environment for this framing. The harness
  should similarly preserve every attempt, finding, and outcome as a run trace.
  [InterCode, NeurIPS 2023](https://openreview.net/forum?id=fvKaLF1ns8)
- SQL string equality is an inadequate primary metric. Spider was designed to
  test generalization across both unseen SQL and unseen schemas; for Catalyst,
  behavioral assertions over the intended rows, columns, filters, and grain are
  more important than reproducing one gold SQL string. [Spider, EMNLP 2018](https://arxiv.org/abs/1809.08887)

## What the live failures tell us

The initial Gemma 4 E4B trials revealed three distinct defect classes:

| Defect class | Observed example | Correct owner |
| --- | --- | --- |
| Output contract | parameter object omitted a required `name` | JSON Schema validation and one structured correction turn |
| Semantic grounding | viral-load predicate used an unbound or non-canonical value such as `VL` | catalog linker and deterministic parameter/catalog checks |
| SQL syntax/dialect | `observed_at >= DATE :date_1` reached Catalyst | PostgreSQL parser/linter feedback before model review |

These should not be collapsed into a generic “review failed” message. Each needs
a stable finding code, a precise location, and a suggested correction that the
generator can act on.

## Proposed Hub profile pipeline

The profile remains owned by Med-Agent Hub. Catalyst sends the profile ID,
question, target, catalog, and correlation metadata; it does not select raw
models or inject role prompts.

| Stage | Owner | Produces | Gate |
| --- | --- | --- | --- |
| `context` | Hub + Catalyst catalog | immutable target, schema, semantic values, policy, prompt hashes | contract valid |
| `schema_link` | deterministic first; model only for unresolved ambiguity | referenced fields, canonical values, time concepts, expected grain | every linked identifier exists |
| `query_generate` | configured generation model | full `catalyst.query.candidate.v1` object | strict JSON Schema |
| `query_lint` | deterministic Hub linter | ordered `catalyst.query.lint.v1` findings | no error findings |
| `query_correct` | same configured generation role | complete replacement candidate, never a textual patch | attempt budget and progress rule |
| `query_plan` | read-only PostgreSQL planner | resolved identifiers/types and non-executing plan metadata | plan succeeds within limits |
| `query_review` | independently configured review role | approve or reject plus concise checks | cannot override lint/plan |
| `query_finalize` | Hub | reviewed query plus safe process trace | all gates passed |
| `preview/execute` | Catalyst | accepted read-only result table | explicit user acceptance |

For Gemma 4 E4B, start with at most three generation attempts total: one initial
candidate and two feedback-driven replacements. Temperature remains zero. Retry
limits, stage models, prompts, and inference parameters belong in the Hub profile.

## Deterministic lint panel

Findings should be accumulated when safe so one correction turn can address
multiple related defects. Checks run in a stable order:

1. **Output contract** — exact JSON object, no prose/code fence, no duplicate or
   unknown keys, required candidate fields present.
2. **SQL parse** — exactly one PostgreSQL statement parsed into an AST.
3. **Operation policy** — top-level `SELECT` or `WITH ... SELECT`; reject DDL,
   DML, transaction, copy, command, and multi-statement nodes.
4. **Catalog identifiers** — every relation is an approved fully qualified view;
   every referenced and projected field exists; no unapproved function or
   wildcard where the contract requires explicit output columns.
5. **Parameter parity** — SQL placeholders and declared parameter names are an
   exact set; names are unique; types and values match the question/catalog;
   question-derived values do not remain as ad hoc SQL literals.
6. **Semantic constraints** — named analytes bind canonical catalog values to
   the analyte field; requested dates, units, patient grain, latest/first logic,
   suppression thresholds, and aggregations are represented when applicable.
7. **Output agreement** — AST projection order and aliases agree with
   `expectedColumns` and the requested result grain.
8. **Resource policy** — bounded literal `LIMIT`, no unbounded cross join,
   approved complexity, and configurable estimated-row/cost ceilings.
9. **Database plan** — run PostgreSQL parse/analyze/planning without `ANALYZE`,
   under a read-only role, short statement/lock timeouts, and an explicit
   transaction rollback.

[SQLGlot](https://github.com/tobymao/sqlglot) supplies the dialect-aware parser,
AST traversal, syntax locations, and identifier inspection already used by the
Catalyst gateway. PostgreSQL `PREPARE` performs server-side parse, analysis, and
rewrite, while plain `EXPLAIN` plans without executing; `EXPLAIN ANALYZE` must not
be used because PostgreSQL explicitly documents that it executes the statement.
See the official [`PREPARE`](https://www.postgresql.org/docs/current/sql-prepare.html),
[`EXPLAIN`](https://www.postgresql.org/docs/current/sql-explain.html), and
[`SET TRANSACTION`](https://www.postgresql.org/docs/current/sql-set-transaction.html)
documentation.

The gateway repeats the security-critical subset before creating a preview. Hub
lint improves generation; the Catalyst boundary remains authoritative.

## Feedback contract

The generator should receive data, not a vague prose rejection. Each finding has:

```json
{
  "code": "sql.invalid_typed_parameter",
  "stage": "sql_parse",
  "severity": "error",
  "path": "sql",
  "line": 1,
  "column": 146,
  "message": "DATE cannot prefix a named bind parameter in PostgreSQL.",
  "evidence": "observed_at >= DATE :date_1",
  "suggestedAction": "Use observed_at >= :date_1 and keep date_1 typed as date."
}
```

Rules for feedback:

- codes and check ordering are stable and testable;
- messages identify the defect and constraint, not a hidden answer;
- evidence is a minimal SQL/catalog excerpt and never contains result rows or
  credentials;
- suggested actions are deterministic templates where possible;
- the next model response is a complete candidate under the same strict schema;
- every replacement is re-linted from the beginning.

## Retry and stopping policy

Retry only when all error findings are classified as correctable from supplied
context. Stop and reject when any of the following is true:

- the configured attempt budget is exhausted;
- the replacement candidate digest is identical to an earlier candidate;
- the same finding-code multiset repeats without improvement;
- a finding requires an unsupported identifier, missing clinical definition, or
  user choice;
- the candidate changes target, catalog version, approved view set, or policy;
- the model returns another malformed contract after its one contract-specific
  correction opportunity.

“Improvement” means fewer error findings or movement to a later deterministic
stage, not a model assertion that the query is better.

## Safe reasoning trace

The UI should show an observable process trace, not private chain-of-thought:

- profile ID and profile revision;
- generation and review role model IDs;
- prompt/config hashes and catalog/dataset versions;
- each attempt number, candidate digest, latency, and status;
- lint check names, stable finding codes, and concise messages;
- whether a deterministic normalization occurred;
- planner status and bounded plan summary;
- reviewer decision and check summaries;
- Catalyst policy result, preview digest, execution ID, and row/truncation facts.

Raw hidden reasoning, credentials, arbitrary model prose, and patient result rows
do not belong in the operating trace.

## Validation methodology

The validation harness should compare two profile revisions rather than report a
single successful demo. Each run emits `run_manifest.json` and `events.jsonl` and
captures all generation attempts. At minimum, report:

- ready/clarification/unsupported/rejected rate by scenario;
- strict-contract validity by attempt;
- parse, catalog, binding, semantic, planner, and policy pass rates;
- correction success rate by finding code;
- repeated-candidate and retry-exhaustion rate;
- end-to-end latency and tokens by role/attempt;
- accepted-query execution success;
- result correctness against record IDs, expected filters, output grain, and
  aggregates;
- false-ready rate, the highest-risk metric;
- truncation correctness and whether the UI disclosed it.

The first experiment matrix should cover:

1. viral-load rows since an exact date;
2. latest viral load per patient;
3. suppressed and unsuppressed cohorts with an explicit threshold definition;
4. longitudinal rise/rebound requiring multiple observations;
5. turnaround-time aggregation;
6. another analyte (CD4 or creatinine) to detect viral-load prompt overfitting;
7. ambiguous test terminology requiring clarification;
8. a field absent from the catalog returning unsupported;
9. unsafe write or unrestricted export requests returning rejected;
10. injected instructions inside the question remaining inert data.

Run each stochastic system case repeatedly even at temperature zero because the
runtime can still vary. Preserve the exact successful and failed candidates and
link aggregate rates back to their trace IDs.

## Rollout

1. Implement the linter and feedback schema as a pure, unit-tested Hub module.
2. Replace reviewer-authored repair with generator correction from deterministic
   findings; retain independent review after the candidate is clean.
3. Add safe planner validation against the isolated read-only analytics role.
4. Surface attempt/finding summaries through the Catalyst trace contract and UI.
5. Run the full scenario matrix on the pinned cohort and compare the old and new
   profile revisions.
6. Promote the profile only if false-ready remains zero in the suite and the
   correction loop materially improves clean-preview yield without hiding
   clarification or unsupported cases.

This is a material prompt and pipeline change. Its PR must include a PCCP-style
change record stating the old/new profile revisions, validation protocol, impact
assessment, rollback condition, and residual risks.

## Implementation checkpoint: 2026-07-16

The first bounded loop is implemented in the isolated Med-Agent Hub checkout:

- SQLGlot 30.12.0 supplies PostgreSQL parsing and AST inspection.
- The Gemma query profile permits three generation attempts at temperature zero.
- Findings cover parse/statement shape, operation policy, approved views and
  fields, placeholder parity, projection agreement, row-limit bounds, and
  catalog-grounded analyte constraints.
- Correction requests contain stable codes, minimal evidence, and a suggested
  action; an unchanged candidate stops the loop.
- Deterministic normalizations are restricted to question/catalog/SQL-grounded
  bindings and removal of unusable unnamed parameter objects only when all SQL
  placeholders are already accounted for.
- Every reviewer-authored replacement is re-linted before a second review.
- Failed attempt history is preserved on retry exhaustion. Successful returned
  queries include one validation check per lint attempt so Catalyst can expose
  whether a clean preview required correction.
- The full Hub suite passes: 288 tests.

Live real-model observations through `catalyst-query-gemma-e4b`:

1. Viral-load trial 1 failed the first semantic lint because the analyte was not
   canonically bound. The structured feedback turn corrected it; attempt 2
   passed lint and independent review and produced a preview.
2. A repeated viral-load trial produced a different valid SQL shape and passed.
3. The first CD4 trials repeatedly omitted a parameter name and were correctly
   rejected. Preserved traces made the repeated contract defect visible.
4. After the narrow orphan-binding normalization, the same CD4 question produced
   a valid preview using canonical `CD4 absolute count`. Accepted execution
   returned 96 rows for 96 patients. An independent database query confirmed
   exactly 96 matching records, only `CD4 absolute count`, only `Cell/µl`, dated
   2026-03-20 through 2026-04-07.

This checkpoint demonstrates that deterministic feedback can improve a real
Gemma-generated query and that the flow generalizes to a second analyte. It does
not yet establish broad text-to-SQL accuracy. Planner-only validation, the full
scenario matrix, repeated-run statistics, and richer UI process-trace rendering
remain required before promotion.
