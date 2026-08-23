# HIV source and review-stage remediation

Triage of one local turn on the `openmrs-hiv` source, 2026-08-18. Question asked:
*"I want to know the number of medication requests prescribed to women, by medication type."*

Session `f12ab117-6951-49ee-8da0-18453465d981`, profile `catalyst-query-gemma-4-12b-qwen2.5-14b-checked`
(gemma-4-12b writer, qwen2.5-14b reviewer).

Everything below is measured, not inferred. Two of my own earlier hypotheses were
wrong and are recorded as such, because both would have sent the fix the wrong way.

## What the user saw

```
Query review failed: query review failed at candidate:
{'status': 'ready', 'target': {...}} is not valid under any of the given schemas
```

That is a raw `jsonschema` dump. Behind it sit four independent defects, three of
which are worse than the message suggests.

## F1 — Flat tables fan out, so every joined count is silently multiplied

`patient_flat` holds 10,669 rows for 5,384 patients. The pipeline's own
`analytics.pipeline_run_v1.resource_counts` reports `Patient: 5384`, so the row
count is ~1.98x the entity count.

The cause is a cross product over repeated FHIR fields. One patient with two
`name.given` values and two `identifier` values becomes four rows:

| id | given | identifier_value |
| --- | --- | --- |
| dd553355… | Horatio | 101-6 |
| dd553355… | Horatio | 101 |
| dd553355… | L | 101-6 |
| dd553355… | L | 101 |

`medication_flat` shows the same shape: 359 Medication resources, 477 rows (1.33x),
fanned out over repeated codings. `medication_request_flat` is clean — 43,412 rows
for 43,412 MedicationRequests — because its repeated fields are singular here.

Consequence for this question: joining requests to patients doubles every count.

| | rows |
| --- | --- |
| `medication_request_flat` | 43,412 |
| joined to `patient_flat`, `gender='female'`, as written | **57,732** |
| `count(DISTINCT r.id)` for the same filter | **28,866** |

57,732 is exactly 2x28,866. The query returned a number that looks plausible and
is wrong by a factor of two. **This is the most serious finding: it is silent.**

It is also not fixed by correcting the column name — the corrected query
(`GROUP BY med_display`) over-counts identically.

## F2 — The catalog advertises columns that can never hold data

`medication_request_flat` exposes two column families, because FHIR
`MedicationRequest.medication[x]` is a choice type and the flattener emits both
branches:

| family | source | populated |
| --- | --- | --- |
| `med_id`, `med_display` | `medicationReference` | 43,412 / 43,412 — **100%** |
| `medication_system`, `medication_code`, `medication_display` | `medicationCodeableConcept` | 0 / 43,412 — **0%** |
| `statusreason_sys`, `statusreason_code`, `statusreason_display` | `statusReason` | **0%** |

A request carries one branch or the other, never both. This export uses references
throughout, so the CodeableConcept family is uniformly empty. The real codes live in
`medication_flat` (`code_sys`, `code_code`, `code_display`, all 100% populated),
reachable via `med_id -> medication_flat.id`.

So the columns are not duplicates in the sense of redundancy — they are the two
arms of a choice type, one of which is dead in this dataset. Nothing in the served
catalog says so.

## F3 — The writer chose a dead column, and had no way to know

The writer selected `medication_display`, then `medication_code` on the follow-up.
Both exist; both are always NULL.

**Correcting an earlier hypothesis of mine:** I first assumed the catalog gave the
model no field-level grounding. It does. `GET /v1/catalyst/workbench/catalog`
serves `medication_request_flat` with all 16 fields, including both `med_display`
and `medication_display`. The model was not guessing at names — it was choosing
between two plausible ones with no signal that one is empty, and picked the more
canonical-sounding. A careful human reader would do the same.

Both executions "succeeded" and returned a single all-NULL group with
`request_count = 57732`.

## F4 — The reviewer diagnosed the problem and then failed to deliver the repair

The reviewer's full output, 961 characters of complete, valid JSON:

```json
{
  "decision": "repair",
  "checks": [ ... "field-grounding": "failed", "output-column-agreement": "failed" ... ],
  "candidate": { "status": "ready" },
  "message": "The candidate uses `medication_code` instead of `medication_display`. The output column names do not match the expected columns. Repairing the candidate to use `medication_display`."
}
```

It caught the defect. Then it *described* the repair in prose and emitted
`candidate: {"status": "ready"}` — a stub with no `sql`, `parameters`, or
`expectedColumns`. `#/$defs/candidate` requires all three, so validation failed at
`candidate`, which is the error the user saw.

**Correcting a second hypothesis:** I suspected truncation against the reviewer's
1024-token budget. It was not. The output is 961 characters and ends in a closing
brace. The model simply did not emit the repaired query.

Note also that its advice was wrong on the merits: `medication_display` is dead
too. A successful repair would have produced another useless query.

