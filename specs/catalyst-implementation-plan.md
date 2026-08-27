# Catalyst implementation plan

**Status:** Documentation alignment is merged (harness `5ee052f`, Catalyst
`75442c2`). Generic-connection implementation is the next work and has not
started. The Spark reference deployment is shipped upstream at the pinned FHIR
Data Pipes revision and is enabled by configuration, not built here.

`specs/catalyst-program-roadmap.md` owns product decisions and the Phase 1
comparison. This file owns implementation order, checkpoints, and status.

## Required outcome

```text
configured connection + explicit SQL dialect
  -> every readable table, view, column, and type
  -> the model and human editor receive the same information
  -> the exact selected SQL executes once
  -> rows or the error returned by the database
```

Catalyst does not own ingestion, a clinical warehouse, or a preferred database
engine. The selected reference deployment is separate:

```text
FHIR source -> FHIR Data Pipes -> Parquet -> Spark SQL
  -> Catalyst and Superset as SQL clients
```

FHIR Data Pipes ships this entire path at the revision this repository already
pins (`3ea890884d674e2f31257a2da421601f2d75b5e9`). Its own
`docker/compose-controller-spark-sql-single.yaml` runs the pipeline controller
with `FHIRDATA_GENERATEPARQUETFILES`, `FHIRDATA_CREATEHIVERESOURCETABLES`, and
`FHIRDATA_CREATEPARQUETVIEWS` defaulted to `true`, beside a
`start-thriftserver.sh` Spark service that shares the `/dwh` Parquet volume and
serves Hive Thrift on container port 10000. `config/thriftserver-hive-config.json`
registers the pipeline's tables and views into that endpoint, and upstream's
`e2e-tests/controller-spark/controller_spark_sql_validation.sh` exercises the
result. This project disabled those three flags and redirected the sink to
PostgreSQL; enabling the shipped path is configuration, not new infrastructure.

FHIR Data Pipes and Spark remain outside the Catalyst product contract: Catalyst
reaches this deployment as one configured SQL connection like any other.

## Current implementation

The harness currently pins Catalyst revision
`75442c2d1d52507b81b524d9f8a480b4a24c0550`, the squash merge of Catalyst
pull request #78. At that revision:

| Code | Current implementation | Selected implementation |
| --- | --- | --- |
| `catalyst-gateway/src/config.py::DataSourceConfig` | Requires `analytics_dsn` and a generated catalog path, with a PostgreSQL default. | Source identity, label, connection configuration or reference, explicit dialect, and optional descriptions. |
| `catalyst-gateway/src/gateway.py::_default_catalyst_service` | Builds every source with `PostgresAnalyticsAdapter`. | Builds each source from its configured connection without a preferred engine or fallback. |
| `catalyst-gateway/src/catalyst/catalog.py::Catalog` | Mixes live discovery and optional descriptions with an approval filter. | Live discovery supplies every readable relation and column; descriptions do not filter. |
| `docs/contracts/catalyst-workbench-editor-catalog-v1.schema.json` | Fixes the editor dialect to PostgreSQL and names the readable schema as a catalog. | Records the declared dialect and complete readable schema. |
| `docs/contracts/catalyst-query-v1.schema.json` and `catalyst/service.py` | Require and emit `approvedViews`, restrict relation identifiers to one PostgreSQL-shaped form, and require descriptive metadata. | Use engine-native identifiers and make descriptions optional; no approved-relation field. |
| `docker-compose.mvp.yml` | Sets `FHIRDATA_GENERATEPARQUETFILES`, `FHIRDATA_CREATEHIVERESOURCETABLES`, and `FHIRDATA_CREATEPARQUETVIEWS` to `false` and points `FHIRDATA_SINKDBCONFIGPATH` at `config/postgres-sink.json`, so the shipped warehouse never materializes. | Those three flags return to `true`, the controller uses the upstream thriftserver config, and the Spark thriftserver service joins the stack sharing the existing `data-pipes-dwh` volume. Catalyst and Superset connect to it as SQL clients. |
| `harness/catalyst/notebook_validation.py` and `harness/catalyst/cli.py` | Open a second PostgreSQL path for read-only and “gold” checks. | The harness executes selected model SQL only through Catalyst and uses reviewed design-time references. |

Every row in this table was re-checked at that revision.

Implementation reuses `AnalyticsProtocol`, `DataSourceBundle`, conversation and
notebook state, query versions, the explicit Run action, results, model-team
orchestration, and Dashboard Builder.

