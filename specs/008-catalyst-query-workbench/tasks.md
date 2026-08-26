# Feature 008 tasks — current work only

**Status:** The query notebook and binding Dashboard Builder design are
accepted. The generic connection, Phase 1 comparison, Phase 2 definition, and
final Phase 3 Dashboard Builder acceptance remain open.

## Before product code

- [ ] Review the current program roadmap, implementation plan, product
  specification, tasks, and binding Dashboard design with the owner.

## Phase 1 — generic Catalyst connection

- [ ] Replace the required analytics address and generated-catalog configuration
  with source ID, label, connection configuration or reference, explicit dialect,
  and optional non-filtering descriptions.
- [ ] Make source availability independent so one unavailable source does not
  prevent application startup or use of another source.
- [ ] Limit shared connection behavior to availability, complete readable schema
  discovery, exact SQL execution with typed parameters and bounds, and rows or
  the database error.
- [ ] Route generated and manually edited queries through the same shared
  connection-execution code.
- [ ] Supply the same source, dialect, and readable-schema snapshot to the model,
  Available data, editor, validation, and recorded execution.
- [ ] Preserve database-native relation and column identifiers and the active
  engine's qualification rules; remove the PostgreSQL-shaped name restriction.
- [ ] Make editor highlighting, formatting, and keyword/function completion use
  the declared dialect.
- [ ] Keep validation advisory and prove that a warning cannot block exact
  selected SQL.
- [ ] Add focused tests with arbitrary fixture relation names, successful
  execution, database failure, and an unavailable source. Do not assert a
  relation count.

**Pause:** Review the connection behavior and focused proof before changing a
reference deployment.

## Phase 1 — Spark reference sources

For each source actually included in the demonstration or comparison:

- [ ] Enable the pinned FHIR Data Pipes Parquet path and materialize applicable
  ViewDefinitions against retained demo data.
- [ ] Run one manual Spark query to prove materialization and one known fact.
- [ ] Connect Spark through the generic Catalyst connection and prove Catalyst
  discovers the same readable tables.
- [ ] Connect Superset to the same Spark source.
- [ ] Prove one successful browser query, one database error, and one saved
  Dataset-to-Superset render.
- [ ] Confirm the chosen Spark query path cannot mutate source data.
- [ ] Remove the separate clinical analytics store, generated catalog, copied
  marts, sink scripts, preferred-engine wiring, fallback, and dedicated tests.
- [ ] Carry forward only descriptions or relationships demonstrated to help the
  accepted readable schema.
- [ ] Remove the standalone `catalyst-agents` and `catalyst-mcp` packages and
  their development wiring; the active Gateway/med-agent-hub path owns model
  execution.

The manual Spark query is only a one-time connection/materialization check. Do
not create a per-scenario or per-run Spark comparison path.

**Pause:** Review the live Catalyst and Superset smoke before merge.

## Phase 1 — reader-led harness and scenario references

- [ ] Pin the accepted Catalyst revision.
- [ ] Confirm the OpenMRS source used by the comparison does not mix another
  source's readable schema.
- [ ] If scenario design reveals a concrete missing semantic need, pause for
  owner review before adding one minimal source-owned view.
- [ ] Remove direct analytics-database access, separate read-only and “gold”
  execution, automatic result matching, their options/events, and dedicated
  tests. Do not translate them to Spark.
- [ ] After the accepted readable schema exists, author and run each ready-turn
  reference once through Catalyst and store its expected facts.
- [ ] Review clarification and unsupported expected responses without SQL,
  including whether each data-availability question is answerable.
- [ ] Make each ready model turn execute selected SQL once through Catalyst;
  clarification and unsupported turns execute none.
- [ ] Present the conversation, actual model context, SQL, rows or error, static
  reference or expected response, rubric, and recorded configuration without an
  automatic verdict.
- [ ] Add focused tests for the simplified runner, incomplete-collection label,
  and reader packet.

**Pause:** Review the scenario references and reader packet before paid live
model runs.

## Phase 1 — fresh comparison

- [ ] Start a new result set after the generic connection, included reference
  sources, and scenario references are accepted.
- [ ] Hold the selected suite, rubric, data, and model-team definitions constant
  for this batch and record the identities actually used.
- [ ] Run the complete suite once for each selected model team.
- [ ] Verify every case contains the complete reader packet and an incomplete
  collection is labelled incomplete.
- [ ] Apply the shared rubric once through a deliberately selected full-context
  human or frontier-model reader.
- [ ] Publish the report and linked evidence without an automatic score,
  disqualification, rank, tie-break, winner, or production-readiness claim.
- [ ] Pause for owner review before Phase 1 closeout.

## Phase 2 — conversation scope

- [ ] Review the Phase 1 report with the owner.
- [ ] Define the broader conversation-mode behavior and acceptance before
  implementation. Do not infer it from Phase 1.

## Phase 3 — Dashboard Builder completion

- [ ] Cover Dataset, Widget, Dashboard, and publication actions through their
  public Gateway routes.
- [ ] Convert a successful typed execution into an immutable Dataset without
  engine-specific literal rules.
- [ ] Preserve exact SQL and typed values for the active dialect and return an
  actionable error when publication cannot represent them safely.
- [ ] Finish deterministic compatibility and reviewable suggestions for the
  accepted visualization families.
- [ ] Finish deterministic native Superset bundle generation and publication
  status based on explicit importer receipts.
- [ ] Run the real model-assisted browser workflow through Spark: ask, edit,
  format, Run, save Dataset versions, save Widgets, arrange and publish a
  Dashboard, import it, and open its stable Superset URL.
- [ ] Inspect one rendered value against the originating Catalyst result without
  a second database query.
- [ ] Compare the live Workbench, Dataset review/library, Widget review/library,
  Dashboard library/arrangement, and publish/import states side by side with the
  binding design.
- [ ] Confirm profile selection, generation/failure evidence, Clear/Restore,
  complete Available data browsing, fixed composer/thread, single editor,
  review panels, multiple Widgets, and actionable publication states remain.
- [ ] Pass focused API, component, bundle, publication, keyboard, focus, error,
  desktop, and narrow-layout checks.
- [ ] Obtain final owner acceptance of the browser-visible workflow.

Phase 3 does not require repeated model runs, restart/reset matrices, environment
parity, independent database reconciliation, or exhaustive infrastructure
failure simulation.

## Guardrails

- Use the smallest change that satisfies a current acceptance item.
- Remove behavior with no current requirement and its tests; do not preserve it behind a
  compatibility flag or port it to Spark.
- Do not add a connector framework, SQL translator, second catalog service,
  relation allowlist, schema ranking, fixed context count, shadow warehouse, or
  automatic fallback.
- Do not add per-run reference execution, result hashing, automatic factual
  equivalence, numerical thresholds, mandatory repeated readers, reseeding,
  restart-persistence proof, local/demo parity, or live Spark on every pull
  request.
- If the thin connection, complete readable schema, or pinned FHIR Data Pipes
  path fails, record the concrete failure and return to the owner before adding
  another subsystem.