Two structural contributors:

- **The contract is documentary, not enforced.** The recorded hub request contains
  `requiredOutputContract` inside `catalystQuery`, and zero occurrences of
  `response_format`, `json_schema`, or `strict`. Validation is post-hoc. A stub
  candidate was emittable because nothing constrained decoding.
- **Two schema shapes disagree.** `REVIEW_SCHEMA` nests the repaired query under
  `candidate`; `BACKEND_REPAIR_SCHEMA` puts `sql`/`parameters`/`expectedColumns` at
  the top level alongside `decision`. The model produced a hybrid of the two.

## F5 — The failure is recorded well and surfaced badly

What the system already does right: the turn records `status: failed`,
`finalSelection.failure.stage = reviewer_output_contract`,
`code = reviewer_output_contract_failed`, the reviewer invocation carries
`outcome: contract_failed`, and the raw output is retained behind an `evidenceRef`.
The bones are good.

What is wrong:

- The HTTP response is **`201 Created`**. A failed turn is indistinguishable from a
  successful one at the API boundary.
- The user-facing text is the `jsonschema` message.
- There is **no retry**, though a malformed-candidate reviewer response is close to
  the ideal retry candidate.
- The reviewer's own useful output — two named failed checks — is thrown away in
  favour of the schema error.
- The turn proceeded with an unreviewed query rather than marking it unreviewed.

## F6 — The blank-column warning already works, and is being ignored

All four executions carried exactly the right warning:

> `medication_display` was blank or NULL in all 1 returned row. Select a populated
> column or revise the SQL expression.

So this is not a detection problem. It is a prominence problem, and a
feedback-loop problem: the warning is never fed back to the writer or reviewer.

---

# Remediation

Ordered by severity of the wrong answer produced, not by effort.

## R1 — Stop the fan-out (F1)

The only defect here that makes numbers wrong. Options, needing a decision:

1. **Fix the flattener** so repeated fields do not cross-multiply — one row per
   entity, repeated fields either dropped, first-only, or moved to child tables.
   Correct at the root; touches fhir-data-pipes config and requires a re-run.
2. **Add de-duplicated views** (`patient_v1` etc., one row per `id`) and approve
   only those for query generation, leaving `*_flat` as raw.
3. **Annotate grain in the catalog** ("~1.98 rows per patient; join with DISTINCT")
   and rely on the model. Weakest — it is advice, not a guarantee.

Recommendation: **2**, then **1** when the pipeline can be re-run. A view is the
only option that makes the correct query the easy one to write, and it can ship
without touching ingestion.

Also: `pipeline_run_v1.resource_counts` gives authoritative entity counts, so a
cheap assertion (`count(DISTINCT id)` == declared count) would have caught this at
ingest. Worth adding regardless of which option is chosen.

## R2 — Mark or hide dead columns (F2, F3)

Annotate served catalog fields with population statistics from the introspection
that already produces the `+schema.<digest>` suffix — at minimum a null fraction.
Then either omit 100%-NULL columns from the approved field list or keep them with an
explicit "empty in this dataset" marker.

Recommendation: annotate honestly, and exclude from the *suggested* field list. A
column that is NULL across 43,412 rows is never a useful projection, and the model
demonstrably cannot tell.

## R3 — Make the reviewer's repair contract real (F4)

- Pass the schema as an actual decoding constraint (`response_format` /
  `json_schema`) for writer and reviewer, and verify the hub honours it end to end.
  If the local grammar cannot handle `$ref`, inline the schema.
- Reconcile `REVIEW_SCHEMA` and `BACKEND_REPAIR_SCHEMA` onto one shape so the prompt,
  the decoder constraint and the validator agree.
- Treat a `repair` decision with no usable candidate as a **reject with diagnosis**,
  not a contract crash: keep the checks and the message, discard the stub.

## R4 — Handle failure like a first-class outcome (F5)

- Show the reviewer's failed checks and message, never the schema error.
- Retry once, bounded, when the only fault is a malformed candidate; record it as
  attempt 2 so the evidence trail stays honest.
- Decide whether a failed turn should keep returning `201`. Changing it is a contract
  change; at minimum the failure must be unmissable in the response body.
- If review cannot be applied, mark the query **unreviewed** rather than letting it
  pass as reviewed.

## R5 — Feed the blank-column warning back (F6)