`catalyst-agents/` and `catalyst-mcp/` are standalone prototypes. The active
Gateway and UI do not import or call them. Their packages, environment entries,
Compose/Procfile services, and dedicated tests are removed with the generic
connection implementation.

## Physical ownership

| Location | Responsibility |
| --- | --- |
| `targets/catalyst/catalyst-gateway/` and `targets/catalyst/catalyst-ui/` | Generic connection behavior, live schema, dialect-aware model/editor context, shared connection-execution code, rows, database errors, notebook, and Dashboard Builder |
| `targets/catalyst/analytics/` and Catalyst Compose files | OpenELIS FHIR Data Pipes, Parquet, and Spark reference deployment |
| `catalyst-sources/openmrs-hiv/` | OpenMRS HIV FHIR Data Pipes, ViewDefinitions, optional descriptions, and Spark reference deployment |
| `scripts/catalyst-mvp.sh` | Combined local reference-stack lifecycle |
| `harness/catalyst/`, `datasets/validation/catalyst/`, and reporting scripts | Scenario definitions, stored references, collection, evidence, and reader report |
| med-agent-hub | Model execution and prompts; not schema discovery or SQL execution |
| Catalyst bundle code and reference-deployment files | Bundle generation and Superset's Spark connection configuration, respectively |

The OpenELIS assets live in the Catalyst repository for packaging convenience;
they are not part of the Catalyst application contract. A Dashboard Builder
`Dataset` is a saved query and execution artifact, not a data source or
restricted schema copy.

## Decisions implementation must preserve

- A source has an identity, label, connection configuration or reference, and
  explicit SQL dialect. Use the simplest configuration supported by the chosen
  client; do not add a connector framework. One implementation reads that
  configuration for every source; the engine never appears in code.
- Live discovery is authoritative. The model and editor receive every relation
  and column readable through the connection. Descriptions may enrich but cannot
  filter that information.
- Catalyst does not translate SQL between engines.
- **The engine is configuration, not code.** A source's connection string and
  declared dialect select the client; the Gateway constructs connections from
  that configuration alone. No module names an engine, no engine-specific
  branch decides behavior, and adding an engine means adding a source entry and
  whatever client library it needs — never a new adapter class or subsystem.
  PostgreSQL and Spark are two configured sources of the same generic code.
- Generated and manually edited queries use shared connection-execution code.
- Validation is advisory. Exact selected SQL reaches the connection.
- Catalyst relies on the connection's configured access, retains its time and
  returned-row limits, and records rows or the database error. The Spark
  reference path must prevent mutation of its source data and demonstrate that
  behavior with one intentional write attempt that is visibly refused.
  Production authorization is later work.
- This stage uses retained demo data with no sensitive records.
- Retained test data is reused. No reseed, restart-persistence, or local/demo
  parity proof is required.
- A ready turn's reference query is run and reviewed once when the scenario is
  designed or changed. Clarification and unsupported turns have a reviewed
  expected response and prove that no SQL ran.
- One complete suite runs once per model team. One full-context reader reviews
  the stored cases by default. The harness does not score, rank, or choose a
  winner automatically.
- Bad SQL and database errors are valid experimental observations.

## Documentation checkpoint

Current instructions state the selected product behavior and identify
implementation status directly. A source application's database and Superset's
internal state remain distinct from the selected clinical analytics path.

The current authority set includes repository guidance, READMEs, roadmaps,
specifications, open tasks, contracts, quickstarts, public descriptions,
scripts, comments, test names, artifact indexes, and links. Documents, reports,
evidence instructions, and executable gates remain only when they have a current
owner.

Machine-readable schemas describe the current code until code and schema change
together. Their contract indexes identify fields that the implementation plan
changes. A field stays only when a current product requirement still needs it.

Acceptance:

- current entry points agree on the required outcome, ownership, and decisions;
- no active instruction requires a preferred analytics engine, fixed or approved
  relation list, curated warehouse, blocking advisory validation, direct
  database replay by the harness, automatic scoring, or repeated judges;
- Feature 008 requirements, open tasks, and contracts state current behavior
  directly, without an amendment above contradictory text;
- Dashboard Builder's accepted interaction and visual scope remains intact;
- links in changed current documents resolve;
- document checks protect links, secrets, and the central architecture without
  exact prose, file hashes, task counts, or parallel status ledgers; and
- the owner approves the current authority set.

## Recommended delivery packaging

