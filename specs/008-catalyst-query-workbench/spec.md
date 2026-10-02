# Feature specification: Catalyst integration and delivery acceptance

**Status:** Current validation protocols and evidence requirements. The compatible
Harness/Catalyst/Hub baseline is merged. Staff Workbench implementation,
Dashboard Builder completion, dual-source local and server deployment, evidence,
and owner acceptance remain open.

## Purpose

The approved [four-pathway reporting roadmap](../openelis-reporting-catalyst-integration.md)
owns the new cross-project scope and order. This harness specification remains
the integration contract, not OpenELIS's reporting product specification. Its
query-backed journeys below remain required; imported Dataset acceptance adds
file upload/review/save without a fabricated query execution. Catalyst's product
specification owns that additive contract and ordinary PostgreSQL support.

This specification defines validation protocols and evidence for an already
prepared Catalyst target. Assembly, deployment and release coordination belong
to the [OpenClinAI umbrella](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md). Catalyst application behavior belongs to its
product specification; interaction and visual requirements belong to its
binding design.

For four-pathway acceptance, generated-query errors may be recovered through the
existing SQL editor. Verify retained state, explicit execution, saved provenance
and correct published results; do not require AI-only query success. The parent
roadmap owns the delivery boundary and any separately authorized model evaluation.

## Authorities

