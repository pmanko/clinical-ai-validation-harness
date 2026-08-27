# Quickstart: Catalyst Query Workbench development

**Status:** The generic connection and Spark reference deployment are not yet
implemented. Begin the Phase 1 comparison after the implementation checkpoints
pass.

## Read first

1. [Catalyst program roadmap](../catalyst-program-roadmap.md)
2. [Catalyst implementation plan](../catalyst-implementation-plan.md)
3. [Feature specification](spec.md)
4. [Current tasks](tasks.md)

Initialize the two sibling targets from an isolated harness worktree:

```bash
git submodule update --init targets/catalyst targets/med-agent-hub
```

Use `scripts/catalyst-mvp.sh` for the combined stack. Do not invoke the target
Compose file alone; the harness wrapper supplies the isolated ports, sibling
Hub context, and source-deployment configuration. Seeding and reset are explicit
operations, not ordinary startup steps.

## Expected architecture

```text
FHIR source -> FHIR Data Pipes -> Parquet -> Spark SQL
  -> Catalyst and Superset
```

Catalyst source configuration supplies a stable source ID, label, connection
configuration or reference, and explicit SQL dialect. The model, Available data
view, editor, validator, and recorded execution use the same complete readable
schema.

For each reference source actually included, confirm once when integrating it:

- FHIR Data Pipes produced nonempty Parquet;
- applicable ViewDefinitions materialized;
- a manual Spark query proves the endpoint and one known fact;
- Catalyst discovers the same readable tables;
- Superset connects to the same Spark source;
- one intentional write attempt through the Spark connection is visibly
  refused and leaves source data unchanged; and
- no separate clinical analytics store or fallback participates.

The manual Spark query is a connection/materialization check. Do not build a
second harness or per-run database comparison.

## Focused Phase 1 product check

Use the retained demo data and a real configured model profile:

1. Start a session against one configured source.
2. Ask a question and inspect the model identity, dialect, and readable-schema
   context.
3. Edit or format the generated SQL.
4. Confirm advisory findings remain visible and Run remains enabled.
5. Run the exact visible query and inspect bounded typed rows.
6. Run one intentionally invalid query and inspect the database error.
7. Ask a contextual follow-up and confirm the latest editor state and prior user
   instructions are available.
8. Refresh and confirm the session, selected version, findings, and result state
   return.
9. Save the successful execution as a Dataset, publish and import it, and open
   its stable Superset URL.
10. Inspect one rendered value against the originating Catalyst result without a
    second database query.

Pause for owner review after the connection proof and again after the browser and
Superset smoke.

This Dataset-to-Superset check covers the generic connection. Final
Dashboard Builder acceptance happens in Phase 3 against
[the delivery goal](dashboard-mvp-delivery-goal.md).

## Scenario references

Do not start paid live model runs until the accepted Spark-readable source and
scenario references are reviewed.

For each ready turn:

- author and run its reference SQL once through the accepted Catalyst path;
- store concise expected facts and the shared rubric.

For clarification and unsupported turns:

- store a reviewed expected response;
- prove no SQL ran;
- determine availability from the accepted readable schema rather than an older
  restricted schema.

References are not rerun during comparison.

## Phase 1 comparison

For each selected model team:

- run the same complete suite once;
- execute each ready selected SQL once through Catalyst;
- store rows or the database error;
- retain the complete conversation, actual model context, source, dialect,
  readable-schema snapshot, SQL, reference or expected response, rubric, and
  recorded model/repository configuration.

Initiate one full-context reader pass by default. The report does not compute a
threshold, rank, disqualification, tie-break, or winner. Additional complete
runs or readers are deliberate follow-up work. When the reader is a frontier
model, state that the interpretation comes from one model-reader pass rather
than independent human review.

## Proportional checks

Run focused unit and contract tests for the code changed in a pull request. A
live end-to-end proof is required when integrating a reference source and before
the comparison, not on every unrelated pull request.

Do not add reseeding, restart-persistence, worktree-persistence, local/demo
parity, exhaustive failure matrices, per-run direct database replay, automatic
factual equivalence, or repeated-reader requirements.