The expected sequence is a Catalyst pull request followed by a harness pull
request that pins the merged Catalyst revision. A small med-agent-hub pull
request is allowed if its current “approved catalog” prompt wording enforces
filtering rather than merely naming the complete supplied schema. Split further
only for an independently useful repository dependency; pull-request count is
not an acceptance condition.

### Catalyst pull request

#### Connection and shared schema

Use `AnalyticsProtocol` and `DataSourceBundle`. Limit common connection
behavior to availability, complete readable schema discovery, exact SQL
execution with typed parameters and bounds, and rows or the database error.
Source-specific dataset browsing is not part of this interface.

One implementation satisfies that protocol for every source, constructed from
configuration: connection string plus declared dialect in, a working connection
out. `PostgresAnalyticsAdapter` is replaced rather than joined by a Spark
sibling — a second engine-named class would recreate the coupling this work
exists to remove. Where an engine genuinely differs (identifier quoting,
parameter style, how a statement timeout and row bound are imposed, how
read-only access is asserted), the difference is expressed as declared
per-source configuration consumed by that one implementation, not as a branch
on engine identity. Use whatever client library each configured dialect needs;
record which library serves which dialect and what each one supports.

Acceptance:

- source configuration has identity, label, connection configuration, and
  explicit dialect, with no preferred-engine default or fallback;
- two sources of different dialects — the PostgreSQL demo source and the Spark
  reference source — are served by the same connection implementation from
  configuration alone, with no engine name appearing in a construction or
  control-flow decision, proven by a test that swaps dialect through
  configuration only;
- typed parameters, the time limit, the returned-row bound, and the read-only
  guarantee each have a recorded per-dialect mechanism; where a configured
  dialect cannot honor one, the limitation is recorded and surfaced rather than
  silently dropped or emulated in Catalyst;
- arbitrary fixture relations reach both the model request and editor; tests
  assert inclusion rather than a count;
- relation and column identifiers preserve the configured engine's native names
  and qualification instead of passing through a PostgreSQL-specific pattern;
- optional descriptions do not filter the readable tables and columns;
- editor completion, formatting, and validation use the declared dialect;
- advisory findings do not block exact selected SQL;
- successful rows and database errors are retained and shown;
- one unavailable source does not prevent application startup; and
- focused tests prove these behaviors without a translator, connector framework,
  second catalog service, or source-specific core interface.

**Review pause:** inspect the connection behavior and focused tests before
changing the reference deployment.

#### Spark reference deployment and product smoke

For each reference source included in the demo or comparison, enable the Spark
path FHIR Data Pipes already ships at the pinned revision. Concretely: restore
`FHIRDATA_GENERATEPARQUETFILES`, `FHIRDATA_CREATEHIVERESOURCETABLES`, and
`FHIRDATA_CREATEPARQUETVIEWS` to `true`; give the controller the upstream
thriftserver config so its tables and views register; add the thriftserver
service from upstream's `compose-controller-spark-sql-single.yaml`, sharing the
existing `data-pipes-dwh` volume at `/dwh`; and publish its Hive Thrift port.
Follow upstream's own compose and
`e2e-tests/controller-spark/controller_spark_sql_validation.sh` rather than
inventing a deployment. Every step lands as committed configuration in this
repository's Compose files and scripts — nothing here is exploratory or
throwaway, and the connection evidence below is the acceptance evidence.

Retain the PostgreSQL analytics service only for as long as another component
genuinely needs its own storage; it is no longer the clinical analytics engine.

The sources do not need to be live simultaneously unless the selected
demonstration explicitly requires that. Whether they can share a Spark endpoint
is an implementation finding; do not design a namespace service in advance.

For the Catalyst-packaged OpenELIS source, when included:

- retained demo data produces nonempty Parquet and applicable ViewDefinitions;
- one manual Spark query proves the materialized endpoint and one known fact;
- Catalyst discovers the same readable tables and returns that fact;
- one generated query is saved and restored after refresh;
- one intentionally invalid selected query reaches Spark and shows its error;
- one saved query publishes and renders through Superset;
- one displayed value is inspected against the originating Catalyst result,
  without a second database query;
- one intentional write attempt reaches the Spark connection, is visibly
  refused, and leaves source data unchanged; and
- no separate clinical analytics store, shadow copy, or fallback participates.

The direct Spark query above is a one-time connection/materialization check. Do
not build a harness, per-scenario, or per-run Spark comparison path.

The completed implementation contains no preferred-engine construction,
relation filtering, generated-catalog requirement, or separate clinical
analytics path. Source-application storage and Superset's internal metadata
storage remain unchanged. Keep only descriptions or relationships shown to help
the readable schema.