1. [plan.md](plan.md) retains experiment/acceptance context; the umbrella owns delivery coordination.
2. [tasks.md](tasks.md) owns detailed progress and acceptance evidence.
3. Catalyst [product specification](https://github.com/DIGI-UW/openelis-catalyst/blob/main/docs/specification.md)
   owns application behavior and contracts.
4. Catalyst [binding design](https://github.com/DIGI-UW/openelis-catalyst/blob/main/docs/dashboard-builder-mvp-design.md)
   owns current interaction and visual requirements.
5. The [program roadmap](../catalyst-program-roadmap.md) owns evaluation,
   comparison, and separately scheduled conversation decisions.

Frozen Catalyst Workbench mocks, research, overlap findings, and handoffs are
dated evidence, not alternate product requirements or a delivery authority.

## Product contracts and experiment observations

Catalyst's maintained product specification and binding design own source
configuration/discovery, query generation, context assembly, advisory validation,
editor behavior, immutable state, connection execution, Dataset/Widget/Dashboard
behavior, publication and importer receipts. The harness does not duplicate those
requirements or implement their transport. [API consumption](contracts/workbench-api.md)
and local machine schemas define the captured formats used by current consumers.

Design experiment cases around these observable boundaries:

- Record the selected source identity, explicit SQL dialect and complete readable schema
  snapshot actually supplied to the model/editor. Credentials are excluded.
- Capture complete instructions, actual model context and omitted-item reasons,
  writer/checker identities, settings and available prompt/configuration provenance.
- Exercise ready, clarification and unsupported outcomes. Ready selected SQL runs
  once through Catalyst; the other outcomes execute none and preserve prior work.
- Preserve exact selected SQL and typed parameters, advisory findings, query lineage,
  digests, bounded typed rows or the native database diagnostic and timing. Generated
  and manually corrected queries both remain valid observations.
- Capture follow-up, failure/retry, refresh and saved-query reuse evidence against the
  product-owned behavior. A successful old result must not be mistaken for execution
  of a changed query. Do not invent state acceptance from backend unit tests.
- For query-backed publication, retain the originating execution, saved objects,
  bundle and explicit importer receipt; inspect one rendered value against the
  captured originating result without a second database query. Imported Datasets
  retain file/source provenance without fabricated SQL or query executions.

The caller prepares Catalyst, sources, model services and Superset and supplies
connection settings, reviewed scenarios, evaluator settings, provenance and an
output directory. The umbrella owns selected revisions and workspace operations.
The harness records supplied or observed identity and explicit missing metadata;
it never reads gitlinks, enforces pins or scans product source trees.

## Evaluation boundary

The [program roadmap](../catalyst-program-roadmap.md) owns the reader-led model
comparison and separately scheduled broader conversation decisions. Each ready
reference is authored, run and reviewed once through accepted Catalyst before
comparison. Store static expected facts; clarification/unsupported cases store
reviewed expected responses based on the actual readable schema.

Collect the same complete suite and rubric for each selected team. The harness
never reruns reference SQL, connects directly to an analytics database, computes
automatic factual equivalence, applies rankings or chooses a model team. A bad
query or native SQL error is evidence, not an automatic disqualification.

Preserve full conversation, actual model context, source/dialect/schema identity,
SQL, rows/error, static reference or expected response, frozen rubric and available
model/target provenance. One full-context reader pass is the default; retain actor,
input digest and rationale. Additional runs/readers are deliberate follow-up,
not mandatory repetition. A frontier-model reader is labeled model interpretation,
not independent human review. Incomplete collection stays visible.

[Feature 006](../006-validation-harness-mvp/spec.md) owns reusable runner execution,
capture, review and offline report generation. Reports consume run-local frozen
inputs and evidence, not current targets, product files or authored dataset paths.

## Selected reference deployment

The selected demonstration will use retained demo data only:

```text
OpenELIS or OpenMRS FHIR
  -> FHIR Data Pipes -> Parquet -> Spark SQL
  -> Catalyst and Superset
```

Each reference source actually included in the demonstration or comparison MUST
prove one live source-to-browser path when integrated. Its ingestion files,
ViewDefinitions, and optional descriptions belong to the source deployment, not
Catalyst core. The retained demo data is reused; ordinary development does not
require reseeding, environment parity, or a live Spark service on every pull
request.

From the umbrella root, use its [`scripts/catalyst-mvp.sh`](https://github.com/pmanko/openclinai.org/blob/main/scripts/catalyst-mvp.sh) for lifecycle,
health, and Superset operations. It owns isolated ports, sibling Hub context,
source configuration, and the no-reseed default. Seeding and reset remain
explicit. Whether both sources can share a Spark endpoint is an implementation
finding; record and review a concrete failure before adding a namespace service,
fork, shadow warehouse, fallback path, or extra connector.

## Connection and source acceptance

The integrated connection path is accepted when:

- repository instructions and active contracts contain no conflicting engine,
  catalog, evaluation, or evidence requirements;
- a generic source exposes arbitrary readable relations to both model and editor;
- a warning does not block exact SQL and a native engine error is shown;
- FHIR Data Pipes produces nonempty Parquet and Spark exposes the expected
  reference relations;
- Catalyst completes one successful and one invalid browser query through Spark;
- one intentional write attempt reaches the Spark connection, is visibly
  refused, and leaves source data unchanged;
- one successful result is saved, published, imported, and rendered in Superset;
- the harness has no direct analytics-database or per-run reference path;
- exact merged revisions and the source, dialect, schema, query, execution,
  saved-object, bundle, and receipt identities are recorded; and
- the owner inspects the real product path.

The Dataset-to-Superset step above is a regression smoke for the generic
connection. It does not complete Dashboard Builder.

## Staff Workbench acceptance

Before Dashboard functionality expands, the complete frozen Workbench design is
deployed locally against the real OpenELIS and OpenMRS sources. Browser proof
covers the shared resizable question composer, failure and retry, preparation
without execution, Explore/Saved work, System/Light/Dark appearance, general
Advanced mode without state loss, complete nonmodal Available data browsing,
explicit execution, one full result table, honest errors and limits, accessible
provenance, focus return, and desktop, short-viewport, 640-, 390-, and
320-CSS-pixel layouts.

The proof includes a side-by-side comparison with the current binding design
and a paced walkthrough. Implementation, merge, local revision, local
deployment, self-validation, owner feedback, and owner acceptance are recorded
separately. Dashboard expansion starts after owner feedback is recorded.

## Dashboard Builder acceptance

Dashboard Builder completes only when the live Workbench, Dataset review and
library, Widget review and library, Dashboard library and arrangement, and all
publish/import states are compared side by side with the binding design. The
comparison proves immutable Dataset and Widget restore, multiple same-source
Widgets, retained arrangement, deterministic same-byte publication, receipt-
controlled status, actionable import failure, successful Superset rendering,
and one displayed value inspected against the originating Catalyst result
without another database query. Focused API, component, accessibility, type,
lint, build, and deterministic browser checks support the gate. Final acceptance
requires the owner's browser review.

## Local, server, and evidence acceptance

The umbrella owner deploys compatible reviewed revisions and prepares retained
data locally and on the demo server. Its `scripts/catalyst-mvp.sh` runs from the
umbrella root; it is not invoked by the harness. In each environment,
both OpenELIS and OpenMRS complete the real path from drafting and schema
browsing through preparation, explicit execution, refinement, Dataset save and
restore, visualization, Dashboard arrangement, publication, import, and
Superset rendering. Import operations run from the checkout that owns the
tested environment.

Archive raw footage, traces, timestamps, revisions, configuration, and receipts.
Short captions and cards remain visible for at least five seconds; longer text
uses about three words per second plus two seconds. Results and details remain
for at least eight seconds. Normal reading and interaction speed is used,
accelerated waits are labelled, holds retain captions, and captions do not cover
demonstrated content. Watch final cuts at normal speed. Supply reviewed cuts and evidence to the umbrella website owner for publication.
That owner publishes immutable videos for both sources and updates public video
and poster references together; website relocation remains separate and pending.

## Out of scope

- a curated or approved application schema;
- fixed relation counts, relation ranking, or silent context truncation;
- a universal connector framework or cross-engine SQL translation;
- a shadow analytics warehouse or automatic database fallback;
- per-run reference execution or a second direct-database comparison;
- automatic factual-equivalence scoring, numerical thresholds, or
  mandatory repeated judges;
- production authentication, authorization, row-level access, or sensitive-data
  policy for this demo-only stage;
- restart, reseed, worktree-persistence, local/demo parity, exhaustive failure
  matrices, or live-database checks on every pull request.