Surface it at result level, and include it in the revision context so a follow-up
turn knows the previous column was empty. Add the same treatment for a suspected
fan-out (returned count exceeding the base table's row count is a strong signal).

## R6 — Decide `medication_flat`'s grain (F1, narrower)

359 resources, 477 rows, same `id` carrying different `code_code`. Decide whether the
grain is one row per Medication or one per coding, then dedupe in a view or document
it. Until then, any join to it inflates.

## Also open

- **catalyst#35** — composer flickers while scrolling; hysteresis on the
  `full`/`line`/`tucked` transitions.

## Sequencing

1. **R5** and the R1 ingest assertion — cheapest, and they make the remaining
   defects self-announcing instead of silent.
2. **R1 option 2** — de-duplicated views. Fixes the wrong numbers.
3. **R2** — kills the wrong-column class.
4. **R3** + **R4** — the correctness and UX core of the review stage.
5. **R6**, then **R1 option 1** when ingestion can be re-run.

---

# Status, 2026-08-19

Two of my findings above were wrong in ways that would have sent the fix the wrong
way. Both are corrected here rather than quietly edited above.

## R1 — done, and not where I first said

**Corrected diagnosis.** I framed F1 as a broken flattener and proposed rewriting
the ViewDefinitions with `.first()`. I proved `.first()` works in this
fhir-data-pipes build (359 Medications became 359 rows instead of 477, in an
isolated probe against a scratch database) — and then found that applying it would
have been damaging. `sql/001_analytics_hiv_v1.sql` states the layering rule in its
header: ingestion stays lossless, *"ALL curation happens here in SQL … Do not add
hand-written ingestion projections; extend these views instead."* The curated views
are built on the cross product, and `hiv_concept_mapping_v1` requires the multiple
codings to exist. The `.first()` rewrite would have destroyed concept mapping to
fix a query bug.

**Actual root cause.** `catalog-overlay.json` approves exactly three views. The
request carried twelve. `Catalog` had `approved_view_names` and `relation_names`
returning the same set, and `with_discovered_relations` rebuilt `views` from every
relation the role can read — so curation was discarded a moment after
`Catalog.load` applied it. `approved_view_names` had no callers at all.

- **catalyst#36** — discovery describes, curation approves. Verified against the
  live source: 12 relations described, 3 approved, no raw flat table among them.
- **harness#52** — a curated `hiv_medication_request_fact_v1` at one row per
  request, because with governance correct the original question had no view that
  could answer it. Verified: 43,412 rows for 43,412 requests, 28,866 for women.
  Also adds a grain assertion to `run-ingestion.sh` covering all four curated
  views — deliberately not the `*_flat` tables, whose grain is cross-product by
  design.

End to end on the local stack, the writer now produces

```sql
SELECT medication_name, COUNT(*) AS request_count
FROM analytics.hiv_medication_request_fact_v1
WHERE patient_gender = :gender AND do_not_perform = false
GROUP BY medication_name
```

which runs with no warnings, returns 30 medication types and sums to 28,866. The
`do_not_perform = false` was not requested: the column comment says those rows are
not prescriptions, and the model read it.

## R5 — already implemented; no work needed

The blank-column warning is generated, rendered in the UI as a Carbon warning
("Returned values need review"), carried in `revisionContext.executionContext`,
sent to the hub, and **present in the writer's prompt** — I confirmed the literal
strings `blank or NULL` and `medication_display` in the follow-up request. The
writer was told the column was blank and answered by choosing its sibling, which is
equally blank. So the gap was never plumbing; it was that nothing said which
columns hold data. That is R1/R2 territory, and building anything here would have
added complexity for no gain.

## R3 + R4 — done, narrower than written

**catalyst#37.** Not truncation: the reviewer's output was 961 characters of
complete, valid JSON. It diagnosed the query correctly and then emitted
`candidate: {"status": "ready"}` with no SQL, which matches no branch of the
candidate `oneOf`.

The corrective re-ask and the instruction for exactly this case already existed in
`_review`. An early `raise` when there were no deterministic findings made both
unreachable — the `else` branch was dead code. Removing it is the fix.

The failure message now leads with a sentence rather than a jsonschema string.

A first attempt of mine downgraded an unusable repair to a plain rejection in
`query_parse`. Reverted: the system deliberately distinguishes *reviewer broke its
contract* from *reviewer rejected the query*, and a test exists to hold that line.

Still open from R3: the contract is documentary, not enforced. The recorded hub
request carries `requiredOutputContract` and zero occurrences of
`response_format`, `json_schema` or `strict`, which is why a stub candidate was
emittable at all. Enforcing it at decode time spans med-agent-hub and needs the
local grammar checked against `$ref`; scoped as its own piece of work.

## R2 — mostly obviated, reassessed down

R2 existed because the model chose an always-empty column. With #36 the model only
sees curated views, whose columns are populated by construction, and with #52 the
question is answerable. What remains is narrower and lower value: annotating
genuinely sparse columns in curated views (HIV viral load has 3 results). Not
built, on purpose.

## R6 — closed inside #52

`medication_flat` (359 resources, 477 rows, same id with different codes) is
de-duplicated inside the new view before the join, and the reason is in the view's
comment. No separate change needed.

## Open

- **catalyst#35** — composer flicker; hysteresis on the scroll disclosure.
- Decode-time contract enforcement (above).
- Sparse-column annotation (above), if wanted.