Remove the standalone `catalyst-agents` and `catalyst-mcp` packages and their
development wiring; the active Gateway/med-agent-hub path owns model execution.

**Review pause:** inspect the live browser and Superset smoke before the Catalyst
pull request merges.

### Harness pull request

Start after the Catalyst change is merged and pin that revision.

#### OpenMRS Spark deployment and scenario references

For the OpenMRS HIV source used by the Phase 1 comparison:

- retained demo data produces nonempty Parquet and applicable ViewDefinitions;
- one manual Spark query proves materialization and one known fact;
- Catalyst discovers the same readable tables without mixing another source;
- each ready-turn reference is then run once through the accepted Catalyst path
  and reviewed against retained demo data;
- clarification and unsupported expectations are reviewed without SQL;
- expected outcomes come from the accepted readable tables and columns; and
- if a real missing semantic need appears, work pauses for owner review before
  one minimal source-owned view is added.

#### Harness and report simplification

Remove `PostgresReadOnlyChecker`, `PostgresGoldExecutionChecker`, their
options and events, automatic result matching, automatic verdicts, and dedicated
tests. Do not translate them to Spark.

Acceptance:

- the runner has no direct analytics-database connection and never reruns
  reference SQL;
- each ready model turn sends selected SQL through Catalyst once and stores rows
  or the database error;
- clarification and unsupported turns execute no SQL;
- a bad model query remains visible and reviewable;
- the reader packet contains the conversation, actual model context, selected
  SQL, rows or error, static reference or expected response, shared rubric, and
  recorded versions and configuration;
- the report contains no threshold, disqualification, rank, tie-break, winner,
  judge averaging, or required repeated review;
- an incomplete collection is labelled incomplete; and
- focused runner/report tests and ordinary repository checks pass.

**Review pause:** inspect the scenario references and reader packet before paid
live model runs.

## Fresh Phase 1 comparison

Start a new result set after the Catalyst and harness pull requests and the
references are accepted. Hold the suite, rubric, data, and model-team definitions
constant for this batch and record the identities actually used. Do not require
identical machines.

Acceptance:

- every selected model team completes the same full suite once;
- every stored case contains the reader packet above;
- model mistakes and database errors remain visible observations;
- one deliberately initiated reader applies the shared rubric to the complete
  stored set with the same context for every team;
- the published report links to its evidence and makes no automatic winner or
  production-readiness claim;
- when the reader is a frontier model, the report states that its interpretation
  comes from one model-reader pass rather than independent human review; and
- the owner reviews the real product path and report before Phase 1 closeout.

Another complete measurement or reader may be chosen later. Neither is a default
gate.

## Later program work

Phase 2 defines the broader conversation product after the Phase 1 report is
reviewed. Phase 3 then completes Dashboard Builder against the binding design.
The Spark work above requires one Dataset-to-Superset regression smoke, not final
Phase 3 acceptance.

Phase 3 remains open until the live Workbench, Dataset review and library,
Widget library, Dashboard library, arrangement, and publish/import states are
compared side by side with the binding design and the required visible behavior
is accepted by the owner.

## Complexity guardrails

Do not add:

- an engine-named adapter class per database, a plugin/connector framework,
  registry, or capability-negotiation layer — one configuration-driven
  connection implementation is the target, and a per-dialect setting is not a
  framework;
- a connector framework, SQL translator, custom query engine, second catalog
  service, relation allowlist/ranking, or fixed schema/context count;
- a FHIR Data Pipes fork, namespace layer, shadow warehouse, or automatic
  fallback before a concrete failure demonstrates the need;
- PostgreSQL marts, catalog generation, reconciliation scripts, or their
  dedicated test matrices in the Spark reference deployment;
- per-run reference execution, direct Spark replay by the harness, row hashing,
  automatic factual equivalence, multiple mandatory judges, adaptive repeats,
  or numerical thresholds;
- restart, reseed, worktree-persistence, local/demo parity, exhaustive failure
  matrices, or live-database checks on every ordinary pull request; or
- production authorization or sensitive-data policy in this demo-data change.

Each pull request runs focused tests for its changes. Each reference source
actually included receives one live end-to-end proof when integrated; ordinary
pull requests do not require a live Spark service.

If the complete readable schema, thin connection behavior, or pinned FHIR Data
Pipes path fails, record the concrete failure and return to the owner before
adding selection, translation, fallback, or another subsystem.
